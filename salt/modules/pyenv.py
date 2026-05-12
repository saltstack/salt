"""
Manage python installations with pyenv.

.. note::
    Git needs to be installed and available via PATH if pyenv is to be
    installed automatically by the module.

.. versionadded:: 2014.4.0
"""

import logging
import os
import re
import shlex

# Set up logger
log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}

__opts__ = {
    "pyenv.root": None,
    "pyenv.build_env": None,
}


def _pyenv_exec(command, args="", env=None, runas=None, ret=None):
    if not is_installed(runas):
        return False

    binary = _pyenv_bin(runas)
    path = _pyenv_path(runas)

    if env:
        env = f" {env}"
    env = env or ""

    binary = f"env PYENV_ROOT={path}{env} {binary}"

    result = __salt__["cmd.run_all"](f"{binary} {command} {args}", runas=runas)

    if isinstance(ret, dict):
        ret.update(result)
        return ret

    if result["retcode"] == 0:
        return result["stdout"]
    else:
        return False


def _pyenv_bin(runas=None):
    path = _pyenv_path(runas)
    return f"{path}/bin/pyenv"


def _pyenv_path(runas=None):
    path = None
    if runas in (None, "root"):
        path = __salt__["config.option"]("pyenv.root") or "/usr/local/pyenv"
    else:
        path = __salt__["config.option"]("pyenv.root") or f"~{runas}/.pyenv"

    return os.path.expanduser(path)


def _install_pyenv(path, runas=None):
    if os.path.isdir(path):
        return True

    return 0 == __salt__["cmd.retcode"](
        f"git clone https://github.com/yyuu/pyenv.git {path}", runas=runas
    )


def _update_pyenv(path, runas=None):
    if not os.path.isdir(path):
        return False

    return 0 == __salt__["cmd.retcode"](
        f"cd {shlex.quote(path)} && git pull", runas=runas
    )


def _update_python_build(path, runas=None):
    path = f"{path}/plugins/python-build"
    if not os.path.isdir(path):
        return False

    return 0 == __salt__["cmd.retcode"](
        f"cd {shlex.quote(path)} && git pull", runas=runas
    )


def install(runas=None, path=None):
    """
    Install pyenv systemwide

    CLI Example:

    .. code-block:: bash

        salt '*' pyenv.install
    """
    path = path or _pyenv_path(runas)
    path = os.path.expanduser(path)
    return _install_pyenv(path, runas)


def update(runas=None, path=None):
    """
    Updates the current versions of pyenv and python-Build

    CLI Example:

    .. code-block:: bash

        salt '*' pyenv.update
    """
    path = path or _pyenv_path(runas)
    path = os.path.expanduser(path)

    return _update_pyenv(path, runas)


def is_installed(runas=None):
    """
    Check if pyenv is installed.

    CLI Example:

    .. code-block:: bash

        salt '*' pyenv.is_installed
    """
    return __salt__["cmd.has_exec"](_pyenv_bin(runas))


def install_python(python, runas=None):
    """
    Install a python implementation.

    python
        The version of python to install, should match one of the
        versions listed by pyenv.list

    CLI Example:

    .. code-block:: bash

        salt '*' pyenv.install_python 2.0.0-p0
    """
    python = re.sub(r"^python-", "", python)

    env = None
    env_list = []

    if __grains__["os"] in ("FreeBSD", "NetBSD", "OpenBSD"):
        env_list.append("MAKE=gmake")

    if __salt__["config.option"]("pyenv.build_env"):
        env_list.append(__salt__["config.option"]("pyenv.build_env"))

    if env_list:
        env = " ".join(env_list)

    ret = {}
    ret = _pyenv_exec("install", python, env=env, runas=runas, ret=ret)
    if ret["retcode"] == 0:
        rehash(runas=runas)
        return ret["stderr"]
    else:
        # Cleanup the failed installation so it doesn't list as installed
        uninstall_python(python, runas=runas)
        return False


def uninstall_python(python, runas=None):
    """
    Uninstall a python implementation.

    python
        The version of python to uninstall. Should match one of the versions
        listed by :mod:`pyenv.versions <salt.modules.pyenv.versions>`

    CLI Example:

    .. code-block:: bash

        salt '*' pyenv.uninstall_python 2.0.0-p0
    """
    python = re.sub(r"^python-", "", python)

    args = f"--force {python}"
    _pyenv_exec("uninstall", args, runas=runas)
    return True


def versions(runas=None):
    """
    List the installed versions of python.

    CLI Example:

    .. code-block:: bash

        salt '*' pyenv.versions
    """
    ret = _pyenv_exec("versions", "--bare", runas=runas)
    return [] if ret is False else ret.splitlines()


def default(python=None, runas=None):
    """
    Returns or sets the currently defined default python.

    python=None
        The version to set as the default. Should match one of the versions
        listed by :mod:`pyenv.versions <salt.modules.pyenv.versions>`. Leave
        blank to return the current default.

    CLI Example:

    .. code-block:: bash

        salt '*' pyenv.default
        salt '*' pyenv.default 2.0.0-p0
    """
    if python:
        _pyenv_exec("global", python, runas=runas)
        return True
    else:
        ret = _pyenv_exec("global", runas=runas)
        return "" if ret is False else ret.strip()


def list_(runas=None):
    """
    List the installable versions of python.

    CLI Example:

    .. code-block:: bash

        salt '*' pyenv.list
    """
    ret = []
    output = _pyenv_exec("install", "--list", runas=runas)
    if output:
        for line in output.splitlines():
            if line == "Available versions:":
                continue
            ret.append(line.strip())
    return ret


def rehash(runas=None):
    """
    Run pyenv rehash to update the installed shims.

    CLI Example:

    .. code-block:: bash

        salt '*' pyenv.rehash
    """
    _pyenv_exec("rehash", runas=runas)
    return True


def do(cmdline=None, runas=None):
    """
    Execute a python command with pyenv's shims from the user or the system.

    CLI Example:

    .. code-block:: bash

        salt '*' pyenv.do 'gem list bundler'
        salt '*' pyenv.do 'gem list bundler' deploy
    """
    path = _pyenv_path(runas)
    cmd_split = cmdline.split()
    quoted_line = ""
    for cmd in cmd_split:
        quoted_line = quoted_line + " " + shlex.quote(cmd)
    result = __salt__["cmd.run_all"](
        f"env PATH={shlex.quote(path)}/shims:$PATH {quoted_line}",
        runas=runas,
        python_shell=True,
    )

    if result["retcode"] == 0:
        rehash(runas=runas)
        return result["stdout"]
    else:
        return False


def do_with_python(python, cmdline, runas=None):
    """
    Execute a python command with pyenv's shims using a specific python version.

    CLI Example:

    .. code-block:: bash

        salt '*' pyenv.do_with_python 2.0.0-p0 'gem list bundler'
        salt '*' pyenv.do_with_python 2.0.0-p0 'gem list bundler' deploy
    """
    if python:
        cmd = f"PYENV_VERSION={python} {cmdline}"
    else:
        cmd = cmdline

    return do(cmd, runas=runas)
