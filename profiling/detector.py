"""
profiling/detector.py - Lightweight YOLOv8 Object Detection Engine.
Runs 100% offline via ONNX Runtime & pure NumPy (no heavy ultralytics package).
"""
from typing import Dict, Any, List, Tuple
from pathlib import Path
import os
from collections import Counter
import numpy as np
from PIL import Image, ImageOps

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


class ObjectDetector:
    """Offline YOLOv8 Object Detector."""

    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        self.session = None

        if ort is not None and self.model_path.exists():
            try:
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 2
                self.session = ort.InferenceSession(
                    str(self.model_path), sess_options=opts, providers=["CPUExecutionProvider"]
                )
                print(f"[ObjectDetector] Loaded YOLOv8 detector from {self.model_path.name}")
            except Exception as err:
                print(f"[ObjectDetector] Failed to initialize YOLO session: {err}")

    def detect(
        self,
        img: Image.Image,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
    ) -> Dict[str, Any]:
        """
        Detects objects in image.
        Returns:
            {
                'people_count': int,
                'counts': Dict[str, int],
                'detected_labels': List[str],
                'total_objects': int
            }
        """
        if self.session is None:
            return {
                "people_count": 0,
                "counts": {},
                "detected_labels": [],
                "total_objects": 0,
            }

        # 1. Normalize EXIF & resize
        clean_img = ImageOps.exif_transpose(img).convert("RGB")
        orig_w, orig_h = clean_img.size

        resized = clean_img.resize((640, 640), Image.Resampling.BILINEAR)
        arr = np.array(resized, dtype=np.float32) / 255.0
        tensor = np.transpose(arr, (2, 0, 1))[None, :]

        # 2. Inference
        input_name = self.session.get_inputs()[0].name
        raw = self.session.run(None, {input_name: tensor})[0]  # (1, 84, 8400)
        output = raw[0].T  # (8400, 84)

        # 3. Filter candidates
        boxes_raw = output[:, :4]
        class_scores = output[:, 4:]
        class_ids = np.argmax(class_scores, axis=1)
        max_scores = np.max(class_scores, axis=1)

        mask = max_scores >= conf_threshold
        if not np.any(mask):
            return {
                "people_count": 0,
                "counts": {},
                "detected_labels": [],
                "total_objects": 0,
            }

        cand_boxes = boxes_raw[mask]
        cand_scores = max_scores[mask]
        cand_classes = class_ids[mask]

        scale_x = orig_w / 640.0
        scale_y = orig_h / 640.0
        x1 = (cand_boxes[:, 0] - cand_boxes[:, 2] / 2.0) * scale_x
        y1 = (cand_boxes[:, 1] - cand_boxes[:, 3] / 2.0) * scale_y
        x2 = (cand_boxes[:, 0] + cand_boxes[:, 2] / 2.0) * scale_x
        y2 = (cand_boxes[:, 1] + cand_boxes[:, 3] / 2.0) * scale_y
        converted_boxes = np.column_stack([x1, y1, x2, y2])

        # 4. NMS per class
        kept_indices = []
        for cid in np.unique(cand_classes):
            c_mask = np.where(cand_classes == cid)[0]
            c_keep = _nms(converted_boxes[c_mask], cand_scores[c_mask], iou_threshold)
            kept_indices.extend(c_mask[c_keep])

        detected_labels = [COCO_CLASSES[cand_classes[idx]] for idx in kept_indices if cand_classes[idx] < len(COCO_CLASSES)]
        counts = dict(Counter(detected_labels))
        people_count = counts.get("person", 0)

        return {
            "people_count": people_count,
            "counts": counts,
            "detected_labels": detected_labels,
            "total_objects": len(kept_indices),
        }
