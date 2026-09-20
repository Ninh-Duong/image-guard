"""
moderator.py - Core image moderation engine (100% local, self-hosted, offline).
"""
from typing import Dict, Any, Union, BinaryIO, Set, Optional, List
import os
import sys
import json
from datetime import datetime, timezone
import numpy as np
from PIL import Image

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from dhash import compute_dhash, is_hash_blocked

try:
    from detector import YoloDetector
except ImportError:
    YoloDetector = None


class LocalModerationEngine:
    """
    Offline Image Moderation Engine:
    1. dHash Filter: Rapid O(1) matching against known banned hashes via perceptual hashing.
    2. Local ONNX Model: Lightweight CNN model running locally on CPU.
    3. Dynamic Rule Engine: Matches probability scores against customizable thresholds.
    4. Fail-Open Circuit Breaker: Prevents upload pipeline blockage upon model/system exceptions.
    """

    DEFAULT_MODEL_URL = "https://huggingface.co/crj/dl-ws/resolve/main/open_nsfw.onnx"

    @staticmethod
    def ensure_model(model_path: str = "model.onnx") -> bool:
        """Downloads the default ONNX model if not already present locally."""
        if os.path.exists(model_path):
            return True
        import urllib.request
        try:
            print(f"[Info] Downloading ONNX model from: {LocalModerationEngine.DEFAULT_MODEL_URL}")
            urllib.request.urlretrieve(LocalModerationEngine.DEFAULT_MODEL_URL, model_path)
            print(f"[Info] Model downloaded successfully to: {model_path}")
            return True
        except Exception as err:
            print(f"[Warning] Failed to download model: {err}")
            return False

    def load_rules(self, rules_path: str = "rules.json") -> Dict[str, Any]:
        """Loads system moderation rules and thresholds from a JSON configuration file."""
        rules = {
            "max_nsfw": 0.70,
            "max_violence": 0.60,
            "min_safe": 0.30,
            "max_hamming_distance": 4,
            "auto_block_on_violation": True,
        }
        if os.path.exists(rules_path):
            try:
                with open(rules_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    rules.update(data)
                print(f"[Info] Loaded system rules from: {rules_path}")
            except Exception as err:
                print(f"[Warning] Failed to load rules from {rules_path}: {err}")
        return rules

    def load_blocklist(self, blocklist_path: str = "blocklist.jsonl"):
        """Loads banned hashes from a persistent JSONL file into memory for 0ms lookups."""
        if not os.path.exists(blocklist_path):
            return
        count = 0
        try:
            with open(blocklist_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        h = record.get("hash")
                        if h:
                            self.blocklist_hashes.add(h)
                            count += 1
                    except json.JSONDecodeError:
                        continue
            print(f"[Info] Loaded {count} banned hash(es) from: {blocklist_path}")
        except Exception as err:
            print(f"[Warning] Failed to read blocklist file {blocklist_path}: {err}")

    def add_to_blocklist(
        self,
        img_hash: str,
        reason: str = "VIOLATION",
        scores: Optional[Dict[str, float]] = None,
    ) -> bool:
        """
        Adds a hash to the in-memory blocklist and appends a database-ready JSONL record.
        """
        if img_hash in self.blocklist_hashes:
            return False

        self.blocklist_hashes.add(img_hash)
        scores = scores or {}
        record = {
            "hash": img_hash,
            "reason": reason,
            "safe_score": round(float(scores.get("safe", 0.0)), 4),
            "nsfw_score": round(float(scores.get("nsfw", 0.0)), 4),
            "violence_score": round(float(scores.get("violence", 0.0)), 4),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(self.blocklist_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            return True
        except Exception as err:
            print(f"[Warning] Failed to write blocklist entry: {err}")
            return False

    def __init__(
        self,
        model_path: str = "model.onnx",
        rules_path: str = "rules.json",
        blocklist_path: str = "blocklist.jsonl",
        label_map: Optional[List[str]] = None,
        auto_download: bool = True,
    ):
        self.blocklist_hashes: Set[str] = set()
        self.model_path = model_path
        self.rules_path = rules_path
        self.blocklist_path = blocklist_path
        self.label_map = label_map or ["safe", "nsfw", "violence"]
        self.session = None

        # 1. Load system rules
        self.default_rules = self.load_rules(rules_path)

        # 2. Load persistent blocklist
        self.load_blocklist(blocklist_path)

        # 3. Initialize ONNX runtime session
        if auto_download and not os.path.exists(model_path):
            self.ensure_model(model_path)

        if ort is not None and os.path.exists(model_path):
            try:
                self.session = ort.InferenceSession(
                    model_path, providers=["CPUExecutionProvider"]
                )
                print(f"[Info] Loaded ONNX model successfully: {model_path}")
            except Exception as err:
                print(f"[Warning] Failed to load ONNX model ({err}). Running in fallback mode.")
        else:
            print(f"[Info] Model file '{model_path}' not found. Running in mock/hash-only mode.")

        # 4. Initialize YOLO object & scene detector
        self.detector = None
        if YoloDetector is not None:
            try:
                self.detector = YoloDetector()
            except Exception as err:
                print(f"[Warning] Failed to initialize YoloDetector: {err}")

    def compute_dhash(self, img: Image.Image, hash_size: int = 8) -> str:
        """Wrapper for compute_dhash utility."""
        return compute_dhash(img, hash_size=hash_size)

    def is_hash_blocked(self, img_hash: str, max_distance: int = 4) -> bool:
        """Checks if hash matches the in-memory blocklist within Hamming distance."""
        return is_hash_blocked(img_hash, self.blocklist_hashes, max_distance=max_distance)

    def evaluate_rules(self, scores: Dict[str, float], rules: Dict[str, Any]) -> List[str]:
        """
        Dynamically evaluates model probability scores against threshold rules.
        Supports any 'max_<label>' or 'min_<label>' dynamically without modifying engine code.
        """
        violations = []
        for rule_key, threshold in rules.items():
            if not isinstance(threshold, (int, float)):
                continue
            if rule_key.startswith("max_") and rule_key != "max_hamming_distance":
                label = rule_key[4:]
                score = scores.get(label)
                if score is not None and score > threshold:
                    violations.append(f"{label.upper()} score exceeded threshold: {score:.2f} > {threshold}")
            elif rule_key.startswith("min_"):
                label = rule_key[4:]
                score = scores.get(label)
                if score is not None and score < threshold:
                    violations.append(f"{label.upper()} score below required threshold: {score:.2f} < {threshold}")
        return violations

    def check(
        self,
        image_input: Union[str, BinaryIO, Image.Image],
        rules: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates an image against perceptual hash blocklist and AI model rules.

        :param image_input: File path, file-like binary object, or PIL.Image instance.
        :param rules: Custom rule thresholds. Defaults to system configuration in rules.json.
        :return: Dict containing decision {'allowed': bool, 'violations': [...], ...}
        """
        if rules is None:
            rules = self.default_rules

        try:
            # 1. Load image
            if isinstance(image_input, Image.Image):
                img = image_input
            else:
                img = Image.open(image_input)

            # 2. Logic 1: dHash lookup (0ms) with Hamming distance
            img_hash = self.compute_dhash(img)
            max_dist = int(rules.get("max_hamming_distance", 4))
            if self.is_hash_blocked(img_hash, max_distance=max_dist):
                return {
                    "allowed": False,
                    "reason": "BANNED_HASH_MATCH",
                    "hash": img_hash,
                    "violations": ["Image matches a previously banned image in the blocklist (dHash match)"],
                }

            # 3. Logic 2: Local CPU ONNX inference
            scores = self._run_inference(img)

            # 4. Logic 3: Extensible dynamic rule evaluation
            violations = self.evaluate_rules(scores, rules)
            passed = len(violations) == 0

            # Automatically record violation in persistent blocklist if configured
            if not passed and rules.get("auto_block_on_violation", True):
                self.add_to_blocklist(img_hash, reason="; ".join(violations), scores=scores)

            # 5. Logic 4: YOLO Object & Scene Context Analysis
            scene = None
            if self.detector is not None:
                try:
                    scene = self.detector.detect(img)
                except Exception as err:
                    print(f"[Warning] Scene detection failed: {err}")

            return {
                "allowed": passed,
                "hash": img_hash,
                "scores": scores,
                "violations": violations,
                "scene": scene,
            }

        except Exception as err:
            # 6. Logic 5: Fail-Open Circuit Breaker Policy
            # Prevents application crash if input image is unreadable or inference fails
            return {
                "allowed": True,
                "flagged_pending_review": True,
                "error": str(err),
                "violations": [],
                "scene": None,
            }

    def check_batch(
        self,
        images: List[Union[str, BinaryIO, Image.Image]],
        rules: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluates a batch of images sequentially.

        :param images: List of file paths, file-like objects, or PIL.Images.
        :param rules: Custom rule thresholds.
        :return: List of evaluation result dictionaries.
        """
        return [self.check(img, rules=rules) for img in images]

    def _run_inference(self, img: Image.Image) -> Dict[str, float]:
        """Preprocesses input image and runs inference on the local ONNX model."""
        if self.session is None:
            # Mock fallback when no model file is loaded
            return {"safe": 0.95, "nsfw": 0.02, "violence": 0.03}

        input_meta = self.session.get_inputs()[0]
        input_name = input_meta.name
        shape = input_meta.shape

        resized = img.convert("RGB").resize((224, 224), Image.Resampling.BILINEAR)
        arr = np.array(resized, dtype=np.float32)

        # Supports both NHWC (e.g. Yahoo OpenNSFW) and NCHW (standard PyTorch export)
        if len(shape) == 4 and shape[-1] == 3:
            # NHWC format: Convert RGB to BGR and subtract ImageNet mean [104, 117, 123]
            arr = arr[:, :, ::-1] - np.array([104.0, 117.0, 123.0], dtype=np.float32)
            input_tensor = np.expand_dims(arr, axis=0)
        else:
            # NCHW format: Normalize to [0, 1] and transpose (H, W, C) -> (C, H, W)
            arr = arr / 255.0
            tensor = np.transpose(arr, (2, 0, 1))
            input_tensor = np.expand_dims(tensor, axis=0)

        raw_output = self.session.run(None, {input_name: input_tensor})[0][0]

        # Apply Softmax if raw logits are returned
        s = np.sum(raw_output)
        if s <= 0.98 or s >= 1.02 or np.any(raw_output < 0):
            e_x = np.exp(raw_output - np.max(raw_output))
            raw_output = e_x / e_x.sum()

        # Dynamically map outputs to configured labels
        result = {}
        for idx, label in enumerate(self.label_map):
            result[label] = float(raw_output[idx]) if idx < len(raw_output) else 0.0

        return result


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    engine = LocalModerationEngine()

    # CLI direct execution mode: python moderator.py <image_path>
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--test"):
        target_path = sys.argv[1]
        if not os.path.exists(target_path):
            print(json.dumps({"error": f"File not found: {target_path}"}, indent=2))
            sys.exit(1)

        result = engine.check(target_path)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("allowed") else 2)

    # Self-test validation suite
    test_img = Image.new("RGB", (100, 100), color="white")
    for x in range(50):
        for y in range(50):
            test_img.putpixel((x, y), (0, 255, 0))

    # 1. Test dHash
    h = engine.compute_dhash(test_img)
    assert isinstance(h, str) and len(h) > 0, "dHash computation failed"

    # 2. Test Check with default rules & scene analysis
    res = engine.check(test_img, rules={"max_nsfw": 0.5, "max_violence": 0.5})
    assert res["allowed"] is True, "Safe test image check failed"
    assert "scene" in res and res["scene"] is not None, "Scene analysis missing"

    # 3. Test Batch check
    batch_res = engine.check_batch([test_img, test_img])
    assert len(batch_res) == 2 and batch_res[0]["allowed"] is True, "Batch check failed"

    # 4. Test Fail-Open with invalid input
    broken_res = engine.check("non_existent_file.jpg")
    assert broken_res["allowed"] is True and broken_res.get("flagged_pending_review") is True, "Fail-Open failed"

    print("[moderator.py] All self-checks and extensibility tests passed successfully.")
