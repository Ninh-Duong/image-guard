# 🛡️ image-guard

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![ONNX Runtime](https://img.shields.io/badge/Inference-ONNX%20Runtime%20CPU-orange.svg)](https://onnxruntime.ai/)
[![Architecture](https://img.shields.io/badge/Design-Clean%20Layered%20Architecture-brightgreen.svg)](docs/02_SYSTEM_ARCHITECTURE.md)
[![Philosophy](https://img.shields.io/badge/Philosophy-Ponytail%20Minimalism-purple.svg)](docs/01_AGENT_RULES.md)
[![Documentation](https://img.shields.io/badge/Docs-Centralized%20Hub-informational.svg)](docs/README.md)

An independent, self-hosted, **100% offline edge microservice** providing content moderation guardrails and contextual user profiling. Built specifically as the core backend intelligence for **Mobile Memory Note & Photo-Sharing Apps**.

---

## 📚 Centralized Knowledge Base (`docs/`)

All technical documentation, architecture designs, AI agent constitutions, and integration specifications are consolidated inside the [**`docs/`**](docs/README.md) directory:

* ⚡ [**FEATURES_AND_APIS.md**](docs/FEATURES_AND_APIS.md): **AI Agent Rapid Context Card** — Complete matrix of capabilities, REST API endpoints, schemas, and rules in under 2 minutes.
* 📜 [**01. AI Agent Constitution**](docs/01_AGENT_RULES.md): The 5 inviolable laws for all AI coding agents (Layer boundaries, Ponytail minimalism, Fail-Fast protocol, Telemetry, Multi-signal & i18n).
* 🏛️ [**02. System Architecture**](docs/02_SYSTEM_ARCHITECTURE.md): 5-tier Clean Architecture model, dataflow diagrams, multi-threaded `ThreadingHTTPServer`, and DoS protection.
* 🧠 [**03. Pipeline & Algorithms**](docs/03_PIPELINE_AND_ALGORITHMS.md): Mathematical principles of 64-bit gradient dHash, NSFW ONNX CNN, YOLOv8n pure NumPy NMS, and Multi-Signal Visual Analyzer with Lazy RapidOCR.
* 🏷️ [**04. Personality Taxonomy & i18n**](docs/04_TAXONOMY_AND_I18N.md): 11 lifestyle categories, social settings, timezone engine, and quad-language support (`vi`, `en`, `ja`, `ko`).
* 🔌 [**05. API & Mobile Integration**](docs/05_API_AND_INTEGRATION.md): Complete REST endpoint specs, database-ready payloads, and client code snippets (Flutter, React Native, Python, cURL).
* 📈 [**06. Process Telemetry & Observability**](docs/06_PROCESS_TELEMETRY.md): Microsecond stage latency tracking, bottleneck analysis, trace schemas, and automated AI tuning protocols.

> [!IMPORTANT]
> **Notice for AI Coding Agents (Cursor, Claude, Copilot, ChatGPT, Antigravity)**: Before modifying any code in this repository, you **MUST** read and strictly follow [**`docs/01_AGENT_RULES.md`**](docs/01_AGENT_RULES.md).

---

## ⚡ Fail-Fast Execution Pipeline

```
[Uploaded Mobile Photo]
       │
       ▼
 1. Input Validation & EXIF Transposition (0ms)
       │  (Corrupted / invalid buffers rejected with HTTP 400 Bad Request)
       ▼
 2. 64-bit Gradient dHash Guard (0ms) ────────> Banned Hash Match? ───> [BLOCK IMMEDIATELY]
       │  (O(1) Bitwise XOR set lookup, Hamming <= 4)                   (Profiling Skipped)
       ▼
 3. ONNX NSFW CNN Guard (15-30ms CPU) ────────> Threshold Exceeded? ──> [BLOCK & PERSIST]
       │  (Dynamic evaluation of max_nsfw threshold)                    (Profiling Skipped)
       ▼
 4. YOLOv8n & Multi-Signal Profiling (30-50ms)
       ├─ YOLOv8n Object Detection (people, food, vehicles, pets, tech...)
       ├─ Multi-Signal Visual Analyzer (billboards, screenshots, sunsets, lazy OCR)
       ├─ Social Setting Classifier (Solo, Duo, Group, Crowd)
       └─ Auto-Generated Captions & Merged Tags (Timezone & Language Adaptive)
```

---

## 🚀 Quick Start

### 1. Launch Server
The system features a **Self-Healing Bootstrap** that verifies dependencies and automatically downloads missing ONNX models:

```bash
# Single command: downloads models if missing and starts the server
python run.py
```
The server will bind to `http://localhost:8000`. Navigate there in your browser to access the interactive web playground.

### 2. Run Integration Tests
```bash
python test_server.py
```
Executes all 13 automated test suites covering input validation, dHash O(1), NSFW guardrails, YOLOv8n, timezone conversion, quad-language localization (`vi`/`en`/`ja`/`ko`), and commercial billboard detection.

---

## 📁 Repository Directory Structure

```
image-guard/
├── docs/                  # 📚 Centralized Knowledge Base & Documentation Hub
│   ├── README.md          # Documentation Sitemap & Navigation
│   ├── FEATURES_AND_APIS.md # Rapid context card for AI Agents
│   ├── 01_AGENT_RULES.md  # Mandatory Constitution for AI Agents
│   ├── 02_SYSTEM_ARCHITECTURE.md
│   ├── 03_PIPELINE_AND_ALGORITHMS.md
│   ├── 04_TAXONOMY_AND_I18N.md
│   ├── 05_API_AND_INTEGRATION.md
│   └── 06_PROCESS_TELEMETRY.md
│
├── core/                  # Configuration, DTOs, i18n & Process Logger
├── guards/                # Moderation guardrails (64-bit dHash, ONNX NSFW)
├── profiling/             # Profiling brain (YOLOv8n, Visual Analyzer, Profiler)
├── services/              # Pipeline orchestration services
├── api/                   # Native HTTP Server (ThreadingHTTPServer)
├── logs/process/          # Execution traces & microsecond telemetry
├── index.html             # Interactive Web UI Playground
├── bootstrap.py           # Dependency & atomic model downloader
├── run.py                 # 1-command startup script
└── test_server.py         # End-to-end integration test suite (13 test cases)
```
