import os
import pathlib
import sys

_repo_root = pathlib.Path(__file__).parent.parent

if os.environ.get("ONEDIR_TESTRUN", "0") == "1":
    # In this particular case, we want to make sure that the repo root
    # is not part if sys.path so that when we import salt, we import salt from
    # the onedir and not the code checkout
    if "" in sys.path:
        sys.path.remove("")
    if str(_repo_root) in sys.path:
        sys.path.remove(str(_repo_root))
