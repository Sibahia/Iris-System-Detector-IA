from ultralytics import YOLO

model = YOLO("best.pt")

for class_id, class_name in model.names.items():
    print(f"ID: {class_id} -> Clase: {class_name}")