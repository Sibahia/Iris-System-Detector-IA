# Testing - Iris System Detector

## Running Tests

```bash
# All tests
pytest tests/ -v

# Database only
pytest tests/test_database.py -v

# Detection only
pytest tests/test_detection.py -v

# Image only
pytest tests/test_image.py -v

# With coverage
pytest tests/ --cov=app --cov=src
```

### Requirements

```bash
pip install -r requirements-test.txt
```

---

## Fixtures (conftest.py)

### test_db

Creates a temporary SQLite file, initializes tables, returns the path. Auto-cleaned after test.

### test_video

Creates a 30-frame test video (640x480, random frames) using OpenCV. Auto-cleaned after test.

---

## Existing Tests

### test_database.py (5 tests)

| Test | Description |
|------|-------------|
| `test_database_initialization` | Verifies `videos` table is created |
| `test_save_video_analysis` | Saves a record, verifies `video_id > 0` |
| `test_get_video_by_id` | Saves and retrieves by ID, verifies fields |
| `test_get_all_videos` | Saves 3 videos, verifies `len >= 3` |
| `test_delete_video` | Saves, deletes, verifies it's gone |

### test_detection.py (5 tests)

| Test | Description |
|------|-------------|
| `test_detector_initialization` | Initializes `YOLOAnomalyDetector(model_size='n')`, verifies model loaded |
| `test_detect_objects_in_frame` | Detects on black frame, verifies `persons` and `weapons` keys |
| `test_crowd_detection` | 6 persons -> `AGLOMERACION_DE_PERSONAS` anomaly |
| `test_weapon_detection` | Knife detection -> `ARMA_DETECTADA`, risk `alto` |
| `test_singleton_factory` | `get_yolo_detector(model_size='n')` returns same instance |

### test_image.py (4 tests)

| Test | Description |
|------|-------------|
| `test_analyze_image_endpoint_success` | POST valid image to `/analyze-image`, verifies 200, `is_anomaly=False`, `risk_percentage=11` |
| `test_analyze_image_endpoint_critical_risk` | Mocked weapon detection, verifies `risk_level="alto"`, `risk_percentage=76` |
| `test_analyze_image_invalid_file_type` | Sends `.mp4` to `/analyze-image`, verifies 400 |
| `test_analyze_image_unregistered_model` | Non-existent model, verifies 400 |

---

## API Test Fixtures

### Creating a test video

```python
# Using test_video fixture from conftest.py
# Generates test_video.mp4 with 30 random 640x480 frames
```

### Mocking the detector

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

## Test Structure

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

## Notes

- Detection tests (`test_detection.py`) require the `best.pt` model to be downloaded
- Image tests (`test_image.py`) use mocked detector (no real model needed)
- Database tests (`test_database.py`) are pure (SQLite only, no model)
- `pytest-asyncio` is available for async tests if needed
