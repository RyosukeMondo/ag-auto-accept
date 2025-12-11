import uiautomation as auto
from typing import List, Optional, Any

class TextQueryService:
    """
    Service for extracting text and finding elements within UI controls.
    Encapsulates the recursive text search logic from IDE mode.
    """

    def has_text_recursive(self, control: Any, texts: List[str], max_depth: int = 25) -> bool:
        """
        Recursively checks if any of the given texts exist in the control or its children.
        """
        return self._has_text_recursive_internal(control, texts, 0, max_depth)

    def _has_text_recursive_internal(self, control: Any, texts: List[str], current_depth: int, max_depth: int) -> bool:
        if current_depth > max_depth:
            return False
            
        try:
            c_name = control.Name
            for t in texts:
                if t in c_name:
                    return True
        except:
            pass

        try:
            for child in control.GetChildren():
                if self._has_text_recursive_internal(child, texts, current_depth + 1, max_depth):
                    return True
        except:
            pass
            
        return False

    def find_button_with_text(self, root_control: Any, texts: List[str]) -> Optional[Any]:
        """
        Finds a ButtonControl that contains any of the specified texts in its Name.
        """
        def button_matcher(control, depth):
            try:
                if control.ControlTypeName == "ButtonControl":
                    c_name = control.Name
                    for s in texts:
                        if s in c_name:
                            return True
            except:
                pass
            return False

        try:
            return root_control.FindFirst(auto.TreeScope.Descendants, button_matcher)
        except Exception:
            return None

    def dump_texts(self, control: Any, max_depth: int = 25) -> List[str]:
        """
        Dumps all text found in the control tree for debugging.
        """
        results = []
        self._dump_texts_recursive(control, results, 0, max_depth)
        return results

    def _dump_texts_recursive(self, control: Any, results: List[str], current_depth: int, max_depth: int):
        if current_depth > max_depth:
            return

        try:
            name = control.Name
            if name:
                results.append(f"{'  ' * current_depth}{name} [{control.ControlTypeName}]")
        except:
            pass

        try:
            for child in control.GetChildren():
                self._dump_texts_recursive(child, results, current_depth + 1, max_depth)
        except:
            pass
