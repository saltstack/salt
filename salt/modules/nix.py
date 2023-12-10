"""
Work with Nix packages
======================

.. versionadded:: 2017.7.0

Does not require the machine to be Nixos, just have Nix installed and available
to use for the user running this command. Their profile must be located in
their home, under ``$HOME/.nix-profile/``, and the nix store, unless specially
set up, should be in ``/nix``. To easily use this with multiple users or a root
user, set up the `nix-daemon`_.

This module exposes most of the common nix operations. Currently not meant to be run as a ``pkg`` module, but explicitly as ``nix.*``.

For more information on nix, see the `nix documentation`_.

.. _`nix documentation`: https://nixos.org/nix/manual/
.. _`nix-daemon`: https://nixos.org/nix/manual/#ssec-multi-user
"""


import itertools
import logging
import os

import salt.utils.itertools
import salt.utils.path

logger = logging.getLogger(__name__)


def __virtual__():
    """
    This only works if we have access to nix-env
    """
    nixhome = os.path.join(
        os.path.expanduser("~{}".format(__opts__["user"])), ".nix-profile/bin/"
    )
    if salt.utils.path.which(
        os.path.join(nixhome, "nix-env")
    ) and salt.utils.path.which(os.path.join(nixhome, "nix-collect-garbage")):
        return True
    else:
        return (
            False,
            "The `nix` binaries required cannot be found or are not installed."
            " (`nix-store` and `nix-env`)",
        )


def _run(cmd):
    """
    Just a convenience function for ``__salt__['cmd.run_all'](cmd)``
    """
    return __salt__["cmd.run_all"](
        cmd, env={"HOME": os.path.expanduser("~{}".format(__opts__["user"]))}
    )


def _nix_env():
    """
    nix-env with quiet option. By default, nix is extremely verbose and prints the build log of every package to stderr. This tells nix to
    only show changes.
    """
    nixhome = os.path.join(
        os.path.expanduser("~{}".format(__opts__["user"])), ".nix-profile/bin/"
    )
    return [os.path.join(nixhome, "nix-env")]


def _nix_collect_garbage():
    """
    Make sure we get the right nix-store, too.
    """
    nixhome = os.path.join(
        os.path.expanduser("~{}".format(__opts__["user"])), ".nix-profile/bin/"
    )
    return [os.path.join(nixhome, "nix-collect-garbage")]


def _quietnix():
    """
    nix-env with quiet option. By default, nix is extremely verbose and prints the build log of every package to stderr. This tells nix to
    only show changes.
    """
    p = _nix_env()
    p.append("--no-build-output")
    return p


def _zip_flatten(x, ys):
    """
    intersperse x into ys, with an extra element at the beginning.
    """
    return itertools.chain.from_iterable(zip(itertools.repeat(x), ys))


def _output_format(out, operation):
    """
    gets a list of all the packages that were affected by ``operation``, splits it up (there can be multiple packages on a line), and then
    flattens that list. We make it to a list for easier parsing.
    """
    return [s.split()[1:] for s in out if s.startswith(operation)]


def _format_upgrade(s):
    """
    split the ``upgrade`` responses on ``' to '``
    """
    return s.split(" to ")


def _strip_quotes(s):
    """
    nix likes to quote itself in a backtick and a single quote. This just strips those.
    """
    return s.strip("'`")


def upgrade(*pkgs):
    """
    Runs an update operation on the specified packages, or all packages if none is specified.

    :type pkgs: list(str)
    :param pkgs:
        List of packages to update

    :return: The upgraded packages. Example element: ``['libxslt-1.1.0', 'libxslt-1.1.10']``
    :rtype: list(tuple(str, str))

    .. code-block:: bash

        salt '*' nix.update
        salt '*' nix.update pkgs=one,two
    """
    cmd = _quietnix()
    cmd.append("--upgrade")
    cmd.extend(pkgs)

    out = _run(cmd)

    upgrades = [
        _format_upgrade(s.split(maxsplit=1)[1])
        for s in out["stderr"].splitlines()
        if s.startswith("upgrading")
    ]

    return [[_strip_quotes(s_) for s_ in s] for s in upgrades]


def install(*pkgs, **kwargs):
    """
    Installs a single or multiple packages via nix

    :type pkgs: list(str)
    :param pkgs:
        packages to update
    :param bool attributes:
        Pass the list of packages or single package as attribues, not package names.
        default: False

    :return: Installed packages. Example element: ``gcc-3.3.2``
    :rtype: list(str)

    .. code-block:: bash

        salt '*' nix.install package [package2 ...]
        salt '*' nix.install attributes=True attr.name [attr.name2 ...]
    """

    attributes = kwargs.get("attributes", False)

    if not pkgs:
        return "Plese specify a package or packages to upgrade"

    cmd = _quietnix()
    cmd.append("--install")

    if kwargs.get("attributes", False):
        cmd.extend(_zip_flatten("--attr", pkgs))
    else:
        cmd.extend(pkgs)

    out = _run(cmd)

    installs = list(
        itertools.chain.from_iterable(
            [
                s.split()[1:]
                for s in out["stderr"].splitlines()
                if s.startswith("installing")
            ]
        )
    )

    return [_strip_quotes(s) for s in installs]


def list_pkgs(installed=True, attributes=True):
    """
    Lists installed packages. Due to how nix works, it defaults to just doing a ``nix-env -q``.

    :param bool installed:
        list only installed packages. This can be a very long list (12,000+ elements), so caution is advised.
        Default: True

    :param bool attributes:
        show the attributes of the packages when listing all packages.
        Default: True

    :return: Packages installed or available, along with their attributes.
    :rtype: list(list(str))

    .. code-block:: bash

        salt '*' nix.list_pkgs
        salt '*' nix.list_pkgs installed=False
    """

    # We don't use -Q here, as it obfuscates the attribute names on full package listings.
    cmd = _nix_env()
    cmd.append("--query")

    if installed:
        # explicitly add this option for consistency, it's normally the default
        cmd.append("--installed")
    if not installed:
        cmd.append("--available")
        # We only show attributes if we're not doing an `installed` run.
        # The output of `nix-env -qaP` and `nix-env -qP` are vastly different:
        #    `nix-env -qaP` returns a list such as 'attr.path  name-version'
        #    `nix-env -qP` returns a list of 'installOrder  name-version'
        # Install order is useful to unambiguously select packages on a single
        # machine, but on more than one it can be a bad thing to specify.
        if attributes:
            cmd.append("--attr-path")

    out = _run(cmd)

    return [s.split() for s in salt.utils.itertools.split(out["stdout"], "\n")]


def uninstall(*pkgs):
    """
    Erases a package from the current nix profile. Nix uninstalls work differently than other package managers, and the symlinks in the
    profile are removed, while the actual package remains. There is also a ``nix.purge`` function, to clear the package cache of unused
    packages.

    :type pkgs: list(str)
    :param pkgs:
        List, single package to uninstall

    :return: Packages that have been uninstalled
    :rtype: list(str)

    .. code-block:: bash

        salt '*' nix.uninstall pkg1 [pkg2 ...]
    """

    cmd = _quietnix()
    cmd.append("--uninstall")
    cmd.extend(pkgs)

    out = _run(cmd)

    fmtout = out["stderr"].splitlines(), "uninstalling"

    return [
        _strip_quotes(s.split()[1])
        for s in out["stderr"].splitlines()
        if s.startswith("uninstalling")
    ]


def collect_garbage():
    """
    Completely removed all currently 'uninstalled' packages in the nix store.

    Tells the user how many store paths were removed and how much space was freed.

    :return: How much space was freed and how many derivations were removed
    :rtype: str

    .. warning::
       This is a destructive action on the nix store.

    .. code-block:: bash

        salt '*' nix.collect_garbage
    """
    cmd = _nix_collect_garbage()
    cmd.append("--delete-old")

    out = _run(cmd)

    return out["stdout"].splitlines()
