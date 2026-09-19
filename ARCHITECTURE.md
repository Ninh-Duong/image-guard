# Architecture & Technical Design: image-guard

This document outlines the technical design, algorithmic foundations, and architectural decisions behind the `image-guard` moderation engine.

---

## 1. Problem Statement & Design Decisions

### The Challenge
- Modern web platforms require automated content moderation to protect users from explicit (NSFW), pornographic, and violent imagery before files reach persistent storage (e.g., S3, Google Cloud Storage).
- **Pitfalls of Cloud AI APIs** (AWS Rekognition, Google Cloud Vision, Hive Moderation, OpenAI):
  - **Latency & Reliability**: Cloud API outages or latency spikes block user upload flows (Single Point of Failure).
  - **Cost at Scale**: Per-image API pricing compounds rapidly as platform traffic grows.
  - **Privacy & Compliance**: Transmitting sensitive user uploads over the internet to third parties introduces data privacy risks.
- **Pitfalls of Training Custom Models from Scratch**:
  - Requires dedicated GPU clusters, extensive labeled datasets, and continuous maintenance overhead.

### The Ponytail Solution
- **100% Offline Local ONNX Inference**: Compact model weights (~23.5MB) executed locally via `onnxruntime` CPU execution providers. No GPUs required.
- **Two-Tier Filtering Architecture**:
  1. **Tier 1 (0ms)**: Perceptual Difference Hashing (`dHash`) with Hamming distance checks instantly rejects duplicate or modified violating images without executing the neural network.
  2. **Tier 2 (15-30ms)**: Local Convolutional Neural Network (CNN) inference classifies novel images.
- **Decoupled Architecture**: The inference engine outputs objective probability distributions ($0.0 - 1.0$). Business logic and thresholding live entirely in [`rules.json`](rules.json).
- **Fail-Open Circuit Breaker**: If model inference or image decoding fails due to corruption, the upload pipeline remains unblocked while marking the entry as `flagged_pending_review: true` for asynchronous inspection.

---

## 2. The Four Core Pillars

```
┌────────────────────────────────────────────────────────┐
│                   1. dHash Lookup                      │
│   Gradient hash + Hamming Distance (Bit count <= 4)   │
└───────────────────────────┬────────────────────────────┘
                            │ (If not matched)
                            ▼
┌────────────────────────────────────────────────────────┐
│               2. Local ONNX Model (CPU)                │
│    Preprocessed 224x224 input -> CNN -> Softmax        │
└───────────────────────────┬────────────────────────────┘
                            │ Probabilities
                            ▼
┌────────────────────────────────────────────────────────┐
│             3. Dynamic Rule Engine                     │
│    Compare scores vs rules.json thresholds            │
└───────────────────────────┬────────────────────────────┘
                            │ Pass / Fail
                            ▼
┌────────────────────────────────────────────────────────┐
│             4. Fail-Open Circuit Breaker               │
│    Unblocks pipeline upon exception, flags entry       │
└────────────────────────────────────────────────────────┘
```

1. **dHash Lookup (Perceptual Hash)**:
   - Evaluates whether an image has been previously banned in sub-millisecond $O(1)$ time.
   - Bypasses the neural network for over 80% of duplicate content on high-traffic platforms.
2. **Local ONNX Model (CPU)**:
   - Packaged in `.onnx` format mounted locally.
   - Optimized C++ execution provider yields consistent inference latencies of ~15-30ms on standard cloud CPUs.
3. **Threshold-based Dynamic Rule Engine**:
   - The neural network only computes objective confidence scores (`safe`, `nsfw`, `violence`).
   - Business criteria (e.g. `max_nsfw: 0.70`, `min_safe: 0.30`) are configured independently and evaluated dynamically.
4. **Fail-Open Policy (High Availability)**:
   - Ensures zero downtime for user uploads even in the event of unexpected runtime anomalies or damaged image headers.

---

## 3. Algorithm & Model Details

### A. Difference Hash (dHash) Algorithm
Unlike cryptographic hashes (MD5, SHA-256) which change drastically with even a single bit modification, perceptual difference hashes capture the structural luminosity gradient across adjacent pixels:

1. **Grayscale Conversion & Downsampling**:
   - The image is converted to grayscale (`L`) and downscaled to $(8 + 1) \times 8 = 9 \times 8$ pixels using bilinear interpolation.
2. **Horizontal Gradient Comparison**:
   - For each of the 8 rows, compare 8 adjacent pixel pairs horizontally:
     $$\text{bit}_{i, j} = \begin{cases} 1 & \text{if } P(i, j+1) > P(i, j) \\ 0 & \text{otherwise} \end{cases}$$
3. **Bit Packing to 64-bit Hex**:
   - $8 \times 8 = 64$ boolean values are packed into a 64-bit unsigned integer, serialized as a hexadecimal string (e.g. `0xc8dcd993d9b8c6f6`).
4. **Hamming Distance Comparison**:
   - Two hashes $H_1$ and $H_2$ are compared using bitwise XOR and bit counting:
     $$\text{dist}(H_1, H_2) = \text{popcount}(H_1 \oplus H_2)$$
   - If $\text{dist} \le 4$, the image is classified as an identical or re-compressed duplicate of an existing banned image.

### B. Convolutional Neural Network (CNN) Pipeline via ONNX
The deep learning classifier inspects semantic features within the image:

1. **Preprocessing**:
   - Resized to $224 \times 224$ pixels.
   - For NHWC models (Yahoo OpenNSFW): Converted from RGB to BGR and centered by subtracting ImageNet channel means:
     $$\mu = [104.0, 117.0, 123.0]$$
2. **Convolutional Feature Layers**:
   - **Shallow layers**: Kernels detect edges, contrast transitions, and skin-tone hues.
   - **Mid layers**: Assemble contours into anatomical shapes and geometries.
   - **Deep layers**: Extract high-level semantic representations (explicit regions, sexual anatomy, violent poses).
3. **Classification & Softmax**:
   - Computes output probabilities:
     $$P(y_i) = \frac{e^{z_i}}{\sum_{j} e^{z_j}}$$
   - Produces probabilities for `safe`, `nsfw`, and `violence`.

---

## 4. Storage & Database Integration

Banned image records are serialized into [`blocklist.jsonl`](blocklist.jsonl) in an append-only flat format:

```json
{"hash": "0xc8dcd993d9b8c6f6", "reason": "NSFW score exceeded threshold: 1.00 > 0.70", "safe_score": 0.0031, "nsfw_score": 0.9969, "violence_score": 0.0, "created_at": "2026-09-20T01:30:00Z"}
```

### Relational Database Mapping

| Field | SQL Data Type | Purpose |
| :--- | :--- | :--- |
| `hash` | `VARCHAR(32) PRIMARY KEY` | 64-bit hexadecimal dHash for $O(1)$ index lookups. |
| `reason` | `TEXT` | Human-readable explanation of why the content was banned. |
| `safe_score` | `FLOAT / REAL` | Confidence score for safe content ($0.0 - 1.0$). |
| `nsfw_score` | `FLOAT / REAL` | Confidence score for explicit content ($0.0 - 1.0$). |
| `violence_score`| `FLOAT / REAL` | Confidence score for violent content ($0.0 - 1.0$). |
| `created_at` | `TIMESTAMP` | ISO 8601 UTC timestamp of the violation. |

---

## 5. References & Related Work

- **[Yahoo Open NSFW](https://github.com/yahoo/open_nsfw)**: Pioneer deep learning model for NSFW detection.
- **[nsfwjs](https://github.com/infinitered/nsfwjs)**: Client-side TensorFlow.js moderation implementation.
- **[Llama Guard 3 Vision](https://github.com/meta-llama/llama-models)**: Open-source multimodal safety moderation from Meta.
- **[Guardrails AI](https://github.com/guardrails-ai/guardrails)**: Validation framework for AI safety policies.
