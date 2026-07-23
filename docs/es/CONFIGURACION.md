# Configuracion - Iris System Detector

## Variables de Entorno

Copiar `.env.example` a `.env` y ajustar valores.

### Modelo

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `MODEL_SIZE` | `s` | Tamano del modelo: `n`, `s`, `m`, `l`, `x` |
| `MODEL_NAME` | `best.pt` | Modelo por defecto |
| `AVAILABLE_MODELS` | `best.pt,gun_detector.pt,gun.pt,suspicious.pt` | Modelos disponibles (comma-separated) |
| `DEVICE` | `cpu` | Dispositivo: `cpu`, `cuda`, `mps` |
| `CONFIDENCE_THRESHOLD` | `0.5` | Umbral de confianza |
| `CROWD_THRESHOLD` | `5` | Personas para alerta de aglomeracion |
| `LOITER_THRESHOLD` | `10.0` | Segundos antes de alerta de loitering |

### Servidor

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Host de binding |
| `PORT` | `8000` | Puerto |
| `DEBUG` | `false` | Modo debug |
| `RELOAD` | `false` | Auto-reload en cambios |
| `LOG_LEVEL` | `INFO` | Nivel de logging |

### Aplicacion

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `SITE_TITLE` | `Iris` | Titulo del sitio (en templates) |
| `MAX_FILE_SIZE_MB` | `300` | Tamano maximo de upload en MB |
| `EMAIL_CONFIG` | `false` | Habilitar alertas por email |
| `ENABLE_EMAIL_ALERTS` | `false` | Habilitar alertas por email |

---

## Modelos Disponibles

### best.pt
Modelo general para deteccion de amenazas. Clases: `weapon`, `person`.

### gun_detector.pt
Detector especifico de armas de fuego. Clases: `weapon`.

### gun.pt
Detector de armas con contexto de persona. Clases: `weapon`, `person`.

### suspicious.pt
Modelo mas detallado. Clases: `person`, `police`, `prisoner`, `armed_person`, `behavior_assault`, `behavior_fight`, `behavior_kidnap`, `behavior_terror`, `behavior_robbery`.

---

## Configuracion de Modelos

`models/model_config.json` define los `class_groups` y `anomaly_map` para cada modelo.

### Estructura

```json
{
  "nombre_modelo.pt": {
    "class_groups": {
      "grupo": [ids_de_clases]
    },
    "armed_person_ids": [ids],
    "anomaly_map": {
      "grupo": {
        "type": "TIPO_DE_ANOMALIA",
        "risk": "nivel_riesgo"
      }
    }
  }
}
```

### Niveles de Riesgo

| Nivel | Descripcion |
|-------|-------------|
| `normal` | Sin anomalias detectadas |
| `bajo` | Actividad menor, sin amenaza |
| `medio` | Actividad sospechosa, requiere atencion |
| `alto` | Amenaza confirmada, accion requerida |

### Tipos de Anomalia

| Tipo | Riesgo |
|------|--------|
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

## Base de Datos

- **Archivo:** `src/storage/anomaly_history.db`
- **Modo:** SQLite con WAL (`PRAGMA journal_mode=WAL`)
- **Tablas:** `videos`, `anomaly_events`, `images`, `streams`
- **En Docker:** Montado como volumen para persistencia

---

## Docker

### docker-compose.yml (desarrollo)

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

### Produccion (GHCR)

Usar imagen pre-compilada:

```yaml
services:
  app:
    image: ghcr.io/sibahia/iris-system-detector-ia:latest
    # mismos volumes y limits
```

Pull: `docker compose pull && docker compose up -d`

---

## Seguridad

### Headers HTTP

Se agregan automaticamente a todas las responses:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy` (default-src self, script-src self unsafe-inline, etc.)

### Correlation ID

Cada request recibe un `X-Correlation-ID` (UUID). Se propagan los headers `X-Real-IP` y `X-Forwarded-For` via Nginx.
