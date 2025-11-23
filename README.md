# 树莓派炮台控制系统

## 项目概述
本项目使用树莓派控制步进电机驱动的炮台系统，包含以下功能：
- 精确角度控制（-30度到30度）
- 开火触发控制
- 瞄准状态检测
- 闭环位置控制

## 硬件连接
### 步进电机控制器
1. 连接树莓派串口(TX/RX)到控制器的RX/TX
2. 控制器VCC接5V电源
3. 控制器GND接树莓派GND
4. 控制器A+/A-接步进电机A相
5. 控制器B+/B-接步进电机B相

### 开火触发
1. 使用继电器模块控制电磁阀
2. 继电器IN引脚接树莓派GPIO17
3. 继电器VCC接5V
4. 继电器GND接树莓派GND
5. 继电器NO触点接电磁阀正极
6. 电磁阀负极接电源负极

## 软件安装
1. 安装依赖库：
```bash
pip install pyserial RPi.GPIO
```

2. 克隆本项目：
```bash
git clone https://github.com/your-repo/raspberry-gun-control.git
```

## 使用说明
### 初始化炮台
```python
from mods.Gun import Gun
gun = Gun(gpio_pin=17, serial_port="/dev/ttyUSB0")
```

### 调整角度
```python
gun.adjust(15)  # 向上调整15度
gun.adjust(-10) # 向下调整10度
```

### 检查瞄准状态
```python
if gun.is_aimed():
    print("已瞄准目标")
```

### 开火
```python
gun.fire()  # 触发开火
```

### 清理资源
```python
gun.cleanup()  # 程序退出前调用
```

## 文件说明
- `mods/Gun.py`: 炮台控制主程序
- `pi-venv/lib/python3.13/site-packages/stepper/device/device.py`: 步进电机驱动库
- `main.py`: 主控制程序（待实现）

## 注意事项
1. 确保步进电机和电磁阀使用独立电源
2. 所有电源需要共地
3. 角度范围限制在-30到30度之间
4. 默认速度为500步/秒，加速度为1000步/秒²
