# Manual de Usuario - Iris System Detector

## Acceso

- **Local:** `http://localhost:8000`
- **Produccion:** `https://iris-detector.duckdns.org`

---

## Interfaces

### Landing Page (`/`)

Pagina principal con acceso rapido a todas las funcionalidades.

### Analisis de Video (`/video-analysis`)

1. Arrastrar o seleccionar un video (.mp4, .avi, .mov, .mkv)
2. Seleccionar modelo (opcional)
3. Ajustar umbral de confianza (opcional)
4. Hacer clic en **Analizar**
5. Esperar progreso (barra de progreso)
6. Ver resultados: nivel de riesgo, clases detectadas, anomalias

### Analisis de Imagen (`/image-analysis`)

1. Arrastrar o seleccionar una imagen (.jpg, .png, .gif, .bmp, .webp)
2. Seleccionar modelo (opcional)
3. Ajustar umbral de confianza (opcional)
4. Hacer clic en **Analizar**
5. Ver resultados inmediatos: personas, armas, objetos, nivel de riesgo

### Monitoreo en Vivo (`/stream-analysis`)

1. Seleccionar fuente (webcam o URL RTSP)
2. Seleccionar modelo
3. Ajustar confianza
4. Hacer clic en **Iniciar**
5. Ver feed en vivo con detecciones superpuestas
6. Hacer clic en **Detener** para guardar resumen

### Historial (`/logs`)

- Ver todos los registros (video, imagen, stream)
- Filtrar por nombre, tipo de registro, o nivel de riesgo
- Buscar por texto
- Ver detalle de cada registro (modal)
- Eliminar registros

### Logs del Sistema (`/terminal-logs`)

- Visor estilo terminal con auto-refresh
- Filtrar por nivel (DEBUG, INFO, WARNING, ERROR)
- Paginacion (50 por pagina)

### Contribuidores (`/contributors`)

- Lista de contribuidores del proyecto

---

## Niveles de Riesgo

| Nivel | Significado | Color |
|-------|-------------|-------|
| `normal` | Sin anomalias | Verde |
| `bajo` | Actividad menor | Azul |
| `medio` | Actividad sospechosa | Amarillo |
| `alto` | Amenaza confirmada | Rojo |

---

## Modelos Disponibles

| Modelo | Uso ideal |
|--------|-----------|
| `best.pt` | General (armas + personas) |
| `gun_detector.pt` | Solo armas de fuego |
| `gun.pt` | Armas con contexto de persona |
| `suspicious.pt` | Comportamientos sospechosos (asalto, pelea, secuestro, terrorismo, robo) |

---

## Tipos de Anomalia

| Tipo | Descripcion | Riesgo |
|------|-------------|--------|
| ARMA_DETECTADA | Se detecto un arma | alto |
| PERSONA_ARMADA | Persona con arma | alto |
| AGLOMERACION_DE_PERSONAS | Muchas personas juntas | medio |
| ALTERCADO_POTENCIAL | Posible altercado | alto |
| AUTORIDAD_DETECTADA | Presencia policial | bajo |
| PRESO_DETECTADO | Persona identificada como prisionero | medio |
| ASALTO | Acto de asalto | alto |
| PELEA | Pelea en curso | alto |
| SECUESTRO | Situacion de secuestro | alto |
| TERRORISMO | Actividad terrorista | alto |
| ROBO | Acto de robo | alto |

---

## Formatos Soportados

| Tipo | Formatos |
|------|----------|
| Video | .mp4, .avi, .mov, .mkv |
| Imagen | .jpg, .jpeg, .png, .gif, .bmp, .webp |
| Stream | Camara web (index 0, 1, ...) o URL RTSP |

---

## Limites

- Tamano maximo de upload: 300 MB (configurable via `MAX_FILE_SIZE_MB`)
- Analisis de video: maximo 2 simultaneos
- Analisis de imagen: maximo 1 simultaneo
- Streams en vivo: maximo 2 simultaneos

---

## Troubleshooting

| Problema | Solucion |
|----------|----------|
| No carga la pagina | Verificar que el servicio esta corriendo (`docker compose ps`) |
| Upload falla | Verificar tamano del archivo (< 300 MB) |
| Video no analiza | Verificar formato (.mp4, .avi, .mov, .mkv) |
| Modelo no aparece | Verificar `AVAILABLE_MODELS` en `.env` |
| Lento en CPU | Usar modelo `n` (nano) en vez de `s` o `m` |
