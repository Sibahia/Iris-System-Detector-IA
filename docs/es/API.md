# API REST - Iris System Detector

Version 4.0.0. Base URL: `http://HOST:8000`

---

## Health Check

```
GET /health
```

**Response 200:**
```json
{
  "status": "healthy",
  "version": "4.0.0",
  "checks": {
    "database": "ok",
    "disk_free_gb": 78.1,
    "models": "ok"
  }
}
```

**Response 503:** Servicio no disponible.

---

## Analisis de Video

### Subir video para analisis

```
POST /analyze-yolo
Content-Type: multipart/form-data
X-Idempotency-Key: <uuid> (opcional)
```

| Param | Tipo | Requerido | Default | Descripcion |
|-------|------|-----------|---------|-------------|
| `file` | file | Si | - | Video (.mp4, .avi, .mov, .mkv) |
| `crowd_threshold` | int | No | 5 | Personas para alerta de aglomeracion |
| `confidence` | float | No | 0.5 | Umbral de confianza |
| `model_name` | string | No | best.pt | Modelo a utilizar |

**Response 200:**
```json
{"task_id": "abc123"}
```

**Límites de concurrencia:** 2 analisis de video simultaneos.

### Consultar estado del analisis

```
GET /tasks/{task_id}
```

**Response 200:**
```json
{
  "task_id": "abc123",
  "status": "processing",
  "progress": 45,
  "result": null
}
```

Estados: `queued`, `processing`, `completed`, `failed`. Los tasks expiran en 3600s.

---

## Historial de Video

### Listar todos

```
GET /history?filename=&min_anomaly_rate=
```

### Obtener uno

```
GET /history/{video_id}
```

### Eliminar

```
DELETE /history/{video_id}
```

---

## Analisis de Imagen

### Subir imagen

```
POST /analyze-image
Content-Type: multipart/form-data
X-Idempotency-Key: <uuid> (opcional)
```

| Param | Tipo | Requerido | Default | Descripcion |
|-------|------|-----------|---------|-------------|
| `file` | file | Si | - | Imagen (.jpg, .png, .gif, .bmp, .webp) |
| `crowd_threshold` | int | No | 5 | Personas para alerta de aglomeracion |
| `confidence` | float | No | 0.5 | Umbral de confianza |
| `model_name` | string | No | best.pt | Modelo a utilizar |

**Response 200:** Resultado completo del analisis (sincrono).

**Limite de concurrencia:** 1 analisis de imagen simultaneo.

### Historial de imagenes

```
GET /image-history?limit=50&offset=0
GET /image-history/{image_id}
DELETE /image-history/{image_id}
```

---

## Historial de Streams

```
GET /stream-history?limit=50&offset=0
GET /stream-history/{stream_id}
DELETE /stream-history/{stream_id}
```

---

## Historial Unificado

```
GET /combined-history?filename=&record_type=video|image|stream
```

### Detalle de registro

```
GET /record-detail/{record_type}/{record_id}
```

Incluye `anomaly_events`, `class_groups`, `model_classes`.

---

## Estadisticas

```
GET /statistics
```

**Response 200:**
```json
{
  "total_videos": 12,
  "total_frames": 3600,
  "avg_anomaly_rate": 0.08,
  "total_anomalies": 288,
  "avg_processing_time": 45.2,
  "total_images": 50,
  "total_anomalous_images": 3,
  "total_weapons_detected_imgs": 1
}
```

---

## Modelos

```
GET /models
```

**Response 200:**
```json
{
  "models": ["best.pt", "gun_detector.pt", "gun.pt", "suspicious.pt"],
  "default": "best.pt"
}
```

---

## Configuracion

```
GET /config
```

**Response 200:** `{"max_file_size_mb": 300}`

---

## Email

### Configurar

```
POST /configure-email
Content-Type: application/x-www-form-urlencoded
```

| Param | Tipo | Default |
|-------|------|---------|
| `smtp_server` | string | smtp.gmail.com |
| `smtp_port` | int | 587 |
| `sender_email` | string | - |
| `sender_password` | string | - |
| `admin_emails` | string | - (comma-separated) |

### Estado

```
GET /email-status
```

---

## Streams en Vivo

### Iniciar

```
POST /live/start
Content-Type: application/json
```

```json
{
  "stream_id": "cam1",
  "source": "0",
  "crowd_threshold": 5,
  "confidence": 0.5,
  "model_name": "best.pt"
}
```

### Detener

```
POST /live/stop
Content-Type: application/json
```

```json
{"stream_id": "cam1"}
```

### Feed MJPEG

```
GET /live/feed/{stream_id}
```

Retorna `multipart/x-mixed-replace` (MJPEG stream).

### Estado

```
GET /live/status/{stream_id}
```

### Detectar camaras

```
GET /live/cameras
```

---

## Logs

### Logs en memoria (buffer circular, 500 entradas)

```
GET /api/logs?level=ERROR&limit=50&offset=0
```

---

## Headers de Seguridad

Todos los responses incluyen:

| Header | Valor |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'unsafe-inline'; ...` |

Todos los responses incluyen `X-Correlation-ID` (UUID auto-generado o del request).

---

## Errores

| Status | Descripcion |
|--------|-------------|
| 400 | Parametros invalidos o archivo no permitido |
| 404 | Recurso no encontrado |
| 413 | Archivo excede `MAX_FILE_SIZE_MB` |
| 429 | Limite de concurrencia alcanzado |
| 500 | Error interno (retorna UUID de error para referencia) |
| 503 | Servicio no disponible |

---

## Concurrencia

| Recurso | Limite |
|---------|--------|
| Analisis de video | 2 simultaneos |
| Analisis de imagen | 1 simultaneo |
| Streams en vivo | 2 simultaneos |
| Tasks activos | 100 max |
| Cache de idempotencia | 3600s TTL |
