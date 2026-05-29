# Guía de Contribución (Contributing Guidelines)

¡Te damos la bienvenida a nuestro proyecto de IA para CCTV! Este documento establece las normas, flujos de trabajo y buenas prácticas que todos los desarrolladores del equipo debemos seguir para mantener la estabilidad, optimización y el blindaje de la rama de producción (`main`).

Al seguir estas pautas, garantizas que nuestro sistema de detección de anomalías y su capa de almacenamiento sigan funcionando de manera impecable.

---

## 🛡️ Producción está Blindada

La rama `main` (o `master`) cuenta con **Branch Protection Rules** activas. Queda estrictamente prohibido:
* Realizar subidas directas (`git push origin main`).
* Evadir las reglas de protección de rama, incluso si cuentas con permisos de administrador en GitHub.

Todo cambio, corrección de errores o nueva característica de Inteligencia Artificial debe pasar obligatoriamente por una revisión de código y superar la suite completa de pruebas automatizadas en nuestro pipeline de Integración Continua (CI).

---

## 🚀 Flujo de Trabajo (Git Workflow)

Para añadir código al repositorio, sigue estrictamente este flujo de trabajo de 5 pasos:

### 1. Crear una rama local
Mantén tus ramas actualizadas a partir de `main` y utiliza nombres descriptivos según el propósito:
* Para nuevas características de IA o base de datos: `feature/nombre-de-la-mejora`
* Para corrección de errores: `bugfix/nombre-del-error`

```bash
git checkout main
git pull origin main
git checkout -b feature/nueva-conexion-camara
```

### 2. Desarrollar y respetar la arquitectura

- Clean Code: Sigue los principios SOLID (especialmente el Principio de Responsabilidad Única).

- Base de datos: Si modificas src/storage/database.py, asegúrate de mantener el aislamiento de las rutas utilizando variables de entorno o mockeo dinámico en los entornos de prueba para no corromper la base de datos real (anomaly_history.db).

### 3. Ejecutar la Suite de Pruebas Unitarias

Antes de confirmar cualquier cambio y subirlo al servidor, debes correr de forma local toda la suite de pruebas con `pytest`. Ningún código se fusionará si hay un solo fallo.

```bash
pytest tests/
```

Debes asegurarte de que tanto el módulo de base de datos (`test_database.py`) como el de detección analítica con visión artificial (`test_detection.py`) marquen un estado exitoso:
```Plaintext
========================= 10 passed in 4.79s ==========================
```

### 4. Subir la rama y abrir un Pull Request (PR)

Una vez que tus pruebas locales pasen a verde, sube tu rama a GitHub:


```powershell
git add .
git commit -m "feat: implementar cache en la persistencia de video"
git push origin feature/nueva-conexion-camara
```

Dirígete a la interfaz web de GitHub y abre un Pull Request hacia la rama main.
### 5. Revisión por Pares y Fusión

- Revisión de Código: Al menos un desarrollador del equipo debe revisar tus cambios, analizar la lógica y otorgar su aprobación (Approve).

- Aprobación de la CI: El pipeline automático de GitHub Actions ejecutará de nuevo pytest. Una vez que la CI esté en verde y cuentes con la aprobación de tu par, el botón de Merge se habilitará para unir tus cambios de forma segura a producción.

## 🛠️ Stack Tecnológico del Proyecto

Asegúrate de que tu entorno de desarrollo local coincida con las dependencias oficiales del entorno de ejecución automatizado:

- Lenguaje: Python 3.14+

- Framework de Testing: pytest 9.0+ con plugins para operaciones asíncronas (pytest-asyncio).

- Visión Artificial: Modelos YOLO y procesamiento de video con OpenCV (cv2).

- Persistencia: Capa relacional nativa con SQLite3 mediante gestión con Row Factory para mapeo de diccionarios.

## 💬 Estilo de Commits

Para mantener un historial de Git legible y limpio, se recomienda seguir la convención de commits semánticos (Conventional Commits):

- feat: Nueva característica para el sistema (ej. feat: agregar bounding boxes a eventos de anomalía).

- fix: Corrección de un fallo (ej. fix: resolver desajuste de parámetros en fixture test_db).

- docs: Cambios exclusivos en la documentación (ej. docs: actualizar instrucciones en contributing.md).

- refactor: Reestructuración de código existente sin cambiar su comportamiento público.