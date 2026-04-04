"""Root conftest.py — ensures the workspace root is on sys.path so that
packages like ``pandora_daemon`` (not yet in the editable install MAPPING)
are importable during test collection."""
import sys
from pathlib import Path

# Insert the workspace root at the front of sys.path so that newly added
# packages are found even before they are picked up by the editable
# install finder.
_workspace_root = str(Path(__file__).parent)
if _workspace_root not in sys.path:
    sys.path.insert(0, _workspace_root)
