"""
dhash.py - Perceptual difference hash (dHash) compatibility module.
Delegates to guards/dhash.py.
"""
from typing import Set
from PIL import Image
from guards.dhash import compute_dhash, hamming_distance, BlocklistManager


def is_hash_blocked(img_hash: str, blocklist: Set[str], max_distance: int = 4) -> bool:
    """Legacy helper for backward compatibility."""
    if not blocklist:
        return False
    try:
        target = int(img_hash, 16)
        return any((target ^ int(h, 16)).bit_count() <= max_distance for h in blocklist)
    except ValueError:
        return img_hash in blocklist


if __name__ == "__main__":
    test_img = Image.new("RGB", (64, 64), color="red")
    h1 = compute_dhash(test_img)
    assert isinstance(h1, str) and len(h1) > 0, "dHash calculation failed"
    assert hamming_distance(h1, h1) == 0, "Self distance should be 0"

    banned = {h1}
    assert is_hash_blocked(h1, banned) is True, "Exact match should be blocked"
    print("[dhash.py] All self-checks passed successfully.")
