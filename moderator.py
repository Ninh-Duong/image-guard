"""
moderator.py - Backward-compatible facade for Image Guard & User Profiling.
Delegates to the modular services/pipeline.py architecture.
"""
from typing import Dict, Any, Union, BinaryIO, Set, Optional, List
from pathlib import Path
import os
import sys
import json
from PIL import Image

from services.pipeline import ImageGuardService
from guards.dhash import compute_dhash


class LocalModerationEngine:
    """
    Backward-compatible adapter for LocalModerationEngine.
    Delegates to the modular layered architecture in services/pipeline.py.
    """

    def __init__(
        self,
        model_path: str = "model.onnx",
        rules_path: str = "rules.json",
        blocklist_path: str = "blocklist.jsonl",
        label_map: Optional[List[str]] = None,
        auto_download: bool = True,
    ):
        self.service = ImageGuardService(
            nsfw_model_path=Path(model_path),
            rules_path=Path(rules_path),
            blocklist_path=Path(blocklist_path),
        )

    @property
    def default_rules(self) -> Dict[str, Any]:
        return self.service.default_rules

    @property
    def blocklist_hashes(self) -> Set[str]:
        return self.service.blocklist.str_hashes

    def compute_dhash(self, img: Image.Image, hash_size: int = 8) -> str:
        return compute_dhash(img, hash_size=hash_size)

    def is_hash_blocked(self, img_hash: str, max_distance: int = 4) -> bool:
        return self.service.blocklist.is_blocked(img_hash, max_distance=max_distance)

    def add_to_blocklist(
        self,
        img_hash: str,
        reason: str = "VIOLATION",
        scores: Optional[Dict[str, float]] = None,
    ) -> bool:
        return self.service.blocklist.add(img_hash, reason=reason, scores=scores)

    def check(
        self,
        image_input: Union[str, BinaryIO, Image.Image],
        rules: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Runs the pipeline and returns a backward-compatible dictionary."""
        response = self.service.process_image(image_input, rules=rules)
        return response.to_dict()

    def check_batch(
        self,
        images: List[Union[str, BinaryIO, Image.Image]],
        rules: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return [self.check(img, rules=rules) for img in images]


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
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result.get("allowed") else 2)

    # Self-test validation suite
    test_img = Image.new("RGB", (100, 100), color="white")
    for x in range(50):
        for y in range(50):
            test_img.putpixel((x, y), (0, 255, 0))

    # 1. Test dHash
    h = engine.compute_dhash(test_img)
    assert isinstance(h, str) and len(h) > 0, "dHash computation failed"

    # 2. Test Check with default rules & profile analysis
    res = engine.check(test_img, rules={"max_nsfw": 0.5})
    assert res["allowed"] is True, "Safe test image check failed"
    assert "profile" in res, "Profile analysis missing"

    # 3. Test Batch check
    batch_res = engine.check_batch([test_img, test_img])
    assert len(batch_res) == 2 and batch_res[0]["allowed"] is True, "Batch check failed"

    # 4. Test Invalid image input handling
    broken_res = engine.check(b"")
    assert broken_res["allowed"] is False and broken_res.get("reason") == "INVALID_IMAGE_PAYLOAD"

    print("[moderator.py] All self-checks and backwards compatibility tests passed successfully.")
