import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import numpy as np
import time
import os

from src.detection.live_stream import (
    LiveStreamDetector,
    _streams,
    create_stream,
    get_stream,
    stop_stream,
    list_streams,
    detect_cameras,
)


@pytest.fixture(autouse=True)
def clean_streams():
    """Clean global _streams dict between tests"""
    _streams.clear()
    yield
    _streams.clear()


class TestLiveStreamDetectorInit:

    def test_default_values(self):
        detector = LiveStreamDetector()
        assert detector.source == 0
        assert detector.crowd_threshold == 3
        assert detector.confidence == 0.5
        assert detector.model_path is None

    def test_internal_attributes(self):
        detector = LiveStreamDetector()
        assert detector.cap is None
        assert detector.detector is None
        assert detector.is_running is False
        assert detector.current_frame is None
        assert detector.current_results == {}
        assert detector.alert_callback is None
        assert detector.last_alert_time == 0
        assert detector.alert_cooldown == 30
        assert detector.total_frames == 0
        assert detector.anomaly_frame_count == 0
        assert detector.max_person_count == 0
        assert detector.max_weapon_count == 0
        assert detector.accumulated_class_counts == {}
        assert detector.anomaly_types_set == set()
        assert detector.fps_values == []

    def test_custom_values(self):
        detector = LiveStreamDetector(
            source="rtsp://test",
            crowd_threshold=5,
            confidence=0.8,
            model_path="/path/to/model.pt",
        )
        assert detector.source == "rtsp://test"
        assert detector.crowd_threshold == 5
        assert detector.confidence == 0.8
        assert detector.model_path == "/path/to/model.pt"


class TestStart:

    @patch("src.detection.live_stream.cv2")
    def test_start_with_int_source_success(self, mock_cv2):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cv2.VideoCapture.return_value = mock_cap

        mock_detector_mod = MagicMock()
        mock_detector_mod.get_yolo_detector.return_value = MagicMock()

        with patch.dict("sys.modules", {
            "detection": MagicMock(),
            "detection.yolo_detector": mock_detector_mod,
        }):
            detector = LiveStreamDetector(source=0, model_path="/models/yolov8s.pt")
            result = detector.start()

        assert result is True
        assert detector.is_running is True
        assert detector.cap == mock_cap
        mock_cv2.VideoCapture.assert_called_once_with(0)

    @patch("src.detection.live_stream.cv2")
    def test_start_with_int_source_fails_to_open(self, mock_cv2):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cv2.VideoCapture.return_value = mock_cap

        detector = LiveStreamDetector(source=0)
        result = detector.start()

        assert result is False
        assert detector.is_running is False

    @patch("src.detection.live_stream.cv2")
    def test_start_with_string_source_sets_env(self, mock_cv2, monkeypatch):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.CAP_FFMPEG = 1900

        mock_detector_mod = MagicMock()
        mock_detector_mod.get_yolo_detector.return_value = MagicMock()

        with patch.dict("sys.modules", {
            "detection": MagicMock(),
            "detection.yolo_detector": mock_detector_mod,
        }):
            detector = LiveStreamDetector(source="rtsp://stream.test")
            result = detector.start()

        assert result is True
        assert os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS") == "timeout;5000000"
        mock_cv2.VideoCapture.assert_called_once_with("rtsp://stream.test", 1900)

    @patch("src.detection.live_stream.cv2")
    def test_start_exception_returns_false(self, mock_cv2):
        mock_cv2.VideoCapture.side_effect = Exception("camera error")

        detector = LiveStreamDetector(source=0)
        result = detector.start()

        assert result is False
        assert detector.is_running is False


class TestStop:

    @patch("src.detection.live_stream.cv2")
    def test_stop_releases_cap(self, mock_cv2):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cv2.VideoCapture.return_value = mock_cap

        mock_detector_mod = MagicMock()
        mock_detector_mod.get_yolo_detector.return_value = MagicMock()

        with patch.dict("sys.modules", {
            "detection": MagicMock(),
            "detection.yolo_detector": mock_detector_mod,
        }):
            detector = LiveStreamDetector(source=0)
            detector.start()
            detector.stop()

        assert detector.is_running is False
        assert detector.cap is None
        mock_cap.release.assert_called_once()

    def test_stop_without_cap(self):
        detector = LiveStreamDetector()
        detector.stop()
        assert detector.is_running is False
        assert detector.cap is None


class TestGetFrame:

    def test_returns_none_when_not_running(self):
        detector = LiveStreamDetector()
        assert detector.get_frame() is None

    def test_returns_none_when_ret_false(self):
        mock_cap = MagicMock()
        mock_cap.read.return_value = (False, None)

        detector = LiveStreamDetector()
        detector.cap = mock_cap
        detector.is_running = True

        assert detector.get_frame() is None

    @patch("src.detection.live_stream.cv2")
    def test_returns_none_when_no_detector(self, mock_cv2):
        mock_cap = MagicMock()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        mock_cv2.imencode.return_value = (True, MagicMock(tobytes=MagicMock(return_value=b"\xff\xd8")))
        mock_cv2.FONT_HERSHEY_SIMPLEX = 0

        detector = LiveStreamDetector()
        detector.cap = mock_cap
        detector.is_running = True
        detector.detector = None

        result = detector.get_frame()

        assert result is not None
        assert isinstance(result[0], bytes)

    @patch("src.detection.live_stream.cv2")
    def test_returns_frame_with_detector(self, mock_cv2):
        mock_cap = MagicMock()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)

        annotated_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_detector = MagicMock()
        mock_detector.process_frame.return_value = (
            annotated_frame,
            {
                "is_anomaly": False,
                "person_count": 1,
                "weapon_count": 0,
                "all_boxes": [{"class_name": "person"}],
                "anomaly_types": [],
            },
        )

        mock_cv2.imencode.return_value = (True, MagicMock(tobytes=MagicMock(return_value=b"\xff\xd8")))
        mock_cv2.FONT_HERSHEY_SIMPLEX = 0
        mock_cv2.putText = MagicMock()

        detector = LiveStreamDetector()
        detector.cap = mock_cap
        detector.is_running = True
        detector.detector = mock_detector

        result = detector.get_frame()

        assert result is not None
        assert detector.total_frames == 1
        assert detector.max_person_count == 1

    @patch("src.detection.live_stream.cv2")
    def test_anomaly_increments_counter(self, mock_cv2):
        mock_cap = MagicMock()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)

        mock_detector = MagicMock()
        mock_detector.process_frame.return_value = (
            frame,
            {
                "is_anomaly": True,
                "person_count": 6,
                "weapon_count": 0,
                "all_boxes": [{"class_name": "person"}] * 6,
                "anomaly_types": ["AGLOMERACION_DE_PERSONAS"],
            },
        )

        mock_cv2.imencode.return_value = (True, MagicMock(tobytes=MagicMock(return_value=b"\xff\xd8")))
        mock_cv2.FONT_HERSHEY_SIMPLEX = 0

        detector = LiveStreamDetector()
        detector.cap = mock_cap
        detector.is_running = True
        detector.detector = mock_detector

        detector.get_frame()

        assert detector.anomaly_frame_count == 1
        assert "AGLOMERACION_DE_PERSONAS" in detector.anomaly_types_set
        assert detector.max_person_count == 6

    @patch("src.detection.live_stream.cv2")
    def test_alert_callback_called(self, mock_cv2):
        mock_cap = MagicMock()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)

        mock_detector = MagicMock()
        mock_detector.process_frame.return_value = (
            frame,
            {
                "is_anomaly": True,
                "person_count": 6,
                "weapon_count": 0,
                "all_boxes": [{"class_name": "person"}] * 6,
                "anomaly_types": ["AGLOMERACION_DE_PERSONAS"],
            },
        )

        mock_cv2.imencode.return_value = (True, MagicMock(tobytes=MagicMock(return_value=b"\xff\xd8")))
        mock_cv2.FONT_HERSHEY_SIMPLEX = 0

        alert_mock = MagicMock()
        detector = LiveStreamDetector()
        detector.cap = mock_cap
        detector.is_running = True
        detector.detector = mock_detector
        detector.alert_callback = alert_mock
        detector.last_alert_time = 0

        detector.get_frame()

        alert_mock.assert_called_once()

    @patch("src.detection.live_stream.cv2")
    def test_alert_callback_respects_cooldown(self, mock_cv2):
        mock_cap = MagicMock()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)

        mock_detector = MagicMock()
        mock_detector.process_frame.return_value = (
            frame,
            {
                "is_anomaly": True,
                "person_count": 6,
                "weapon_count": 0,
                "all_boxes": [{"class_name": "person"}] * 6,
                "anomaly_types": ["AGLOMERACION_DE_PERSONAS"],
            },
        )

        mock_cv2.imencode.return_value = (True, MagicMock(tobytes=MagicMock(return_value=b"\xff\xd8")))
        mock_cv2.FONT_HERSHEY_SIMPLEX = 0

        alert_mock = MagicMock()
        detector = LiveStreamDetector()
        detector.cap = mock_cap
        detector.is_running = True
        detector.detector = mock_detector
        detector.alert_callback = alert_mock
        detector.last_alert_time = time.time()

        detector.get_frame()

        alert_mock.assert_not_called()


class TestGetSummary:

    def test_summary_no_frames(self):
        detector = LiveStreamDetector()
        detector.start_time = time.time()
        summary = detector.get_summary()

        assert summary["stream_id"] == "main"
        assert summary["total_frames"] == 0
        assert summary["anomaly_frames"] == 0
        assert summary["anomaly_rate"] == 0
        assert summary["risk_level"] == "normal"
        assert summary["max_person_count"] == 0
        assert summary["max_weapon_count"] == 0

    def test_summary_risk_alto_by_weapon(self):
        detector = LiveStreamDetector()
        detector.start_time = time.time()
        detector.total_frames = 10
        detector.anomaly_frame_count = 2
        detector.max_weapon_count = 1

        summary = detector.get_summary()
        assert summary["risk_level"] == "alto"

    def test_summary_risk_alto_by_anomaly_rate(self):
        detector = LiveStreamDetector()
        detector.start_time = time.time()
        detector.total_frames = 10
        detector.anomaly_frame_count = 6

        summary = detector.get_summary()
        assert summary["risk_level"] == "alto"
        assert summary["anomaly_rate"] == 0.6

    def test_summary_risk_medio(self):
        detector = LiveStreamDetector()
        detector.start_time = time.time()
        detector.total_frames = 10
        detector.anomaly_frame_count = 3

        summary = detector.get_summary()
        assert summary["risk_level"] == "medio"
        assert summary["anomaly_rate"] == 0.3

    def test_summary_risk_bajo(self):
        detector = LiveStreamDetector()
        detector.start_time = time.time()
        detector.total_frames = 10
        detector.anomaly_frame_count = 1

        summary = detector.get_summary()
        assert summary["risk_level"] == "bajo"
        assert summary["anomaly_rate"] == 0.1

    def test_summary_with_class_counts(self):
        detector = LiveStreamDetector()
        detector.start_time = time.time()
        detector.accumulated_class_counts = {"person": 5, "knife": 1}
        detector.anomaly_types_set = {"ARMA_DETECTADA"}

        summary = detector.get_summary()
        assert summary["class_counts"] == {"person": 5, "knife": 1}
        assert "ARMA_DETECTADA" in summary["anomaly_types"]


class TestGetStatus:

    def test_status_default(self):
        detector = LiveStreamDetector()
        status = detector.get_status()

        assert status["is_running"] is False
        assert status["source"] == "0"
        assert status["fps"] == 0.0
        assert status["is_anomaly"] is False
        assert status["person_count"] == 0
        assert status["vehicle_count"] == 0
        assert status["anomaly_types"] == []
        assert status["model_name"] == "default"

    def test_status_after_results(self):
        detector = LiveStreamDetector()
        detector.current_results = {
            "is_anomaly": True,
            "person_count": 3,
            "vehicle_count": 1,
            "anomaly_types": ["AGLOMERACION_DE_PERSONAS"],
            "class_counts": {"person": 3, "car": 1},
        }
        detector.model_name = "yolov8s.pt"

        status = detector.get_status()
        assert status["is_anomaly"] is True
        assert status["person_count"] == 3
        assert status["vehicle_count"] == 1
        assert status["model_name"] == "yolov8s.pt"
        assert status["class_counts"] == {"person": 3, "car": 1}


class TestModuleFunctions:

    def test_create_stream(self):
        stream = create_stream("test1", source=0)
        assert isinstance(stream, LiveStreamDetector)
        assert stream.source == 0
        assert "test1" in _streams

    def test_create_stream_replaces_existing(self):
        s1 = create_stream("test1", source=0)
        s1.stop = MagicMock()
        s2 = create_stream("test1", source=1)
        assert s2.source == 1
        s1.stop.assert_called_once()

    def test_get_stream_exists(self):
        create_stream("test1", source=0)
        result = get_stream("test1")
        assert result is not None
        assert result.source == 0

    def test_get_stream_not_exists(self):
        result = get_stream("nonexistent")
        assert result is None

    def test_stop_stream_exists(self):
        create_stream("test1", source=0)
        result = stop_stream("test1")
        assert result is True
        assert "test1" not in _streams

    def test_stop_stream_not_exists(self):
        result = stop_stream("nonexistent")
        assert result is False

    def test_list_streams_empty(self):
        result = list_streams()
        assert result == {}

    def test_list_streams_multiple(self):
        create_stream("s1", source=0)
        create_stream("s2", source=1)
        result = list_streams()
        assert len(result) == 2
        assert "s1" in result
        assert "s2" in result

    @patch("src.detection.live_stream.cv2")
    def test_detect_cameras(self, mock_cv2):
        mock_cap_real = MagicMock()
        mock_cap_real.isOpened.return_value = True
        mock_cap_real.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cap_real.release = MagicMock()

        mock_cap_empty = MagicMock()
        mock_cap_empty.isOpened.return_value = False

        mock_cv2.VideoCapture.side_effect = [mock_cap_real, mock_cap_empty] + [mock_cap_empty] * 8
        mock_cv2.CAP_V4L2 = 200

        cameras = detect_cameras()
        assert len(cameras) == 1
        assert cameras[0]["index"] == 0
        assert cameras[0]["type"] == "usb"
        assert cameras[0]["name"] == "Camera 0"

    @patch("src.detection.live_stream.cv2")
    def test_detect_cameras_none_available(self, mock_cv2):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.CAP_V4L2 = 200

        cameras = detect_cameras()
        assert cameras == []
