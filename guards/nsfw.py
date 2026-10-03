"""
guards/nsfw.py - Local ONNX-based NSFW Classifier.
Decoupled inference engine outputting [safe, nsfw] probabilities with threshold checking.
"""
from typing import Dict, Any, List
from pathlib import Path
import os
import numpy as np
from PIL import Image, ImageOps

try:
    import onnxruntime as ort
except ImportError:
    ort = None


class NSFWClassifier:
    """Local CPU ONNX Inference for Explicit Content Detection."""

    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        self.session = None

        if ort is not None and self.model_path.exists():
            try:
                # Optimize CPU thread allocation
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 2
                self.session = ort.InferenceSession(
                    str(self.model_path), sess_options=opts, providers=["CPUExecutionProvider"]
                )
                print(f"[NSFWClassifier] Loaded ONNX model from {self.model_path.name}")
            except Exception as err:
                print(f"[NSFWClassifier] Failed to load model ({err}). Running fallback.")
        else:
            print(f"[NSFWClassifier] Model {self.model_path.name} not found. Running in fallback mode.")

    def predict(self, img: Image.Image) -> Dict[str, float]:
        """
        Runs inference on 224x224 RGB image.
        Returns normalized probability scores: {'safe': 0.0 - 1.0, 'nsfw': 0.0 - 1.0}.
        """
        if self.session is None:
            # Fallback mock for testing or missing model
            return {"safe": 0.98, "nsfw": 0.02}

        # 1. Normalize EXIF and resize
        clean_img = ImageOps.exif_transpose(img).convert("RGB")
        resized = clean_img.resize((224, 224), Image.Resampling.BILINEAR)
        arr = np.array(resized, dtype=np.float32)

        input_meta = self.session.get_inputs()[0]
        input_name = input_meta.name
        shape = input_meta.shape

        # 2. Support NHWC (Yahoo OpenNSFW) or NCHW (PyTorch export)
        if len(shape) == 4 and shape[-1] == 3:
            # NHWC: Convert RGB to BGR and subtract ImageNet mean [104, 117, 123]
            arr = arr[:, :, ::-1] - np.array([104.0, 117.0, 123.0], dtype=np.float32)
            tensor = np.expand_dims(arr, axis=0)
        else:
            # NCHW: Normalize to [0, 1] and transpose
            arr = arr / 255.0
            tensor = np.expand_dims(np.transpose(arr, (2, 0, 1)), axis=0)

        raw_output = self.session.run(None, {input_name: tensor})[0][0]

        # 3. Softmax check if logits
        s = np.sum(raw_output)
        if s <= 0.98 or s >= 1.02 or np.any(raw_output < 0):
            e_x = np.exp(raw_output - np.max(raw_output))
            raw_output = e_x / e_x.sum()

        safe_score = float(raw_output[0]) if len(raw_output) > 0 else 0.5
        nsfw_score = float(raw_output[1]) if len(raw_output) > 1 else 0.5

        return {
            "safe": round(safe_score, 4),
            "nsfw": round(nsfw_score, 4),
        }

    def evaluate_rules(self, scores: Dict[str, float], rules: Dict[str, Any]) -> List[str]:
        """
        Dynamically evaluates model scores against thresholds in rules config.
        """
        violations = []
        max_nsfw = float(rules.get("max_nsfw", 0.70))
        min_safe = float(rules.get("min_safe", 0.30))

        if scores.get("nsfw", 0.0) > max_nsfw:
            violations.append(f"NSFW score exceeded threshold: {scores['nsfw']:.2f} > {max_nsfw:.2f}")

        if scores.get("safe", 1.0) < min_safe:
            violations.append(f"SAFE score below required threshold: {scores['safe']:.2f} < {min_safe:.2f}")

        return violations
