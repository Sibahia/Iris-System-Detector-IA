import pytest
from src.storage.database import (
    init_database,
    save_video_analysis,
    get_video_by_id,
    get_all_videos,
    delete_video
)

class TestDatabase:
    
    def test_database_initialization(self, test_db):
        """Test database creates tables"""
        import sqlite3
        
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        
        # Check if videos table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='videos'"
        )
        assert cursor.fetchone() is not None
    
    def test_save_video_analysis(self, test_db):
        """Test saving video analysis results"""
        video_id = save_video_analysis(
            filename="test.mp4",
            frame_count=100,
            anomaly_count=10,
            anomaly_rate=0.1,
            processing_time=5.0,
            threshold_used=5,
            anomaly_scores=[0.0] * 100,
            anomaly_flags=[False] * 100,
            output_video_path="/videos/test.mp4",
            db_path=test_db
        )
        
        assert video_id > 0
    
    def test_get_video_by_id(self, test_db):
        """Test retrieving video by ID"""
        # Save video first
        video_id = save_video_analysis(
            filename="test.mp4",
            frame_count=100,
            anomaly_count=10,
            anomaly_rate=0.1,
            processing_time=5.0,
            threshold_used=5,
            anomaly_scores=[0.0] * 100,
            anomaly_flags=[False] * 100,
            output_video_path="/videos/test.mp4",
            db_path=test_db
        )
        
        # Retrieve video
        video = get_video_by_id(video_id, db_path=test_db)
        
        assert video is not None
        assert video['id'] == video_id
        assert video['filename'] == "test.mp4"
        assert video['frame_count'] == 100
    
    def test_get_all_videos(self, test_db):
        """Test retrieving all videos"""
        # Save multiple videos
        for i in range(3):
            save_video_analysis(
                filename=f"test_{i}.mp4",
                frame_count=100,
                anomaly_count=10,
                anomaly_rate=0.1,
                processing_time=5.0,
                threshold_used=5,
                anomaly_scores=[0.0] * 100,
                anomaly_flags=[False] * 100,
                output_video_path=f"/videos/test_{i}.mp4",
                db_path=test_db
            )
        
        videos = get_all_videos(db_path=test_db)
        assert len(videos) == 3
    
    def test_delete_video(self, test_db):
        """Test deleting video"""
        # Save video
        video_id = save_video_analysis(
            filename="test.mp4",
            frame_count=100,
            anomaly_count=10,
            anomaly_rate=0.1,
            processing_time=5.0,
            threshold_used=5,
            anomaly_scores=[0.0] * 100,
            anomaly_flags=[False] * 100,
            output_video_path="/videos/test.mp4",
            db_path=test_db
        )
        
        # Delete video
        result = delete_video(video_id, db_path=test_db)
        assert result == True
        
        # Verify deletion
        video = get_video_by_id(video_id, db_path=test_db)
        assert video is None