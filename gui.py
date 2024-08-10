import dearpygui.dearpygui as dpg
import threading
import logging
import traceback
from pynput import keyboard
import numpy as np
from PIL import Image
import win32gui
import time
import os
import json
import sys
from typing import List, Tuple
import math
import ctypes

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class GUI:
    def __init__(self, config_manager, hp_monitor, key_presser):
        self.config_manager = config_manager
        self.hp_monitor = hp_monitor
        self.key_presser = key_presser
        self.status_labels = {}
        self.listener = None
        self.update_thread = None
        self.should_update = threading.Event()
        self.hp_history: List[Tuple[float, float]] = []
        self.profiles_dir = "profiles"
        self.key_input_ids = []
        self.freq_input_ids = []
        self.log_window = None
        self.screenshot_texture_id = None
        self.screenshot_image = None
        self.frame_time = 1.0 / 60.0  # Target 60 FPS
        self.scaling_factor = self.get_display_scaling_factor()

    def get_display_scaling_factor(self):
        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            return user32.GetDpiForSystem() / 96.0
        except Exception as e:
            logging.error(f"Failed to get display scaling factor: {e}")
            return 1.0

    def setup(self):
        try:
            logging.debug("Setting up GUI")
            self.load_font()
            self.set_theme()
            
            window_width = int(615 * self.scaling_factor)
            window_height = int(825 * self.scaling_factor)

            with dpg.window(label="ZXOneButton", width=window_width, height=window_height, tag="main_window", no_close=True):
                with dpg.group(horizontal=True):
                    self.create_click_settings()
                    self.create_key_settings()
                    self.create_hp_settings()
                with dpg.group(horizontal=True):
                    self.create_status_section()
                    with dpg.group():
                        self.create_profile_section()
                        self.create_guide()
                    self.create_log_window()    

            self.setup_viewport()
            self.setup_hotkeys()
            self.start_status_update_thread()
            
            dpg.set_primary_window("main_window", True)
            logging.debug("GUI setup complete")
        except Exception as e:
            logging.error(f"An error occurred during setup: {str(e)}")
            logging.error(traceback.format_exc())
            raise

    def run_with_frame_limit(self):
        while dpg.is_dearpygui_running():
            start_time = time.perf_counter()
            
            dpg.render_dearpygui_frame()
            
            end_time = time.perf_counter()
            frame_duration = end_time - start_time
            if frame_duration < self.frame_time:
                time.sleep(self.frame_time - frame_duration)

    def load_font(self):
        try:
            with dpg.font_registry():
                default_font_path = self.get_resource_path(os.path.join("fonts", "OpenSans-Medium.ttf"))
                header_font_path = self.get_resource_path(os.path.join("fonts", "OpenSans-Bold.ttf"))
                
                logging.debug(f"Loading default font from: {default_font_path}")
                if not os.path.exists(default_font_path):
                    logging.error(f"Default font file not found: {default_font_path}")
                default_font = dpg.add_font(default_font_path, 19)
                
                logging.debug(f"Loading header font from: {header_font_path}")
                if not os.path.exists(header_font_path):
                    logging.error(f"Header font file not found: {header_font_path}")
                self.header_font = dpg.add_font(header_font_path, 22)
                
                dpg.bind_font(default_font)
        except Exception as e:
            logging.error(f"Error loading fonts: {str(e)}")
            raise

    def set_theme(self):
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (0, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (235, 235, 235))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (139, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (165, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (185, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (20, 20, 20))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (40, 40, 40))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (60, 60, 60))
                dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (139, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (139, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (185, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (165, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (185, 0, 0))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 5)
        dpg.bind_theme(global_theme)


    def create_click_settings(self):
        try:
            with dpg.child_window(label="Click Settings", width=138, height=280):
                dpg.add_text("Click Settings:", color=(255, 255, 255))
                dpg.bind_item_font(dpg.last_item(), self.header_font)
                with dpg.group():
                    if self.config_manager is None:
                        logging.error("config_manager is None")
                        return
                    
                    self.left_click_checkbox = dpg.add_checkbox(
                        label="Left Click",
                        default_value=self.config_manager.get('left_click_var'),
                        callback=lambda sender, app_data, user_data: self.update_left_click_var(sender, app_data, user_data, unused=None)
                    )
                    dpg.add_text("LC Frequency (ms)")
                    left_click_freq = dpg.add_input_int(
                        label="",
                        default_value=int(self.config_manager.get('left_click_freq') * 1000),
                        callback=lambda sender, app_data, user_data: self.update_left_click_freq(sender, app_data, user_data, unused=None),
                        width=100,
                        step=100
                    )
                    self.freq_input_ids.append(left_click_freq)
                    with dpg.tooltip(parent=self.left_click_checkbox):
                        dpg.add_text("Enable/disable left click auto-pressing")

                    self.right_click_checkbox = dpg.add_checkbox(
                        label="Right Click",
                        default_value=self.config_manager.get('right_click_var'),
                        callback=lambda sender, app_data, user_data: self.update_right_click_var(sender, app_data, user_data, unused=None)
                    )
                    dpg.add_text("RC Frequency (ms)")
                    right_click_freq = dpg.add_input_int(
                        label="",
                        default_value=int(self.config_manager.get('right_click_freq') * 1000),
                        callback=lambda sender, app_data, user_data: self.update_right_click_freq(sender, app_data, user_data, unused=None),
                        width=100,
                        step=100
                    )
                    self.freq_input_ids.append(right_click_freq)
                    with dpg.tooltip(parent=self.right_click_checkbox):
                        dpg.add_text("Enable/disable right click auto-pressing")

                    dpg.add_spacer(height=2)
                    dpg.add_separator()
                    dpg.add_spacer(height=2)

                    self.hold_shift_checkbox = dpg.add_checkbox(
                        label="Hold Shift",
                        default_value=bool(self.config_manager.get('hold_shift_key')),
                        callback=lambda sender, app_data, user_data: self.update_hold_shift_var(sender, app_data, user_data, unused=None)
                    )
                    with dpg.tooltip(parent=self.hold_shift_checkbox):
                        dpg.add_text("Enable/disable holding the Shift key")
        except Exception as e:
            logging.error(f"Error in create_click_settings: {str(e)}")
            logging.error(traceback.format_exc())
            raise

    def create_key_settings(self):
        with dpg.child_window(label="Key Settings", width=182, height=280):
            dpg.add_text("Key Settings:", color=(255, 255, 255))
            dpg.bind_item_font(dpg.last_item(), self.header_font)
            for i in range(4):
                with dpg.group():
                    key_input = dpg.add_input_text(label=f"Key {i+1}", default_value=self.config_manager.get(f'key_to_press_{i}'), callback=lambda sender, app_data, user_data: self.update_key_to_press(sender, app_data, user_data, unused=None), user_data=i, width=50)
                    self.key_input_ids.append(key_input)
                    freq_input = dpg.add_input_int(label=f"Freq (ms)", default_value=int(self.config_manager.get(f'frequency_{i}') * 1000), callback=lambda sender, app_data, user_data: self.update_frequency(sender, app_data, user_data, unused=None), user_data=i, width=100, step=100)
                    self.freq_input_ids.append(freq_input)
                    with dpg.tooltip(parent=key_input):
                        dpg.add_text(f"Set the key to be auto-pressed for slot {i+1}")

    def screenshot_image_available(self):
        return True

    def create_hp_settings(self):
        with dpg.child_window(label="HP Settings", width=248, height=280):
            dpg.add_text("HP Settings:", color=(255, 255, 255))
            dpg.bind_item_font(dpg.last_item(), self.header_font)

            self.monitor_hp_checkbox = dpg.add_checkbox(
                label="HP Monitor",
                default_value=bool(self.config_manager.get('monitor_hp')),
                callback=lambda sender, app_data, user_data: self.update_monitor_hp_var(sender, app_data, user_data, unused=None)
            )
            with dpg.tooltip(parent=self.monitor_hp_checkbox):
                dpg.add_text("Enable/disable HP monitoring")

            with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False, borders_innerV=False, borders_outerV=False):
                dpg.add_table_column()
                dpg.add_table_column()

                with dpg.table_row():
                    dpg.add_text("HP Key")
                    dpg.add_text("HP Threshold")

                with dpg.table_row():
                    self.hp_key_input = dpg.add_input_text(
                        label="",
                        default_value=self.config_manager.get('hp_key').upper(),
                        callback=lambda sender, app_data, user_data: self.update_hp_key(sender, app_data, user_data, unused=None),
                        width=100,
                        tag="hp_key_input"
                    )
                    with dpg.tooltip(parent=self.hp_key_input):
                        dpg.add_text("Set the key for using health potions")

                    self.hp_scale = dpg.add_slider_int(
                        label="",
                        min_value=0,
                        max_value=100,
                        default_value=int(self.config_manager.get('hp_level')),
                        callback=lambda sender, app_data, user_data: self.update_hp_level(sender, app_data, user_data, unused=None),
                        width=-1
                    )
                    with dpg.tooltip(parent=self.hp_scale):
                        dpg.add_text("Adjust the HP threshold for potion use")

            dpg.add_separator()
            dpg.add_spacer(height=3)

            self.select_screenshot_area_button = dpg.add_button(
                label="Select Screenshot Area", 
                callback=lambda sender, app_data, user_data: self.select_screenshot_area(),
                width=-1
            )
            with dpg.tooltip(parent=self.select_screenshot_area_button):
                dpg.add_text("Select the area of the screen where the HP bar is located")

            with dpg.group(horizontal=True):
                self.screenshot_group = dpg.add_group()
            
            # Initialize with "No Screenshot Area Selected" text
            self.update_screenshot_display(None)

    def select_screenshot_area(self):
        self.hp_monitor.select_screenshot_area()
        self.log_message("Screenshot area selected successfully", color=(0, 255, 0))

    def update_screenshot_display(self, screenshot=None):
        dpg.delete_item(self.screenshot_group, children_only=True)
        if screenshot:
            dpg.add_text("No Screenshot Area Selected", color=(255, 0, 0), parent=self.screenshot_group)

    def update_resolution(self, sender, app_data, user_data, unused):
        self.config_manager.set('resolution', app_data)
        self.hp_monitor.update_resolution(app_data)

    def create_status_section(self):
        with dpg.child_window(label="Status", width=390, height=380):
            dpg.add_text("Status:", color=(255, 255, 255))
            dpg.bind_item_font(dpg.last_item(), self.header_font)
            self.status_labels = {
                "d4_status": dpg.add_text("Diablo IV Window Status: Idle"),
                "tool_status": dpg.add_text("Tool Status: Idle"),
                "hp_monitoring_status": dpg.add_text("HP Monitoring Status: Idle"),
                "current_hp": dpg.add_text("Current HP: Idle")
            }
            for label in self.status_labels.values():
                self.update_status_label_color_coded(label, dpg.get_value(label))

            with dpg.plot(label="HP Graph", height=200, width=-1):
                dpg.add_plot_legend()
                dpg.add_plot_axis(dpg.mvXAxis, label="Time")
                dpg.add_plot_axis(dpg.mvYAxis, label="HP %", tag="y_axis")
                dpg.set_axis_limits("y_axis", 0, 200)
                self.hp_series = dpg.add_line_series([], [], label="HP", parent="y_axis")
                dpg.bind_item_handler_registry(self.hp_series, "hp_series_handler")

            with dpg.item_handler_registry(tag="hp_series_handler"):
                dpg.add_item_hover_handler(callback=self.hp_series_hover)

    def hp_series_hover(self, sender, app_data, user_data, unused):
        if self.hp_history:
            plot = dpg.get_item_parent(sender)
            mouse_pos = dpg.get_plot_mouse_pos()
            start_time = self.hp_history[0][0]
            x = [(t - start_time) for t, _ in self.hp_history]
            y = [hp for _, hp in self.hp_history]
            
            closest_point = min(range(len(x)), key=lambda i: abs(x[i] - mouse_pos[0]))
            
            dpg.set_value("hover_text", f"Time: {x[closest_point]:.2f}s, HP: {y[closest_point]:.2f}%")
            dpg.configure_item("hover_text", pos=dpg.get_mouse_pos())

        with dpg.tooltip(parent=plot):
            dpg.add_text("", tag="hover_text")

        with dpg.tooltip(parent=plot):
            dpg.add_text("", tag="hover_text")

    def create_profile_section(self):
        with dpg.child_window(label="Profiles", width=185, height=234):
            dpg.add_text("Profiles:", color=(255, 255, 255))
            dpg.bind_item_font(dpg.last_item(), self.header_font)
            with dpg.group():
                self.profile_name = dpg.add_input_text(label="", width=168)
                with dpg.tooltip(parent=self.profile_name):
                    dpg.add_text("Enter a name for the profile")
                self.save_profile_button = dpg.add_button(label="Save Profile", callback=lambda sender, app_data, user_data: self.save_profile(sender, app_data, user_data, unused=None), width=-1)
                with dpg.tooltip(parent=self.save_profile_button):
                    dpg.add_text("Save current settings as a new profile")
            self.load_profile_button = dpg.add_button(label="Load Profile", callback=lambda sender, app_data, user_data: self.load_profile(sender, app_data, user_data, unused=None), width=-1)
            with dpg.tooltip(parent=self.load_profile_button):
                dpg.add_text("Load settings from a saved profile")
            self.profile_list = dpg.add_combo(label="", width=168)
            with dpg.tooltip(parent=self.profile_list):
                dpg.add_text("Select a profile to load")
            self.update_profile_list()
            self.reset_button = dpg.add_button(label="Reset to Default", callback=lambda sender, app_data, user_data: self.reset_to_default(sender, app_data, user_data, unused=None), width=-1)
            with dpg.tooltip(parent=self.reset_button):
                dpg.add_text("Reset all settings to default values")
     
    def create_guide(self):
        with dpg.child_window(label="Guide", width=185, height=142):
            dpg.add_text("Keyboard Shortcuts:", color=(255, 255, 255))
            dpg.bind_item_font(dpg.last_item(), self.header_font)
            dpg.add_text("F3: Start/Stop tool")
            dpg.add_separator()
            dpg.add_spacer(height=2)

            # Add a button to trigger the popup
            dpg.add_button(label='About', callback=lambda: dpg.show_item('about_popup'), width=-1)

            # Define the popup window
            with dpg.popup(dpg.last_item(), modal=True, tag='about_popup'):
                dpg.add_text("Version 2.2.2")
                dpg.add_text("Prompter: TruongTieuPham")
                dpg.add_text("Code and Debug by Claude.ai and Perplexity.ai")

    def get_resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for Nuitka """
        try:
            # Check if the application is frozen (compiled with Nuitka)
            if '__compiled__' in globals():
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            full_path = os.path.join(base_path, relative_path)
            logging.debug(f"Resource path resolved: {full_path}")
            return full_path
        except Exception as e:
            logging.error(f"Error in get_resource_path: {str(e)}")
            return relative_path
        
    def setup_viewport(self):
        window_width = int(615 * self.scaling_factor)
        window_height = int(825 * self.scaling_factor)
        dpg.create_viewport(title='ZXOneButton', width=window_width, height=window_height)
        small_icon_path = self.get_resource_path(os.path.join("icons", "icon_32x32.ico"))
        large_icon_path = self.get_resource_path(os.path.join("icons", "icon_256x256.ico"))
        
        logging.debug(f"Setting small icon from: {small_icon_path}")
        if not os.path.exists(small_icon_path):
            logging.error(f"Small icon file not found: {small_icon_path}")
        dpg.set_viewport_small_icon(small_icon_path)
        
        logging.debug(f"Setting large icon from: {large_icon_path}")
        if not os.path.exists(large_icon_path):
            logging.error(f"Large icon file not found: {large_icon_path}")
        dpg.set_viewport_large_icon(large_icon_path)

    def setup_hotkeys(self):
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()

    def on_key_press(self, key):
        try:
            if key == keyboard.Key.f3:
                self.toggle_tool()
        except AttributeError:
            pass

    def toggle_tool(self):
        if self.key_presser.should_press.is_set():
            self.key_presser.stop_pressing()
            self.hp_monitor.stop_monitoring()
            self.update_status_label("Tool Status: Tool Stopped", "tool_status")
            self.update_status_label("HP Monitoring Status: Stopped", "hp_monitoring_status")
        else:
            self.key_presser.start_pressing()
            if self.config_manager.get('monitor_hp'):
                self.hp_monitor.start_monitoring()
            self.update_status_label("Tool Status: Tool Started", "tool_status")
            self.update_status_label("HP Monitoring Status: Started", "hp_monitoring_status")

    def update_left_click_var(self, sender, app_data, user_data, unused):
        self.config_manager.set('left_click_var', dpg.get_value(self.left_click_checkbox))

    def update_left_click_freq(self, sender, app_data, user_data, unused):
        self.config_manager.set('left_click_freq', app_data / 1000)

    def update_right_click_var(self, sender, app_data, user_data, unused):
        self.config_manager.set('right_click_var', dpg.get_value(self.right_click_checkbox))

    def update_right_click_freq(self, sender, app_data, user_data, unused):
        self.config_manager.set('right_click_freq', app_data / 1000)

    def update_hold_shift_var(self, sender, app_data, user_data, unused):
        self.config_manager.set('hold_shift_key', dpg.get_value(self.hold_shift_checkbox))

    def update_key_to_press(self, sender, app_data, user_data, unused):
        self.config_manager.set(f'key_to_press_{user_data}', app_data)

    def update_frequency(self, sender, app_data, user_data, unused):
        self.config_manager.set(f'frequency_{user_data}', app_data / 1000)

    def update_hp_key(self, sender, app_data, user_data, unused):
        lowercase_key = app_data.lower()
        self.config_manager.set('hp_key', lowercase_key)
        dpg.set_value(self.hp_key_input, lowercase_key.upper())

    def update_hp_level(self, sender, app_data, user_data, unused):
        self.config_manager.set('hp_level', app_data)

    def update_monitor_hp_var(self, sender, app_data, user_data, unused):
        self.config_manager.set('monitor_hp', dpg.get_value(self.monitor_hp_checkbox))

    def update_status_label(self, text, status_type):
        if status_type in self.status_labels:
            label = self.status_labels[status_type]
            self.update_status_label_color_coded(label, text)
            dpg.set_value(label, text)
        else:
            logging.warning(f"Unknown status type: {status_type}")

    def update_status_label_color_coded(self, label, text):
        orange_color = [255, 165, 0]
        red_color = [255, 0, 0]
        green_color = [0, 255, 0]

        if any(word in text for word in ["Idle"]):
            color = orange_color
        elif any(word in text for word in ["Not Active", "Stopped", "Disabled", "Tool Stopped", "Monitoring Disabled"]):
            color = red_color
        elif any(word in text for word in ["Active", "Started", "Completed", "Running", "Resumed", "Tool Running", "Tool Resumed", "Tool Started"]):
            color = green_color
        else:
            color = [255, 255, 255]

        with dpg.theme() as theme_id:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_Text, color)

        dpg.bind_item_theme(label, theme_id)
        dpg.set_value(label, text)

    def update_status_label_thread_safe(self, label, text):
        threading.Thread(target=self.update_status_label_color_coded, args=(label, text)).start()

    def start_status_update_thread(self):
        self.should_update.set()
        self.update_thread = threading.Thread(target=self.update_status_labels)
        self.update_thread.daemon = True
        self.update_thread.start()

    def update_status_labels(self):
        while self.should_update.is_set():
            self.update_diablo_window_status()
            self.update_hp()
            self.update_hp_graph()
            time.sleep(0.1)

    def update_diablo_window_status(self):
        active_window = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        if "Diablo IV" in active_window:
            if self.key_presser.should_press.is_set():
                status = "Diablo IV Window Status: Active - Tool Running"
            else:
                status = "Diablo IV Window Status: Active - Tool Stopped"
        else:
            if self.key_presser.should_press.is_set():
                status = "Diablo IV Window Status: Not Active - Tool Stopped"
                self.key_presser.stop_pressing()  # Instead of pausing, stop the tool
            else:
                status = "Diablo IV Window Status: Not Active - Tool Stopped"
        self.update_status_label(status, "d4_status")

    def update_hp(self):
        if self.hp_monitor.should_monitor.is_set():
            result = self.hp_monitor.get_hp_percentage()
            if result is not None:
                hp_percentage, screenshot = result
                status = f"Current HP: {hp_percentage:.2f}%"
                self.hp_history.append((time.time(), hp_percentage))
                if len(self.hp_history) > 60:  # Keep only last 60 seconds
                    self.hp_history.pop(0)
            else:
                status = "Current HP: Unable to calculate"
        else:
            status = "Current HP: Monitoring Disabled"
        self.update_status_label(status, "current_hp")

    def update_hp_graph(self):
        if self.hp_history:
            start_time = self.hp_history[0][0]
            x = [(t - start_time) for t, _ in self.hp_history]
            y = [hp for _, hp in self.hp_history]
            dpg.set_value(self.hp_series, [x, y])

            # Update the gradient for the HP graph
            with dpg.theme() as series_theme:
                with dpg.theme_component(dpg.mvLineSeries):
                    dpg.add_theme_color(dpg.mvPlotCol_Line, (139, 0, 0), category=dpg.mvThemeCat_Plots)
                    dpg.add_theme_style(dpg.mvPlotStyleVar_FillAlpha, 0.5, category=dpg.mvThemeCat_Plots)
            dpg.bind_item_theme(self.hp_series, series_theme)

    def save_profile(self, sender, app_data, user_data, unused):
        profile_name = dpg.get_value(self.profile_name)
        if not profile_name:
            dpg.add_text("Please enter a profile name", color=(255, 0, 0), parent="main_window")
            return

        if not os.path.exists(self.profiles_dir):
            os.makedirs(self.profiles_dir)

        profile_path = os.path.join(self.profiles_dir, f"{profile_name}.json")
        with open(profile_path, 'w') as f:
            json.dump(self.config_manager.config, f, indent=4)

        self.update_profile_list()

    def load_profile(self, sender, app_data, user_data, unused):
        selected_profile = dpg.get_value(self.profile_list)
        if not selected_profile:
            return
        profile_path = os.path.join(self.profiles_dir, selected_profile)
        with open(profile_path, 'r') as f:
            config = json.load(f)
        
        self.config_manager.config.update(config)
        self.config_manager.save_config()
        self.update_gui_from_config()

    def update_profile_list(self):
        if not os.path.exists(self.profiles_dir):
            return

        profiles = [f for f in os.listdir(self.profiles_dir) if f.endswith('.json')]
        dpg.configure_item(self.profile_list, items=profiles)

    def update_gui_from_config(self):
        dpg.set_value(self.left_click_checkbox, self.config_manager.get('left_click_var'))
        dpg.set_value(self.right_click_checkbox, self.config_manager.get('right_click_var'))
        dpg.set_value(self.monitor_hp_checkbox, bool(self.config_manager.get('monitor_hp')))
        dpg.set_value(self.hp_scale, int(self.config_manager.get('hp_level')))
        
        # Update left and right click frequencies
        dpg.set_value(self.freq_input_ids[0], int(self.config_manager.get('left_click_freq') * 1000))
        dpg.set_value(self.freq_input_ids[1], int(self.config_manager.get('right_click_freq') * 1000))
        dpg.set_value(self.hold_shift_checkbox, self.config_manager.get('hold_shift_key'))
        
        for i in range(4):
            dpg.set_value(self.key_input_ids[i], self.config_manager.get(f'key_to_press_{i}'))
            dpg.set_value(self.freq_input_ids[i+2], int(self.config_manager.get(f'frequency_{i}') * 1000))
        
        # Update HP key
        dpg.set_value(self.hp_key_input, self.config_manager.get('hp_key').upper())

    def reset_to_default(self, sender, app_data, user_data, unused):
        self.config_manager.reset_to_default()
        self.update_gui_from_config()

    def create_log_window(self):
        with dpg.child_window(label="Log", height=100, width=583, parent="main_window"):
            self.log_window = dpg.add_child_window(label="Log Content", autosize_x=True, autosize_y=True)

    def log_message(self, message, color=(255, 255, 255)):
        dpg.add_text(message, color=color, wrap=580, parent=self.log_window)
        dpg.set_y_scroll(self.log_window, -1)  # Scroll to the bottom

    def cleanup(self):
        self.should_update.clear()
        if self.update_thread:
            self.update_thread.join()
        if self.listener:
            self.listener.stop()
        self.key_presser.stop_pressing()
        self.hp_monitor.stop_monitoring()

if __name__ == "__main__":
    gui = GUI(None, None, None)  # For testing purposes only
    gui.setup()
    gui.run_with_frame_limit()