import os
import sys
import tempfile
import time
import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, BackgroundTasks, Request, Header
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import threading
from pydantic import BaseModel
import logging
import mimetypes

load_dotenv()

env_value = os.getenv("EMAIL_CONFIG", "false").lower()
MODEL_SIZE = os.getenv("MODEL_SIZE", "s")
DEVICE = os.getenv("DEVICE", "cpu")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
CROWD_THRESHOLD = int(os.getenv("CROWD_THRESHOLD", "5"))
LOITER_THRESHOLD = float(os.getenv("LOITER_THRESHOLD", "10.0"))
EMAIL_CONFIG = env_value in ("true", "1", "yes")
SITE_TITLE = os.getenv("SITE_TITLE", "Iris")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "300"))
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Importaciones de la base de datos extendida
from storage.database import (
    init_database,
    save_video_analysis,
    get_all_videos,
    get_video_by_id,
    search_videos,
    delete_video,
    get_statistics,
    save_image_analysis,
    get_all_images,
    get_image_by_id,
    delete_image,
    save_stream_analysis,
    get_all_streams,
    get_stream_by_id,
    delete_stream,
    get_anomaly_events,
)

from logs.memory_handler import MemoryLogHandler
from detection.model_utils import get_native_class_names_for_model, compute_class_groups

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])

memory_log_handler = MemoryLogHandler(capacity=500)
memory_log_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(memory_log_handler)

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
VIDEOS_DIR = os.path.join(STATIC_DIR, "videos")
IMAGES_DIR = os.path.join(STATIC_DIR, "images") 
MODELS_DIR = os.path.join(BASE_DIR, "models") # Nueva carpeta de modelos personalizados

os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# Parseo de Modelos Disponibles configurados en el .env
AVAILABLE_MODELS = [m.strip() for m in os.getenv("AVAILABLE_MODELS", "best.pt").split(",") if m.strip()]
DEFAULT_MODEL = os.getenv("MODEL_NAME", "best.pt")
if DEFAULT_MODEL not in AVAILABLE_MODELS:
    AVAILABLE_MODELS.insert(0, DEFAULT_MODEL)

# =====================================================================
# FILE VALIDATION UTILITIES
# =====================================================================

IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89\x50\x4e\x47": "image/png",
    b"\x47\x49\x46\x38": "image/gif",
    b"\x42\x4d": "image/bmp",
}

VIDEO_SIGNATURES: dict[bytes, str] = {
    b"\x1a\x45\xdf\xa3": "video/webm",
    b"\x52\x49\x46\x46": "video/avi",
}

EXT_TO_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".bmp": "image/bmp", ".webp": "image/webp",
    ".mp4": "video/mp4", ".avi": "video/x-msvideo",
    ".mov": "video/quicktime", ".mkv": "video/x-matroska",
}

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def detect_mime_by_magic(content: bytes) -> str:
    for sig, mime in IMAGE_SIGNATURES.items():
        if content[:len(sig)] == sig:
            return mime
    for sig, mime in VIDEO_SIGNATURES.items():
        if content[:len(sig)] == sig:
            return mime
    if len(content) > 8 and content[4:8] == b"ftyp":
        return "video/mp4"
    return "unknown"


def validate_upload(content: bytes, filename: str, content_type: str, expected_type: str):
    ext = os.path.splitext(filename)[1].lower()
    allowed = ALLOWED_VIDEO_EXTENSIONS if expected_type == "video" else ALLOWED_IMAGE_EXTENSIONS

    if ext not in allowed:
        raise HTTPException(400, f"La extensión '{ext}' no está permitida para archivos de tipo {expected_type}")

    if not content_type.startswith(f"{expected_type}/"):
        raise HTTPException(400, f"El tipo de contenido debe ser {expected_type}/*, se recibió '{content_type}'")

    magic_mime = detect_mime_by_magic(content)
    if magic_mime == "unknown":
        return

    expected_mime = EXT_TO_MIME.get(ext)
    if expected_mime and magic_mime != expected_mime:
        raise HTTPException(400, f"La extensión '{ext}' no coincide con el formato real del archivo ('{magic_mime}')")


# =====================================================================
# LIFESPAN MANAGEMENT (MANEJADOR DE CONTEXTO)
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Evento de inicialización (Startup)
    init_database()
    _cleanup_expired_tasks()
    logger.info("Application started successfully via lifespan context")
    yield
    # Aquí puedes agregar lógica de cierre (Shutdown) si es necesario en el futuro
    logger.info("Application shutting down")

app = FastAPI(
    title="Iris System Detector",
    description="YOLOv8/YOLO11-based video and image anomaly detection",
    version="4.0.0",
    lifespan=lifespan
)

mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("video/x-msvideo", ".avi")
mimetypes.add_type("image/jpeg", ".jpg")
mimetypes.add_type("image/png", ".png")

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src blob:; connect-src 'self'"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    path = request.url.path
    if path not in ("/api/logs",) and not path.startswith("/static/"):
        logger.info(json.dumps({
            "correlation_id": correlation_id,
            "method": request.method,
            "path": path,
            "status": response.status_code,
        }))
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_id = str(uuid.uuid4())
    logger.error(f"Unhandled error {error_id}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Ocurrió un error. Reporte el código: {error_id}"}
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

TASKS = {}
TASKS_TTL_SECONDS = 3600
TASKS_MAX_ACTIVE = 100


def _cleanup_expired_tasks():
    """Remove completed/failed tasks older than TASKS_TTL_SECONDS"""
    now = time.time()
    expired = [
        tid for tid, t in TASKS.items()
        if t.get("status") in ("completed", "failed")
        and now - t.get("created_at", now) > TASKS_TTL_SECONDS
    ]
    for tid in expired:
        del TASKS[tid]

    expired_keys = [
        k for k, v in _idempotency_cache.items()
        if now - v.get("created_at", now) > IDEMPOTENCY_TTL
    ]
    for k in expired_keys:
        del _idempotency_cache[k]

    active = [tid for tid, t in TASKS.items() if t.get("status") in ("queued", "processing")]
    while len(active) > TASKS_MAX_ACTIVE:
        oldest = active.pop(0)
        TASKS[oldest]["status"] = "failed"
        TASKS[oldest]["error"] = "Tarea descartada: demasiadas tareas activas"

    timer = threading.Timer(60, _cleanup_expired_tasks)
    timer.daemon = True
    timer.start()

_video_semaphore = threading.Semaphore(2)
_image_semaphore = threading.Semaphore(1)
_stream_semaphore = threading.Semaphore(2)

IDEMPOTENCY_TTL = 3600
_idempotency_cache: Dict[str, Dict[str, Any]] = {}


def _get_cached_result(key: str):
    entry = _idempotency_cache.get(key)
    if entry and time.time() - entry["created_at"] < IDEMPOTENCY_TTL:
        return entry["result"]
    if entry:
        del _idempotency_cache[key]
    return None


def _store_result(key: str, result: Any):
    _idempotency_cache[key] = {"result": result, "created_at": time.time()}


def run_analysis_task(
    task_id: str,
    file_path: str,
    output_path: str,
    crowd_threshold: int,
    confidence: float,
    original_filename: str,
    model_name: Optional[str] = None,
):
    if not _video_semaphore.acquire(timeout=30):
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["error"] = "Servidor ocupado, todos los slots de video ocupados. Intente nuevamente."
        return

    try:
        from detection.yolo_detector import get_yolo_detector

        TASKS[task_id]["status"] = "processing"

        def update_progress(p):
            TASKS[task_id]["progress"] = p

        model_path = os.path.join("models", model_name) if model_name else None
        yolo = get_yolo_detector(
            model_size=MODEL_SIZE,
            model_path=model_path,
            device=DEVICE,
            confidence_threshold=confidence,
            crowd_threshold=crowd_threshold,
            loiter_threshold_seconds=LOITER_THRESHOLD,
        )
        stats = yolo.process_video(
            file_path, output_path, progress_callback=update_progress
        )

        video_id = save_video_analysis(
            filename=original_filename,
            frame_count=stats["total_frames"],
            anomaly_count=stats["anomaly_frames"],
            anomaly_rate=stats["anomaly_rate"],
            processing_time=stats["processing_time"],
            threshold_used=crowd_threshold,
            anomaly_scores=[
                1.0 if r["is_anomaly"] else 0.0 for r in stats["frame_results"]
            ],
            anomaly_flags=[r["is_anomaly"] for r in stats["frame_results"]],
            output_video_path=output_path,
            original_video_path=file_path,
            model_name=model_name or "default",
        )

        if stats["anomaly_frames"] > 0:
            try:
                from alerts.email_alerts import send_anomaly_alert

                send_anomaly_alert(
                    anomaly_types=list(stats["anomaly_types_count"].keys()),
                    details=[
                        f"Video: {original_filename}",
                        f"Anomalias: {stats['anomaly_frames']} cuadros",
                        f"Tasa: {stats['anomaly_rate'] * 100:.1f}%",
                    ],
                    video_filename=original_filename,
                    video_id=video_id,
                )
            except Exception as e:
                logger.error(f"Error de email: {e}")

        TASKS[task_id]["status"] = "completed"
        TASKS[task_id]["progress"] = 100
        
        final_risk = "normal"
        risk_percentage = 0

        if stats["max_weapons"] > 0:
            final_risk = "critico"
            risk_percentage = 100
        elif "ALTERCADO_POTENCIAL" in stats["anomaly_types_count"]:
            final_risk = "alto"
            risk_percentage = 85
        elif stats["anomaly_frames"] > 0:
            final_risk = "medio"
            risk_percentage = 50
        else:
            final_risk = "normal"
            risk_percentage = 10
        
        TASKS[task_id]["result"] = {
            "video_id": video_id,
            "total_frames": stats["total_frames"],
            "anomaly_frames": stats["anomaly_frames"],
            "anomaly_rate": stats["anomaly_rate"],
            "max_people_detected": stats["max_people"],
            "max_weapons_detected": stats["max_weapons"],
            "crowd_threshold": crowd_threshold,
            "anomaly_types": stats["anomaly_types_count"],
            "processing_time": stats["processing_time"],
            "annotated_video_url": f"/static/videos/{os.path.basename(output_path)}",
            "risk_level": final_risk,
            "risk_percentage": risk_percentage,
            "model_name": model_name or "default",
            "class_counts": stats.get("class_counts", {}),
            "model_classes": list(yolo.model_class_names.values()) if hasattr(yolo, 'model_class_names') else [],
            "class_groups": compute_class_groups(
                model_name or "default",
                stats.get("class_counts", {}),
                getattr(yolo, 'model_class_names', {})
            )
        }

    except Exception as e:
        error_id = str(uuid.uuid4())
        logger.error(f"Task failed [{error_id}]: {e}", exc_info=True)
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["error"] = f"Ocurrió un error. Reporte el código: {error_id}"
    finally:
        _video_semaphore.release()
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except:
                pass


class HealthResponse(BaseModel):
    status: str
    version: str


# =====================================================================
# TEMPLATE VIEWS ROUTING
# =====================================================================

@app.get("/", response_class=HTMLResponse)
async def view_root():
    template_path = os.path.join(TEMPLATES_DIR, "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read().replace("{{SITE_TITLE}}", SITE_TITLE)
        return HTMLResponse(content=content)
    
@app.get("/logs", response_class=HTMLResponse)
async def view_logs():
    template_path = os.path.join(TEMPLATES_DIR, "logs.html")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read().replace("{{SITE_TITLE}}", SITE_TITLE)
        return HTMLResponse(content=content)
    
@app.get("/video-analysis", response_class=HTMLResponse)
async def view_video_analysis():
    template_path = os.path.join(TEMPLATES_DIR, "video.html")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read().replace("{{SITE_TITLE}}", SITE_TITLE)
        return HTMLResponse(content=content)
    
@app.get("/stream-analysis", response_class=HTMLResponse)
async def view_stream_analysis():
    template_path = os.path.join(TEMPLATES_DIR, "stream.html")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read().replace("{{SITE_TITLE}}", SITE_TITLE)
        return HTMLResponse(content=content)

@app.get("/image-analysis", response_class=HTMLResponse)
async def view_image_analysis():
    template_path = os.path.join(TEMPLATES_DIR, "images.html")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read().replace("{{SITE_TITLE}}", SITE_TITLE)
        return HTMLResponse(content=content)
    
@app.get("/contributors", response_class=HTMLResponse)
async def view_contributors():
    template_path = os.path.join(TEMPLATES_DIR, "contributing.html")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read().replace("{{SITE_TITLE}}", SITE_TITLE)
        return HTMLResponse(content=content)


@app.get("/health")
async def health():
    import shutil
    from storage.database import get_connection

    health_status = {
        "status": "healthy",
        "version": app.version,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.") + "Z",
        "checks": {}
    }

    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        health_status["checks"]["database"] = "ok"
    except Exception:
        health_status["checks"]["database"] = "error"
        health_status["status"] = "degraded"

    try:
        usage = shutil.disk_usage(BASE_DIR)
        free_gb = usage.free / (1024 ** 3)
        health_status["checks"]["disk_free_gb"] = round(free_gb, 1)
        if usage.free / usage.total < 0.1:
            health_status["status"] = "degraded"
    except Exception:
        health_status["checks"]["disk"] = "unknown"

    missing = [m for m in AVAILABLE_MODELS if not os.path.exists(os.path.join(MODELS_DIR, m))]
    health_status["checks"]["models"] = "ok" if not missing else f"missing: {missing}"
    if missing:
        health_status["status"] = "degraded"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)


@app.get("/api/logs")
async def get_logs(
    level: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    return memory_log_handler.get_logs(level=level, limit=limit, offset=offset)


@app.get("/terminal-logs")
async def terminal_logs_page():
    with open(os.path.join(TEMPLATES_DIR, "terminal_logs.html"), encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content.replace("{{SITE_TITLE}}", SITE_TITLE))


# =====================================================================
# MODEL MANIFEST UTILITIES
# =====================================================================

@app.get("/models")
async def get_available_models():
    """Retorna los modelos cargables configurados para el entorno de ejecucion"""
    return {"models": AVAILABLE_MODELS, "default": DEFAULT_MODEL}


@app.get("/config")
async def get_config():
    """Retorna configuración pública del servidor para el frontend"""
    return {"max_file_size_mb": MAX_FILE_SIZE_MB}


# =====================================================================
# VIDEO INFERENCE ENDPOINTS
# =====================================================================

@app.post("/analyze-yolo")
async def analyze_yolo(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    crowd_threshold: int = Query(5),
    confidence: float = Query(CONFIDENCE_THRESHOLD),
    model_name: Optional[str] = Query(None),
    x_idempotency_key: Optional[str] = Header(None)
):
    if x_idempotency_key:
        cached = _get_cached_result(x_idempotency_key)
        if cached is not None:
            return cached

    safe_filename = os.path.basename(file.filename or "video.mp4")

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    try:
        content = await file.read()

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(413, f"El archivo excede el tamaño máximo de {MAX_FILE_SIZE_MB}MB")

        validate_upload(content, safe_filename, file.content_type or "", "video")

        temp.write(content)
        temp.close()
        temp_path = temp.name

        import cv2
        cap = cv2.VideoCapture(temp_path)
        if not cap.isOpened():
            cap.release()
            raise HTTPException(400, "El archivo de video está corrupto o no se puede leer")
        cap.release()
    except HTTPException:
        temp.close()
        try:
            os.unlink(temp.name)
        except:
            pass
        raise
    except:
        temp.close()
        raise HTTPException(500, "No se pudo guardar el archivo")

    if model_name and model_name not in AVAILABLE_MODELS:
        raise HTTPException(400, f"El modelo '{model_name}' no está registrado en los modelos disponibles.")

    task_id = str(uuid.uuid4())
    output_filename = f"yolo_{task_id}.mp4"
    output_path = os.path.join(VIDEOS_DIR, output_filename)

    TASKS[task_id] = {"status": "queued", "progress": 0, "result": None, "created_at": time.time()}

    background_tasks.add_task(
        run_analysis_task,
        task_id,
        temp_path,
        output_path,
        crowd_threshold,
        confidence,
        safe_filename,
        model_name,
    )

    result = {"task_id": task_id}
    if x_idempotency_key:
        _store_result(x_idempotency_key, result)

    return result


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "Tarea no encontrada")
    return task


@app.get("/history")
async def get_history(
    filename: Optional[str] = None, min_anomaly_rate: Optional[float] = None
):
    if filename or min_anomaly_rate:
        return search_videos(filename=filename, min_anomaly_rate=min_anomaly_rate)
    return get_all_videos()


@app.get("/history/{video_id}")
async def get_history_item(video_id: int):
    result = get_video_by_id(video_id)
    if not result:
        raise HTTPException(404, "Video no encontrado")
    return result


@app.delete("/history/{video_id}")
async def delete_history_item(video_id: int):
    video = get_video_by_id(video_id)
    if video and video.get("output_video_path"):
        try:
            os.remove(video["output_video_path"])
        except:
            pass

    success = delete_video(video_id)
    if not success:
        raise HTTPException(404, "Video no encontrado")
    return {"deleted": True}


# =====================================================================
# STATIC IMAGE INFERENCE ENDPOINTS (CON SOPORTE PARA CARPETA MODELS/)
# =====================================================================

@app.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    crowd_threshold: int = Query(5),
    confidence: float = Query(CONFIDENCE_THRESHOLD),
    model_name: Optional[str] = Query(None),
    x_idempotency_key: Optional[str] = Header(None)
):
    if x_idempotency_key:
        cached = _get_cached_result(x_idempotency_key)
        if cached is not None:
            return cached

    # Validar y resolver que modelo usar
    selected_model = model_name if model_name else DEFAULT_MODEL
    if selected_model not in AVAILABLE_MODELS:
        raise HTTPException(400, f"El modelo '{selected_model}' no está registrado en los modelos disponibles.")

    model_path = os.path.join("models", selected_model)

    safe_filename = os.path.basename(file.filename or "image.jpg")
    ext = os.path.splitext(safe_filename)[1] or ".jpg"
    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        content = await file.read()

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(413, f"El archivo excede el tamaño máximo de {MAX_FILE_SIZE_MB}MB")

        validate_upload(content, safe_filename, file.content_type or "", "image")

        temp_input.write(content)
        temp_input.close()
        temp_path = temp_input.name

        from PIL import Image
        try:
            img = Image.open(temp_path)
            img.verify()
        except Exception:
            raise HTTPException(400, "El archivo de imagen está corrupto o no se puede leer")
    except HTTPException:
        temp_input.close()
        try:
            os.unlink(temp_input.name)
        except:
            pass
        raise
    except:
        temp_input.close()
        raise HTTPException(500, "No se pudo guardar la imagen")

    # Configurar rutas de salida fijas
    unique_id = str(uuid.uuid4())
    output_filename = f"out_{unique_id}{ext}"
    output_path = os.path.join(IMAGES_DIR, output_filename)

    try:
        from detection.image_detector import get_image_detector

        if not _image_semaphore.acquire(blocking=False):
            raise HTTPException(503, "Servidor ocupado, intente nuevamente")

        try:
            detector = get_image_detector(
                model_path=model_path,
                default_confidence=confidence,
                crowd_threshold=crowd_threshold,
                device=DEVICE
            )

            raw_results = await asyncio.to_thread(
                detector.process_image, temp_input.name, output_path, confidence
            )
        finally:
            _image_semaphore.release()
        
        # Guardar en base de datos
        db_id = save_image_analysis(raw_results)
        
        # Agregar metadata web complementaria para el frontend
        raw_results["image_id"] = db_id
        raw_results["annotated_image_url"] = f"/static/images/{output_filename}"
        
        # Calcular porcentaje de riesgo analogo al pipeline de videos
        risk_pct = 10
        if raw_results["risk_level"] == "critico":
            risk_pct = 100
        elif raw_results["risk_level"] == "alto":
            risk_pct = 85
        elif raw_results["is_anomaly"]:
            risk_pct = 50
            
        raw_results["risk_percentage"] = risk_pct
        raw_results["crowd_threshold"] = crowd_threshold
        raw_results["model_classes"] = list(detector.model_class_names.values()) if hasattr(detector, 'model_class_names') else []
        raw_results["class_groups"] = compute_class_groups(
            raw_results.get("model_used", ""),
            raw_results.get("class_counts", {}),
            getattr(detector, 'model_class_names', {})
        )

        if x_idempotency_key:
            _store_result(x_idempotency_key, raw_results)

        return raw_results

    except HTTPException:
        raise
    except Exception as e:
        error_id = str(uuid.uuid4())
        logger.error(f"Image analysis failed [{error_id}]: {e}", exc_info=True)
        raise HTTPException(500, f"Ocurrió un error. Reporte el código: {error_id}")
    finally:
        if os.path.exists(temp_input.name):
            try:
                os.unlink(temp_input.name)
            except:
                pass


@app.get("/image-history")
async def get_image_history(limit: int = Query(50), offset: int = Query(0)):
    """Recupera la lista paginada de imagenes analizadas de la base de datos"""
    return get_all_images(limit=limit, offset=offset)


@app.get("/image-history/{image_id}")
async def get_image_history_item(image_id: int):
    """Obtiene detalles especificos de una imagen registrada"""
    result = get_image_by_id(image_id)
    if not result:
        raise HTTPException(404, "Registro de imagen no encontrado")
    return result


@app.delete("/image-history/{image_id}")
async def delete_image_history_item(image_id: int):
    """Elimina la imagen de la BD y purga su archivo de disco"""
    success = delete_image(image_id)
    if not success:
        raise HTTPException(404, "Imagen no encontrada")
    return {"deleted": True}


# =====================================================================
# STREAM HISTORY ENDPOINTS
# =====================================================================

@app.get("/stream-history")
async def get_stream_history(limit: int = Query(50), offset: int = Query(0)):
    return get_all_streams(limit=limit, offset=offset)


@app.get("/stream-history/{stream_id}")
async def get_stream_history_item(stream_id: int):
    result = get_stream_by_id(stream_id)
    if not result:
        raise HTTPException(404, "Registro de stream no encontrado")
    return result


@app.delete("/stream-history/{stream_id}")
async def delete_stream_history_item(stream_id: int):
    success = delete_stream(stream_id)
    if not success:
        raise HTTPException(404, "Registro de stream no encontrado")
    return {"deleted": True}


# =====================================================================
# COMBINED HISTORY (videos + images + streams)
# =====================================================================

@app.get("/combined-history")
async def get_combined_history(
    filename: Optional[str] = Query(None),
    min_anomaly_rate: Optional[float] = Query(None),
    record_type: Optional[str] = Query(None),
):
    videos = get_all_videos(limit=1000)
    images = get_all_images(limit=1000)
    streams = get_all_streams(limit=1000)

    result = []

    for v in videos:
        item = dict(v)
        item["record_type"] = "video"
        result.append(item)

    for img in images:
        result.append({
            "id": img["id"],
            "filename": os.path.basename(img["input_path"]),
            "upload_time": img["created_at"],
            "frame_count": None,
            "anomaly_count": 1 if img["is_anomaly"] else 0,
            "anomaly_rate": 1.0 if img["is_anomaly"] else 0.0,
            "threshold_used": img["used_confidence"],
            "model_used": img.get("model_used", ""),
            "risk_level": img["risk_level"],
            "processing_time": img["processing_time_ms"] / 1000.0 if img.get("processing_time_ms") else None,
            "record_type": "image",
        })

    for s in streams:
        result.append({
            "id": s["id"],
            "filename": s.get("source", "Desconocido"),
            "upload_time": s.get("start_time", ""),
            "frame_count": s.get("total_frames", 0),
            "anomaly_count": s.get("anomaly_frames", 0),
            "anomaly_rate": s.get("anomaly_rate", 0.0),
            "threshold_used": s.get("confidence", 0),
            "model_used": s.get("model_used", ""),
            "risk_level": s.get("risk_level", "normal"),
            "processing_time": s.get("duration_seconds", 0),
            "record_type": "stream",
        })

    if record_type == "video":
        result = [r for r in result if r["record_type"] == "video"]
    elif record_type == "image":
        result = [r for r in result if r["record_type"] == "image"]
    elif record_type == "stream":
        result = [r for r in result if r["record_type"] == "stream"]

    if filename:
        fl = filename.lower()
        result = [r for r in result if fl in r.get("filename", "").lower()]

    if min_anomaly_rate is not None:
        result = [r for r in result if (r.get("anomaly_rate") or 0) >= min_anomaly_rate]

    result.sort(key=lambda r: r.get("upload_time", "") or "", reverse=True)

    return result


# =====================================================================
# RECORD DETAIL (para modal de logs)
# =====================================================================

@app.get("/record-detail/{record_type}/{record_id}")
async def get_record_detail(record_type: str, record_id: int):
    if record_type == "video":
        record = get_video_by_id(record_id)
        if not record:
            raise HTTPException(404, "Video no encontrado")
        events = get_anomaly_events(record_id)
        record["anomaly_events"] = events
        record["record_type"] = "video"
        class_counts = {}
        for ev in events:
            bboxes = ev.get("bounding_boxes", [])
            if isinstance(bboxes, list):
                for box in bboxes:
                    name = box.get("class_name", "unknown")
                    class_counts[name] = class_counts.get(name, 0) + 1
        record["class_counts"] = class_counts

        model_name = record.get("model_name") or record.get("model_used", "")
        native_names = get_native_class_names_for_model(model_name)
        if not native_names:
            native_names = list(class_counts.keys())
        record["model_classes"] = native_names

        names_map = {i: name for i, name in enumerate(native_names)}
        record["class_groups"] = compute_class_groups(model_name, class_counts, names_map)
        return record

    elif record_type == "image":
        record = get_image_by_id(record_id)
        if not record:
            raise HTTPException(404, "Imagen no encontrada")
        record["record_type"] = "image"
        model_name = record.get("model_used", "")
        native_names = get_native_class_names_for_model(model_name)
        if not native_names:
            native_names = record.get("detected_classes", [])
        record["model_classes"] = native_names
        names_map = {i: name for i, name in enumerate(native_names)}
        class_counts = record.get("class_counts", {})
        if isinstance(class_counts, str):
            try:
                class_counts = json.loads(class_counts)
            except Exception:
                class_counts = {}
        record["class_groups"] = compute_class_groups(model_name, class_counts, names_map)
        return record

    elif record_type == "stream":
        record = get_stream_by_id(record_id)
        if not record:
            raise HTTPException(404, "Stream no encontrado")
        record["record_type"] = "stream"
        model_name = record.get("model_name") or record.get("model_used", "")
        native_names = get_native_class_names_for_model(model_name)
        record["model_classes"] = native_names
        class_counts = record.get("class_counts", {})
        if isinstance(class_counts, str):
            try:
                class_counts = json.loads(class_counts)
            except Exception:
                class_counts = {}
        record["class_counts"] = class_counts
        names_map = {i: name for i, name in enumerate(native_names)}
        record["class_groups"] = compute_class_groups(model_name, class_counts, names_map)
        return record

    else:
        raise HTTPException(400, f"Tipo de registro inválido: {record_type}. Use video, image o stream.")


# =====================================================================
# GLOBAL STATS & CORE OPERATIONS
# =====================================================================

@app.get("/statistics")
async def get_global_statistics():
    return get_statistics()


@app.post("/configure-email")
async def configure_email(
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
    sender_email: str = "",
    sender_password: str = "",
    admin_emails: str = "",
):
    from alerts.email_alerts import configure_email as config_email

    admin_list = [e.strip() for e in admin_emails.split(",") if e.strip()]
    success = config_email(
        smtp_server, smtp_port, sender_email, sender_password, admin_list
    )

    return {"configured": success}


@app.get("/email-status")
async def email_status():
    from alerts.email_alerts import get_email_status
    return get_email_status()


@app.get("/live", response_class=HTMLResponse)
async def live_page():
    template_path = os.path.join(TEMPLATES_DIR, "live.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/live/start")
async def start_live_stream(data: dict):
    from detection.live_stream import create_stream

    if not _stream_semaphore.acquire(blocking=False):
        raise HTTPException(503, "Máximo de streams alcanzado, cierre uno primero")

    stream_id = data.get("stream_id", "main")
    source = data.get("source", 0)
    threshold = data.get("crowd_threshold", 3)
    confidence = data.get("confidence", 0.5)
    model_name = data.get("model_name")

    if model_name and model_name not in AVAILABLE_MODELS:
        raise HTTPException(400, f"El modelo '{model_name}' no está registrado en los modelos disponibles.")

    if isinstance(source, str) and source.isdigit():
        source = int(source)

    stream = create_stream(
        stream_id=stream_id, source=source, crowd_threshold=threshold,
        confidence=confidence, model_name=model_name,
    )

    success = stream.start()

    if not success:
        _stream_semaphore.release()

    return {"success": success, "stream_id": stream_id}


@app.post("/live/stop")
async def stop_live_stream(data: dict):
    from detection.live_stream import get_stream, stop_stream

    stream_id = data.get("stream_id", "main")
    stream = get_stream(stream_id)
    if stream and stream.is_running:
        summary = stream.get_summary()
        try:
            save_stream_analysis(summary)
        except Exception as e:
            logger.error(f"Failed to save stream summary: {e}")

    success = stop_stream(stream_id)
    if success:
        _stream_semaphore.release()

    return {"success": success}


@app.get("/live/feed/{stream_id}")
async def live_feed(stream_id: str):
    from detection.live_stream import get_stream

    stream = get_stream(stream_id)
    if not stream or not stream.is_running:
        raise HTTPException(404, "Stream no encontrado o no está activo")

    return StreamingResponse(
        stream.generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/live/status/{stream_id}")
async def live_status(stream_id: str):
    from detection.live_stream import get_stream

    stream = get_stream(stream_id)
    if not stream:
        return {"is_running": False}

    return stream.get_status()


@app.get("/live/cameras")
async def detect_cameras():
    from detection.live_stream import detect_cameras
    return detect_cameras()


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)