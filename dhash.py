"""
dhash.py - Fast perceptual difference hash (dHash) utilities for image deduplication.
"""
from typing import Set
import numpy as np
from PIL import Image


def compute_dhash(img: Image.Image, hash_size: int = 8) -> str:
    """
    Computes a 64-bit difference hash (dHash) based on brightness gradients.
    Resistant to scaling, minor compression, and formatting changes.

    :param img: PIL.Image instance.
    :param hash_size: Grid height (width is hash_size + 1). Default 8 creates a 64-bit hash.
    :return: Hexadecimal hash string (e.g., '0xc8dcd993d9b8c6f6').
    """
    # Resize to (width + 1, height) in grayscale
    resized = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
    arr = np.array(resized)

    # Compare adjacent pixels horizontally: arr[:, 1:] > arr[:, :-1]
    diff = arr[:, 1:] > arr[:, :-1]

    # Convert 64 boolean bits into a hexadecimal string
    decimal_val = 0
    for bit in diff.flatten():
        decimal_val = (decimal_val << 1) | int(bit)
    return hex(decimal_val)


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Computes the Hamming bit distance between two hexadecimal hash strings.
    Utilizes Python standard library integer bit_count() for O(1) speed.
    """
    return (int(hash1, 16) ^ int(hash2, 16)).bit_count()


def is_hash_blocked(img_hash: str, blocklist: Set[str], max_distance: int = 4) -> bool:
    """
    Checks if an image hash exists in the blocklist or is within the Hamming distance threshold.

    :param img_hash: Hex hash string of the target image.
    :param blocklist: Set of banned hex hash strings.
    :param max_distance: Maximum bit difference to consider a match (default: 4 bits).
    :return: True if the hash matches a banned entry, False otherwise.
    """
    if not blocklist:
        return False
    try:
        target = int(img_hash, 16)
        return any((target ^ int(h, 16)).bit_count() <= max_distance for h in blocklist)
    except ValueError:
        return img_hash in blocklist


if __name__ == "__main__":
    # Self-test
    test_img = Image.new("RGB", (64, 64), color="red")
    h1 = compute_dhash(test_img)
    assert isinstance(h1, str) and len(h1) > 0, "dHash calculation failed"
    assert hamming_distance(h1, h1) == 0, "Self distance should be 0"

    banned = {h1}
    assert is_hash_blocked(h1, banned) is True, "Exact match should be blocked"
    print("[dhash.py] All self-checks passed successfully.")
