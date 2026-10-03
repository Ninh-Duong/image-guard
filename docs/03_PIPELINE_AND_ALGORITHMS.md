# 🧠 03 - Pipeline & Computer Vision Algorithms

This document outlines the mathematical foundations, optimization techniques, and local CPU-based computer vision models powering `image-guard`.

---

## 1. Stage 1: Input Validation & EXIF Normalization (0ms)

Before feeding raw bytes to neural networks, the image is validated and orientation-corrected:
* **Byte Check**: Validates magic signatures (JPEG `FF D8`, PNG `89 50 4E 47`, WebP `52 49 46 46`). Corrupted buffers trigger HTTP `400 Bad Request`.
* **EXIF Transposition**: Mobile smartphones (iOS, Android) frequently store sensor orientation metadata (EXIF Tags 1–8) without rotating pixel data. If uncorrected, CNNs see upside-down or sideways images.
  ```python
  from PIL import Image, ImageOps
  img = Image.open(io.BytesIO(raw_bytes))
  img = ImageOps.exif_transpose(img)  # Normalizes physical orientation
  ```

---

## 2. Stage 2: 64-bit Gradient dHash & $O(1)$ Bitwise Matching (0ms)

Perceptual Difference Hashing (dHash) detects identical or slightly altered images (compression, scaling, format changes) instantaneously.

### Mathematical Principles:
1. **Grayscale Conversion & Downsampling**: Converts the image to luminance ($L$) and applies bilinear interpolation down to $9 \times 8$ pixels (9 columns, 8 rows).
2. **Neighboring Gradient Comparison**: Evaluates relative intensity differences between adjacent pixels across each of the 8 rows:
   $$b_{i, j} = \begin{cases} 1 & \text{if } P(i, j+1) > P(i, j) \\ 0 & \text{otherwise} \end{cases}$$
   where $i \in [0, 7]$ (row) and $j \in [0, 7]$ (column).
3. **64-bit Integer Packing**: 64 binary values ($8 \times 8 = 64$) are packed into an unsigned 64-bit integer:
   $$H = \sum_{k=0}^{63} b_k \cdot 2^{63-k}$$
   Represented as a fixed-length 16-hex character string: `f"0x{H:016x}"`.

### Dual-Indexed $O(1)$ Lookup & Bitwise Hamming Distance:
The `BlocklistManager` maintains two in-memory sets:
- `int_hashes: Set[int]`: Set of 64-bit integers for native bitwise matching.
- When matching against the blocklist:
  1. Exact $O(1)$ set lookup: `target_int in self.int_hashes` (completes in $< 0.001$ms).
  2. Fuzzy Hamming Distance check ($\le 4$ bits):
     Executes a bitwise XOR on the 64-bit integers and counts set bits via `int.bit_count()` (native in Python 3.10+):
     $$\text{dist}(A, B) = \text{popcount}(A \oplus B)$$
     **Zero string manipulation or character iteration loops**, delivering microsecond performance.

---

## 3. Stage 3: NSFW Content Classification via ONNX Runtime CPU (15–30ms)

Content safety is evaluated using a lightweight convolutional neural network (`model.onnx`) running in FP32 on CPU.
* **Pre-processing**:
  - Resizes image to $224 \times 224$ pixels.
  - Normalizes RGB channels from $[0, 255]$ to $[0.0, 1.0]$.
  - Applies standard ImageNet normalization: $\mu = [0.485, 0.456, 0.406]$, $\sigma = [0.229, 0.224, 0.225]$.
  - Reshapes tensor to NCHW format: `(1, 3, 224, 224)`.
* **Inference**:
  - Executed via `onnxruntime.InferenceSession` on CPU with optimized threading.
  - Generates Softmax probabilities across two classes: `safe` and `nsfw`.
* **Dynamic Rule Thresholds**:
  Configured in `rules.json`:
  ```json
  {
    "max_nsfw": 0.70,
    "min_safe": 0.30
  }
  ```
  If `nsfw_score > 0.70`, the image is marked as a violation and its dHash is auto-saved to `blocklist.jsonl` if `auto_block_on_violation` is enabled.

---

## 4. Stage 4: YOLOv8n Object Detection & Pure NumPy NMS (30–45ms)

Rather than installing heavy dependencies like `ultralytics` or `torch`, `image-guard` implements letterbox pre-processing and Non-Maximum Suppression (NMS) using **pure NumPy**.

### 1. Letterbox Preprocessing (Aspect-Ratio Preserved):
Scales the input image while preserving its aspect ratio so that the longest edge equals 640 pixels. Remaining margins are padded with neutral gray `(114, 114, 114)` to prevent geometric distortion.

### 2. Output Tensor Decoding:
The `yolov8n.onnx` model outputs a tensor of shape `(1, 84, 8400)`:
- 84 rows: 4 bounding box coordinates $(x_c, y_c, w, h)$ and 80 COCO class probability scores.
- 8400 columns: Predictions across anchor points over feature pyramid layers.

### 3. Pure NumPy Non-Maximum Suppression (NMS):
- Filters candidate boxes with `confidence < conf_threshold` ($0.25$).
- Calculates Intersection-over-Union (IoU) between overlapping candidates:
  $$\text{IoU}(A, B) = \frac{\text{Area}(A \cap B)}{\text{Area}(A \cup B)}$$
- Suppresses redundant overlapping boxes where $\text{IoU} > \text{iou\_threshold}$ ($0.45$).

---

## 5. Stage 5: Multi-Signal Visual Profiling & Lazy RapidOCR (`visual_analyzer.py`)

Because YOLOv8's COCO-80 dataset only includes living physical objects (people, animals, vehicles, food...), typical mobile photos such as commercial billboards, screenshots, receipts, and landscapes lack COCO bounding boxes.

The module `profiling/visual_analyzer.py` provides multi-signal heuristics:

### 1. Mobile Screen Ratio Analysis (Screenshot Detection):
- Smartphone screen ratio heuristic: $H / W > 1.70$ or $W / H > 1.70$ (matching standard 16:9, 19.5:9, 20:9 displays).
- Combined with UI element dispersion to classify as `screenshot_and_app`.

### 2. Color Gradient & Warmth Analysis (Sunset / Nature):
- Divides the image into vertical zones (sky, horizon, terrain).
- Computes the color warmth ratio: $W_{\text{warm}} = \frac{R}{B + 1e-5}$.
- If $W_{\text{warm}} > 1.40$ with high chromatic variance, classifies as `sunset_and_nature`.

### 3. Lazy RapidOCR for Commercial Signboards & Receipts:
- **Lazy Execution**: OCR is only initialized and invoked when YOLO detects 0 physical objects or when high text density is indicated.
- **ONNX Execution**: Leverages `rapidocr-onnxruntime` on CPU ($150-250$ms).
- **Keyword Spotting & Classification**:
  - Detects domains (`.com`, `.vn`), business/industrial identifiers (`bourbon`, `an hoa`, `cong nghiep`), advertising keywords (`quang cao`, `thi cong`, `bien hieu`) $\to$ Classifies as `signboard_and_commercial`.
  - Detects financial keywords (`hoa don`, `tong tien`, `vat`, `receipt`, `vnd`) $\to$ Classifies as `document_and_receipt`.
  - Extracted proper nouns are automatically converted into hashtags (e.g. `#Bourbon`).
