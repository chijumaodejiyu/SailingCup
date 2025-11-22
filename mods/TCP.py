import socket
import struct
import time

class VideoStreamSender:
    """
    视频流TCP传输类
    """
    def __init__(self, target_ip, target_port):
        """
        初始化视频流发送器
        
        参数:
            target_ip (str): 目标IP地址
            target_port (int): 目标端口
        """
        self.target_ip = target_ip
        self.target_port = target_port
        self.socket = None
        self.sequence = 0  # 帧序列号
        self.connected = False
        
    def connect(self):
        """建立TCP连接"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.target_ip, self.target_port))
            self.connected = True
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            self.connected = False
            return False
            
    def send_frame(self, frame_data, timestamp=None):
        """
        发送视频帧
        
        参数:
            frame_data (bytes): 视频帧数据
            timestamp (float, optional): 时间戳，默认为当前时间
            
        返回:
            bool: 发送是否成功
        """
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
            return True
        except Exception as e:
            print(f"发送帧数据失败: {e}")
            self.connected = False
            return False
            
    def close(self):
        """关闭连接"""
        if self.socket:
            self.socket.close()
            self.connected = False
