import threading
import time
import logging
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Controller as KeyboardController, Key, Listener, KeyCode
from queue import Queue, Empty, PriorityQueue

class PrioritizedItem:
    def __init__(self, priority, action_type, action):
        self.priority = priority
        self.action_type = action_type
        self.action = action

    def __lt__(self, other):
        return self.priority < other.priority

class KeyPresser:
    def __init__(self, config, config_manager):
        self.config_manager = config_manager
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        self.should_press = threading.Event()
        self.is_paused = threading.Event()
        self.lock = threading.Lock()
        self.threads = []
        self.manual_key_thread = None
        self.manual_keys_pressed = set()
        self.key_press_queue = PriorityQueue()
        self.hp_key_press_queue = Queue()
        self.key_press_thread = None
        self.shift_thread = None
        self.config = config

    def update_config(self, new_config):
        self.config = new_config
        self.config_manager.update_config(new_config)
        if self.should_press.is_set():
            self.stop_pressing()
            self.start_pressing()

    def start_pressing(self):
        self.should_press.set()
        logging.debug(f"Left click var: {self.config_manager.get('left_click_var')}")
        logging.debug(f"Right click var: {self.config_manager.get('right_click_var')}")
        logging.debug(f"Left click freq: {self.config_manager.get('left_click_freq')}")
        logging.debug(f"Right click freq: {self.config_manager.get('right_click_freq')}")
        logging.debug(f"Hold shift key: {self.config_manager.get('hold_shift_key')}")

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

        if self.config_manager.get('hold_shift_key'):
            self.shift_thread = threading.Thread(target=self.hold_shift_key)
            self.shift_thread.start()
            self.threads.append(self.shift_thread)

    def stop_pressing(self):
        self.should_press.clear()
        logging.info("Stopping all key pressing operations.")
        for thread in self.threads:
            thread.join()
        self.threads.clear()
        while not self.key_press_queue.empty():
            try:
                self.key_press_queue.get_nowait()
            except Empty:
                pass
        while not self.hp_key_press_queue.empty():
            try:
                self.hp_key_press_queue.get_nowait()
            except Empty:
                pass
        self.keyboard_controller.release(Key.shift)

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
            self.key_press_queue.put(PrioritizedItem(1, 'key', key))  # Use priority 1 for normal keys
            time.sleep(frequency)

    def schedule_mouse_click(self, button, frequency):
        next_click_time = time.perf_counter()
        while self.should_press.is_set():
            if self.is_paused.is_set():
                time.sleep(0.01)
                continue
            current_time = time.perf_counter()
            if current_time >= next_click_time:
                self.key_press_queue.put(PrioritizedItem(1, 'mouse', button))  # Use priority 1 for mouse clicks
                next_click_time = current_time + frequency
            else:
                time.sleep(0.01)

    def process_key_press_queue(self):
        while self.should_press.is_set():
            if self.is_paused.is_set():
                time.sleep(0.01)
                continue

            try:
                # First, check the HP key press queue
                try:
                    action_type, action = self.hp_key_press_queue.get_nowait()
                    self.process_action(action_type, action)
                except Empty:
                    # If no HP key press, process from the main queue
                    item = self.key_press_queue.get(timeout=0.1)
                    self.process_action(item.action_type, item.action)
            except Empty:
                pass
            except Exception as e:
                logging.error(f"Error processing action: {e}")

    def process_action(self, action_type, action):
        with self.lock:
            if action_type == 'key':
                if isinstance(action, str) and hasattr(Key, action.lower()):
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

    def handle_manual_keys(self):
        def on_press(key):
            if not self.should_press.is_set():
                return False
            if key not in self.manual_keys_pressed:
                self.manual_keys_pressed.add(key)
                self.key_press_queue.put(PrioritizedItem(1, 'manual_press', key))  # Use priority 1 for manual keys

        def on_release(key):
            if not self.should_press.is_set():
                return False
            if key in self.manual_keys_pressed:
                self.manual_keys_pressed.remove(key)
                self.key_press_queue.put(PrioritizedItem(1, 'manual_release', key))  # Use priority 1 for manual keys

        with Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

    def press_hp_key(self):
        hp_key = self.config_manager.get('hp_key')
        hp_frequency = self.config_manager.get('hp_frequency', 0.1)
        if not hp_key:
            logging.warning("HP key is not set.")
            return

        self.hp_key_press_queue.put(('key', hp_key))
        time.sleep(hp_frequency)

    def hold_shift_key(self):
        while self.should_press.is_set():
            if self.config_manager.get('hold_shift_key'):
                self.keyboard_controller.press(Key.shift)
                while self.should_press.is_set() and self.config_manager.get('hold_shift_key'):
                    time.sleep(0.1)
                self.keyboard_controller.release(Key.shift)
            else:
                time.sleep(0.1)