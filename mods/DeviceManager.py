from typing import Dict, Any, Optional
import serial
import cv2
import logging
from contextlib import contextmanager

class DeviceManager:
    """统一设备管理类，负责管理所有硬件设备资源"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._devices: Dict[str, Any] = {}
        
    def register_serial(self, name: str, port: str, baudrate: int, timeout: float = 1.0) -> None:
        """
        注册串口设备
        
        参数:
            name: 设备名称
            port: 串口路径
            baudrate: 波特率
            timeout: 超时时间(秒)
        """
        if name in self._devices:
            raise ValueError(f"设备 {name} 已存在")
            
        try:
            ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=timeout
            )
            self._devices[name] = ser
            self.logger.info(f"串口设备 {name} 注册成功, 端口: {port}, 波特率: {baudrate}")
        except Exception as e:
            self.logger.error(f"串口设备 {name} 注册失败: {e}")
            raise
            
    def register_camera(self, name: str, device_index: int = 0) -> None:
        """
        注册摄像头设备
        
        参数:
            name: 设备名称
            device_index: 摄像头索引
        """
        if name in self._devices:
            raise ValueError(f"设备 {name} 已存在")
            
        try:
            cap = cv2.VideoCapture(device_index)
            if not cap.isOpened():
                raise RuntimeError(f"无法打开摄像头设备 {device_index}")
                
            self._devices[name] = cap
            self.logger.info(f"摄像头设备 {name} 注册成功, 索引: {device_index}")
        except Exception as e:
            self.logger.error(f"摄像头设备 {name} 注册失败: {e}")
            raise
            
    def get_device(self, name: str) -> Any:
        """
        获取设备实例
        
        参数:
            name: 设备名称
            
        返回:
            设备实例
            
        异常:
            KeyError: 设备不存在时抛出
        """
        if name not in self._devices:
            raise KeyError(f"设备 {name} 不存在")
        return self._devices[name]
        
    def close_all(self) -> None:
        """关闭所有设备"""
        for name, device in self._devices.items():
            try:
                if isinstance(device, serial.Serial):
                    if device.is_open:
                        device.close()
                elif isinstance(device, cv2.VideoCapture):
                    device.release()
                self.logger.info(f"设备 {name} 已关闭")
            except Exception as e:
                self.logger.error(f"关闭设备 {name} 失败: {e}")
                
    @contextmanager
    def device_context(self, name: str):
        """
        设备上下文管理器
        
        参数:
            name: 设备名称
            
        用法:
            with device_manager.device_context('chassis') as device:
                device.write(...)
        """
        device = self.get_device(name)
        try:
            yield device
        finally:
            pass  # 不自动关闭设备，由close_all统一管理
            
    def __del__(self):
        """析构函数，确保资源释放"""
        self.close_all()