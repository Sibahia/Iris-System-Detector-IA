import os
import sys
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Asegurar que el entorno reconozca la raíz y la carpeta src/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from app import app, AVAILABLE_MODELS, DEFAULT_MODEL

client = TestClient(app)

class TestImageDetectionAPI:

    @pytest.fixture
    def mock_image_file(self):
        """Genera un archivo binario falso que simula ser una imagen JPEG"""
        return ("test_image.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF", "image/jpeg")

    @pytest.fixture
    def mock_detector_success_normal(self):
        """Simula una respuesta exitosa sin anomalías"""
        return {
            "is_anomaly": False,
            "risk_level": "normal",
            "detections": {"persons": [], "weapons": []},
            "summary": "No threats detected."
        }

    @pytest.fixture
    def mock_detector_success_critical(self):
        """Simula una respuesta con una anomalía crítica (arma detectada)"""
        return {
            "is_anomaly": True,
            "risk_level": "critico",
            "detections": {
                "persons": [], 
                "weapons": [{"class_name": "pistol", "confidence": 0.88}]
            },
            "summary": "Weapon detected!"
        }

    @patch("app.save_image_analysis")
    @patch("detection.image_detector.YOLOImageDetector")
    def test_analyze_image_endpoint_success(self, mock_detector_cls, mock_save_db, mock_image_file, mock_detector_success_normal):
        """Prueba que el endpoint /analyze-image procese una imagen válida correctamente"""
        
        # Configurar el Mock de YOLOImageDetector y su método process_image
        mock_detector_instance = MagicMock()
        mock_detector_instance.process_image.return_value = mock_detector_success_normal
        mock_detector_cls.return_value = mock_detector_instance
        
        # Configurar el mock de base de datos para retornar un ID ficticio
        mock_save_db.return_value = 42

        # Ejecutar la petición HTTP POST
        response = client.post(
            "/analyze-image",
            files={"file": mock_image_file},
            params={"crowd_threshold": 5, "confidence": 0.5}
        )

        # Aserciones
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["is_anomaly"] is False
        assert json_data["risk_level"] == "normal"
        assert json_data["risk_percentage"] == 10  # Lógica del if/else en tu app.py
        assert json_data["image_id"] == 42
        assert "annotated_image_url" in json_data

    @patch("app.save_image_analysis")
    @patch("detection.image_detector.YOLOImageDetector")
    def test_analyze_image_endpoint_critical_risk(self, mock_detector_cls, mock_save_db, mock_image_file, mock_detector_success_critical):
        """Prueba que calcule el 100% de riesgo si el nivel es crítico"""
        
        mock_detector_instance = MagicMock()
        mock_detector_instance.process_image.return_value = mock_detector_success_critical
        mock_detector_cls.return_value = mock_detector_instance
        mock_save_db.return_value = 43

        response = client.post(
            "/analyze-image",
            files={"file": mock_image_file},
            params={"model_name": DEFAULT_MODEL}
        )

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["risk_level"] == "critico"
        assert json_data["risk_percentage"] == 100  # Máximo riesgo verificado

    def test_analyze_image_invalid_file_type(self):
        """Prueba que el sistema rechace archivos que no sean imágenes"""
        bad_file = ("test.mp4", b"fake_video_data", "video/mp4")
        
        response = client.post("/analyze-image", files={"file": bad_file})
        
        assert response.status_code == 400
        assert response.json()["detail"] == "File must be an image"

    def test_analyze_image_unregistered_model(self, mock_image_file):
        """Prueba que falle con un error 400 si se solicita un modelo no registrado"""
        response = client.post(
            "/analyze-image",
            files={"file": mock_image_file},
            params={"model_name": "modelo_inexistente.pt"}
        )
        
        assert response.status_code == 400
        assert "is not registered in AVAILABLE_MODELS" in response.json()["detail"]