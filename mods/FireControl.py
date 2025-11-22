from ultralytics.models.yolo import YOLO
import numpy as np
from collections import defaultdict
import time

class CNN:
    def __init__(self) -> None:
        """初始化火控系统"""
        self.model = YOLO('yolov11n.pt')
        self.model.eval()
        
        # 目标跟踪
        self.track_history = defaultdict(lambda: [])
        self.next_id = 0
        
    def detect(self, frame):
        """
        检测并跟踪目标
        
        参数:
            frame (numpy.ndarray): 输入帧图像
            
        返回:
            list: 检测结果列表，每个元素为包含目标信息的字典
        """
        # 使用YOLO进行目标检测
        results = self.model(frame)
        
        # 解析检测结果
        detections = []
        current_time = time.time()
        
        for result in results:
            for box in result.boxes:
                # 只处理类别为0的目标
                if int(box.cls) == 0:
                    # 获取边界框坐标
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    
                    # 分配或获取目标ID
                    if box.id is not None:
                        track_id = int(box.id)
                    else:
                        track_id = self.next_id
                        self.next_id += 1
                    
                    # 更新跟踪历史
                    self.track_history[track_id].append((current_time, (x1, y1, x2, y2)))
                    
                    # 保留最近10次跟踪记录
                    if len(self.track_history[track_id]) > 10:
                        self.track_history[track_id].pop(0)
                    
                    # 计算目标稳定性
                    stability = self._calculate_stability(track_id)
                    
                    # 格式化检测结果
                    detections.append({
                        'id': track_id,
                        'bbox': [x1, y1, x2, y2],
                        'class': 0,
                        'confidence': float(box.conf),
                        'timestamp': current_time,
                        'stability': stability
                    })
        
        return detections
        
    def _calculate_stability(self, track_id):
        """
        计算目标跟踪稳定性
        
        参数:
            track_id (int): 目标ID
            
        返回:
            float: 稳定性分数(0-1)
        """
        history = self.track_history[track_id]
        if len(history) < 2:
            return 0.0
            
        # 计算位置变化率
        positions = np.array([item[1] for item in history])
        center_points = np.array([[(x1+x2)/2, (y1+y2)/2] for x1,y1,x2,y2 in positions])
        
        # 计算移动标准差
        std = np.std(center_points, axis=0)
        avg_std = np.mean(std)
        
        # 转换为稳定性分数 (0-1)
        max_pixel_variation = 50  # 假设最大像素变化为50
        stability = 1.0 - min(avg_std / max_pixel_variation, 1.0)
        
        return stability
        
    def cleanup_tracks(self):
        """清理过期的跟踪记录"""
        current_time = time.time()
        expired_ids = []
        
        for track_id, history in self.track_history.items():
            if current_time - history[-1][0] > 5.0:  # 5秒未更新
                expired_ids.append(track_id)
                
        for track_id in expired_ids:
            del self.track_history[track_id]