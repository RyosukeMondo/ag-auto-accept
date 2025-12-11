import time
import os
import ctypes
from pywinauto import Desktop
from typing import Protocol, List, Any, Callable
import threading

class AutomationStrategy(Protocol):
    def run(self, stop_event: threading.Event, snapshot_event: threading.Event, config_manager: Any, logger: Callable[[str], None], debug: bool = False):
        """Run the automation loop."""
        ...

class BaseStrategy:
    def __init__(self, desktop_provider=None):
        self.desktop_provider = desktop_provider or (lambda: Desktop(backend="uia"))

    def get_all_window_titles(self, desktop):
        titles = []
        try:
            for w in desktop.windows():
                try:
                    t = w.window_text()
                    if t:
                        titles.append(t)
                except:
                    pass
        except Exception as e:
            titles.append(f"Error listing windows: {e}")
        return "\n".join([f"- {t}" for t in titles])

    def get_window_structure(self, window, depth=0, max_depth=5, verbose=False):
        if depth > max_depth:
            return ""
        
        indent = "  " * depth
        try:
            text = window.window_text()
            try:
                ctrl_type = window.element_info.control_type
            except:
                ctrl_type = "Unknown"
            
            extra = ""
            if verbose:
                try:
                    rect = window.rectangle()
                    extra += f" Rect:{rect}"
                except:
                    pass
                try:
                    auto_id = window.element_info.automation_id
                    if auto_id:
                        extra += f" AutoID:{auto_id}"
                except:
                    pass
        except:
            return ""
            
        info = f"\n{indent}- [{ctrl_type}] '{text}'{extra}"
        
        try:
            for child in window.children():
                info += self.get_window_structure(child, depth + 1, max_depth, verbose)
        except:
            pass
            
        return info

class IdeStrategy(BaseStrategy):
    def run(self, stop_event, snapshot_event, config_manager, logger, debug=False):
        desktop = self.desktop_provider()
        target_title_part = config_manager.get("target_window_title", "Antigravity")
        search_texts = config_manager.get("search_texts_ide", ["Run command? Reject AcceptAlt+⏎"])
        # Fallback
        if not search_texts:
             search_texts = config_manager.get("search_texts", ["Run command? Reject AcceptAlt+⏎"])
        
        interval = config_manager.get("interval", 1.0)

        while not stop_event.is_set():
            if debug and snapshot_event.is_set():
                try:
                    all_windows = self.get_all_window_titles(desktop)
                    content = f"IDE MODE SNAPSHOT\n\nALL VISIBLE WINDOWS:\n{all_windows}\n"
                    
                    with open("debug_snapshot.txt", "w", encoding="utf-8") as f:
                        f.write(content)
                    logger("Snapshot saved to debug_snapshot.txt (Window List)")
                    print(content)
                    snapshot_event.clear()
                except Exception as e:
                    logger(f"Snapshot failed: {e}")

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
                            continue 
                except Exception as e:
                    logger(f"Fail: Error listing windows: {e}")
                    stop_event.wait(interval)
                    continue

                if found_targets:
                    for w in found_targets:
                        try:
                            title = w.window_text()
                            if "Ag-Accept" in title or "Antigravity Monitor" in title:
                                continue 
                            
                            logger(f"Checking window: '{title}'")
                            
                            has_accept = False
                            try:
                                descendants = w.descendants()
                                for item in descendants:
                                        t = item.window_text()
                                        if t:
                                            for target_text in search_texts:
                                                if target_text in t:
                                                    has_accept = True
                                                    logger(f"Found target text in element: '{t}'")
                                                    break
                                        if has_accept:
                                            break
                            except Exception as e:
                                logger(f"Warning: scanning failed for '{title}': {e}")
                            
                            if has_accept:
                                logger(f"Refocusing and sending key to '{title}'")
                                
                                previous_focus_hwnd = ctypes.windll.user32.GetForegroundWindow()

                                try:
                                    w.set_focus()
                                except Exception as focus_err:
                                     logger(f"Focus warning: {focus_err}")
                                
                                w.type_keys('%{ENTER}', with_spaces=True)
                                logger("Success: Sent Alt+Enter")

                                if previous_focus_hwnd:
                                    try:
                                        ctypes.windll.user32.SetForegroundWindow(previous_focus_hwnd)
                                    except Exception as e:
                                        logger(f"Failed to restore focus: {e}")
                            else:
                                logger(f"Skipping '{title}': Target text not found.")
                            
                        except Exception as e:
                            logger(f"Fail: Operation on '{title}' failed. Error: {e}")

            except Exception as e:
                logger(f"Error in loop: {e}")

            if stop_event.wait(interval):
                break

class AgentManagerStrategy(BaseStrategy):
    def run(self, stop_event, snapshot_event, config_manager, logger, debug=False):
        desktop = self.desktop_provider()
        target_title_part = config_manager.get("target_window_title", "Antigravity")
        raw_search_texts = config_manager.get("search_texts_agent_manager", ["Accept"])
        # Ensure search texts are clean
        search_texts = [s.strip() for s in raw_search_texts if s]
        
        context_texts = config_manager.get("context_text_agent_manager", ["Run command?"])
        interval = config_manager.get("interval", 1.0)

        target_window = None
        
        logger(f"Waiting for target window... (Looking for buttons: {search_texts} with context: {context_texts})")

        while not stop_event.is_set():
            if debug and snapshot_event.is_set():
                # ... (snapshot logic omitted for brevity, keeping existing) ...
                try:
                    all_windows = self.get_all_window_titles(desktop)
                    target_info = ""
                    if target_window:
                         try:
                            target_info = f"\n\nLOCKED TARGET STRUCTURE:\n{self.get_window_structure(target_window, verbose=True)}"
                         except:
                            target_info = "\n\nLOCKED TARGET: <Error getting structure>"
                    
                    content = f"AGENT MANAGER SNAPSHOT\n\nALL VISIBLE WINDOWS:\n{all_windows}{target_info}"
                    
                    with open("debug_snapshot.txt", "w", encoding="utf-8") as f:
                        f.write(content)
                    logger("Snapshot saved to debug_snapshot.txt")
                    try:
                        os.startfile("debug_snapshot.txt")
                    except:
                        pass
                    snapshot_event.clear()
                except Exception as e:
                    logger(f"Snapshot failed: {e}")

            try:
                if debug:
                    logger("DEBUG: Start of scan cycle...")

                # 1. Find Target Window
                if not target_window:
                    try:
                        windows = desktop.windows()
                        best_match = None
                        
                        for w in windows:
                            title = w.window_text()
                            title_lower = title.lower()
                            
                            if "ag-accept" in title_lower or "antigravity monitor" in title_lower:
                                continue
                                
                            if title == target_title_part:
                                best_match = w
                                break 
                            
                            if target_title_part in title:
                                if best_match is None:
                                    best_match = w
                        
                        if best_match:
                            target_window = best_match
                            failure_count = 0
                            logger(f"Locked on to window: '{target_window.window_text()}'")
                            
                            if debug:
                                try:
                                    target_window.draw_outline(colour='green', thickness=2)
                                except:
                                    pass
                    except Exception as e:
                        logger(f"Error searching for window: {e}")
                
                if not target_window:
                    stop_event.wait(interval)
                    continue

                # 2. Check Validity
                try:
                    if ctypes.windll.user32.IsWindow(target_window.handle):
                        failure_count = 0 
                    else:
                        raise Exception("Window handle invalid")
                except Exception as e:
                    failure_count += 1
                    if failure_count < 3:
                        logger(f"Warning: Target check failed ({failure_count}/3): {e}. Keeping lock...")
                        stop_event.wait(interval)
                        continue
                    else:
                        logger(f"Target window lost (3 consecutive failures). Re-scanning...")
                        target_window = None
                        failure_count = 0
                        continue

                # 3. Check for Context
                context_found = False
                if not context_texts:
                    context_found = True
                else:
                    try:
                        full_text_dump = target_window.window_text()
                        for ctx in context_texts:
                            if ctx in full_text_dump:
                                context_found = True
                                break
                        
                        if not context_found:
                            descendants = target_window.descendants() 
                            for item in descendants:
                                t = item.window_text()
                                if t:
                                    for ctx in context_texts:
                                        if ctx in t:
                                            context_found = True
                                            break
                                if context_found:
                                    break
                    except Exception:
                        pass 
                
                if not context_found:
                    if debug:
                        logger(f"Debug: Context {context_texts} not found in target window. Skipping scan.")
                        logger("DEBUG: Cycle end (Context missing).")
                    stop_event.wait(interval)
                    continue


                # 4. Look for Button
                try:
                    found_accept = False
                    found_buttons_debug = [] 
                    
                    # Recursive search function to mimic get_window_structure logic
                    # descendants() can be flaky or return different results than walking children
                    def verify_context(root, contexts):
                        if not contexts:
                            return True
                        # Search entire tree for ANY of the context strings
                        # This works because we passed strict requirements. 
                        # Ideally we check proximity, but "same window" is the baseline requirement.
                        # Using descendants() carefully:
                        try:
                           for c in contexts:
                               # Start with a broad search for any control containing the text
                               # descendants() might be slow. Optimization:
                               # Just check if we can find it.
                               # Using our own recursive scanner is safer given descendants() flakiness.
                               pass
                        except:
                            pass
                        
                        # Simple recursive finder for context
                        def find_text_recurse(w, target_text):
                            try:
                                if target_text in w.window_text():
                                    return True
                            except: pass
                            try:
                                for child in w.children():
                                    if find_text_recurse(child, target_text):
                                        return True
                            except: pass
                            return False

                        for ctx in contexts:
                            if find_text_recurse(root, ctx):
                                return True
                        return False

                    # Recursive search function to mimic get_window_structure logic
                    # descendants() can be flaky or return different results than walking children
                    def recursive_find(window, depth=0, max_depth=10, file_handle=None, root_window=None):
                        if depth > max_depth:
                            return None

                        try:
                            children = window.children()
                        except:
                            return None

                        for child in children:
                            # 1. First, RECURSE deeper (Depth-First)
                            result = recursive_find(child, depth + 1, max_depth, file_handle, root_window)
                            if result:
                                return result

                            # 2. Check this node
                            try:
                                t = child.window_text()

                                # AGGRESSIVE LOGGING: Dump every node visited to file
                                if debug and file_handle:
                                    try:
                                        ctype = child.element_info.control_type
                                        file_handle.write(f"{'  ' * depth}[{ctype}] {repr(t)}\n")
                                    except:
                                        file_handle.write(f"{'  ' * depth}[Unknown] {repr(t)}\n")

                                if t:
                                    t_clean = t.strip()
                                    
                                    # Candidate Logging (Partial/Loose for debug info)
                                    t_lower = t_clean.lower()
                                    if "accept" in t_lower or "reject" in t_lower:
                                       msg = f"[{child.element_info.control_type}] {repr(t_clean)}"
                                       found_buttons_debug.append(msg)
                                       if debug and file_handle:
                                            file_handle.write(f"  >>> CANDIDATE: {msg}\n")

                                    for btn_text in search_texts:
                                        # STRICT MATCHING: Case-Sensitive Substring
                                        # User requested "check upper, lower difference" -> Case matters.
                                        # We use 'in' to allow "Accept (5)" to match "Accept", but "accept" will NOT match "Accept".
                                        if btn_text in t_clean:
                                            # Found potential match, now VALIDATE CONTEXT if configured
                                            if context_texts:
                                                if verify_context(root_window, context_texts):
                                                    if debug and file_handle:
                                                        file_handle.write(f"      -> MATCH SUCCEEDED (Strict+Context): '{btn_text}' in '{t_clean}'\n")
                                                    return child
                                                else:
                                                    if debug and file_handle:
                                                        file_handle.write(f"      -> Mismatch: Context {context_texts} NOT found in window.\n")
                                            else:
                                                if debug and file_handle:
                                                    file_handle.write(f"      -> MATCH SUCCEEDED (Strict): '{btn_text}' in '{t_clean}'\n")
                                                return child
                                        
                                        # Robust Fallback (for logging mismatch)
                                        elif btn_text.lower() in t_lower:
                                            if debug and file_handle:
                                                file_handle.write(f"      -> Mismatch: Strict Case Required. Conf='{btn_text}' vs Found='{t_clean}'\n")
                                        
                            except:
                                pass
                        
                        return None

                    logger(f"Scanning window hierarchy recursively for: {search_texts}...")
                    if debug:
                        logger(f"DEBUG: Active Search List: {search_texts}")
                        
                    found_element = None
                    if debug:
                        try:
                            with open("debug_scan_trace.txt", "w", encoding="utf-8") as f:
                                f.write(f"Scan started at {time.strftime('%H:%M:%S')}\nTarget: {search_texts}\nContext: {context_texts}\n")
                                found_element = recursive_find(target_window, file_handle=f, root_window=target_window)
                                f.write("Scan complete.\n")
                            logger("Saved detailed scan trace to 'debug_scan_trace.txt'")
                        except Exception as e:
                            logger(f"Error writing debug trace: {e}")
                            found_element = recursive_find(target_window, root_window=target_window)
                    else:
                        found_element = recursive_find(target_window, root_window=target_window)

                    if found_element:
                        t = found_element.window_text()
                        logger(f"Found target element: {repr(t)} (Type: {found_element.element_info.control_type})")
                        
                        if debug:
                            try:
                                found_element.draw_outline(colour='green', thickness=2)
                                rect = found_element.rectangle()
                                logger(f"Debug: Element Rect: {rect}")
                                time.sleep(0.5) 
                            except Exception as draw_err:
                                logger(f"Debug: Failed to draw outline: {draw_err}")

                        # Try to focus parent/window first
                        try:
                            target_window.set_focus()
                        except:
                            pass

                        logger(f"ACTION: CLICKING element {repr(t)} (Outstanding)...")
                        
                        # Try invoke pattern first, then click_input
                        try:
                            try:
                                if hasattr(found_element, 'invoke'):
                                    found_element.invoke()
                                    logger(f"RESULT: SUCCESS (Invoked {repr(t)})")
                                    found_accept = True
                                else:
                                    logger("Debug: Element has no invoke method")
                                    raise Exception("No invoke method")
                            except Exception as invoke_err:
                                logger(f"Invoke warning ({invoke_err}), attempting physical click...")
                                found_element.click_input()
                                logger(f"RESULT: SUCCESS (Clicked {repr(t)} via input)")
                                found_accept = True
                        except Exception as click_err:
                             logger(f"RESULT: FAILURE (Error clicking/invoking {repr(t)}: {click_err})")

                    if not found_accept:
                        logger(f"Debug: Target element not found after recursive search.")
                        
                        if debug:
                            if found_buttons_debug:
                                logger(f"Candidates seen: {', '.join(found_buttons_debug[:10])}")
                            else:
                                logger("No candidates with 'Accept'/'Reject' seen in tree.")

                            logger(f"Dumping structure for analysis...")
                        try:
                            structure = self.get_window_structure(target_window, max_depth=10, verbose=True)
                            logger(f"Window Structure Dump:\n{structure}")
                            
                            # Also save to file for easier reading
                            with open("debug_structure_dump.txt", "w", encoding="utf-8") as f:
                                f.write(structure)
                            logger("Structure also saved to 'debug_structure_dump.txt'")
                        except Exception as dump_err:
                            logger(f"Failed to dump structure: {dump_err}")

                        if len(found_buttons_debug) > 0:
                            buttons_sample = ", ".join(found_buttons_debug[:10])
                            if len(found_buttons_debug) > 10:
                                buttons_sample += ", ..."
                            logger(f"Visible buttons found: {buttons_sample}")
                        else:
                             logger("No buttons found using 'descendants(control_type=\"Button\")'.")

                except Exception as e:
                    logger(f"Error interacting with window: {e}")
                    pass

            except Exception as e:
                logger(f"Loop error: {e}")

            if debug:
                logger(f"DEBUG: Cycle end. Waiting {interval}s...")

            if stop_event.wait(interval):
                break
