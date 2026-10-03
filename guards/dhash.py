"""
guards/dhash.py - High-speed perceptual difference hash (dHash) & Blocklist Manager.
Optimized for 0ms duplicate matching using native Python bitwise operations.
"""
from typing import Set, Dict, Optional, Any
from pathlib import Path
import json
from datetime import datetime, timezone
import numpy as np
from PIL import Image, ImageOps


def compute_dhash(img: Image.Image, hash_size: int = 8) -> str:
    """
    Computes a 64-bit difference hash (dHash) based on horizontal brightness gradients.
    Resistant to scaling, minor compression, and formatting changes.
    Output is formatted as a standardized fixed-width 16-character hex string (0x0123456789abcdef).
    """
    # 1. Normalize EXIF orientation and convert to grayscale
    img_clean = ImageOps.exif_transpose(img).convert("L")

    # 2. Resize to (hash_size + 1, hash_size)
    resized = img_clean.resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
    arr = np.array(resized)

    # 3. Compare adjacent pixels horizontally: arr[:, 1:] > arr[:, :-1]
    diff = arr[:, 1:] > arr[:, :-1]

    # 4. Pack 64 boolean bits into a 64-bit unsigned integer
    decimal_val = 0
    for bit in diff.flatten():
        decimal_val = (decimal_val << 1) | int(bit)

    # Fixed-width 16 hex digits (64 bits) with 0x prefix
    return f"0x{decimal_val:016x}"


def hamming_distance(hash1: str, hash2: str) -> int:
    """Computes the Hamming bit distance between two hexadecimal hash strings."""
    return (int(hash1, 16) ^ int(hash2, 16)).bit_count()


class BlocklistManager:
    """
    In-memory dual-indexed blocklist manager:
    - Stores hashes as integers for O(1) exact lookups & ultra-fast bitwise XOR scans.
    - Persists append-only database-ready records to blocklist.jsonl.
    """

    def __init__(self, blocklist_path: Path):
        self.blocklist_path = Path(blocklist_path)
        self.str_hashes: Set[str] = set()
        self.int_hashes: Set[int] = set()
        self.load()

    def load(self):
        """Loads banned hashes into memory."""
        self.str_hashes.clear()
        self.int_hashes.clear()
        if not self.blocklist_path.exists():
            return

        try:
            with open(self.blocklist_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        h = record.get("hash")
                        if h:
                            h_clean = h.lower()
                            self.str_hashes.add(h_clean)
                            try:
                                self.int_hashes.add(int(h_clean, 16))
                            except ValueError:
                                pass
                    except json.JSONDecodeError:
                        continue
            print(f"[BlocklistManager] Loaded {len(self.str_hashes)} banned hash(es) from {self.blocklist_path.name}")
        except Exception as err:
            print(f"[BlocklistManager] Failed to read blocklist: {err}")

    def is_blocked(self, img_hash: str, max_distance: int = 4) -> bool:
        """
        Fast lookup:
        - If max_distance == 0: Instant O(1) set lookup.
        - If max_distance > 0: Integer XOR bit_count scan without string parsing inside loop.
        """
        if not self.int_hashes:
            return False

        try:
            target_int = int(img_hash, 16)
        except ValueError:
            return img_hash.lower() in self.str_hashes

        if max_distance == 0:
            return target_int in self.int_hashes

        # Fast integer bitwise scan
        return any((target_int ^ h).bit_count() <= max_distance for h in self.int_hashes)

    def add(
        self,
        img_hash: str,
        reason: str = "VIOLATION",
        scores: Optional[Dict[str, float]] = None,
    ) -> bool:
        """Adds a hash to memory and persists to blocklist.jsonl."""
        h_clean = img_hash.lower()
        if h_clean in self.str_hashes:
            return False

        self.str_hashes.add(h_clean)
        try:
            self.int_hashes.add(int(h_clean, 16))
        except ValueError:
            pass

        scores = scores or {}
        record = {
            "hash": h_clean,
            "reason": reason,
            "safe_score": round(float(scores.get("safe", 0.0)), 4),
            "nsfw_score": round(float(scores.get("nsfw", 0.0)), 4),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with open(self.blocklist_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            return True
        except Exception as err:
            print(f"[BlocklistManager] Failed to append blocklist entry: {err}")
            return False
