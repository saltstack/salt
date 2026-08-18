"""
Manage and query Cabal packages
===============================

.. versionadded:: 2015.8.0

"""

import logging

import salt.utils.path
from salt.exceptions import CommandExecutionError

logger = logging.getLogger(__name__)


# Function alias to make sure not to shadow built-in's
__func_alias__ = {"list_": "list"}


def __virtual__():
    """
    Only work when cabal-install is installed.
    """
    return (salt.utils.path.which("cabal") is not None) and (
        salt.utils.path.which("ghc-pkg") is not None
    )


def update(user=None, env=None):
    """
    Updates list of known packages.

    user
        The user to run cabal update with

    env
        Environment variables to set when invoking cabal. Uses the
        same ``env`` format as the :py:func:`cmd.run
        <salt.modules.cmdmod.run>` execution function.

    CLI Example:

    .. code-block:: bash

        salt '*' cabal.update

    """
    return __salt__["cmd.run_all"]("cabal update", runas=user, env=env)


def install(pkg=None, pkgs=None, user=None, install_global=False, env=None):
    """
    Install a cabal package.

    pkg
        A package name in format accepted by cabal-install. See:
        https://wiki.haskell.org/Cabal-Install

    pkgs
        A list of packages names in same format as ``pkg``

    user
        The user to run cabal install with

    install_global
        Install package globally instead of locally

    env
        Environment variables to set when invoking cabal. Uses the
        same ``env`` format as the :py:func:`cmd.run
        <salt.modules.cmdmod.run>` execution function

    CLI Example:

    .. code-block:: bash

        salt '*' cabal.install shellcheck
        salt '*' cabal.install shellcheck-0.3.5
    """

    cmd = ["cabal install"]

    if install_global:
        cmd.append("--global")

    if pkg:
        cmd.append(f'"{pkg}"')
    elif pkgs:
        cmd.append('"{}"'.format('" "'.join(pkgs)))

    result = __salt__["cmd.run_all"](" ".join(cmd), runas=user, env=env)

    if result["retcode"] != 0:
        raise CommandExecutionError(result["stderr"])

    return result


def list_(pkg=None, user=None, installed=False, env=None):
    """
    List packages matching a search string.

    pkg
        Search string for matching package names
    user
        The user to run cabal list with
    installed
        If True, only return installed packages.
    env
        Environment variables to set when invoking cabal. Uses the
        same ``env`` format as the :py:func:`cmd.run
        <salt.modules.cmdmod.run>` execution function

    CLI Example:

    .. code-block:: bash

        salt '*' cabal.list
        salt '*' cabal.list ShellCheck
    """
    cmd = ["cabal list --simple-output"]

    if installed:
        cmd.append("--installed")

    if pkg:
        cmd.append(f'"{pkg}"')

    result = __salt__["cmd.run_all"](" ".join(cmd), runas=user, env=env)

    packages = {}
    for line in result["stdout"].splitlines():
        data = line.split()
        package_name = data[0]
        package_version = data[1]
        packages[package_name] = package_version

    return packages


def uninstall(pkg, user=None, env=None):
    """
    Uninstall a cabal package.

    pkg
        The package to uninstall
    user
        The user to run ghc-pkg unregister with
    env
        Environment variables to set when invoking cabal. Uses the
        same ``env`` format as the :py:func:`cmd.run
        <salt.modules.cmdmod.run>` execution function

    CLI Example:

    .. code-block:: bash

        salt '*' cabal.uninstall ShellCheck

    """
    cmd = ["ghc-pkg unregister"]
    cmd.append(f'"{pkg}"')

    result = __salt__["cmd.run_all"](" ".join(cmd), runas=user, env=env)

    if result["retcode"] != 0:
        raise CommandExecutionError(result["stderr"])

    return result
