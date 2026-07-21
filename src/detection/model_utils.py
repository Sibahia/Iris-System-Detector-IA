import os
import yaml
from functools import lru_cache

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models")


@lru_cache(maxsize=8)
def get_native_class_names_for_model(model_name: str) -> list[str]:
    if not model_name:
        return []

    base = model_name.replace(".pt", "")
    yaml_path = os.path.join(MODELS_DIR, f"{base}_openvino_model", "metadata.yaml")

    if os.path.exists(yaml_path):
        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            names_dict = data.get("names", {})
            sorted_ids = sorted(names_dict.keys(), key=lambda k: int(k))
            return [names_dict[i] for i in sorted_ids]
        except Exception:
            pass

    pt_path = os.path.join(MODELS_DIR, model_name)
    if os.path.exists(pt_path):
        try:
            from ultralytics import YOLO
            temp = YOLO(pt_path)
            if hasattr(temp, "names") and temp.names:
                sorted_ids = sorted(temp.names.keys(), key=lambda k: int(k))
                return [temp.names[i] for i in sorted_ids]
        except Exception:
            pass

    return []


def compute_class_groups(model_name: str, class_counts: dict, class_names: dict) -> dict:
    from detection.class_mapper import _load_config

    if not model_name:
        return {}
    config = _load_config()
    model_cfg = config.get(model_name, {})
    class_groups = model_cfg.get("class_groups", {})
    if not class_groups:
        return {}

    result = {}
    for group_name, ids in class_groups.items():
        if not ids:
            continue
        native_names = []
        for cls_id in ids:
            name = class_names.get(cls_id)
            if name:
                native_names.append(name)
        if not native_names:
            continue
        detected = {n: class_counts.get(n, 0) for n in native_names if class_counts.get(n, 0) > 0}
        total = sum(detected.values())
        result[group_name] = {
            "count": total,
            "natives": native_names,
            "detected_natives": detected,
        }
    return result
