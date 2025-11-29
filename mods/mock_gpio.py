"""
模拟GPIO模块，用于在PC上调试树莓派GPIO相关代码
"""

import logging
from typing import Dict, Set

logger = logging.getLogger(__name__)

class MockGPIO:
    """模拟GPIO类，用于在PC上模拟树莓派的GPIO功能"""
    
    # GPIO模式常量
    BCM = 'BCM'
    BOARD = 'BOARD'
    OUT = 'OUT'
    IN = 'IN'
    HIGH = True
    LOW = False
    
    # 引脚状态存储
    _pin_modes: Dict[int, str] = {}
    _pin_states: Dict[int, bool] = {}
    _setup_pins: Set[int] = set()
    
    @classmethod
    def setmode(cls, mode: str) -> None:
        """设置GPIO模式"""
        logger.info(f"模拟GPIO: 设置模式为 {mode}")
    
    @classmethod
    def setup(cls, pin: int, mode: str) -> None:
        """设置引脚模式"""
        cls._pin_modes[pin] = mode
        cls._setup_pins.add(pin)
        cls._pin_states[pin] = cls.LOW
        logger.info(f"模拟GPIO: 设置引脚 {pin} 模式为 {mode}")
    
    @classmethod
    def output(cls, pin: int, state: bool) -> None:
        """设置引脚输出状态"""
        if pin not in cls._setup_pins:
            logger.warning(f"模拟GPIO: 引脚 {pin} 未设置，自动设置为输出模式")
            cls.setup(pin, cls.OUT)
        
        cls._pin_states[pin] = state
        state_str = "HIGH" if state else "LOW"
        logger.info(f"模拟GPIO: 设置引脚 {pin} 为 {state_str}")
    
    @classmethod
    def input(cls, pin: int) -> bool:
        """读取引脚输入状态"""
        if pin not in cls._setup_pins:
            logger.warning(f"模拟GPIO: 引脚 {pin} 未设置，返回LOW")
            return cls.LOW
        
        return cls._pin_states.get(pin, cls.LOW)
    
    @classmethod
    def cleanup(cls, pin: int = None) -> None:
        """清理GPIO资源"""
        if pin is None:
            # 清理所有引脚
            cls._pin_modes.clear()
            cls._pin_states.clear()
            cls._setup_pins.clear()
            logger.info("模拟GPIO: 清理所有引脚")
        else:
            # 清理指定引脚
            cls._pin_modes.pop(pin, None)
            cls._pin_states.pop(pin, None)
            cls._setup_pins.discard(pin)
            logger.info(f"模拟GPIO: 清理引脚 {pin}")
    
    @classmethod
    def setwarnings(cls, flag: bool) -> None:
        """设置警告显示"""
        logger.info(f"模拟GPIO: 设置警告显示为 {flag}")
    
    @classmethod
    def get_pin_state(cls, pin: int) -> bool:
        """获取引脚当前状态（用于测试）"""
        return cls._pin_states.get(pin, cls.LOW)
    
    @classmethod
    def get_pin_mode(cls, pin: int) -> str:
        """获取引脚模式（用于测试）"""
        return cls._pin_modes.get(pin, None)
    
    @classmethod
    def get_all_pins(cls) -> Dict[int, Dict[str, any]]:
        """获取所有引脚状态（用于测试）"""
        return {
            pin: {
                'mode': cls._pin_modes.get(pin),
                'state': cls._pin_states.get(pin, cls.LOW),
                'setup': pin in cls._setup_pins
            }
            for pin in cls._setup_pins
        }

# 创建全局实例
GPIO = MockGPIO