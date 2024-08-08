import numpy as np
import time
import logging
import threading
from mss import mss
from PIL import Image, ImageGrab
import cv2
import pyautogui

class HPMonitor:
    def __init__(self, config_manager, key_presser, scaling_factor):
        self.config_manager = config_manager
        self.key_presser = key_presser
        self.scaling_factor = scaling_factor  # We're not using this directly, but keeping it for compatibility
        self.screenshot_area = None
        self.monitoring_thread = None
        self.should_monitor = threading.Event()
        self.is_paused = threading.Event()
        self.sct = mss()

    def select_screenshot_area(self):
        logging.info("Selecting screenshot area...")
        try:
            screenshot = ImageGrab.grab()
            screenshot.save("temp_screenshot.png")
            
            img = cv2.imread("temp_screenshot.png")
            
            roi = cv2.selectROI("Select HP Bar Area", img, False)
            cv2.destroyAllWindows()
            
            self.screenshot_area = {
                "top": roi[1],
                "left": roi[0],
                "width": roi[2],
                "height": roi[3]
            }
            logging.info(f"Screenshot area selected: {self.screenshot_area}")
        except Exception as e:
            logging.error(f"Error selecting screenshot area: {e}")

    def detect_hp_bar(self, screenshot):
        hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
        
        lower_blue = np.array([100, 30, 100])
        upper_blue = np.array([140, 255, 255])
        
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        
        lower_black = np.array([0, 0, 0])
        upper_black = np.array([180, 255, 15])
        
        black_mask = cv2.inRange(hsv, lower_black, upper_black)
        
        combined_mask = cv2.bitwise_or(blue_mask, black_mask)
        
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)
            return x, y, w, h
        else:
            return None

    def get_hp_percentage(self):
        if not self.screenshot_area:
            logging.warning("Screenshot area not selected. Please select an area first.")
            return None

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with mss() as sct:
                    screenshot = np.array(sct.grab(self.screenshot_area))
            except Exception as e:
                logging.warning(f"mss screenshot failed (attempt {attempt + 1}): {e}")
                try:
                    screenshot = pyautogui.screenshot(region=(
                        self.screenshot_area['left'],
                        self.screenshot_area['top'],
                        self.screenshot_area['width'],
                        self.screenshot_area['height']
                    ))
                    screenshot = np.array(screenshot)
                except Exception as e:
                    logging.error(f"pyautogui screenshot failed (attempt {attempt + 1}): {e}")
                    if attempt == max_retries - 1:
                        logging.error("Max retries reached. Unable to capture screenshot.")
                        return None
                    time.sleep(0.1)
                    continue
        try:
            hp_bar = self.detect_hp_bar(screenshot)
            if hp_bar is None:
                logging.warning("HP bar not detected in the screenshot.")
                return None

            x, y, w, h = hp_bar
            hp_bar_img = screenshot[y:y+h, x:x+w]

            middle_line = h // 2
            hp_line = hp_bar_img[middle_line:middle_line+1, :]

            hsv = cv2.cvtColor(hp_line, cv2.COLOR_BGR2HSV)

            lower_blue = np.array([85, 110, 35])
            upper_blue = np.array([140, 255, 255])
            mask = cv2.inRange(hsv, lower_blue, upper_blue)

            blue_pixels = cv2.countNonZero(mask)
            total_pixels = w - 2

            hp_percentage = (blue_pixels / total_pixels) * 100
            print(blue_pixels)
            print(total_pixels)

            logging.info(f"Calculated HP percentage: {hp_percentage:.2f}%")
            return hp_percentage

        except Exception as e:
            logging.error(f"Error processing HP percentage (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return None
            time.sleep(0.1)

    def __del__(self):
        if hasattr(self, 'sct'):
            self.sct.close()

    def start_monitoring(self):
        if not self.monitoring_thread or not self.monitoring_thread.is_alive():
            self.should_monitor.set()
            self.monitoring_thread = threading.Thread(target=self.monitor_hp)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            logging.info("HP monitoring started.")

    def stop_monitoring(self):
        self.should_monitor.clear()
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join()
        logging.info("HP monitoring stopped.")

    def monitor_hp(self):
        while self.should_monitor.is_set():
            if self.is_paused.is_set():
                time.sleep(0.1)
                continue

            hp_percentage = self.get_hp_percentage()
            if hp_percentage is not None:
                logging.info(f"Current HP: {hp_percentage:.2f}%")
                
                hp_threshold = self.config_manager.get('hp_level', 85)
                if 5 < hp_percentage < hp_threshold:
                    hp_key = self.config_manager.get('hp_key', '5')
                    logging.info(f"HP below threshold ({hp_threshold}%). Pressing HP key: {hp_key}")
                    self.key_presser.press_hp_key()
                elif hp_percentage == 0:
                    logging.info("HP is 0%. Skipping HP key press.")
            else:
                logging.warning("Failed to get HP percentage.")
            
            time.sleep(0.1)  # Increased sleep time to reduce CPU usage

    def set_pause(self, pause):
        if pause:
            self.is_paused.set()
            logging.info("HP monitoring paused.")
        else:
            self.is_paused.clear()
            logging.info("HP monitoring unpaused.")
        return self.is_paused.is_set()

    def get_cursor_position(self):
        with mss() as sct:
            return sct.position