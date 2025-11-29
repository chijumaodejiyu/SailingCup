"""
步进电机调试工具
用于调试和控制树莓派上的步进电机
"""

import serial
import time
import threading
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import json
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StepperCommand(Enum):
    """步进电机命令枚举"""
    MOVE_CW = "CW"      # 顺时针转动
    MOVE_CCW = "CCW"    # 逆时针转动
    STOP = "STOP"       # 停止
    SET_SPEED = "SPD"   # 设置速度
    SET_POSITION = "POS" # 设置位置
    GET_STATUS = "STAT" # 获取状态
    RESET = "RST"       # 复位
    HOME = "HOME"       # 回零

class StepperDebugTool:
    """步进电机调试工具"""
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200):
        """
        初始化步进电机调试工具
        
        Args:
            port: 串口端口
            baudrate: 波特率
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_port = None
        self.is_connected = False
        
        # 调试参数
        self.command_history: List[Dict[str, Any]] = []
        self.response_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # 步进电机状态
        self.current_position = 0
        self.target_position = 0
        self.current_speed = 100  # 默认速度
        self.is_moving = False
        self.direction = "STOP"
        
        # 线程控制
        self.monitoring = False
        self.monitor_thread = None
        
        # 配置参数
        self.steps_per_revolution = 200  # 每转步数
        self.microstepping = 16          # 微步细分
        
        logger.info(f"步进电机调试工具初始化完成，端口: {port}, 波特率: {baudrate}")
    
    def connect(self) -> bool:
        """连接串口"""
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            self.is_connected = True
            logger.info(f"串口连接成功: {self.port}")
            return True
        except Exception as e:
            logger.error(f"串口连接失败: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """断开串口连接"""
        self.stop_monitoring()
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False
        logger.info("串口已断开")
    
    def send_command(self, command: StepperCommand, value: Optional[str] = None) -> bool:
        """
        发送步进电机命令
        
        Args:
            command: 命令类型
            value: 命令参数值
            
        Returns:
            bool: 发送是否成功
        """
        if not self.is_connected:
            logger.error("串口未连接，无法发送命令")
            return False
        
        # 构建命令字符串
        if value:
            cmd_str = f"{command.value} {value}\n"
        else:
            cmd_str = f"{command.value}\n"
        
        try:
            # 发送命令
            bytes_sent = self.serial_port.write(cmd_str.encode())
            self.serial_port.flush()
            
            # 记录命令历史
            timestamp = datetime.now()
            command_entry = {
                'timestamp': timestamp,
                'command': command.value,
                'value': value,
                'raw_command': cmd_str.strip(),
                'bytes_sent': bytes_sent
            }
            self.command_history.append(command_entry)
            
            # 限制历史记录大小
            if len(self.command_history) > self.max_history:
                self.command_history.pop(0)
            
            logger.info(f"发送命令: {cmd_str.strip()}")
            return True
            
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            return False
    
    def read_response(self, timeout: float = 1.0) -> Optional[str]:
        """
        读取响应
        
        Args:
            timeout: 超时时间(秒)
            
        Returns:
            Optional[str]: 响应字符串，超时返回None
        """
        if not self.is_connected:
            return None
        
        start_time = time.time()
        response_lines = []
        
        while time.time() - start_time < timeout:
            if self.serial_port.in_waiting > 0:
                try:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        response_lines.append(line)
                        
                        # 记录响应历史
                        timestamp = datetime.now()
                        response_entry = {
                            'timestamp': timestamp,
                            'response': line,
                            'raw_data': line.encode()
                        }
                        self.response_history.append(response_entry)
                        
                        # 限制历史记录大小
                        if len(self.response_history) > self.max_history:
                            self.response_history.pop(0)
                        
                        logger.info(f"收到响应: {line}")
                except Exception as e:
                    logger.error(f"读取响应失败: {e}")
                    break
        
        return '\n'.join(response_lines) if response_lines else None
    
    def move_clockwise(self, steps: int) -> bool:
        """顺时针转动指定步数"""
        return self.send_command(StepperCommand.MOVE_CW, str(steps))
    
    def move_counterclockwise(self, steps: int) -> bool:
        """逆时针转动指定步数"""
        return self.send_command(StepperCommand.MOVE_CCW, str(steps))
    
    def stop(self) -> bool:
        """停止电机"""
        return self.send_command(StepperCommand.STOP)
    
    def set_speed(self, speed: int) -> bool:
        """设置电机速度"""
        return self.send_command(StepperCommand.SET_SPEED, str(speed))
    
    def set_position(self, position: int) -> bool:
        """设置目标位置"""
        return self.send_command(StepperCommand.SET_POSITION, str(position))
    
    def get_status(self) -> bool:
        """获取电机状态"""
        return self.send_command(StepperCommand.GET_STATUS)
    
    def reset(self) -> bool:
        """复位电机"""
        return self.send_command(StepperCommand.RESET)
    
    def home(self) -> bool:
        """回零操作"""
        return self.send_command(StepperCommand.HOME)
    
    def start_monitoring(self):
        """开始监控电机状态"""
        if self.monitoring:
            logger.warning("监控已在进行中")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("开始监控电机状态")
    
    def stop_monitoring(self):
        """停止监控电机状态"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
        logger.info("停止监控电机状态")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring and self.is_connected:
            try:
                # 定期获取状态
                if self.send_command(StepperCommand.GET_STATUS):
                    response = self.read_response(timeout=0.5)
                    if response:
                        self._parse_status_response(response)
                
                time.sleep(0.1)  # 监控间隔
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                break
    
    def _parse_status_response(self, response: str):
        """解析状态响应"""
        try:
            # 简单的状态解析逻辑，实际应根据具体协议实现
            if "POS:" in response:
                # 解析位置信息
                pos_str = response.split("POS:")[1].split()[0]
                self.current_position = int(pos_str)
            
            if "SPD:" in response:
                # 解析速度信息
                spd_str = response.split("SPD:")[1].split()[0]
                self.current_speed = int(spd_str)
            
            if "MOVING" in response:
                self.is_moving = True
            elif "STOP" in response:
                self.is_moving = False
            
            logger.debug(f"状态更新 - 位置: {self.current_position}, 速度: {self.current_speed}, 移动: {self.is_moving}")
            
        except Exception as e:
            logger.error(f"解析状态响应失败: {e}")
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            'position': self.current_position,
            'speed': self.current_speed,
            'is_moving': self.is_moving,
            'direction': self.direction,
            'connected': self.is_connected
        }
    
    def save_command_history(self, filename: str = None) -> bool:
        """保存命令历史到文件"""
        if not self.command_history:
            logger.warning("没有命令历史可保存")
            return False
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stepper_commands_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # 转换为可序列化的格式
                history_data = []
                for entry in self.command_history:
                    serializable_entry = {
                        'timestamp': entry['timestamp'].isoformat(),
                        'command': entry['command'],
                        'value': entry['value'],
                        'raw_command': entry['raw_command'],
                        'bytes_sent': entry['bytes_sent']
                    }
                    history_data.append(serializable_entry)
                
                json.dump(history_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"命令历史已保存到: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"保存命令历史失败: {e}")
            return False
    
    def save_response_history(self, filename: str = None) -> bool:
        """保存响应历史到文件"""
        if not self.response_history:
            logger.warning("没有响应历史可保存")
            return False
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stepper_responses_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # 转换为可序列化的格式
                history_data = []
                for entry in self.response_history:
                    serializable_entry = {
                        'timestamp': entry['timestamp'].isoformat(),
                        'response': entry['response'],
                        'raw_data': entry['raw_data'].hex() if entry['raw_data'] else ''
                    }
                    history_data.append(serializable_entry)
                
                json.dump(history_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"响应历史已保存到: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"保存响应历史失败: {e}")
            return False
    
    def clear_history(self):
        """清空历史记录"""
        self.command_history.clear()
        self.response_history.clear()
        logger.info("历史记录已清空")

def main():
    """主函数 - 命令行界面"""
    import argparse
    
    parser = argparse.ArgumentParser(description='步进电机调试工具')
    parser.add_argument('--port', '-p', default='/dev/ttyUSB0', help='串口端口')
    parser.add_argument('--baudrate', '-b', type=int, default=115200, help='波特率')
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # 连接命令
    connect_parser = subparsers.add_parser('connect', help='连接串口')
    
    # 移动命令
    move_parser = subparsers.add_parser('move', help='移动电机')
    move_parser.add_argument('direction', choices=['cw', 'ccw'], help='方向: cw(顺时针), ccw(逆时针)')
    move_parser.add_argument('steps', type=int, help='步数')
    
    # 停止命令
    stop_parser = subparsers.add_parser('stop', help='停止电机')
    
    # 速度命令
    speed_parser = subparsers.add_parser('speed', help='设置速度')
    speed_parser.add_argument('speed', type=int, help='速度值')
    
    # 位置命令
    position_parser = subparsers.add_parser('position', help='设置位置')
    position_parser.add_argument('position', type=int, help='目标位置')
    
    # 状态命令
    status_parser = subparsers.add_parser('status', help='获取状态')
    
    # 复位命令
    reset_parser = subparsers.add_parser('reset', help='复位电机')
    
    # 回零命令
    home_parser = subparsers.add_parser('home', help='回零操作')
    
    # 监控命令
    monitor_parser = subparsers.add_parser('monitor', help='开始监控')
    monitor_parser.add_argument('action', choices=['start', 'stop'], help='监控动作')
    
    # 保存命令
    save_parser = subparsers.add_parser('save', help='保存历史记录')
    save_parser.add_argument('type', choices=['commands', 'responses'], help='保存类型')
    save_parser.add_argument('--filename', '-f', help='文件名')
    
    args = parser.parse_args()
    
    # 创建调试工具实例
    tool = StepperDebugTool(port=args.port, baudrate=args.baudrate)
    
    if args.command == 'connect':
        if tool.connect():
            print("连接成功")
        else:
            print("连接失败")
    
    elif args.command == 'move':
        if tool.connect():
            if args.direction == 'cw':
                success = tool.move_clockwise(args.steps)
            else:
                success = tool.move_counterclockwise(args.steps)
            print(f"移动命令发送{'成功' if success else '失败'}")
    
    elif args.command == 'stop':
        if tool.connect():
            success = tool.stop()
            print(f"停止命令发送{'成功' if success else '失败'}")
    
    elif args.command == 'speed':
        if tool.connect():
            success = tool.set_speed(args.speed)
            print(f"速度设置命令发送{'成功' if success else '失败'}")
    
    elif args.command == 'position':
        if tool.connect():
            success = tool.set_position(args.position)
            print(f"位置设置命令发送{'成功' if success else '失败'}")
    
    elif args.command == 'status':
        if tool.connect():
            success = tool.get_status()
            if success:
                response = tool.read_response(timeout=1.0)
                if response:
                    print(f"状态响应: {response}")
                else:
                    print("未收到状态响应")
            else:
                print("状态查询命令发送失败")
    
    elif args.command == 'reset':
        if tool.connect():
            success = tool.reset()
            print(f"复位命令发送{'成功' if success else '失败'}")
    
    elif args.command == 'home':
        if tool.connect():
            success = tool.home()
            print(f"回零命令发送{'成功' if success else '失败'}")
    
    elif args.command == 'monitor':
        if tool.connect():
            if args.action == 'start':
                tool.start_monitoring()
                print("开始监控，按Ctrl+C停止")
                try:
                    while True:
                        status = tool.get_current_status()
                        print(f"当前位置: {status['position']}, 速度: {status['speed']}, 移动: {status['is_moving']}")
                        time.sleep(1)
                except KeyboardInterrupt:
                    tool.stop_monitoring()
                    print("监控已停止")
            else:
                tool.stop_monitoring()
                print("监控已停止")
    
    elif args.command == 'save':
        if args.type == 'commands':
            success = tool.save_command_history(args.filename)
            print(f"命令历史保存{'成功' if success else '失败'}")
        else:
            success = tool.save_response_history(args.filename)
            print(f"响应历史保存{'成功' if success else '失败'}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
