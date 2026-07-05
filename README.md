# 📹 Sistema de detección de amenazas en entornos de seguridad - CCTV

Este proyecto es un fork del repositorio [CCTV_Video_Anomaly_Detection](https://github.com/saadkhan2003/CCTV_Video_Anomaly_Detection), sistema de detección de anomalías de vídeo de alto rendimiento, impulsado por IA, diseñado para videovigilancia CCTV. Utiliza YOLOv11 con optimización OpenVINO para la detección en tiempo real en CPU estándar, e incluye una interfaz web y funciones de alerta de anomalías.

---
## 🏗️ Arquitectura del Sistema

```mermaid
graph TD
    %% Estilos globales
    classDef frontend fill:#3b82f6,stroke:#1d4ed8,color:#fff,font-weight:bold;
    classDef backend fill:#10b981,stroke:#047857,color:#fff,font-weight:bold;
    classDef module fill:#6366f1,stroke:#4338ca,color:#fff;
    classDef storage fill:#f59e0b,stroke:#b45309,color:#fff;

    %% Nodos de la Arquitectura
    UI[Frontend<br>8 Vistas HTML + JS/CSS]:::frontend
    API[FastAPI Backend<br>app.py]:::backend

    subgraph Core [Módulos de Detección]
        VID[Video Detector<br>YOLOAnomalyDetector<br>YOLOv11 + OpenVINO + ByteTrack]:::module
        IMG[Image Detector<br>YOLOImageDetector]:::module
        LIVE[Live Stream<br>LiveStreamDetector<br>MJPEG]:::module
        VIZ[Visualization<br>Autoencoder]:::module
    end

    subgraph Aux [Servicios Auxiliares]
        ALT[Alerts Module<br>SMTP Email]:::module
        DB_MOD[Storage Module<br>SQLite]:::module
    end

    DB[(anomaly_history.db)]:::storage
    MOD[(Modelos YOLO<br>best.pt / OpenVINO)]:::storage

    %% Flujos de datos y conexiones
    UI <-->|HTTP / WebSockets| API

    API -->|/analyze-yolo| VID
    API -->|/analyze-image| IMG
    API -->|/live/*| LIVE
    API -->|/history / /statistics| DB_MOD
    API -->|/configure-email| ALT

    VID -->|Resultados| API
    IMG -->|Resultados| API
    LIVE -->|Resultados| API

    VID -.->|Lee modelo| MOD
    IMG -.->|Lee modelo| MOD
    LIVE -.->|Lee modelo| MOD

    DB_MOD <-->|CRUD| DB
```
---
## 📈 Diagramas del Sistema

### 1. Diagrama de Casos de Uso
```mermaid
graph LR
    subgraph Actores
        Operador((Operador))
        Administrador((Administrador))
    end

    subgraph CCTV_IA_TEST [Sistema CCTV_IA_TEST]
        Monitoreo(Monitoreo)
        Visualizar(Visualizar Flujo de Video)
        Detectar(Detectar Objetos)
        RecibirAlerta(Recibir Alerta de Alarma)
        
        Entrenar(Entrenar Modelo)
        Actualizar(Actualizar Modelo)
        Configurar(Configurar Parámetros)
        
        Visualizar -.->|&lt;&lt;include&gt;&gt;| Detectar
        Visualizar -.->|&lt;&lt;extend&gt;&gt;| RecibirAlerta
    end

    Operador --> Monitoreo
    Operador --> Visualizar
    Operador --> RecibirAlerta

    Administrador --> Entrenar
    Administrador --> Actualizar
    Administrador --> Configurar
```

### 2. Diagrama de Flujo: Captura de Objetos para Entrenamiento (Armas)
```mermaid
flowchart TD
    Inicio([INICIO]) --> Iniciar[Iniciar N Cantidad de Entrenamiento]
    Iniciar --> Cargar[Cargar N Cantidad de Imágenes]
    Cargar --> Capturar[Capturar Frame de Imagen]
    
    Capturar --> EsArma{¿Es un Arma?}
    EsArma -- NO --> Capturar
    EsArma -- SI --> Confianza{¿Confianza > 0.5?}
    
    Confianza -- NO --> Capturar
    Confianza -- SI --> Guardar[Guardar Resultado en Dataset]
    
    Guardar --> Guardado[Entrenamiento Guardado]
    Guardado --> Cumplido{¿Entrenar N Cantidad<br/>Cumplido?}
    
    Cumplido -- NO --> Iniciar
    Cumplido -- SI --> Fin([FIN])
```

### 3. Diagrama de Flujo: Detección de Objetos en Producción (Armas)
```mermaid
flowchart TD
    Inicio([INICIO]) --> Capturar[Capturar Frame]
    Capturar --> Valido{¿Frame Válido?}
    
    Valido -- NO --> Capturar
    Valido -- SI --> Ejecutar[Ejecutar Modelo de Predicción]
    
    Ejecutar --> EsArma{¿Es un Arma?}
    EsArma -- NO --> Capturar
    EsArma -- SI --> Confianza{¿Confianza > 0.5?}
    
    Confianza -- NO --> Ejecutar
    Confianza -- SI --> Detectada[\Arma Detectada/]
    
    Detectada --> Fin([FIN])
```

### 4. Diagrama de Secuencia de Detección
```mermaid
sequenceDiagram
    participant Sistema as Sistema
    participant Camara as Cámara/Video
    participant Modelo as Modelo IA
    participant Alerta as Alerta

    Sistema->>Camara: Detectar fuente (Cámara/Stream)
    Camara-->>Sistema: Fuente lista
    Sistema->>Modelo: Inicializar modelo

    loop Bucle de detección
        Sistema->>Camara: Capturar frames
        Camara-->>Sistema: Frame obtenido
        Sistema->>Modelo: Analizar frames
        
        alt ¿Detecta arma?
            Modelo-->>Sistema: Arma detectada
            Note over Sistema: Trazar cuadro sobre detección
            Sistema->>Alerta: Enviar alerta
        else No detecta arma
            Modelo-->>Sistema: Sin detección
        end
    end
```
---

## 🛠️ Inicio Rápido

### 📋 Pre-requisitos

Antes de comenzar, asegúrate de cumplir con los siguientes requerimientos en tu entorno local:

- **Python**: 3.10 o superior
- **Operating System**: Windows 10+ / Ubuntu 22.04 / macOS 12+
- **RAM**: 8 GB mínimo (16 GB recomendado)
- **Storage**: Al menos 10 GB de espacio libre (para dependencias y modelos)

### 🚀 Instalación

Sigue estos pasos en tu terminal para clonar el proyecto y preparar tu entorno de desarrollo:

1. **Clonar el repositorio**
   ```bash
   git clone [https://github.com/Sibahia/prueba-cctv-ia.git](https://github.com/Sibahia/prueba-cctv-ia)
   cd prueba-cctv-ia
   ```

2. **Crear el entorno virtual (Altamente recomendado)**
    ```bash
    python -m venv venv
    ```

    - **Activar en Linux/macOS:**
        ```bash
        source venv/bin/activate
        ```

    - **Activar en Windows:**
        ```bash
        .\venv\Scripts\Activate.ps1
        ```

3. **Instalar las dependencias**
    ```powershell
    pip install -r requirements.txt

    Nota: La primera instalación puede tardar unos minutos mientras descarga librerías pesadas como OpenVINO o parches de procesamiento de video.
    ```

### Primera Prueba (First Run)

Para verificar que todo el sistema base e interfaces funcionen correctamente después de tus modificaciones:

1. **Iniciar el servidor backend/aplicación**
    ```python
    python app.py
    ```

        Nota importante: En esta primera ejecución, el script descargará automáticamente el modelo base YOLOv11 (~50MB) y realizará la conversión inicial al formato optimizado de OpenVINO (puede tardar de 1 a 2 minutos).

2. **Acceder al Dashboard**
    Abre tu navegador web e ingresa a la siguiente dirección local:
    ```plaintext
    http://localhost:
    ```

3. **Prueba de análisis rápida**

    - Ve a la pestaña "Analyze".

    - Sube un video corto de prueba (formatos soportados: .mp4, .avi, .mov).

    - Deja los parámetros por defecto y haz clic en "Start Analysis".

    - Comprueba que el procesamiento avance en tiempo real y devuelva los recuadros de detección de anomalías sin errores en la consola.

---

## 🐳 Despliegue con Docker

Este proyecto cuenta con soporte nativo para contenedores Docker mediante **Docker Compose**, lo que facilita su despliegue y actualización en cualquier entorno sin necesidad de configurar Python o instalar dependencias de sistema manualmente.

### 📋 Pre-requisitos
- **Docker** instalado y en ejecución.
- **Docker Compose** instalado.

### 🚀 Construir y Ejecutar el Contenedor
Para levantar la aplicación por primera vez o después de realizar cambios en el código:
```bash
docker compose up -d --build
```
Este comando se encarga de:
1. Descargar e instalar la imagen base con OpenCV y dependencias necesarias.
2. Compilar e instalar los paquetes de `requirements.txt`.
3. Iniciar el backend con FastAPI expuesto en el puerto `8000`.

### 🔄 Cómo Actualizar el Contenedor (cctv_ia_test)
Cuando realices cambios en el código base o actualices dependencias en `requirements.txt`, ejecuta el siguiente comando para reconstruir la imagen y reiniciar el contenedor de manera transparente:
```bash
docker compose up -d --build
```
*Esto detendrá el contenedor actual, reconstruirá únicamente las capas que hayan cambiado y levantará el nuevo contenedor en segundo plano.*

### 🛑 Detener el Contenedor
Para pausar o detener el servicio de forma limpia:
```bash
docker compose down
```

### 📂 Persistencia de Datos y Volúmenes
El archivo `docker-compose.yml` mapea volúmenes clave para asegurar la persistencia y permitir cambios rápidos en el diseño sin reconstruir la imagen:

| Origen (Host) | Destino (Contenedor) | Propósito |
|---|---|---|
| `./src/storage/anomaly_history.db` | `/app/src/storage/anomaly_history.db` | Historial de análisis persistente (SQLite) |
| `./static` | `/app/static` | Almacenamiento de videos, fotos e inferencias procesadas |
| `./templates` | `/app/templates` | Vistas HTML dinámicas para modificaciones en tiempo de diseño |

---
