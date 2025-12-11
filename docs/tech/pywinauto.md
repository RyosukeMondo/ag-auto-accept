# Pywinauto Technical Notes

## Overview
This document details specific behaviors and limitations of the `pywinauto` library (specifically the `uia` backend) observed in this project, and the workarounds implemented.

## Object Types
When using `Desktop(backend="uia").windows()`, the returned list contains **`pywinauto.controls.uiawrapper.UIAWrapper`** objects.

These are *resolved* UI elements, distinct from `WindowSpecification` objects (which are lazy wrappers returned by `app.WindowName`).

## Key Limitations & APIs

### 1. Missing `.exists()` Method
**Issue**: `UIAWrapper` objects do **not** have an `.exists()` method. Calling it raises an `AttributeError`.  
**Solution**: To check if a window reference is still valid (e.g., hasn't been closed), check the window handle against the Windows API.

```python
import ctypes

# Correct way to check validity
is_valid = ctypes.windll.user32.IsWindow(window.handle)
```

### 2. Missing `.dump_tree()` Method
**Issue**: `UIAWrapper` objects do **not** have a `.dump_tree()` method.  
**Solution**: You must manually iterate through the children using recursion.

```python
def get_window_structure(window, depth=0):
    text = window.window_text()
    try:
        ctrl_type = window.element_info.control_type
    except:
        ctrl_type = "Unknown"
        
    print(f"{'  ' * depth}- [{ctrl_type}] '{text}'")
    
    for child in window.children():
        get_window_structure(child, depth + 1)
```

### 3. Window Matching
**Issue**: `window.window_text()` returns the full title.  
**Best Practice**: When iterating through `desktop.windows()`, prioritize **exact matches** over partial matches to avoid locking onto unintended windows (like VSCode editor windows that contain the project name).

## Reference
- **Backend used**: `uia` (required for modern apps)
- **Library version**: `0.6.8` (approximate, based on behavior)
