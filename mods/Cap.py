import cv2
import time
import threading
import queue
import logging
from typing import Optional, Tuple, Any
import numpy as np

class Camera:
    """摄像头控制类，提供多线程视频采集功能"""
    
    # 配置常量
    DEFAULT_WIDTH = 1280  # 默认分辨率宽度
    DEFAULT_HEIGHT = 720  # 默认分辨率高度
    DEFAULT_FPS = 30  # 默认帧率
    QUEUE_SIZE = 2  # 帧队列大小
    FPS_CALC_INTERVAL = 30  # 帧率计算间隔(帧数)
    
    def __init__(self, device_index: int = 0) -> None:
        """
        初始化摄像头(自动多线程版本)
        
        参数:
            device_index: 摄像头设备索引，默认为0
            
        异常:
            RuntimeError: 无法打开摄像头设备时抛出
        """
        self.cap = cv2.VideoCapture(device_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开摄像头设备 {device_index}")
            
        # 设置摄像头参数
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.DEFAULT_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.DEFAULT_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, self.DEFAULT_FPS)
        
        # 多线程相关变量
        self.frame_queue: queue.Queue = queue.Queue(maxsize=self.QUEUE_SIZE)
        self.running: bool = True
        self.thread: threading.Thread = threading.Thread(target=self._capture_thread)
        self.thread.start()
        
        # 帧率计算变量
        self.frame_count: int = 0
        self.start_time: float = time.time()
        
        # 日志
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"摄像头设备 {device_index} 初始化成功")

    def _capture_thread(self) -> None:
        """
        图像捕获线程
        持续从摄像头捕获帧并放入队列
        """
        try:
            while self.running:
                # 简单清空缓冲区
                for _ in range(2):
                    self.cap.grab()
                    
                # 读取帧
                ret, frame = self.cap.read()
                if not ret:
                    self.logger.warning("读取摄像头帧失败")
                    continue
                    
                # 更新帧率计数
                self.frame_count += 1
                if self.frame_count % self.FPS_CALC_INTERVAL == 0:
                    elapsed = time.time() - self.start_time
                    fps = self.FPS_CALC_INTERVAL / elapsed
                    self.logger.info(f"当前帧率: {fps:.2f} FPS")
                    self.frame_count = 0
                    self.start_time = time.time()
                    
                # 放入队列(如果队列已满则丢弃旧帧)
                if self.frame_queue.full():
                    self.frame_queue.get()
                self.frame_queue.put(frame)
        except Exception as e:
            self.logger.error(f"捕获线程异常: {e}")
            raise

    def get_frame(self, quality: str = 'HIGH') -> Optional[np.ndarray]:
        """
        获取摄像头帧数据
        
        参数:
            quality: 帧质量，'HIGH'或'LOW'
            
        返回:
            摄像头帧数据，如果获取失败则返回None
            
        异常:
            ValueError: 当quality参数无效时抛出
        """
        if quality not in ['HIGH', 'LOW']:
            raise ValueError("quality参数必须是'HIGH'或'LOW'")
            
        try:
            if not self.frame_queue.empty():
                frame = self.frame_queue.get()
                
                # 根据质量调整分辨率
                if quality == 'HIGH':
                    return frame
                else:
                    return cv2.resize(frame, (640, 480), interpolation=cv2.INTER_LINEAR)
            return None
        except Exception as e:
            self.logger.error(f"获取帧数据失败: {e}")
            raise

    def release(self) -> None:
        """
        释放摄像头资源
        停止捕获线程并释放摄像头设备
        """
        self.running = False
        try:
            if self.thread is not None:
                self.thread.join()
            self.cap.release()
            self.logger.info("摄像头资源已释放")
        except Exception as e:
            self.logger.error(f"释放资源失败: {e}")
            raise

if __name__ == '__main__':
    """测试摄像头模块"""
    logging.basicConfig(level=logging.INFO)
    try:
        cam = Camera(1)
        logging.info("摄像头测试开始，按q键退出")
        
        while True:
            frame = cam.get_frame(quality='HIGH')
            if frame is not None:
                cv2.imshow('Camera Preview', frame)
                
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except Exception as e:
        logging.error(f"摄像头测试失败: {e}")
    finally:
        if 'cam' in locals():
            cam.release()
        cv2.destroyAllWindows()
        logging.info("摄像头测试结束")