import cv2 as cv
import numpy as np
from mods.FireControl import CNN
from mods.TCP import VideoStreamSender
import time
import serial

class Target:
    def __init__(self, id, bbox, timestamp):
        self.id = id
        self.bbox = bbox  # [x1, y1, x2, y2]
        self.timestamp = timestamp
        self.active = True

class MainController:
    def __init__(self):
        # 初始化模块
        self.camera = self.init_camera()
        self.fire_control = CNN()
        self.chassis = self.init_chassis()
        self.gun = self.init_gun()
        self.tcp_sender = VideoStreamSender('192.168.1.100', 8080)
        
        # 目标池
        self.target_pool = []
        
    def init_camera(self):
        """初始化摄像头
        自动检测并打开可用的摄像头设备
        """
        import cv2
        
        # 尝试打开摄像头设备，最多尝试5个设备索引
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"成功打开摄像头设备 {i}")
                
                # 设置摄像头参数
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                cap.set(cv2.CAP_PROP_FPS, 30)
                
                # 创建Camera实例
                from mods.Cap import Camera
                return Camera(i)
            
            cap.release()
        
        raise RuntimeError("无法找到可用的摄像头设备")
        
    def init_chassis(self):
        """初始化底盘控制"""
        # TODO: 实现底盘初始化
        pass
        
    def init_gun(self):
        """初始化炮台控制"""
        # TODO: 实现炮台初始化
        pass
        
    def chassis_self_test(self):
        """底盘自检和陀螺仪校准"""
        print("开始底盘自检...")
        # TODO: 实现360度旋转自检
        print("底盘自检完成")
        
    def update_target_pool(self, detections):
        """更新目标池"""
        current_time = time.time()
        # 1. 标记所有现有目标为不活跃
        for target in self.target_pool:
            target.active = False
            
        # 2. 更新或添加新目标
        for det in detections:
            if det['class'] == 0:  # 只处理类别为0的目标
                # 检查是否已在目标池中
                existing_target = next((t for t in self.target_pool if t.id == det['id']), None)
                if existing_target:
                    existing_target.bbox = det['bbox']
                    existing_target.timestamp = current_time
                    existing_target.active = True
                else:
                    self.target_pool.append(Target(det['id'], det['bbox'], current_time))
                    
        # 3. 移除不活跃的目标
        self.target_pool = [t for t in self.target_pool if t.active]
        
    def fire_control_solution(self):
        """火控解算
        使用精确的像素到角度转换算法
        摄像头参数：焦距3mm，FOV 85度，分辨率1920x1080
        """
        if not self.target_pool:
            return None
            
        # 摄像头参数
        h_fov = 85  # 水平视场角(度)
        v_fov = h_fov * (9/16)  # 垂直视场角(度)，假设16:9比例
        img_width = 1920
        img_height = 1080
        
        # 计算每个目标的角度差
        for target in self.target_pool:
            # 计算目标中心坐标(图像坐标系)
            target_center_x = (target.bbox[0] + target.bbox[2]) / 2
            target_center_y = (target.bbox[1] + target.bbox[3]) / 2
            
            # 转换为以图像中心为原点的坐标
            x = target_center_x - img_width / 2
            y = img_height / 2 - target_center_y  # y轴向下为正，需要反转
            
            # 计算水平角度差(度)
            x_angle = (x / (img_width / 2)) * (h_fov / 2)
            
            # 计算垂直角度差(度)
            y_angle = (y / (img_height / 2)) * (v_fov / 2)
            
            # 保存计算结果
            target.x_angle = x_angle
            target.y_angle = y_angle
            target.distance_to_center = np.sqrt(x**2 + y**2)  # 像素距离
            
        # 按距离排序，选择最近的目标
        priority_target = min(self.target_pool, key=lambda x: x.distance_to_center)
        
        return {
            'x_angle': priority_target.x_angle,
            'y_angle': priority_target.y_angle,
            'target': priority_target
        }
        
    def run(self):
        """主循环"""
        # 初始化连接
        self.tcp_sender.connect()
        
        # 底盘自检
        self.chassis_self_test()
        
        while True:
            # 获取帧数据
            frame = self.camera.get_frame('HIGH')
            
            # 目标检测
            detections = self.fire_control.detect(frame)
            
            # 更新目标池
            self.update_target_pool(detections)
            
            # 火控解算
            fire_solution = self.fire_control_solution()
            if fire_solution:
                # 控制底盘和炮台
                self.chassis.turn(fire_solution['x_angle'])
                self.gun.adjust(fire_solution['y_angle'])
                
                # 瞄准后开火
                if self.gun.is_aimed():
                    self.gun.fire()
                    
            # 发送视频流
            self.tcp_sender.send_frame(cv.imencode('.jpg', frame)[1].tobytes())
            
            # 控制帧率
            time.sleep(0.1)

if __name__ == '__main__':
    controller = MainController()
    controller.run()