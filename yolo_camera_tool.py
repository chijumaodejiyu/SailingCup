import argparse
import cv2
from ultralytics import YOLO


def run_yolo_on_camera(model_path, conf=0.25, camera_id=0):
    model = YOLO(model_path)
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"无法打开摄像头: {camera_id}")
        return
    print("按 q 退出摄像头检测...")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("无法读取摄像头帧")
            break
        results = model.predict(frame, conf=conf)
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    conf_score = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"{class_id}:{conf_score:.2f}", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        cv2.imshow("YOLO Camera Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

def main():
    parser = argparse.ArgumentParser(description="YOLO模型摄像头测试工具")
    parser.add_argument('--model', type=str, default='mods/best.pt', help='模型路径')
    parser.add_argument('--conf', type=float, default=0.25, help='置信度阈值')
    parser.add_argument('--camera', type=int, default=0, help='摄像头ID')
    args = parser.parse_args()
    run_yolo_on_camera(args.model, conf=args.conf, camera_id=args.camera)

if __name__ == '__main__':
    main()
