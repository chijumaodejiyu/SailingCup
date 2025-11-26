"""
模拟串口模块，用于在PC上调试树莓派串口相关代码
"""

import logging
import time
from typing import Optional, Any, Dict
from io import BytesIO

logger = logging.getLogger(__name__)

class MockSerial:
    """模拟串口类，用于在PC上模拟串口功能"""
    
    def __init__(self, port: str, baudrate: int = 115200, timeout: Optional[float] = None):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._is_open = True
        self._buffer = BytesIO()
        self._read_pos = 0
        self._write_log: list = []
        
        logger.info(f"模拟串口: 创建串口设备 {port}, 波特率 {baudrate}")
    
    @property
    def is_open(self) -> bool:
        """检查串口是否打开"""
        return self._is_open
    
    def open(self) -> None:
        """打开串口"""
        if not self._is_open:
            self._is_open = True
            logger.info(f"模拟串口: 打开串口 {self.port}")
    
    def close(self) -> None:
        """关闭串口"""
        if self._is_open:
            self._is_open = False
            self._buffer.close()
            logger.info(f"模拟串口: 关闭串口 {self.port}")
    
    def write(self, data: bytes) -> int:
        """写入数据到串口"""
        if not self._is_open:
            logger.warning(f"模拟串口: 串口 {self.port} 未打开，无法写入")
            return 0
        
        written = len(data)
        self._buffer.write(data)
        self._write_log.append(data)
        
        logger.info(f"模拟串口: 向 {self.port} 写入 {written} 字节数据: {data.hex()}")
        return written
    
    def read(self, size: int = 1) -> bytes:
        """从串口读取数据"""
        if not self._is_open:
            logger.warning(f"模拟串口: 串口 {self.port} 未打开，无法读取")
            return b''
        
        # 模拟读取数据（返回空数据或模拟响应）
        if self._buffer.tell() > self._read_pos:
            self._buffer.seek(self._read_pos)
            data = self._buffer.read(size)
            self._read_pos = self._buffer.tell()
        else:
            # 模拟无数据可读的情况
            data = b''
            if self.timeout is not None:
                time.sleep(0.01)  # 模拟短暂等待
        
        logger.info(f"模拟串口: 从 {self.port} 读取 {len(data)} 字节数据: {data.hex()}")
        return data
    
    def readline(self) -> bytes:
        """读取一行数据"""
        if not self._is_open:
            return b''
        
        # 模拟读取一行数据（以换行符结尾）
        line = b"SIMULATED_RESPONSE\n"
        logger.info(f"模拟串口: 从 {self.port} 读取一行数据: {line.decode().strip()}")
        return line
    
    def flush(self) -> None:
        """刷新缓冲区"""
        logger.info(f"模拟串口: 刷新 {self.port} 缓冲区")
    
    def reset_input_buffer(self) -> None:
        """重置输入缓冲区"""
        self._read_pos = self._buffer.tell()
        logger.info(f"模拟串口: 重置 {self.port} 输入缓冲区")
    
    def reset_output_buffer(self) -> None:
        """重置输出缓冲区"""
        self._write_log.clear()
        logger.info(f"模拟串口: 重置 {self.port} 输出缓冲区")
    
    def get_write_log(self) -> list:
        """获取写入日志（用于测试）"""
        return self._write_log.copy()
    
    def simulate_response(self, response: bytes) -> None:
        """模拟接收到响应数据（用于测试）"""
        current_pos = self._buffer.tell()
        self._buffer.seek(0, 2)  # 移动到文件末尾
        self._buffer.write(response)
        self._buffer.seek(current_pos)  # 恢复原位置
        logger.info(f"模拟串口: 模拟接收到响应: {response.hex()}")

# 创建模拟串口工厂函数
def create_mock_serial(port: str, baudrate: int = 115200, timeout: Optional[float] = None) -> MockSerial:
    """创建模拟串口实例"""
    return MockSerial(port, baudrate, timeout)

# 模拟serial模块的接口
class Serial(MockSerial):
    """模拟的serial.Serial类，保持与真实serial模块相同的接口"""
    pass
