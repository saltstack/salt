#!/usr/bin/env python3
# see issue: https://gitlab.com/saltstack/open/salt-pkg/-/issues/19
import _pyio
import contextlib
import multiprocessing
import os
import pathlib
import sys

import salt.scripts
import salt.utils.platform

# tiamat pip breaks singlebin on Windows at the moment
# https://gitlab.com/saltstack/pop/tiamat-pip/-/issues/4
if not sys.platform.startswith("win"):
    import tiamatpip.cli
    import tiamatpip.configure
    import tiamatpip.utils

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


# tiamat pip breaks singlebin on Windows at the moment
# https://gitlab.com/saltstack/pop/tiamat-pip/-/issues/4
if not sys.platform.startswith("win"):
    PIP_PATH = pathlib.Path(f"{os.sep}opt", "saltstack", "salt", "pypath")
    with contextlib.suppress(PermissionError):
        PIP_PATH.mkdir(mode=0o755, parents=True, exist_ok=True)
    tiamatpip.configure.set_user_site_packages_path(PIP_PATH)


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
    # tiamat pip breaks singlebin on Windows at the moment
    # https://gitlab.com/saltstack/pop/tiamat-pip/-/issues/4
    if not sys.platform.startswith("win"):
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
    # tiamat pip breaks singlebin on Windows at the moment
    # https://gitlab.com/saltstack/pop/tiamat-pip/-/issues/4
    if not sys.platform.startswith("win"):
        with tiamatpip.utils.patched_sys_argv(args):
            s_fun()
    else:
        s_fun()


def py_shell():
    if not sys.platform.startswith("win"):
        import readline  # optional, will allow Up/Down/History in the console
    import code

    variables = globals().copy()
    variables.update(locals())
    shell = code.InteractiveConsole(variables)
    shell.interact()


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        multiprocessing.freeze_support()
    redirect(sys.argv)
