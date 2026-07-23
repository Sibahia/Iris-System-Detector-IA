# Testing - Iris System Detector

## Correr Tests

```bash
# Todos los tests
pytest tests/ -v

# Solo database
pytest tests/test_database.py -v

# Solo deteccion
pytest tests/test_detection.py -v

# Solo imagen
pytest tests/test_image.py -v

# Con cobertura
pytest tests/ --cov=app --cov=src
```

### Requisitos

```bash
pip install -r requirements-test.txt
```

---

## Fixtures (conftest.py)

### test_db

Crea un SQLite temporal, inicializa las tablas, retorna el path. Se auto-elimina al finalizar.

### test_video

Crea un video de prueba de 30 frames (640x480, frames aleatorios) con OpenCV. Se auto-elimina al finalizar.

---

## Tests Existentes

### test_database.py (5 tests)

| Test | Descripcion |
|------|-------------|
| `test_database_initialization` | Verifica que la tabla `videos` se crea |
| `test_save_video_analysis` | Guarda un registro, verifica `video_id > 0` |
| `test_get_video_by_id` | Guarda y recupera por ID, verifica campos |
| `test_get_all_videos` | Guarda 3 videos, verifica `len >= 3` |
| `test_delete_video` | Guarda, elimina, verifica que no existe |

### test_detection.py (5 tests)

| Test | Descripcion |
|------|-------------|
| `test_detector_initialization` | Inicializa `YOLOAnomalyDetector(model_size='n')`, verifica modelo cargado |
| `test_detect_objects_in_frame` | Detecta en frame negro, verifica `persons` y `weapons` |
| `test_crowd_detection` | 6 personas -> anomalia `AGLOMERACION_DE_PERSONAS` |
| `test_weapon_detection` | Deteccion de cuchillo -> `ARMA_DETECTADA`, risk `alto` |
| `test_singleton_factory` | `get_yolo_detector(model_size='n')` retorna misma instancia |

### test_image.py (4 tests)

| Test | Descripcion |
|------|-------------|
| `test_analyze_image_endpoint_success` | POST imagen valida a `/analyze-image`, verifica 200, `is_anomaly=False`, `risk_percentage=11` |
| `test_analyze_image_endpoint_critical_risk` | Mock de arma detectada, verifica `risk_level="alto"`, `risk_percentage=76` |
| `test_analyze_image_invalid_file_type` | Envio de `.mp4` a `/analyze-image`, verifica 400 |
| `test_analyze_image_unregistered_model` | Modelo inexistente, verifica 400 |

---

## Fixtures para Tests de API

### Crear video de prueba

```python
# Usando fixture test_video de conftest.py
# Genera test_video.mp4 con 30 frames aleatorios 640x480
```

### Mock del detector

```python
from unittest.mock import patch, MagicMock

mock_result = {
    "persons": 2, "weapons": 0, "vehicles": 0,
    "persons_count": 2, "weapons_count": 0, "objects_count": 0,
    "classes": {}, "class_names": {},
    "anomaly": False, "anomaly_score": 0.0,
    "risk_level": "normal", "anomaly_types": []
}

with patch("app.get_yolo_detector") as mock:
    mock.return_value.analyze_frame.return_value = mock_result
    # ... test
```

---

## Estructura de un Test

```python
import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

class TestEndpoint:
    def test_success(self, test_video):
        with open(test_video, "rb") as f:
            response = client.post("/analyze-image", files={"file": ("test.jpg", f, "image/jpeg")})
        assert response.status_code == 200
        data = response.json()
        assert "risk_level" in data

    def test_invalid_input(self):
        response = client.post("/analyze-image", files={"file": ("test.mp4", b"data", "video/mp4")})
        assert response.status_code == 400
```

---

## Notas

- Los tests de deteccion (`test_detection.py`) necesitan el modelo `best.pt` descargado
- Los tests de imagen (`test_image.py`) usan mocks del detector (no necesitan modelo real)
- Los tests de database (`test_database.py`) son puros (solo SQLite, sin modelo)
- `pytest-asyncio` esta disponible para tests async si se necesitan
