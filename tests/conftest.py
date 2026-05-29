import pytest
import tempfile
import os
import importlib

@pytest.fixture
def test_db(monkeypatch):
    """Crea una base de datos temporal y redirige dinámicamente el módulo de producción"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        temp_db_path = f.name
    import src.storage.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", temp_db_path)
    db_module.init_database()
    
    yield temp_db_path
    if os.path.exists(temp_db_path):
        try:
            os.unlink(temp_db_path)
        except OSError:
            pass


@pytest.fixture
def test_video():
    """Create test video file"""
    import cv2
    import numpy as np
    
    # Create 30-frame test video
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video = cv2.VideoWriter('test_video.mp4', fourcc, 30.0, (640, 480))
    
    for i in range(30):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        video.write(frame)
    
    video.release()
    yield 'test_video.mp4'
    
    os.unlink('test_video.mp4')