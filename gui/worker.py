# gui/worker.py
import sys
import os
import asyncio
import logging
from PyQt5.QtCore import QThread, pyqtSignal

class CollectionWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        # 在 exe 所在目录创建日志文件
        self.log_file = os.path.join(os.path.dirname(sys.executable), "worker_debug.log")
        self.write_log("=== Worker 初始化 ===")

    def write_log(self, msg):
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except:
            pass

    def run(self):
        # 将标准输出和错误重定向到日志文件（便于调试）
        sys.stdout = open(os.path.join(os.path.dirname(sys.executable), "stdout.log"), "w", encoding="utf-8")
        sys.stderr = open(os.path.join(os.path.dirname(sys.executable), "stderr.log"), "w", encoding="utf-8")

        try:
            self.write_log("run() 开始")
            self.log_signal.emit("🚀 开始 IPTV 采集任务...")
            
            base_dir = os.path.dirname(sys.executable)
            self.write_log(f"工作目录: {base_dir}")
            self.log_signal.emit(f"📂 工作目录: {base_dir}")

            # 确保 _internal 在 sys.path 中（PyInstaller onedir 模式）
            internal_dir = os.path.join(base_dir, '_internal')
            if os.path.exists(internal_dir) and internal_dir not in sys.path:
                sys.path.insert(0, internal_dir)
                self.write_log(f"已添加 _internal 路径: {internal_dir}")

            # 尝试导入 src
            try:
                import src
                self.write_log("src 导入成功")
                self.log_signal.emit("✅ src 模块导入成功")
            except ImportError as e:
                self.write_log(f"src 导入失败: {e}")
                self.log_signal.emit(f"❌ src 模块导入失败: {e}")
                self.finished_signal.emit(False)
                return

            # 导入主函数
            try:
                from src.run import main as run_main
                self.write_log("src.run 导入成功")
                self.log_signal.emit("✅ src.run 导入成功")
            except ImportError as e:
                self.write_log(f"src.run 导入失败: {e}")
                self.log_signal.emit(f"❌ src.run 导入失败: {e}")
                self.finished_signal.emit(False)
                return

            # 设置日志捕获
            from src.logger import logger
            self.write_log("日志模块加载成功")

            class GuiLogHandler(logging.Handler):
                def __init__(self, signal):
                    super().__init__()
                    self.signal = signal
                def emit(self, record):
                    msg = self.format(record)
                    self.signal.emit(msg)

            gui_handler = GuiLogHandler(self.log_signal)
            gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(gui_handler)

            # 运行采集
            self.log_signal.emit("⏳ 正在运行采集任务，请稍候...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                exit_code = loop.run_until_complete(run_main())
            finally:
                loop.close()

            if exit_code == 0:
                self.log_signal.emit("✅ 采集任务成功完成")
                self.finished_signal.emit(True)
            else:
                self.log_signal.emit(f"❌ 采集任务退出，错误码: {exit_code}")
                self.finished_signal.emit(False)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.write_log(f"异常: {e}\n{tb}")
            self.log_signal.emit(f"❌ 采集任务异常: {str(e)}")
            self.log_signal.emit(tb)
            self.finished_signal.emit(False)
        finally:
            try:
                logger.removeHandler(gui_handler)
            except:
                pass
            self.write_log("=== Worker 结束 ===")
            sys.stdout.close()
            sys.stderr.close()
