from typing import Optional
from stepper.device import Device
from stepper.stepper_core.parameters import DeviceParams
from stepper.stepper_core.configs import Address
import RPi.GPIO as GPIO
import time
import logging
from .DeviceManager import DeviceManager

class Gun:
    """炮台控制类，提供炮台角度调整和开火控制"""
    
    def __init__(self, device_manager: DeviceManager, device_name: str = "gun", 
                 gpio_pin: int = 17, address: int = 0x01, steps_per_degree: int = 100) -> None:
        """
        初始化炮台控制
        
        参数:
            device_manager: 设备管理器实例
            device_name: 设备名称，默认为"gun"
            gpio_pin: 开火触发GPIO引脚，默认为17
            address: 设备地址，默认为0x01
            steps_per_degree: 每度对应的步进脉冲数，默认为100

        硬件连接说明:
        1. 步进电机控制器:
           - 连接树莓派串口(TX/RX)到控制器的RX/TX
           - 控制器VCC接5V电源
           - 控制器GND接树莓派GND
           - 控制器A+/A-接步进电机A相
           - 控制器B+/B-接步进电机B相

        2. 开火触发:
           - 使用继电器模块控制电磁阀
           - 继电器IN引脚接树莓派GPIO{gpio_pin}
           - 继电器VCC接5V
           - 继电器GND接树莓派GND
           - 继电器NO触点接电磁阀正极
           - 电磁阀负极接电源负极

        3. 电源:
           - 步进电机和电磁阀使用独立电源
           - 确保电源共地
        """
        self.logger = logging.getLogger(__name__)
        self.device_manager = device_manager
        self.device_name = device_name
        
        # 设置GPIO模式
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # 初始化开火引脚
        self.fire_pin = gpio_pin
        GPIO.setup(self.fire_pin, GPIO.OUT)
        GPIO.output(self.fire_pin, GPIO.LOW)
        
        try:
            # 获取串口设备
            serial_device = device_manager.get_device(device_name)
            
            # 初始化步进电机控制
            self.device = Device(
                device_params=DeviceParams(
                    serial_connection=serial_device,
                    address=Address(address)
                )
            )
            self.device.enable()
            
            # 步进电机参数
            self.steps_per_degree = steps_per_degree
            
            # 当前角度
            self.current_angle: float = 0.0
            self.target_angle: float = 0.0
            
            self.logger.info(f"炮台控制器初始化成功, 设备: {device_name}, GPIO引脚: {gpio_pin}")
            
        except Exception as e:
            self.logger.error(f"炮台控制器初始化失败: {e}")
            raise
        
    def adjust(self, angle: float) -> None:
        """
        调整炮台角度
        
        参数:
            angle: 调整角度，正值为向上，负值为向下
            
        异常:
            RuntimeError: 调整失败时抛出
        """
        try:
            # 限制角度范围 (-30度到30度)
            angle = max(-30, min(30, angle))
            self.target_angle = angle
            
            # 计算目标位置(脉冲数)
            target_steps = int(angle * self.steps_per_degree)
            
            # 设置运动参数
            self.device.set_speed(500)  # 设置速度为500步/秒
            self.device.set_acceleration(1000)  # 设置加速度为1000步/秒²
            
            # 使用绝对位置移动
            self.device.move_to(target_steps)
            
            # 等待移动完成
            while not self.device.is_in_position:
                time.sleep(0.1)
                
            # 更新角度状态
            self.current_angle = angle
            self.logger.debug(f"炮台调整到 {angle} 度")
            
        except Exception as e:
            self.logger.error(f"炮台调整失败: {e}")
            raise
        
    def is_aimed(self, threshold: float = 1.0) -> bool:
        """
        检查是否已瞄准目标
        
        参数:
            threshold: 角度阈值，默认为1.0度
            
        返回:
            是否已瞄准
        """
        try:
            # 检查设备是否在位置
            if not self.device.is_in_position:
                return False
                
            # 检查位置误差
            error_params = self.device.position_error
            error_steps = abs(error_params.error)  # 从PositionErrorParams中提取error字段
            error_angle = error_steps / self.steps_per_degree
            
            aimed = error_angle <= threshold and abs(self.current_angle - self.target_angle) <= threshold
            if aimed:
                self.logger.debug("炮台已瞄准目标")
            return aimed
            
        except Exception as e:
            self.logger.error(f"检查瞄准状态失败: {e}")
            return False
        
    def fire(self) -> None:
        """触发开火"""
        try:
            self.logger.info("触发开火")
            GPIO.output(self.fire_pin, GPIO.HIGH)
            time.sleep(1)  # 保持高电平1秒
            GPIO.output(self.fire_pin, GPIO.LOW)
            self.logger.info("开火完成")
        except Exception as e:
            self.logger.error(f"开火失败: {e}")
            raise
        
    def cleanup(self) -> None:
        """清理资源"""
        try:
            self.device.stop()
            self.device.disable()
            GPIO.cleanup()
            self.logger.info("炮台资源已清理")
        except Exception as e:
            self.logger.error(f"清理炮台资源失败: {e}")
            raise

if __name__ == "__main__":
    """示例主函数，用于单独调试Gun模块"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        print("初始化炮台...")
        # 创建设备管理器并注册串口设备
        device_manager = DeviceManager()
        device_manager.register_serial("gun", "/dev/ttyUSB0", 115200)
        
        gun = Gun(device_manager=device_manager, device_name="gun", gpio_pin=17)
        
        while True:
            print("\n当前选项:")
            print("1. 调整角度")
            print("2. 开火")
            print("3. 检查瞄准状态")
            print("4. 退出")
            
            choice = input("请选择操作(1-4): ")
            
            if choice == "1":
                angle = float(input("请输入角度(-30到30): "))
                gun.adjust(angle)
                print(f"已调整到 {angle} 度")
                
            elif choice == "2":
                gun.fire()
                print("已开火")
                
            elif choice == "3":
                if gun.is_aimed():
                    print("已瞄准目标")
                else:
                    print("未瞄准目标")
                    
            elif choice == "4":
                break
                
            else:
                print("无效输入，请重新选择")
                
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        print("清理资源...")
        if 'gun' in locals():
            gun.cleanup()
        if 'device_manager' in locals():
            device_manager.close_all()
        print("程序退出")