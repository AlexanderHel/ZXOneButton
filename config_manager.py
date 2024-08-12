import json
import os
from functools import lru_cache

class ConfigManager:
    def __init__(self):
        self.config = {}
        self.default_config = {
            "left_click_var": False,
            "left_click_freq": 0.01,
            "right_click_var": False,
            "right_click_freq": 0.01,
            "hold_right_click_var": False,
            "key_to_press_0": "",
            "key_to_press_1": "",
            "key_to_press_2": "",
            "key_to_press_3": "",
            "frequency_0": 0.01,
            "frequency_1": 0.01,
            "frequency_2": 0.01,
            "frequency_3": 0.01,
            "hp_key": "",
            "hp_level": 85,
            "hp_frequency": 0.1,
            "monitor_hp": True,
            "monitor_diablo_window": True,
            "hold_shift_key": False
        }
        self.is_dirty = False
        self.load_config()

    def load_config(self):
        if not os.path.exists('default_config.json'):
            with open('default_config.json', 'w') as f:
                json.dump(self.default_config, f, indent=4)

        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                loaded_config = json.load(f)
                # Update the loaded config with any new default settings
                self.config = self.default_config.copy()
                self.config.update(loaded_config)
        else:
            self.config = self.default_config.copy()
        
        self.save_config()

    def save_config(self):
        if self.is_dirty:
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4)
            self.is_dirty = False

    def update_config(self, new_config):
        self.config.update(new_config)
        self.is_dirty = True
        self.get.cache_clear()  # Clear the cache for the 'get' method
        self.save_config()

    @lru_cache(maxsize=32)
    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        if self.config.get(key) != value:
            self.config[key] = value
            self.is_dirty = True
            self.get.cache_clear()  # Clear the cache for the 'get' method

    def save_profile(self, profile_name):
        if not os.path.exists('profiles'):
            os.makedirs('profiles')
        profile_path = os.path.join('profiles', f'{profile_name}.json')
        with open(profile_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def load_profile(self, profile_name):
        profile_path = os.path.join('profiles', f'{profile_name}.json')
        if os.path.exists(profile_path):
            with open(profile_path, 'r') as f:
                loaded_profile = json.load(f)
                # Update the loaded profile with any new default settings
                self.config = self.default_config.copy()
                self.config.update(loaded_profile)
            self.is_dirty = True
            self.get.cache_clear()  # Clear the cache for the 'get' method
            self.save_config()

    @lru_cache(maxsize=1)
    def get_profile_list(self):
        if not os.path.exists('profiles'):
            return []
        return [f.split('.')[0] for f in os.listdir('profiles') if f.endswith('.json')]

    def reset_to_default(self):
        if self.config != self.default_config:
            self.config = self.default_config.copy()
            self.is_dirty = True
            self.get.cache_clear()  # Clear the cache for the 'get' method
            self.save_config()

    def cleanup(self):
        self.save_config()  # Ensure any unsaved changes are written to disk