# AGENT_RULES.md - Repository Architectural Constitution for AI Agents

> [!IMPORTANT]
> **THIS CONSTITUTION HAS BEEN CONSOLIDATED INTO THE CENTRAL KNOWLEDGE BASE AT:**
> 👉 [**`docs/01_AGENT_RULES.md`**](docs/01_AGENT_RULES.md)
>
> All AI Coding Agents (Cursor, Claude, Copilot, ChatGPT, Antigravity, etc.) are **strictly required** to read and adhere to the complete constitution located inside the `docs/` folder.

---

## Executive Summary of the 5 Inviolable Laws:

1. **Clean Layered Architecture (Preserve Boundaries)**: Strictly honor the dependency chain `api/` $\to$ `services/` $\to$ `guards/` & `profiling/` $\to$ `core/`. Never merge layers or introduce circular imports.
2. **Ponytail Minimalist Law (Standard Library First)**: NEVER install or introduce heavy web frameworks (`FastAPI`, `Flask`...). NEVER install heavy vision frameworks in runtime (`torch`, `ultralytics`...). Use native standard library and approved packages: `numpy`, `pillow`, `onnxruntime`, `rapidocr-onnxruntime`.
3. **Fail-Fast Guardrail Protocol (Early Exit)**: If an image violates Tier 1 (dHash 0ms) or Tier 2 (NSFW 15–30ms), abort immediately (`is_allowed = False`). NEVER invoke YOLOv8 or the Profiler on violating uploads.
4. **Process Logging & Telemetry Contract**: Every request must record microsecond stage latencies into `logs/process/latest_run.json`. The `database_payload` must always be structured for direct persistence into PostgreSQL JSONB or MongoDB.
5. **Multi-Signal Profiling, Localization & Timezone**: Never hardcode language strings. Route all display text through `core/i18n.py` supporting 4 languages (`vi`, `en`, `ja`, `ko`). Compute contextual time-of-day tags from the client's timezone. For non-COCO images, use `profiling/visual_analyzer.py` (aspect ratios, color warmth, lazy OCR) instead of falling back to generic defaults.

👉 Read the full constitution at: [**`docs/01_AGENT_RULES.md`**](docs/01_AGENT_RULES.md)
