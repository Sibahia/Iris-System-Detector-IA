# DEPLOYMENT.md — Iris System Detector IA en VPS

Guía paso a paso para desplegar el sistema en una VPS de Contabo.

---

## Specs de la VPS

| Recurso | Valor |
|---------|-------|
| Proveedor | Contabo |
| OS | Ubuntu 24.04.4 LTS |
| CPU | 4 vCPU |
| RAM | 8 GB |
| Almacenamiento | 100 GB SSD |
| Puerto | 200 Mbit/s |
| Dominio | iFreeDomains (.xyz) |

---

## Fase 1: Preparar la VPS

### 1.1 Conectar por SSH

```bash
ssh root@TU_IP_VPS
```

### 1.2 Actualizar sistema

```bash
apt update && apt upgrade -y
```

### 1.3 Instalar Docker y Docker Compose

```bash
# Instalar Docker
curl -fsSL https://get.docker.com | sh

# Habilitar y arrancar
systemctl enable docker && systemctl start docker

# Verificar
docker --version
docker compose version
```

### 1.4 Crear swap (4 GB)

Para evitar OOM con modelos YOLO cargados:

```bash
# Crear swap de 4 GB
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Hacer permanente
echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab

# Reducir swappiness (usar RAM primero)
echo 'vm.swappiness=10' | tee -a /etc/sysctl.conf
sysctl -p
```

### 1.5 Instalar Nginx

```bash
apt install nginx -y
systemctl enable nginx && systemctl start nginx
```

### 1.6 Configurar firewall

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
```

### 1.7 Instalar Certbot (para HTTPS)

```bash
apt install certbot python3-certbot-nginx -y
```

---

## Fase 2: Clonar el repositorio

```bash
cd /opt
git clone https://github.com/Sibahia/Iris-System-Detector-IA.git
cd Iris-System-Detector-IA
git checkout feature/alejandro
```

---

## Fase 3: Configurar variables de entorno

```bash
cp .env.example .env
nano .env
```

Configurar con estos valores:

```env
# Modelo
MODEL_SIZE=s
MODEL_NAME=best.pt
AVAILABLE_MODELS=best.pt,gun_detector.pt,gun.pt,suspicious.pt
DEVICE=cpu

# Deteccion
CONFIDENCE_THRESHOLD=0.5
CROWD_THRESHOLD=5
LOITER_THRESHOLD=10.0

# Servidor
HOST=0.0.0.0
PORT=8000
DEBUG=false
RELOAD=false
LOG_LEVEL=INFO
ENABLE_EMAIL_ALERTS=false
MAX_FILE_SIZE_MB=300
SITE_TITLE=Iris
```

---

## Fase 4: Crear docker-compose.yml en la VPS

> **IMPORTANTE**: El `docker-compose.yml` del repo es para desarrollo local (build desde source). En la VPS usamos la imagen pre-armada de GHCR.

```bash
cat > /opt/Iris-System-Detector-IA/docker-compose.yml << 'EOF'
services:
  app:
    image: ghcr.io/sibahia/iris-system-detector-ia:latest
    container_name: iris-system-detector-ia
    ports:
      - "${PORT:-8000}:8000"
    env_file:
      - .env
    volumes:
      - ./src/storage:/app/src/storage
    restart: unless-stopped
    user: "1000:1000"
    deploy:
      resources:
        limits:
          memory: 6G
          cpus: "3.5"
        reservations:
          memory: 1G
          cpus: "1.0"
EOF
```

**Diferencias con el docker-compose del repo:**

| Campo | Repo (dev) | VPS (produccion) |
|-------|-----------|------------------|
| Imagen | `build: .` | `image: ghcr.io/sibahia/iris-system-detector-ia:latest` |
| Volumes | `static/`, `templates/`, `src/storage/` | Solo `src/storage/` (DB) |
| Memoria | 3 GB | 6 GB |
| CPU | 3.0 | 3.5 |

> Los archivos estaticos, templates y modelos ya estan dentro de la imagen de GHCR. Solo se monta `src/storage/` para persistir la base de datos.

---

## Fase 5: Autenticar GHCR e iniciar Docker

### 5.1 Login a GitHub Container Registry

Necesitas un Personal Access Token (PAT) de GitHub con permisos `read:packages`:

1. Ir a https://github.com/settings/tokens
2. **Generate new token (classic)**
3. Seleccionar scope: `read:packages`
4. Copiar el token

En la VPS:

```bash
echo "TU_GITHUB_TOKEN" | docker login ghcr.io -u Sibahia --password-stdin
```

> Este login se guarda y no es necesario repetirlo.

### 5.2 Pull e iniciar

```bash
cd /opt/Iris-System-Detector-IA

# Pull de la imagen (~30 seg, sin build)
docker compose pull

# Iniciar en background
docker compose up -d

# Verificar que arranco
docker compose ps
docker compose logs --tail=20
```

### Verificar salud

```bash
curl http://localhost:8000/health
# Respuesta esperada: {"status": "healthy"}

# Verificar consumo de recursos
docker stats iris-system-detector-ia --no-stream
```

**Recursos esperados en idle:**

| Recurso | Uso esperado |
|---------|-------------|
| RAM | ~1.5-2.5 GB (con modelos cargados) |
| CPU | <5% en idle, spikes durante inferencia |
| Disco | ~500 MB (imagen Docker con modelos incluidos) |

---

## Fase 6: Registrar dominio en iFreeDomains

### 6.1 Crear cuenta

1. Ir a https://ifreedomains.com/register.php
2. Completar registro (gratis)
3. Buscar un dominio `.xyz` disponible (ej: `iris-detection.xyz`)
4. Registrar (costo: $0.00)

### 6.2 Configurar nameservers

En el panel de iFreeDomains:

1. Ir a **My Domains** > **Manage Domain**
2. **Management Tools** > **Nameservers**
3. Seleccionar **Use default nameservers** (o configurar custom)
4. Si usas nameservers custom, agregar:

```
ns1.contabo.net
ns2.contabo.net
ns3.contabo.net
```

5. Guardar cambios (propagacion: ~30 min)

### 6.3 Configurar registros DNS

En el panel de iFreeDomains:

1. Ir a **My Domains** > **Manage Domain**
2. **Manage iFreeDomains DNS**
3. Agregar registro A:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | TU_IP_VPS | 300 |
| A | www | TU_IP_VPS | 300 |

4. Guardar (propagacion: ~30 min)

### 6.4 Verificar propagacion

```bash
# Desde tu PC local
nslookup iris-detection.xyz
# Debe resolver a TU_IP_VPS

# O usar:
dig iris-detection.xyz
```

---

## Fase 7: Configurar Nginx

### 7.1 Crear configuracion

```bash
nano /etc/nginx/sites-available/iris
```

Contenido:

```nginx
server {
    listen 80;
    server_name iris-detection.xyz www.iris-detection.xyz;

    client_max_body_size 300M;

    # Archivos estaticos directos (sin pasar por Python)
    location /static/ {
        alias /opt/Iris-System-Detector-IA/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy a la app FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts para analisis de video/largo
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
        proxy_send_timeout 300s;
    }

    # WebSocket (si se usa en el futuro)
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 7.2 Habilitar sitio

```bash
ln -s /etc/nginx/sites-available/iris /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default  # quitar default
nginx -t  # verificar sintaxis
systemctl reload nginx
```

### 7.3 Verificar

```bash
curl -I http://iris-detection.xyz
# Debe retornar HTTP 200
```

---

## Fase 8: Certificado SSL con Let's Encrypt

```bash
certbot --nginx -d iris-detection.xyz -d www.iris-detection.xyz
```

Seguir las instrucciones en pantalla:
- Ingresar email para notificaciones
- Aceptar terminos
- Redirigir HTTP a HTTPS (opcion 2)

### Verificar HTTPS

```bash
curl -I https://iris-detection.xyz
# Debe retornar HTTP 200 con headers de HSTS
```

### Renovacion automatica

Certbot configura un cron automatico. Verificar:

```bash
systemctl status certbot.timer
certbot renew --dry-run
```

---

## Fase 9: Backup automatico

### 9.1 Crear directorio de backups

```bash
mkdir -p /opt/backups/iris
```

### 9.2 Script de backup

```bash
cat > /opt/backups/backup_iris.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups/iris"
APP_DIR="/opt/Iris-System-Detector-IA"

# Detener contenedor para backup consistente
cd "$APP_DIR"
docker compose stop app

# Backup de la base de datos
cp "$APP_DIR/src/storage/anomaly_history.db" "$BACKUP_DIR/db_$DATE.db"

# Backup de archivos estaticos
tar czf "$BACKUP_DIR/static_$DATE.tar.gz" -C "$APP_DIR" static/images/ static/videos/ 2>/dev/null

# Backup de configuracion
cp "$APP_DIR/.env" "$BACKUP_DIR/env_$DATE.env"

# Reiniciar contenedor
docker compose start app

# Limpiar backups viejos (mantener 7 dias)
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.env" -mtime +7 -delete

echo "$(date): Backup completado - $DATE" >> /var/log/iris_backup.log
EOF

chmod +x /opt/backups/backup_iris.sh
```

### 9.3 Cron de backup diario (3 AM)

```bash
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/backups/backup_iris.sh") | crontab -
```

---

## Fase 10: Monitoreo automatico

### 10.1 Script de health check

```bash
cat > /opt/iris_healthcheck.sh << 'EOF'
#!/bin/bash
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null)
if [ "$RESPONSE" != "200" ]; then
    echo "$(date): Iris no responde (HTTP $RESPONSE). Reiniciando..." >> /var/log/iris_healthcheck.log
    cd /opt/Iris-System-Detector-IA && docker compose restart
fi
EOF

chmod +x /opt/iris_healthcheck.sh
```

### 10.2 Cron cada 5 minutos

```bash
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/iris_healthcheck.sh") | crontab -
```

### 10.3 Verificar crons

```bash
crontab -l
```

---

## Fase 11: Verificar deployment completo

### Checklist

| Verificacion | Comando | Resultado esperado |
|-------------|---------|-------------------|
| Docker corriendo | `docker compose ps` | Estado: running |
| Health check | `curl http://localhost:8000/health` | `{"status": "healthy"}` |
| HTTPS | `curl -I https://iris-detection.xyz` | HTTP 200 |
| Recursos | `docker stats --no-stream` | RAM < 3 GB |
| Swap | `free -h` | Swap usado: 0-500 MB |
| Backup | `ls /opt/backups/iris/` | Archivos de hoy |
| Crons | `crontab -l` | 2 entries (backup + healthcheck) |
| Firewall | `ufw status` | 80, 443, 22 allow |

### URLs de la aplicacion

| Ruta | URL |
|------|-----|
| Dashboard | `https://iris-detection.xyz/` |
| Video | `https://iris-detection.xyz/video` |
| Imagenes | `https://iris-detection.xyz/images` |
| Streams | `https://iris-detection.xyz/stream` |
| Logs | `https://iris-detection.xyz/logs` |
| Terminal Logs | `https://iris-detection.xyz/terminal-logs` |
| Health | `https://iris-detection.xyz/health` |
| Stats | `https://iris-detection.xyz/statistics` |

---

## Fase 12: Actualizaciones futuras

```bash
cd /opt/Iris-System-Detector-IA

# 1. Backup antes de actualizar
/opt/backups/backup_iris.sh

# 2. Pull la ultima imagen desde GHCR
docker compose pull

# 3. Reiniciar con la nueva imagen
docker compose up -d

# 4. Verificar
curl http://localhost:8000/health
```

> No es necesario hacer `git pull` en la VPS. La imagen de GHCR contiene todo el codigo. Solo se necesita pull de la nueva imagen.

---

## Estructura de archivos en la VPS

```
/opt/
├── Iris-System-Detector-IA/          # Directorio de trabajo
│   ├── docker-compose.yml            # Orchestration (GHCR, NO build local)
│   ├── .env                          # Config (NO versionar)
│   └── src/storage/
│       └── anomaly_history.db        # SQLite (WAL mode) — persistente
├── backups/iris/                     # Backups automaticos
│   ├── db_YYYYMMDD_HHMMSS.db
│   ├── static_YYYYMMDD_HHMMSS.tar.gz
│   └── env_YYYYMMDD_HHMMSS.env
└── iris_healthcheck.sh               # Health check script
```

> **Dentro del container** (imagen GHCR):
> - `/app/app.py` — FastAPI main
> - `/app/models/` — Modelos YOLO (~201 MB)
> - `/app/static/` — CSS, JS, fonts, imagenes, videos
> - `/app/templates/` — HTML templates
> - `/app/src/storage/` — Montado desde el host (persistente)

---

## Comandos de emergencia

| Situacion | Comando |
|-----------|---------|
| Ver logs en tiempo real | `docker compose logs -f` |
| Ver ultimos 100 logs | `docker compose logs --tail=100` |
| Reiniciar servicio | `docker compose restart` |
| Detener servicio | `docker compose stop` |
| Iniciar servicio | `docker compose start` |
| Pull nueva imagen | `docker compose pull` |
| Verificar espacio en disco | `df -h` |
| Verificar RAM | `free -h` |
| Verificar swap | `swapon --show` |
| Verificar container | `docker ps \| grep iris` |
| Verificar nginx | `systemctl status nginx` |
| Verificar SSL | `certbot certificates` |
| Renovar SSL manualmente | `certbot renew` |
| Verificar crons | `crontab -l` |
| Verificar firewall | `ufw status` |
| Restaurar backup DB | `docker cp backup.db iris:/app/src/storage/anomaly_history.db` |

---

## Notas importantes

1. **Sin GPU**: Los modelos YOLO corren en CPU (~1-3 seg por frame). Para video, se procesa cada N frames (configurable).
2. **SQLite**: Usa WAL mode para concurrencia lectura/escritura. Funciona bien para 1-2 usuarios concurrentes.
3. **GHCR**: La imagen contiene todo (codigo, modelos, templates, static). Solo se monta la DB en el host.
4. **DuckDNS como fallback**: Si iFreeDomains tiene problemas, puedes usar DuckDNS como alternativa rapida (sin cambiar nada en Nginx, solo el DNS).
5. **Backup critico**: La DB SQLite es el dato mas importante. Los backups se guardan en `/opt/backups/iris/`.
6. **Swap**: Se configura 4 GB de swap para evitar OOM con modelos grandes cargados en RAM.
7. **No git pull en VPS**: Las actualizaciones son via `docker compose pull` (GHCR), no via `git pull`.
