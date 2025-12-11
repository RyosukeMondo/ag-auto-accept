
import threading
from typing import Optional, Callable
from injector import inject, singleton

from ag_accept.services.config_service import ConfigService
from ag_accept.services.debug_service import DebugService
from ag_accept.services.scheduler_service import SchedulerService
from ag_accept.services.window_service import WindowService
from ag_accept.services.text_query_service import TextQueryService
from ag_accept.automation import IdeStrategy, AgentManagerStrategy, AutomationStrategy

@singleton
class AutomationService:
    """
    Service responsible for managing the automation lifecycle (start/stop)
    and selecting the appropriate strategy.
    """
    
    @inject
    def __init__(self, 
                 config: ConfigService, 
                 debug: DebugService,
                 scheduler: SchedulerService,
                 window: WindowService, # passed to strategies
                 text: TextQueryService # passed to strategies
                 ):
        self.config = config
        self.debug_service = debug
        self.scheduler = scheduler
        self.window_service = window
        self.text_service = text
        
        self.thread: Optional[threading.Thread] = None
        self.stop_event: Optional[threading.Event] = None
        self.snapshot_event = threading.Event()
        self.is_running_flag = False

    def start_automation(self, mode: str, logger: Callable[[str], None], state_callback: Optional[Callable[[str], None]] = None) -> None:
        if self.is_running_flag:
            return

        self.is_running_flag = True
        self.stop_event = threading.Event()
        self.snapshot_event.clear()
        
        # Decide strategy
        strategy: Optional[AutomationStrategy] = None
        if mode == "IDE":
            strategy = IdeStrategy(self.window_service, self.text_service, self.debug_service)
        elif mode == "AgentManager":
            strategy = AgentManagerStrategy(self.window_service, self.text_service, self.debug_service)
        
        if not strategy:
            logger(f"Error: Unknown mode {mode}")
            self.stop_automation()
            return
            
        debug_enabled = self.config.debug_enabled

        def run_target():
             try:
                 strategy.run(self.stop_event, self.snapshot_event, self.config, logger, state_callback, debug_enabled)
             except Exception as e:
                 logger(f"Automation Thread Error: {e}")
             finally:
                 self.is_running_flag = False

        self.thread = threading.Thread(target=run_target)
        self.thread.daemon = True
        self.thread.start()

    def stop_automation(self) -> None:
        if self.is_running_flag and self.stop_event:
            self.stop_event.set()
        
        # We don't join here to avoid blocking UI, usually daemon thread just dies or logic stops
        self.is_running_flag = False

    def trigger_snapshot(self) -> None:
        if self.is_running_flag:
            self.snapshot_event.set()

    def is_running(self) -> bool:
        return self.is_running_flag
