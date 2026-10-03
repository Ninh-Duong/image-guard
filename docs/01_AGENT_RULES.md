# 📜 01 - Inviolable Technical Constitution for AI Agents (AGENT_RULES)

> **MANDATORY CONSTITUTION FOR ALL AI CODING AGENTS (Cursor, Claude, Copilot, ChatGPT, Antigravity, etc.)**
> You are modifying the `image-guard` repository. Before making any code edits, adding features, or debugging, you **MUST** read and strictly adhere to the five inviolable architectural laws described below.

---

## 🏛️ LAW 1: The Clean Layered Architecture (Preserve Layer Boundaries)

The repository strictly enforces separation of concerns across five distinct packages. **Never merge layers or introduce circular dependencies.**

```
┌────────────────────────────────────────────────────────┐
│                   Presentation Layer                   │
│         api/server.py (ThreadingHTTPServer)            │
│       - HTTP Request/Response Serialization            │
│       - DoS Guardrail (MAX_UPLOAD_SIZE = 20MB)         │
│       - CORS Preflight & Headers                       │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                    Services Layer                      │
│             services/pipeline.py                       │
│       - Input Validation & EXIF Normalization          │
│       - Orchestration & Fail-Fast Pipeline             │
│       - Circuit Breaker Exception Handling             │
└─────────────┬────────────────────────────┬─────────────┘
              │                            │
┌─────────────▼──────────────┐ ┌───────────▼─────────────┐
│       Guards Layer         │ │     Profiling Layer     │
│   guards/dhash.py (0ms)    │ │ profiling/detector.py   │
│   guards/nsfw.py (15-30ms) │ │ profiling/profiler.py   │
│                            │ │ profiling/visual_analyzer│
└─────────────┬──────────────┘ └───────────┬─────────────┘
              │                            │
┌─────────────▼────────────────────────────▼─────────────┐
│                     Core Layer                         │
│   core/config.py (Thresholds, Paths, Limits)           │
│   core/types.py (DTOs, Dataclasses, Schemas)           │
│   core/i18n.py (Localization VI/EN/JA/KO, Timezone)    │
│   core/process_logger.py (AI Agent Microsecond Traces) │
└────────────────────────────────────────────────────────┘
```

* **Rule 1.1**: The Presentation layer (`api/server.py`) must ONLY handle HTTP requests, headers, query parameters, and serialization. **NEVER** place moderation or profiling logic here.
* **Rule 1.2**: Modules in the Guards layer (`guards/`) must remain pure functional engines with zero HTTP dependencies.
* **Rule 1.3**: Compatibility facades at the root directory (`server.py`, `dhash.py`, `moderator.py`, `detector.py`) MUST remain thin delegation wrappers to maintain backward compatibility.

---

## 🧘 LAW 2: The Ponytail Minimalist Law (Standard Library First)

This repository is built following the **Ponytail Engineering Philosophy**: The most robust and performant code is the code that leverages native platform capabilities and the Python Standard Library.

* **Rule 2.1 (Zero Heavy Web Frameworks)**: **NEVER** install or introduce `FastAPI`, `Flask`, `Django`, `Tornado`, or `Starlette`. The HTTP server MUST remain Python's native `http.server.ThreadingHTTPServer`.
* **Rule 2.2 (Zero Heavy Vision/DL Packages in Production)**: **NEVER** install or import `ultralytics`, `torch`, or `torchvision` in the core pipeline.
  - Object detection runs strictly via `onnxruntime` + pure NumPy Non-Maximum Suppression (NMS) (`profiling/detector.py`).
  - Perceptual hashing runs strictly via 64-bit integer arithmetic and bitwise XOR (`guards/dhash.py`).
  - Text spotting runs via pre-installed `rapidocr-onnxruntime` or lightweight NumPy heuristics (`profiling/visual_analyzer.py`).
* **Rule 2.3 (Dependency Ceiling)**: Permitted third-party dependencies are strictly limited to:
  `numpy`, `pillow`, `onnxruntime`, and `rapidocr-onnxruntime`.

---

## ⚡ LAW 3: The Fail-Fast Guardrail Protocol (Early Exit)

CPU cycles are precious. Content moderation guardrails MUST execute before expensive profiling:

```
[Uploaded Image]
      │
      ▼
 1. Input Validation & EXIF Transposition (0ms)
      │  (HTTP 400 Bad Request on corrupted/empty payloads)
      ▼
 2. Tier 1: Perceptual dHash Guard (0ms) ────────> Banned Hash Match? ───> [BLOCK IMMEDIATELY]
      │  (O(1) Set lookup + Hamming Distance <= 4)                        (YOLO & Profiling SKIPPED)
      ▼
 3. Tier 2: ONNX NSFW CNN Guard (15-30ms) ──────> Threshold Exceeded? ──> [BLOCK & RECORD]
      │  (Dynamic rule evaluation)                                        (YOLO & Profiling SKIPPED)
      ▼
 4. Tier 3 & 4: YOLOv8n & Visual Profiling (30-50ms)
      │  (ONLY RUNS WHEN IMAGE IS VERIFIED SAFE)
```

* **Rule 3.1**: If Tier 1 or Tier 2 rejects an image, the pipeline **MUST ABORT IMMEDIATELY** (`is_allowed = False`). Never invoke YOLOv8 or the Profiler on violating content.
* **Rule 3.2 (Self-Healing Fail-Fast Bootstrap)**: During system startup (`bootstrap.py` or `run.py`), missing weights (`model.onnx`, `yolov8n.onnx`) must be atomically downloaded or the system must crash immediately with a clear error. Never allow silent runtime failures.

---

## 📊 LAW 4: Process Logging & Telemetry Contract

Every execution through the pipeline produces microsecond-precision traces to facilitate automated AI inspection and self-optimization:

* **Rule 4.1**: Every request must record microsecond timings for each stage:
  - `stage_1_validation`
  - `stage_2_dhash_guard`
  - `stage_3_nsfw_guard`
  - `stage_4_yolo_detection`
  - `stage_5_user_profiling`
* **Rule 4.2**: The file `logs/process/latest_run.json` must always reflect the most recent run so an AI Agent can inspect execution with a single file read or via `GET /logs/latest`.
* **Rule 4.3**: The database payload (`database_payload`) must always be formatted for direct persistence into PostgreSQL JSONB or MongoDB, containing `merged_tags`, `note_metadata`, `user_profile`, and `guard_scores`.
* **Rule 4.4**: The system must enforce FIFO log rotation (maximum 500 trace files) to prevent unbounded disk growth.

---

## 🌐 LAW 5: Multi-Signal Profiling, Localization & Timezone Rules

To serve real-world mobile memory note applications:

* **Rule 5.1 (No Hardcoded Language Strings)**: Never hardcode Vietnamese or English strings in business logic. All labels, captions, and tags MUST be configured in the centralized dictionary `DEFAULT_INTERESTS_I18N` in [`core/i18n.py`](file:///d:/Visual%20Studio%20Code/image-guard/core/i18n.py) with full support for 4 standard locales:
  - `vi`: Vietnamese
  - `en`: English
  - `ja`: Japanese (日本語)
  - `ko`: Korean (한국어)
* **Rule 5.2 (Timezone Awareness)**: All time-of-day tags (`#MorningVibes`, `#SunsetVibes`, `#LateNight`) and greeting captions MUST be computed from the client's timezone (`tz`), supporting both IANA strings (e.g. `Asia/Ho_Chi_Minh`, `America/New_York`) and UTC offsets (e.g. `+07:00`).
* **Rule 5.3 (Multi-Signal Vision Heuristics)**: YOLOv8's COCO-80 dataset only includes living physical objects. For non-COCO images (billboards, advertisements, phone screenshots, receipts, sunsets), the system MUST use [`profiling/visual_analyzer.py`](file:///d:/Visual%20Studio%20Code/image-guard/profiling/visual_analyzer.py) (aspect ratio analysis, color warmth heuristics, lazy RapidOCR) rather than falling back to generic default tags.
