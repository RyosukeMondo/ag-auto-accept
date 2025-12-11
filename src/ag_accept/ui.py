import tkinter as tk
from tkinter import ttk
import threading
import time
import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from injector import inject
from ag_accept.services.config_service import ConfigService
from ag_accept.services.automation_service import AutomationService
from ag_accept.automation import (
    STATE_IDLE, STATE_SEARCHING_WINDOW, STATE_WINDOW_FOUND,
    STATE_CHECKING_CONTEXT, STATE_CONTEXT_MATCHED, STATE_CONTEXT_FAILED,
    STATE_SEARCHING_BUTTON, STATE_BUTTON_FOUND, STATE_BUTTON_FAILED,
    STATE_ACTION_SUCCESS, STATE_ACTION_FAILED
)

class VisualStateManager:
    def __init__(self, root, parent_frame):
        self.root = root
        self.canvas = tk.Canvas(parent_frame, height=80, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(fill="x", padx=5, pady=5)
        
        self.nodes = {}
        self.links = {}
        
        self.setup_pipeline()
        
    def setup_pipeline(self):
        # Define nodes: (x, y, label)
        # Using relative layout logic
        y = 40
        spacing = 100
        start_x = 50
        
        node_defs = [
            ("window", "Window", start_x),
            ("context", "Context", start_x + spacing),
            ("button", "Button", start_x + spacing * 2),
            ("action", "Action", start_x + spacing * 3)
        ]
        
        # Draw links first
        for i in range(len(node_defs) - 1):
            key1, _, x1 = node_defs[i]
            key2, _, x2 = node_defs[i+1]
            link = self.canvas.create_line(x1+20, y, x2-20, y, fill="#555555", width=2)
            self.links[f"{key1}-{key2}"] = link
            
        # Draw nodes
        for key, label, x in node_defs:
            # Circle
            r = 20
            oval = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill="#555555", outline="")
            # Text
            text = self.canvas.create_text(x, y+30, text=label, fill="gray", font=("Arial", 9))
            self.nodes[key] = (oval, text)

    def set_color(self, node_key, color):
        if node_key in self.nodes:
            oval, _ = self.nodes[node_key]
            self.canvas.itemconfig(oval, fill=color)

    def reset(self):
        for key in self.nodes:
            self.set_color(key, "#555555")

    def update_state(self, state):
        # Update UI in main thread
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, lambda: self.update_state(state))
            return
            
        # Logic to map state to visual colors
        # Colors: Grey (#555555) -> Idle/Pending
        #         Yellow (#FFD700) -> Searching/Working
        #         Green (#32CD32) -> Success
        #         Red (#FF4500) -> Fail
        
        if state == STATE_IDLE or state == STATE_SEARCHING_WINDOW:
            self.reset()
            if state == STATE_SEARCHING_WINDOW:
                self.set_color("window", "#FFD700") # Yellow
                
        elif state == STATE_WINDOW_FOUND:
            self.set_color("window", "#32CD32") # Green
            
        elif state == STATE_CHECKING_CONTEXT:
            self.set_color("context", "#FFD700")

        elif state == STATE_CONTEXT_MATCHED:
            self.set_color("context", "#32CD32")
            
        elif state == STATE_CONTEXT_FAILED:
            self.set_color("context", "#FF4500") # Red
            self.set_color("button", "#555555") # Reset downstream
            
        elif state == STATE_SEARCHING_BUTTON:
            self.set_color("button", "#FFD700")
            
        elif state == STATE_BUTTON_FOUND:
            self.set_color("button", "#32CD32")
            
        elif state == STATE_BUTTON_FAILED:
            self.set_color("button", "#FF4500")
            
        elif state == STATE_ACTION_SUCCESS:
            self.set_color("action", "#32CD32")
            # Flash effect or something?
            
        elif state == STATE_ACTION_FAILED:
            self.set_color("action", "#FF4500")



class AutoAccepterUI:
    @inject
    def __init__(self, root: ctk.CTk, config_service: ConfigService, automation_service: AutomationService):
        self.root = root
        self.config_service = config_service
        self.automation_service = automation_service
        
        self.root.title("Ag-Accept")
        
        width = self.config_service.get("window_width", 700)
        height = self.config_service.get("window_height", 800)
        self.root.geometry(f"{width}x{height}")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.setup_ui()
        self.log(f"Config loaded from: {config_service.get_config_path()}")
        self.start_telemetry_loop()

    def setup_ui(self):
        # Create Tabview
        self.tabview = ctk.CTkTabview(self.root)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_dashboard = self.tabview.add("Dashboard")
        self.tab_telemetry = self.tabview.add("Telemetry")
        
        self.setup_dashboard(self.tab_dashboard)
        self.setup_telemetry(self.tab_telemetry)

    def setup_state_viz(self, parent):
        viz_frame = ctk.CTkFrame(parent)
        viz_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(viz_frame, text="Pipeline State").pack(anchor="w", padx=5)
        
        self.visual_state_manager = VisualStateManager(self.root, viz_frame)

    def setup_dashboard(self, parent):
        # Top Control Panel
        control_frame = ctk.CTkFrame(parent)
        control_frame.pack(fill="x", padx=5, pady=5)
        
        # Column 1: Config
        self.interval_var = ctk.StringVar(value=str(self.config_service.get("interval", 1.0)))
        ctk.CTkLabel(control_frame, text="Interval (s):").grid(row=0, column=0, padx=5, pady=5)
        ctk.CTkEntry(control_frame, textvariable=self.interval_var, width=60).grid(row=0, column=1, padx=5, pady=5)
        
        self.mode_var = ctk.StringVar(value=self.config_service.get("mode", "IDE"))
        ctk.CTkLabel(control_frame, text="Mode:").grid(row=0, column=2, padx=5, pady=5)
        self.mode_combo = ctk.CTkComboBox(control_frame, variable=self.mode_var, values=["IDE", "AgentManager"], command=self.on_mode_change, width=120)
        self.mode_combo.grid(row=0, column=3, padx=5, pady=5)

        # Column 2: Toggles
        self.debug_var = ctk.BooleanVar(value=self.config_service.get("debug_enabled", False))
        ctk.CTkCheckBox(control_frame, text="Debug", variable=self.debug_var, command=self.on_debug_change).grid(row=0, column=4, padx=10, pady=5)

        # Actions Row
        action_frame = ctk.CTkFrame(parent)
        action_frame.pack(fill="x", padx=5, pady=5)

        self.start_btn = ctk.CTkButton(action_frame, text="START Monitoring", command=self.start_monitoring, fg_color="green", hover_color="darkgreen")
        self.start_btn.pack(side="left", fill="x", expand=True, padx=5)

        self.stop_btn = ctk.CTkButton(action_frame, text="STOP", command=self.stop_monitoring, state="disabled", fg_color="red", hover_color="darkred")
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=5)
        
        self.snapshot_btn = ctk.CTkButton(action_frame, text="Snapshot", command=self.trigger_snapshot, state="disabled")
        self.snapshot_btn.pack(side="left", padx=5)

        # State Viz Area
        self.setup_state_viz(parent)

        # Logs Area
        log_frame = ctk.CTkFrame(parent)
        log_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(log_frame, text="Activity Log").pack(anchor="w", padx=5)
        
        # Use Treeview for logs as it supports columns better, but style it dark
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#2b2b2b", 
                        foreground="white", 
                        fieldbackground="#2b2b2b",
                        borderwidth=0)
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="white", relief="flat")
        style.map("Treeview", background=[('selected', '#3a7ebf')])
        
        columns = ("time", "status", "message")
        self.log_tree = ttk.Treeview(log_frame, columns=columns, show="headings", height=15)
        self.log_tree.heading("time", text="Time")
        self.log_tree.heading("status", text="Status")
        self.log_tree.heading("message", text="Message")
        
        self.log_tree.column("time", width=80, anchor="center")
        self.log_tree.column("status", width=80, anchor="center")
        self.log_tree.column("message", width=400, anchor="w")
        
        self.log_tree.pack(side="left", fill="both", expand=True)
        
        sb = ctk.CTkScrollbar(log_frame, command=self.log_tree.yview)
        sb.pack(side="right", fill="y")
        self.log_tree.configure(yscroll=sb.set)
        
        # Tags for colors
        self.log_tree.tag_configure("success", foreground="#90ee90")
        self.log_tree.tag_configure("error", foreground="#ff6b6b")
        self.log_tree.tag_configure("muted", foreground="#aaaaaa")
        self.log_tree.tag_configure("normal", foreground="#ffffff")


    def setup_telemetry(self, parent):
        # Matplotlib Graph
        self.fig = Figure(figsize=(5, 4), dpi=100, constrained_layout=True)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Automation Performance (Events/min)")
        self.ax.set_facecolor('#2b2b2b')
        self.fig.patch.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='white')
        self.ax.xaxis.label.set_color('white')
        self.ax.yaxis.label.set_color('white')
        self.ax.title.set_color('white')
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['top'].set_color('white') 
        self.ax.spines['right'].set_color('white')
        self.ax.spines['left'].set_color('white')

        # Mock data buffers
        self.x_data = []
        self.y_data = []
        self.line, = self.ax.plot(self.x_data, self.y_data, 'c-') # Cyan line

        # Remove internal margins
        # self.fig.tight_layout() # using constrained_layout=True instead

        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.draw()
        
        # Use pack for better fill and centering
        tk_widget = self.canvas.get_tk_widget()
        tk_widget.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Bind to configure event to fix initial layout issues
        tk_widget.bind("<Configure>", self.on_telemetry_resize)

    def on_telemetry_resize(self, event):
        # Force a redraw when the widget is resized or shown
        # This fixes the issue where centering is off until window resize
        self.canvas.draw()
        
    def start_telemetry_loop(self):
        # Update graph every second (mock for now, or hook to service stats)
        # In a real scenario, AutomationService would track 'actions per minute'
        self.update_telemetry()
        
    def update_telemetry(self):
        # Simple mock or basic stat: count total logs?
        # Ideally, we ask automation_service for stats
        # For now, let's just plot 'random' or stable activity if running
        
        # TODO: Implement real stats in AutomationService
        # For demo, we just tick x
        import random
        
        if len(self.x_data) > 20:
            self.x_data.pop(0)
            self.y_data.pop(0)
            
        self.x_data.append(time.strftime("%M:%S"))
        # Mock value: 0 if stopped, random if running
        val = 0
        if self.start_btn.cget("state") == "disabled": # Running
            val = random.randint(1, 10)
        self.y_data.append(val)
        
        self.line.set_data(range(len(self.y_data)), self.y_data)
        self.ax.set_xlim(0, max(20, len(self.y_data)))
        self.ax.set_ylim(0, 12)
        
        # Redraw
        self.canvas.draw()
        
        # Schedule next update
        self.root.after(1000, self.update_telemetry)

    def log(self, message):
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
        
        self.log_tree.insert("", 0, values=(timestamp, status, message), tags=(tag,))
        # Limit logs
        if len(self.log_tree.get_children()) > 100:
             self.log_tree.delete(self.log_tree.get_children()[-1])


    def start_monitoring(self):
        self.config_service.reload()
        self.log("Config reloaded.")
        try:
            interval = float(self.interval_var.get())
            if interval <= 0: raise ValueError
            self.config_service.set("interval", interval)
        except ValueError:
            self.log("Error: Invalid interval")
            return

        mode = self.mode_var.get()
        self.config_service.set("mode", mode)

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.mode_combo.configure(state="disabled")
        self.snapshot_btn.configure(state="normal")
        
        debug = self.debug_var.get()
        self.log(f"Started (Mode: {mode}, Interval: {interval}s)")
        

        
        # Pass state callback
        self.automation_service.start_automation(mode, self.log, self.visual_state_manager.update_state)

    def stop_monitoring(self):
        self.automation_service.stop_automation()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.snapshot_btn.configure(state="disabled")
        self.mode_combo.configure(state="normal")
        self.log("Stopped monitoring.")

    def trigger_snapshot(self):
        self.automation_service.trigger_snapshot()
        self.log("Snapshot requested...")

    def on_mode_change(self, choice):
        self.config_service.set("mode", choice)

    def on_debug_change(self):
        val = self.debug_var.get()
        self.config_service.set("debug_enabled", val)
        self.log(f"Debug set to: {val}")

    def on_close(self):
        self.stop_monitoring()
        self.config_service.save()
        self.root.destroy()
        import sys
        sys.exit(0)

    # ... helpers ...
    def save_current_config(self):
        pass # Handle in on_close
