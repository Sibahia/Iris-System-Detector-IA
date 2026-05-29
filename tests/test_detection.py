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
        """Test object detection in single frame"""
        import numpy as np
        
        # Create dummy frame
        frame = np.zeros((640, 480, 3), dtype=np.uint8)
        
        # Run detection
        results = detector.detect_frame(frame)
        
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)
    
    def test_crowd_detection(self, detector):
        """Test crowd anomaly detection"""
        # Simulate 10 person detections
        detections = [
            {'class': 'person', 'bbox': [i*50, 100, 50, 100]}
            for i in range(10)
        ]
        
        is_crowd = detector.is_crowd_anomaly(detections, threshold=5)
        assert is_crowd == True
    
    def test_weapon_detection(self, detector):
        """Test weapon detection"""
        detections = [
            {'class': 'knife', 'confidence': 0.8}
        ]
        
        has_weapon = detector.has_weapon(detections)
        assert has_weapon == True
    
    def test_loitering_detection(self, detector):
        """Test loitering detection"""
        # Simulate person staying in same position
        track_id = 1
        positions = [(100, 100)] * 15  # 15 frames at same position
        
        for pos in positions:
            detector.update_tracker(track_id, pos)
        
        is_loitering = detector.is_loitering(track_id, threshold=10.0)
        assert is_loitering == True
    
    @pytest.mark.parametrize("confidence,expected", [
        (0.3, True),   # Low confidence should detect
        (0.5, True),   # Medium confidence
        (0.9, False),  # High confidence filters out
    ])
    def test_confidence_thresholds(self, confidence, expected):
        """Test different confidence thresholds"""
        detector = YOLODetector(
            model_size='n',
            confidence_threshold=confidence
        )
        
        # Simulate detection with 0.6 confidence
        detection = {'class': 'person', 'confidence': 0.6}
        passed = detector.passes_threshold(detection)
        
        assert passed == expected