"""
SQLite Database Layer for Anomaly Detection History
====================================================

Stores and retrieves video and image analysis history, enabling search 
and filtering of past anomaly detection results.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import json

# Database file path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'anomaly_history.db')


def get_connection():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
    return conn


def init_database():
    """Initialize database tables"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Create videos table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            frame_count INTEGER,
            anomaly_count INTEGER,
            anomaly_rate REAL,
            processing_time REAL,
            threshold_used REAL,
            output_video_path TEXT,
            original_video_path TEXT,
            avg_anomaly_score REAL,
            max_anomaly_score REAL
        )
    ''')
    
    # 2. Create anomaly_events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS anomaly_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            frame_number INTEGER,
            anomaly_score REAL,
            timestamp_in_video REAL,
            is_anomaly BOOLEAN,
            bounding_boxes TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        )
    ''')

    # 3. Create images table (Nueva tabla para analisis de imagenes fijas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_path TEXT NOT NULL,
            output_path TEXT NOT NULL,
            model_used TEXT NOT NULL,
            used_confidence REAL NOT NULL,
            is_anomaly BOOLEAN NOT NULL,
            risk_level TEXT NOT NULL CHECK(risk_level IN ('normal', 'medio', 'alto', 'critico')),
            persons_count INTEGER NOT NULL,
            weapons_count INTEGER NOT NULL,
            objects_count INTEGER NOT NULL,
            anomaly_types TEXT, -- Almacenado como JSON String
            detected_classes TEXT, -- Almacenado como JSON String
            processing_time_ms INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 4. Create streams table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS streams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stream_id TEXT NOT NULL,
            source TEXT NOT NULL,
            model_used TEXT,
            confidence REAL,
            crowd_threshold INTEGER,
            start_time TEXT,
            end_time TEXT,
            duration_seconds REAL,
            avg_fps REAL,
            total_frames INTEGER DEFAULT 0,
            anomaly_frames INTEGER DEFAULT 0,
            anomaly_rate REAL DEFAULT 0,
            max_person_count INTEGER DEFAULT 0,
            max_weapon_count INTEGER DEFAULT 0,
            class_counts TEXT,
            anomaly_types TEXT,
            risk_level TEXT DEFAULT 'normal'
        )
    ''')

    # 5. Migrate: add model_used column to videos if not exists
    try:
        cursor.execute("ALTER TABLE videos ADD COLUMN model_used TEXT")
        print("Added model_used column to videos")
    except sqlite3.OperationalError:
        pass

    # 6. Migrate: add class_counts column to images if not exists
    try:
        cursor.execute("ALTER TABLE images ADD COLUMN class_counts TEXT")
        print("Added class_counts column to images")
    except sqlite3.OperationalError:
        pass

    # 7. Migrate: add class_counts column to videos if not exists
    try:
        cursor.execute("ALTER TABLE videos ADD COLUMN class_counts TEXT")
        print("Added class_counts column to videos")
    except sqlite3.OperationalError:
        pass

    # 8. Migrate: add risk_level column to videos if not exists
    try:
        cursor.execute("ALTER TABLE videos ADD COLUMN risk_level TEXT DEFAULT 'normal'")
        print("Added risk_level column to videos")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
    print("Database initialized successfully!")


# =====================================================================
# VIDEO ANALYSIS METRIC PERSISTENCE
# =====================================================================

def save_video_analysis(
    filename: str,
    frame_count: int,
    anomaly_count: int,
    anomaly_rate: float,
    processing_time: float,
    threshold_used: float,
    anomaly_scores: List[float],
    anomaly_flags: List[bool],
    output_video_path: Optional[str] = None,
    original_video_path: Optional[str] = None,
    frame_bboxes: Optional[List[List[Dict]]] = None,
    model_name: Optional[str] = None,
    class_counts: Optional[Dict] = None,
    risk_level: Optional[str] = None
) -> int:
    """Save video analysis results to database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    avg_score = sum(anomaly_scores) / len(anomaly_scores) if anomaly_scores else 0
    max_score = max(anomaly_scores) if anomaly_scores else 0
    class_counts_json = json.dumps(class_counts) if class_counts else None
    
    cursor.execute('''
        INSERT INTO videos (
            filename, frame_count, anomaly_count, anomaly_rate,
            processing_time, threshold_used, output_video_path,
            original_video_path, avg_anomaly_score, max_anomaly_score,
            model_used, class_counts, risk_level
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        filename, frame_count, anomaly_count, anomaly_rate,
        processing_time, threshold_used, output_video_path,
        original_video_path, avg_score, max_score,
        model_name, class_counts_json, risk_level
    ))
    
    video_id = cursor.lastrowid
    if video_id is None:
        conn.close()
        raise RuntimeError("Failed to insert video record and retrieve its ID.")
    
    fps = 30
    for i, (score, is_anomaly) in enumerate(zip(anomaly_scores, anomaly_flags)):
        bboxes_json = None
        if frame_bboxes and i < len(frame_bboxes):
            bboxes_json = json.dumps(frame_bboxes[i])
        
        cursor.execute('''
            INSERT INTO anomaly_events (
                video_id, frame_number, anomaly_score,
                timestamp_in_video, is_anomaly, bounding_boxes
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (video_id, i, score, i / fps, is_anomaly, bboxes_json))
    
    conn.commit()
    conn.close()
    return video_id


def get_all_videos(limit: int = 50, offset: int = 0) -> List[Dict]:
    """Get all video analyses with pagination"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM videos ORDER BY upload_time DESC LIMIT ? OFFSET ?', (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_video_by_id(video_id: int) -> Optional[Dict]:
    """Get a specific video analysis by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM videos WHERE id = ?', (video_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    if isinstance(result.get("class_counts"), str):
        try:
            result["class_counts"] = json.loads(result["class_counts"])
        except Exception:
            result["class_counts"] = {}
    return result


def get_anomaly_events(video_id: int) -> List[Dict]:
    """Get all anomaly events for a video"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM anomaly_events WHERE video_id = ? ORDER BY frame_number', (video_id,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        event = dict(row)
        if event.get('bounding_boxes'):
            event['bounding_boxes'] = json.loads(event['bounding_boxes'])
        result.append(event)
    return result


def search_videos(
    filename: Optional[str] = None,
    min_anomaly_rate: Optional[float] = None,
    max_anomaly_rate: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """Search videos with various filters"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM videos WHERE 1=1'
    params = []
    
    if filename:
        query += ' AND filename LIKE ?'
        params.append(f'%{filename}%')
    if min_anomaly_rate is not None:
        query += ' AND anomaly_rate >= ?'
        params.append(min_anomaly_rate)
    if max_anomaly_rate is not None:
        query += ' AND anomaly_rate <= ?'
        params.append(max_anomaly_rate)
    if start_date:
        query += ' AND date(upload_time) >= date(?)'
        params.append(start_date)
    if end_date:
        query += ' AND date(upload_time) <= date(?)'
        params.append(end_date)
        
    query += ' ORDER BY upload_time DESC LIMIT ?'
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_video(video_id: int) -> bool:
    """Delete a video analysis and its events"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT output_video_path FROM videos WHERE id = ?', (video_id,))
    row = cursor.fetchone()
    
    if row and row['output_video_path']:
        video_path = row['output_video_path']
        if os.path.exists(video_path):
            os.remove(video_path)
            
    cursor.execute('DELETE FROM videos WHERE id = ?', (video_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    return deleted


# =====================================================================
# IMAGE ANALYSIS METRIC PERSISTENCE
# =====================================================================

def save_image_analysis(analysis_data: Dict[str, Any]) -> int:
    """
    Guarda el diccionario de salida de YOLOImageDetector.process_image en la base de datos.
    
    Returns:
        image_id: El ID del registro insertado.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    anomaly_types_json = json.dumps(analysis_data.get("anomaly_types", []))
    detected_classes_json = json.dumps(analysis_data.get("detected_classes", []))
    class_counts_json = json.dumps(analysis_data.get("class_counts", {}))
    
    cursor.execute('''
        INSERT INTO images (
            input_path, output_path, model_used, used_confidence,
            is_anomaly, risk_level, persons_count, weapons_count,
            objects_count, anomaly_types, detected_classes,
            class_counts, processing_time_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        analysis_data["input_path"],
        analysis_data["output_path"],
        analysis_data["model_used"],
        analysis_data["used_confidence"],
        1 if analysis_data["is_anomaly"] else 0,
        analysis_data["risk_level"],
        analysis_data["persons_count"],
        analysis_data["weapons_count"],
        analysis_data["objects_count"],
        anomaly_types_json,
        detected_classes_json,
        class_counts_json,
        analysis_data["processing_time_ms"]
    ))
    
    image_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    if image_id is None:
        raise RuntimeError("Failed to insert image record.")
        
    return image_id


def get_all_images(limit: int = 50, offset: int = 0) -> List[Dict]:
    """Recupera los registros de imagenes analizadas con paginacion"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM images ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        img_dict = dict(row)
        img_dict["anomaly_types"] = json.loads(img_dict["anomaly_types"]) if img_dict.get("anomaly_types") else []
        img_dict["detected_classes"] = json.loads(img_dict["detected_classes"]) if img_dict.get("detected_classes") else []
        img_dict["class_counts"] = json.loads(img_dict["class_counts"]) if img_dict.get("class_counts") else {}
        img_dict["is_anomaly"] = bool(img_dict["is_anomaly"])
        result.append(img_dict)
        
    return result


def get_image_by_id(image_id: int) -> Optional[Dict]:
    """Recupera el analisis de una imagen especifica por su ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM images WHERE id = ?', (image_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        img_dict = dict(row)
        img_dict["anomaly_types"] = json.loads(img_dict["anomaly_types"]) if img_dict.get("anomaly_types") else []
        img_dict["detected_classes"] = json.loads(img_dict["detected_classes"]) if img_dict.get("detected_classes") else []
        img_dict["class_counts"] = json.loads(img_dict["class_counts"]) if img_dict.get("class_counts") else {}
        img_dict["is_anomaly"] = bool(img_dict["is_anomaly"])
        return img_dict
        
    return None


def delete_image(image_id: int) -> bool:
    """Elimina el registro de una imagen y borra su archivo procesado del disco"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT output_path FROM images WHERE id = ?', (image_id,))
    row = cursor.fetchone()
    
    if row and row['output_path']:
        if os.path.exists(row['output_path']):
            os.remove(row['output_path'])
            
    cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    return deleted


# =====================================================================
# STREAM ANALYSIS PERSISTENCE
# =====================================================================

def save_stream_analysis(data: Dict[str, Any]) -> int:
    """Save stream analysis summary to database"""
    conn = get_connection()
    cursor = conn.cursor()

    class_counts_json = json.dumps(data.get("class_counts", {}))
    anomaly_types_json = json.dumps(data.get("anomaly_types", []))

    cursor.execute('''
        INSERT INTO streams (
            stream_id, source, model_used, confidence, crowd_threshold,
            start_time, end_time, duration_seconds, avg_fps,
            total_frames, anomaly_frames, anomaly_rate,
            max_person_count, max_weapon_count,
            class_counts, anomaly_types, risk_level
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get("stream_id", "main"),
        data.get("source", ""),
        data.get("model_used"),
        data.get("confidence"),
        data.get("crowd_threshold"),
        data.get("start_time"),
        data.get("end_time"),
        data.get("duration_seconds"),
        data.get("avg_fps"),
        data.get("total_frames", 0),
        data.get("anomaly_frames", 0),
        data.get("anomaly_rate", 0.0),
        data.get("max_person_count", 0),
        data.get("max_weapon_count", 0),
        class_counts_json,
        anomaly_types_json,
        data.get("risk_level", "normal"),
    ))

    stream_id = cursor.lastrowid
    conn.commit()
    conn.close()

    if stream_id is None:
        raise RuntimeError("Failed to insert stream record.")
    return stream_id


def get_all_streams(limit: int = 50, offset: int = 0) -> List[Dict]:
    """Get all stream analyses with pagination"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM streams ORDER BY start_time DESC LIMIT ? OFFSET ?', (limit, offset))
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        d = dict(row)
        if d.get("class_counts"):
            d["class_counts"] = json.loads(d["class_counts"])
        if d.get("anomaly_types"):
            d["anomaly_types"] = json.loads(d["anomaly_types"])
        result.append(d)
    return result


def get_stream_by_id(stream_db_id: int) -> Optional[Dict]:
    """Get a specific stream analysis by DB id"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM streams WHERE id = ?', (stream_db_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        if d.get("class_counts"):
            d["class_counts"] = json.loads(d["class_counts"])
        if d.get("anomaly_types"):
            d["anomaly_types"] = json.loads(d["anomaly_types"])
        return d
    return None


def delete_stream(stream_db_id: int) -> bool:
    """Delete a stream analysis record"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM streams WHERE id = ?', (stream_db_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# =====================================================================
# GLOBAL METRICS & INITIALIZATION
# =====================================================================

def get_statistics() -> Dict[str, Any]:
    """Get overall statistics for both videos and images"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Metricas de video (Protegidas con COALESCE por seguridad)
    cursor.execute('''
        SELECT 
            COUNT(*) as total_videos,
            COALESCE(SUM(frame_count), 0) as total_frames,
            COALESCE(AVG(anomaly_rate), 0.0) as avg_anomaly_rate,
            COALESCE(SUM(anomaly_count), 0) as total_anomalies,
            COALESCE(AVG(processing_time), 0.0) as avg_processing_time
        FROM videos
    ''')
    video_stats = dict(cursor.fetchone())
    
    # Metricas de imagenes (Protegidas con COALESCE)
    cursor.execute('''
        SELECT 
            COUNT(*) as total_images,
            COALESCE(SUM(CASE WHEN is_anomaly = 1 THEN 1 ELSE 0 END), 0) as total_anomalous_images,
            COALESCE(SUM(weapons_count), 0) as total_weapons_detected_imgs
        FROM images
    ''')
    image_stats = dict(cursor.fetchone())
    
    conn.close()
    
    return {**video_stats, **image_stats}


# Initialize database on import
init_database()