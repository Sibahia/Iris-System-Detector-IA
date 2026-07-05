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
    WEAPON_CLASSES = [0, 2, 3, 4, 5, 6, 7]
    
    CLASS_NAMES_MAP = {
        0: "arma",
        1: "persona",
        2: "rifle",
        3: "pistola",
        4: "arma de fuego",
        5: "cuchillo",
        6: "armas",
        7: "Cuchillo"
    }

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
            print(f"🔧 Usando CONFIDENCE_THRESHOLD desde parámetro: {self.confidence_threshold}")
        elif env_conf is not None:
            try:
                self.confidence_threshold = float(env_conf)
                print(f"🔧 Usando CONFIDENCE_THRESHOLD desde .env: {self.confidence_threshold}")
            except ValueError:
                print(f"⚠️ Valor inválido en .env para CONFIDENCE_THRESHOLD ('{env_conf}'). Usando fallback.")
                self.confidence_threshold = 0.5
        else:
            self.confidence_threshold = 0.5
            print(f"ℹ️ Variable CONFIDENCE_THRESHOLD no encontrada en .env. Usando valor por defecto: {self.confidence_threshold}")

        self.crowd_threshold = crowd_threshold
        self.loiter_threshold = loiter_threshold_seconds
        self.device = device
        self.model_path = model_path

        model_name = model_path or os.getenv("MODEL_NAME", f"yolo11{model_size}.pt")
        print(f"Cargando modelo YOLO: {model_name}")
        self.model = YOLO(model_name)

        if device == "cpu":
            try:
                model_dir = os.path.dirname(model_name) or "."
                base_name = os.path.splitext(os.path.basename(model_name))[0]
                openvino_path = os.path.join(model_dir, f"{base_name}_openvino_model/")
                if not os.path.exists(openvino_path):
                    print(
                        "🚀 Exportando modelo a OpenVINO para aceleración en CPU... (Tarda ~1 min por única vez)"
                    )
                    self.model.export(format="openvino")
                    print("✅ ¡Exportación completa!")

                print(f"Cargando modelo OpenVINO: {openvino_path}")
                self.model = YOLO(openvino_path, task="detect")
                print("✅ ¡Modelo optimizado con OpenVINO cargado!")
            except Exception as e:
                print(f"⚠️ Falló la exportación a OpenVINO (usando PyTorch como respaldo): {e}")
                self.model = YOLO(model_name)
        else:
            print("✅ ¡Modelo YOLO cargado con éxito!")

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
            "weapons": [],
            "other_objects": [],
            "all_boxes": [],
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
                    resolved_name = self.CLASS_NAMES_MAP.get(cls, self.model.names[cls])
                else:
                    resolved_name = self.CLASS_NAMES_MAP.get(cls, f"Clase {cls}")

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
        weapon_count = len(detections["weapons"])

        # 1. Monitoreo de Multitudes (Riesgo Base: Medio/Alto)
        if person_count >= self.crowd_threshold:
            anomalies["is_anomaly"] = True
            anomalies["anomaly_types"].append("AGLOMERACION_DE_PERSONAS")
            anomalies["anomaly_details"].append(
                f"Multitud detectada: {person_count} personas (límite: {self.crowd_threshold})"
            )
            anomalies["risk_level"] = (
                "alto" if person_count > self.crowd_threshold * 2 else "medio"
            )

        # 2. Monitoreo de Proximidad (Riesgo Base: Alto)
        if person_count >= 2:
            close_pairs = self._check_proximity(
                detections["persons"], proximity_threshold=150
            )
            if close_pairs > 0:
                anomalies["is_anomaly"] = True
                anomalies["anomaly_types"].append("ALTERCADO_POTENCIAL")
                anomalies["anomaly_details"].append(
                    f"Advertencia: {close_pairs} personas muy próximas"
                )
                anomalies["risk_level"] = "alto"

        # 3. CRÍTICO: DETECCIÓN DE ARMAS (Caso Grave - Sobreescribe todo a Crítico)
        if weapon_count > 0:
            anomalies["is_anomaly"] = True
            weapon_names = [w["class_name"].upper() for w in detections["weapons"]]
            
            # Insertamos la alerta de armas al inicio para asegurar máxima visibilidad
            anomalies["anomaly_types"].insert(0, "ARMA_DETECTADA")
            anomalies["anomaly_details"].insert(
                0, f"⚠ ARMA DETECTADA: {', '.join(weapon_names)}"
            )
            
            # Forzamos riesgo critico sin importar las reglas anteriores
            anomalies["risk_level"] = "critico"

        # 4. Combinación Sospechosa
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

    def draw_annotations(
        self, frame: np.ndarray, detections: Dict[str, Any], anomalies: Dict[str, Any]
    ) -> np.ndarray:
        frame_copy = frame.copy()
        overlay = frame.copy()
        h, w = frame_copy.shape[:2]

        is_critico = anomalies.get("risk_level") == "critico"

        # Dibujar Personas (Si es critico por arma, el recuadro de la persona cambia a rojo de alerta)
        person_color = (0, 0, 255) if (anomalies["is_anomaly"] or is_critico) else (0, 255, 0)
        for det in detections["persons"]:
            x1, y1, x2, y2 = det["bbox"]
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), person_color, 2)
            label = f"Persona {det['confidence']:.0%}"
            if "id" in det and det["id"] != -1:
                label += f" ID:{det['id']}"

            (t_w, t_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame_copy, (x1, y1 - 20), (x1 + t_w, y1), person_color, -1)
            cv2.putText(
                frame_copy, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
            )

        # Dibujar Armas (Recuadro más grueso y llamativo)
        for det in detections.get("weapons", []):
            x1, y1, x2, y2 = det["bbox"]
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 0, 255), 3)
            label = f"⚠ {det['class_name'].upper()} {det['confidence']:.0%}"

            (t_w, t_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame_copy, (x1, y1 - 25), (x1 + t_w, y1), (0, 0, 255), -1)
            cv2.putText(
                frame_copy, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
            )

        # Barra superior de estado
        pad = 20
        bar_height = 50

        if anomalies["is_anomaly"]:
            # Si el riesgo es critico, forzamos un rojo vivo (0, 0, 255)
            status_color = (0, 0, 255) if is_critico else (0, 100, 200)
            status_text = "🚨 RIESGO CRITICO: ARMA" if is_critico else "⚠ ANOMALIA DETECTADA"
            detail_text = ", ".join(anomalies["anomaly_types"])
        else:
            status_color = (0, 150, 0)
            status_text = "● NORMAL"
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

        # Barra inferior de detalles críticos (Se mantiene activa para casos graves)
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
        stats["model_name"] = os.path.basename(self.model_path) if self.model_path else os.getenv("MODEL_NAME", "default")

        return stats


_detector_instance = None


def get_yolo_detector(
    model_size: str = "s",
    model_path: Optional[str] = None,
    device: str = "cpu",
    confidence_threshold: Optional[float] = None,
    crowd_threshold: int = 5,
    loiter_threshold_seconds: float = 10.0,
) -> YOLOAnomalyDetector:
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = YOLOAnomalyDetector(
            model_size=model_size,
            model_path=model_path,
            device=device,
            confidence_threshold=confidence_threshold,
            crowd_threshold=crowd_threshold,
            loiter_threshold_seconds=loiter_threshold_seconds,
        )
    return _detector_instance