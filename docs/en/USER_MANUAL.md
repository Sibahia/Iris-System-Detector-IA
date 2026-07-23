# User Manual - Iris System Detector

## Access

- **Local:** `http://localhost:8000`
- **Production:** `https://iris-detector.duckdns.org`

---

## Interfaces

### Landing Page (`/`)

Main page with quick access to all features.

### Video Analysis (`/video-analysis`)

1. Drag and drop or select a video (.mp4, .avi, .mov, .mkv)
2. Select model (optional)
3. Adjust confidence threshold (optional)
4. Click **Analyze**
5. Wait for progress (progress bar)
6. View results: risk level, detected classes, anomalies

### Image Analysis (`/image-analysis`)

1. Drag and drop or select an image (.jpg, .png, .gif, .bmp, .webp)
2. Select model (optional)
3. Adjust confidence threshold (optional)
4. Click **Analyze**
5. View immediate results: persons, weapons, objects, risk level

### Live Monitoring (`/stream-analysis`)

1. Select source (webcam or RTSP URL)
2. Select model
3. Adjust confidence
4. Click **Start**
5. View live feed with detection overlays
6. Click **Stop** to save summary

### History (`/logs`)

- View all records (video, image, stream)
- Filter by name, record type, or risk level
- Search by text
- View detail of each record (modal)
- Delete records

### System Logs (`/terminal-logs`)

- Terminal-style viewer with auto-refresh
- Filter by level (DEBUG, INFO, WARNING, ERROR)
- Pagination (50 per page)

### Contributors (`/contributors`)

- Project contributors list

---

## Risk Levels

| Level | Meaning | Color |
|-------|---------|-------|
| `normal` | No anomalies | Green |
| `bajo` | Minor activity | Blue |
| `medio` | Suspicious activity | Yellow |
| `alto` | Confirmed threat | Red |

---

## Available Models

| Model | Ideal Use |
|-------|-----------|
| `best.pt` | General (weapons + persons) |
| `gun_detector.pt` | Firearms only |
| `gun.pt` | Weapons with person context |
| `suspicious.pt` | Suspicious behaviors (assault, fight, kidnapping, terrorism, robbery) |

---

## Anomaly Types

| Type | Description | Risk |
|------|-------------|------|
| ARMA_DETECTADA | Weapon detected | alto |
| PERSONA_ARMADA | Armed person | alto |
| AGLOMERACION_DE_PERSONAS | Crowd gathering | medio |
| ALTERCADO_POTENCIAL | Potential altercation | alto |
| AUTORIDAD_DETECTADA | Police presence | bajo |
| PRESO_DETECTADO | Prisoner identified | medio |
| ASALTO | Assault | alto |
| PELEA | Fight in progress | alto |
| SECUESTRO | Kidnapping situation | alto |
| TERRORISMO | Terrorism activity | alto |
| ROBO | Robbery | alto |

---

## Supported Formats

| Type | Formats |
|------|---------|
| Video | .mp4, .avi, .mov, .mkv |
| Image | .jpg, .jpeg, .png, .gif, .bmp, .webp |
| Stream | Webcam (index 0, 1, ...) or RTSP URL |

---

## Limits

- Max upload size: 300 MB (configurable via `MAX_FILE_SIZE_MB`)
- Video analysis: max 2 simultaneous
- Image analysis: max 1 simultaneous
- Live streams: max 2 simultaneous

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Page won't load | Verify service is running (`docker compose ps`) |
| Upload fails | Check file size (< 300 MB) |
| Video won't analyze | Check format (.mp4, .avi, .mov, .mkv) |
| Model doesn't appear | Check `AVAILABLE_MODELS` in `.env` |
| Slow on CPU | Use model `n` (nano) instead of `s` or `m` |
