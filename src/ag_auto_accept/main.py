
import tkinter as tk
from tkinter import scrolledtext
import threading
import time
import re
import json
import os
import platformdirs
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

APP_NAME = "ag-auto-accept"
APP_AUTHOR = "RyosukeMondo"

def load_config():
    config_dir = platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)
    config_path = os.path.join(config_dir, "config.json")
    
    default_config = {
        "interval": 1.0,
        "target_window_title": "Antigravity",
        "search_texts": ["Run command? Reject AcceptAlt+⏎"]
    }
    
    if not os.path.exists(config_path):
        try:
            os.makedirs(config_dir, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
        except Exception as e:
            print(f"Error creating default config: {e}")
            return default_config

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
            # Merge with defaults to ensure all keys exist
            config = default_config.copy()
            config.update(user_config)
            return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return default_config

class AutoAccepter:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Accepter")
        self.root.geometry("500x400")

        self.config = load_config()

        # Control Frame
        control_frame = tk.Frame(root)
        control_frame.pack(pady=10, padx=10, fill=tk.X)

        # Interval
        tk.Label(control_frame, text="Interval (sec):").pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value=str(self.config.get("interval", 1.0)))
        tk.Entry(control_frame, textvariable=self.interval_var, width=10).pack(side=tk.LEFT, padx=5)

        # Start/Stop Buttons
        self.start_btn = tk.Button(control_frame, text="Start", command=self.start_monitoring, bg="#ccffcc")
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(control_frame, text="Stop", command=self.stop_monitoring, state=tk.DISABLED, bg="#ffcccc")
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Config Button
        self.config_btn = tk.Button(control_frame, text="Open Config", command=self.open_config)
        self.config_btn.pack(side=tk.LEFT, padx=5)

        # Log Area
        self.log_area = scrolledtext.ScrolledText(root, state=tk.DISABLED, height=15)
        self.log_area.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        # Log config path for user info
        config_dir = platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)
        self.log(f"Config loaded from: {os.path.join(config_dir, 'config.json')}")

        self.is_running = False
        self.monitor_thread = None
        self.current_stop_event = None

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)

    def open_config(self):
        config_dir = platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)
        config_path = os.path.join(config_dir, "config.json")
        try:
            os.startfile(config_path)
            self.log("Opened config file.")
        except Exception as e:
            self.log(f"Error opening config: {e}")

    def start_monitoring(self):
        # Reload config to get latest searches/titles
        self.config = load_config()
        self.log("Config reloaded.")
        
        try:
            interval = float(self.interval_var.get())
            if interval <= 0:
                raise ValueError("Interval must be positive")
        except ValueError:
            self.log("Error: Invalid interval")
            return

        self.is_running = True
        # Create a new event for this run to avoid race conditions with old threads
        self.current_stop_event = threading.Event()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log(f"Started monitoring (Interval: {interval}s)")

        self.monitor_thread = threading.Thread(target=self.run_monitor_loop, args=(interval, self.current_stop_event))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop_monitoring(self):
        if self.is_running:
            self.is_running = False
            if self.current_stop_event:
                self.current_stop_event.set()
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.log("Stopping monitoring...")

    def run_monitor_loop(self, interval, stop_event):
        desktop = Desktop(backend="uia")
        target_title_part = self.config.get("target_window_title", "Antigravity")
        search_texts = self.config.get("search_texts", ["Run command? Reject AcceptAlt+⏎"])
        
        while not stop_event.is_set():
            try:
                found_targets = []
                try:
                    windows = desktop.windows()
                    for w in windows:
                        try:
                            title = w.window_text()
                            if target_title_part in title:
                                found_targets.append(w)
                        except Exception:
                            continue # Window might have closed
                except Exception as e:
                    self.log(f"Fail: Error listing windows: {e}")
                    stop_event.wait(interval)
                    continue

                if not found_targets:
                    pass
                else:
                    for w in found_targets:
                        try:
                            title = w.window_text()
                            # Updated to check for "Auto Accepter" to prevent self-detection if title changes
                            if "Auto Accepter" in title or "Antigravity Monitor" in title:
                                continue # Skip self
                            
                            self.log(f"Checking window: '{title}'")
                            
                            # Search for "Accept" text in descendants
                            has_accept = False
                            try:
                                descendants = w.descendants()
                                for item in descendants:
                                        t = item.window_text()
                                        if t:
                                            for target_text in search_texts:
                                                if target_text in t:
                                                    has_accept = True
                                                    self.log(f"Found target text in element: '{t}'")
                                                    break
                                        if has_accept:
                                            break
                            except Exception as e:
                                self.log(f"Warning: scanning failed for '{title}': {e}")
                            
                            if has_accept:
                                self.log(f"Refocusing and sending key to '{title}'")
                                try:
                                    w.set_focus()
                                except Exception as focus_err:
                                     self.log(f"Focus warning: {focus_err}")
                                
                                w.type_keys('%{ENTER}', with_spaces=True)
                                self.log("Success: Sent Alt+Enter")
                            else:
                                self.log(f"Skipping '{title}': Target text not found.")
                            
                        except Exception as e:
                            self.log(f"Fail: Operation on '{title}' failed. Error: {e}")

            except Exception as e:
                self.log(f"Error in loop: {e}")

            if stop_event.wait(interval):
                break
            
        self.log("Monitoring stopped.")

def main():
    root = tk.Tk()
    app = AutoAccepter(root)
    root.mainloop()

if __name__ == "__main__":
    main()
