
import tkinter as tk
from ag_accept.config import ConfigManager
from ag_accept.ui import AutoAccepterUI
from ag_accept.automation import IdeStrategy, AgentManagerStrategy, NativeAutomationProvider

def strategy_factory(mode):
    provider = NativeAutomationProvider()
    if mode == "IDE":
        return IdeStrategy(provider)
    elif mode == "AgentManager":
        return AgentManagerStrategy(provider)
    return None

def main():
    try:
        root = tk.Tk()
        
        # Dependency Injection
        config_manager = ConfigManager()
        
        app = AutoAccepterUI(root, config_manager, strategy_factory)
        
        root.mainloop()
    except Exception as e:
        import traceback
        with open("crash.log", "a") as f:
            f.write(f"\nCRASH IN MAIN LOOP/INIT:\n{traceback.format_exc()}\n")
        raise e

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        with open("crash.log", "w") as f:
            f.write(traceback.format_exc())
        print("CRASHED! Check crash.log")
        input("Press Enter to exit...")
