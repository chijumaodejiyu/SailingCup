import cv2
import numpy as np
import time
import logging
import threading
import serial
import platform
import os
from typing import List, Dict, Optional, Tuple
from collections import deque
from stepper.device import Device
from stepper.stepper_core.parameters import DeviceParams
from stepper.stepper_core.configs import Address

def is_raspberry_pi() -> bool:
    """检测是否运行在树莓派上"""
    try:
        # 检查平台和硬件信息
        if platform.system() != 'Linux':
            return False
        
        # 检查是否存在树莓派特有的文件
        if os.path.exists('/proc/device-tree/model'):
            with open('/proc/device-tree/model', 'r') as f:
                model_info = f.read().lower()
                if 'raspberry' in model_info:
                    return True
        
        # 检查环境变量
        if os.environ.get('RASPBERRY_PI', '').lower() in ('1', 'true', 'yes'):
            return True
            
        return False
    except:
        return False

# 条件导入GPIO模块
if is_raspberry_pi():
    try:
        import RPi.GPIO as GPIO
        logger.info("使用真实的RPi.GPIO模块")
    except ImportError:
        logger.warning("无法导入RPi.GPIO，使用模拟GPIO模块")
        from mods.mock_gpio import GPIO
else:
    logger.info("检测到非树莓派环境，使用模拟GPIO模块")
    from mods.mock_gpio import GPIO

# 配置常量
CAMERA_SOURCE = 0  # 摄像头源
TCP_SERVER_IP = '192.168.1.100'  # TODO: 配置TCP服务器IP
TCP_SERVER_PORT = 8080  # TODO: 配置TCP服务器端口
SERIAL_PORT_A = '/dev/ttyAMA0'  # A串口 - 底盘STM32
SERIAL_PORT_B = '/dev/ttyAMA1'  # B串口 - 步进电机y轴
SERIAL_BAUDRATE = 115200
FIRE_GPIO_PIN = 18  # 开火GPIO引脚

# 摄像头参数
CAMERA_H_FOV = 85  # 水平视场角(度)
CAMERA_V_FOV = CAMERA_H_FOV * (9/16)  # 垂直视场角(度)
IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080

# 控制参数
AIM_THRESHOLD = 2.0  # 瞄准阈值(度)
SEARCH_ANGLE = 25  # 搜索角度(度)
DETECTION_AVERAGE_COUNT = 3  # 检测结果平均次数
MAIN_LOOP_SLEEP = 0.05  # 主循环休眠时间(秒)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SerialController:
    """串口控制器"""
    
    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        
    def connect(self) -> bool:
        """连接串口"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            logger.info(f"串口 {self.port} 连接成功")
            return True
        except Exception as e:
            logger.error(f"串口 {self.port} 连接失败: {e}")
            return False
            
    def send_command(self, command: str) -> bool:
        """发送命令到串口"""
        if not self.serial or not self.serial.is_open:
            logger.error("串口未连接")
            return False
            
        try:
            self.serial.write((command + '\n').encode())
            return True
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            return False
            
    def close(self):
        """关闭串口"""
        if self.serial and self.serial.is_open:
            self.serial.close()

class GPIOController:
    """GPIO控制器"""
    
    def __init__(self, fire_pin: int):
        self.fire_pin = fire_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.fire_pin, GPIO.OUT)
        GPIO.output(self.fire_pin, GPIO.LOW)
        
    def fire(self):
        """执行开火"""
        try:
            GPIO.output(self.fire_pin, GPIO.HIGH)
            time.sleep(0.1)  # 开火脉冲持续时间
            GPIO.output(self.fire_pin, GPIO.LOW)
            logger.info("开火执行")
        except Exception as e:
            logger.error(f"开火失败: {e}")
            
    def cleanup(self):
        """清理GPIO"""
        GPIO.cleanup()

class CameraController:
    """摄像头控制器（使用ffmpeg）"""
    
    def __init__(self, source: int = 0):
        self.source = source
        self.cap = None
        
    def initialize(self) -> bool:
        """初始化摄像头"""
        try:
            # 使用ffmpeg后端
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
            if not self.cap.isOpened():
                logger.error("无法打开摄像头")
                return False
                
            # 设置分辨率
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_HEIGHT)
            logger.info("摄像头初始化成功")
            return True
        except Exception as e:
            logger.error(f"摄像头初始化失败: {e}")
            return False
            
    def get_frame(self) -> Optional[np.ndarray]:
        """获取帧数据"""
        if not self.cap or not self.cap.isOpened():
            return None
            
        ret, frame = self.cap.read()
        if ret:
            return frame
        return None
        
    def release(self):
        """释放摄像头"""
        if self.cap:
            self.cap.release()

class YOLODetector:
    """YOLO11目标检测器（非阻塞方式）"""
    
    def __init__(self):
        self.model = None
        self.detection_queue = deque(maxlen=DETECTION_AVERAGE_COUNT)
        self.lock = threading.Lock()
        
    def initialize(self) -> bool:
        """初始化YOLO模型"""
        try:
            # TODO: 加载YOLO11模型
            # self.model = yolov11.load_model('path/to/model')
            logger.info("YOLO检测器初始化成功")
            return True
        except Exception as e:
            logger.error(f"YOLO检测器初始化失败: {e}")
            return False
            
    def detect_async(self, frame: np.ndarray):
        """异步目标检测"""
        def detection_task():
            try:
                # TODO: 实现YOLO11检测逻辑
                # detections = self.model.detect(frame)
                # 模拟检测结果
                detections = self._mock_detection(frame)
                
                with self.lock:
                    self.detection_queue.append(detections)
            except Exception as e:
                logger.error(f"目标检测失败: {e}")
                
        threading.Thread(target=detection_task, daemon=True).start()
        
    def get_average_detection(self) -> List[Dict]:
        """获取平均检测结果"""
        with self.lock:
            if not self.detection_queue:
                return []
                
            # 对最近DETECTION_AVERAGE_COUNT次检测结果取平均
            all_detections = []
            for detections in self.detection_queue:
                all_detections.extend(detections)
                
            # TODO: 实现检测结果平均逻辑
            return all_detections
            
    def _mock_detection(self, frame: np.ndarray) -> List[Dict]:
        """模拟检测结果（用于测试）"""
        # 返回模拟的检测结果
        return [{
            'class': 0,
            'confidence': 0.95,
            'bbox': [IMAGE_WIDTH//2-50, IMAGE_HEIGHT//2-50, 
                    IMAGE_WIDTH//2+50, IMAGE_HEIGHT//2+50],
            'id': 1
        }]

class AngleCalculator:
    """角度计算器"""
    
    @staticmethod
    def pixel_to_angle(pixel_x: float, pixel_y: float) -> Tuple[float, float]:
        """像素坐标转换为角度
        
        Args:
            pixel_x: 像素x坐标（图像坐标系）
            pixel_y: 像素y坐标（图像坐标系）
            
        Returns:
            Tuple[float, float]: (水平角度差, 垂直角度差)
        """
        # 转换为以图像中心为原点的坐标
        x = pixel_x - IMAGE_WIDTH / 2
        y = IMAGE_HEIGHT / 2 - pixel_y  # y轴向下为正，需要反转
        
        # 计算水平角度差(度)
        x_angle = (x / (IMAGE_WIDTH / 2)) * (CAMERA_H_FOV / 2)
        
        # 计算垂直角度差(度)
        y_angle = (y / (IMAGE_HEIGHT / 2)) * (CAMERA_V_FOV / 2)
        
        return x_angle, y_angle
        
    @staticmethod
    def calculate_target_center(bbox: List[float]) -> Tuple[float, float]:
        """计算目标中心坐标"""
        x_center = (bbox[0] + bbox[2]) / 2
        y_center = (bbox[1] + bbox[3]) / 2
        return x_center, y_center

class MainController:
    """主控制器"""
    
    def __init__(self):
        self.camera = CameraController(CAMERA_SOURCE)
        self.yolo = YOLODetector()
        self.serial_a = SerialController(SERIAL_PORT_A, SERIAL_BAUDRATE)  # 底盘串口
        self.gpio = GPIOController(FIRE_GPIO_PIN)
        self.angle_calc = AngleCalculator()
        
        # 步进电机控制
        self.device_manager = DeviceManager()
        self.gun_device = None
        self.steps_per_degree = 100  # 每度对应的步进脉冲数
        
        self.current_angle = 0  # 当前角度
        self.target_locked = False  # 目标锁定状态
        self.search_mode = True  # 搜索模式
        
    def initialize(self) -> bool:
        """初始化所有组件"""
        try:
            if not self.camera.initialize():
                return False
                
            if not self.yolo.initialize():
                return False
                
            if not self.serial_a.connect():
                return False
                
            # 初始化步进电机设备
            try:
                # 注册串口设备
                self.device_manager.register_serial("gun", SERIAL_PORT_B, SERIAL_BAUDRATE)
                
                # 获取串口设备
                serial_device = self.device_manager.get_device("gun")
                
                # 初始化步进电机控制
                self.gun_device = Device(
                    device_params=DeviceParams(
                        serial_connection=serial_device,
                        address=Address(0x01)
                    )
                )
                self.gun_device.enable()
                logger.info("步进电机设备初始化成功")
                
            except Exception as e:
                logger.error(f"步进电机设备初始化失败: {e}")
                return False
                
            logger.info("所有组件初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False
            
    def control_chassis(self, angle: float):
        """控制底盘转动"""
        # TODO: 实现底盘控制协议
        command = f"TURN {angle:.2f}"
        self.serial_a.send_command(command)
        
    def control_gun(self, angle: float):
        """控制枪械俯仰"""
        if not self.gun_device:
            logger.error("步进电机设备未初始化")
            return
            
        try:
            # 计算目标步数
            target_steps = int(angle * self.steps_per_degree)
            
            # 设置运动参数
            self.gun_device.set_speed(500)  # 设置速度为500步/秒
            self.gun_device.set_acceleration(1000)  # 设置加速度为1000步/秒²
            
            # 使用绝对位置移动
            self.gun_device.move_to(target_steps)
            
            # 等待移动完成
            while not self.gun_device.is_in_position:
                time.sleep(0.01)  # 短暂等待，避免阻塞主循环
                
            logger.debug(f"炮台调整到 {angle} 度")
            
        except Exception as e:
            logger.error(f"炮台调整失败: {e}")
        
    def is_target_locked(self, x_angle: float, y_angle: float) -> bool:
        """检查目标是否锁定"""
        return abs(x_angle) < AIM_THRESHOLD and abs(y_angle) < AIM_THRESHOLD
        
    def search_target(self):
        """搜索目标模式"""
        self.current_angle += SEARCH_ANGLE
        self.control_chassis(self.current_angle)
        logger.info(f"搜索模式：转动到角度 {self.current_angle}度")
        
    def process_detection(self, detections: List[Dict]) -> Optional[Tuple[float, float]]:
        """处理检测结果"""
        if not detections:
            return None
            
        # 找到离中心最近的目标
        min_distance = float('inf')
        best_target = None
        
        for detection in detections:
            if detection['class'] == 0:  # 只处理目标类别
                x_center, y_center = self.angle_calc.calculate_target_center(detection['bbox'])
                distance = np.sqrt((x_center - IMAGE_WIDTH/2)**2 + (y_center - IMAGE_HEIGHT/2)**2)
                
                if distance < min_distance:
                    min_distance = distance
                    best_target = detection
                    
        if best_target:
            x_center, y_center = self.angle_calc.calculate_target_center(best_target['bbox'])
            return self.angle_calc.pixel_to_angle(x_center, y_center)
            
        return None
        
    def run(self):
        """主控制循环"""
        logger.info("主控制循环开始")
        
        try:
            while True:
                # 获取帧数据
                frame = self.camera.get_frame()
                if frame is None:
                    logger.warning("获取帧数据失败")
                    time.sleep(MAIN_LOOP_SLEEP)
                    continue
                    
                # 异步目标检测
                self.yolo.detect_async(frame)
                
                # 获取平均检测结果
                detections = self.yolo.get_average_detection()
                
                if detections:
                    # 处理检测结果
                    angles = self.process_detection(detections)
                    
                    if angles:
                        x_angle, y_angle = angles
                        
                        # 控制瞄准
                        self.control_chassis(x_angle)
                        self.control_gun(y_angle)
                        
                        # 检查是否锁定目标
                        if self.is_target_locked(x_angle, y_angle):
                            if not self.target_locked:
                                logger.info("目标锁定")
                                self.target_locked = True
                            
                            # 执行开火
                            self.gpio.fire()
                            self.search_mode = False
                        else:
                            self.target_locked = False
                    else:
                        # 没有检测到目标，进入搜索模式
                        if not self.search_mode:
                            self.search_mode = True
                            logger.info("进入搜索模式")
                            
                        self.search_target()
                else:
                    # 没有检测到目标，进入搜索模式
                    if not self.search_mode:
                        self.search_mode = True
                        logger.info("进入搜索模式")
                        
                    self.search_target()
                    
                time.sleep(MAIN_LOOP_SLEEP)
                
        except KeyboardInterrupt:
            logger.info("程序被用户中断")
        except Exception as e:
            logger.error(f"主循环异常: {e}")
        finally:
            self.cleanup()
            
    def cleanup(self):
        """清理资源"""
        logger.info("清理资源")
        self.camera.release()
        self.serial_a.close()
        self.gpio.cleanup()
        
        # 清理步进电机设备
        if self.gun_device:
            try:
                self.gun_device.stop()
                self.gun_device.disable()
                logger.info("步进电机设备已清理")
            except Exception as e:
                logger.error(f"清理步进电机设备失败: {e}")
        
        # 清理设备管理器
        try:
            self.device_manager.close_all()
            logger.info("设备管理器已清理")
        except Exception as e:
            logger.error(f"清理设备管理器失败: {e}")

if __name__ == '__main__':
    controller = MainController()
    if controller.initialize():
        controller.run()
    else:
        logger.error("初始化失败，程序退出")
