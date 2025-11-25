from typing import Optional, Dict, Any
import time
import logging
import threading
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
            config: 系统配置字典
            
        配置示例:
            {
                "devices": {
                    "chassis": {"port": "/dev/ttyUSB0", "baudrate": 115200},
                    "gun": {"port": "/dev/ttyUSB1", "baudrate": 115200},
                    "camera": {"device_index": 0}
                },
                "tcp": {
                    "target_ip": "192.168.1.100",
                    "target_port": 8080
                },
                "fire_control": {
                    "model_path": "yolov11n.pt"
                }
            }
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # 初始化设备管理器
        self.device_manager = DeviceManager()
        
        # 注册设备
        self._register_devices()
        
        # 初始化各模块
        self._initialize_modules()
        
        self.logger.info("火控系统初始化完成")
        
    def _register_devices(self) -> None:
        """注册所有硬件设备"""
        try:
            # 注册串口设备
            if "chassis" in self.config["devices"]:
                chassis_cfg = self.config["devices"]["chassis"]
                self.device_manager.register_serial(
                    "chassis", 
                    chassis_cfg["port"], 
                    chassis_cfg["baudrate"]
                )
                
            if "gun" in self.config["devices"]:
                gun_cfg = self.config["devices"]["gun"]
                self.device_manager.register_serial(
                    "gun",
                    gun_cfg["port"],
                    gun_cfg["baudrate"]
                )
                
            # 注册摄像头设备
            if "camera" in self.config["devices"]:
                camera_cfg = self.config["devices"]["camera"]
                self.device_manager.register_camera(
                    "camera",
                    camera_cfg["device_index"]
                )
                
            self.logger.info("所有设备注册完成")
            
        except Exception as e:
            self.logger.error(f"设备注册失败: {e}")
            raise
            
    def _initialize_modules(self) -> None:
        """初始化所有功能模块"""
        try:
            # 初始化底盘控制
            self.chassis = Chassis(self.device_manager, "chassis")
            
            # 初始化炮台控制
            gun_cfg = self.config.get("gun", {})
            self.gun = Gun(
                device_manager=self.device_manager,
                device_name="gun",
                gpio_pin=gun_cfg.get("gpio_pin", 17),
                address=gun_cfg.get("address", 0x01),
                steps_per_degree=gun_cfg.get("steps_per_degree", 100)
            )
            
            # 初始化火控系统
            fire_control_cfg = self.config.get("fire_control", {})
            self.fire_control = FireControl(
                model_path=fire_control_cfg.get("model_path", "yolov11n.pt")
            )
            
            # 初始化摄像头
            self.camera = Camera(0)  # 使用独立的摄像头实例
            
            # 初始化TCP传输
            if "tcp" in self.config:
                tcp_cfg = self.config["tcp"]
                self.video_sender = VideoStreamSender(
                    target_ip=tcp_cfg["target_ip"],
                    target_port=tcp_cfg["target_port"]
                )
            else:
                self.video_sender = None
                
            self.logger.info("所有功能模块初始化完成")
            
        except Exception as e:
            self.logger.error(f"模块初始化失败: {e}")
            raise
            
    def start(self) -> None:
        """启动火控系统"""
        if self.running:
            self.logger.warning("火控系统已在运行中")
            return
            
        try:
            # 执行底盘自检
            self.chassis.self_test()
            
            # 启动主循环线程
            self.running = True
            self.thread = threading.Thread(target=self._main_loop)
            self.thread.start()
            
            self.logger.info("火控系统启动成功")
            
        except Exception as e:
            self.logger.error(f"火控系统启动失败: {e}")
            raise
            
    def stop(self) -> None:
        """停止火控系统"""
        if not self.running:
            return
            
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            
        self.logger.info("火控系统已停止")
        
    def _main_loop(self) -> None:
        """主循环，处理目标检测和跟踪"""
        while self.running:
            try:
                # 获取摄像头帧
                frame = self.camera.get_frame(quality='HIGH')
                if frame is None:
                    time.sleep(0.01)
                    continue
                    
                # 目标检测
                detections = self.fire_control.detect(frame)
                
                # 处理检测结果
                self._process_detections(detections)
                
                # 发送视频流（如果配置了TCP）
                if self.video_sender:
                    # 这里需要将帧转换为字节数据
                    # 实际实现中可能需要使用cv2.imencode()
                    pass
                    
                # 清理过期跟踪记录
                self.fire_control.cleanup_tracks()
                
                time.sleep(0.033)  # 约30FPS
                
            except Exception as e:
                self.logger.error(f"主循环异常: {e}")
                time.sleep(1)  # 异常后等待1秒再继续
                
    def _process_detections(self, detections: list) -> None:
        """处理检测到的目标"""
        if not detections:
            return
            
        # 选择最稳定的目标
        stable_targets = [d for d in detections if d['stability'] > 0.7]
        if not stable_targets:
            return
            
        # 选择置信度最高的目标
        target = max(stable_targets, key=lambda x: x['confidence'])
        
        # 计算目标在图像中的位置
        bbox = target['bbox']
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        
        # 根据目标位置计算底盘转向角度和炮台调整角度
        # 这里需要根据实际摄像头视野和机械结构进行计算
        chassis_angle = self._calculate_chassis_angle(center_x)
        gun_angle = self._calculate_gun_angle(center_y)
        
        # 控制底盘和炮台
        try:
            self.chassis.turn(chassis_angle)
            self.gun.adjust(gun_angle)
            
            # 如果已瞄准且目标稳定，可以开火
            if self.gun.is_aimed() and target['stability'] > 0.9:
                self.gun.fire()
                self.logger.info(f"开火！目标ID: {target['id']}")
                
        except Exception as e:
            self.logger.error(f"控制执行失败: {e}")
            
    def _calculate_chassis_angle(self, center_x: float) -> float:
        """根据目标水平位置计算底盘转向角度"""
        # 假设图像宽度为1280，中心为640
        # 角度范围：-180到180度
        image_width = 1280
        image_center = image_width / 2
        max_angle = 180
        
        # 计算偏移比例 (-1到1)
        offset_ratio = (center_x - image_center) / image_center
        
        # 转换为角度
        angle = offset_ratio * max_angle
        
        # 限制角度范围
        return max(-180, min(180, angle))
        
    def _calculate_gun_angle(self, center_y: float) -> float:
        """根据目标垂直位置计算炮台调整角度"""
        # 假设图像高度为720，中心为360
        # 角度范围：-30到30度
        image_height = 720
        image_center = image_height / 2
        max_angle = 30
        
        # 计算偏移比例 (-1到1)
        offset_ratio = (center_y - image_center) / image_center
        
        # 转换为角度
        angle = offset_ratio * max_angle
        
        # 限制角度范围
        return max(-30, min(30, angle))
        
    def cleanup(self) -> None:
        """清理所有资源"""
        self.stop()
        
        # 清理各模块资源
        if hasattr(self, 'gun'):
            self.gun.cleanup()
        if hasattr(self, 'camera'):
            self.camera.release()
        if hasattr(self, 'video_sender'):
            self.video_sender.close()
            
        # 关闭设备管理器
        self.device_manager.close_all()
        
        self.logger.info("火控系统资源清理完成")