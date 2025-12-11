import time
import os
import uiautomation as auto
import pythoncom

from typing import Protocol, Any, Callable, List, Optional, Union
import threading

# Configure uiautomation
auto.SetGlobalSearchTimeout(1.0)  # Fast fail for checks

class AutomationControl(Protocol):
    """Abstract interface for a UI control."""
    Name: str
    ControlTypeName: str
    BoundingRectangle: Any
    AutomationId: str

    def GetChildren(self) -> List['AutomationControl']: ...
    def FindFirst(self, scope: Any, condition: Any) -> Optional['AutomationControl']: ...
    def SetFocus(self) -> None: ...
    def SendKeys(self, keys: str) -> None: ...
    def Invoke(self) -> None: ...
    def Click(self) -> None: ...
    def Exists(self, timeout: int, interval: int) -> bool: ...

class WindowProvider(Protocol):
    """Abstract provider for window operations."""
    def get_root_control(self) -> AutomationControl: ...
    def create_name_condition(self, name: str, case_sensitive: bool = False) -> Any: ...
    # Helper to expose uiautomation constants/types if needed, or abstract them
    # For now we might leak some uiautomation types (like Scope) or wrap them.
    # To keep it simple, we'll assume the strategies use the provider for factory methods 
    # or we just mock the control objects returning specific attributes.

class NativeAutomationProvider:
    """Concrete implementation using uiautomation."""
    def get_root_control(self) -> Any:
        return auto.GetRootControl()

class AutomationStrategy(Protocol):
    def run(self, stop_event: threading.Event, snapshot_event: threading.Event, config_manager: Any, logger: Callable[[str], None], debug: bool = False):
        """Run the automation loop."""
        ...

class BaseStrategy:
    def __init__(self, provider: WindowProvider):
        self.provider = provider

    def get_window_structure(self, window, depth=0, max_depth=5):
        if depth > max_depth:
            return ""
        
        indent = "  " * depth
        try:
            name = window.Name
            control_type = window.ControlTypeName
            
            # Extra info
            extra = ""
            try:
                rect = window.BoundingRectangle
                extra += f" Rect:{rect}"
            except:
                pass
            try:
                auto_id = window.AutomationId
                if auto_id:
                    extra += f" AutoID:{auto_id}"
            except:
                pass
            
            info = f"\n{indent}- [{control_type}] '{name}'{extra}"
            
            for child in window.GetChildren():
                # Handling uiautomation child iteration vs list
                info += self.get_window_structure(child, depth + 1, max_depth)
            
            return info
        except Exception as e:
            return f"\n{indent}<Error reading control: {e}>"

    def get_all_window_titles(self):
        titles = []
        try:
            root = self.provider.get_root_control()
            for window in root.GetChildren():
                try:
                    name = window.Name
                    if name:
                        titles.append(name)
                except:
                    pass
        except Exception as e:
            titles.append(f"Error listing windows: {e}")
        return "\n".join([f"- {t}" for t in titles])

class IdeStrategy(BaseStrategy):
    def run(self, stop_event, snapshot_event, config_manager, logger, debug=False):
        # Initialize COM for this thread
        pythoncom.CoInitialize()
        try:
            target_title_part = config_manager.get("target_window_title", "Antigravity")
            search_texts = config_manager.get("search_texts_ide", ["Run command?", "Reject", "Accept"])
            interval = config_manager.get("interval", 1.0)

            logger("Starting IDE Strategy (uiautomation)...")

            while not stop_event.is_set():
                if debug and snapshot_event.is_set():
                    try:
                        all_windows = self.get_all_window_titles()
                        content = f"IDE MODE SNAPSHOT\n\nALL VISIBLE WINDOWS:\n{all_windows}\n"
                        with open("debug_snapshot.txt", "w", encoding="utf-8") as f:
                            f.write(content)
                        logger("Snapshot saved to debug_snapshot.txt")
                        snapshot_event.clear()
                    except Exception as e:
                        logger(f"Snapshot failed: {e}")

                try:
                    # Find all potential windows
                    root = self.provider.get_root_control()
                    for window in root.GetChildren():
                        name = window.Name
                        # Basic filter to avoid our own window or irrelevant ones
                        if "Ag-Accept" in name or "Antigravity Monitor" in name:
                            continue
                    
                        if target_title_part in name:
                            # Process matching window
                            try:
                                # Quick text search
                                # uiautomation is fast, we can scan 
                                found_text = False
                            
                                # Helper to find text
                                def has_text_recursive(control, texts, depth=0, max_depth=3):
                                    if depth > max_depth: return False
                                    c_name = control.Name
                                    for t in texts:
                                        if t in c_name:
                                            return True
                                    for child in control.GetChildren():
                                        if has_text_recursive(child, texts, depth + 1, max_depth):
                                            return True
                                    return False

                                if has_text_recursive(window, search_texts):
                                    logger(f"Found target text in '{name}'. Activating and sending Alt+Enter...")
                                
                                    try:
                                        window.SetFocus()
                                    except Exception as e:
                                        logger(f"Focus warning: {e}")

                                    # Send keys
                                    window.SendKeys('%{Enter}')
                                    logger("Sent Alt+Enter")
                                
                                    # Small debounce
                                    time.sleep(0.5)
                            except Exception as e:
                                logger(f"Error processing window '{name}': {e}")

                except Exception as e:
                    logger(f"Loop error: {e}")

                if stop_event.wait(interval):
                    break
        finally:
            pythoncom.CoUninitialize()

class AgentManagerStrategy(BaseStrategy):
    def run(self, stop_event, snapshot_event, config_manager, logger, debug=False):
        pythoncom.CoInitialize()
        try:
            target_title_part = config_manager.get("target_window_title", "Antigravity")
            raw_search_texts = config_manager.get("search_texts_agent_manager", ["Accept"])
            search_texts = [s.strip() for s in raw_search_texts if s]
            context_texts = config_manager.get("context_text_agent_manager", ["Run command?"])
            interval = config_manager.get("interval", 1.0)
            
            target_window = None
            
            logger(f"Waiting for target window '{target_title_part}'...")

            while not stop_event.is_set():
            # Snapshot logic
                if debug and snapshot_event.is_set():
                    try:
                        all_windows = self.get_all_window_titles()
                        target_info = ""
                        if target_window and target_window.Exists(0, 0):
                             target_info = f"\n\nLOCKED TARGET STRUCTURE:\n{self.get_window_structure(target_window, verbose=True)}"
                    
                        content = f"AGENT MANAGER SNAPSHOT (uiautomation)\n\nALL VISIBLE WINDOWS:\n{all_windows}{target_info}"
                        with open("debug_snapshot.txt", "w", encoding="utf-8") as f:
                            f.write(content)
                        logger("Snapshot saved to debug_snapshot.txt")
                        try:
                            os.startfile("debug_snapshot.txt")
                        except: pass
                        snapshot_event.clear()
                    except Exception as e:
                        logger(f"Snapshot failed: {e}")

                try:
                    # 1. Find Target if lost
                    if not target_window or not target_window.Exists(0, 0):
                        target_window = None
                        root = self.provider.get_root_control()
                        best_match = None
                    
                        for window in root.GetChildren():
                            name = window.Name
                            if "ag-accept" in name.lower() or "antigravity monitor" in name.lower():
                                continue
                        
                            if name == target_title_part:
                                best_match = window
                                break
                            if target_title_part in name:
                                if not best_match: best_match = window
                            
                        if best_match:
                            target_window = best_match
                            logger(f"Locked on to window: '{target_window.Name}'")
                        else:
                            stop_event.wait(interval)
                            continue

                    # 2. Check Context
                    # We can use regex search for context if needed, or simple recursive check
                    # For performance, try to narrow down.
                
                    context_found = False
                    if not context_texts:
                        context_found = True
                    else:
                        # Search specifically for context texts
                        # Construct a combined condition or verify existence
                        # Using a manual walk for multiple texts is often clearer or using FindFirst
                        # Optimisation: Check window Name first (often contains the text)
                        if any(ctx in target_window.Name for ctx in context_texts):
                            context_found = True
                        else:
                            # Try to find a TextControl or similar with the context
                            # BFS/DFS search
                        
                            # We'll use a custom walker for flexibility
                            def verify_context(control):
                                for ctx in context_texts:
                                    try:
                                        if control.FindFirst(auto.TreeScope.Descendants, auto.NameControlCondition(Name=ctx, CaseSensitive=False)): # Approximating contains?
                                            # uiautomation NameControlCondition is exact or regex.
                                            # Let's use regex for contains
                                            # escaping special chars might be needed if ctx has them, but assuming simple text
                                            pass
                                    except: pass
                                
                                    # Using Python loop for contain check is robust
                                    found = control.FindFirst(auto.TreeScope.Descendants, lambda c, d: ctx in c.Name)
                                    if found: return True
                                return False

                            if verify_context(target_window):
                                context_found = True

                    if not context_found:
                        if debug: logger("Context not found in target. Skipping...")
                        stop_event.wait(interval)
                        continue

                    # 3. Look for Button
                    # We want a Button that contains one of the search_texts
                
                    found_button = None
                
                    # Use custom Lambda condition for flexible "contains" search on Buttons
                    def button_matcher(control, depth):
                        if control.ControlTypeName == "ButtonControl":
                            c_name = control.Name
                            for s in search_texts:
                                if s in c_name: # substring match
                                    return True
                        return False
                
                    found_button = target_window.FindFirst(auto.TreeScope.Descendants, button_matcher)

                    if found_button:
                        btn_name = found_button.Name
                        logger(f"Found button: '{btn_name}'")
                    
                        # Highlight if debug
                        if debug:
                            try:
                                # Rectangle isn't a method, it is a property 'BoundingRectangle'
                                # uiautomation has MoveCursorToMyCenter() etc.
                                # We can verify it's visible?
                                pass
                            except: pass

                        # Ensure target window is foreground? 
                        # Sometimes invoke works in background, but focus is safer
                        try:
                            target_window.SetFocus()
                        except: pass
                    
                        try:
                            found_button.Invoke()
                            logger(f"Clicked '{btn_name}' (Invoke)")
                        except Exception as invoke_err:
                            logger(f"Invoke failed ({invoke_err}), trying Click...")
                            try:
                                found_button.Click()
                                logger(f"Clicked '{btn_name}' (Click)")
                            except Exception as click_err:
                                logger(f"Failed to click '{btn_name}': {click_err}")
                            
                    else:
                        if debug: logger("No target buttons found.")

                except Exception as e:
                    logger(f"Error in automation loop: {e}")
                    target_window = None # Lost context probably

                stop_event.wait(interval)
        finally:
            pythoncom.CoUninitialize()
