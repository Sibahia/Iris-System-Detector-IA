# Configuration - Iris System Detector

## Environment Variables

Copy `.env.example` to `.env` and adjust values.

### Model

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_SIZE` | `s` | Model size: `n`, `s`, `m`, `l`, `x` |
| `MODEL_NAME` | `best.pt` | Default model |
| `AVAILABLE_MODELS` | `best.pt,gun_detector.pt,gun.pt,suspicious.pt` | Available models (comma-separated) |
| `DEVICE` | `cpu` | Inference device: `cpu`, `cuda`, `mps` |
| `CONFIDENCE_THRESHOLD` | `0.5` | Confidence threshold |
| `CROWD_THRESHOLD` | `5` | Person count for crowd alert |
| `LOITER_THRESHOLD` | `10.0` | Seconds before loitering alert |

### Server

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Bind host |
| `PORT` | `8000` | Port |
| `DEBUG` | `false` | Debug mode |
| `RELOAD` | `false` | Auto-reload on changes |
| `LOG_LEVEL` | `INFO` | Logging level |

### Application

| Variable | Default | Description |
|----------|---------|-------------|
| `SITE_TITLE` | `Iris` | Site title (in templates) |
| `MAX_FILE_SIZE_MB` | `300` | Max upload size in MB |
| `EMAIL_CONFIG` | `false` | Enable email alerting |
| `ENABLE_EMAIL_ALERTS` | `false` | Enable email alerting |

---

## Available Models

### best.pt
General threat detection model. Classes: `weapon`, `person`.

### gun_detector.pt
Firearm-specific detector. Classes: `weapon`.

### gun.pt
Weapon detection with person context. Classes: `weapon`, `person`.

### suspicious.pt
Most detailed model. Classes: `person`, `police`, `prisoner`, `armed_person`, `behavior_assault`, `behavior_fight`, `behavior_kidnap`, `behavior_terror`, `behavior_robbery`.

---

## Model Configuration

`models/model_config.json` defines `class_groups` and `anomaly_map` for each model.

### Structure

```json
{
  "model_name.pt": {
    "class_groups": {
      "group": [class_ids]
    },
    "armed_person_ids": [ids],
    "anomaly_map": {
      "group": {
        "type": "ANOMALY_TYPE",
        "risk": "risk_level"
      }
    }
  }
}
```

### Risk Levels

| Level | Description |
|-------|-------------|
| `normal` | No anomalies detected |
| `bajo` | Minor activity, no threat |
| `medio` | Suspicious activity, requires attention |
| `alto` | Confirmed threat, action required |

### Anomaly Types

| Type | Risk |
|------|------|
| `ARMA_DETECTADA` | alto |
| `PERSONA_ARMADA` | alto |
| `AGLOMERACION_DE_PERSONAS` | medio |
| `ALTERCADO_POTENCIAL` | alto |
| `AUTORIDAD_DETECTADA` | bajo |
| `PRESO_DETECTADO` | medio |
| `ASALTO` | alto |
| `PELEA` | alto |
| `SECUESTRO` | alto |
| `TERRORISMO` | alto |
| `ROBO` | alto |

---

## Database

- **File:** `src/storage/anomaly_history.db`
- **Mode:** SQLite with WAL (`PRAGMA journal_mode=WAL`)
- **Tables:** `videos`, `anomaly_events`, `images`, `streams`
- **In Docker:** Mounted as volume for persistence

---

## Docker

### docker-compose.yml (development)

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    volumes:
      - ./src/storage:/app/src/storage
      - ./static:/app/static
      - ./templates:/app/templates
    deploy:
      resources:
        limits:
          memory: 3G
          cpus: "3.0"
```

### Production (GHCR)

Use pre-built image:

```yaml
services:
  app:
    image: ghcr.io/sibahia/iris-system-detector-ia:latest
    # same volumes and limits
```

Pull: `docker compose pull && docker compose up -d`

---

## Security

### HTTP Headers

Automatically added to all responses:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy` (default-src self, script-src self unsafe-inline, etc.)

### Correlation ID

Every request receives an `X-Correlation-ID` (UUID). `X-Real-IP` and `X-Forwarded-For` headers are propagated via Nginx.
