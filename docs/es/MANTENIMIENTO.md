# Mantenimiento - Iris System Detector

## Comandos Docker

| Accion | Comando |
|--------|---------|
| Ver estado | `docker compose ps` |
| Ver logs en tiempo real | `docker compose logs -f` |
| Ver ultimos 100 logs | `docker compose logs --tail=100` |
| Reiniciar | `docker compose restart` |
| Detener | `docker compose stop` |
| Iniciar | `docker compose start` |
| Pull nueva imagen | `docker compose pull` |
| Reconstruir (dev) | `docker compose build && docker compose up -d` |

---

## Health Check

### Verificacion manual

```bash
curl http://localhost:8000/health
```

Response esperado:
```json
{"status": "healthy", "version": "4.0.0", "checks": {"database": "ok", "disk_free_gb": 78.1, "models": "ok"}}
```

### Health check automatico (Docker)

Docker ejecuta un health check cada 30s via `HEALTHCHECK` en el Dockerfile. Si falla 3 veces, el container se reinicia.

### Health check externo (cron)

```bash
*/5 * * * * /opt/iris_healthcheck.sh
```

Script que verifica `/health` y reinicia el container si esta unhealthy.

---

## Backups

### Ubicacion

```
/opt/backups/iris/
├── db_YYYYMMDD_HHMMSS.db
├── static_YYYYMMDD_HHMMSS.tar.gz
└── env_YYYYMMDD_HHMMSS.env
```

### Backup automatico

```bash
0 3 * * * /opt/backups/backup_iris.sh
```

Ejecuta diariamente a las 3 AM. Retiene 7 dias.

### Backup manual

```bash
/opt/backups/backup_iris.sh
```

### Restaurar backup

```bash
# Detener container
docker compose stop

# Restaurar DB
cp /opt/backups/iris/db_YYYYMMDD_HHMMSS.db /opt/Iris-System-Detector-IA/src/storage/anomaly_history.db

# Restaurar static
tar xzf /opt/backups/iris/static_YYYYMMDD_HHMMSS.tar.gz -C /opt/Iris-System-Detector-IA/

# Iniciar container
docker compose start
```

---

## Base de Datos

### Verificar integridad

```bash
sqlite3 /opt/Iris-System-Detector-IA/src/storage/anomaly_history.db "PRAGMA integrity_check;"
```

### Optimizar

```bash
sqlite3 /opt/Iris-System-Detector-IA/src/storage/anomaly_history.db "ANALYZE; VACUUM;"
```

### Ver tamano

```bash
ls -lh /opt/Iris-System-Detector-IA/src/storage/anomaly_history.db
```

### Exportar

```bash
sqlite3 /opt/Iris-System-Detector-IA/src/storage/anomaly_history.db .dump > backup.sql
```

---

## Monitoreo de Recursos

```bash
# RAM y swap
free -h

# Disco
df -h

# Container stats
docker stats --no-stream

# Procesos
docker compose top
```

### Limites configurados

| Recurso | Limite | Reserva |
|---------|--------|---------|
| RAM | 6 GB (produccion) / 3 GB (dev) | 512 MB - 1 GB |
| CPU | 3.5 cores (produccion) / 3.0 (dev) | 0.5 - 1.0 core |
| Swap | 4 GB | permanente |

---

## Actualizaciones

### Produccion (GHCR)

```bash
# 1. Backup
/opt/backups/backup_iris.sh

# 2. Pull nueva imagen
docker compose pull

# 3. Reiniciar
docker compose up -d

# 4. Verificar
curl http://localhost:8000/health
```

### Desarrollo (build local)

```bash
# 1. Pull codigo
git pull origin feature/alejandro

# 2. Rebuild
docker compose build --no-cache

# 3. Up
docker compose up -d
```

---

## Seguridad del Servidor

### Firewall (UFW)

Puertos abiertos: 22 (SSH), 80 (HTTP), 443 (HTTPS)

```bash
ufw status
```

### SSL (Let's Encrypt)

```bash
# Verificar certificado
certbot certificates

# Renovar manualmente
certbot renew

# Verificar auto-renovacion
systemctl status certbot.timer
```

---

## Troubleshooting

| Problema | Diagnostico | Solucion |
|----------|-------------|----------|
| Container no inicia | `docker compose logs` | Verificar .env, puertos, permisos |
| 502 Bad Gateway | Nginx no puede conectar a :8000 | `systemctl restart nginx`, verificar container |
| Sin espacio en disco | `df -h` | Limpiar `/static/`, backups viejos |
| DB bloqueada | `PRAGMA journal_mode=WAL` | Verificar que no hay procesos zombies |
| Modelo no carga | Verificar `models/` en container | `docker compose down && docker compose up -d` |
| Health check falla | `curl localhost:8000/health` | Verificar DB y espacio en disco |
| Logs flooded | Muchos requests `/health` | Throttling configurado (15 min) |
| OOM Kill | `docker stats` | Aumentar limite de RAM o usar modelo mas pequeno |
