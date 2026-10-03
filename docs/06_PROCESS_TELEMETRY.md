# 📈 06 - Process Telemetry & Performance Observability

This document details the microsecond-precision telemetry system, execution trace schemas, and self-optimization protocols designed for AI Agents and DevOps engineers.

---

## 1. Telemetry Directory Structure

All runtime traces, historical logs, and aggregate metrics are persisted inside `logs/process/`:

```
logs/process/
├── runs/                          # Detailed JSON execution traces per photo (Max 500 FIFO)
│   └── trace_<timestamp>_<id>.json
├── latest_run.json                # Snapshot of the most recent request (Fast single-read for AI)
├── history.jsonl                  # Append-only sequential log for historical regression analysis
└── metrics_summary.json           # Rolling aggregate statistics (P50, P95, bottleneck distributions)
```

---

## 2. Anatomy of `latest_run.json`

This file is atomically updated after each request. AI Agents can read it directly from disk or query `GET /logs/latest`:

```json
{
  "trace_id": "trace_20261003_091920_eb73d9",
  "timestamp": "2026-10-03T16:19:20.912345+07:00",
  "image_metadata": {
    "format": "JPEG",
    "width": 1280,
    "height": 720,
    "aspect_ratio": 1.7778,
    "size_bytes": 142058
  },
  "pipeline_stages": {
    "stage_1_validation": { "duration_ms": 0.42, "status": "OK" },
    "stage_2_dhash_guard": { "duration_ms": 0.15, "dhash": "0x1818181818000000", "status": "CLEAN" },
    "stage_3_nsfw_guard": { "duration_ms": 19.84, "scores": {"safe": 0.9962, "nsfw": 0.0038}, "status": "PASS" },
    "stage_4_yolo_detection": { "duration_ms": 32.10, "objects_detected": 0, "status": "PASS" },
    "stage_5_user_profiling": { "duration_ms": 11.25, "interest": "sunset_and_nature", "status": "PASS" }
  },
  "performance_breakdown": {
    "total_latency_ms": 63.76,
    "bottleneck_stage": "stage_4_yolo_detection",
    "bottleneck_percentage": 50.34
  },
  "agent_telemetry": {
    "optimization_opportunities": [
      "YOLO inference consumed >50% of total time. Consider tuning letterbox or quantizing to INT8 if running on ultra-low-power edge."
    ]
  },
  "database_payload": {
    "memory_id": "mem_20261003_091921_c64985",
    "dhash": "0x1818181818000000",
    "moderation_status": "APPROVED",
    "is_allowed": true,
    "user_profile": { ... },
    "note_metadata": { ... }
  }
}
```

---

## 3. Rolling Metrics: `metrics_summary.json`

Maintained continuously and available via `GET /logs/summary`:
- `total_runs`: Total number of requests processed.
- `allowed_runs` vs `blocked_runs`: Ratio of clean vs violating uploads.
- `avg_latency_ms`: Rolling end-to-end average pipeline execution time.
- `bottleneck_distribution`: Frequency count identifying which stage consumed the highest latency.
- `error_count`: Total unhandled runtime exceptions.

---

## 4. Automated AI Agent Optimization Protocol

When an AI Agent is tasked with diagnosing or improving system performance:
1. **Step 1**: Query `GET /logs/summary` or view `metrics_summary.json` to identify the dominant bottleneck stage (`stage_3_nsfw_guard` vs `stage_4_yolo_detection`).
2. **Step 2**: Inspect `history.jsonl` to assess latency variance across image sizes and resolutions.
3. **Step 3**: Consult [`01_AGENT_RULES.md`](01_AGENT_RULES.md) to ensure any architectural adjustments comply with the Ponytail minimalism law (pure standard library, zero unapproved dependencies).
4. **Step 4**: Execute `python test_server.py` to verify that 100% of integration test suites pass before and after changes.
