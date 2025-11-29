"""
步进电机调试工具（基于stepper库）
用于调试和控制树莓派上的步进电机，使用zdt_stepper第三方库
"""

import time
import threading
import logging
import argparse
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import serial.tools.list_ports

from stepper.device import Device
from stepper.stepper_core.parameters import DeviceParams
from stepper.stepper_core.configs import Address
from mods.DeviceManager import DeviceManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StepperCommand(Enum):
    """步进电机命令枚举"""
    MOVE_ABS = "MOVE_ABS"      # 绝对位置移动
    MOVE_REL = "MOVE_REL"      # 相对位置移动
    STOP = "STOP"              # 停止
    SET_SPEED = "SET_SPEED"    # 设置速度
    SET_ACCEL = "SET_ACCEL"    # 设置加速度
    GET_STATUS = "GET_STATUS"  # 获取状态
    ENABLE = "ENABLE"          # 启用设备
    DISABLE = "DISABLE"        # 禁用设备
    HOME = "HOME"              # 回零

class StepperDebugTool:
    """基于stepper库的步进电机调试工具"""
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200, address: int = 1,
                 autoconnect: bool = False, scan_timeout: float = 5.0, max_retries: int = 3):
        """
        初始化步进电机调试工具
        
        Args:
            port: 串口端口
            baudrate: 波特率
            address: 设备地址
            autoconnect: 是否自动扫描并连接设备
            scan_timeout: 扫描超时时间（秒）
            max_retries: 最大重试次数
        """
        self.port = port
        self.baudrate = baudrate
        self.address = address
        self.autoconnect = autoconnect
        self.scan_timeout = scan_timeout
        self.max_retries = max_retries
        
        # 设备管理器
        self.device_manager = DeviceManager()
        self.device = None
        self.is_connected = False
        
        # 调试参数
        self.command_history: List[Dict[str, Any]] = []
        self.status_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # 步进电机状态
        self.current_position = 0
        self.target_position = 0
        self.current_speed = 500  # 默认速度（步/秒）
        self.current_acceleration = 1000  # 默认加速度（步/秒²）
        self.is_moving = False
        self.is_enabled = False
        
        # 线程控制
        self.monitoring = False
        self.monitor_thread = None
        
        logger.info(f"步进电机调试工具初始化完成，端口: {port}, 波特率: {baudrate}, 地址: {address}")
        logger.info(f"自动连接: {'启用' if autoconnect else '禁用'}")
    
    def scan_ports(self) -> List[str]:
        """扫描可用的串口设备"""
        try:
            ports = serial.tools.list_ports.comports()
            available_ports = []
            
            for port in ports:
                port_info = {
                    'device': port.device,
                    'description': port.description,
                    'hwid': port.hwid,
                    'vid': port.vid if port.vid else None,
                    'pid': port.pid if port.pid else None
                }
                available_ports.append(port_info)
                logger.info(f"发现串口: {port.device} - {port.description}")
            
            return available_ports
        except Exception as e:
            logger.error(f"扫描串口失败: {e}")
            return []
    
    def _connect_to_port(self, port: str) -> bool:
        """尝试连接到指定端口"""
        try:
            # 先关闭现有连接
            if self.is_connected:
                self.disconnect()
            
            # 注册串口设备
            self.device_manager.register_serial("debug_device", port, self.baudrate)
            
            # 获取串口设备
            serial_device = self.device_manager.get_device("debug_device")
            
            # 初始化步进电机设备
            self.device = Device(
                device_params=DeviceParams(
                    serial_connection=serial_device,
                    address=Address(self.address)
                )
            )
            
            # 验证设备连接
            if self._validate_device():
                self.port = port  # 更新当前端口
                self.is_connected = True
                logger.info(f"设备连接成功: {port}")
                return True
            else:
                logger.warning(f"设备验证失败: {port}")
                self.disconnect()
                return False
                
        except Exception as e:
            logger.debug(f"连接端口 {port} 失败: {e}")
            return False
    
    def _validate_device(self) -> bool:
        """验证设备是否正常工作"""
        try:
            # 尝试获取设备状态来验证连接
            # 这里可以根据实际设备协议添加更复杂的验证逻辑
            if self.device:
                # 简单的状态检查
                status = self.get_status()
                return 'error' not in status
            return False
        except Exception as e:
            logger.debug(f"设备验证失败: {e}")
            return False
    
    def connect(self) -> bool:
        """连接设备"""
        if self.autoconnect:
            return self._autoconnect()
        else:
            return self._connect_to_port(self.port)
    
    def _autoconnect(self) -> bool:
        """自动扫描并连接设备"""
        logger.info("开始自动扫描串口设备...")
        
        start_time = time.time()
        retry_count = 0
        
        while retry_count < self.max_retries:
            # 扫描可用串口
            available_ports = self.scan_ports()
            
            if not available_ports:
                logger.warning("未发现可用串口设备")
                time.sleep(1)  # 等待1秒后重试
                retry_count += 1
                continue
            
            # 尝试连接每个可用串口
            for port_info in available_ports:
                port = port_info['device']
                logger.info(f"尝试连接串口: {port}")
                
                if self._connect_to_port(port):
                    logger.info(f"自动连接成功: {port}")
                    return True
                
                # 检查是否超时
                if time.time() - start_time > self.scan_timeout:
                    logger.warning(f"扫描超时 ({self.scan_timeout}秒)")
                    return False
            
            # 等待一段时间后重试
            logger.info(f"扫描完成，等待重试... (重试次数: {retry_count + 1}/{self.max_retries})")
            time.sleep(2)
            retry_count += 1
        
        logger.error(f"自动连接失败，达到最大重试次数: {self.max_retries}")
        return False
    
    def disconnect(self):
        """断开设备连接"""
        self.stop_monitoring()
        
        if self.device:
            try:
                self.device.stop()
                self.device.disable()
            except Exception as e:
                logger.error(f"设备停止失败: {e}")
        
        try:
            self.device_manager.close_all()
        except Exception as e:
            logger.error(f"设备管理器关闭失败: {e}")
        
        self.device = None
        self.is_connected = False
        logger.info("设备已断开")
    
    def enable_device(self) -> bool:
        """启用设备"""
        if not self.is_connected:
            logger.error("设备未连接")
            return False
        
        try:
            self.device.enable()
            self.is_enabled = True
            self._log_command(StepperCommand.ENABLE)
            logger.info("设备已启用")
            return True
        except Exception as e:
            logger.error(f"设备启用失败: {e}")
            return False
    
    def disable_device(self) -> bool:
        """禁用设备"""
        if not self.is_connected:
            logger.error("设备未连接")
            return False
        
        try:
            self.device.disable()
            self.is_enabled = False
            self._log_command(StepperCommand.DISABLE)
            logger.info("设备已禁用")
            return True
        except Exception as e:
            logger.error(f"设备禁用失败: {e}")
            return False
    
    def move_absolute(self, position: int) -> bool:
        """绝对位置移动"""
        if not self.is_connected or not self.is_enabled:
            logger.error("设备未连接或未启用")
            return False
        
        try:
            # 设置运动参数
            self.device.set_speed(self.current_speed)
            self.device.set_acceleration(self.current_acceleration)
            
            # 执行绝对位置移动
            self.device.move_to(position)
            self.target_position = position
            
            self._log_command(StepperCommand.MOVE_ABS, str(position))
            logger.info(f"绝对位置移动: {position} 步")
            return True
            
        except Exception as e:
            logger.error(f"绝对位置移动失败: {e}")
            return False
    
    def move_relative(self, steps: int) -> bool:
        """相对位置移动"""
        if not self.is_connected or not self.is_enabled:
            logger.error("设备未连接或未启用")
            return False
        
        try:
            # 设置运动参数
            self.device.set_speed(self.current_speed)
            self.device.set_acceleration(self.current_acceleration)
            
            # 执行相对位置移动
            self.device.move(steps)
            self.target_position = self.current_position + steps
            
            self._log_command(StepperCommand.MOVE_REL, str(steps))
            logger.info(f"相对位置移动: {steps} 步")
            return True
            
        except Exception as e:
            logger.error(f"相对位置移动失败: {e}")
            return False
    
    def stop(self) -> bool:
        """停止运动"""
        if not self.is_connected:
            logger.error("设备未连接")
            return False
        
        try:
            self.device.stop()
            self._log_command(StepperCommand.STOP)
            logger.info("运动已停止")
            return True
        except Exception as e:
            logger.error(f"停止运动失败: {e}")
            return False
    
    def set_speed(self, speed: int) -> bool:
        """设置速度"""
        if not self.is_connected:
            logger.error("设备未连接")
            return False
        
        try:
            self.device.set_speed(speed)
            self.current_speed = speed
            self._log_command(StepperCommand.SET_SPEED, str(speed))
            logger.info(f"速度设置为: {speed} 步/秒")
            return True
        except Exception as e:
            logger.error(f"设置速度失败: {e}")
            return False
    
    def set_acceleration(self, acceleration: int) -> bool:
        """设置加速度"""
        if not self.is_connected:
            logger.error("设备未连接")
            return False
        
        try:
            self.device.set_acceleration(acceleration)
            self.current_acceleration = acceleration
            self._log_command(StepperCommand.SET_ACCEL, str(acceleration))
            logger.info(f"加速度设置为: {acceleration} 步/秒²")
            return True
        except Exception as e:
            logger.error(f"设置加速度失败: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取设备状态"""
        if not self.is_connected:
            return {'error': '设备未连接'}
        
        try:
            # 获取设备状态
            self.is_moving = not self.device.is_in_position
            
            # 更新当前位置（这里需要根据实际协议获取）
            # 在实际应用中，可能需要通过特定的状态查询命令获取当前位置
            if not self.is_moving:
                self.current_position = self.target_position
            
            status = {
                'position': self.current_position,
                'target_position': self.target_position,
                'speed': self.current_speed,
                'acceleration': self.current_acceleration,
                'is_moving': self.is_moving,
                'is_enabled': self.is_enabled,
                'is_connected': self.is_connected,
                'timestamp': datetime.now()
            }
            
            # 记录状态历史
            self.status_history.append(status.copy())
            if len(self.status_history) > self.max_history:
                self.status_history.pop(0)
            
            self._log_command(StepperCommand.GET_STATUS)
            return status
            
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return {'error': str(e)}
    
    def home(self) -> bool:
        """回零操作"""
        if not self.is_connected or not self.is_enabled:
            logger.error("设备未连接或未启用")
            return False
        
        try:
            # 这里需要根据具体的回零协议实现
            # 假设回零到位置0
            return self.move_absolute(0)
        except Exception as e:
            logger.error(f"回零操作失败: {e}")
            return False
    
    def start_monitoring(self):
        """开始监控设备状态"""
        if self.monitoring:
            logger.warning("监控已在进行中")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("开始监控设备状态")
    
    def stop_monitoring(self):
        """停止监控设备状态"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
        logger.info("停止监控设备状态")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring and self.is_connected:
            try:
                # 定期获取状态
                status = self.get_status()
                if 'error' not in status:
                    logger.debug(f"监控状态 - 位置: {status['position']}, 移动: {status['is_moving']}")
                
                time.sleep(0.1)  # 监控间隔
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                break
    
    def _log_command(self, command: StepperCommand, value: Optional[str] = None):
        """记录命令历史"""
        timestamp = datetime.now()
        command_entry = {
            'timestamp': timestamp,
            'command': command.value,
            'value': value,
            'position': self.current_position
        }
        self.command_history.append(command_entry)
        
        # 限制历史记录大小
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前状态（简化版）"""
        return self.get_status()
    
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
                        'position': entry['position']
                    }
                    history_data.append(serializable_entry)
                
                json.dump(history_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"命令历史已保存到: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"保存命令历史失败: {e}")
            return False
    
    def save_status_history(self, filename: str = None) -> bool:
        """保存状态历史到文件"""
        if not self.status_history:
            logger.warning("没有状态历史可保存")
            return False
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stepper_status_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # 转换为可序列化的格式
                history_data = []
                for entry in self.status_history:
                    serializable_entry = entry.copy()
                    serializable_entry['timestamp'] = serializable_entry['timestamp'].isoformat()
                    history_data.append(serializable_entry)
                
                json.dump(history_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"状态历史已保存到: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"保存状态历史失败: {e}")
            return False
    
    def clear_history(self):
        """清空历史记录"""
        self.command_history.clear()
        self.status_history.clear()
        logger.info("历史记录已清空")

def main():
    """主函数 - 命令行界面"""
    parser = argparse.ArgumentParser(description='基于stepper库的步进电机调试工具')
    parser.add_argument('--port', '-p', default='/dev/ttyUSB0', help='串口端口')
    parser.add_argument('--baudrate', '-b', type=int, default=115200, help='波特率')
    parser.add_argument('--address', '-a', type=int, default=1, help='设备地址')
    parser.add_argument('--autoconnect', action='store_true', help='自动扫描并连接设备')
    parser.add_argument('--scan-timeout', type=float, default=5.0, help='扫描超时时间（秒）')
    parser.add_argument('--max-retries', type=int, default=3, help='最大重试次数')
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # 连接命令
    connect_parser = subparsers.add_parser('connect', help='连接设备')
    
    # 启用/禁用命令
    enable_parser = subparsers.add_parser('enable', help='启用设备')
    disable_parser = subparsers.add_parser('disable', help='禁用设备')
    
    # 移动命令
    move_abs_parser = subparsers.add_parser('move_abs', help='绝对位置移动')
    move_abs_parser.add_argument('position', type=int, help='目标位置（步数）')
    
    move_rel_parser = subparsers.add_parser('move_rel', help='相对位置移动')
    move_rel_parser.add_argument('steps', type=int, help='移动步数')
    
    # 停止命令
    stop_parser = subparsers.add_parser('stop', help='停止运动')
    
    # 参数设置命令
    speed_parser = subparsers.add_parser('speed', help='设置速度')
    speed_parser.add_argument('speed', type=int, help='速度值（步/秒）')
    
    accel_parser = subparsers.add_parser('accel', help='设置加速度')
    accel_parser.add_argument('acceleration', type=int, help='加速度值（步/秒²）')
    
    # 状态命令
    status_parser = subparsers.add_parser('status', help='获取状态')
    
    # 回零命令
    home_parser = subparsers.add_parser('home', help='回零操作')
    
    # 监控命令
    monitor_parser = subparsers.add_parser('monitor', help='开始监控')
    monitor_parser.add_argument('action', choices=['start', 'stop'], help='监控动作')
    
    # 保存命令
    save_parser = subparsers.add_parser('save', help='保存历史记录')
    save_parser.add_argument('type', choices=['commands', 'status'], help='保存类型')
    save_parser.add_argument('--filename', '-f', help='文件名')
    
    args = parser.parse_args()
    
    # 创建调试工具实例
    tool = StepperDebugTool(
        port=args.port, 
        baudrate=args.baudrate, 
        address=args.address,
        autoconnect=args.autoconnect,
        scan_timeout=args.scan_timeout,
        max_retries=args.max_retries
    )
    
    if args.command == 'connect':
        if tool.connect():
            print("连接成功")
        else:
            print("连接失败")
    
    elif args.command == 'enable':
        if tool.connect():
            success = tool.enable_device()
            print(f"设备启用{'成功' if success else '失败'}")
    
    elif args.command == 'disable':
        if tool.connect():
            success = tool.disable_device()
            print(f"设备禁用{'成功' if success else '失败'}")
    
    elif args.command == 'move_abs':
        if tool.connect():
            if tool.enable_device():
                success = tool.move_absolute(args.position)
                print(f"绝对位置移动命令{'成功' if success else '失败'}")
    
    elif args.command == 'move_rel':
        if tool.connect():
            if tool.enable_device():
                success = tool.move_relative(args.steps)
                print(f"相对位置移动命令{'成功' if success else '失败'}")
    
    elif args.command == 'stop':
        if tool.connect():
            success = tool.stop()
            print(f"停止命令{'成功' if success else '失败'}")
    
    elif args.command == 'speed':
        if tool.connect():
            success = tool.set_speed(args.speed)
            print(f"速度设置命令{'成功' if success else '失败'}")
    
    elif args.command == 'accel':
        if tool.connect():
            success = tool.set_acceleration(args.acceleration)
            print(f"加速度设置命令{'成功' if success else '失败'}")
    
    elif args.command == 'status':
        if tool.connect():
            status = tool.get_status()
            if 'error' not in status:
                print(f"设备状态:")
                print(f"  当前位置: {status['position']}")
                print(f"  目标位置: {status['target_position']}")
                print(f"  速度: {status['speed']} 步/秒")
                print(f"  加速度: {status['acceleration']} 步/秒²")
                print(f"  是否移动: {'是' if status['is_moving'] else '否'}")
                print(f"  是否启用: {'是' if status['is_enabled'] else '否'}")
                print(f"  是否连接: {'是' if status['is_connected'] else '否'}")
            else:
                print(f"获取状态失败: {status['error']}")
    
    elif args.command == 'home':
        if tool.connect():
            if tool.enable_device():
                success = tool.home()
                print(f"回零命令{'成功' if success else '失败'}")
    
    elif args.command == 'monitor':
        if tool.connect():
            if tool.enable_device():
                if args.action == 'start':
                    tool.start_monitoring()
                    print("开始监控，按Ctrl+C停止")
                    try:
                        while True:
                            status = tool.get_current_status()
                            if 'error' not in status:
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
            success = tool.save_status_history(args.filename)
            print(f"状态历史保存{'成功' if success else '失败'}")
    
    else:
        parser.print_help()
    
    # 断开连接
    tool.disconnect()

if __name__ == "__main__":
    main()
