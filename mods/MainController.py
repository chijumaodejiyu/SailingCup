from typing import Optional, Dict, Any
import logging
import time
from .DeviceManager import DeviceManager
from .Chassis import Chassis
from .Gun import Gun
from .FireControl import FireControl
from .Cap import Camera
from .TCP import VideoStreamSender

class MainController:
    """主控制类，协调所有子系统工作"""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化主控制器
        
        参数:
            config: 配置字典，包含所有子系统的配置
            
        异常:
            RuntimeError: 初始化失败时抛出
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.running = False
        
        # 初始化子系统
        try:
            # 创建设备管理器
            self.device_manager = DeviceManager()
            
            # 注册设备
            self._register_devices()
            
            # 初始化子系统
            self.camera = Camera(device_index=config.get('camera_index', 0))
            self.chassis = Chassis(
                device_manager=self.device_manager,
                device_name=config.get('chassis_device', 'chassis')
            )
            self.gun = Gun(
                device_manager=self.device_manager,
                device_name=config.get('gun_device', 'gun'),
                gpio_pin=config.get('gun_gpio_pin', 17)
            )
            self.fire_control = FireControl(
                model_path=config.get('model_path', 'yolov11n.pt')
            )
            
            # 初始化TCP发送器（可选）
            if config.get('enable_tcp_stream', False):
                self.video_sender = VideoStreamSender(
                    target_ip=config.get('target_ip', '127.0.0.1'),
                    target_port=config.get('target_port', 8080)
                )
            else:
                self.video_sender = None
                
            self.logger.info("主控制器初始化成功")
            
        except Exception as e:
            self.logger.error(f"主控制器初始化失败: {e}")
            raise
            
    def _register_devices(self) -> None:
        """注册所有硬件设备"""
        # 注册底盘串口设备
        self.device_manager.register_serial(
            name=self.config.get('chassis_device', 'chassis'),
            port=self.config.get('chassis_port', '/dev/ttyUSB0'),
            baudrate=self.config.get('chassis_baudrate', 115200)
        )
        
        # 注册炮台串口设备
        self.device_manager.register_serial(
            name=self.config.get('gun_device', 'gun'),
            port=self.config.get('gun_port', '/dev/ttyUSB1'),
            baudrate=self.config.get('gun_baudrate', 115200)
        )
        
    def start(self) -> None:
        """启动主控制器"""
        try:
            self.running = True
            self.logger.info("主控制器启动")
            
            # 执行底盘自检
            self.chassis.self_test()
            
            # 主循环
            self._main_loop()
            
        except Exception as e:
            self.logger.error(f"主控制器运行失败: {e}")
            raise
        finally:
            self.stop()
            
    def stop(self) -> None:
        """停止主控制器"""
        self.running = False
        self.logger.info("主控制器停止")
        
    def _main_loop(self) -> None:
        """主控制循环"""
        while self.running:
            try:
                # 获取摄像头帧
                frame = self.camera.get_frame(quality='HIGH')
                if frame is None:
                    time.sleep(0.01)  # 等待下一帧
                    continue
                    
                # 发送视频流（如果启用）
                if self.video_sender:
                    # 这里需要将帧转换为字节数据
                    # 实际实现需要根据具体编码格式处理
                    pass
                
                # 目标检测
                detections = self.fire_control.detect(frame)
                
                # 处理检测结果
                self._process_detections(detections)
                
                # 清理过期跟踪记录
                self.fire_control.cleanup_tracks()
                
                time.sleep(0.01)  # 控制循环频率
                
            except Exception as e:
                self.logger.error(f"主循环异常: {e}")
                time.sleep(0.1)  # 异常后短暂等待
                
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
        
        # 计算目标位置（简化示例）
        bbox = target['bbox']
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        
        # 根据目标位置调整炮台和底盘
        self._aim_at_target(center_x, center_y, target['stability'])
        
    def _aim_at_target(self, x: float, y: float, stability: float) -> None:
        """瞄准目标位置"""
        # 简化示例：根据目标位置计算角度
        # 实际实现需要根据摄像头参数和目标距离计算
        
        # 炮台角度调整（垂直方向）
        gun_angle = self._calculate_gun_angle(y)
        self.gun.adjust(gun_angle)
        
        # 底盘转向（水平方向）
        chassis_angle = self._calculate_chassis_angle(x)
        self.chassis.turn(chassis_angle)
        
        # 如果瞄准稳定且角度合适，可以开火
        if (stability > 0.9 and 
            self.gun.is_aimed() and 
            abs(chassis_angle) < 10):  # 底盘转向角度小
            self.gun.fire()
            self.logger.info("开火！")
            
    def _calculate_gun_angle(self, y: float) -> float:
        """计算炮台角度（简化实现）"""
        # 实际实现需要根据摄像头参数和目标距离计算
        return max(-30, min(30, (y - 0.5) * 60))  # 简化计算
        
    def _calculate_chassis_angle(self, x: float) -> float:
        """计算底盘转向角度（简化实现）"""
        # 实际实现需要根据摄像头参数和目标距离计算
        return max(-180, min(180, (x - 0.5) * 360))  # 简化计算
        
    def cleanup(self) -> None:
        """清理所有资源"""
        try:
            self.stop()
            
            # 清理子系统
            if hasattr(self, 'camera'):
                self.camera.release()
            if hasattr(self, 'gun'):
                self.gun.cleanup()
            if hasattr(self, 'device_manager'):
                self.device_manager.close_all()
            if hasattr(self, 'video_sender'):
                self.video_sender.close()
                
            self.logger.info("所有资源已清理")
        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")
            
    def __del__(self):
        """析构函数，确保资源清理"""
        self.cleanup()