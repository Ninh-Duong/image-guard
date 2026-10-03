"""
services/pipeline.py - Core Orchestration Pipeline for Image Guard & User Profiling.
Orchestrates Input Validation -> Guardrail Filter (Fail Fast) -> User Profile Extraction.
Integrated with microsecond-level Process Logging for AI Agent analysis & optimization,
and dynamically localized to user language and timezone.
"""
from typing import Dict, Any, Union, BinaryIO, Optional, List
import time
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError

from core.config import (
    RULES_PATH,
    BLOCKLIST_PATH,
    NSFW_MODEL_PATH,
    YOLO_MODEL_PATH,
    DEFAULT_RULES,
)
from core.types import GuardResult, ProcessResponse
from core.process_logger import PipelineTracer
from core.i18n import (
    resolve_language,
    resolve_timezone,
    get_time_of_day,
    DEFAULT_LANGUAGE,
    DEFAULT_TIMEZONE,
)
from guards.dhash import compute_dhash, BlocklistManager
from guards.nsfw import NSFWClassifier
from profiling.detector import ObjectDetector
from profiling.profiler import UserProfiler


class InvalidImagePayloadError(ValueError):
    """Raised when client uploads an empty or unreadable non-image payload."""
    pass


class ImageGuardService:
    """
    Main Service coordinating Image Guardrails and User Profile Insights.
    Architecture:
    1. Input Validation: Check image format and EXIF normalization.
    2. Tier 1 Guard (0ms): dHash matching against banned image blocklist.
    3. Tier 2 Guard (15-30ms): ONNX NSFW Classifier against dynamic rules.
       -> Fail-Fast: If image is blocked in Tier 1 or Tier 2, STOP immediately (saves CPU).
    4. Tier 3 Profiling: Object detection & user lifestyle/hobby extraction (only for approved photos).
       -> Localized tags and captions matching user's language and timezone.
    """

    def __init__(
        self,
        nsfw_model_path: Path = NSFW_MODEL_PATH,
        yolo_model_path: Path = YOLO_MODEL_PATH,
        rules_path: Path = RULES_PATH,
        blocklist_path: Path = BLOCKLIST_PATH,
    ):
        self.rules_path = Path(rules_path)
        self.default_rules = self.load_rules(self.rules_path)
        self.blocklist = BlocklistManager(blocklist_path)
        self.nsfw_classifier = NSFWClassifier(nsfw_model_path)
        self.detector = ObjectDetector(yolo_model_path)
        self.profiler = UserProfiler()

    def load_rules(self, rules_path: Path) -> Dict[str, Any]:
        """Loads moderation rules from JSON file, falling back to defaults."""
        rules = dict(DEFAULT_RULES)
        if rules_path.exists():
            try:
                with open(rules_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    rules.update(data)
                print(f"[ImageGuardService] Loaded rules from {rules_path.name}")
            except Exception as err:
                print(f"[ImageGuardService] Failed to load rules: {err}")
        return rules

    @staticmethod
    def _load_image(image_input: Union[str, Path, BinaryIO, bytes, Image.Image]) -> Image.Image:
        """Loads and normalizes an image with EXIF transpose."""
        try:
            if isinstance(image_input, Image.Image):
                img = image_input
            elif isinstance(image_input, bytes):
                import io
                if len(image_input) == 0:
                    raise InvalidImagePayloadError("Empty image payload (0 bytes received).")
                img = Image.open(io.BytesIO(image_input))
            else:
                img = Image.open(image_input)

            # Force load image data into memory and apply EXIF orientation
            img.load()
            return ImageOps.exif_transpose(img)
        except (UnidentifiedImageError, OSError, ValueError) as err:
            raise InvalidImagePayloadError(f"Invalid or corrupted image format: {err}")

    def process_image(
        self,
        image_input: Union[str, Path, BinaryIO, bytes, Image.Image],
        rules: Optional[Dict[str, Any]] = None,
        skip_profiling: bool = False,
        client_info: Optional[Dict[str, Any]] = None,
        lang: Optional[str] = None,
        timezone_str: Optional[str] = None,
    ) -> ProcessResponse:
        """
        Executes the full pipeline: Input Validation -> Guardrail Filter -> User Profiling.
        Records structured JSON telemetry via PipelineTracer for AI Agent review & optimization.
        Adapts merged tags, interest labels, captions, and localized time to user language and timezone.
        """
        client_info = dict(client_info or {})
        active_rules = rules if rules is not None else self.default_rules

        # 0. Resolve Language & Timezone
        accept_lang = client_info.get("accept_language")
        user_lang = resolve_language(lang, accept_language=accept_lang, tz_name=timezone_str)
        user_tz_name, user_tz_obj = resolve_timezone(timezone_str)
        now_local = datetime.now(user_tz_obj)
        time_of_day = get_time_of_day(now_local)
        local_iso = now_local.isoformat()

        client_info["resolved_language"] = user_lang
        client_info["resolved_timezone"] = user_tz_name
        client_info["time_of_day"] = time_of_day

        tracer = PipelineTracer(client_info=client_info)

        # 1. Stage 1: Input Validation
        t0 = time.perf_counter()
        try:
            img = self._load_image(image_input)
            val_ms = (time.perf_counter() - t0) * 1000.0

            raw_size = len(image_input) if isinstance(image_input, bytes) else 0
            img_meta = {
                "format": getattr(img, "format", "RGB"),
                "mode": img.mode,
                "dimensions": {"width": img.width, "height": img.height},
                "aspect_ratio": round(img.width / img.height, 2) if img.height > 0 else 1.0,
                "size_bytes": raw_size,
            }
            tracer.set_image_meta(img_meta)
            tracer.record_stage("stage_1_validation", "PASSED", val_ms, img_meta)

        except InvalidImagePayloadError as val_err:
            val_ms = (time.perf_counter() - t0) * 1000.0
            tracer.record_stage("stage_1_validation", "REJECTED", val_ms, {"error": str(val_err)})
            tracer.record_stage("stage_2_dhash_guard", "SKIPPED", 0.0, {"reason": "Validation failed"})
            tracer.record_stage("stage_3_nsfw_guard", "SKIPPED", 0.0, {"reason": "Validation failed"})
            tracer.record_stage("stage_4_yolo_detection", "SKIPPED", 0.0, {"reason": "Validation failed"})
            tracer.record_stage("stage_5_user_profiling", "SKIPPED", 0.0, {"reason": "Validation failed"})

            guard_res = GuardResult(
                allowed=False,
                reason="INVALID_IMAGE_PAYLOAD",
                violations=[str(val_err)],
                error=str(val_err),
            )
            db_rec = {
                "memory_id": f"mem_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
                "dhash": None,
                "moderation_status": "REJECTED_INVALID_PAYLOAD",
                "is_allowed": False,
                "user_language": user_lang,
                "user_timezone": user_tz_name,
                "local_created_at": local_iso,
                "time_of_day": time_of_day,
                "guard_scores": {},
                "violations": [str(val_err)],
                "tags": {"merged_tags": [], "search_keywords": [], "tag_weights": {}, "lifestyle_tags": []},
                "user_profile": None,
                "note_metadata": None,
                "detected_objects": {},
                "image_info": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            tracer.finish(is_allowed=False, guard_summary=guard_res.to_dict(), db_record=db_rec)

            return ProcessResponse(
                guard=guard_res,
                profile=None,
                execution_time_ms=val_ms,
                trace_id=tracer.trace_id,
                db_record=db_rec,
            )

        try:
            # 2. Stage 2: Tier 1 dHash Filter (0ms)
            t1 = time.perf_counter()
            img_hash = compute_dhash(img)
            max_dist = int(active_rules.get("max_hamming_distance", 4))
            is_banned = self.blocklist.is_blocked(img_hash, max_distance=max_dist)
            dhash_ms = (time.perf_counter() - t1) * 1000.0

            tracer.record_stage(
                "stage_2_dhash_guard",
                "BLOCKED" if is_banned else "PASSED",
                dhash_ms,
                {
                    "hash": img_hash,
                    "max_hamming_distance": max_dist,
                    "blocklist_size": len(self.blocklist.str_hashes),
                    "is_blocked": is_banned,
                },
            )

            if is_banned:
                # Fail-Fast: Skip NSFW and YOLO
                tracer.record_stage("stage_3_nsfw_guard", "SKIPPED", 0.0, {"reason": "Fail-Fast: Banned in dHash"})
                tracer.record_stage("stage_4_yolo_detection", "SKIPPED", 0.0, {"reason": "Fail-Fast: Banned in dHash"})
                tracer.record_stage("stage_5_user_profiling", "SKIPPED", 0.0, {"reason": "Fail-Fast: Banned in dHash"})

                guard_res = GuardResult(
                    allowed=False,
                    hash=img_hash,
                    reason="BANNED_HASH_MATCH",
                    violations=["Image matches a previously banned image in the blocklist (dHash match)."],
                )
                db_rec = {
                    "memory_id": f"mem_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
                    "dhash": img_hash,
                    "moderation_status": "BLOCKED",
                    "is_allowed": False,
                    "user_language": user_lang,
                    "user_timezone": user_tz_name,
                    "local_created_at": local_iso,
                    "time_of_day": time_of_day,
                    "guard_scores": {},
                    "violations": guard_res.violations,
                    "tags": {"merged_tags": [], "search_keywords": [], "tag_weights": {}, "lifestyle_tags": []},
                    "user_profile": None,
                    "note_metadata": None,
                    "detected_objects": {},
                    "image_info": img_meta,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                tracer.finish(is_allowed=False, guard_summary=guard_res.to_dict(), db_record=db_rec)

                elapsed = (time.perf_counter() - t0) * 1000.0
                return ProcessResponse(
                    guard=guard_res,
                    profile=None,
                    execution_time_ms=elapsed,
                    trace_id=tracer.trace_id,
                    db_record=db_rec,
                )

            # 3. Stage 3: Tier 2 Local ONNX NSFW Inference
            t2 = time.perf_counter()
            scores = self.nsfw_classifier.predict(img)
            violations = self.nsfw_classifier.evaluate_rules(scores, active_rules)
            is_allowed = len(violations) == 0
            nsfw_ms = (time.perf_counter() - t2) * 1000.0

            # Automatically persist violation to blocklist if configured
            if not is_allowed and active_rules.get("auto_block_on_violation", True):
                self.blocklist.add(img_hash, reason="; ".join(violations), scores=scores)

            tracer.record_stage(
                "stage_3_nsfw_guard",
                "PASSED" if is_allowed else "VIOLATED",
                nsfw_ms,
                {
                    "scores": scores,
                    "violations": violations,
                    "max_nsfw_rule": active_rules.get("max_nsfw", 0.70),
                },
            )

            guard_result = GuardResult(
                allowed=is_allowed,
                hash=img_hash,
                scores=scores,
                violations=violations,
            )

            # If blocked by NSFW rules or profiling explicitly skipped -> FAIL FAST
            if not is_allowed or skip_profiling:
                skip_reason = "Fail-Fast: NSFW rule violation" if not is_allowed else "Client requested skip_profile"
                tracer.record_stage("stage_4_yolo_detection", "SKIPPED", 0.0, {"reason": skip_reason})
                tracer.record_stage("stage_5_user_profiling", "SKIPPED", 0.0, {"reason": skip_reason})

                db_rec = {
                    "memory_id": f"mem_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
                    "dhash": img_hash,
                    "moderation_status": "APPROVED" if is_allowed else "BLOCKED",
                    "is_allowed": is_allowed,
                    "user_language": user_lang,
                    "user_timezone": user_tz_name,
                    "local_created_at": local_iso,
                    "time_of_day": time_of_day,
                    "guard_scores": scores,
                    "violations": violations,
                    "tags": {"merged_tags": [], "search_keywords": [], "tag_weights": {}, "lifestyle_tags": []},
                    "user_profile": None,
                    "note_metadata": None,
                    "detected_objects": {},
                    "image_info": img_meta,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                tracer.finish(is_allowed=is_allowed, guard_summary=guard_result.to_dict(), db_record=db_rec)

                elapsed = (time.perf_counter() - t0) * 1000.0
                return ProcessResponse(
                    guard=guard_result,
                    profile=None,
                    execution_time_ms=elapsed,
                    trace_id=tracer.trace_id,
                    db_record=db_rec,
                )

            # 4. Stage 4: YOLOv8 Object Detection
            t3 = time.perf_counter()
            detections = self.detector.detect(img)
            yolo_ms = (time.perf_counter() - t3) * 1000.0

            tracer.record_stage(
                "stage_4_yolo_detection",
                "COMPLETED",
                yolo_ms,
                {
                    "people_count": detections["people_count"],
                    "counts": detections["counts"],
                    "total_objects": detections["total_objects"],
                },
            )

            # 5. Stage 5: User Personality & Hobby Profiling (Localized to Language & Timezone)
            t4 = time.perf_counter()
            user_profile = self.profiler.build_profile(
                people_count=detections["people_count"],
                counts=detections["counts"],
                total_objects=detections["total_objects"],
                lang=user_lang,
                timezone_str=user_tz_name,
                img=img,
            )
            profiling_ms = (time.perf_counter() - t4) * 1000.0

            tracer.record_stage(
                "stage_5_user_profiling",
                "COMPLETED",
                profiling_ms,
                {
                    "language": user_lang,
                    "timezone": user_tz_name,
                    "time_of_day": time_of_day,
                    "primary_interest": user_profile.primary_interest,
                    "interest_label": user_profile.interest_label,
                    "confidence": user_profile.confidence,
                    "lifestyle_tags_count": len(user_profile.lifestyle_tags),
                    "merged_tags_count": len(user_profile.merged_tags),
                    "social_type": user_profile.social_context.get("type"),
                },
            )

            # Construct Complete Database-Ready Record
            time_display = (
                now_local.strftime("%H:%M - %d/%m/%Y")
                if user_lang == "vi"
                else now_local.strftime("%I:%M %p - %b %d, %Y")
            )
            db_record = {
                "memory_id": f"mem_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
                "dhash": img_hash,
                "moderation_status": "APPROVED",
                "is_allowed": True,
                "user_language": user_lang,
                "user_timezone": user_tz_name,
                "local_created_at": local_iso,
                "time_of_day": time_of_day,
                "guard_scores": scores,
                "violations": [],
                "user_profile": {
                    "primary_interest": user_profile.primary_interest,
                    "interest_label": user_profile.interest_label,
                    "confidence": user_profile.confidence,
                    "social_setting": user_profile.social_context.get("type"),
                    "people_count": user_profile.social_context.get("people_count", 0),
                    "scene_summary": user_profile.scene_summary,
                },
                "note_metadata": {
                    "suggested_caption": user_profile.suggested_note_caption,
                    "local_time_display": time_display,
                    "time_of_day": time_of_day,
                    "timezone": user_tz_name,
                    "language": user_lang,
                },
                "tags": {
                    "merged_tags": user_profile.merged_tags,
                    "search_keywords": user_profile.search_keywords,
                    "tag_weights": user_profile.tag_weights,
                    "lifestyle_tags": user_profile.lifestyle_tags,
                },
                "detected_objects": detections["counts"],
                "image_info": img_meta,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            tracer.finish(
                is_allowed=True,
                guard_summary=guard_result.to_dict(),
                profile_summary=user_profile.to_dict(),
                db_record=db_record,
            )

            elapsed = (time.perf_counter() - t0) * 1000.0
            return ProcessResponse(
                guard=guard_result,
                profile=user_profile,
                execution_time_ms=elapsed,
                trace_id=tracer.trace_id,
                db_record=db_record,
            )

        except Exception as internal_err:
            # 6. Fail-Open Circuit Breaker
            elapsed = (time.perf_counter() - t0) * 1000.0
            print(f"[ImageGuardService] Internal error during processing: {internal_err}")
            tracer.record_stage("circuit_breaker", "TRIGGERED", elapsed, {"error": str(internal_err)})

            guard_res = GuardResult(
                allowed=True,
                hash=None,
                flagged_pending_review=True,
                reason="CIRCUIT_BREAKER_INTERNAL_ERROR",
                error=str(internal_err),
            )
            db_rec = {
                "memory_id": f"mem_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
                "dhash": None,
                "moderation_status": "FLAGGED_PENDING_REVIEW",
                "is_allowed": True,
                "user_language": user_lang,
                "user_timezone": user_tz_name,
                "local_created_at": local_iso,
                "time_of_day": time_of_day,
                "guard_scores": {},
                "violations": [],
                "tags": {"merged_tags": [], "search_keywords": [], "tag_weights": {}, "lifestyle_tags": []},
                "user_profile": None,
                "note_metadata": None,
                "detected_objects": {},
                "image_info": img_meta if "img_meta" in locals() else {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            tracer.finish(is_allowed=True, guard_summary=guard_res.to_dict(), db_record=db_rec)

            return ProcessResponse(
                guard=guard_res,
                profile=None,
                execution_time_ms=elapsed,
                trace_id=tracer.trace_id,
                db_record=db_rec,
            )
