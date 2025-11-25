import time
import logging
from typing import Optional, Union
from contextlib import contextmanager
from .DeviceManager import DeviceManager

class Chassis:
    """底盘控制类，提供底盘运动控制和状态管理"""
    
    # 配置常量
    MAX_ANGLE = 180  # 最大转向角度(度)
    MIN_ANGLE = -180  # 最小转向角度(度)
    COMMAND_DELAY = 0.1  # 命令间隔时间(秒)
    
    def __init__(self, device_manager: DeviceManager, device_name: str = "chassis") -> None:
        """
        初始化底盘控制
        
        参数:
            device_manager: 设备管理器实例
            device_name: 设备名称，默认为"chassis"
            
        异常:
            RuntimeError: 无法获取串口设备时抛出
        """
        self.logger = logging.getLogger(__name__)
        self.device_manager = device_manager
        self.device_name = device_name
        
        try:
            # 获取串口设备
            self.serial = device_manager.get_device(device_name)
            if not self.serial.is_open:
                raise RuntimeError(f"串口设备 {device_name} 未打开")
                
            # 陀螺仪校准状态
            self.gyro_calibrated: bool = False
            self.logger.info(f"底盘控制器初始化成功, 设备: {device_name}")
        except Exception as e:
            self.logger.error(f"底盘控制器初始化失败: {e}")
            raise
        
    def self_test(self) -> None:
        """
        执行底盘自检和陀螺仪校准
        控制小车旋转360度完成自检
        
        异常:
            RuntimeError: 自检失败时抛出
        """
        try:
            self.logger.info("开始底盘自检...")
            
            # 发送旋转命令
            self.send_command("ROTATE 360")
            
            # 等待自检完成
            while True:
                response = self.serial.readline().decode().strip()
                if response == "SELF_TEST_COMPLETE":
                    self.logger.info("底盘自检完成")
                    break
                time.sleep(self.COMMAND_DELAY)
                
            # 陀螺仪校准
            self.calibrate_gyro()
        except Exception as e:
            self.logger.error(f"底盘自检失败: {e}")
            raise
            
    def calibrate_gyro(self) -> None:
        """
        执行陀螺仪校准
        
        异常:
            RuntimeError: 校准失败时抛出
        """
        try:
            self.logger.info("开始陀螺仪校准...")
            self.send_command("CALIBRATE_GYRO")
            
            while True:
                response = self.serial.readline().decode().strip()
                if response == "GYRO_CALIBRATED":
                    self.gyro_calibrated = True
                    self.logger.info("陀螺仪校准完成")
                    break
                time.sleep(self.COMMAND_DELAY)
        except Exception as e:
            self.logger.error(f"陀螺仪校准失败: {e}")
            raise
            
    def turn(self, angle: float) -> None:
        """
        控制底盘转向
        
        参数:
            angle: 转向角度，正值为顺时针，负值为逆时针
            
        异常:
            RuntimeError: 转向失败或陀螺仪未校准时抛出
        """
        if not self.gyro_calibrated:
            raise RuntimeError("陀螺仪未校准，请先执行自检")
            
        try:
            # 限制角度范围
            angle = max(self.MIN_ANGLE, min(self.MAX_ANGLE, angle))
            self.send_command(f"TURN {angle}")
            self.logger.debug(f"发送转向命令: {angle}度")
        except Exception as e:
            self.logger.error(f"转向控制失败: {e}")
            raise
            
    def send_command(self, command: str) -> None:
        """
        发送串口命令
        
        参数:
            command: 要发送的命令字符串
            
        异常:
            RuntimeError: 命令发送失败时抛出
        """
        try:
            self.serial.write(f"{command}\n".encode())
            time.sleep(self.COMMAND_DELAY)  # 确保命令间隔
        except Exception as e:
            self.logger.error(f"命令发送失败: {command}, 错误: {e}")
            raise
            
    def close(self) -> None:
        """关闭底盘控制器（不再管理串口资源）"""
        self.logger.info("底盘控制器已关闭")
        # 串口资源由DeviceManager统一管理
            
    @contextmanager
    def chassis_context(self):
        """
        提供上下文管理支持
        示例用法:
        with chassis.chassis_context() as c:
            c.turn(45)
        """
        try:
            yield self
        finally:
            self.close()