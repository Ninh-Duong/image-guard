"""
detector.py - Compatibility facade for YOLOv8 detector and scene analysis.
Delegates to profiling/detector.py and profiling/profiler.py.
"""
from typing import Dict, Any
from pathlib import Path
from PIL import Image

from profiling.detector import ObjectDetector, COCO_CLASSES
from profiling.profiler import UserProfiler

DEFAULT_MODEL_PATH = str(Path(__file__).parent / "yolov8n.onnx")


class YoloDetector:
    """Compatibility wrapper around ObjectDetector and UserProfiler."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.detector = ObjectDetector(Path(model_path))
        self.profiler = UserProfiler()

    def detect(self, img: Image.Image, conf_threshold: float = 0.35, iou_threshold: float = 0.45) -> Dict[str, Any]:
        raw = self.detector.detect(img, conf_threshold=conf_threshold, iou_threshold=iou_threshold)
        profile = self.profiler.build_profile(raw["people_count"], raw["counts"], raw["total_objects"])
        return {
            "summary": profile.scene_summary,
            "people_count": raw["people_count"],
            "scene_tag": profile.interest_label,
            "counts": raw["counts"],
            "total_objects": raw["total_objects"],
            "profile": profile.to_dict(),
        }


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    detector = YoloDetector()
    dummy = Image.new("RGB", (320, 320), color=(200, 200, 200))
    res = detector.detect(dummy)
    assert "summary" in res and "people_count" in res
    print(f"[detector.py] Self-check passed: {res['summary']}")
