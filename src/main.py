# src/main.py
import sys
import os
import traceback
from pathlib import Path

# 获取程序所在目录，确保能导入 src 模块
base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
sys.path.insert(0, str(base_dir))

def main():
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        from src.gui.main_window import IPTVMainWindow
        from src.utils.logger_handler import setup_gui_logging

        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)
        app.setApplicationName("IPTV 智能管理工具")
        app.setOrganizationName("IPTVCollector")
        
        setup_gui_logging()
        window = IPTVMainWindow()
        window.show()
        sys.exit(app.exec())
    
    except Exception as e:
        error_msg = traceback.format_exc()
        try:
            with open("error.log", "w", encoding="utf-8") as f:
                f.write(error_msg)
        except:
            pass
        print("=" * 60)
        print("程序启动失败！错误信息已写入 error.log")
        print("=" * 60)
        print(error_msg)
        input("按 Enter 键退出...")
        sys.exit(1)

if __name__ == "__main__":
    main()
