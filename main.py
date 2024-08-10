import dearpygui.dearpygui as dpg
import pywinstyles
from gui import GUI
from hp_monitor import HPMonitor
from key_presser import KeyPresser
from config_manager import ConfigManager
import logging
import time
import traceback
import sys
import ctypes

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class ZXOneButton:
    def __init__(self):
        try:
            self.config_manager = ConfigManager()
            self.key_presser = KeyPresser(self.config_manager)
            self.scaling_factor = self.get_display_scaling_factor()
            self.hp_monitor = HPMonitor(self.config_manager, self.key_presser, self.scaling_factor)
            self.gui = GUI(self.config_manager, self.hp_monitor, self.key_presser)
            self.target_fps = 60
            self.frame_time = 1.0 / self.target_fps
        except Exception as e:
            logging.error(f"Error during initialization: {e}")
            logging.error(traceback.format_exc())
            raise

    def get_display_scaling_factor(self):
        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            return user32.GetDpiForSystem() / 96.0
        except Exception as e:
            logging.error(f"Failed to get display scaling factor: {e}")
            return 1.0

    def run(self):
        try:
            logging.info("Starting application...")
            logging.info(f"Display scaling factor: {self.scaling_factor}")
            dpg.create_context()
            logging.info("DearPyGui context created")
            
            self.gui.setup()
            logging.info("GUI setup complete")
            dpg.setup_dearpygui()
            logging.info("DearPyGui setup complete")
            
            dpg.show_viewport()
            logging.info("Viewport shown")
            pywinstyles.apply_style(self, "acrylic")
            
            last_time = time.perf_counter()
            while dpg.is_dearpygui_running():
                current_time = time.perf_counter()
                delta_time = current_time - last_time
                
                if delta_time >= self.frame_time:
                    dpg.render_dearpygui_frame()
                    last_time = current_time
                else:
                    time.sleep(self.frame_time - delta_time)

        except Exception as e:
            logging.error(f"An error occurred while running the application: {e}")
            logging.error(traceback.format_exc())
        finally:
            self.cleanup()

    def cleanup(self):
        try:
            logging.info("Starting cleanup...")
            if hasattr(self, 'key_presser'):
                self.key_presser.stop_pressing()
            if hasattr(self, 'hp_monitor'):
                self.hp_monitor.stop_monitoring()
            if hasattr(self, 'gui'):
                self.gui.cleanup()
            if hasattr(self, 'config_manager'):
                self.config_manager.cleanup()
            dpg.destroy_context()
            logging.info("Application shutdown complete.")
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
            logging.error(traceback.format_exc())

if __name__ == "__main__":
    try:
        app = ZXOneButton()
        app.run()
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        logging.error(traceback.format_exc())
    finally:
        logging.info("Application has finished. Exiting.")
        sys.exit(0)