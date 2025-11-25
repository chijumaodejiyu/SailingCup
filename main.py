import cv2 as cv
import numpy as np
import time
import logging
from typing import List, Dict, Optional
from mods.FireControl import CNN
from mods.TCP import VideoStreamSender
from mods.Cap import Camera
from mods.Chassis import Chassis
from mods.Gun import Gun

# 配置常量
DEFAULT_CAMERA_INDEX = 0
TCP_SERVER_IP = '192.168.1.100'
TCP_SERVER_PORT = 8080
MAIN_LOOP_SLEEP_TIME = 0.1  # 主循环休眠时间(秒)
CAMERA_H_FOV = 85  # 水平视场角(度)
CAMERA_V_FOV = CAMERA_H_FOV * (9/16)  # 垂直视场角(度)
IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Target:
    def __init__(self, id: int, bbox: List[float], timestamp: float):
        self.id = id
        self.bbox = bbox  # [x1, y1, x2, y2]
        self.timestamp = timestamp
        self.active = True
        self.x_angle: Optional[float] = None
        self.y_angle: Optional[float] = None
        self.distance_to_center: Optional[float] = None

class MainController:
    def __init__(self):
        """初始化主控制器"""
        try:
            # 初始化模块
            self.camera = Camera(DEFAULT_CAMERA_INDEX)
            self.fire_control = CNN()
            self.chassis = Chassis()
            self.gun = Gun()
            self.tcp_sender = VideoStreamSender(TCP_SERVER_IP, TCP_SERVER_PORT)
            
            # 目标池
            self.target_pool: List[Target] = []
            
            logger.info("主控制器初始化完成")
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise
        
    def chassis_self_test(self) -> None:
        """底盘自检和陀螺仪校准"""
        try:
            logger.info("开始底盘自检...")
            self.chassis.self_test()
            logger.info("底盘自检完成")
        except Exception as e:
            logger.error(f"底盘自检失败: {e}")
            raise
        
    def update_target_pool(self, detections: List[Dict]) -> None:
        """更新目标池"""
        try:
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
        except Exception as e:
            logger.error(f"更新目标池失败: {e}")
            raise
            
    def fire_control_solution(self) -> Optional[Dict]:
        """火控解算
        使用精确的像素到角度转换算法
        
        返回:
            Optional[Dict]: 火控解算结果，包含x角度、y角度和目标信息
        """
        try:
            if not self.target_pool:
                return None
                
            # 计算每个目标的角度差
            for target in self.target_pool:
                # 计算目标中心坐标(图像坐标系)
                target_center_x = (target.bbox[0] + target.bbox[2]) / 2
                target_center_y = (target.bbox[1] + target.bbox[3]) / 2
                
                # 转换为以图像中心为原点的坐标
                x = target_center_x - IMAGE_WIDTH / 2
                y = IMAGE_HEIGHT / 2 - target_center_y  # y轴向下为正，需要反转
                
                # 计算水平角度差(度)
                x_angle = (x / (IMAGE_WIDTH / 2)) * (CAMERA_H_FOV / 2)
                
                # 计算垂直角度差(度)
                y_angle = (y / (IMAGE_HEIGHT / 2)) * (CAMERA_V_FOV / 2)
                
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
        except Exception as e:
            logger.error(f"火控解算失败: {e}")
            raise
            
    def run(self) -> None:
        """主控制循环"""
        try:
            # 初始化连接
            self.tcp_sender.connect()
            
            # 底盘自检
            self.chassis_self_test()
            
            logger.info("主控制循环开始运行")
            while True:
                try:
                    # 获取帧数据
                    frame = self.camera.get_frame('HIGH')
                    if frame is None:
                        logger.warning("获取帧数据失败")
                        continue
                    
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
                    time.sleep(MAIN_LOOP_SLEEP_TIME)
                    
                except Exception as e:
                    logger.error(f"主循环迭代出错: {e}", exc_info=True)
                    time.sleep(1)  # 出错后等待1秒再继续
                    
        except Exception as e:
            logger.critical(f"主控制循环异常终止: {e}", exc_info=True)
            raise
        finally:
            logger.info("主控制循环结束")

if __name__ == '__main__':
    try:
        controller = MainController()
        controller.run()
    except Exception as e:
        logger.critical(f"程序异常终止: {e}", exc_info=True)