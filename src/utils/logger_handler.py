# src/utils/logger_handler.py
"""日志重定向到 GUI"""

import logging
from typing import Optional, Callable


class GUILogHandler(logging.Handler):
    """将日志重定向到 GUI 的 Handler"""
    
    def __init__(self):
        super().__init__()
        self.callback: Optional[Callable] = None
    
    def set_callback(self, callback: Callable):
        """设置回调函数"""
        self.callback = callback
    
    def emit(self, record: logging.LogRecord):
        """处理日志记录"""
        if self.callback:
            msg = self.format(record)
            self.callback(msg)


# 全局实例
gui_log_handler = GUILogHandler()


def setup_gui_logging():
    """配置日志重定向到 GUI"""
    import logging
    from src.core.logger import logger
    
    # 移除原有 handlers，避免重复输出
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 添加 GUI handler
    gui_log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(gui_log_handler)
    
    # 也保留控制台输出（用于调试）
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console)
    
    logger.info("📡 GUI 日志已配置")
