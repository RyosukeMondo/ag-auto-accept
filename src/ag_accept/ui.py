import tkinter as tk
from tkinter import ttk
import threading
import time
import os

class AutoAccepterUI:
    def __init__(self, root, config_manager, strategy_factory):
        self.root = root
        self.config_manager = config_manager
        self.strategy_factory = strategy_factory
        
        self.root.title("Ag-Accept")
        
        width = self.config_manager.get("window_width", 600)
        height = self.config_manager.get("window_height", 700)
        self.root.geometry(f"{width}x{height}")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.is_dark_mode = True # Default
        
        # State
        self.is_running = False
        self.monitor_thread = None
        self.current_stop_event = None
        self.snapshot_event = threading.Event()

        self.setup_ui()
        self.apply_theme()
        
        self.log(f"Config loaded from: {config_manager.get_config_path()}")

    def setup_ui(self):
        # Control Frame
        self.control_frame = tk.Frame(self.root)
        self.control_frame.pack(pady=10, padx=10, fill=tk.X)

        # Interval
        self.interval_label = tk.Label(self.control_frame, text="Interval (sec):")
        self.interval_label.pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value=str(self.config_manager.get("interval", 1.0)))
        self.interval_entry = tk.Entry(self.control_frame, textvariable=self.interval_var, width=10)
        self.interval_entry.pack(side=tk.LEFT, padx=5)

        # Mode Selector
        self.mode_label = tk.Label(self.control_frame, text="Mode:")
        self.mode_label.pack(side=tk.LEFT, padx=(10, 0))
        self.mode_var = tk.StringVar(value=self.config_manager.get("mode", "IDE"))
        self.mode_combo = ttk.Combobox(self.control_frame, textvariable=self.mode_var, values=["IDE", "AgentManager"], state="readonly", width=12)
        self.mode_combo.pack(side=tk.LEFT, padx=5)
        self.mode_combo.bind("<<ComboboxSelected>>", self.on_mode_change)

        # Debug Toggle
        self.debug_var = tk.BooleanVar(value=self.config_manager.get("debug_enabled", False))
        self.debug_chk = tk.Checkbutton(self.control_frame, text="Debug", variable=self.debug_var, command=self.on_debug_change)
        self.debug_chk.pack(side=tk.LEFT, padx=5)

        # Snapshot Button
        self.snapshot_btn = tk.Button(self.control_frame, text="Snapshot", command=self.trigger_snapshot, state=tk.DISABLED)
        self.snapshot_btn.pack(side=tk.LEFT, padx=5)

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

        # Log Area
        self.setup_log_area()

    def setup_log_area(self):
        # PanedWindow for split view (Log List | Log Detail)
        self.paned_window = tk.PanedWindow(self.root, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Frame for Treeview
        self.log_list_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.log_list_frame, height=200)

        columns = ("time", "status", "message")
        self.log_tree = ttk.Treeview(self.log_list_frame, columns=columns, show="headings", height=10)
        
        self.log_tree.heading("time", text="Time")
        self.log_tree.heading("status", text="Status")
        self.log_tree.heading("message", text="Message")
        
        self.log_tree.column("time", width=80, anchor=tk.CENTER)
        self.log_tree.column("status", width=80, anchor=tk.CENTER)
        self.log_tree.column("message", width=400, anchor=tk.W)

        scrollbar_y = ttk.Scrollbar(self.log_list_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        scrollbar_x = ttk.Scrollbar(self.log_list_frame, orient=tk.HORIZONTAL, command=self.log_tree.xview)
        self.log_tree.configure(yscroll=scrollbar_y.set, xscroll=scrollbar_x.set)
        
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind selection
        self.log_tree.bind("<<TreeviewSelect>>", self.on_log_select)

        # Frame for Detail View
        self.detail_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.detail_frame, height=100)

        self.detail_label = tk.Label(self.detail_frame, text="Log Details:", anchor="w")
        self.detail_label.pack(side=tk.TOP, fill=tk.X)

        self.detail_text = tk.Text(self.detail_frame, wrap=tk.WORD, height=5, state=tk.DISABLED)
        detail_scroll = ttk.Scrollbar(self.detail_frame, orient=tk.VERTICAL, command=self.detail_text.yview)
        self.detail_text.configure(yscroll=detail_scroll.set)
        
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def on_log_select(self, event):
        selection = self.log_tree.selection()
        if selection:
            item = self.log_tree.item(selection[0])
            values = item['values'] 
            # values is a tuple (time, status, message)
            # We want to show the full message in the detail view
            if len(values) >= 3:
                full_message = values[2]
                self.show_detail(full_message)

    def show_detail(self, message):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete(1.0, tk.END)
        self.detail_text.insert(tk.END, message)
        self.detail_text.config(state=tk.DISABLED)

    def log(self, message):
        # Allow calling from other threads
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, lambda: self.log(message))
            return
            
        timestamp = time.strftime("%H:%M:%S")
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
        
        # Insert into tree view
        # We store the full message in values. Treeview might truncate visually but data is there.
        item_id = self.log_tree.insert("", tk.END, values=(timestamp, status, message), tags=(tag,))
        self.log_tree.see(item_id)
        
        # Auto-scroll detail view if it was showing the latest log? 
        # For now, let's just keep the tree view following the latest.
    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()

    def apply_theme(self):
        style = ttk.Style()
        style.theme_use("default") 

        if self.is_dark_mode:
            bg_color = "#2b2b2b"
            fg_color = "#ffffff"
            tree_bg = "#1e1e1e"
            tree_fg = "#dddddd"
            tree_sel = "#3e3e3e"
            
            self.log_tree.tag_configure("success", foreground="#90ee90")
            self.log_tree.tag_configure("error", foreground="#ff6b6b")
            self.log_tree.tag_configure("muted", foreground="#aaaaaa")
            self.log_tree.tag_configure("normal", foreground="#ffffff")
        else:
            bg_color = "SystemButtonFace"
            fg_color = "black"
            tree_bg = "white"
            tree_fg = "black"
            tree_sel = "#3399ff"
            
            self.log_tree.tag_configure("success", foreground="green")
            self.log_tree.tag_configure("error", foreground="red")
            self.log_tree.tag_configure("muted", foreground="gray")
            self.log_tree.tag_configure("normal", foreground="black")

        self.root.configure(bg=bg_color)
        self.control_frame.configure(bg=bg_color)
        # self.log_frame is gone, we use paned_window now
        
        self.paned_window.configure(bg=bg_color)
        self.log_list_frame.configure(bg=bg_color)
        self.detail_frame.configure(bg=bg_color)
        self.detail_label.configure(bg=bg_color, fg=fg_color)
        self.detail_text.configure(bg=tree_bg, fg=tree_fg, insertbackground=fg_color)

        
        self.interval_label.configure(bg=bg_color, fg=fg_color)
        self.interval_entry.configure(bg=tree_bg, fg=tree_fg, insertbackground=fg_color)
        
        style.configure("Treeview", background=tree_bg, foreground=tree_fg, fieldbackground=tree_bg, borderwidth=0)
        style.map("Treeview", background=[('selected', tree_sel)], foreground=[('selected', 'white')])
        
        style.configure("Treeview.Heading", background=bg_color, foreground=fg_color, relief="flat")
        style.map("Treeview.Heading", background=[('active', tree_sel)])

    def open_config(self):
        try:
            import subprocess
            subprocess.Popen(['explorer', self.config_manager.get_config_path()])
            self.log("Opened config file.")
        except Exception as e:
            self.log(f"Error opening config: {e}")

    def start_monitoring(self):
        self.config_manager.reload()
        self.log("Config reloaded.")
        
        try:
            interval = float(self.interval_var.get())
            if interval <= 0: raise ValueError("Interval must be positive")
            self.config_manager.set("interval", interval)
        except ValueError:
            self.log("Error: Invalid interval")
            return

        mode = self.mode_var.get()
        self.config_manager.set("mode", mode)

        self.is_running = True
        self.current_stop_event = threading.Event()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.mode_combo.config(state=tk.DISABLED)
        self.snapshot_btn.config(state=tk.NORMAL)
        
        debug = self.debug_var.get()
        self.log(f"Started monitoring (Mode: {mode}, Interval: {interval}s, Debug: {debug})")
        
        self.snapshot_event.clear()

        # Strategy Factory usage
        strategy = self.strategy_factory(mode)
        if not strategy:
             self.log(f"Error: Unknown mode {mode}")
             self.stop_monitoring()
             return

        self.monitor_thread = threading.Thread(
            target=strategy.run, 
            args=(self.current_stop_event, self.snapshot_event, self.config_manager, self.log, debug)
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop_monitoring(self):
        if self.is_running:
            self.is_running = False
            if self.current_stop_event:
                self.current_stop_event.set()
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.snapshot_btn.config(state=tk.DISABLED)
            self.mode_combo.config(state="readonly")
            self.log("Stopping monitoring...")

    def trigger_snapshot(self):
        if self.is_running:
            self.snapshot_event.set()
            self.log("Snapshot requested...")

    def on_mode_change(self, event=None):
        mode = self.mode_var.get()
        self.config_manager.set("mode", mode)
        # Force save immediately? Or let config logic handle it. 
        # ConfigManager sets in memory, assuming save happens separate or implicitly?
        # ConfigManager provided earlier only saved on load/check. Let's force save if we can or just leave for close.
        # Actually ConfigManager provided doesn't have an explicit 'save' method exposed, 
        # but 'set' just updates the dict. 'on_close' we should save.

    def on_debug_change(self):
        val = self.debug_var.get()
        self.config_manager.set("debug_enabled", val)
        self.log(f"Debug set to: {val}")

    def save_current_config(self):
        # Update config with current UI state
        self.config_manager.set("window_width", self.root.winfo_width())
        self.config_manager.set("window_height", self.root.winfo_height())
        self.config_manager.set("debug_enabled", self.debug_var.get())
        self.config_manager.set("mode", self.mode_var.get())
        
        # Manually save to disk - ConfigManager needs a save method or we reproduce it
        # The ConfigManager seen in config.py had 'load_config' which saved if missing,
        # but 'set' was in-memory. We should add 'save()' to ConfigManager or mimic it.
        # Let's check config.py content again... 
        # It has 'set', 'get', 'reload'. And 'load_config' writes if needed.
        # But no public 'save' method. We should implement one in config.py, 
        # but for now let's write directly since we have the path.
        
        try:
            import json
            with open(self.config_manager.get_config_path(), "w", encoding="utf-8") as f:
                json.dump(self.config_manager.config, f, indent=4)
            # self.log("Config saved.") # Can't log if closing
        except Exception as e:
            print(f"Error saving config: {e}")

    def on_close(self):
        self.stop_monitoring()
        self.save_current_config()
        self.root.destroy()
