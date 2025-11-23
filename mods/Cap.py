import cv2
import time
import threading
import queue

class Camera:
    def __init__(self, device_index=0):
        """
        初始化摄像头(自动多线程版本)
        
        参数:
            device_index (int): 摄像头设备索引，默认为0
        """
        self.cap = cv2.VideoCapture(device_index)
        if not self.cap.isOpened():
            raise RuntimeError("无法打开摄像头设备")
            
        # 设置摄像头参数(默认720p分辨率)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        # 多线程相关变量
        self.frame_queue = queue.Queue(maxsize=2)  # 双缓冲队列
        self.running = True
        self.thread = threading.Thread(target=self._capture_thread)
        self.thread.start()
        
        # 帧率计算变量
        self.frame_count = 0
        self.start_time = time.time()

    def _capture_thread(self):
        """图像捕获线程"""
        while self.running:
            # 简单清空缓冲区
            for _ in range(2):
                self.cap.grab()
                
            # 读取帧
            ret, frame = self.cap.read()
            if not ret:
                continue
                
            # 更新帧率计数
            self.frame_count += 1
            if self.frame_count % 30 == 0:
                elapsed = time.time() - self.start_time
                fps = 30 / elapsed
                print(f"当前帧率: {fps:.2f} FPS")
                self.frame_count = 0
                self.start_time = time.time()
                
            # 放入队列(如果队列已满则丢弃旧帧)
            if self.frame_queue.full():
                self.frame_queue.get()
            self.frame_queue.put(frame)

    def get_frame(self, quality='HIGH'):
        """
        获取摄像头帧数据
        
        参数:
            quality (str): 帧质量，'HIGH'或'LOW'
            
        返回:
            numpy.ndarray: 摄像头帧数据
        """
        if quality not in ['HIGH', 'LOW']:
            raise ValueError("Quality must be 'HIGH' or 'LOW'")
            
        # 从队列获取最新帧
        if not self.frame_queue.empty():
            frame = self.frame_queue.get()
            
            # 根据质量调整分辨率
            if quality == 'HIGH':
                return frame
            else:
                return cv2.resize(frame, (640, 480), interpolation=cv2.INTER_LINEAR)
        return None

    def release(self):
        """释放摄像头资源"""
        self.running = False
        if self.thread is not None:
            self.thread.join()
        self.cap.release()

if __name__ == '__main__':
    try:
        # 初始化摄像头(接口保持不变)
        cam = Camera(1)
        print("摄像头初始化成功")
        
        # 捕获并显示帧
        while True:
            frame = cam.get_frame(quality='HIGH')
            if frame is not None:
                cv2.imshow('Camera Preview', frame)
                
            # 按q键退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                cam.release()
                break
                
    except Exception as e:
        print(f"发生错误: {e}")
        
    finally:
        # 确保释放资源
        cv2.destroyAllWindows()
        print("程序已退出")