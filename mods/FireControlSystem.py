from typing import Optional, Dict, Any
import logging
import time
from .DeviceManager import DeviceManager
from .Chassis import Chassis
from .Gun import Gun
from .FireControl import FireControl
from .Cap import Camera
from .TCP import VideoStreamSender

class FireControlSystem:
    """主火控系统类，协调所有模块工作"""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化火控系统
        
        参数:
            config: 系统配置字典，包含设备参数、网络设置等
            
        异常:
            RuntimeError: 系统初始化失败时抛出
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.running = False
        
        try:
            # 初始化设备管理器
            self.device_manager = DeviceManager()
            
            # 注册设备
            self._register_devices()
            
            # 初始化各模块
            self._initialize_modules()
            
            self.logger.info("火控系统初始化成功")
            
        except Exception as e:
            self.logger.error(f"火控系统初始化失败: {e}")
            raise
            
    def _register_devices(self) -> None:
        """注册所有硬件设备"""
        # 注册串口设备
        if 'serial_devices' in self.config:
            for name, params in self.config['serial_devices'].items():
                self.device_manager.register_serial(
                    name=name,
                    port=params.get('port', '/dev/ttyUSB0'),
                    baudrate=params.get('baudrate', 115200),
                    timeout=params.get('timeout', 1.0)
                )
        
        # 注册摄像头设备
        if 'camera_devices' in self.config:
            for name, params in self.config['camera_devices'].items():
                self.device_manager.register_camera(
                    name=name,
                    device_index=params.get('device_index', 0)
                )
                
    def _initialize_modules(self) -> None:
        """初始化所有功能模块"""
        # 初始化底盘控制
        self.chassis = Chassis(
            device_manager=self.device_manager,
            device_name=self.config.get('chassis_device', 'chassis')
        )
        
        # 初始化炮台控制
        self.gun = Gun(
            device_manager=self.device_manager,
            device_name=self.config.get('gun_device', 'gun'),
            gpio_pin=self.config.get('gun_gpio_pin', 17),
            address=self.config.get('gun_address', 0x01),
            steps_per_degree=self.config.get('steps_per_degree', 100)
        )
        
        # 初始化火控系统
        self.fire_control = FireControl(
            model_path=self.config.get('model_path', 'yolov11n.pt')
        )
        
        # 初始化摄像头
        self.camera = Camera(
            device_index=self.config.get('camera_index', 0)
        )
        
        # 初始化视频流发送器
        if 'tcp_config' in self.config:
            tcp_config = self.config['tcp_config']
            self.video_sender = VideoStreamSender(
                target_ip=tcp_config.get('target_ip', '127.0.0.1'),
                target_port=tcp_config.get('target_port', 8080)
            )
        else:
            self.video_sender = None
            
    def start(self) -> None:
        """启动火控系统"""
        try:
            self.running = True
            
            # 执行底盘自检
            self.logger.info("开始系统自检...")
            self.chassis.self_test()
            
            self.logger.info("火控系统启动成功")
            
        except Exception as e:
            self.logger.error(f"火控系统启动失败: {e}")
            raise
            
    def stop(self) -> None:
        """停止火控系统"""
        self.running = False
        
        try:
            # 停止所有模块
            if hasattr(self, 'camera'):
                self.camera.release()
                
            if hasattr(self, 'video_sender') and self.video_sender:
                self.video_sender.close()
                
            if hasattr(self, 'device_manager'):
                self.device_manager.close_all()
                
            self.logger.info("火控系统已停止")
            
        except Exception as e:
            self.logger.error(f"火控系统停止失败: {e}")
            
    def auto_targeting(self) -> Optional[Dict[str, Any]]:
        """
        自动目标跟踪和瞄准
        
        返回:
            目标信息字典，如果没有目标则返回None
        """
        if not self.running:
            self.logger.warning("火控系统未启动")
            return None
            
        try:
            # 获取摄像头帧
            frame = self.camera.get_frame(quality='HIGH')
            if frame is None:
                return None
                
            # 检测目标
            detections = self.fire_control.detect(frame)
            if not detections:
                return None
                
            # 选择最稳定的目标
            best_target = max(detections, key=lambda x: x['stability'])
            
            # 计算瞄准角度（简化版本）
            # 这里应该根据目标位置计算底盘转向角度和炮台调整角度
            target_info = {
                'id': best_target['id'],
                'bbox': best_target['bbox'],
                'confidence': best_target['confidence'],
                'stability': best_target['stability'],
                'chassis_angle': 0,  # 需要根据目标位置计算
                'gun_angle': 0      # 需要根据目标位置计算
            }
            
            self.logger.info(f"锁定目标: ID {target_info['id']}, 置信度: {target_info['confidence']:.2f}")
            return target_info
            
        except Exception as e:
            self.logger.error(f"自动目标跟踪失败: {e}")
            return None
            
    def engage_target(self, target_info: Dict[str, Any]) -> bool:
        """
        攻击目标
        
        参数:
            target_info: 目标信息字典
            
        返回:
            攻击是否成功
        """
        if not self.running:
            self.logger.warning("火控系统未启动")
            return False
            
        try:
            # 底盘转向
            chassis_angle = target_info.get('chassis_angle', 0)
            if chassis_angle != 0:
                self.chassis.turn(chassis_angle)
                
            # 炮台调整
            gun_angle = target_info.get('gun_angle', 0)
            if gun_angle != 0:
                self.gun.adjust(gun_angle)
                
            # 等待瞄准完成
            while not self.gun.is_aimed():
                time.sleep(0.1)
                
            # 开火
            self.gun.fire()
            
            self.logger.info(f"成功攻击目标: ID {target_info['id']}")
            return True
            
        except Exception as e:
            self.logger.error(f"攻击目标失败: {e}")
            return False
            
    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()