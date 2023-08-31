import os
import pathlib
import sys

_repo_root = pathlib.Path(__file__).resolve().parent.parent

if os.environ.get("ONEDIR_TESTRUN", "0") == "1":
    # In this particular case, we want to make sure that the repo root
    # is not part if sys.path so that when we import salt, we import salt from
    # the onedir and not the code checkout
    for path in list(sys.path):
        if path == "":
            sys.path.remove(path)
        elif pathlib.Path(path).resolve() == _repo_root:
            sys.path.remove(path)
