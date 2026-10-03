"""
core/config.py - Centralized configuration and default thresholds.
"""
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = BASE_DIR / "rules.json"
BLOCKLIST_PATH = BASE_DIR / "blocklist.jsonl"
NSFW_MODEL_PATH = BASE_DIR / "model.onnx"
YOLO_MODEL_PATH = BASE_DIR / "yolov8n.onnx"
INDEX_HTML_PATH = BASE_DIR / "index.html"

# URLs for bootstrapping
NSFW_MODEL_URL = "https://huggingface.co/crj/dl-ws/resolve/main/open_nsfw.onnx"
YOLO_MODEL_URL = "https://huggingface.co/Kalray/yolov8/resolve/main/yolov8n.onnx"

# Security & limits
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB max payload to prevent DoS

# Default moderation rules
DEFAULT_RULES = {
    "max_nsfw": 0.70,
    "min_safe": 0.30,
    "max_hamming_distance": 4,
    "auto_block_on_violation": True,
}
