# -*- coding: utf-8 -*-
"""
Manage and query NPM packages.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

import salt.modules.cmdmod

# Import salt libs
import salt.utils.json
import salt.utils.path
import salt.utils.user
from salt.exceptions import CommandExecutionError
from salt.ext import six
from salt.utils.versions import LooseVersion as _LooseVersion

try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote


log = logging.getLogger(__name__)

# Function alias to make sure not to shadow built-in's
__func_alias__ = {"list_": "list"}


def __virtual__():
    """
    Only work when npm is installed.
    """
    try:
        if salt.utils.path.which("npm") is not None:
            _check_valid_version()
            return True
        else:
            return (
                False,
                "npm execution module could not be loaded "
                "because the npm binary could not be located",
            )
    except CommandExecutionError as exc:
        return (False, six.text_type(exc))


def _check_valid_version():
    """
    Check the version of npm to ensure this module will work. Currently
    npm must be at least version 1.2.
    """

    # Locate the full path to npm
    npm_path = salt.utils.path.which("npm")

    # pylint: disable=no-member
    res = salt.modules.cmdmod.run(
        "{npm} --version".format(npm=npm_path), output_loglevel="quiet"
    )
    npm_version, valid_version = _LooseVersion(res), _LooseVersion("1.2")
    # pylint: enable=no-member
    if npm_version < valid_version:
        raise CommandExecutionError(
            "'npm' is not recent enough({0} < {1}). Please Upgrade.".format(
                npm_version, valid_version
            )
        )


def install(
    pkg=None,
    pkgs=None,
    dir=None,
    runas=None,
    registry=None,
    env=None,
    dry_run=False,
    silent=True,
):
    """
    Install an NPM package.

    If no directory is specified, the package will be installed globally. If
    no package is specified, the dependencies (from package.json) of the
    package in the given directory will be installed.

    pkg
        A package name in any format accepted by NPM, including a version
        identifier

    pkgs
        A list of package names in the same format as the ``name`` parameter

        .. versionadded:: 2014.7.0

    dir
        The target directory in which to install the package, or None for
        global installation

    runas
        The user to run NPM with

    registry
        The NPM registry to install the package from.

        .. versionadded:: 2014.7.0

    env
        Environment variables to set when invoking npm. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.

        .. versionadded:: 2014.7.0

    silent
        Whether or not to run NPM install with --silent flag.

        .. versionadded:: 2016.3.0

    dry_run
        Whether or not to run NPM install with --dry-run flag.

        .. versionadded:: 2015.8.4

    silent
        Whether or not to run NPM install with --silent flag.

        .. versionadded:: 2015.8.5

    CLI Example:

    .. code-block:: bash

        salt '*' npm.install coffee-script

        salt '*' npm.install coffee-script@1.0.1

    """
    # Protect against injection
    if pkg:
        pkgs = [_cmd_quote(pkg)]
    elif pkgs:
        pkgs = [_cmd_quote(v) for v in pkgs]
    else:
        pkgs = []
    if registry:
        registry = _cmd_quote(registry)

    cmd = ["npm", "install", "--json"]
    if silent:
        cmd.append("--silent")

    if not dir:
        cmd.append("--global")

    if registry:
        cmd.append('--registry="{0}"'.format(registry))

    if dry_run:
        cmd.append("--dry-run")

    cmd.extend(pkgs)

    env = env or {}

    if runas:
        uid = salt.utils.user.get_uid(runas)
        if uid:
            env.update({"SUDO_UID": uid, "SUDO_USER": ""})

    cmd = " ".join(cmd)
    result = __salt__["cmd.run_all"](
        cmd, python_shell=True, cwd=dir, runas=runas, env=env
    )

    if result["retcode"] != 0:
        raise CommandExecutionError(result["stderr"])

    # npm >1.2.21 is putting the output to stderr even though retcode is 0
    npm_output = result["stdout"] or result["stderr"]
    try:
        return salt.utils.json.find_json(npm_output)
    except ValueError:
        return npm_output


def uninstall(pkg, dir=None, runas=None, env=None):
    """
    Uninstall an NPM package.

    If no directory is specified, the package will be uninstalled globally.

    pkg
        A package name in any format accepted by NPM

    dir
        The target directory from which to uninstall the package, or None for
        global installation

    runas
        The user to run NPM with

    env
        Environment variables to set when invoking npm. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.

        .. versionadded:: 2015.5.3

    CLI Example:

    .. code-block:: bash

        salt '*' npm.uninstall coffee-script

    """
    # Protect against injection
    if pkg:
        pkg = _cmd_quote(pkg)

    env = env or {}

    if runas:
        uid = salt.utils.user.get_uid(runas)
        if uid:
            env.update({"SUDO_UID": uid, "SUDO_USER": ""})

    cmd = ["npm", "uninstall", '"{0}"'.format(pkg)]
    if not dir:
        cmd.append("--global")

    cmd = " ".join(cmd)

    result = __salt__["cmd.run_all"](
        cmd, python_shell=True, cwd=dir, runas=runas, env=env
    )

    if result["retcode"] != 0:
        log.error(result["stderr"])
        return False
    return True


def list_(pkg=None, dir=None, runas=None, env=None, depth=None):
    """
    List installed NPM packages.

    If no directory is specified, this will return the list of globally-
    installed packages.

    pkg
        Limit package listing by name

    dir
        The directory whose packages will be listed, or None for global
        installation

    runas
        The user to run NPM with

        .. versionadded:: 2014.7.0

    env
        Environment variables to set when invoking npm. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.

        .. versionadded:: 2014.7.0

    depth
        Limit the depth of the packages listed

        .. versionadded:: 2016.11.6,2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' npm.list

    """
    env = env or {}

    if runas:
        uid = salt.utils.user.get_uid(runas)
        if uid:
            env.update({"SUDO_UID": uid, "SUDO_USER": ""})

    cmd = ["npm", "list", "--json", "--silent"]

    if not dir:
        cmd.append("--global")

    if depth is not None:
        if not isinstance(depth, (int, float)):
            raise salt.exceptions.SaltInvocationError(
                "Error: depth {0} must be a number".format(depth)
            )
        cmd.append("--depth={0}".format(int(depth)))

    if pkg:
        # Protect against injection
        pkg = _cmd_quote(pkg)
        cmd.append('"{0}"'.format(pkg))
    cmd = " ".join(cmd)

    result = __salt__["cmd.run_all"](
        cmd, cwd=dir, runas=runas, env=env, python_shell=True, ignore_retcode=True
    )

    # npm will return error code 1 for both no packages found and an actual
    # error. The only difference between the two cases are if stderr is empty
    if result["retcode"] != 0 and result["stderr"]:
        raise CommandExecutionError(result["stderr"])

    return salt.utils.json.loads(result["stdout"]).get("dependencies", {})


def cache_clean(path=None, runas=None, env=None, force=False):
    """
    Clean cached NPM packages.

    If no path for a specific package is provided the entire cache will be cleared.

    path
        The cache subpath to delete, or None to clear the entire cache

    runas
        The user to run NPM with

    env
        Environment variables to set when invoking npm. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.

    force
        Force cleaning of cache.  Required for npm@5 and greater

        .. versionadded:: 2016.11.6

    CLI Example:

    .. code-block:: bash

        salt '*' npm.cache_clean force=True

    """
    env = env or {}

    if runas:
        uid = salt.utils.user.get_uid(runas)
        if uid:
            env.update({"SUDO_UID": uid, "SUDO_USER": ""})

    cmd = ["npm", "cache", "clean"]
    if path:
        cmd.append(path)
    if force is True:
        cmd.append("--force")

    cmd = " ".join(cmd)
    result = __salt__["cmd.run_all"](
        cmd, cwd=None, runas=runas, env=env, python_shell=True, ignore_retcode=True
    )

    if result["retcode"] != 0:
        log.error(result["stderr"])
        return False
    return True


def cache_list(path=None, runas=None, env=None):
    """
    List NPM cached packages.

    If no path for a specific package is provided this will list all the cached packages.

    path
        The cache subpath to list, or None to list the entire cache

    runas
        The user to run NPM with

    env
        Environment variables to set when invoking npm. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.

    CLI Example:

    .. code-block:: bash

        salt '*' npm.cache_clean

    """
    env = env or {}

    if runas:
        uid = salt.utils.user.get_uid(runas)
        if uid:
            env.update({"SUDO_UID": uid, "SUDO_USER": ""})

    cmd = ["npm", "cache", "ls"]
    if path:
        cmd.append(path)

    cmd = " ".join(cmd)
    result = __salt__["cmd.run_all"](
        cmd, cwd=None, runas=runas, env=env, python_shell=True, ignore_retcode=True
    )

    if result["retcode"] != 0 and result["stderr"]:
        raise CommandExecutionError(result["stderr"])

    return result["stdout"]


def cache_path(runas=None, env=None):
    """
    List path of the NPM cache directory.

    runas
        The user to run NPM with

    env
        Environment variables to set when invoking npm. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.

    CLI Example:

    .. code-block:: bash

        salt '*' npm.cache_path

    """
    env = env or {}

    if runas:
        uid = salt.utils.user.get_uid(runas)
        if uid:
            env.update({"SUDO_UID": uid, "SUDO_USER": ""})

    cmd = "npm config get cache"

    result = __salt__["cmd.run_all"](
        cmd, cwd=None, runas=runas, env=env, python_shell=True, ignore_retcode=True
    )

    return result.get("stdout") or result.get("stderr")
