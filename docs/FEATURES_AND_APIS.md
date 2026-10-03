# ⚡ FEATURES_AND_APIS.md - AI Agent Rapid Context & Feature Guide

> **AI AGENT CONTEXT INGESTION NOTICE**:
> This document is specifically structured for AI Coding Agents (Cursor, Claude, Copilot, ChatGPT, Antigravity) to rapidly understand the entire codebase, all active features, REST API endpoints, schemas, architectural boundaries, and runtime behaviors in under 2 minutes.

---

## 1. Executive Summary & Core Mission

- **Project Name**: `image-guard`
- **Core Role**: An independent, **100% offline edge microservice** built as the backend intelligence for **Mobile Memory Note & Photo-Sharing Apps**.
- **Dual Mission**:
  1. **Content Moderation (Guardrail)**: Block explicit/NSFW images and banned duplicate images (via 64-bit dHash) *before* they reach cloud storage.
  2. **Contextual User Profiling**: Analyze approved photos on CPU to extract user hobbies, social settings, lifestyle tags, and auto-generated captions localized in 4 languages (`vi`, `en`, `ja`, `ko`) and adjusted for the user's local timezone.
- **Design Philosophy**: **Ponytail Minimalism** — Native Python Standard Library first, zero heavy web frameworks (FastAPI/Flask are strictly banned), zero heavy vision frameworks (Torch/Ultralytics are strictly banned), runtime dependency ceiling limited to `numpy`, `pillow`, `onnxruntime`, and `rapidocr-onnxruntime`.

---

## 2. Feature Matrix & Capabilities

| Capability | Module | Implementation Details | Latency |
| :--- | :--- | :--- | :---: |
| **Input Validation** | `services/pipeline.py` | Magic byte header check (JPEG, PNG, WebP), EXIF transposition (`ImageOps.exif_transpose`). | $< 1$ms |
| **DoS Guardrail** | `api/server.py` | Hard payload cap `MAX_UPLOAD_SIZE = 20MB`. Returns `413 Payload Too Large`. | 0ms |
| **Duplicate / Banned Filter** | `guards/dhash.py` | 64-bit gradient difference hash ($9 \times 8$). Dual-indexed $O(1)$ set lookup + Hamming distance ($\le 4$ bits) using bitwise XOR (`int.bit_count()`). | $< 1$ms |
| **NSFW Content Guard** | `guards/nsfw.py` | Local ONNX MobileNet/ResNet50 CNN model (`model.onnx`). Dynamic thresholds (`max_nsfw: 0.70`, `min_safe: 0.30`). Auto-records violations to `blocklist.jsonl`. | 15–30ms |
| **Fail-Fast Early Exit** | `services/pipeline.py` | When Tier 1 or Tier 2 flags a violation, the pipeline immediately aborts (`is_allowed = False`), bypassing all object detection and profiling to save 70%+ CPU cycles. | — |
| **Object Detection** | `profiling/detector.py` | YOLOv8 Nano (`yolov8n.onnx`) running on ONNX Runtime CPU. Pure NumPy Letterbox pre-processing ($640 \times 640$) and pure NumPy Non-Maximum Suppression (NMS). Zero `torch` dependency. | 30–45ms |
| **Multi-Signal Visual Profiling** | `profiling/visual_analyzer.py` | Solves COCO-80 limits: analyzes mobile screen ratios ($> 1.70$), sunset/sunrise warmth ($R/B > 1.40$), and lazy OCR via `rapidocr-onnxruntime` for commercial billboards, banners, and receipts. | 10–25ms |
| **User Personality Taxonomy** | `profiling/profiler.py` | 11 primary interest categories, social settings (`solo`, `duo`, `group`, `crowd`), tag merging, and note captions. | $< 2$ms |
| **Quad-Language Localization** | `core/i18n.py` | Full native translations for labels, captions, and tags in Vietnamese (`vi`), English (`en`), Japanese (`ja`), and Korean (`ko`). | 0ms |
| **Timezone Intelligence** | `core/i18n.py` | Converts UTC to client timezone (IANA string e.g. `Asia/Ho_Chi_Minh` or UTC offset e.g. `+07:00`) to tag time of day (`morning`, `noon`, `afternoon`, `evening`, `night`). | 0ms |
| **Microsecond Telemetry** | `core/process_logger.py` | Traces every request stage in microseconds, identifies performance bottlenecks, writes `latest_run.json`, `history.jsonl`, and `metrics_summary.json`. | $< 1$ms |
| **Database-Ready Payload** | `core/types.py` | Pre-structures output records with `memory_id`, `merged_tags`, `guard_scores`, `user_profile`, and `note_metadata` ready for direct PostgreSQL JSONB or MongoDB persistence. | 0ms |
| **Self-Healing Bootstrap** | `bootstrap.py` / `run.py` | Checks environment, creates missing directories, and performs atomic downloads for `model.onnx` and `yolov8n.onnx` if absent. | At startup |

---

## 3. Complete REST API Reference

The server runs on `http://localhost:8000` via Python's native `http.server.ThreadingHTTPServer`.

### 3.1 `POST /check` (or `POST /guard`) — Core Inspection & Profiling Pipeline
Evaluates an uploaded image through moderation guardrails and extracts user profiling data.

- **Request Method**: `POST`
- **Query Parameters**:
  - `lang` *(optional, string, default: `"vi"`)*: Target language: `"vi"`, `"en"`, `"ja"`, or `"ko"`.
  - `tz` *(optional, string, default: `"UTC"`)*: Client timezone, e.g. `"Asia/Ho_Chi_Minh"`, `"America/New_York"`, or `"+07:00"`.
- **Headers**:
  - `Content-Type`: `image/jpeg`, `image/png`, `application/octet-stream`, or `multipart/form-data`.
- **Body**: Raw binary bytes of the image file (Max: `20MB`).

#### Response: 200 OK (Clean Image Approved)
```json
{
  "is_allowed": true,
  "status": "APPROVED",
  "dhash": "0x1818181818000000",
  "guard_scores": {
    "safe": 0.9962,
    "nsfw": 0.0038
  },
  "user_profile": {
    "primary_interest": "signboard_and_commercial",
    "interest_label": "Biển hiệu & Bảng quảng cáo",
    "confidence": 0.9,
    "detected_objects": ["signboard", "text_spotting"],
    "people_count": 0,
    "social_setting": "no_person",
    "scene_summary": "Phát hiện thông tin bảng hiệu / thương mại: Bourbon"
  },
  "note_metadata": {
    "suggested_caption": "Dừng chân ghi lại một bảng hiệu / địa điểm trên hành trình 📍",
    "lifestyle_tags": ["#BienQuangCao", "#DiaDiem", "#CheckIn", "#DoanhNghiep"],
    "object_tags": ["#Bourbon"],
    "merged_tags": ["#BienQuangCao", "#DiaDiem", "#CheckIn", "#Bourbon", "#DoanhNghiep"],
    "time_context": {
      "timezone": "Asia/Ho_Chi_Minh",
      "local_time": "2026-10-03T16:20:00+07:00",
      "time_of_day": "afternoon"
    }
  },
  "trace_id": "trace_20261003_092000_a1b2c3",
  "latency_ms": 42.15
}
```

#### Response: 200 OK (Violating Content Blocked - Fail-Fast Early Exit)
When blocked, `user_profile` and `note_metadata` are set to `null` to conserve CPU cycles:
```json
{
  "is_allowed": false,
  "status": "BLOCKED",
  "reason": "NSFW_VIOLATION",
  "dhash": "0xa3c8f1e2903b41d5",
  "guard_scores": {
    "safe": 0.0512,
    "nsfw": 0.9488
  },
  "user_profile": null,
  "note_metadata": null,
  "trace_id": "trace_20261003_092100_f4e5d6",
  "latency_ms": 18.42
}
```

---

### 3.2 `GET /rules` — Retrieve Active Moderation Thresholds
- **Response (200 OK)**:
```json
{
  "max_nsfw": 0.70,
  "min_safe": 0.30,
  "max_hamming_distance": 4,
  "auto_block_on_violation": true
}
```

---

### 3.3 `GET /blocklist` — Export Banned Hashes
- **Response (200 OK)**:
```json
{
  "total_banned": 3,
  "hashes": [
    "0x1111222233334444",
    "0x5555666677778888",
    "0xa3c8f1e2903b41d5"
  ]
}
```

---

### 3.4 `POST /blocklist` — Manually Register Banned Hash
- **Request Body**:
```json
{
  "hash": "0x1234567890abcdef",
  "reason": "Manual copyright ban"
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Hash added to blocklist",
  "hash": "0x1234567890abcdef",
  "total_banned": 4
}
```

---

### 3.5 `GET /languages` — Supported Locales & Sample Timezones
- **Response (200 OK)**:
```json
{
  "source_supported_languages": ["vi", "en", "ja", "ko"],
  "default_language": "vi",
  "sample_timezones": [
    "Asia/Ho_Chi_Minh",
    "Asia/Tokyo",
    "Asia/Seoul",
    "America/New_York",
    "Europe/London",
    "+07:00",
    "+09:00"
  ]
}
```

---

### 3.6 `GET /logs/latest` — Execution Trace of the Most Recent Run
Enables an AI Agent to immediately inspect the last execution with a single request:
- **Response (200 OK)**: Full JSON trace containing image metadata, microsecond stage timings, bottleneck stage identification, and AI optimization suggestions.

---

### 3.7 `GET /logs/summary` — Rolling Performance & Latency Telemetry
- **Response (200 OK)**:
```json
{
  "total_runs": 88,
  "allowed_runs": 72,
  "blocked_runs": 16,
  "avg_latency_ms": 52.34,
  "bottlenecks": {
    "stage_4_yolo_detection": 58,
    "stage_3_nsfw_guard": 22,
    "stage_1_validation": 8
  },
  "error_count": 0
}
```

---

### 3.8 `GET /` — Interactive Web UI Dashboard
Serves the self-contained interactive playground (`index.html`) featuring live image drop, real-time stage timing graphs, and process log inspection.

---

## 4. Architectural Boundaries (5 Clean Layers)

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

---

## 5. Primary Interest Taxonomy (11 Categories)

| ID (`primary_interest`) | English Label | Vietnamese Label | Trigger Signals / COCO Classes |
| :--- | :--- | :--- | :--- |
| `food_and_dining` | Food & Culinary Delights | Ẩm thực & Thưởng thức món ngon | `pizza, sandwich, cake, bowl, cup, wine glass, dining table` |
| `work_and_study` | Work & Tech Productivity | Làm việc & Học tập / Công nghệ | `laptop, keyboard, mouse, cell phone, book` |
| `movies_and_chill` | Movies & Cozy Entertainment | Xem phim & Giải trí thư giãn | `tv, remote, couch, bed` |
| `travel_and_explore` | Travel & Adventure | Du lịch & Khám phá | `airplane, bus, train, boat, suitcase, backpack, bicycle, car` |
| `pet_lover` | Pets & Animal Companions | Yêu thú cưng & Động vật | `dog, cat, bird, horse, sheep, cow` |
| `sports_and_fitness` | Sports & Healthy Fitness | Thể thao & Rèn luyện sức khỏe | `sports ball, baseball bat, tennis racket, skateboard, surfboard` |
| `social_and_gathering` | Social Gatherings & Friends | Gặp gỡ & Kết nối bạn bè | $\ge 2$ people + dining table or social context |
| `signboard_and_commercial` | Billboards & Commercial Signage | Biển hiệu & Bảng quảng cáo | High text density, commercial keywords, domains (`.com`, `.vn`), industrial park names |
| `screenshot_and_app` | Screenshots & App Interfaces | Ảnh chụp màn hình & Ứng dụng | Aspect ratio $> 1.70$ (smartphone standard) + UI text density |
| `document_and_receipt` | Documents & Financial Receipts | Tài liệu & Hóa đơn chứng từ | Receipt keywords (`tong tien`, `vat`, `vnd`, `receipt`), tabulated text |
| `sunset_and_nature` | Sunsets & Natural Landscapes | Hoàng hôn & Thiên nhiên bầu trời | Sky gradient, color warmth ratio $R/B > 1.40$, landscapes |
| `general_photo` | Life Moments & Scenery (Fallback) | Không gian & Cảnh vật | Generic photo not matching the above categories |

---

## 6. Immutable AI Agent Rules Checklist

Before submitting any code changes, ensure:
1. [ ] **No Heavy Frameworks**: No `fastapi`, `flask`, `torch`, `torchvision`, or `ultralytics` added.
2. [ ] **Layer Purity**: No business logic or guards placed in `api/server.py`.
3. [ ] **Fail-Fast Integrity**: If a guard fails, profiling is completely skipped.
4. [ ] **Telemetry Maintained**: All 5 pipeline stages are timed and recorded.
5. [ ] **Localization Preserved**: No hardcoded text; all strings routed through `core/i18n.py`.
6. [ ] **Test Suite Green**: Run `python test_server.py` and verify all 13 tests pass (100%).
