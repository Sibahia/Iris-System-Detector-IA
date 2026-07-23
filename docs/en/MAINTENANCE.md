# Maintenance - Iris System Detector

## Docker Commands

| Action | Command |
|--------|---------|
| Check status | `docker compose ps` |
| View live logs | `docker compose logs -f` |
| View last 100 logs | `docker compose logs --tail=100` |
| Restart | `docker compose restart` |
| Stop | `docker compose stop` |
| Start | `docker compose start` |
| Pull new image | `docker compose pull` |
| Rebuild (dev) | `docker compose build && docker compose up -d` |

---

## Health Check

### Manual verification

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy", "version": "4.0.0", "checks": {"database": "ok", "disk_free_gb": 78.1, "models": "ok"}}
```

### Automatic health check (Docker)

Docker runs a health check every 30s via `HEALTHCHECK` in the Dockerfile. If it fails 3 times, the container is restarted.

### External health check (cron)

```bash
*/5 * * * * /opt/iris_healthcheck.sh
```

Script that verifies `/health` and restarts the container if unhealthy.

---

## Backups

### Location

```
/opt/backups/iris/
├── db_YYYYMMDD_HHMMSS.db
├── static_YYYYMMDD_HHMMSS.tar.gz
└── env_YYYYMMDD_HHMMSS.env
```

### Automatic backup

```bash
0 3 * * * /opt/backups/backup_iris.sh
```

Runs daily at 3 AM. Retains 7 days.

### Manual backup

```bash
/opt/backups/backup_iris.sh
```

### Restore backup

```bash
# Stop container
docker compose stop

# Restore DB
cp /opt/backups/iris/db_YYYYMMDD_HHMMSS.db /opt/Iris-System-Detector-IA/src/storage/anomaly_history.db

# Restore static
tar xzf /opt/backups/iris/static_YYYYMMDD_HHMMSS.tar.gz -C /opt/Iris-System-Detector-IA/

# Start container
docker compose start
```

---

## Database

### Verify integrity

```bash
sqlite3 /opt/Iris-System-Detector-IA/src/storage/anomaly_history.db "PRAGMA integrity_check;"
```

### Optimize

```bash
sqlite3 /opt/Iris-System-Detector-IA/src/storage/anomaly_history.db "ANALYZE; VACUUM;"
```

### Check size

```bash
ls -lh /opt/Iris-System-Detector-IA/src/storage/anomaly_history.db
```

### Export

```bash
sqlite3 /opt/Iris-System-Detector-IA/src/storage/anomaly_history.db .dump > backup.sql
```

---

## Resource Monitoring

```bash
# RAM and swap
free -h

# Disk
df -h

# Container stats
docker stats --no-stream

# Processes
docker compose top
```

### Configured Limits

| Resource | Limit | Reservation |
|----------|-------|-------------|
| RAM | 6 GB (production) / 3 GB (dev) | 512 MB - 1 GB |
| CPU | 3.5 cores (production) / 3.0 (dev) | 0.5 - 1.0 core |
| Swap | 4 GB | permanent |

---

## Updates

### Production (GHCR)

```bash
# 1. Backup
/opt/backups/backup_iris.sh

# 2. Pull new image
docker compose pull

# 3. Restart
docker compose up -d

# 4. Verify
curl http://localhost:8000/health
```

### Development (local build)

```bash
# 1. Pull code
git pull origin feature/alejandro

# 2. Rebuild
docker compose build --no-cache

# 3. Up
docker compose up -d
```

---

## Server Security

### Firewall (UFW)

Open ports: 22 (SSH), 80 (HTTP), 443 (HTTPS)

```bash
ufw status
```

### SSL (Let's Encrypt)

```bash
# Check certificate
certbot certificates

# Manual renewal
certbot renew

# Verify auto-renewal
systemctl status certbot.timer
```

---

## Troubleshooting

| Problem | Diagnosis | Solution |
|---------|-----------|----------|
| Container won't start | `docker compose logs` | Check .env, ports, permissions |
| 502 Bad Gateway | Nginx can't connect to :8000 | `systemctl restart nginx`, check container |
| Low disk space | `df -h` | Clean `/static/`, old backups |
| DB locked | `PRAGMA journal_mode=WAL` | Check for zombie processes |
| Model won't load | Verify `models/` in container | `docker compose down && docker compose up -d` |
| Health check fails | `curl localhost:8000/health` | Check DB and disk space |
| Logs flooded | Too many `/health` requests | Throttling configured (15 min) |
| OOM Kill | `docker stats` | Increase RAM limit or use smaller model |
