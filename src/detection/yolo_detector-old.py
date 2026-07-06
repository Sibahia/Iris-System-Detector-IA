import cv2
import numpy as np
import imageio
from ultralytics import YOLO
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from dotenv import load_dotenv
import time
import os

load_dotenv()

class VideoWriter:

    def __init__(self, output_path: str, fps: float, width: int, height: int):
        self.output_path = output_path
        self.fps = fps
        self.width = width
        self.height = height
        self.writer = imageio.get_writer(
            output_path, fps=fps, codec="libx264", pixelformat="yuv420p"
        )
        self.frame_count = 0

    def write(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.writer.append_data(frame_rgb)
        self.frame_count += 1

    def release(self):
        self.writer.close()


class YOLOAnomalyDetector:

    PERSON_CLASS = 1
    VEHICLE_CLASSES = []
    WEAPON_CLASSES = [0, 2, 3, 4, 5, 6, 7]
    
    CLASS_NAMES_MAP = {
        0: "weapon",
        1: "person",
        2: "rifle",
        3: "pistol",
        4: "gun",
        5: "knife",
        6: "guns",
        7: "Knife"
    }

    def __init__(
        self,
        model_size: str = "s",
        confidence_threshold: float = 0.5,
        crowd_threshold: int = 5,
        loiter_threshold_seconds: float = 10.0,
        device: str = "cpu",
    ):
        self.confidence_threshold = confidence_threshold
        self.crowd_threshold = crowd_threshold
        self.loiter_threshold = loiter_threshold_seconds
        self.device = device

        model_name = os.getenv("MODEL_NAME", f"yolo11{model_size}.pt")
        print(f"Loading YOLO model: {model_name}")
        self.model = YOLO(model_name)

        if device == "cpu":
            try:
                model_dir = os.path.dirname(model_name) or "."
                base_name = os.path.splitext(os.path.basename(model_name))[0]
                openvino_path = os.path.join(model_dir, f"{base_name}_openvino_model/")
                if not os.path.exists(openvino_path):
                    print(
                        "🚀 Exporting model to OpenVINO for 2-3x CPU speedup... (This takes ~1 min once)"
                    )
                    self.model.export(format="openvino")
                    print("✅ Export complete!")

                print(f"Loading OpenVINO model: {openvino_path}")
                self.model = YOLO(openvino_path, task="detect")
                print("✅ OpenVINO optimized model loaded!")
            except Exception as e:
                print(f"⚠️ OpenVINO export failed (using PyTorch fallback): {e}")
                self.model = YOLO(model_name)
        else:
            print("✅ YOLO model loaded!")

        self.person_tracks: Dict[int, List[Tuple[float, float, float]]] = defaultdict(
            list
        )
        self.object_velocities: Dict[int, float] = {}
        self.frame_count = 0

    def detect_objects(self, frame: np.ndarray) -> Dict[str, Any]:
        results = self.model.track(
            frame,
            conf=self.confidence_threshold,
            persist=True,
            verbose=False,
            tracker="bytetrack.yaml",
        )

        detections = {
            "persons": [],
            "vehicles": [],
            "weapons": [],
            "other_objects": [],
            "all_boxes": [],
        }

        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes

            for i, box in enumerate(boxes):
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].cpu().numpy()
                id = int(box.id[0]) if box.id is not None else -1
                x1, y1, x2, y2 = map(int, xyxy)

                resolved_name = "unknown"
                if self.model.names and cls in self.model.names:
                    resolved_name = self.model.names[cls]
                else:
                    resolved_name = self.CLASS_NAMES_MAP.get(cls, f"Class {cls}")

                detection = {
                    "class_id": cls,
                    "class_name": resolved_name,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                    "id": id,
                }

                detections["all_boxes"].append(detection)

                if cls == self.PERSON_CLASS:
                    detections["persons"].append(detection)
                elif cls in self.VEHICLE_CLASSES:
                    detections["vehicles"].append(detection)
                elif cls in self.WEAPON_CLASSES:
                    detections["weapons"].append(detection)
                else:
                    detections["other_objects"].append(detection)

        return detections

    def check_anomalies(
        self, detections: Dict[str, Any], fps: float = 30.0
    ) -> Dict[str, Any]:
        anomalies = {
            "is_anomaly": False,
            "anomaly_types": [],
            "anomaly_details": [],
            "risk_level": "normal",
        }

        person_count = len(detections["persons"])
        vehicle_count = len(detections["vehicles"])

        if person_count >= self.crowd_threshold:
            anomalies["is_anomaly"] = True
            anomalies["anomaly_types"].append("CROWD_GATHERING")
            anomalies["anomaly_details"].append(
                f"Crowd detected: {person_count} people (threshold: {self.crowd_threshold})"
            )
            anomalies["risk_level"] = (
                "high" if person_count > self.crowd_threshold * 2 else "medium"
            )

        if person_count >= 2:
            close_pairs = self._check_proximity(
                detections["persons"], proximity_threshold=150
            )
            if close_pairs > 0:
                anomalies["is_anomaly"] = True
                anomalies["anomaly_types"].append("POTENTIAL_CONFLICT")
                anomalies["anomaly_details"].append(
                    f"Warning: {close_pairs} people in close proximity - possible altercation"
                )
                anomalies["risk_level"] = "high"

        if vehicle_count >= 3:
            anomalies["is_anomaly"] = True
            anomalies["anomaly_types"].append("TRAFFIC_CONGESTION")
            anomalies["anomaly_details"].append(
                f"Multiple vehicles detected: {vehicle_count}"
            )
            if anomalies["risk_level"] == "normal":
                anomalies["risk_level"] = "low"

        if len(detections["weapons"]) > 0:
            anomalies["is_anomaly"] = True
            weapon_names = [w["class_name"] for w in detections["weapons"]]
            anomalies["anomaly_types"].append("WEAPON_DETECTED")
            anomalies["anomaly_details"].insert(
                0, f"⚠ WEAPON DETECTED: {', '.join(weapon_names)}"
            )
            anomalies["risk_level"] = "critical"

        if vehicle_count > 0 and person_count >= 2:
            anomalies["is_anomaly"] = True
            if "CROWD_GATHERING" not in anomalies["anomaly_types"]:
                anomalies["anomaly_types"].append("ACTIVITY_DETECTED")
                anomalies["anomaly_details"].append(
                    f"Activity: {person_count} people near {vehicle_count} vehicle(s)"
                )

        self.frame_count += 1
        return anomalies

    def _check_proximity(
        self, persons: List[Dict], proximity_threshold: int = 150
    ) -> int:
        close_count = 0

        for i, p1 in enumerate(persons):
            for j, p2 in enumerate(persons):
                if i >= j:
                    continue

                c1 = p1["center"]
                c2 = p2["center"]
                distance = np.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2)

                if distance < proximity_threshold:
                    close_count += 1

        return close_count

    def _check_velocity(self, persons: List[Dict], fps: float) -> int:
        running_count = 0
        current_ids = set()

        for person in persons:
            track_id = person.get("id", -1)
            if track_id == -1:
                continue

            current_ids.add(track_id)
            center = person["center"]

            if track_id not in self.person_tracks:
                self.person_tracks[track_id] = []

            self.person_tracks[track_id].append(center)

            if len(self.person_tracks[track_id]) > 10:
                self.person_tracks[track_id].pop(0)

            history = self.person_tracks[track_id]
            if len(history) >= 3:
                start_pos = history[0]
                end_pos = history[-1]
                distance = np.sqrt(
                    (start_pos[0] - end_pos[0]) ** 2 + (start_pos[1] - end_pos[1]) ** 2
                )

                speed_per_step = distance / (len(history) - 1)

                if speed_per_step > 25:
                    running_count += 1
                    self.object_velocities[track_id] = speed_per_step

        for tid in list(self.person_tracks.keys()):
            if tid not in current_ids:
                del self.person_tracks[tid]
                if tid in self.object_velocities:
                    del self.object_velocities[tid]

        return running_count

    def process_frame(
        self, frame: np.ndarray, draw_detections: bool = True, fps: float = 30.0
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        detections = self.detect_objects(frame)
        anomalies = self.check_anomalies(detections, fps)

        results = {
            **detections,
            **anomalies,
            "person_count": len(detections["persons"]),
            "vehicle_count": len(detections["vehicles"]),
        }

        if draw_detections:
            frame = self.draw_annotations(frame, detections, anomalies)

        return frame, results

    def draw_annotations(
        self, frame: np.ndarray, detections: Dict[str, Any], anomalies: Dict[str, Any]
    ) -> np.ndarray:
        frame_copy = frame.copy()
        overlay = frame.copy()
        h, w = frame_copy.shape[:2]

        person_color = (0, 0, 255) if anomalies["is_anomaly"] else (0, 255, 0)
        for det in detections["persons"]:
            x1, y1, x2, y2 = det["bbox"]
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), person_color, 2)

            label = f"Person {det['confidence']:.0%}"
            if "id" in det and det["id"] != -1:
                label += f" ID:{det['id']}"

            (t_w, t_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame_copy, (x1, y1 - 20), (x1 + t_w, y1), person_color, -1)
            cv2.putText(
                frame_copy,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

        for det in detections["vehicles"]:
            x1, y1, x2, y2 = det["bbox"]
            cv2.rectangle(
                frame_copy, (x1, y1), (x2, y2), (255, 165, 0), 2
            )
            label = f"{det['class_name']}"

            (t_w, t_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame_copy, (x1, y1 - 20), (x1 + t_w, y1), (255, 165, 0), -1)
            cv2.putText(
                frame_copy,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

        for det in detections.get("weapons", []):
            x1, y1, x2, y2 = det["bbox"]
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 0, 255), 3)
            label = f"⚠ {det['class_name']} {det['confidence']:.0%}"

            (t_w, t_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame_copy, (x1, y1 - 25), (x1 + t_w, y1), (0, 0, 255), -1)
            cv2.putText(
                frame_copy,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        pad = 20
        bar_height = 50

        if anomalies["is_anomaly"]:
            status_color = (0, 0, 200)
            status_text = "⚠ ANOMALY DETECTED"
            detail_text = ", ".join(anomalies["anomaly_types"])
        else:
            status_color = (0, 150, 0)
            status_text = "● NORMAL"
            detail_text = "Monitoring..."

        cv2.rectangle(overlay, (0, 0), (w, bar_height), (0, 0, 0), -1)
        camera_alpha = 0.6
        cv2.addWeighted(
            overlay, camera_alpha, frame_copy, 1 - camera_alpha, 0, frame_copy
        )

        cv2.putText(
            frame_copy,
            status_text,
            (pad, 28),
            cv2.FONT_HERSHEY_DUPLEX,
            0.7,
            status_color if not anomalies["is_anomaly"] else (0, 0, 255),
            1,
        )

        cv2.putText(
            frame_copy,
            detail_text,
            (pad, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (220, 220, 220),
            1,
        )

        stats_text = (
            f"P: {len(detections['persons'])} | V: {len(detections['vehicles'])}"
        )

        (tw, th), _ = cv2.getTextSize(stats_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.putText(
            frame_copy,
            stats_text,
            (w - tw - pad, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1,
        )

        if anomalies["is_anomaly"] and anomalies["anomaly_details"]:
            overlay_bottom = frame_copy.copy()
            cv2.rectangle(
                overlay_bottom, (0, h - 40), (w, h), (0, 0, 150), -1
            )
            cv2.addWeighted(overlay_bottom, 0.6, frame_copy, 0.4, 0, frame_copy)

            detail_msg = anomalies["anomaly_details"][0]
            cv2.putText(
                frame_copy,
                detail_msg,
                (pad, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
            )

        return frame_copy

    def process_video(
        self,
        input_path: str,
        output_path: str,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {input_path}")

        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        out = VideoWriter(output_path, fps, width, height)

        stats = {
            "total_frames": 0,
            "anomaly_frames": 0,
            "max_people": 0,
            "max_vehicles": 0,
            "anomaly_types_count": defaultdict(int),
            "frame_results": [],
        }

        start_time = time.time()
        frame_num = 0

        while True:
            if progress_callback and frame_num % 10 == 0:
                progress = int((frame_num / total_frames) * 100)
                progress_callback(progress)

            ret, frame = cap.read()
            if not ret:
                break

            if frame_num % 3 == 0:
                annotated_frame, results = self.process_frame(
                    frame, draw_detections=True, fps=fps
                )
                last_results = results
                last_annotated = annotated_frame
            else:
                if "last_results" in locals():
                    results = last_results
                    annotated_frame = self.draw_annotations(frame, results, results)
                else:
                    annotated_frame, results = self.process_frame(
                        frame, draw_detections=True, fps=fps
                    )
                    last_results = results

            stats["total_frames"] += 1
            if results["is_anomaly"]:
                stats["anomaly_frames"] += 1
                for atype in results["anomaly_types"]:
                    stats["anomaly_types_count"][atype] += 1

            stats["max_people"] = max(stats["max_people"], results["person_count"])
            stats["max_vehicles"] = max(stats["max_vehicles"], results["vehicle_count"])

            stats["frame_results"].append(
                {
                    "frame": frame_num,
                    "is_anomaly": results["is_anomaly"],
                    "persons": results["person_count"],
                    "vehicles": results["vehicle_count"],
                }
            )

            out.write(annotated_frame)
            frame_num += 1

        cap.release()
        out.release()

        stats["processing_time"] = time.time() - start_time
        stats["anomaly_rate"] = (
            stats["anomaly_frames"] / stats["total_frames"]
            if stats["total_frames"] > 0
            else 0
        )
        stats["anomaly_types_count"] = dict(stats["anomaly_types_count"])

        return stats


_detector_instance = None


def get_yolo_detector(
    model_size: str = "s",
    device: str = "cpu",
    confidence_threshold: float = 0.5,
    crowd_threshold: int = 5,
    loiter_threshold_seconds: float = 10.0,
) -> YOLOAnomalyDetector:
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = YOLOAnomalyDetector(
            model_size=model_size,
            device=device,
            confidence_threshold=confidence_threshold,
            crowd_threshold=crowd_threshold,
            loiter_threshold_seconds=loiter_threshold_seconds,
        )
    return _detector_instance