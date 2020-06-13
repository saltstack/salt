# -*- coding: utf-8 -*-
#!/usr/bin/env python3

# Import python libs
import multiprocessing
import os
import site
import sys

# Import third party libs
from pip._internal.cli.main import main

# Import salt libs
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
)


PIP_PATH = os.path.join("opt", "saltstack", "salt", "pypath")
if not os.path.exists(PIP_PATH):
    os.makedirs(PIP_PATH, mode=0o755)

site.ENABLE_USER_SITE = True
site.USER_BASE = PIP_PATH


def redirect():
    """
    Change the args and redirect to another salt script
    """
    if len(sys.argv) < 2:
        msg = "Must pass in a salt command, available commands are:"
        for cmd in AVAIL:
            msg += "\n{0}".format(cmd)
        print(msg)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "shell":
        py_shell()
        return
    elif cmd == "pip":
        pip()
        return
    elif cmd not in AVAIL:
        # Fall back to the salt command
        sys.argv[0] = "salt"
        s_fun = salt.scripts.salt_main
    else:
        sys.argv[0] = "salt-{0}".format(cmd)
        sys.argv.pop(1)
        s_fun = getattr(salt.scripts, "salt_{0}".format(cmd))
    s_fun()


def py_shell():
    import readline  # optional, will allow Up/Down/History in the console
    import code

    variables = globals().copy()
    variables.update(locals())
    shell = code.InteractiveConsole(variables)
    shell.interact()


def pip():
    targets = (
        "install",
        "list",
        "freeze",
        "uninstall",
    )
    try:
        cmd = sys.argv[2]
    except IndexError:
        msg = "Must pass in available pip command which are:"
        for cmd in targets:
            msg += "\n{0}".format(cmd)
        print(msg)
        sys.exit(1)

    # Valid command found
    if cmd == "install" and cmd in targets:
        args = [cmd, "--target", PIP_PATH]
        _change_perms(PIP_PATH, 0o777)
    elif cmd == "uninstall" and cmd in targets:
        print("pip uninstall is a feature in progress")
        sys.exit(1)
    elif cmd == "list" or "freeze" and cmd in targets:
        args = [cmd, "--path", PIP_PATH]
    else:
        args = [cmd]
    args.extend(sys.argv[3:])
    parser = ["pip"] + args
    sys.argv = parser
    main(args)

    # When main return, return original mode to restrict access
    _change_perms(PIP_PATH, 0o755)


def _change_perms(path, mode):
    for root, dirs, files in os.walk(path, topdown=False):
        for dir in [os.path.join(root, d) for d in dirs]:
            os.chmod(dir, mode)
        for file in [os.path.join(root, f) for f in files]:
            os.chmod(file, mode)


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        multiprocessing.freeze_support()
    redirect()
