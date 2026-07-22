import json
import os

WEAPON_KEYWORDS = [
    "gun", "knife", "weapon", "bomb", "terror", "assault",
    "fight", "kidnap", "robbery", "theaf", "suspicious",
    "arma", "cuchillo", "pistol", "rifle", "fuego", "robo",
    "violence", "attack", "murder", "hostil", "peligro"
]

PERSON_KEYWORDS = [
    "person", "people", "man", "woman", "police", "prisoner",
    "persona", "gente", "hombre", "mujer", "policia", "prisionero"
]

_CONFIG_CACHE = None

def _get_config_path():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "models",
        "model_config.json"
    )

def _load_config():
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    config_path = _get_config_path()
    try:
        with open(config_path) as f:
            _CONFIG_CACHE = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _CONFIG_CACHE = {}
    return _CONFIG_CACHE


def classify_classes(model_names: dict, model_name: str = None) -> dict:
    result = {
        "weapon_ids": set(),
        "person_ids": set(),
        "armed_person_ids": set(),
        "behavior_categories": {},
        "class_names": dict(model_names) if model_names else {},
        "categories": {},
        "anomaly_map": {},
        "model_name": model_name,
    }

    config = _load_config()
    model_config = config.get(model_name) if model_name else None

    if model_config:
        class_groups = model_config.get("class_groups", {})
        for category, ids in class_groups.items():
            id_set = set(ids)
            result["behavior_categories"][category] = id_set
            for cls_id in ids:
                result["categories"][cls_id] = category
                if category == "weapon":
                    result["weapon_ids"].add(cls_id)
                elif category == "person":
                    result["person_ids"].add(cls_id)
                elif category == "armed_person":
                    result["person_ids"].add(cls_id)
                    result["weapon_ids"].add(cls_id)
                    result["armed_person_ids"].add(cls_id)

        result["anomaly_map"] = model_config.get("anomaly_map", {})
        return result

    # Fallback: keyword-based matching
    weapon_ids = set()
    person_ids = set()
    categories = {}

    for cls_id, name in (model_names or {}).items():
        name_lower = name.lower()
        cat = "otro"
        if any(w in name_lower for w in PERSON_KEYWORDS):
            person_ids.add(cls_id)
            cat = "persona"
        if any(w in name_lower for w in WEAPON_KEYWORDS):
            weapon_ids.add(cls_id)
            cat = "arma"
        if cls_id in person_ids and cls_id in weapon_ids:
            result["armed_person_ids"].add(cls_id)
        categories[cls_id] = cat

    result["weapon_ids"] = weapon_ids
    result["person_ids"] = person_ids
    result["categories"] = categories

    result["anomaly_map"] = {
        "weapon": { "type": "ARMA_DETECTADA", "risk": "alto" },
        "armed_person": { "type": "PERSONA_ARMADA", "risk": "alto" },
        "crowd": { "type": "AGLOMERACION_DE_PERSONAS", "risk": "medio" },
        "proximity": { "type": "ALTERCADO_POTENCIAL", "risk": "alto" },
    }

    return result
