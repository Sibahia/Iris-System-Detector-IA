import cv2
import numpy as np
import threading
from ultralytics import YOLO
from typing import Dict, Any, Optional
import os
import time

from .class_mapper import classify_classes


class YOLOImageDetector:
    def __init__(
        self,
        model_path: str,
        default_confidence: float = 0.5,
        crowd_threshold: int = 5,
        device: str = "cpu"
    ):
        self.default_confidence = default_confidence
        self.crowd_threshold = crowd_threshold
        self.device = device
        self.model_path = model_path

        self.model = YOLO(model_path)

        if device == "cpu":
            try:
                model_dir = os.path.dirname(model_path) or "."
                base_name = os.path.splitext(os.path.basename(model_path))[0]
                openvino_path = os.path.join(model_dir, f"{base_name}_openvino_model/")
                if not os.path.exists(openvino_path):
                    self.model.export(format="openvino")
                self.model = YOLO(openvino_path, task="detect")
            except Exception as e:
                print(f"Fallo OpenVINO (usando PyTorch de respaldo): {e}")
                self.model = YOLO(model_path)

        model_name_for_mapping = os.path.basename(self.model_path) if self.model_path else None
        mapping = classify_classes(self.model.names, model_name=model_name_for_mapping)
        self.WEAPON_CLASSES = mapping["weapon_ids"]
        self.PERSON_CLASSES = mapping["person_ids"]
        self.ARMED_PERSON_CLASSES = mapping["armed_person_ids"]
        self.BEHAVIOR_CATEGORIES = mapping["behavior_categories"]
        self.model_class_names = mapping["class_names"]
        self.model_class_categories = mapping["categories"]
        self.anomaly_map = mapping["anomaly_map"]

    def detect_and_analyze(self, frame: np.ndarray, conf_override: Optional[float] = None) -> Dict[str, Any]:
        current_conf = conf_override if conf_override is not None else self.default_confidence

        results = self.model(
            frame,
            conf=current_conf,
            device=self.device,
            verbose=False
        )

        detections = {
            "persons": [],
            "weapons": [],
            "other_objects": [],
            "all_boxes": [],
            "behaviors": {},
            "used_confidence": current_conf
        }

        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes

            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, xyxy)

                raw_name = self.model_class_names.get(cls, f"Clase_{cls}")
                category = self.model_class_categories.get(cls, "otro")

                detection = {
                    "class_id": cls,
                    "class_name": raw_name,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                    "category": category
                }

                detections["all_boxes"].append(detection)

                # Behavior categories
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

                # Weapons (includes armed_person, dual category)
                if cls in self.WEAPON_CLASSES:
                    detections["weapons"].append(detection)

                # Other
                if (cls not in self.PERSON_CLASSES and
                        cls not in self.WEAPON_CLASSES and
                        behavior_found is None):
                    detections["other_objects"].append(detection)

        return detections

    def evaluate_anomalies(self, detections: Dict[str, Any]) -> Dict[str, Any]:
        anomalies = {
            "is_anomaly": False,
            "anomaly_types": [],
            "anomaly_details": [],
            "risk_level": "normal"
        }

        person_count = len(detections["persons"])
        weapon_count = len(detections["weapons"])

        # Crowd detection
        if person_count >= self.crowd_threshold:
            anomalies["is_anomaly"] = True
            entry = self.anomaly_map.get("crowd", {})
            anomalies["anomaly_types"].append(entry.get("type", "AGLOMERACION_DE_PERSONAS"))
            anomalies["anomaly_details"].append(f"Multitud: {person_count} personas detectadas.")
            anomalies["risk_level"] = "alto" if person_count > self.crowd_threshold * 2 else entry.get("risk", "medio")

        # Weapon detection
        if weapon_count > 0:
            anomalies["is_anomaly"] = True
            weapon_names = list(set([w["class_name"] for w in detections["weapons"]]))
            entry = self.anomaly_map.get("weapon", {})
            anomalies["anomaly_types"].insert(0, entry.get("type", "ARMA_DETECTADA"))
            anomalies["anomaly_details"].insert(0, f"ELEMENTO PELIGROSO: {', '.join(weapon_names)}")
            anomalies["risk_level"] = entry.get("risk", "alto")

        # Behavior-based anomalies
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
                risk_order = {"normal": 0, "bajo": 1, "medio": 2, "alto": 3}
                if risk_order.get(risk, 0) > risk_order.get(anomalies["risk_level"], 0):
                    anomalies["risk_level"] = risk

        return anomalies

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

    def draw_annotations(self, frame: np.ndarray, detections: Dict[str, Any], anomalies: Dict[str, Any]) -> np.ndarray:
        frame_copy = frame.copy()
        h, w = frame_copy.shape[:2]

        for det in detections["all_boxes"]:
            x1, y1, x2, y2 = det["bbox"]
            class_name = det["class_name"]
            color = self.CLASS_COLORS.get(class_name, (255, 120, 0))

            is_weapon = det["class_id"] in self.WEAPON_CLASSES
            thickness = 3 if is_weapon else 2
            prefix = "ALERTA: " if is_weapon else ""

            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, thickness)
            label = f"{prefix}{class_name} {det['confidence']:.0%}"

            (t_w, t_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame_copy, (x1, y1 - 20), (x1 + t_w, y1), color, -1)
            cv2.putText(frame_copy, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Banner Superior
        overlay = frame_copy.copy()
        cv2.rectangle(overlay, (0, 0), (w, 50), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame_copy, 0.4, 0, frame_copy)

        if anomalies["is_anomaly"]:
            status_color = (0, 100, 200)
            status_text = "ANOMALIA DETECTADA"
        else:
            status_color = (0, 150, 0)
            status_text = "ESTADO NORMAL"

        confidence = detections['used_confidence']
        anomaly_str = ", ".join(anomalies["anomaly_types"]) if anomalies["anomaly_types"] else "Limpio"
        detail_text = f"Confianza: {confidence:.2f} | {anomaly_str}"

        cv2.putText(frame_copy, status_text, (20, 25), cv2.FONT_HERSHEY_DUPLEX, 0.6, status_color, 1)
        cv2.putText(frame_copy, detail_text, (20, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (220, 220, 220), 1)

        return frame_copy

    def process_image(self, input_path: str, output_path: str, conf_override: Optional[float] = None) -> Dict[str, Any]:
        start_time = time.time()
        frame = cv2.imread(input_path)
        if frame is None:
            raise ValueError(f"No se pudo leer la imagen en: {input_path}")

        detections = self.detect_and_analyze(frame, conf_override=conf_override)
        anomalies = self.evaluate_anomalies(detections)
        annotated_frame = self.draw_annotations(frame, detections, anomalies)

        cv2.imwrite(output_path, annotated_frame)
        processing_time = time.time() - start_time

        class_counts = {}
        for d in detections["all_boxes"]:
            name = d["class_name"]
            class_counts[name] = class_counts.get(name, 0) + 1

        return {
            "input_path": input_path,
            "output_path": output_path,
            "model_used": os.path.basename(self.model_path),
            "used_confidence": float(detections["used_confidence"]),
            "is_anomaly": bool(anomalies["is_anomaly"]),
            "risk_level": anomalies["risk_level"],
            "persons_count": len(detections["persons"]),
            "weapons_count": len(detections["weapons"]),
            "objects_count": len(detections["other_objects"]),
            "class_counts": class_counts,
            "anomaly_types": anomalies["anomaly_types"],
            "detected_classes": list(set([d["class_name"] for d in detections["all_boxes"]])),
            "processing_time_ms": int(processing_time * 1000)
        }


_image_detector_instance = None
_image_detector_model_path = None
_image_detector_lock = threading.Lock()


def get_image_detector(
    model_path: str,
    default_confidence: float = 0.5,
    crowd_threshold: int = 5,
    device: str = "cpu"
) -> YOLOImageDetector:
    global _image_detector_instance, _image_detector_model_path
    with _image_detector_lock:
        if _image_detector_instance is None or model_path != _image_detector_model_path:
            _image_detector_instance = YOLOImageDetector(
                model_path=model_path,
                default_confidence=default_confidence,
                crowd_threshold=crowd_threshold,
                device=device
            )
            _image_detector_model_path = model_path
        return _image_detector_instance
