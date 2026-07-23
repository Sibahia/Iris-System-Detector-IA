# REST API - Iris System Detector

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

**Response 503:** Service unavailable.

---

## Video Analysis

### Upload video for analysis

```
POST /analyze-yolo
Content-Type: multipart/form-data
X-Idempotency-Key: <uuid> (optional)
```

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | file | Yes | - | Video (.mp4, .avi, .mov, .mkv) |
| `crowd_threshold` | int | No | 5 | Person count for crowd alert |
| `confidence` | float | No | 0.5 | Confidence threshold |
| `model_name` | string | No | best.pt | Model to use |

**Response 200:** `{"task_id": "abc123"}`

**Concurrency limit:** 2 simultaneous video analyses.

### Check analysis status

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

States: `queued`, `processing`, `completed`, `failed`. Tasks expire after 3600s.

---

## Video History

```
GET /history?filename=&min_anomaly_rate=
GET /history/{video_id}
DELETE /history/{video_id}
```

---

## Image Analysis

### Upload image

```
POST /analyze-image
Content-Type: multipart/form-data
X-Idempotency-Key: <uuid> (optional)
```

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | file | Yes | - | Image (.jpg, .png, .gif, .bmp, .webp) |
| `crowd_threshold` | int | No | 5 | Person count for crowd alert |
| `confidence` | float | No | 0.5 | Confidence threshold |
| `model_name` | string | No | best.pt | Model to use |

**Response 200:** Full analysis result (synchronous).

**Concurrency limit:** 1 simultaneous image analysis.

### Image history

```
GET /image-history?limit=50&offset=0
GET /image-history/{image_id}
DELETE /image-history/{image_id}
```

---

## Stream History

```
GET /stream-history?limit=50&offset=0
GET /stream-history/{stream_id}
DELETE /stream-history/{stream_id}
```

---

## Combined History

```
GET /combined-history?filename=&record_type=video|image|stream
```

### Record detail

```
GET /record-detail/{record_type}/{record_id}
```

Includes `anomaly_events`, `class_groups`, `model_classes`.

---

## Statistics

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

## Models

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

## Configuration

```
GET /config
```

**Response 200:** `{"max_file_size_mb": 300}`

---

## Email

### Configure

```
POST /configure-email
Content-Type: application/x-www-form-urlencoded
```

| Param | Type | Default |
|-------|------|---------|
| `smtp_server` | string | smtp.gmail.com |
| `smtp_port` | int | 587 |
| `sender_email` | string | - |
| `sender_password` | string | - |
| `admin_emails` | string | - (comma-separated) |

### Status

```
GET /email-status
```

---

## Live Streams

### Start

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

### Stop

```
POST /live/stop
Content-Type: application/json
```

```json
{"stream_id": "cam1"}
```

### MJPEG Feed

```
GET /live/feed/{stream_id}
```

Returns `multipart/x-mixed-replace` (MJPEG stream).

### Status

```
GET /live/status/{stream_id}
```

### Detect cameras

```
GET /live/cameras
```

---

## Logs

### In-memory logs (circular buffer, 500 entries)

```
GET /api/logs?level=ERROR&limit=50&offset=0
```

---

## Security Headers

All responses include:

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'unsafe-inline'; ...` |

All responses include `X-Correlation-ID` (auto-generated UUID or from request).

---

## Errors

| Status | Description |
|--------|-------------|
| 400 | Invalid parameters or file type not allowed |
| 404 | Resource not found |
| 413 | File exceeds `MAX_FILE_SIZE_MB` |
| 429 | Concurrency limit reached |
| 500 | Internal error (returns error UUID for reference) |
| 503 | Service unavailable |

---

## Concurrency

| Resource | Limit |
|----------|-------|
| Video analysis | 2 simultaneous |
| Image analysis | 1 simultaneous |
| Live streams | 2 simultaneous |
| Active tasks | 100 max |
| Idempotency cache | 3600s TTL |
