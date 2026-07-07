# RUNBOOK — Sistema de Detección de Anomalías CCTV

## Fase #1: Diagnóstico

Ante un incidente, verificar el estado del sistema con los siguientes comandos:

| Verificación | Comando / URL |
|---|---|
| Health Check | `GET /health` o `curl http://localhost:8000/health` |
| Logs del contenedor | `docker compose logs --tail=100` |
| Logs en tiempo real | `docker compose logs -f` |
| Estado del proceso | `docker ps \| grep cctv` |
| Espacio en disco | `df -h` |
| Base de datos | `sqlite3 src/storage/anomaly_history.db "SELECT count(*) FROM videos;"` |
| Modelos YOLO | `ls -la models/` |

## Fase #2: Protocolo ante Caídas

### Nivel L1 — Operador

1. Verificar `/health` endpoint (debe devolver `"status": "healthy"`)
2. Si el servicio no responde: `docker compose restart`
3. Revisar logs recientes: `docker compose logs --tail=50`
4. Si el problema persiste, escalar a **L2**.

### Nivel L2 — Administrador

1. Verificar espacio en disco: `df -h`
2. Verificar integridad de la base de datos (corrupción de SQLite)
3. Verificar que los modelos YOLO existen en `models/`
4. Verificar conectividad de red si usa streams RTSP
5. Si no se resuelve en 15 minutos, escalar a **L3**.

### Nivel L3 — Ingeniero DevOps

1. Reconstruir imagen desde cero: `docker compose build --no-cache`
2. Restaurar desde backup más reciente
3. Rollback a versión anterior del código: `git checkout <tag-anterior>`
4. Si el entorno está comprometido, proceder a **Recuperación ante Desastres**.

## Fase #3: Recuperación ante Desastres

### Estrategia de Respaldos (Regla 3-2-1)

- **3** copias de los datos: producción + backup local + backup externo
- **2** medios diferentes: disco local + almacenamiento externo (S3, SCP)
- **1** copia fuera del sitio

### Datos a respaldar

| Dato | Ruta |
|---|---|
| Base de datos SQLite | `src/storage/anomaly_history.db` |
| Imágenes analizadas | `static/images/` |
| Videos procesados | `static/videos/` |
| Configuración | `.env` |

### Procedimiento de restauración desde cero

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd <repo-directory>

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con los valores de producción

# 3. Iniciar el sistema
docker compose up -d

# 4. Verificar salud
curl http://localhost:8000/health

# 5. Restaurar base de datos
docker compose stop
docker cp backup.db $(docker compose ps -q app):/app/src/storage/anomaly_history.db

# 6. Restaurar archivos estáticos
docker cp backup_static/. $(docker compose ps -q app):/app/static/

# 7. Reiniciar
docker compose start

# 8. Verificar restauración
curl http://localhost:8000/health
curl http://localhost:8000/statistics
```
