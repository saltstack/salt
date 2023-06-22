import os
import pathlib
import sys

_repo_root = pathlib.Path(__file__).parent.parent
_paths_to_check = {""}
if sys.platform.startswith("win"):
    _paths_to_check.add(str(_repo_root).replace("\\", "\\\\"))
    _paths_to_check.add(str(_repo_root.resolve()).replace("\\", "\\\\"))
else:
    _paths_to_check.add(str(_repo_root))


if os.environ.get("ONEDIR_TESTRUN", "0") == "1":
    # In this particular case, we want to make sure that the repo root
    # is not part if sys.path so that when we import salt, we import salt from
    # the onedir and not the code checkout
    for path in _paths_to_check:
        if path in sys.path:
            sys.path.remove(path)
