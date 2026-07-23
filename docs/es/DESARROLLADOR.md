# Guia del Desarrollador - Iris System Detector

## Arquitectura

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

## Estructura del Proyecto

```
├── app.py                     # FastAPI main, routes, middleware
├── class.py                   # Legacy (referenced by detection)
├── Dockerfile                 # python:3.12-slim, uvicorn entrypoint
├── docker-compose.yml         # Single service, 3GB limit
├── .env.example               # Template de variables de entorno
├── requirements.txt           # 170 dependencias
├── requirements-test.txt      # Dependencias de testing
├── models/
│   ├── model_config.json      # Class groups + anomaly maps por modelo
│   ├── best.pt                # Modelo general
│   ├── gun_detector.pt        # Detector de armas
│   ├── gun.pt                 # Armas con contexto
│   └── suspicious.pt          # Comportamientos sospechosos
├── src/
│   ├── detection/
│   │   ├── yolo_detectr.py    # YOLOAnomalyDetector (clase principal)
│   │   ├── image_detector.py  # YOLOImageDetector
│   │   ├── class_mapper.py    # Mapeo de clases a categorias
│   │   └── model_utils.py     # Utilidades de modelos
│   ├── storage/
│   │   └── database.py        # SQLite: init, CRUD, migrations
│   └── logs/
│       └── memory_handler.py  # Buffer circular de logs
├── templates/
│   ├── index.html             # Landing page
│   ├── video.html             # Analisis de video
│   ├── images.html            # Analisis de imagen
│   ├── stream.html            # Monitoreo en vivo
│   ├── live.html              # Visor de stream
│   ├── logs.html              # Historial combinado
│   ├── terminal_logs.html     # Visor de logs estilo terminal
│   └── contributing.html      # Contributors
├── static/
│   ├── js/                    # 7 modulos JS vanilla
│   └── css/                   # Tailwind CSS
└── tests/
    ├── conftest.py            # Fixtures: test_db, test_video
    ├── test_database.py       # 5 tests de CRUD
    ├── test_detection.py      # 5 tests de YOLO
    └── test_image.py          # 4 tests de API de imagen
```

---

## Rutas de la Aplicacion

### Paginas (GET, retornan HTML)

| Path | Template | Descripcion |
|------|----------|-------------|
| `/` | index.html | Landing page |
| `/video-analysis` | video.html | Upload y analisis de video |
| `/image-analysis` | images.html | Upload y analisis de imagen |
| `/stream-analysis` | stream.html | Monitoreo en vivo |
| `/live` | live.html | Visor de stream MJPEG |
| `/logs` | logs.html | Historial combinado |
| `/terminal-logs` | terminal_logs.html | Logs estilo terminal |
| `/contributors` | contributing.html | Contribuidores |

### API (REST)

Ver [API.md](API.md) para referencia completa.

---

## Modulos de Deteccion

### YOLOAnomalyDetector

Clase principal de inferencia. Singleton por `model_size`.

```python
detector = YOLOAnomalyDetector(model_size="n")
results = detector.analyze_frame(frame, confidence=0.5)
# Retorna: {"persons": int, "weapons": int, "vehicles": int, ...}
```

### class_mapper.py

Convierte IDs de clase del modelo en categorias comportamentales.

**Estrategia 1 (config):** Lee `models/model_config.json`. Si el modelo tiene entrada, usa sus `class_groups`.

**Estrategia 2 (fallback):** Busca keywords en nombres de clase:
- Armas: `gun`, `knife`, `weapon`, `bomb`, `pistol`, `rifle`, ...
- Personas: `person`, `people`, `man`, `woman`, `police`, ...

### model_utils.py

- `get_native_class_names_for_model(model_name)`: Obtiene nombres de clase nativos del modelo (via metadata YAML o .pt).
- `compute_class_groups(model_name, class_counts, class_names)`: Agrega estadisticas por grupo de clases.

---

## Concuencia

| Recurso | Limite | Mecanismo |
|---------|--------|-----------|
| Video analysis | 2 | `threading.Semaphore` |
| Image analysis | 1 | `threading.Semaphore` |
| Streams en vivo | 2 | `threading.Semaphore` |
| Tasks activos | 100 | Dict in-memory |
| Cache idempotencia | 3600s | Dict in-memory |

Tasks se limpian cada 60s (TTL: 3600s).

---

## Base de Datos

### Tablas

**videos** - Analisis de video
- `id`, `filename`, `upload_time`, `frame_count`, `anomaly_count`, `anomaly_rate`
- `processing_time`, `threshold_used`, `output_video_path`, `original_video_path`
- `avg_anomaly_score`, `max_anomaly_score`, `model_used`, `class_counts` (JSON)
- `risk_level` (normal/bajo/medio/alto), `crowd_threshold`, `risk_percentage` (0-100)
- `max_people_detected`, `max_weapons_detected`

**anomaly_events** - Eventos por frame
- `id`, `video_id` (FK), `frame_number`, `anomaly_score`, `timestamp_in_video`
- `is_anomaly`, `bounding_boxes` (JSON)

**images** - Analisis de imagen
- `id`, `input_path`, `output_path`, `model_used`, `used_confidence`
- `is_anomaly`, `risk_level`, `persons_count`, `weapons_count`, `objects_count`
- `anomaly_types` (JSON), `detected_classes` (JSON), `class_counts` (JSON)
- `processing_time_ms`, `created_at`, `risk_percentage`

**streams** - Analisis de streams en vivo
- `id`, `stream_id`, `source`, `model_used`, `confidence`, `crowd_threshold`
- `start_time`, `end_time`, `duration_seconds`, `avg_fps`
- `total_frames`, `anomaly_frames`, `anomaly_rate`
- `max_person_count`, `max_weapon_count`, `class_counts` (JSON)
- `anomaly_types` (JSON), `risk_level`, `risk_percentage`

### Funciones Principales

```python
init_database() -> None
save_video_analysis(...) -> int  # retorna video_id
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

- **MemoryLogHandler**: Buffer circular de 500 entradas en memoria
- **JSONFormatter**: Output estructurado a stdout
- **Correlation ID**: UUID unico por request, propagado en headers
- **Throttling**: `/health` se loguea cada 15 min, `/favicon.ico` no se loguea

---

## Workflow de Desarrollo

1. Crear branch `feature/<nombre>` desde `main`
2. Desarrollar respetando principios SOLID
3. Correr `pytest tests/` antes de commitear
4. Push y abrir PR
5. Review + CI approval antes de merge

### Formato de Commits

Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`

### Stack

- Python 3.12+, FastAPI, Uvicorn
- YOLO (ultralytics), OpenCV, PyTorch, OpenVINO
- SQLite (WAL mode), pytest
- Tailwind CSS (frontend)
