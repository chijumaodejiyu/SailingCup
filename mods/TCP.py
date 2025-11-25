import socket
import struct
import time
import logging
from typing import Optional

class VideoStreamSender:
    """视频流TCP传输类"""
    
    def __init__(self, target_ip: str, target_port: int) -> None:
        """
        初始化视频流发送器
        
        参数:
            target_ip: 目标IP地址
            target_port: 目标端口
            
        异常:
            ValueError: 参数无效时抛出
        """
        if not target_ip or not isinstance(target_port, int) or target_port <= 0:
            raise ValueError("无效的目标IP地址或端口")
            
        self.target_ip = target_ip
        self.target_port = target_port
        self.socket: Optional[socket.socket] = None
        self.sequence: int = 0  # 帧序列号
        self.connected: bool = False
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"视频流发送器初始化成功，目标: {target_ip}:{target_port}")
        
    def connect(self) -> bool:
        """建立TCP连接"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)  # 设置连接超时
            self.socket.connect((self.target_ip, self.target_port))
            self.connected = True
            self.logger.info(f"TCP连接建立成功: {self.target_ip}:{self.target_port}")
            return True
        except Exception as e:
            self.logger.error(f"TCP连接失败: {e}")
            self.connected = False
            return False
            
    def send_frame(self, frame_data: bytes, timestamp: Optional[float] = None) -> bool:
        """
        发送视频帧
        
        参数:
            frame_data: 视频帧数据
            timestamp: 时间戳，默认为当前时间
            
        返回:
            发送是否成功
            
        异常:
            ValueError: 帧数据无效时抛出
        """
        if not frame_data or len(frame_data) == 0:
            raise ValueError("帧数据不能为空")
                
        if not self.connected:
            if not self.connect():
                return False
                
        if timestamp is None:
            timestamp = time.time()
            
        try:
            # 打包数据: 序列号(4字节) + 时间戳(8字节) + 帧数据长度(4字节) + 帧数据
            header = struct.pack('!IdI', self.sequence, timestamp, len(frame_data))
            self.socket.sendall(header + frame_data)
            self.sequence += 1
            self.logger.debug(f"发送帧数据成功，序列号: {self.sequence-1}, 大小: {len(frame_data)}字节")
            return True
        except Exception as e:
            self.logger.error(f"发送帧数据失败: {e}")
            self.connected = False
            return False
            
    def close(self) -> None:
        """关闭连接"""
        try:
            if self.socket:
                self.socket.close()
                self.connected = False
                self.logger.info("TCP连接已关闭")
        except Exception as e:
            self.logger.error(f"关闭TCP连接失败: {e}")
            
    def __del__(self):
        """析构函数，确保连接关闭"""
        self.close()
