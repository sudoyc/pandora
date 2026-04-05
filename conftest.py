"""Root conftest.py — ensures packages resolve to the pandora project root."""
import sys
from pathlib import Path

_workspace_root = Path(__file__).parent
_workspace_root_str = str(_workspace_root)
if _workspace_root_str not in sys.path:
    sys.path.insert(0, _workspace_root_str)
