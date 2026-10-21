import os
import pathlib
import sys


def setup(pth_file_path):
    # Honor SALT_EXTRAS_DIR when set (packaging with SALT_ONEDIR_HARDEN
    # relocates the extras tree outside /opt/saltstack/salt so the onedir
    # can stay read-only). See issue #70198. Fall back to the historical
    # <relenv_root>/extras-<py-major>.<py-minor> location otherwise.
    extras_override = os.environ.get("SALT_EXTRAS_DIR")
    if extras_override:
        extras_path = extras_override
    else:
        extras_parent_path = pathlib.Path(pth_file_path).resolve().parent.parent
        if not sys.platform.startswith("win"):
            extras_parent_path = extras_parent_path.parent

        extras_path = str(extras_parent_path / "extras-{}.{}".format(*sys.version_info))

    if extras_path in sys.path and sys.path[0] != extras_path:
        # The extras directory must come first
        sys.path.remove(extras_path)

    if extras_path not in sys.path:
        sys.path.insert(0, extras_path)
