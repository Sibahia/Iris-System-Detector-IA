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


def classify_classes(model_names: dict) -> dict:
    weapon_ids = set()
    person_ids = set()
    categories = {}

    for cls_id, name in (model_names or {}).items():
        name_lower = name.lower()
        if any(w in name_lower for w in PERSON_KEYWORDS):
            person_ids.add(cls_id)
            categories[cls_id] = "persona"
        if any(w in name_lower for w in WEAPON_KEYWORDS):
            weapon_ids.add(cls_id)
            categories[cls_id] = "arma"
        if cls_id not in categories:
            categories[cls_id] = "otro"

    return {
        "weapon_ids": weapon_ids,
        "person_ids": person_ids,
        "class_names": dict(model_names) if model_names else {},
        "categories": categories,
    }
