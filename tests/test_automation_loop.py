import unittest
import threading
import time
from unittest.mock import MagicMock, call
from ag_accept.automation import IdeStrategy, AgentManagerStrategy, WindowProvider

class MockControl:
    def __init__(self, name="Target", children=None):
        self.Name = name
        self.ControlTypeName = "Window"
        self.BoundingRectangle = [0,0,10,10]
        self.AutomationId = "123"
        self.children = children or []

    def GetChildren(self):
        return self.children

    def FindFirst(self, scope, condition):
        return None  # Default nothing found

    def Exists(self, *args):
        return True

    def SetFocus(self): pass
    def SendKeys(self, k): pass
    def Invoke(self): pass
    def Click(self): pass

class MockWindowProvider:
    def __init__(self):
        self.root = MockControl("Root")
        
    def get_root_control(self):
        return self.root
    
    def set_windows(self, windows):
        self.root.children = windows

class MockConfig:
    def __init__(self, interval=0.1):
        self._interval = interval
        self.config = {
            "target_window_title": "Antigravity",
            "search_texts_ide": ["Accept"],
            "search_texts_agent_manager": ["Accept"],
            "context_text_agent_manager": [],
            "interval": interval
        }
    def get(self, key, default=None):
        return self.config.get(key, default)

class TestAutomationLoop(unittest.TestCase):
    def setUp(self):
        self.provider = MockWindowProvider()
        self.stop_event = threading.Event()
        self.snapshot_event = threading.Event()
        self.logger = MagicMock()
    
    def test_loop_interval_on_success(self):
        """Verify wait is called even if target found (periodic check)."""
        # Setup target
        target = MockControl("Antigravity")
        self.provider.set_windows([target])
        
        # We need to spy on stop_event.wait
        # Ideally the loop runs, finds target, waits, then runs again.
        
        strategy = IdeStrategy(self.provider)
        config = MockConfig(interval=0.01) # fast interval
        
        # Run in a thread or just let it run for a bit?
        # Better: Mock stop_event.wait so it has a side effect counter and eventually stops?
        
        wait_calls = 0
        def side_effect_wait(timeout):
            nonlocal wait_calls
            wait_calls += 1
            if wait_calls >= 3:
                self.stop_event.set() # Stop after 3 cycles
            return False # Timeout expired (normal loop)

        self.stop_event.wait = MagicMock(side_effect=side_effect_wait)
        self.stop_event.is_set = MagicMock(side_effect=lambda: wait_calls >= 3)
        
        strategy.run(self.stop_event, self.snapshot_event, config, self.logger)
        
        # Assertions
        # Should have called wait with correct interval
        self.stop_event.wait.assert_called_with(0.01)
        self.assertEqual(wait_calls, 3)

    def test_loop_interval_on_failure(self):
        """Verify wait is called even if target NOT found (periodic check)."""
        # No target windows
        self.provider.set_windows([])
        
        strategy = IdeStrategy(self.provider)
        config = MockConfig(interval=0.01)
        
        wait_calls = 0
        def side_effect_wait(timeout):
            nonlocal wait_calls
            wait_calls += 1
            if wait_calls >= 3:
                self.stop_event.set()
            return False

        self.stop_event.wait = MagicMock(side_effect=side_effect_wait)
        self.stop_event.is_set = MagicMock(side_effect=lambda: wait_calls >= 3)
        
        strategy.run(self.stop_event, self.snapshot_event, config, self.logger)
        
        self.stop_event.wait.assert_called_with(0.01)
        self.assertEqual(wait_calls, 3)

    def test_agent_manager_interval_success(self):
        """Verify AgentManager loop intervals."""
        target = MockControl("Antigravity")
        # Agent manager looks for buttons
        
        self.provider.set_windows([target])
        strategy = AgentManagerStrategy(self.provider)
        config = MockConfig(interval=0.01)
        
        wait_calls = 0
        def side_effect_wait(timeout):
            nonlocal wait_calls
            wait_calls += 1
            if wait_calls >= 3:
                self.stop_event.set()
            return False

        self.stop_event.wait = MagicMock(side_effect=side_effect_wait)
        self.stop_event.is_set = MagicMock(side_effect=lambda: wait_calls >= 3)
        
        strategy.run(self.stop_event, self.snapshot_event, config, self.logger)
        
        self.stop_event.wait.assert_called_with(0.01)
        self.assertEqual(wait_calls, 3)

if __name__ == '__main__':
    unittest.main()
