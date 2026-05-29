import pytest
import tempfile
import os

@pytest.fixture
def test_db():
    """Create temporary test database"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    # Initialize test database
    from src.storage.database import init_database
    init_database(db_path)
    
    yield db_path
    
    # Cleanup
    os.unlink(db_path)


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