import cv2
import numpy as np
from ultralytics import YOLO
from typing import Dict, Any, Optional
import os
import time

class YOLOImageDetector:
    def __init__(
        self,
        model_path: str,
        default_confidence: float = 0.5,
        crowd_threshold: int = 5,
        device: str = "cpu"
    ):
        """
        Detector dinamico de anomalias en imagenes fijas.
        Soporta variaciones dinamicas de confianza (0.1 - 0.8) por cada llamada.
        """
        self.default_confidence = default_confidence
        self.crowd_threshold = crowd_threshold
        self.device = device
        self.model_path = model_path

        print(f"Cargando modelo dinamico para imagenes: {model_path}")
        self.model = YOLO(model_path)
        
        # Optimizacion OpenVINO para CPU
        if device == "cpu":
            try:
                base_name = os.path.splitext(os.path.basename(model_path))[0]
                openvino_path = f"{base_name}_openvino_model/"
                if not os.path.exists(openvino_path):
                    print(f"Optimizando {model_path} con OpenVINO...")
                    self.model.export(format="openvino")
                self.model = YOLO(openvino_path, task="detect")
                print("Modelo optimizado con OpenVINO cargado exitosamente")
            except Exception as e:
                print(f"Fallo OpenVINO (usando PyTorch de respaldo): {e}")
                self.model = YOLO(model_path)

        self.model_classes = self.model.names if self.model.names else {}

    def _resolve_class_category(self, class_id: int, class_name: str) -> str:
        """Determina la categoria analizando el nombre de la clase devuelta por el modelo."""
        name_lower = class_name.lower()
        if "person" in name_lower or "persona" in name_lower:
            return "persona"
        elif any(w in name_lower for w in ["weapon", "arma", "gun", "pistol", "rifle", "knife", "cuchillo", "fuego"]):
            return "arma"
        else:
            return "objeto_general"

    def detect_and_analyze(self, frame: np.ndarray, conf_override: Optional[float] = None) -> Dict[str, Any]:
        """
        Realiza la inferencia utilizando un nivel de confianza dinamico si se solicita.
        """
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
            "used_confidence": current_conf
        }

        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes

            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, xyxy)

                raw_name = self.model_classes.get(cls, f"Clase_{cls}")
                category = self._resolve_class_category(cls, raw_name)

                detection = {
                    "class_id": cls,
                    "class_name": raw_name.upper(),
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                    "category": category
                }

                detections["all_boxes"].append(detection)

                if category == "persona":
                    detections["persons"].append(detection)
                elif category == "arma":
                    detections["weapons"].append(detection)
                else:
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

        if person_count >= self.crowd_threshold:
            anomalies["is_anomaly"] = True
            anomalies["anomaly_types"].append("AGLOMERACION_DE_PERSONAS")
            anomalies["anomaly_details"].append(f"Multitud: {person_count} personas detectadas.")
            anomalies["risk_level"] = "alto" if person_count > self.crowd_threshold * 2 else "medio"

        if weapon_count > 0:
            anomalies["is_anomaly"] = True
            weapon_names = list(set([w["class_name"] for w in detections["weapons"]]))
            anomalies["anomaly_types"].insert(0, "ARMA_DETECTADA")
            anomalies["anomaly_details"].insert(0, f"ELEMENTO CRITICO: {', '.join(weapon_names)}")
            anomalies["risk_level"] = "critico"

        return anomalies

    def draw_annotations(self, frame: np.ndarray, detections: Dict[str, Any], anomalies: Dict[str, Any]) -> np.ndarray:
        frame_copy = frame.copy()
        h, w = frame_copy.shape[:2]
        is_critico = anomalies.get("risk_level") == "critico"

        for det in detections["all_boxes"]:
            x1, y1, x2, y2 = det["bbox"]
            category = det["category"]
            
            if category == "arma":
                color = (0, 0, 255)
                thickness = 3
                prefix = "ALERTA: "
            elif category == "persona":
                color = (0, 0, 255) if (anomalies["is_anomaly"] or is_critico) else (0, 255, 0)
                thickness = 2
                prefix = ""
            else:
                color = (255, 120, 0)
                thickness = 2
                prefix = "OBJ: "

            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, thickness)
            label = f"{prefix}{det['class_name']} {det['confidence']:.0%}"

            (t_w, t_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame_copy, (x1, y1 - 20), (x1 + t_w, y1), color, -1)
            cv2.putText(frame_copy, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Banner Superior
        overlay = frame_copy.copy()
        cv2.rectangle(overlay, (0, 0), (w, 50), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame_copy, 0.4, 0, frame_copy)

        if is_critico:
            status_color = (0, 0, 255)
            status_text = "RIESGO CRITICO"
        elif anomalies["is_anomaly"]:
            status_color = (0, 100, 200)
            status_text = "ANOMALIA DETECTADA"
        else:
            status_color = (0, 150, 0)
            status_text = "ESTADO NORMAL"
        
        detail_text = f"Confianza: {detections['used_confidence']:.2f} | " + (", ".join(anomalies["anomaly_types"]) if anomalies["anomaly_types"] else "Limpio")

        cv2.putText(frame_copy, status_text, (20, 25), cv2.FONT_HERSHEY_DUPLEX, 0.6, status_color, 1)
        cv2.putText(frame_copy, detail_text, (20, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (220, 220, 220), 1)

        return frame_copy

    def process_image(self, input_path: str, output_path: str, conf_override: Optional[float] = None) -> Dict[str, Any]:
        """
        Procesa una imagen y devuelve un esquema estricto optimizado para insercion en bases de datos.
        """
        start_time = time.time()
        frame = cv2.imread(input_path)
        if frame is None:
            raise ValueError(f"No se pudo leer la imagen en: {input_path}")

        detections = self.detect_and_analyze(frame, conf_override=conf_override)
        anomalies = self.evaluate_anomalies(detections)
        annotated_frame = self.draw_annotations(frame, detections, anomalies)

        cv2.imwrite(output_path, annotated_frame)
        processing_time = time.time() - start_time

        # Calcular conteo por clase desde all_boxes
        class_counts = {}
        for d in detections["all_boxes"]:
            name = d["class_name"]
            class_counts[name] = class_counts.get(name, 0) + 1

        # Formato estructurado directo para persistencia en base de datos
        return {
            "input_path": input_path,
            "output_path": output_path,
            "model_used": os.path.basename(self.model_path),
            "used_confidence": float(detections["used_confidence"]),
            "is_anomaly": bool(anomalies["is_anomaly"]),
            "risk_level": anomalies["risk_level"], # normal, medio, alto, critico
            "persons_count": len(detections["persons"]),
            "weapons_count": len(detections["weapons"]),
            "objects_count": len(detections["other_objects"]),
            "class_counts": class_counts,
            "anomaly_types": anomalies["anomaly_types"], # Guardar como JSON o texto separado por comas
            "detected_classes": list(set([d["class_name"] for d in detections["all_boxes"]])), # Guardar como JSON
            "processing_time_ms": int(processing_time * 1000)
        }