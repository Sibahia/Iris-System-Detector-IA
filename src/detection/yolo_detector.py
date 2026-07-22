import cv2
import numpy as np
import imageio
import threading
from ultralytics import YOLO
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from dotenv import load_dotenv
import time
import os

from .class_mapper import classify_classes

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

    def __init__(
        self,
        model_size: str = "s",
        model_path: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        crowd_threshold: int = 5,
        loiter_threshold_seconds: float = 10.0,
        device: str = "cpu",
    ):
        env_conf = os.getenv("CONFIDENCE_THRESHOLD")
        if confidence_threshold is not None:
            self.confidence_threshold = confidence_threshold
        elif env_conf is not None:
            try:
                self.confidence_threshold = float(env_conf)
            except ValueError:
                self.confidence_threshold = 0.5
        else:
            self.confidence_threshold = 0.5

        self.crowd_threshold = crowd_threshold
        self.loiter_threshold = loiter_threshold_seconds
        self.device = device
        self.model_path = model_path

        model_name = model_path or os.getenv("MODEL_NAME", f"yolo11{model_size}.pt")
        self.model = YOLO(model_name)

        if device == "cpu":
            try:
                model_dir = os.path.dirname(model_name) or "."
                base_name = os.path.splitext(os.path.basename(model_name))[0]
                openvino_path = os.path.join(model_dir, f"{base_name}_openvino_model/")
                if not os.path.exists(openvino_path):
                    self.model.export(format="openvino")
                self.model = YOLO(openvino_path, task="detect")
            except Exception as e:
                print(f"Falló exportación OpenVINO (usando PyTorch): {e}")
                self.model = YOLO(model_name)

        model_name_for_mapping = os.path.basename(self.model_path) if self.model_path else None
        mapping = classify_classes(self.model.names, model_name=model_name_for_mapping)
        self.WEAPON_CLASSES = mapping["weapon_ids"]
        self.PERSON_CLASSES = mapping["person_ids"]
        self.ARMED_PERSON_CLASSES = mapping["armed_person_ids"]
        self.BEHAVIOR_CATEGORIES = mapping["behavior_categories"]
        self.model_class_names = mapping["class_names"]
        self.anomaly_map = mapping["anomaly_map"]

        self.person_tracks: Dict[int, List[Tuple[float, float, float]]] = defaultdict(list)
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
            "weapons": [],
            "other_objects": [],
            "all_boxes": [],
            "behaviors": {},
        }

        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes

            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].cpu().numpy()
                id = int(box.id[0]) if box.id is not None else -1
                x1, y1, x2, y2 = map(int, xyxy)

                if self.model.names and cls in self.model.names:
                    resolved_name = self.model.names[cls]
                else:
                    resolved_name = self.model_class_names.get(cls, f"Clase {cls}")

                detection = {
                    "class_id": cls,
                    "class_name": resolved_name,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                    "id": id,
                }

                detections["all_boxes"].append(detection)

                # Behavior categories (e.g. assault, fight, kidnap)
                behavior_found = None
                for cat_name, cat_ids in self.BEHAVIOR_CATEGORIES.items():
                    if cls in cat_ids:
                        if cat_name not in detections["behaviors"]:
                            detections["behaviors"][cat_name] = []
                        detections["behaviors"][cat_name].append(detection)
                        behavior_found = cat_name
                        break

                # Persons (includes armed_person)
                if cls in self.PERSON_CLASSES:
                    detections["persons"].append(detection)

                # Weapons (includes armed_person, so they go to BOTH lists)
                if cls in self.WEAPON_CLASSES:
                    detections["weapons"].append(detection)

                # Other: not person, not weapon, not behavior
                if (cls not in self.PERSON_CLASSES and
                        cls not in self.WEAPON_CLASSES and
                        behavior_found is None):
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
        weapon_count = len(detections["weapons"])

        # 1. Crowd detection
        if person_count >= self.crowd_threshold:
            anomalies["is_anomaly"] = True
            entry = self.anomaly_map.get("crowd", {})
            anomalies["anomaly_types"].append(entry.get("type", "AGLOMERACION_DE_PERSONAS"))
            anomalies["anomaly_details"].append(
                f"Multitud detectada: {person_count} personas (límite: {self.crowd_threshold})"
            )
            anomalies["risk_level"] = (
                "alto" if person_count > self.crowd_threshold * 2 else entry.get("risk", "medio")
            )

        # 2. Proximity detection
        if person_count >= 2:
            close_pairs = self._check_proximity(
                detections["persons"], proximity_threshold=150
            )
            if close_pairs > 0:
                anomalies["is_anomaly"] = True
                entry = self.anomaly_map.get("proximity", {})
                anomalies["anomaly_types"].append(entry.get("type", "ALTERCADO_POTENCIAL"))
                anomalies["anomaly_details"].append(
                    f"Advertencia: {close_pairs} personas muy próximas"
                )
                anomalies["risk_level"] = entry.get("risk", "alto")

        # 3. Weapon detection (alto - overrides everything)
        if weapon_count > 0:
            anomalies["is_anomaly"] = True
            weapon_names = [w["class_name"].upper() for w in detections["weapons"]]
            entry = self.anomaly_map.get("weapon", {})
            anomalies["anomaly_types"].insert(0, entry.get("type", "ARMA_DETECTADA"))
            anomalies["anomaly_details"].insert(
                0, f"ARMA DETECTADA: {', '.join(weapon_names)}"
            )
            anomalies["risk_level"] = entry.get("risk", "alto")

        # 4. Behavior-based anomalies (from suspicious.pt etc.)
        for cat_name, cat_detections in detections.get("behaviors", {}).items():
            if not cat_detections:
                continue
            entry = self.anomaly_map.get(cat_name)
            if entry:
                anomaly_type = entry["type"]
                behavior_names = [d["class_name"].upper() for d in cat_detections]
                risk = entry.get("risk", "alto")
                anomalies["is_anomaly"] = True
                if anomaly_type not in anomalies["anomaly_types"]:
                    anomalies["anomaly_types"].append(anomaly_type)
                    anomalies["anomaly_details"].append(
                        f"{anomaly_type}: {', '.join(behavior_names)}"
                    )
                # Upgrade risk if behavior risk is higher
                risk_order = {"normal": 0, "bajo": 1, "medio": 2, "alto": 3}
                if risk_order.get(risk, 0) > risk_order.get(anomalies["risk_level"], 0):
                    anomalies["risk_level"] = risk

        # 5. Suspicious combo (weapons + people)
        if weapon_count > 0 and person_count >= 2:
            if "ACTIVIDAD_SOSPECHOSA" not in anomalies["anomaly_types"]:
                anomalies["anomaly_types"].append("ACTIVIDAD_SOSPECHOSA")
                anomalies["anomaly_details"].append(
                    f"Actividad: {person_count} personas cerca de arma(s)"
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
            "weapon_count": len(detections["weapons"]),
        }

        if draw_detections:
            frame = self.draw_annotations(frame, detections, anomalies)

        return frame, results

    CLASS_COLORS = {
        "weapon": (0, 0, 255),
        "person": (0, 200, 0),
        "rifle": (0, 165, 255),
        "pistol": (255, 0, 200),
        "gun": (0, 0, 200),
        "guns": (0, 0, 200),
        "knife": (0, 255, 255),
        "Knife": (0, 255, 255),
        "police": (255, 150, 0),
        "prisoner": (0, 140, 255),
        "armed_person": (180, 0, 180),
        "behavior_assault": (255, 0, 100),
        "behavior_fight": (255, 100, 0),
        "behavior_kidnap": (100, 0, 255),
        "behavior_terror": (0, 0, 180),
        "behavior_robbery": (255, 165, 0),
    }

    def draw_annotations(
        self, frame: np.ndarray, detections: Dict[str, Any], anomalies: Dict[str, Any]
    ) -> np.ndarray:
        frame_copy = frame.copy()
        overlay = frame.copy()
        h, w = frame_copy.shape[:2]

        drawn_ids = set()
        for det in detections["all_boxes"]:
            det_id = id(det)
            if det_id in drawn_ids:
                continue
            drawn_ids.add(det_id)

            x1, y1, x2, y2 = det["bbox"]
            class_name = det["class_name"]
            color = self.CLASS_COLORS.get(class_name, (255, 120, 0))

            is_weapon = det["class_id"] in self.WEAPON_CLASSES
            thickness = 3 if is_weapon else 2
            prefix = "! " if is_weapon else ""

            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, thickness)
            label = f"{prefix}{class_name} {det['confidence']:.0%}"
            if "id" in det and det["id"] != -1:
                label += f" ID:{det['id']}"

            (t_w, t_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame_copy, (x1, y1 - 20), (x1 + t_w, y1), color, -1)
            cv2.putText(
                frame_copy, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
            )

        # Top status bar
        pad = 20
        bar_height = 50

        if anomalies["is_anomaly"]:
            status_color = (0, 100, 200)
            status_text = "ANOMALIA DETECTADA"
            detail_text = ", ".join(anomalies["anomaly_types"])
        else:
            status_color = (0, 150, 0)
            status_text = "NORMAL"
            detail_text = "Monitoreando..."

        cv2.rectangle(overlay, (0, 0), (w, bar_height), (0, 0, 0), -1)
        camera_alpha = 0.6
        cv2.addWeighted(overlay, camera_alpha, frame_copy, 1 - camera_alpha, 0, frame_copy)

        cv2.putText(
            frame_copy, status_text, (pad, 28), cv2.FONT_HERSHEY_DUPLEX, 0.7,
            status_color, 1
        )

        cv2.putText(
            frame_copy, detail_text, (pad, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1
        )

        stats_text = (
            f"P: {len(detections['persons'])} | A: {len(detections['weapons'])}"
        )

        (tw, th), _ = cv2.getTextSize(stats_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.putText(
            frame_copy, stats_text, (w - tw - pad, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1
        )

        # Bottom detail bar
        if anomalies["is_anomaly"] and anomalies["anomaly_details"]:
            overlay_bottom = frame_copy.copy()
            cv2.rectangle(overlay_bottom, (0, h - 40), (w, h), (0, 0, 180), -1)
            cv2.addWeighted(overlay_bottom, 0.7, frame_copy, 0.3, 0, frame_copy)

            detail_msg = anomalies["anomaly_details"][0]
            cv2.putText(
                frame_copy, detail_msg, (pad, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1
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
            raise ValueError(f"No se pudo abrir el video: {input_path}")

        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        out = VideoWriter(output_path, fps, width, height)

        stats = {
            "total_frames": 0,
            "anomaly_frames": 0,
            "max_people": 0,
            "max_weapons": 0,
            "anomaly_types_count": defaultdict(int),
            "frame_results": [],
            "class_counts": {},
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
            stats["max_weapons"] = max(stats["max_weapons"], results["weapon_count"])

            if frame_num % 3 == 0 and "all_boxes" in results:
                frame_classes = set(det["class_name"] for det in results["all_boxes"])
                for name in frame_classes:
                    stats["class_counts"][name] = stats["class_counts"].get(name, 0) + 1

            stats["frame_results"].append(
                {
                    "frame": frame_num,
                    "is_anomaly": results["is_anomaly"],
                    "persons": results["person_count"],
                    "weapons": results["weapon_count"],
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
        model_basename = os.path.basename(self.model_path) if self.model_path else None
        stats["model_name"] = model_basename or os.getenv("MODEL_NAME", "default")

        return stats


_detector_instance = None
_detector_model_path = None
_detector_lock = threading.Lock()


def get_yolo_detector(
    model_size: str = "s",
    model_path: Optional[str] = None,
    device: str = "cpu",
    confidence_threshold: Optional[float] = None,
    crowd_threshold: int = 5,
    loiter_threshold_seconds: float = 10.0,
) -> YOLOAnomalyDetector:
    global _detector_instance, _detector_model_path
    with _detector_lock:
        if _detector_instance is None or model_path != _detector_model_path:
            _detector_instance = YOLOAnomalyDetector(
                model_size=model_size,
                model_path=model_path,
                device=device,
                confidence_threshold=confidence_threshold,
                crowd_threshold=crowd_threshold,
                loiter_threshold_seconds=loiter_threshold_seconds,
            )
            _detector_model_path = model_path
        return _detector_instance
