# ARCHITECTURE.md - System & Technical Design

> [!IMPORTANT]
> **THIS ARCHITECTURE SPECIFICATION HAS BEEN CONSOLIDATED INTO THE CENTRAL KNOWLEDGE BASE AT:**
> 👉 [**`docs/02_SYSTEM_ARCHITECTURE.md`**](docs/02_SYSTEM_ARCHITECTURE.md)
>
> Please refer to the complete architecture documentation, dataflow diagrams, and model specifications inside the `docs/` folder.

---

## Executive Architectural Summary:

- **Pattern**: Clean Layered Architecture across 5 decoupled packages (`api` $\to$ `services` $\to$ `guards` & `profiling` $\to$ `core`).
- **HTTP Engine**: Python native `ThreadingHTTPServer`, non-blocking, multi-threaded request processing, with hard limit DoS protection (`MAX_UPLOAD_SIZE = 20MB`).
- **Pipelines & Vision Algorithms**: Mathematical formulations for 64-bit gradient dHash, local CPU ONNX NSFW CNN, and YOLOv8n pure NumPy NMS are detailed in [**`docs/03_PIPELINE_AND_ALGORITHMS.md`**](docs/03_PIPELINE_AND_ALGORITHMS.md).
- **Taxonomy & Localization**: 11 lifestyle categories, social settings, timezone engine, and quad-language support (`vi`, `en`, `ja`, `ko`) are detailed in [**`docs/04_TAXONOMY_AND_I18N.md`**](docs/04_TAXONOMY_AND_I18N.md).

👉 Read the full technical architecture at: [**`docs/02_SYSTEM_ARCHITECTURE.md`**](docs/02_SYSTEM_ARCHITECTURE.md)
