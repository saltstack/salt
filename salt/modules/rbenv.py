"""
Manage ruby installations with rbenv. rbenv is supported on Linux and macOS.
rbenv doesn't work on Windows (and isn't really necessary on Windows as there is
no system Ruby on Windows). On Windows, the RubyInstaller and/or Pik are both
good alternatives to work with multiple versions of Ruby on the same box.

http://misheska.com/blog/2013/06/15/using-rbenv-to-manage-multiple-versions-of-ruby/

.. versionadded:: 0.16.0
"""


import logging
import os
import re

import salt.utils.args
import salt.utils.data
import salt.utils.path
import salt.utils.platform
from salt.exceptions import SaltInvocationError

# Set up logger
log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}

__opts__ = {
    "rbenv.root": None,
    "rbenv.build_env": None,
}


def __virtual__():
    """
    Only work on POSIX-like systems
    """
    if salt.utils.platform.is_windows():
        return (
            False,
            "The rbenv execution module failed to load: only available on non-Windows"
            " systems.",
        )
    return True


def _shlex_split(s):
    # from python:salt.utils.args.shlex_split: passing None for s will read
    # the string to split from standard input.
    if s is None:
        ret = salt.utils.args.shlex_split("")
    else:
        ret = salt.utils.args.shlex_split(s)

    return ret


def _parse_env(env):
    if not env:
        env = {}
    if isinstance(env, list):
        env = salt.utils.data.repack_dictlist(env)
    if not isinstance(env, dict):
        env = {}

    for bad_env_key in (x for x, y in env.items() if y is None):
        log.error(
            "Environment variable '%s' passed without a value. "
            "Setting value to an empty string",
            bad_env_key,
        )
        env[bad_env_key] = ""

    return env


def _rbenv_bin(runas=None):
    path = _rbenv_path(runas)
    return "{}/bin/rbenv".format(path)


def _rbenv_path(runas=None):
    path = None
    if runas in (None, "root"):
        path = __salt__["config.option"]("rbenv.root") or "/usr/local/rbenv"
    else:
        path = __salt__["config.option"]("rbenv.root") or "~{}/.rbenv".format(runas)

    return os.path.expanduser(path)


def _rbenv_exec(command, env=None, runas=None, ret=None):
    if not is_installed(runas):
        return False

    binary = _rbenv_bin(runas)
    path = _rbenv_path(runas)

    environ = _parse_env(env)
    environ["RBENV_ROOT"] = path

    result = __salt__["cmd.run_all"]([binary] + command, runas=runas, env=environ)

    if isinstance(ret, dict):
        ret.update(result)
        return ret

    if result["retcode"] == 0:
        return result["stdout"]
    else:
        return False


def _install_rbenv(path, runas=None):
    if os.path.isdir(path):
        return True

    cmd = ["git", "clone", "https://github.com/rbenv/rbenv.git", path]
    return __salt__["cmd.retcode"](cmd, runas=runas, python_shell=False) == 0


def _install_ruby_build(path, runas=None):
    path = "{}/plugins/ruby-build".format(path)
    if os.path.isdir(path):
        return True

    cmd = ["git", "clone", "https://github.com/rbenv/ruby-build.git", path]
    return __salt__["cmd.retcode"](cmd, runas=runas, python_shell=False) == 0


def _update_rbenv(path, runas=None):
    if not os.path.isdir(path):
        return False

    return (
        __salt__["cmd.retcode"](
            ["git", "pull"], runas=runas, cwd=path, python_shell=False
        )
        == 0
    )


def _update_ruby_build(path, runas=None):
    path = "{}/plugins/ruby-build".format(path)
    if not os.path.isdir(path):
        return False

    return (
        __salt__["cmd.retcode"](
            ["git", "pull"], runas=runas, cwd=path, python_shell=False
        )
        == 0
    )


def install(runas=None, path=None):
    """
    Install rbenv systemwide

    CLI Example:

    .. code-block:: bash

        salt '*' rbenv.install
    """
    path = path or _rbenv_path(runas)
    path = os.path.expanduser(path)
    return _install_rbenv(path, runas) and _install_ruby_build(path, runas)


def update(runas=None, path=None):
    """
    Updates the current versions of rbenv and ruby-build

    runas
        The user under which to run rbenv. If not specified, then rbenv will be
        run as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rbenv.update
    """
    path = path or _rbenv_path(runas)
    path = os.path.expanduser(path)

    return _update_rbenv(path, runas) and _update_ruby_build(path, runas)


def is_installed(runas=None):
    """
    Check if rbenv is installed

    CLI Example:

    .. code-block:: bash

        salt '*' rbenv.is_installed
    """
    return __salt__["cmd.has_exec"](_rbenv_bin(runas))


def install_ruby(ruby, runas=None):
    """
    Install a ruby implementation.

    ruby
        The version of Ruby to install, should match one of the
        versions listed by :py:func:`rbenv.list <salt.modules.rbenv.list>`

    runas
        The user under which to run rbenv. If not specified, then rbenv will be
        run as the user under which Salt is running.

    Additional environment variables can be configured in pillar /
    grains / master:

    .. code-block:: yaml

        rbenv:
          build_env: 'CONFIGURE_OPTS="--no-tcmalloc" CFLAGS="-fno-tree-dce"'

    CLI Example:

    .. code-block:: bash

        salt '*' rbenv.install_ruby 2.0.0-p0
    """
    ruby = re.sub(r"^ruby-", "", ruby)

    env = None
    env_list = []

    if __grains__["os"] in ("FreeBSD", "NetBSD", "OpenBSD"):
        env_list.append("MAKE=gmake")

    if __salt__["config.get"]("rbenv:build_env"):
        env_list.append(__salt__["config.get"]("rbenv:build_env"))
    elif __salt__["config.option"]("rbenv.build_env"):
        env_list.append(__salt__["config.option"]("rbenv.build_env"))

    if env_list:
        env = " ".join(env_list)

    ret = {}
    ret = _rbenv_exec(["install", ruby], env=env, runas=runas, ret=ret)
    if ret is not False and ret["retcode"] == 0:
        rehash(runas=runas)
        return ret["stderr"]
    else:
        # Cleanup the failed installation so it doesn't list as installed
        uninstall_ruby(ruby, runas=runas)
        return False


def uninstall_ruby(ruby, runas=None):
    """
    Uninstall a ruby implementation.

    ruby
        The version of ruby to uninstall. Should match one of the versions
        listed by :py:func:`rbenv.versions <salt.modules.rbenv.versions>`.

    runas
        The user under which to run rbenv. If not specified, then rbenv will be
        run as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rbenv.uninstall_ruby 2.0.0-p0
    """
    ruby = re.sub(r"^ruby-", "", ruby)
    _rbenv_exec(["uninstall", "--force", ruby], runas=runas)
    return True


def versions(runas=None):
    """
    List the installed versions of ruby

    CLI Example:

    .. code-block:: bash

        salt '*' rbenv.versions
    """
    ret = _rbenv_exec(["versions", "--bare"], runas=runas)
    return [] if ret is False else ret.splitlines()


def default(ruby=None, runas=None):
    """
    Returns or sets the currently defined default ruby

    ruby
        The version to set as the default. Should match one of the versions
        listed by :py:func:`rbenv.versions <salt.modules.rbenv.versions>`.
        Leave blank to return the current default.

    CLI Example:

    .. code-block:: bash

        salt '*' rbenv.default
        salt '*' rbenv.default 2.0.0-p0
    """
    if ruby:
        _rbenv_exec(["global", ruby], runas=runas)
        return True
    else:
        ret = _rbenv_exec(["global"], runas=runas)
        return "" if ret is False else ret.strip()


def list_(runas=None):
    """
    List the installable versions of ruby

    runas
        The user under which to run rbenv. If not specified, then rbenv will be
        run as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rbenv.list
    """
    ret = []
    output = _rbenv_exec(["install", "--list"], runas=runas)
    if output:
        for line in output.splitlines():
            if line == "Available versions:":
                continue
            ret.append(line.strip())
    return ret


def rehash(runas=None):
    """
    Run ``rbenv rehash`` to update the installed shims

    runas
        The user under which to run rbenv. If not specified, then rbenv will be
        run as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rbenv.rehash
    """
    _rbenv_exec(["rehash"], runas=runas)
    return True


def do(cmdline, runas=None, env=None):
    """
    Execute a ruby command with rbenv's shims from the user or the system

    CLI Example:

    .. code-block:: bash

        salt '*' rbenv.do 'gem list bundler'
        salt '*' rbenv.do 'gem list bundler' deploy
    """
    if not cmdline:
        # This is a positional argument so this should never happen, but this
        # will handle cases where someone explicitly passes a false value for
        # cmdline.
        raise SaltInvocationError("Command must be specified")

    path = _rbenv_path(runas)
    if not env:
        env = {}

    # NOTE: Env vars (and their values) need to be str type on both Python 2
    # and 3. The code below first normalizes all path components to unicode to
    # stitch them together, and then converts the result back to a str type.
    env["PATH"] = salt.utils.stringutils.to_str(
        os.pathsep.join(
            (
                salt.utils.path.join(path, "shims"),
                salt.utils.stringutils.to_unicode(os.environ["PATH"]),
            )
        )
    )

    try:
        cmdline = salt.utils.args.shlex_split(cmdline)
    except AttributeError:
        cmdauth = salt.utils.args.shlex_split(str(cmdline))

    result = __salt__["cmd.run_all"](cmdline, runas=runas, env=env, python_shell=False)

    if result["retcode"] == 0:
        rehash(runas=runas)
        return result["stdout"]
    else:
        return False


def do_with_ruby(ruby, cmdline, runas=None):
    """
    Execute a ruby command with rbenv's shims using a specific ruby version

    CLI Example:

    .. code-block:: bash

        salt '*' rbenv.do_with_ruby 2.0.0-p0 'gem list bundler'
        salt '*' rbenv.do_with_ruby 2.0.0-p0 'gem list bundler' runas=deploy
    """
    if not cmdline:
        # This is a positional argument so this should never happen, but this
        # will handle cases where someone explicitly passes a false value for
        # cmdline.
        raise SaltInvocationError("Command must be specified")

    try:
        cmdline = salt.utils.args.shlex_split(cmdline)
    except AttributeError:
        cmdline = salt.utils.args.shlex_split(str(cmdline))

    env = {}
    if ruby:
        env["RBENV_VERSION"] = ruby
        cmd = cmdline
    else:
        cmd = cmdline

    return do(cmd, runas=runas, env=env)
