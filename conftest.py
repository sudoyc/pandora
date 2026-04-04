"""Root conftest.py — ensures packages resolve to the pandora project root.

The editable install MAPPING may point to a different workspace. We patch
the editable finder so that ``pandora_daemon`` always resolves from this
project's directory, making new modules visible immediately after creation.
"""
import sys
from pathlib import Path

_workspace_root = Path(__file__).parent

# Insert the workspace root at the front of sys.path (fallback path finder).
_workspace_root_str = str(_workspace_root)
if _workspace_root_str not in sys.path:
    sys.path.insert(0, _workspace_root_str)

# Patch the editable install MAPPING so pandora_daemon points here, not to
# a stale workspace that may be missing newly created modules.
_pandora_daemon_path = str(_workspace_root / "pandora_daemon")
for _finder in sys.meta_path:
    _mapping = getattr(_finder, "MAPPING", None) if hasattr(_finder, "__class__") else None
    if _mapping is None:
        # Try via the module the finder belongs to
        _mod = getattr(_finder, "__module__", None)
        if _mod and "editable" in (_mod or ""):
            import importlib
            _editable_mod = importlib.import_module(_mod)
            _mapping = getattr(_editable_mod, "MAPPING", None)
    if _mapping is not None and "pandora_daemon" in _mapping:
        _mapping["pandora_daemon"] = _pandora_daemon_path
        break
