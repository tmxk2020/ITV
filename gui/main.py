# gui/main.py
import sys
import os
from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow

# 显式导入所有后端模块，确保 PyInstaller 打包时包含它们
import src
import src.config
import src.logger
import src.run
import src.fetcher
import src.parser
import src.speed_tester
import src.ffmpeg_validator
import src.generator
import src.merger
import src.blacklist_filter
import src.demo_filter
import src.database
import src.alias_matcher
import src.classifier
import src.logo_matcher
import src.generator_enhanced
import src.special_categories
import src.stable.manager
import src.source_pool.discoverer
import src.candidate.observer
import src.quality.monitor
import src.overseas_filter
# 如果有其他子模块，继续添加

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("IPTV 智能整理平台")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
