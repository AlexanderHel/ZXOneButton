import threading
import time
import logging
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Controller as KeyboardController, Key, Listener
from collections import deque

class KeyPresser:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        self.should_press = threading.Event()
        self.is_paused = threading.Event()
        self.lock = threading.Lock()
        self.threads = []
        self.manual_key_thread = None
        self.manual_keys_pressed = set()
        self.key_press_queue = deque()
        self.key_press_thread = None

    def start_pressing(self):
        self.should_press.set()
        logging.debug(f"Left click var: {self.config_manager.get('left_click_var')}")
        logging.debug(f"Right click var: {self.config_manager.get('right_click_var')}")
        logging.debug(f"Left click freq: {self.config_manager.get('left_click_freq')}")
        logging.debug(f"Right click freq: {self.config_manager.get('right_click_freq')}")

        self.key_press_thread = threading.Thread(target=self.process_key_press_queue)
        self.key_press_thread.start()
        self.threads.append(self.key_press_thread)

        for i in range(4):
            thread = threading.Thread(target=self.schedule_key_press, args=(i,))
            thread.start()
            self.threads.append(thread)

        if self.config_manager.get('left_click_var'):
            left_click_thread = threading.Thread(target=self.schedule_mouse_click, args=('left', self.config_manager.get('left_click_freq')))
            left_click_thread.start()
            self.threads.append(left_click_thread)

        if self.config_manager.get('right_click_var'):
            right_click_thread = threading.Thread(target=self.schedule_mouse_click, args=('right', self.config_manager.get('right_click_freq')))
            right_click_thread.start()
            self.threads.append(right_click_thread)

        self.manual_key_thread = threading.Thread(target=self.handle_manual_keys)
        self.manual_key_thread.start()
        self.threads.append(self.manual_key_thread)

    def stop_pressing(self):
        self.should_press.clear()
        logging.info("Stopping all key pressing operations.")
        for thread in self.threads:
            thread.join()
        self.threads.clear()
        self.key_press_queue.clear()

    def schedule_key_press(self, index):
        while self.should_press.is_set():
            if self.is_paused.is_set():
                time.sleep(0.01)
                continue

            key = self.config_manager.get(f'key_to_press_{index}')
            if not key:
                time.sleep(0.1)
                continue

            frequency = self.config_manager.get(f'frequency_{index}')
            self.key_press_queue.append(('key', key))
            time.sleep(frequency)

    def schedule_mouse_click(self, button, frequency):
        next_click_time = time.perf_counter()
        while self.should_press.is_set():
            if self.is_paused.is_set():
                time.sleep(0.01)
                continue
            current_time = time.perf_counter()
            if current_time >= next_click_time:
                self.key_press_queue.append(('mouse', button))
                next_click_time = current_time + frequency
            else:
                time.sleep(0.01)

    def process_key_press_queue(self):
        while self.should_press.is_set():
            if self.is_paused.is_set():
                time.sleep(0.01)
                continue

            try:
                action_type, action = self.key_press_queue.popleft()
                with self.lock:
                    if action_type == 'key':
                        if hasattr(Key, action.lower()):
                            key_obj = getattr(Key, action.lower())
                        else:
                            key_obj = action
                        self.keyboard_controller.press(key_obj)
                        time.sleep(0.05)
                        self.keyboard_controller.release(key_obj)
                    elif action_type == 'mouse':
                        if action == 'left':
                            self.mouse_controller.click(Button.left)
                        elif action == 'right':
                            self.mouse_controller.click(Button.right)
            except IndexError:
                time.sleep(0.01)
            except Exception as e:
                logging.error(f"Error processing {action_type} action {action}: {e}")

    def handle_manual_keys(self):
        def on_press(key):
            if not self.should_press.is_set():
                return False
            if key not in self.manual_keys_pressed:
                self.manual_keys_pressed.add(key)
                self.key_press_queue.append(('manual_press', key))

        def on_release(key):
            if not self.should_press.is_set():
                return False
            if key in self.manual_keys_pressed:
                self.manual_keys_pressed.remove(key)
                self.key_press_queue.append(('manual_release', key))

        with Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

    def press_hp_key(self):
        hp_key = self.config_manager.get('hp_key')
        if not hp_key:
            logging.warning("HP key is not set.")
            return

        with self.lock:
            # Check if there's already an HP key press in the queue
            if any(action == ('key', hp_key) for action in self.key_press_queue):
                logging.debug("HP key press already queued, skipping.")
                return

            # Add the HP key press to the queue
            self.key_press_queue.append(('key', hp_key))

        # Wait for the key press to be processed
        while ('key', hp_key) in self.key_press_queue:
            time.sleep(0.01)

        # Add a cooldown period after the key press
        time.sleep(0.5)