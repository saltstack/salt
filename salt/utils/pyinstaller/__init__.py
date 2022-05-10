"""
This module exists to help PyInstaller bundle Salt
"""
import pathlib

PYINSTALLER_UTILS_DIR_PATH = pathlib.Path(__file__).resolve().parent


def get_hook_dirs():
    """
    Return a list of paths that PyInstaller can search for hooks.
    """
    hook_dirs = {PYINSTALLER_UTILS_DIR_PATH}
    for path in PYINSTALLER_UTILS_DIR_PATH.iterdir():
        if not path.is_dir():
            continue
        if "__pycache__" in path.parts:
            continue
        hook_dirs.add(path)

    return sorted(str(p) for p in hook_dirs)
