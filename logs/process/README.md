# Process Logs Directory (AI Agent Telemetry Guide)

> [!NOTE]
> Comprehensive telemetry documentation and the automated optimization protocol are maintained in:
> 👉 [**`docs/06_PROCESS_TELEMETRY.md`**](../../docs/06_PROCESS_TELEMETRY.md)

This directory contains execution traces, latency telemetry, and profiling logs designed specifically for AI Agents to inspect pipeline telemetry, diagnose latency bottlenecks, and execute automated optimization cycles.

---

## 📁 Directory Layout
```
logs/process/
├── runs/                          # Detailed JSON traces per image execution (Max 500 FIFO)
│   └── trace_<timestamp>_<id>.json
├── latest_run.json                # Trace of the most recent request (Single read for AI Agent)
├── history.jsonl                  # Append-only sequential JSON Lines for historical regressions
├── metrics_summary.json           # Rolling aggregate stats (P50, P95, Bottlenecks distribution)
└── README.md                      # This directory guide
```

---

## 🔍 How an AI Agent Reads & Optimizes

### 1. Instant Inspection (Single Call)
Read `logs/process/latest_run.json` or call HTTP `GET /logs/latest` to inspect the exact execution profile of the last processed photo:
- `image_metadata`: Format, resolution, aspect ratio, raw bytes.
- `pipeline_stages`: Microsecond-precision timings for `stage_1_validation`, `stage_2_dhash_guard`, `stage_3_nsfw_guard`, `stage_4_yolo_detection`, and `stage_5_user_profiling`.
- `performance_breakdown.bottleneck_stage`: Immediately identifies which stage consumed the most execution time.
- `agent_telemetry.optimization_opportunities`: AI-tailored hints identifying low-hanging optimization targets.

### 2. Historical Regression Analysis
Inspect `logs/process/history.jsonl` to calculate:
- Violation frequency trends.
- Latency spikes across different image resolutions.
- Impact of threshold adjustments.

### 3. Aggregate Performance Metrics
Inspect `logs/process/metrics_summary.json` or call HTTP `GET /logs/summary`:
- Total requests executed (`total_runs`).
- Average end-to-end latency (`avg_latency_ms`).
- Ratio of allowed vs blocked photos.
- Stage-by-stage bottleneck distribution.

### 4. Database-Ready Record & Merged Tags
Each run trace logs `database_payload` and `merged_tags`, structured for direct DB persistence (MongoDB document or PostgreSQL JSONB):
```json
{
  "database_payload": {
    "memory_id": "mem_20261003_034255_329e44",
    "dhash": "0x1818181818000000",
    "moderation_status": "APPROVED",
    "is_allowed": true,
    "guard_scores": {"safe": 0.9962, "nsfw": 0.0038},
    "user_profile": {
      "primary_interest": "food_and_dining",
      "interest_label": "Food & Culinary Delights",
      "confidence": 0.85,
      "social_setting": "duo",
      "people_count": 2,
      "scene_summary": "2 people with 1 pizza, 2 cups"
    },
    "note_metadata": {
      "suggested_caption": "A delicious meal to recharge energy! 🍜🍰"
    },
    "tags": {
      "merged_tags": ["#Foodie", "#FoodPorn", "#Pizza", "#Bestie"],
      "primary_tags": ["#Foodie", "#FoodPorn"],
      "object_tags": ["#Pizza"],
      "time_tags": ["#Noon"]
    }
  }
}
```
