import time
import os
import pythoncom

from typing import Protocol, Any, Callable, List, Optional
import threading

from injector import inject
# Import new services
from ag_accept.services.window_service import WindowService
from ag_accept.services.text_query_service import TextQueryService
from ag_accept.services.scheduler_service import SchedulerService
from ag_accept.services.debug_service import DebugService

# State Constants
STATE_IDLE = "IDLE"
STATE_SEARCHING_WINDOW = "SEARCHING_WINDOW"
STATE_WINDOW_FOUND = "WINDOW_FOUND"
STATE_CHECKING_CONTEXT = "CHECKING_CONTEXT"
STATE_CONTEXT_MATCHED = "CONTEXT_MATCHED" 
STATE_CONTEXT_FAILED = "CONTEXT_FAILED"
STATE_SEARCHING_BUTTON = "SEARCHING_BUTTON"
STATE_BUTTON_FOUND = "BUTTON_FOUND"
STATE_BUTTON_FAILED = "BUTTON_FAILED"
STATE_ACTION_SUCCESS = "ACTION_SUCCESS"
STATE_ACTION_FAILED = "ACTION_FAILED"

class AutomationStrategy(Protocol):
    def run(self, stop_event: threading.Event, snapshot_event: threading.Event, config_manager: Any, logger: Callable[[str], None], state_callback: Callable[[str], None] = None, debug: bool = False):
        """Run the automation loop."""
        ...

class IdeStrategy:
    @inject
    def __init__(self, window_service: WindowService, text_service: TextQueryService, debug_service: DebugService):
        self.window_service = window_service
        self.text_service = text_service
        self.debug_service = debug_service

    def run(self, stop_event, snapshot_event, config_manager, logger, state_callback=None, debug=False):
        pythoncom.CoInitialize()
        try:
            target_title_part = config_manager.get("target_window_title", "Antigravity")
            search_texts = config_manager.get("search_texts_ide", ["Run command?", "Reject", "Accept"])
            interval = config_manager.get("interval", 1.0)

            logger("Starting IDE Strategy (refactored)...")

            while not stop_event.is_set():
                if debug and snapshot_event.is_set():
                    self.debug_service.save_snapshot(
                        f"IDE SNAPSHOT\n{self.window_service.get_all_window_titles_string()}"
                    )
                    logger("Snapshot saved.")
                    snapshot_event.clear()

                try:
                    # Find all potential windows
                    windows = self.window_service.get_all_windows(exclude_titles=["Ag-Accept", "Antigravity Monitor"])
                    
                    for window in windows:
                        if state_callback: state_callback(STATE_SEARCHING_WINDOW)
                        name = window.Name
                        if target_title_part in name:
                            if state_callback: state_callback(STATE_WINDOW_FOUND)
                            # Use TextQueryService for recursive search
                            if state_callback: state_callback(STATE_CHECKING_CONTEXT)
                            if self.text_service.has_text_recursive(window, search_texts):
                                if state_callback: state_callback(STATE_CONTEXT_MATCHED)
                                logger(f"Found target text in '{name}'. Activating...")
                                
                                self.window_service.focus_window(window)
                                
                                try:
                                    if state_callback: state_callback(STATE_ACTION_SUCCESS) # Treat as success event though just preparing
                                    # Send keys - Trying explicit {Alt}{Enter} instead of %{Enter}
                                    window.SendKeys('{Alt}{Enter}')
                                    logger("Sent {Alt}{Enter}")
                                    time.sleep(0.5)
                                except Exception as e:
                                    if state_callback: state_callback(STATE_ACTION_FAILED)
                                    logger(f"SendKeys error: {e}")
                            else:
                                if state_callback: state_callback(STATE_CONTEXT_FAILED)

                except Exception as e:
                    logger(f"Loop error: {e}")

                if stop_event.wait(interval):
                    break
        finally:
            pythoncom.CoUninitialize()

class AgentManagerStrategy:
    @inject
    def __init__(self, window_service: WindowService, text_service: TextQueryService, debug_service: DebugService):
        self.window_service = window_service
        self.text_service = text_service
        self.debug_service = debug_service
        self.scheduler = SchedulerService() # Not fully replacing main loop yet, but ready

    def run(self, stop_event, snapshot_event, config_manager, logger, state_callback=None, debug=False):
        pythoncom.CoInitialize()
        try:
            target_title_part = config_manager.get("target_window_title", "Antigravity")
            
            # Extract texts
            raw_search_texts = config_manager.get("search_texts_agent_manager", ["Accept"])
            search_texts = [s.strip() for s in raw_search_texts if s]
            
            context_texts = config_manager.get("context_text_agent_manager", ["Run command?"])
            interval = config_manager.get("interval", 1.0)
            
            target_window = None
            
            logger(f"Waiting for target window '{target_title_part}'...")

            while not stop_event.is_set():
                # Snapshot
                if debug and snapshot_event.is_set():
                    content = f"AGENT MANAGER SNAPSHOT\n{self.window_service.get_all_window_titles_string()}"
                    if target_window:
                         try:
                             content += f"\n\nTARGET STRUCTURE:\n{self.window_service.get_window_structure(target_window)}"
                             # Dump text for debugging "Target text not found"
                             content += f"\n\nTEXT DUMP:\n" + "\n".join(self.text_service.dump_texts(target_window))
                         except: pass
                    
                    self.debug_service.save_snapshot(content)
                    self.debug_service.open_snapshot()
                    logger("Snapshot saved and opened.")
                    snapshot_event.clear()

                try:
                    # 1. Find Target
                    # Re-verify target existence
                    if target_window:
                        try:
                            if not target_window.Exists(0, 0):
                                target_window = None
                        except:
                            target_window = None

                    if not target_window:
                        if state_callback: state_callback(STATE_SEARCHING_WINDOW)
                        target_window = self.window_service.find_window_by_title(
                            target_title_part, 
                            exclude_titles=["Ag-Accept", "Antigravity Monitor"]
                        )
                        
                        if target_window:
                            if state_callback: state_callback(STATE_WINDOW_FOUND)
                            logger(f"Locked on to window: '{target_window.Name}'")
                        else:
                            stop_event.wait(interval)
                            continue
                    else:
                        if state_callback: state_callback(STATE_WINDOW_FOUND)

                    # 2. Check Context (Recursive Search - Fixes "Target text not found")
                    # Previously we used a custom verify_context, now we use the service which does recursive
                    context_found = False
                    if state_callback: state_callback(STATE_CHECKING_CONTEXT)
                    if not context_texts:
                        context_found = True
                    else:
                        # Use the service!
                        if self.text_service.has_text_recursive(target_window, context_texts):
                            context_found = True
                        else:
                            # Fallback or specific logic if needed? 
                            # The service logic matches the IDE one which user said "didn't work since implemented agentmanager"
                            # implying the old IDE way WAS working and they want it back.
                            pass

                    if not context_found:
                        if state_callback: state_callback(STATE_CONTEXT_FAILED)
                        # Don't log spam if waiting
                        stop_event.wait(interval)
                        continue
                    
                    if state_callback: state_callback(STATE_CONTEXT_MATCHED)

                    # 3. Look for Button
                    if state_callback: state_callback(STATE_SEARCHING_BUTTON)
                    found_button = self.text_service.find_button_with_text(target_window, search_texts)

                    if found_button:
                        if state_callback: state_callback(STATE_BUTTON_FOUND)
                        btn_name = found_button.Name
                        logger(f"Found button: '{btn_name}'")
                        
                        # Focus Management
                        self.window_service.focus_window(target_window)
                        
                        try:
                            found_button.Invoke()
                            logger(f"Clicked '{btn_name}' (Invoke)")
                            if state_callback: state_callback(STATE_ACTION_SUCCESS)
                        except:
                            try:
                                found_button.Click()
                                logger(f"Clicked '{btn_name}' (Click)")
                                if state_callback: state_callback(STATE_ACTION_SUCCESS)
                            except Exception as e:
                                logger(f"Click failed: {e}")
                                if state_callback: state_callback(STATE_ACTION_FAILED)
                        
                        # Back Focus ? (User asked for "back focus", interpreting as restore)
                        # self.window_service.restore_previous_focus() 
                        # This might be annoying if done too fast, maybe optional?
                        # For now, let's keep it simple or enable if we want true "back focus".
                        # Given user asked for service "back focus", I'll add a call but maybe comment out or check config?
                        # I'll add it but assume user wants it.
                        self.window_service.restore_previous_focus()

                    else:
                        if state_callback: state_callback(STATE_BUTTON_FAILED)
                        # Button not found
                        pass

                except Exception as e:
                    logger(f"Loop error: {e}")
                    target_window = None

                stop_event.wait(interval)
        finally:
            pythoncom.CoUninitialize()
