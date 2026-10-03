"""
profiling/profiler.py - User Personality, Hobbies & Lifestyle Insight Extractor.
Extracts user traits, social context, suggested captions, and merges multi-domain tags
dynamically adapted to the user's language (VI/EN) and timezone.
"""
from typing import Dict, Any, List, Set, Optional
from datetime import datetime
from core.types import UserProfileInsight, SocialContext
from core.i18n import (
    resolve_language,
    resolve_timezone,
    get_time_of_day,
    CATEGORIES_I18N,
    DEFAULT_INTERESTS_I18N,
    ENTITY_TAGS_I18N,
    SOCIAL_CONTEXT_I18N,
    TIME_OF_DAY_CONFIG,
    DEFAULT_LANGUAGE,
    DEFAULT_TIMEZONE,
)
from profiling.visual_analyzer import VisualAnalyzer


class UserProfiler:
    """
    Extracts User Profile Insights, Hobbies, Lifestyle Tags & Merged Database Tags.
    Fully aware of User Language (vi/en) and Timezone for localized feeds & memories.
    """

    @staticmethod
    def infer_social_context(people_count: int, lang: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
        """Categorizes social setting with localized descriptions based on number of persons."""
        lang_dict = SOCIAL_CONTEXT_I18N.get(lang, SOCIAL_CONTEXT_I18N[DEFAULT_LANGUAGE])

        if people_count == 0:
            cfg = lang_dict["no_people"]
            return {
                "type": "no_people",
                "people_count": 0,
                "description": cfg["description"],
            }
        elif people_count == 1:
            cfg = lang_dict["solo"]
            return {
                "type": "solo",
                "people_count": 1,
                "description": cfg["description"],
            }
        elif people_count == 2:
            cfg = lang_dict["duo"]
            return {
                "type": "duo",
                "people_count": 2,
                "description": cfg["description"],
            }
        elif 3 <= people_count <= 5:
            cfg = lang_dict["group"]
            desc = cfg["description_template"].format(count=people_count)
            return {
                "type": "group",
                "people_count": people_count,
                "description": desc,
            }
        else:
            cfg = lang_dict["crowd"]
            desc = cfg["description_template"].format(count=people_count)
            return {
                "type": "crowd",
                "people_count": people_count,
                "description": desc,
            }

    def build_profile(
        self,
        people_count: int,
        counts: Dict[str, int],
        total_objects: int,
        lang: str = DEFAULT_LANGUAGE,
        timezone_str: str = DEFAULT_TIMEZONE,
        img: Optional[Any] = None,
    ) -> UserProfileInsight:
        """
        Analyzes detected entities to establish user profile and builds merged tags for DB persistence.
        Applies multi-signal visual analysis (Billboards, Screenshots, Documents, Sunsets).
        """
        lang = resolve_language(lang)
        tz_name, tz_obj = resolve_timezone(timezone_str)
        now_local = datetime.now(tz_obj)
        time_of_day = get_time_of_day(now_local)

        detected_set = set(counts.keys())
        category_scores: Dict[str, float] = {}
        activities: List[Dict[str, Any]] = []

        # 1. Score categories based on matched objects
        for cat_key, cat_meta in CATEGORIES_I18N.items():
            matched = detected_set.intersection(cat_meta["objects"])
            if matched:
                weight = sum(counts[obj] for obj in matched)
                confidence = min(0.95, 0.40 + 0.15 * weight)
                category_scores[cat_key] = confidence
                localized_cat = cat_meta.get(lang, cat_meta[DEFAULT_LANGUAGE])
                activities.append({
                    "category": cat_key,
                    "label": localized_cat["label"],
                    "confidence": round(confidence, 2),
                    "matched_items": list(matched),
                })

        # 2. Check for Social / Charity / Group Event
        default_interests = DEFAULT_INTERESTS_I18N.get(lang, DEFAULT_INTERESTS_I18N[DEFAULT_LANGUAGE])
        if people_count >= 3:
            social_conf = min(0.92, 0.50 + 0.08 * people_count)
            is_charity_or_community = people_count >= 5 and any(
                k in counts for k in ["backpack", "bicycle", "car", "bus"]
            )
            soc_cfg = default_interests["social_and_community"]
            activities.append({
                "category": "social_and_community",
                "label": soc_cfg["label"],
                "confidence": round(social_conf, 2),
                "matched_items": ["person"] * people_count,
            })
            if is_charity_or_community:
                category_scores["social_and_community"] = social_conf

        # 3. Determine Primary Interest
        primary_tag = "#KyNiem" if lang == "vi" else "#Memories"
        if category_scores:
            primary_key = max(category_scores.items(), key=lambda x: x[1])[0]
            if primary_key == "social_and_community":
                soc_cfg = default_interests["social_and_community"]
                interest_label = soc_cfg["label"]
                tags = list(soc_cfg["tags"])
                caption = soc_cfg["caption"]
                confidence = category_scores[primary_key]
                primary_tag = soc_cfg["primary_tag"]
            else:
                cat_meta = CATEGORIES_I18N[primary_key]
                loc_cat = cat_meta.get(lang, cat_meta[DEFAULT_LANGUAGE])
                interest_label = loc_cat["label"]
                tags = list(loc_cat["tags"])
                caption = loc_cat["caption"]
                confidence = category_scores[primary_key]
                primary_tag = loc_cat["primary_tag"]
        else:
            if people_count > 0:
                primary_key = "lifestyle_portrait"
                port_cfg = default_interests["lifestyle_portrait"]
                interest_label = port_cfg["label"]
                tags = list(port_cfg["tags"])
                caption = port_cfg["caption"]
                confidence = 0.60
                primary_tag = port_cfg["primary_tag"]
            else:
                # Multi-Signal Visual & Text Composition Analysis
                signals = VisualAnalyzer.analyze(img) if img is not None else {}

                if signals.get("is_billboard"):
                    primary_key = "signboard_and_commercial"
                    cfg = default_interests["signboard_and_commercial"]
                    interest_label = cfg["label"]
                    tags = list(cfg["tags"])
                    caption = cfg["caption"]
                    confidence = 0.85
                    primary_tag = cfg["primary_tag"]
                    for kw in signals.get("extracted_keywords", []):
                        tag_name = "#" + "".join(w.capitalize() for w in kw.split())
                        if tag_name not in tags:
                            tags.append(tag_name)

                elif signals.get("is_document"):
                    primary_key = "document_and_receipt"
                    cfg = default_interests["document_and_receipt"]
                    interest_label = cfg["label"]
                    tags = list(cfg["tags"])
                    caption = cfg["caption"]
                    confidence = 0.80
                    primary_tag = cfg["primary_tag"]

                elif signals.get("is_screenshot"):
                    primary_key = "screenshot_and_app"
                    cfg = default_interests["screenshot_and_app"]
                    interest_label = cfg["label"]
                    tags = list(cfg["tags"])
                    caption = cfg["caption"]
                    confidence = 0.75
                    primary_tag = cfg["primary_tag"]

                elif signals.get("is_sunset"):
                    primary_key = "sunset_and_nature"
                    cfg = default_interests["sunset_and_nature"]
                    interest_label = cfg["label"]
                    tags = list(cfg["tags"])
                    caption = cfg["caption"]
                    confidence = 0.75
                    primary_tag = cfg["primary_tag"]

                else:
                    primary_key = "general_photo"
                    gen_cfg = default_interests["general_photo"]
                    interest_label = gen_cfg["label"]
                    tags = list(gen_cfg["tags"])
                    caption = gen_cfg["caption"]
                    confidence = 0.50
                    primary_tag = gen_cfg["primary_tag"]

        # 4. Social context
        social_context = self.infer_social_context(people_count, lang=lang)
        social_type = social_context.get("type", "solo")

        # 5. Scene summary description
        items_summary = ", ".join(f"{v} {k}" for k, v in counts.items() if k != "person")
        if people_count > 0:
            if lang == "vi":
                scene_summary = f"{people_count} người" + (f" cùng {items_summary}" if items_summary else "")
            else:
                people_label = f"{people_count} person" if people_count == 1 else f"{people_count} people"
                scene_summary = f"{people_label}" + (f" with {items_summary}" if items_summary else "")
        else:
            if primary_key == "signboard_and_commercial":
                scene_summary = "Biển hiệu quảng cáo / Địa điểm thương mại" if lang == "vi" else "Commercial signboard / Landmark"
            elif primary_key == "screenshot_and_app":
                scene_summary = "Ảnh chụp màn hình điện thoại" if lang == "vi" else "Phone screenshot"
            elif primary_key == "document_and_receipt":
                scene_summary = "Hóa đơn / Tài liệu văn bản" if lang == "vi" else "Document / Receipt"
            elif primary_key == "sunset_and_nature":
                scene_summary = "Bầu trời hoàng hôn" if lang == "vi" else "Sunset sky"
            else:
                default_scene = "Không gian tĩnh" if lang == "vi" else "Still scenery"
                scene_summary = items_summary if items_summary else default_scene

        # 6. UNIFIED MERGED TAGS GENERATION (FOR DATABASE & DOWNSTREAM AI)
        merged_tags_set: Set[str] = set()
        tag_weights: Dict[str, float] = {}

        # 6.1 Primary interest tag (weight 0.95)
        if primary_tag:
            merged_tags_set.add(primary_tag)
            tag_weights[primary_tag] = 0.95

        # 6.2 Lifestyle tags (weight 0.85 - 0.90)
        for t in tags:
            merged_tags_set.add(t)
            tag_weights[t] = 0.90

        # 6.3 Localized Object entity tags (weight 0.80)
        entity_map = ENTITY_TAGS_I18N.get(lang, ENTITY_TAGS_I18N[DEFAULT_LANGUAGE])
        for obj_name in counts.keys():
            if obj_name in entity_map:
                e_tag = entity_map[obj_name]
                merged_tags_set.add(e_tag)
                tag_weights[e_tag] = round(min(0.85, 0.70 + 0.05 * counts[obj_name]), 2)

        # 6.4 Localized Social setting tags (weight 0.75)
        social_dict = SOCIAL_CONTEXT_I18N.get(lang, SOCIAL_CONTEXT_I18N[DEFAULT_LANGUAGE])
        if social_type in social_dict and "tags" in social_dict[social_type]:
            for s_tag in social_dict[social_type]["tags"]:
                merged_tags_set.add(s_tag)
                if s_tag not in tag_weights:
                    tag_weights[s_tag] = 0.75

        # 6.5 Time-of-Day contextual tags (derived from user timezone) (weight 0.70)
        tod_config = TIME_OF_DAY_CONFIG.get(lang, TIME_OF_DAY_CONFIG[DEFAULT_LANGUAGE])
        if time_of_day in tod_config:
            for tod_tag in tod_config[time_of_day]["tags"]:
                merged_tags_set.add(tod_tag)
                if tod_tag not in tag_weights:
                    tag_weights[tod_tag] = 0.70

        # Sort merged tags by weight descending
        sorted_tags = sorted(list(merged_tags_set), key=lambda x: tag_weights.get(x, 0.5), reverse=True)

        # Search keywords (normalized without '#' for full-text search & embedding)
        search_keywords = [
            t.lstrip("#").lower().replace("_", " ") for t in sorted_tags
        ]

        return UserProfileInsight(
            primary_interest=primary_key,
            interest_label=interest_label,
            confidence=round(confidence, 2),
            lifestyle_tags=tags,
            detected_activities=activities,
            social_context=social_context,
            scene_summary=scene_summary,
            suggested_note_caption=caption,
            merged_tags=sorted_tags,
            search_keywords=search_keywords,
            tag_weights=tag_weights,
        )
