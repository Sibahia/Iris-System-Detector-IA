import pytest
import numpy as np
from src.detection.yolo_detector import YOLOAnomalyDetector, get_yolo_detector

class TestYOLODetector:
    
    @pytest.fixture
    def detector(self):
        """Initialize detector for tests using the correct class name"""
        return YOLOAnomalyDetector(
            model_size='n',
            device='cpu',
            confidence_threshold=0.5,
            crowd_threshold=5,
            loiter_threshold_seconds=10.0
        )
    
    def test_detector_initialization(self, detector):
        """Test detector initializes correctly"""
        assert detector is not None
        assert detector.model is not None
        assert detector.confidence_threshold == 0.5
    
    def test_detect_objects_in_frame(self, detector):
        """Test object detection in single frame (without vehicles)"""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        results = detector.detect_objects(frame)
        
        assert isinstance(results, dict)
        assert "persons" in results
        assert "weapons" in results
        assert "vehicles" not in results 
    
    def test_crowd_detection(self, detector):
        """Test crowd anomaly detection using check_anomalies"""
        detections = {
            "persons": [{'class_id': 0, 'confidence': 0.9, 'center': (100, 100)}] * 6,
            "weapons": []
        }
        
        anomalies = detector.check_anomalies(detections)
        assert anomalies["is_anomaly"] == True
        assert "AGLOMERACION_DE_PERSONAS" in anomalies["anomaly_types"]
    
    def test_weapon_detection(self, detector):
        """Test weapon detection"""
        detections = {
            "persons": [],
            "weapons": [{'class_id': 43, 'class_name': 'knife', 'confidence': 0.8}]
        }
        
        anomalies = detector.check_anomalies(detections)
        assert anomalies["is_anomaly"] == True
        assert "ARMA_DETECTADA" in anomalies["anomaly_types"]
        assert anomalies["risk_level"] == "alto"

    def test_singleton_factory(self):
        """Test that get_yolo_detector returns the same instance"""
        detector1 = get_yolo_detector(model_size='n')
        detector2 = get_yolo_detector(model_size='n')
        assert detector1 is detector2