"""
detector.py - Lightweight YOLOv8 Object Detection and Scene Context Analyzer.
100% offline, powered by ONNX Runtime and pure NumPy (no ultralytics dependency).
"""
from typing import Dict, Any, List, Union
from collections import Counter
from pathlib import Path
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
from PIL import Image

try:
    import onnxruntime as ort
except ImportError:
    ort = None

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
    "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop",
    "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

DEFAULT_MODEL_PATH = str(Path(__file__).parent / "yolov8n.onnx")


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = 0.45) -> List[int]:
    """Pure NumPy Non-Maximum Suppression (NMS)."""
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        union = areas[i] + areas[order[1:]] - inter
        ovr = np.where(union > 0, inter / union, 0.0)

        inds = np.where(ovr <= iou_threshold)[0]
        order = order[inds + 1]
    return keep


class YoloDetector:
    """Offline YOLOv8 Object Detection and Context Extraction Engine."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = model_path
        self.session = None
        if ort is not None and os.path.exists(model_path):
            try:
                self.session = ort.InferenceSession(
                    model_path, providers=["CPUExecutionProvider"]
                )
                print(f"[Info] Loaded YOLO detector successfully: {model_path}")
            except Exception as err:
                print(f"[Warning] Failed to initialize YOLO session: {err}")

    def detect(
        self,
        img: Image.Image,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
    ) -> Dict[str, Any]:
        """Runs object detection, counts instances, and infers scene context."""
        if self.session is None:
            return {
                "summary": "Detector chưa được nạp (chế độ dự phòng)",
                "people_count": 0,
                "scene_tag": "Không xác định",
                "counts": {},
                "total_objects": 0,
            }

        # 1. Preprocessing: Resize to 640x640, float32, NCHW
        orig_w, orig_h = img.size
        resized = img.convert("RGB").resize((640, 640), Image.Resampling.BILINEAR)
        arr = np.array(resized, dtype=np.float32) / 255.0
        tensor = np.transpose(arr, (2, 0, 1))[None, :]

        # 2. Inference
        input_name = self.session.get_inputs()[0].name
        raw = self.session.run(None, {input_name: tensor})[0]  # (1, 84, 8400)
        output = raw[0].T  # (8400, 84)

        # 3. Filter candidates
        boxes_raw = output[:, :4]  # cx, cy, w, h
        class_scores = output[:, 4:]  # (8400, 80)
        class_ids = np.argmax(class_scores, axis=1)
        max_scores = np.max(class_scores, axis=1)

        mask = max_scores >= conf_threshold
        if not np.any(mask):
            return {
                "summary": "Không phát hiện đối tượng rõ ràng",
                "people_count": 0,
                "scene_tag": "Bình thường",
                "counts": {},
                "total_objects": 0,
            }

        cand_boxes = boxes_raw[mask]
        cand_scores = max_scores[mask]
        cand_classes = class_ids[mask]

        # Convert cx, cy, w, h (640 scale) -> x1, y1, x2, y2 (original scale)
        scale_x = orig_w / 640.0
        scale_y = orig_h / 640.0
        x1 = (cand_boxes[:, 0] - cand_boxes[:, 2] / 2.0) * scale_x
        y1 = (cand_boxes[:, 1] - cand_boxes[:, 3] / 2.0) * scale_y
        x2 = (cand_boxes[:, 0] + cand_boxes[:, 2] / 2.0) * scale_x
        y2 = (cand_boxes[:, 1] + cand_boxes[:, 3] / 2.0) * scale_y
        converted_boxes = np.column_stack([x1, y1, x2, y2])

        # 4. Non-Maximum Suppression per class
        kept_indices = []
        for cid in np.unique(cand_classes):
            c_mask = np.where(cand_classes == cid)[0]
            c_keep = _nms(converted_boxes[c_mask], cand_scores[c_mask], iou_threshold)
            kept_indices.extend(c_mask[c_keep])

        detected_labels = [COCO_CLASSES[cand_classes[idx]] for idx in kept_indices]
        counts = dict(Counter(detected_labels))
        people_count = counts.get("person", 0)

        # 5. Rule-based Scene Context Inference
        scene_tag = self._infer_scene(people_count, counts)
        summary = self._build_summary(people_count, counts, scene_tag)

        return {
            "summary": summary,
            "people_count": people_count,
            "scene_tag": scene_tag,
            "counts": counts,
            "total_objects": len(kept_indices),
        }

    @staticmethod
    def _infer_scene(people: int, counts: Dict[str, int]) -> str:
        """Determines scene category from detected entities."""
        has_office = any(k in counts for k in ["laptop", "chair", "dining table", "tv", "keyboard"])
        has_traffic = any(k in counts for k in ["car", "bus", "truck", "motorcycle", "bicycle", "traffic light"])
        has_dining = any(k in counts for k in ["bottle", "cup", "wine glass", "fork", "knife", "pizza", "sandwich", "bowl"])
        has_living = any(k in counts for k in ["couch", "bed", "refrigerator", "sink", "microwave"])
        has_nature = any(k in counts for k in ["dog", "cat", "bird", "horse", "sheep", "cow"])

        if people >= 2 and has_office:
            return "Văn phòng / Họp nhóm / Làm việc"
        elif people == 1 and has_office:
            return "Bàn làm việc cá nhân / Công nghệ"
        elif has_traffic:
            return "Giao thông / Đường phố ngoài trời"
        elif has_dining:
            return "Ăn uống / Quán ăn / Bàn tiệc"
        elif has_living:
            return "Không gian sinh hoạt trong nhà"
        elif has_nature:
            return "Thú cưng / Động vật / Ngoài trời"
        elif people >= 3:
            return "Đám đông / Sự kiện"
        elif people == 1:
            return "Chân dung cá nhân"
        return "Bối cảnh thông thường"

    @staticmethod
    def _build_summary(people: int, counts: Dict[str, int], scene_tag: str) -> str:
        """Builds a human-friendly Vietnamese description."""
        parts = []
        if people > 0:
            parts.append(f"{people} người")
        for k, v in counts.items():
            if k != "person":
                parts.append(f"{v} {k}")

        items_str = ", ".join(parts) if parts else "Không có đối tượng nổi bật"
        return f"Phát hiện: {items_str} (Bối cảnh: {scene_tag})"


if __name__ == "__main__":
    detector = YoloDetector()
    dummy = Image.new("RGB", (320, 320), color=(200, 200, 200))
    res = detector.detect(dummy)
    assert "summary" in res and "people_count" in res
    print(f"[detector.py] Self-check passed: {res}")
