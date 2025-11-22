import cv2
import time

class Camera:
    def __init__(self, device_index=0):
        """
        初始化摄像头
        
        参数:
            device_index (int): 摄像头设备索引，默认为0
        """
        self.cap = cv2.VideoCapture(device_index)
        if not self.cap.isOpened():
            raise RuntimeError("无法打开摄像头设备")
            
        # 设置摄像头参数
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
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
            
        # 抓取5帧以清空缓冲区
        for _ in range(5):
            self.cap.grab()
            
        # 读取帧
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("无法读取摄像头帧数据")
            
        # 根据质量调整分辨率
        if quality == 'HIGH':
            return frame
        else:
            return cv2.resize(frame, (640, 480), interpolation=cv2.INTER_LINEAR)
            
    def release(self):
        """释放摄像头资源"""
        self.cap.release()