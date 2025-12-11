import json
import os
import platformdirs

APP_NAME = "ag-accept"
APP_AUTHOR = "RyosukeMondo"

class ConfigManager:
    def __init__(self):
        self.config_dir = platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)
        self.config_path = os.path.join(self.config_dir, "config.json")
        self.default_config = {
            "interval": 1.0,
            "target_window_title": "Antigravity",
            "search_texts_ide": ["Run command?", "Reject", "Accept"], # Fixed list
            "search_texts_agent_manager": ["Accept"], # Ensure single item list
            "context_text_agent_manager": ["Run command?"],
            "mode": "AgentManager",
            "debug_enabled": False,
            "window_width": 600,
            "window_height": 700
        }
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_path):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.default_config, f, indent=4)
            except Exception as e:
                print(f"Error creating default config: {e}")
                return self.default_config.copy()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                # Merge with defaults to ensure all keys exist
                config = self.default_config.copy()
                config.update(user_config)
                
                # Check if we need to migrate/save specific new keys
                should_save = False
                for key in self.default_config:
                    if key not in user_config:
                        should_save = True
                
                if should_save:
                    try:
                        with open(self.config_path, "w", encoding="utf-8") as f_out:
                             json.dump(config, f_out, indent=4)
                        print("Config migrated to new version.")
                    except Exception as e:
                        print(f"Error saving migrated config: {e}")

                return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.default_config.copy()

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
    
    def reload(self):
        self.config = self.load_config()

    def get_config_path(self):
        return self.config_path
