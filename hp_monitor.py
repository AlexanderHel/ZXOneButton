import numpy as np
import time
import logging
import threading
import os
import cv2
import pyautogui
from mss import mss
from PIL import Image, ImageGrab
from datetime import datetime

class HPMonitor:
    def __init__(self, config_manager, key_presser, scaling_factor):
        self.config_manager = config_manager
        self.key_presser = key_presser
        self.scaling_factor = scaling_factor
        self.screenshot_area = None
        self.monitoring_thread = None
        self.should_monitor = threading.Event()
        self.sct = mss()
        self.use_party_hp_bar = self.config_manager.get('use_party_hp_bar', False)

    def update_config(self, new_config):
        self.config_manager.update_config(new_config)
        self.use_party_hp_bar = self.config_manager.get('use_party_hp_bar', False)
        if self.should_monitor.is_set():
            self.stop_monitoring()
            self.start_monitoring()

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
        if self.use_party_hp_bar:
            return self.detect_party_hp_bar(screenshot)
        else:
            return self.detect_regular_hp_bar(screenshot)

    def detect_regular_hp_bar(self, screenshot):
        hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([100, 30, 100])
        upper_blue = np.array([140, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        lower_black = np.array([0, 0, 0])
        upper_black = np.array([180, 255, 15])
        black_mask = cv2.inRange(hsv, lower_black, upper_black)

        combined_mask = cv2.bitwise_or(blue_mask, black_mask)

        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if 55 <= w <= 80 and 4 <= h <= 10:
                valid_contours.append(contour)

        if not valid_contours:
            lower_yellow = np.array([10, 65, 15])
            upper_yellow = np.array([50, 185, 185])
            yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
            combined_mask = cv2.bitwise_or(yellow_mask, black_mask)

            contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if 55 <= w <= 80 and 4 <= h <= 10:
                    roi = screenshot[y:y+h, x:x+w]
                    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                    yellow_black_mask = cv2.bitwise_or(cv2.inRange(hsv_roi, lower_yellow, upper_yellow),
                                                       cv2.inRange(hsv_roi, lower_black, upper_black))
                    if np.count_nonzero(yellow_black_mask) == roi.shape[0] * roi.shape[1]:
                        valid_contours.append(contour)
                        logging.info("Found valid yellow-black contour.")
                    else:
                        logging.info("Found yellow-black contour with other colors. Ignoring.")

        if valid_contours:
            largest_contour = max(valid_contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)
            return x, y, w, h
        else:
            logging.warning("No valid HP bar detected in the screenshot.")
            return None

    def detect_party_hp_bar(self, screenshot):
        hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
        lower_red = np.array([0, 100, 100])
        upper_red = np.array([10, 255, 255])
        red_mask1 = cv2.inRange(hsv, lower_red, upper_red)
        lower_red = np.array([160, 100, 100])
        upper_red = np.array([179, 255, 255])
        red_mask2 = cv2.inRange(hsv, lower_red, upper_red)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)

        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h
            if 10 <= w <= 200 and 2 <= h <= 20 and 5 <= aspect_ratio <= 15:
                valid_contours.append(contour)

        if valid_contours:
            largest_contour = max(valid_contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)
            return x, y, w, h
        else:
            logging.warning("No valid party HP bar detected in the screenshot.")
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

                if self.use_party_hp_bar:
                    lower_red = np.array([0, 100, 100])
                    upper_red = np.array([10, 255, 255])
                    mask1 = cv2.inRange(hsv, lower_red, upper_red)
                    lower_red = np.array([160, 100, 100])
                    upper_red = np.array([179, 255, 255])
                    mask2 = cv2.inRange(hsv, lower_red, upper_red)
                    mask = cv2.bitwise_or(mask1, mask2)
                    red_pixels = cv2.countNonZero(mask)
                    hp_percentage = (red_pixels / w) * 100
                else:
                    lower_blue = np.array([100, 30, 100])
                    upper_blue = np.array([140, 255, 255])
                    mask = cv2.inRange(hsv, lower_blue, upper_blue)
                    blue_pixels = cv2.countNonZero(mask)

                    if blue_pixels == 0:
                        lower_yellow = np.array([10, 65, 15])
                        upper_yellow = np.array([50, 185, 185])
                        mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
                        yellow_pixels = cv2.countNonZero(mask)
                        hp_percentage = (yellow_pixels / (w - 2)) * 100
                    else:
                        hp_percentage = (blue_pixels / (w - 2)) * 100

                logging.info(f"Calculated HP percentage: {hp_percentage:.2f}%")
                return hp_percentage, screenshot

            except Exception as e:
                logging.error(f"Error processing HP percentage (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(0.25)

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

    def save_hp_bar_image(self, screenshot):
        if not os.path.exists('hp_bar_images'):
            os.makedirs('hp_bar_images')
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hp_bar_images/hp_bar_{timestamp}.png"
        
        Image.fromarray(screenshot).save(filename)
        logging.info(f"HP bar image saved: {filename}")

    def monitor_hp(self):
        while self.should_monitor.is_set():
            result = self.get_hp_percentage()
            if result is not None:
                hp_percentage, screenshot = result
                logging.info(f"Current HP: {hp_percentage:.2f}%")
                
                hp_threshold = self.config_manager.get('hp_level', 85)
                if 1 < hp_percentage < hp_threshold:
                    hp_key = self.config_manager.get('hp_key', '5')
                    hp_frequency = self.config_manager.get('hp_frequency', 0.1)
                    logging.info(f"HP below threshold ({hp_threshold}%). Pressing HP key: {hp_key}")
                    self.key_presser.press_hp_key()
                    self.save_hp_bar_image(screenshot)
                    time.sleep(hp_frequency)
                elif hp_percentage == 0:
                    logging.info("HP is 0%. Skipping HP key press.")
            else:
                logging.warning("Failed to get HP percentage.")
            
            time.sleep(0.1)

    def get_cursor_position(self):
        with mss() as sct:
            return sct.position