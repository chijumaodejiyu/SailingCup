#!/usr/bin/env python3
"""
串口调试工具
用于调试树莓派串口通信的交互式工具
"""

import serial
import time
import threading
import logging
import sys
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SerialDebugTool")

class SerialDebugTool:
    """串口调试工具类"""
    
    def __init__(self):
        self.serial_port = None
        self.is_connected = False
        self.receiving = False
        self.receive_thread = None
        self.send_history: List[Dict[str, Any]] = []
        self.receive_buffer: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # 默认串口参数
        self.port = "/dev/ttyUSB0"
        self.baudrate = 115200
        self.bytesize = serial.EIGHTBITS
        self.parity = serial.PARITY_NONE
        self.stopbits = serial.STOPBITS_ONE
        self.timeout = 1
        
        # 数据格式设置
        self.send_format = "ASCII"  # ASCII 或 HEX
        self.receive_format = "ASCII"  # ASCII 或 HEX
        self.auto_newline = True
        self.show_timestamp = True
        
    def list_available_ports(self) -> List[str]:
        """列出可用的串口设备"""
        ports = []
        # 在Linux系统上检查常见的串口设备
        common_ports = [
            "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2", "/dev/ttyUSB3",
            "/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyACM2", "/dev/ttyACM3",
            "/dev/ttyS0", "/dev/ttyS1", "/dev/ttyS2", "/dev/ttyS3"
        ]
        
        for port in common_ports:
            if os.path.exists(port):
                ports.append(port)
                
        return ports
    
    def connect(self, port: str, baudrate: int = 115200, 
                bytesize: int = serial.EIGHTBITS, parity: str = serial.PARITY_NONE,
                stopbits: float = serial.STOPBITS_ONE, timeout: float = 1) -> bool:
        """连接串口"""
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=timeout
            )
            
            self.port = port
            self.baudrate = baudrate
            self.bytesize = bytesize
            self.parity = parity
            self.stopbits = stopbits
            self.timeout = timeout
            self.is_connected = True
            
            logger.info(f"串口连接成功: {port} {baudrate}bps")
            return True
            
        except Exception as e:
            logger.error(f"串口连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开串口连接"""
        if self.serial_port and self.serial_port.is_open:
            self.stop_receiving()
            self.serial_port.close()
            self.is_connected = False
            logger.info("串口已断开")
    
    def start_receiving(self):
        """开始接收数据"""
        if not self.is_connected:
            logger.error("串口未连接，无法开始接收")
            return False
            
        self.receiving = True
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        logger.info("开始接收数据")
        return True
    
    def stop_receiving(self):
        """停止接收数据"""
        self.receiving = False
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2)
        logger.info("停止接收数据")
    
    def _receive_loop(self):
        """接收数据循环"""
        while self.receiving and self.is_connected:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        self._process_received_data(data)
                time.sleep(0.01)  # 短暂休眠，避免CPU占用过高
            except Exception as e:
                logger.error(f"接收数据错误: {e}")
                break
    
    def _process_received_data(self, data: bytes):
        """处理接收到的数据"""
        timestamp = datetime.now()
        
        # ASCII格式显示
        ascii_data = data.decode('ascii', errors='replace')
        
        # HEX格式显示
        hex_data = data.hex().upper()
        
        # 保存到缓冲区
        receive_entry = {
            'timestamp': timestamp,
            'raw_data': data,
            'ascii_data': ascii_data,
            'hex_data': hex_data,
            'length': len(data)
        }
        
        self.receive_buffer.append(receive_entry)
        
        # 限制缓冲区大小
        if len(self.receive_buffer) > self.max_history:
            self.receive_buffer.pop(0)
        
        # 实时显示接收到的数据
        self._display_received_data(receive_entry)
    
    def _display_received_data(self, data_entry: Dict[str, Any]):
        """显示接收到的数据"""
        timestamp_str = data_entry['timestamp'].strftime("%H:%M:%S.%f")[:-3]
        
        if self.receive_format == "ASCII":
            display_data = data_entry['ascii_data'].replace('\n', '\\n').replace('\r', '\\r')
        else:
            display_data = data_entry['hex_data']
            
        if self.show_timestamp:
            print(f"[{timestamp_str}] RX: {display_data}")
        else:
            print(f"RX: {display_data}")
    
    def send_data(self, data: str) -> bool:
        """发送数据"""
        if not self.is_connected:
            logger.error("串口未连接，无法发送数据")
            return False
            
        try:
            # 根据发送格式处理数据
            if self.send_format == "HEX":
                # HEX格式发送
                try:
                    # 移除空格和换行符
                    hex_data = data.replace(' ', '').replace('\n', '').replace('\r', '')
                    # 确保HEX字符串长度为偶数
                    if len(hex_data) % 2 != 0:
                        hex_data = '0' + hex_data
                    data_bytes = bytes.fromhex(hex_data)
                except ValueError as e:
                    logger.error(f"HEX格式错误: {e}")
                    return False
            else:
                # ASCII格式发送
                if self.auto_newline and not data.endswith('\n'):
                    data += '\n'
                data_bytes = data.encode('ascii')
            
            # 发送数据
            bytes_sent = self.serial_port.write(data_bytes)
            self.serial_port.flush()
            
            # 记录发送历史
            timestamp = datetime.now()
            send_entry = {
                'timestamp': timestamp,
                'raw_data': data_bytes,
                'sent_data': data,
                'format': self.send_format,
                'length': bytes_sent
            }
            self.send_history.append(send_entry)
            
            # 限制历史记录大小
            if len(self.send_history) > self.max_history:
                self.send_history.pop(0)
            
            # 显示发送的数据
            self._display_sent_data(send_entry)
            
            logger.info(f"发送数据成功: {bytes_sent} 字节")
            return True
            
        except Exception as e:
            logger.error(f"发送数据失败: {e}")
            return False
    
    def _display_sent_data(self, data_entry: Dict[str, Any]):
        """显示发送的数据"""
        timestamp_str = data_entry['timestamp'].strftime("%H:%M:%S.%f")[:-3]
        
        if self.send_format == "ASCII":
            display_data = data_entry['sent_data'].replace('\n', '\\n').replace('\r', '\\r')
        else:
            display_data = data_entry['raw_data'].hex().upper()
            
        if self.show_timestamp:
            print(f"[{timestamp_str}] TX: {display_data}")
        else:
            print(f"TX: {display_data}")
    
    def clear_receive_buffer(self):
        """清空接收缓冲区"""
        self.receive_buffer.clear()
        logger.info("接收缓冲区已清空")
    
    def clear_send_history(self):
        """清空发送历史"""
        self.send_history.clear()
        logger.info("发送历史已清空")
    
    def save_receive_data(self, filename: str = None) -> bool:
        """保存接收到的数据到文件"""
        if not self.receive_buffer:
            logger.warning("没有接收数据可保存")
            return False
            
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"serial_receive_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("串口接收数据记录\n")
                f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"端口: {self.port}\n")
                f.write(f"波特率: {self.baudrate}\n")
                f.write("=" * 50 + "\n\n")
                
                for entry in self.receive_buffer:
                    timestamp_str = entry['timestamp'].strftime("%H:%M:%S.%f")[:-3]
                    f.write(f"[{timestamp_str}] ")
                    f.write(f"ASCII: {entry['ascii_data']} | ")
                    f.write(f"HEX: {entry['hex_data']}\n")
            
            logger.info(f"接收数据已保存到: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"保存接收数据失败: {e}")
            return False
    
    def save_send_history(self, filename: str = None) -> bool:
        """保存发送历史到文件"""
        if not self.send_history:
            logger.warning("没有发送历史可保存")
            return False
            
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"serial_send_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("串口发送历史记录\n")
                f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"端口: {self.port}\n")
                f.write(f"波特率: {self.baudrate}\n")
                f.write("=" * 50 + "\n\n")
                
                for entry in self.send_history:
                    timestamp_str = entry['timestamp'].strftime("%H:%M:%S.%f")[:-3]
                    f.write(f"[{timestamp_str}] ")
                    f.write(f"格式: {entry['format']} | ")
                    f.write(f"数据: {entry['sent_data']}\n")
            
            logger.info(f"发送历史已保存到: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"保存发送历史失败: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取工具状态"""
        return {
            'connected': self.is_connected,
            'receiving': self.receiving,
            'port': self.port,
            'baudrate': self.baudrate,
            'send_format': self.send_format,
            'receive_format': self.receive_format,
            'receive_count': len(self.receive_buffer),
            'send_count': len(self.send_history)
        }


def interactive_mode():
    """交互式模式"""
    tool = SerialDebugTool()
    
    print("=" * 60)
    print("串口调试工具")
    print("=" * 60)
    
    while True:
        print("\n=== 主菜单 ===")
        print("1. 列出可用串口")
        print("2. 连接串口")
        print("3. 断开串口")
        print("4. 开始接收数据")
        print("5. 停止接收数据")
        print("6. 发送数据")
        print("7. 设置参数")
        print("8. 查看状态")
        print("9. 保存数据")
        print("10. 清空缓冲区")
        print("0. 退出")
        
        choice = input("请选择操作: ").strip()
        
        if choice == "1":
            # 列出可用串口
            ports = tool.list_available_ports()
            if ports:
                print("可用串口:")
                for i, port in enumerate(ports, 1):
                    print(f"  {i}. {port}")
            else:
                print("未找到可用串口")
                
        elif choice == "2":
            # 连接串口
            port = input("请输入串口设备路径 (如 /dev/ttyUSB0): ").strip()
            if not port:
                print("请输入有效的串口路径")
                continue
                
            baudrate = input("请输入波特率 (默认 115200): ").strip()
            if not baudrate:
                baudrate = 115200
            else:
                try:
                    baudrate = int(baudrate)
                except ValueError:
                    print("波特率必须是数字")
                    continue
            
            if tool.connect(port, baudrate):
                print("串口连接成功")
            else:
                print("串口连接失败")
                
        elif choice == "3":
            # 断开串口
            tool.disconnect()
            print("串口已断开")
            
        elif choice == "4":
            # 开始接收数据
            if tool.start_receiving():
                print("开始接收数据...")
            else:
                print("无法开始接收数据")
                
        elif choice == "5":
            # 停止接收数据
            tool.stop_receiving()
            print("停止接收数据")
            
        elif choice == "6":
            # 发送数据
            if not tool.is_connected:
                print("请先连接串口")
                continue
                
            data = input("请输入要发送的数据: ").strip()
            if not data:
                print("请输入有效数据")
                continue
                
            if tool.send_data(data):
                print("数据发送成功")
            else:
                print("数据发送失败")
                
        elif choice == "7":
            # 设置参数
            print("\n=== 参数设置 ===")
            print("1. 设置发送格式 (当前: {})".format(tool.send_format))
            print("2. 设置接收格式 (当前: {})".format(tool.receive_format))
            print("3. 设置自动换行 (当前: {})".format(tool.auto_newline))
            print("4. 设置显示时间戳 (当前: {})".format(tool.show_timestamp))
            
            sub_choice = input("请选择要设置的参数: ").strip()
            
            if sub_choice == "1":
                format_choice = input("选择发送格式 (1.ASCII 2.HEX): ").strip()
                if format_choice == "1":
                    tool.send_format = "ASCII"
                    print("发送格式设置为 ASCII")
                elif format_choice == "2":
                    tool.send_format = "HEX"
                    print("发送格式设置为 HEX")
                else:
                    print("无效选择")
                    
            elif sub_choice == "2":
                format_choice = input("选择接收格式 (1.ASCII 2.HEX): ").strip()
                if format_choice == "1":
                    tool.receive_format = "ASCII"
                    print("接收格式设置为 ASCII")
                elif format_choice == "2":
                    tool.receive_format = "HEX"
                    print("接收格式设置为 HEX")
                else:
                    print("无效选择")
                    
            elif sub_choice == "3":
                auto_newline = input("启用自动换行? (y/n): ").strip().lower()
                tool.auto_newline = auto_newline == 'y'
                print("自动换行 {}".format("启用" if tool.auto_newline else "禁用"))
                
            elif sub_choice == "4":
                show_ts = input("显示时间戳? (y/n): ").strip().lower()
                tool.show_timestamp = show_ts == 'y'
                print("时间戳显示 {}".format("启用" if tool.show_timestamp else "禁用"))
            else:
                print("无效选择")
                
        elif choice == "8":
            # 查看状态
            status = tool.get_status()
            print("\n=== 工具状态 ===")
            for key, value in status.items():
                print(f"{key}: {value}")
                
        elif choice == "9":
            # 保存数据
            print("\n=== 保存数据 ===")
            print("1. 保存接收数据")
            print("2. 保存发送历史")
            
            sub_choice = input("请选择: ").strip()
            
            if sub_choice == "1":
                filename = input("输入文件名 (留空使用默认名称): ").strip()
                if not filename:
                    filename = None
                if tool.save_receive_data(filename):
                    print("接收数据保存成功")
                else:
                    print("接收数据保存失败")
                    
            elif sub_choice == "2":
                filename = input("输入文件名 (留空使用默认名称): ").strip()
                if not filename:
                    filename = None
                if tool.save_send_history(filename):
                    print("发送历史保存成功")
                else:
                    print("发送历史保存失败")
            else:
                print("无效选择")
                
        elif choice == "10":
            # 清空缓冲区
            print("\n=== 清空缓冲区 ===")
            print("1. 清空接收缓冲区")
            print("2. 清空发送历史")
            print("3. 清空全部")
            
            sub_choice = input("请选择: ").strip()
            
            if sub_choice == "1":
                tool.clear_receive_buffer()
                print("接收缓冲区已清空")
            elif sub_choice == "2":
                tool.clear_send_history()
                print("发送历史已清空")
            elif sub_choice == "3":
                tool.clear_receive_buffer()
                tool.clear_send_history()
                print("全部缓冲区已清空")
            else:
                print("无效选择")
                
        elif choice == "0":
            # 退出
            tool.disconnect()
            print("谢谢使用!")
            break
            
        else:
            print("无效选择，请重新输入")


if __name__ == "__main__":
    try:
        interactive_mode()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行错误: {e}")
