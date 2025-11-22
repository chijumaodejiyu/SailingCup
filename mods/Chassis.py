import serial
import time

class Chassis:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
        """
        初始化底盘控制
        
        参数:
            port (str): 串口设备路径，默认为'/dev/ttyUSB0'
            baudrate (int): 波特率，默认为115200
        """
        self.serial = serial.Serial(port, baudrate, timeout=1)
        if not self.serial.is_open:
            raise RuntimeError("无法打开串口设备")
            
        # 陀螺仪校准状态
        self.gyro_calibrated = False
        
    def self_test(self):
        """
        底盘自检和陀螺仪校准
        控制小车旋转360度完成自检
        """
        print("开始底盘自检...")
        
        # 发送旋转命令
        self.send_command("ROTATE 360")
        
        # 等待自检完成
        while True:
            response = self.serial.readline().decode().strip()
            if response == "SELF_TEST_COMPLETE":
                print("底盘自检完成")
                break
            time.sleep(0.1)
            
        # 陀螺仪校准
        self.calibrate_gyro()
        
    def calibrate_gyro(self):
        """陀螺仪校准"""
        print("开始陀螺仪校准...")
        self.send_command("CALIBRATE_GYRO")
        
        while True:
            response = self.serial.readline().decode().strip()
            if response == "GYRO_CALIBRATED":
                self.gyro_calibrated = True
                print("陀螺仪校准完成")
                break
            time.sleep(0.1)
            
    def turn(self, angle):
        """
        控制底盘转向
        
        参数:
            angle (float): 转向角度，正值为顺时针，负值为逆时针
        """
        if not self.gyro_calibrated:
            raise RuntimeError("陀螺仪未校准，请先执行自检")
            
        # 限制角度范围
        angle = max(-180, min(180, angle))
        self.send_command(f"TURN {angle}")
        
    def send_command(self, command):
        """
        发送串口命令
        
        参数:
            command (str): 要发送的命令
        """
        self.serial.write(f"{command}\n".encode())
        
    def close(self):
        """关闭串口连接"""
        self.serial.close()