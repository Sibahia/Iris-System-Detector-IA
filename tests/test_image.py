import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from unittest.mock import MagicMock, patch

from app import app, AVAILABLE_MODELS, DEFAULT_MODEL

client = TestClient(app)

class TestImageDetectionAPI:

    @pytest.fixture
    def mock_image_file(self):
        """Genera una imagen JPEG válida mínima usando PIL"""
        buf = io.BytesIO()
        Image.new("RGB", (2, 2), color="red").save(buf, format="JPEG")
        buf.seek(0)
        return ("test_image.jpg", buf.read(), "image/jpeg")

    @pytest.fixture
    def mock_detector_success_normal(self):
        """Simula la respuesta real exacta que espera tu app.py sin amenazas"""
        return {
            "is_anomaly": False,
            "risk_level": "normal",
            "persons_count": 0,
            "weapons_count": 0,
            "objects_count": 0,
            "detections": {"persons": [], "weapons": []},
            "summary": "No threats detected."
        }

    @pytest.fixture
    def mock_detector_success_critical(self):
        """Simula la respuesta real exacta con una anomalía crítica"""
        return {
            "is_anomaly": True,
            "risk_level": "alto",
            "persons_count": 0,
            "weapons_count": 1,
            "objects_count": 0,
            "detections": {
                "persons": [], 
                "weapons": [{"class_name": "pistol", "confidence": 0.88}]
            },
            "summary": "Weapon detected!"
        }

    @patch("app.save_image_analysis")
    @patch("detection.image_detector.get_image_detector")
    def test_analyze_image_endpoint_success(self, mock_get_detector, mock_save_db, mock_image_file, mock_detector_success_normal):
        """Prueba que el endpoint /analyze-image procese una imagen válida correctamente"""
        
        mock_detector_instance = MagicMock()
        mock_detector_instance.process_image.return_value = mock_detector_success_normal
        mock_get_detector.return_value = mock_detector_instance
        
        mock_save_db.return_value = 42

        response = client.post(
            "/analyze-image",
            files={"file": mock_image_file},
            params={"crowd_threshold": 5, "confidence": 0.5}
        )

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["is_anomaly"] is False
        assert json_data["risk_level"] == "normal"
        assert json_data["risk_percentage"] == 11
        assert json_data["image_id"] == 42
        assert "annotated_image_url" in json_data

    @patch("app.save_image_analysis")
    @patch("detection.image_detector.get_image_detector")
    def test_analyze_image_endpoint_critical_risk(self, mock_get_detector, mock_save_db, mock_image_file, mock_detector_success_critical):
        """Prueba que calcule riesgo progresivo según severidad de armas"""
        
        mock_detector_instance = MagicMock()
        mock_detector_instance.process_image.return_value = mock_detector_success_critical
        mock_get_detector.return_value = mock_detector_instance
        mock_save_db.return_value = 43

        response = client.post(
            "/analyze-image",
            files={"file": mock_image_file},
            params={"model_name": DEFAULT_MODEL}
        )

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["risk_level"] == "alto"
        assert json_data["risk_percentage"] == 76

    def test_analyze_image_invalid_file_type(self):
        """Prueba que el sistema rechace archivos que no sean imágenes"""
        bad_file = ("test.mp4", b"fake_video_data", "video/mp4")
        
        response = client.post("/analyze-image", files={"file": bad_file})
        
        assert response.status_code == 400
        assert "no está permitida" in response.json()["detail"]

    def test_analyze_image_unregistered_model(self, mock_image_file):
        """Prueba que falle con un error 400 si se solicita un modelo no registrado"""
        response = client.post(
            "/analyze-image",
            files={"file": mock_image_file},
            params={"model_name": "modelo_inexistente.pt"}
        )
        
        assert response.status_code == 400
        assert "no está registrado" in response.json()["detail"]