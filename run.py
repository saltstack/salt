#!/usr/bin/env python3
# see issue: https://gitlab.com/saltstack/open/salt-pkg/-/issues/19
import contextlib
import multiprocessing
import os
import pathlib
import sys

import _pyio
import tiamatpip.cli
import tiamatpip.configure
import tiamatpip.utils

import salt.scripts
import salt.utils.platform

AVAIL = (
    "minion",
    "master",
    "call",
    "api",
    "cloud",
    "cp",
    "extend",
    "key",
    "proxy",
    "pip",
    "run",
    "shell",
    "spm",
    "ssh",
    "support",
    "syndic",
    "python",
)


if "TIAMAT_PIP_PYPATH" in os.environ:
    PIP_PATH = pathlib.Path(os.environ["TIAMAT_PIP_PYPATH"]).resolve()
elif not sys.platform.startswith("win"):
    PIP_PATH = pathlib.Path(f"{os.sep}opt", "saltstack", "salt", "pypath")
else:
    PIP_PATH = pathlib.Path(os.getenv("LocalAppData"), "salt", "pypath")
with contextlib.suppress(PermissionError):
    PIP_PATH.mkdir(mode=0o755, parents=True, exist_ok=True)
tiamatpip.configure.set_user_base_path(PIP_PATH)


def py_shell():
    if not sys.platform.startswith("win"):
        # optional, will allow Up/Down/History in the console
        import readline
    import code

    variables = globals().copy()
    variables.update(locals())
    shell = code.InteractiveConsole(variables)
    shell.interact()


def python_runtime():
    import traceback

    # extract the absolute script path to alter sys.path and specific dunder variables
    script = pathlib.Path(sys.argv[2]).expanduser().resolve()
    sys.path.insert(0, str(script.parent))

    # update passed args so they don't start with "<binary> python"
    sys.argv[:] = sys.argv[2:]
    exec_locals = {"__name__": "__main__", "__file__": str(script), "__doc__": None}
    with open(script, encoding="utf-8") as rfh:
        try:
            exec(rfh.read(), exec_locals)
        except Exception:
            traceback.print_exc()
            sys.exit(1)


def redirect(argv):
    """
    Change the args and redirect to another salt script
    """
    if len(argv) < 2:
        msg = "Must pass in a salt command, available commands are:"
        for cmd in AVAIL:
            msg += f"\n{cmd}"
        print(msg, file=sys.stderr, flush=True)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "shell":
        py_shell()
        return
    if cmd == "python":
        if len(argv) < 3:
            msg = "Must pass script location to this command"
            print(msg, file=sys.stderr, flush=True)
            sys.exit(1)

        python_runtime()
        return
    if tiamatpip.cli.should_redirect_argv(argv):
        tiamatpip.cli.process_pip_argv(argv)
        return
    if cmd not in AVAIL:
        # Fall back to the salt command
        args = ["salt"]
        s_fun = salt.scripts.salt_main
    else:
        args = [f"salt-{cmd}"]
        sys.argv.pop(1)
        s_fun = getattr(salt.scripts, f"salt_{cmd}")
    args.extend(argv[1:])
    with tiamatpip.utils.patched_sys_argv(args):
        s_fun()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    redirect(sys.argv)
