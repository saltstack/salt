import pathlib
import sys


def setup(pth_file_path):
    # Discover the extras-<py-major>.<py-minor> directory
    extras_parent_path = pathlib.Path(pth_file_path).resolve().parent.parent
    if not sys.platform.startswith("win"):
        extras_parent_path = extras_parent_path.parent

    extras_path = str(extras_parent_path / "extras-{}.{}".format(*sys.version_info))

    if extras_path in sys.path and sys.path[0] != extras_path:
        # The extras directory must come first
        sys.path.remove(extras_path)

    if extras_path not in sys.path:
        sys.path.insert(0, extras_path)
