import argparse
import cv2
from ultralytics import YOLO
import numpy as np


def run_yolo_on_image(model_path, image_path, conf=0.25, show=True):
    model = YOLO(model_path)
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图片: {image_path}")
        return
    results = model.predict(image, conf=conf)
    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                conf_score = float(box.conf[0].cpu().numpy())
                class_id = int(box.cls[0].cpu().numpy())
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(image, f"{class_id}:{conf_score:.2f}", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
    if show:
        cv2.imshow("YOLO Detection", image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return results

def main():
    parser = argparse.ArgumentParser(description="YOLO模型测试工具")
    parser.add_argument('--model', type=str, default='mods/best.pt', help='模型路径')
    parser.add_argument('--image', type=str, required=True, help='待检测图片路径')
    parser.add_argument('--conf', type=float, default=0.25, help='置信度阈值')
    parser.add_argument('--noshow', action='store_true', help='不显示检测结果窗口')
    args = parser.parse_args()
    run_yolo_on_image(args.model, args.image, conf=args.conf, show=not args.noshow)

if __name__ == '__main__':
    main()
