# Developer Guide - Iris System Detector

## Architecture

```
FastAPI (app.py)
  ├── Middleware: Security Headers + Correlation ID
  ├── Page Routes: 8 HTML views
  ├── API Routes: 20+ REST endpoints
  ├── Background Tasks: Video/Stream analysis (threading)
  └── Synchronous: Image analysis

Detection Modules (src/detection/)
  ├── YOLOAnomalyDetector: Core YOLO inference
  ├── YOLOImageDetector: Image-specific analysis
  ├── class_mapper.py: Class ID -> behavioral category mapping
  └── model_utils.py: Model metadata + class group aggregation

Storage (src/storage/)
  └── database.py: SQLite with WAL, 4 tables, 17 migrations

Logging (src/logs/)
  └── memory_handler.py: In-memory circular buffer (500 entries)

Frontend
  ├── templates/: 8 Jinja2 HTML files (Tailwind CSS)
  └── static/js/: 7 JS modules (vanilla, no framework)
```

---

## Project Structure

```
├── app.py                     # FastAPI main, routes, middleware
├── class.py                   # Legacy (referenced by detection)
├── Dockerfile                 # python:3.12-slim, uvicorn entrypoint
├── docker-compose.yml         # Single service, 3GB limit
├── .env.example               # Environment variable template
├── requirements.txt           # 170 dependencies
├── requirements-test.txt      # Test dependencies
├── models/
│   ├── model_config.json      # Class groups + anomaly maps per model
│   ├── best.pt                # General model
│   ├── gun_detector.pt        # Firearm detector
│   ├── gun.pt                 # Weapons with person context
│   └── suspicious.pt          # Suspicious behaviors
├── src/
│   ├── detection/
│   │   ├── yolo_detectr.py    # YOLOAnomalyDetector (main class)
│   │   ├── image_detector.py  # YOLOImageDetector
│   │   ├── class_mapper.py    # Class to category mapping
│   │   └── model_utils.py     # Model utilities
│   ├── storage/
│   │   └── database.py        # SQLite: init, CRUD, migrations
│   └── logs/
│       └── memory_handler.py  # Circular log buffer
├── templates/
│   ├── index.html             # Landing page
│   ├── video.html             # Video analysis
│   ├── images.html            # Image analysis
│   ├── stream.html            # Live monitoring
│   ├── live.html              # Stream viewer
│   ├── logs.html              # Combined history
│   ├── terminal_logs.html     # Terminal-style log viewer
│   └── contributing.html      # Contributors
├── static/
│   ├── js/                    # 7 vanilla JS modules
│   └── css/                   # Tailwind CSS
└── tests/
    ├── conftest.py            # Fixtures: test_db, test_video
    ├── test_database.py       # 5 CRUD tests
    ├── test_detection.py      # 5 YOLO tests
    └── test_image.py          # 4 image API tests
```

---

## Application Routes

### Page Routes (GET, return HTML)

| Path | Template | Description |
|------|----------|-------------|
| `/` | index.html | Landing page |
| `/video-analysis` | video.html | Video upload and analysis |
| `/image-analysis` | images.html | Image upload and analysis |
| `/stream-analysis` | stream.html | Live monitoring |
| `/live` | live.html | MJPEG stream viewer |
| `/logs` | logs.html | Combined history |
| `/terminal-logs` | terminal_logs.html | Terminal-style log viewer |
| `/contributors` | contributing.html | Contributors |

### API Routes (REST)

See [API.md](API.md) for complete reference.

---

## Detection Modules

### YOLOAnomalyDetector

Main inference class. Singleton per `model_size`.

```python
detector = YOLOAnomalyDetector(model_size="n")
results = detector.analyze_frame(frame, confidence=0.5)
# Returns: {"persons": int, "weapons": int, "vehicles": int, ...}
```

### class_mapper.py

Converts model class IDs to behavioral categories.

**Strategy 1 (config):** Reads `models/model_config.json`. If the model has an entry, uses its `class_groups`.

**Strategy 2 (fallback):** Searches class names for keywords:
- Weapons: `gun`, `knife`, `weapon`, `bomb`, `pistol`, `rifle`, ...
- Persons: `person`, `people`, `man`, `woman`, `police`, ...

### model_utils.py

- `get_native_class_names_for_model(model_name)`: Gets native class names from model (via metadata YAML or .pt).
- `compute_class_groups(model_name, class_counts, class_names)`: Aggregates stats by class group.

---

## Concurrency

| Resource | Limit | Mechanism |
|----------|-------|-----------|
| Video analysis | 2 | `threading.Semaphore` |
| Image analysis | 1 | `threading.Semaphore` |
| Live streams | 2 | `threading.Semaphore` |
| Active tasks | 100 | In-memory dict |
| Idempotency cache | 3600s | In-memory dict |

Tasks are cleaned up every 60s (TTL: 3600s).

---

## Database

### Tables

**videos** - Video analysis records
- `id`, `filename`, `upload_time`, `frame_count`, `anomaly_count`, `anomaly_rate`
- `processing_time`, `threshold_used`, `output_video_path`, `original_video_path`
- `avg_anomaly_score`, `max_anomaly_score`, `model_used`, `class_counts` (JSON)
- `risk_level` (normal/bajo/medio/alto), `crowd_threshold`, `risk_percentage` (0-100)
- `max_people_detected`, `max_weapons_detected`

**anomaly_events** - Per-frame events
- `id`, `video_id` (FK), `frame_number`, `anomaly_score`, `timestamp_in_video`
- `is_anomaly`, `bounding_boxes` (JSON)

**images** - Image analysis records
- `id`, `input_path`, `output_path`, `model_used`, `used_confidence`
- `is_anomaly`, `risk_level`, `persons_count`, `weapons_count`, `objects_count`
- `anomaly_types` (JSON), `detected_classes` (JSON), `class_counts` (JSON)
- `processing_time_ms`, `created_at`, `risk_percentage`

**streams** - Live stream analysis records
- `id`, `stream_id`, `source`, `model_used`, `confidence`, `crowd_threshold`
- `start_time`, `end_time`, `duration_seconds`, `avg_fps`
- `total_frames`, `anomaly_frames`, `anomaly_rate`
- `max_person_count`, `max_weapon_count`, `class_counts` (JSON)
- `anomaly_types` (JSON), `risk_level`, `risk_percentage`

### Key Functions

```python
init_database() -> None
save_video_analysis(...) -> int  # returns video_id
get_all_videos(limit, offset) -> List[Dict]
get_video_by_id(video_id) -> Optional[Dict]
get_anomaly_events(video_id) -> List[Dict]
search_videos(filename, min_anomaly_rate, ...) -> List[Dict]
delete_video(video_id) -> bool
save_image_analysis(data, risk_percentage) -> int
get_all_images(limit, offset) -> List[Dict]
save_stream_analysis(data, risk_percentage) -> int
get_statistics() -> Dict
```

---

## Logging

- **MemoryLogHandler**: 500-entry circular buffer in memory
- **JSONFormatter**: Structured output to stdout
- **Correlation ID**: Unique UUID per request, propagated in headers
- **Throttling**: `/health` logged every 15 min, `/favicon.ico` not logged

---

## Development Workflow

1. Create branch `feature/<name>` from `main`
2. Develop following SOLID principles
3. Run `pytest tests/` before committing
4. Push and open a PR
5. Review + CI approval before merge

### Commit Format

Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`

### Stack

- Python 3.12+, FastAPI, Uvicorn
- YOLO (ultralytics), OpenCV, PyTorch, OpenVINO
- SQLite (WAL mode), pytest
- Tailwind CSS (frontend)
