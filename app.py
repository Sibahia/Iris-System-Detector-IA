import os
import sys
import tempfile
import time
import uuid
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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
    delete_image
)

logging.basicConfig(level=logging.INFO)
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
# LIFESPAN MANAGEMENT (MANEJADOR DE CONTEXTO)
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Evento de inicialización (Startup)
    init_database()
    logger.info("Application started successfully via lifespan context")
    yield
    # Aquí puedes agregar lógica de cierre (Shutdown) si es necesario en el futuro
    logger.info("Application shutting down")

app = FastAPI(
    title="CCTV Anomaly Detection",
    description="YOLOv8/YOLO11-based video and image anomaly detection",
    version="4.0.0",
    lifespan=lifespan
)

mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("video/x-msvideo", ".avi")
mimetypes.add_type("image/jpeg", ".jpg")
mimetypes.add_type("image/png", ".png")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

TASKS = {}

def run_analysis_task(
    task_id: str,
    file_path: str,
    output_path: str,
    crowd_threshold: int,
    confidence: float,
    original_filename: str,
    model_name: Optional[str] = None,
):
    try:
        from detection.yolo_detector import YOLOAnomalyDetector

        TASKS[task_id]["status"] = "processing"

        def update_progress(p):
            TASKS[task_id]["progress"] = p

        model_path = os.path.join("models", model_name) if model_name else None
        yolo = YOLOAnomalyDetector(
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
            "max_vehicles_detected": 0,  
            "anomaly_types": stats["anomaly_types_count"],
            "processing_time": stats["processing_time"],
            "annotated_video_url": f"/static/videos/{os.path.basename(output_path)}",
            "risk_level": final_risk,
            "risk_percentage": risk_percentage
        }

    except Exception as e:
        logger.error(f"Task failed: {e}")
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["error"] = str(e)
    finally:
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
    
@app.get("/video-base", response_class=HTMLResponse)
async def view_video_base():
    template_path = os.path.join(TEMPLATES_DIR, "video-base.html")
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
    return {"status": "healthy", "version": "4.0.0"}


# =====================================================================
# MODEL MANIFEST UTILITIES
# =====================================================================

@app.get("/models")
async def get_available_models():
    """Retorna los modelos cargables configurados para el entorno de ejecucion"""
    return {"models": AVAILABLE_MODELS, "default": DEFAULT_MODEL}


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
):
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "File must be a video")

    if model_name and model_name not in AVAILABLE_MODELS:
        raise HTTPException(400, f"Model '{model_name}' is not registered in AVAILABLE_MODELS.")

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    try:
        content = await file.read()
        temp.write(content)
        temp.close()
        temp_path = temp.name
    except:
        temp.close()
        raise HTTPException(500, "Failed to save file")

    task_id = str(uuid.uuid4())
    output_filename = f"yolo_{task_id}.mp4"
    output_path = os.path.join(VIDEOS_DIR, output_filename)

    TASKS[task_id] = {"status": "queued", "progress": 0, "result": None}

    background_tasks.add_task(
        run_analysis_task,
        task_id,
        temp_path,
        output_path,
        crowd_threshold,
        confidence,
        file.filename,
        model_name,
    )

    return {"task_id": task_id}


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
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
        raise HTTPException(404, "Video not found")
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
        raise HTTPException(404, "Video not found")
    return {"deleted": True}


# =====================================================================
# STATIC IMAGE INFERENCE ENDPOINTS (CON SOPORTE PARA CARPETA MODELS/)
# =====================================================================

@app.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    crowd_threshold: int = Query(5),
    confidence: float = Query(CONFIDENCE_THRESHOLD),
    model_name: Optional[str] = Query(None)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image")

    # Validar y resolver que modelo usar
    selected_model = model_name if model_name else DEFAULT_MODEL
    if selected_model not in AVAILABLE_MODELS:
        raise HTTPException(400, f"Model '{selected_model}' is not registered in AVAILABLE_MODELS.")

    # Construir la ruta correcta apuntando al subdirectorio models/
    model_path = os.path.join("models", selected_model)

    # Guardar archivo de entrada temporalmente
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        content = await file.read()
        temp_input.write(content)
        temp_input.close()
    except:
        temp_input.close()
        raise HTTPException(500, "Failed to save uploaded image")

    # Configurar rutas de salida fijas
    unique_id = str(uuid.uuid4())
    output_filename = f"out_{unique_id}{ext}"
    output_path = os.path.join(IMAGES_DIR, output_filename)

    try:
        from detection.image_detector import YOLOImageDetector
        
        # Instanciar el detector estatico modular apuntando a models/
        detector = YOLOImageDetector(
            model_path=model_path,
            default_confidence=confidence,
            crowd_threshold=crowd_threshold,
            device=DEVICE
        )

        # Procesar y renderizar la imagen
        raw_results = detector.process_image(temp_input.name, output_path, conf_override=confidence)
        
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

        return raw_results

    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        raise HTTPException(500, f"Analysis execution error: {str(e)}")
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
        raise HTTPException(404, "Image audit log not found")
    return result


@app.delete("/image-history/{image_id}")
async def delete_image_history_item(image_id: int):
    """Elimina la imagen de la BD y purga su archivo de disco"""
    success = delete_image(image_id)
    if not success:
        raise HTTPException(404, "Image not found")
    return {"deleted": True}


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
    with open(template_path, "r") as f:
        return HTMLResponse(content=f.read())


@app.post("/live/start")
async def start_live_stream(data: dict):
    from detection.live_stream import create_stream

    stream_id = data.get("stream_id", "main")
    source = data.get("source", 0)
    threshold = data.get("crowd_threshold", 3)
    confidence = data.get("confidence", 0.5)
    model_name = data.get("model_name")

    if model_name and model_name not in AVAILABLE_MODELS:
        raise HTTPException(400, f"Model '{model_name}' is not registered in AVAILABLE_MODELS.")

    if isinstance(source, str) and source.isdigit():
        source = int(source)

    stream = create_stream(
        stream_id=stream_id, source=source, crowd_threshold=threshold,
        confidence=confidence, model_name=model_name,
    )

    success = stream.start()

    return {"success": success, "stream_id": stream_id}


@app.post("/live/stop")
async def stop_live_stream(data: dict):
    from detection.live_stream import stop_stream

    stream_id = data.get("stream_id", "main")
    success = stop_stream(stream_id)

    return {"success": success}


@app.get("/live/feed/{stream_id}")
async def live_feed(stream_id: str):
    from detection.live_stream import get_stream

    stream = get_stream(stream_id)
    if not stream or not stream.is_running:
        raise HTTPException(404, "Stream not found or not running")

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