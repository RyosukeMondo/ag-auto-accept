
import warnings
# Suppress SyntaxWarning from pywinauto (invalid escape sequences in Python 3.12)
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pywinauto")

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import re
import json
import os
import platformdirs
from pywinauto import Desktop
from pywinauto.keyboard import send_keys
import ctypes

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

        self.is_dark_mode = True # Default to Dark Mode

        # Control Frame
        self.control_frame = tk.Frame(root)
        self.control_frame.pack(pady=10, padx=10, fill=tk.X)

        # Interval
        self.interval_label = tk.Label(self.control_frame, text="Interval (sec):")
        self.interval_label.pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value=str(self.config.get("interval", 1.0)))
        self.interval_entry = tk.Entry(self.control_frame, textvariable=self.interval_var, width=10)
        self.interval_entry.pack(side=tk.LEFT, padx=5)

        # Start/Stop Buttons
        self.start_btn = tk.Button(self.control_frame, text="Start", command=self.start_monitoring, bg="#ccffcc")
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(self.control_frame, text="Stop", command=self.stop_monitoring, state=tk.DISABLED, bg="#ffcccc")
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Config Button
        self.config_btn = tk.Button(self.control_frame, text="Open Config", command=self.open_config)
        self.config_btn.pack(side=tk.LEFT, padx=5)

        # Theme Toggle
        self.theme_btn = tk.Button(self.control_frame, text="☀/🌙", command=self.toggle_theme, width=4)
        self.theme_btn.pack(side=tk.RIGHT, padx=5)

        # Log Area (Treeview for Table Mode)
        columns = ("time", "status", "message")
        self.log_tree = ttk.Treeview(root, columns=columns, show="headings", height=15)
        
        # Column Headings
        self.log_tree.heading("time", text="Time")
        self.log_tree.heading("status", text="Status")
        self.log_tree.heading("message", text="Message")
        
        # Column Configuration
        self.log_tree.column("time", width=60, anchor=tk.CENTER)
        self.log_tree.column("status", width=70, anchor=tk.CENTER)
        self.log_tree.column("message", width=300, anchor=tk.W) # Expandable
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(root, orient=tk.VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscroll=scrollbar.set)
        
        # We need them to be in the same frame to look good. Let's wrap them in a frame.
        self.log_tree.pack_forget() # Undo the pack above if it was there (it wasn't in this block, but safe to keep logic consistent)
        
        self.log_frame = tk.Frame(root)
        self.log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.apply_theme()
        
        # Log config path for user info
        config_dir = platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)
        self.log(f"Config loaded from: {os.path.join(config_dir, 'config.json')}")

        self.is_running = False
        self.monitor_thread = None
        self.current_stop_event = None

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()

    def apply_theme(self):
        style = ttk.Style()
        style.theme_use("default") # Use default to allow easier color customization specifically for Treeview

        if self.is_dark_mode:
            bg_color = "#2b2b2b"
            fg_color = "#ffffff"
            tree_bg = "#1e1e1e"
            tree_fg = "#dddddd"
            tree_sel = "#3e3e3e"
            
            # Tags
            self.log_tree.tag_configure("success", foreground="#90ee90") # Light Green
            self.log_tree.tag_configure("error", foreground="#ff6b6b")   # Light Red
            self.log_tree.tag_configure("muted", foreground="#aaaaaa")   # Light Gray
            self.log_tree.tag_configure("normal", foreground="#ffffff")
        else:
            bg_color = "SystemButtonFace" # Default windows gray-ish
            fg_color = "black"
            tree_bg = "white"
            tree_fg = "black"
            tree_sel = "#3399ff" # Default selection blue-ish
            
            # Tags
            self.log_tree.tag_configure("success", foreground="green")
            self.log_tree.tag_configure("error", foreground="red")
            self.log_tree.tag_configure("muted", foreground="gray")
            self.log_tree.tag_configure("normal", foreground="black")

        # Apply to containers
        self.root.configure(bg=bg_color)
        self.control_frame.configure(bg=bg_color)
        self.log_frame.configure(bg=bg_color)
        
        # Apply to labels and standard widgets
        # Note: Buttons on Windows don't always accept BG changes cleanly without style tweaks, 
        # but we'll try for the Labels and basics.
        self.interval_label.configure(bg=bg_color, fg=fg_color)
        self.interval_entry.configure(bg=tree_bg, fg=tree_fg, insertbackground=fg_color)
        
        # Configure Treeview colors via Style
        style.configure("Treeview", 
                        background=tree_bg, 
                        foreground=tree_fg, 
                        fieldbackground=tree_bg,
                        borderwidth=0)
        style.map("Treeview", background=[('selected', tree_sel)], foreground=[('selected', 'white')])
        
        # Header style
        style.configure("Treeview.Heading", background=bg_color, foreground=fg_color, relief="flat")
        style.map("Treeview.Heading", background=[('active', tree_sel)])

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        
        # Determine Status and Tag
        status = "INFO"
        tag = "normal"
        
        msg_lower = message.lower()
        if "success" in msg_lower:
            status = "SUCCESS"
            tag = "success"
        elif "error" in msg_lower or "fail" in msg_lower:
            status = "ERROR"
            tag = "error"
        elif "checking" in msg_lower or "skipping" in msg_lower:
            status = "CHECK"
            tag = "muted"
        
        # Insert into Treeview
        item_id = self.log_tree.insert("", tk.END, values=(timestamp, status, message), tags=(tag,))
        self.log_tree.see(item_id)

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
                                
                                # Save currently focused window
                                previous_focus_hwnd = ctypes.windll.user32.GetForegroundWindow()

                                try:
                                    w.set_focus()
                                except Exception as focus_err:
                                     self.log(f"Focus warning: {focus_err}")
                                
                                w.type_keys('%{ENTER}', with_spaces=True)
                                self.log("Success: Sent Alt+Enter")

                                # Restore focus to previous window
                                if previous_focus_hwnd:
                                    try:
                                        # Use AttachThreadInput to ensure we can switch focus back if needed
                                        # But simple SetForegroundWindow might work if we just had focus
                                        ctypes.windll.user32.SetForegroundWindow(previous_focus_hwnd)
                                        # self.log("Restored focus to previous window.")
                                    except Exception as e:
                                        self.log(f"Failed to restore focus: {e}")
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
