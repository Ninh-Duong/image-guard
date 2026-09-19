# image-guard

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![ONNX Runtime](https://img.shields.io/badge/Inference-ONNX%20Runtime%20CPU-orange.svg)](https://onnxruntime.ai/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An independent, self-hosted, **100% offline** image content moderation engine. Automatically detects Not-Safe-For-Work (NSFW) content and explicit imagery while evaluating customizable rule thresholds before images are persisted into your storage systems.

Built strictly under the **Ponytail** engineering philosophy: minimal code, zero external cloud dependencies, standard library first, maximum extensibility, and blazing execution efficiency.

---

## Architecture & How It Works

```
[Uploaded Image]
       │
       ├──> 1. Perceptual dHash Filter (0ms) ────────> Matches banned hash? ───> [BLOCK IMMEDIATELY]
       │       (Hamming Distance <= 4 bits)
       │
       └──> 2. Local ONNX CNN Inference (15-30ms CPU)
                │
                ├─ Preprocessing: Resized to 224x224 RGB tensor
                ├─ Feature Extraction: Edges → Anatomy → Explicit Regions
                └─ Softmax Classifier: [P(safe), P(nsfw), P(violence)]
                      │
                      ▼
            3. Dynamic Extensible Rule Engine ───────> Exceeds thresholds? ────> [FLAG / BLOCK]
                      │
                      ▼ (Fail-Open Circuit Breaker)
            4. Allows upload or flags for asynchronous manual review upon errors
```

See the [Architecture Documentation](ARCHITECTURE.md) for deep technical details and mathematical background.

---

## Key Features

- **100% Offline & Private**: Zero external cloud API calls (e.g., AWS Rekognition, Google Cloud Vision, Hive). Completely immune to third-party outages, price hikes, or privacy leaks.
- **dHash Fast Filter ($0\text{ms}$)**: 64-bit gradient difference hashing with Hamming distance rejects 80%+ duplicate violating images before reaching the neural network.
- **CPU-Optimized Inference**: Powered by ONNX Runtime using optimized C++ CPU kernels (~15-30ms). No expensive GPU instances needed.
- **Extensible Rule Engine**: Model outputs objective probabilities ($0.0 - 1.0$), while business rules are decoupled and dynamically evaluated via [`rules.json`](rules.json) without modifying code.
- **Self-Bootstrapping Deployment**: Automatically checks and installs missing dependencies (`numpy`, `Pillow`, `onnxruntime`) and downloads model weights with an animated progress bar.
- **Batch Processing**: Built-in `check_batch()` method for scanning albums or bulk upload queues.
- **CLI Direct Execution**: Inspect images instantly from scripts or terminal (`python moderator.py image.jpg`).
- **CORS-Ready REST API**: Native `OPTIONS` support for seamless integration with external React/Vue/Next.js frontends.
- **Fail-Open Circuit Breaker**: Gracefully catches decode or inference errors, preventing upload pipeline deadlocks by setting `flagged_pending_review: true`.
- **Database-Ready Storage**: Banned images are recorded in [`blocklist.jsonl`](blocklist.jsonl) using a flat schema ready for 1-command bulk import into PostgreSQL, MySQL, SQLite, or MongoDB.

---

## Installation

```bash
pip install -r requirements.txt
```

### Dependencies
- `onnxruntime`: High-performance local inference engine on CPU.
- `Pillow`: Image decoding and transformation.
- `numpy`: Array manipulation and tensor transformations.

*(All other utilities use the **100% Python Standard Library**).*

---

## Quickstart

### 1. Universal 1-Command Runner (Self-Bootstrapping)

Deploying on a fresh machine or server? Just run:

```bash
python run.py
```

`run.py` automatically:
1. Detects dependencies (`numpy`, `Pillow`, `onnxruntime`) and installs any missing packages via `pip`.
2. Verifies local ONNX weights; downloads `model.onnx` (~23.5 MB) with a real-time progress bar if missing.
3. Launches the local HTTP server at **[http://localhost:8000](http://localhost:8000)**.

Alternatively, start the server directly:
```bash
python server.py
```

Open your browser at **[http://localhost:8000](http://localhost:8000)**:
- Drag and drop images for instant evaluation with real-time loading feedback.
- Adjust `max_nsfw`, `max_violence`, and `min_safe` sliders in real time.
- View probability meters (Safe, NSFW, Violence).
- Click `+ Ban this dHash Permanently` to save hashes to the persistent blocklist.

---

### 2. Python SDK Usage

#### Single Image Check
```python
from moderator import LocalModerationEngine

# Initialize the engine (loads model and rules once into memory)
moderator = LocalModerationEngine()

# Check an image (accepts file path, PIL.Image, or io.BytesIO)
result = moderator.check("path/to/image.jpg")

if not result["allowed"]:
    print("Image blocked:", result["violations"])
    print("Perceptual dHash:", result["hash"])
else:
    print("Image approved. Safe score:", result["scores"]["safe"])
```

#### Batch Image Processing
```python
images = ["photo1.jpg", "photo2.png", "photo3.webp"]
results = moderator.check_batch(images)

for path, res in zip(images, results):
    status = "ALLOWED" if res["allowed"] else "BLOCKED"
    print(f"[{status}] {path} -> {res.get('violations', [])}")
```

#### Custom Model Swapping & Custom Labels
```python
# Easily plug in any custom ONNX model and label mapping
custom_engine = LocalModerationEngine(
    model_path="path/to/custom_model.onnx",
    label_map=["safe", "nsfw", "violence", "hate_symbols", "gore"]
)
```

---

### 3. Command Line Interface (CLI)

Evaluate any image directly from the terminal or bash scripts:

```bash
python moderator.py sample.jpg
```

**Output (JSON):**
```json
{
  "allowed": false,
  "hash": "0xc8dcd993d9b8c6f6",
  "scores": {
    "safe": 0.0031,
    "nsfw": 0.9969,
    "violence": 0.0
  },
  "violations": [
    "NSFW score exceeded threshold: 1.00 > 0.70"
  ]
}
```
*(Exit code: `0` if allowed, `2` if blocked, `1` if error).*

---

### 4. REST API Integration (CORS Enabled)

Integrate `image-guard` into your existing backend or frontend (React, Vue, Node.js, Go, PHP):

#### Endpoint: `POST /check`
Send raw binary image data:
```bash
curl -X POST "http://localhost:8000/check?max_nsfw=0.60&min_safe=0.30" \
     -H "Content-Type: image/jpeg" \
     --data-binary "@sample.jpg"
```

#### Endpoint: `GET /rules`
Retrieve current system configuration.

#### Endpoint: `POST /blocklist`
Add a hash to the persistent blocklist:
```bash
curl -X POST "http://localhost:8000/blocklist" \
     -H "Content-Type: application/json" \
     -d '{"hash": "0xc8dcd993d9b8c6f6", "reason": "MANUAL_BAN"}'
```

---

## Configuration & Extensible Rules (`rules.json`)

System rules live in [`rules.json`](rules.json). Modifying thresholds requires no code changes:

```json
{
  "max_nsfw": 0.70,
  "max_violence": 0.60,
  "min_safe": 0.30,
  "max_hamming_distance": 4,
  "auto_block_on_violation": true
}
```

### How Extensible Rules Work
The engine's `evaluate_rules()` dynamically parses any rule with prefix `max_<label>` or `min_<label>`:
- Add `"max_gore": 0.50` $\rightarrow$ automatically checks `scores.get("gore") > 0.50`.
- Add `"max_hate_symbols": 0.30` $\rightarrow$ automatically checks `scores.get("hate_symbols") > 0.30`.
- Add `"min_aesthetic_score": 0.60` $\rightarrow$ automatically checks `scores.get("aesthetic_score") < 0.60`.

---

## Persistent Blocklist (`blocklist.jsonl`)

Banned images are saved in append-only JSON Lines format ([`blocklist.jsonl`](blocklist.jsonl)):

```json
{"hash": "0xc8dcd993d9b8c6f6", "reason": "NSFW score exceeded threshold: 1.00 > 0.70", "safe_score": 0.0031, "nsfw_score": 0.9969, "violence_score": 0.0, "created_at": "2026-09-20T01:30:00Z"}
```

### Database Migration
The flat schema maps 1:1 to SQL tables:

```sql
CREATE TABLE blocked_images (
    hash VARCHAR(32) PRIMARY KEY,
    reason TEXT NOT NULL,
    safe_score REAL,
    nsfw_score REAL,
    violence_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- **PostgreSQL**: `\copy blocked_images FROM 'blocklist.jsonl'`
- **MongoDB**: `mongoimport --collection blocked_images --file blocklist.jsonl`

---

## Repository Structure

```
image-guard/
├── .gitignore            # Git ignore for models, virtualenvs, and bytecode
├── ARCHITECTURE.md       # Technical design and algorithmic foundations
├── README.md             # Project documentation and API guide
├── rules.json            # System moderation rule configurations
├── blocklist.jsonl       # Persistent database-ready blocklist
├── bootstrap.py          # Automated dependency resolution & model downloader
├── run.py                # Universal 1-command startup runner
├── dhash.py              # Perceptual difference hashing & Hamming distance utilities
├── moderator.py          # Core moderation engine, dynamic rules & CLI
├── index.html            # Standalone responsive web dashboard
├── server.py             # Built-in HTTP server with CORS support
├── test_server.py        # Automated end-to-end integration tests
└── requirements.txt      # Minimal project dependencies
```

---

## Testing & Verification

Run all unit tests:
```bash
python dhash.py
python moderator.py
```

Run the end-to-end integration test suite:
```bash
python test_server.py
```

---

## License

This project is open-sourced under the [MIT License](LICENSE).
