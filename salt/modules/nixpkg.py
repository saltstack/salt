"""
Work with Nix packages
======================

.. versionadded:: 3008.0

Does not require the machine to be Nixos, just have Nix installed and available
to use for the user running this command. Their profile must be located in
their home, under ``$HOME/.nix-profile/``, and the nix store, unless specially
set up, should be in ``/nix``. To easily use this with multiple users or a root
user, set up the `nix-daemon`_.

This module is compatible with the ``pkg`` state, so you can use it with
``pkg.installed``, ``pkg.removed``, ``pkg.latest``, etc.

For more information on nix, see the `nix documentation`_.

.. _`nix documentation`: https://nix.dev/manual/nix/latest/
.. _`nix-daemon`: https://nix.dev/manual/nix/latest/installation/multi-user
"""

import copy
import logging
import os
import re

import salt.utils.data
import salt.utils.functools
import salt.utils.json
import salt.utils.path
from salt.exceptions import CommandExecutionError, MinionError

logger = logging.getLogger(__name__)

__virtualname__ = "pkg"


def __virtual__():
    """
    This only works if we have access to nix
    """
    nixhome = _nix_home()
    if salt.utils.path.which(os.path.join(nixhome, "nix")) and salt.utils.path.which(
        os.path.join(nixhome, "nix-collect-garbage")
    ):
        return __virtualname__
    else:
        return (
            False,
            "The `nix` binaries required cannot be found or are not installed."
            " (`nix-collect-garbage` and `nix`)",
        )


def _nix_user():
    """
    Get the user that nix is running as.
    This is the user defined in `nixpkg.user`, `nix.user` or the user that is running the salt command.
    """
    return __opts__.get("nixpkg.user", __opts__.get("nix.user", __opts__["user"]))


def _nix_home():
    """
    Get the path to the nix profile for the nix user.
    """
    return os.path.join(os.path.expanduser(f"~{_nix_user()}"), ".nix-profile/bin/")


def _run(cmd):
    """
    Just a convenience function for ``__salt__['cmd.run_all'](cmd)``
    """
    return __salt__["cmd.run_all"](cmd, runas=_nix_user())


def _nix_profile():
    """
    nix profile command
    """
    return [os.path.join(_nix_home(), "nix"), "profile"]


def _nix_collect_garbage():
    """
    Make sure we get the right nix-collect-garbage, too.
    """
    return [os.path.join(_nix_home(), "nix-collect-garbage")]


def upgrade(*pkgs, **kwargs):
    """
    Runs an update operation on the specified packages, or all packages if none is specified.

    :type pkgs: list(str)
    :param pkgs:
        List of packages to update

    :return: The upgraded packages. Example element: ``['libxslt-1.1.0', 'libxslt-1.1.10']``
    :rtype: list(tuple(str, str))

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
        salt '*' pkg.upgrade pkgs=one,two
    """
    if salt.utils.data.is_true(kwargs.get("refresh", True)):
        refresh_db()

    logger.info("Upgrading packages: %s", pkgs)

    old = list_pkgs()
    logger.debug("Initial packages: %s", old)

    cmd = _nix_profile()
    cmd.append("upgrade")
    if pkgs:
        cmd.extend(pkgs)
    else:
        cmd.append("--all")

    out = _run(cmd)
    if out["retcode"] != 0 and out["stderr"]:
        errors = [out["stderr"]]
    else:
        errors = []

    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    logger.debug("Final packages: %s", new)

    ret = salt.utils.data.compare_dicts(old, new)
    logger.debug("Package changes: %s", ret)

    if errors:
        raise CommandExecutionError(
            "Problem encountered upgrading package(s)",
            info={"errors": errors, "changes": ret},
        )

    return ret


def list_upgrades(refresh=True, **kwargs):
    """
    List all available package upgrades.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    """
    if salt.utils.data.is_true(refresh):
        refresh_db()

    old = list_pkgs()
    ret = {}
    for pkg_name in old:
        latest = latest_version(pkg_name, refresh=False)
        if latest:
            ret[pkg_name] = latest
    return ret


def _add_source(pkg):
    return f"nixpkgs#{pkg}" if "#" not in pkg else pkg


def install(name=None, pkgs=None, **kwargs):
    """
    Installs a single or multiple packages via nix profile

    :type name: str
    :param name:
        package to install
    :type pkgs: list(str)
    :param pkgs:
        packages to install

    :return: Installed packages. Example element: ``gcc-3.3.2``
    :rtype: list(str)

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install vim
        salt '*' pkg.install pkgs='[vim, git]'
    """

    try:
        targets, pkg_type = __salt__["pkg_resource.parse_targets"](
            name, pkgs, kwargs.get("sources", {})
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if not targets:
        return {}

    logger.info("Installing packages: %s", targets)

    old = list_pkgs()
    logger.debug("Initial packages: %s", old)

    cmd = _nix_profile()
    cmd.append("add")
    cmd.extend(list(map(_add_source, targets)))

    out = _run(cmd)
    if out["retcode"] != 0 and out["stderr"]:
        errors = [out["stderr"]]
    else:
        errors = []

    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    logger.debug("Final packages: %s", new)

    ret = salt.utils.data.compare_dicts(old, new)
    logger.debug("Package changes: %s", ret)

    if errors:
        raise CommandExecutionError(
            "Problem encountered installing package(s)",
            info={"errors": errors, "changes": ret},
        )

    return ret


def _list_pkgs_from_context(versions_as_list):
    """
    Use pkg list from __context__
    """
    if versions_as_list:
        return __context__["pkg.list_pkgs"]

    ret = copy.deepcopy(__context__["pkg.list_pkgs"])
    __salt__["pkg_resource.stringify"](ret)
    return ret


def _extract_version(info):
    # Extract the version from a Nix store path.
    # Store paths have the format: /nix/store/<hash>-<pname>-<version>[-<output>]
    # The hash is base32 (no hyphens), so the first hyphen after the basename
    # separates the hash from <pname>-<version>.
    # We find the version by looking for the first segment that starts with a digit.
    for store_path in info.get("storePaths", []):
        basename = store_path.rsplit("/", 1)[-1]
        # Split off the hash (first segment before the first hyphen)
        _, _, rest = basename.partition("-")
        if not rest:
            continue
        # Find the version: first hyphen-separated part that starts with a digit
        parts = rest.split("-")
        for part in parts:
            if part and re.match(r"\d", part):
                return part
    return "unknown"


def list_pkgs(versions_as_list=False, **kwargs):
    """
    Lists installed packages.

    :param bool versions_as_list:
        returns versions as lists, not strings.
        Default: False

    :return: Packages installed or available, along with their attributes.
    :rtype: list(list(str))

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs versions_as_list=True
    """

    if kwargs.get("purge_desired", False):
        return {}

    versions_as_list = salt.utils.data.is_true(versions_as_list)

    if "pkg.list_pkgs" in __context__ and kwargs.get("use_context", True):
        return _list_pkgs_from_context(versions_as_list)

    cmd = _nix_profile()
    cmd.append("list")
    cmd.append("--json")

    package_info = salt.utils.json.loads(_run(cmd)["stdout"])
    package_info = package_info.get("elements", {})

    ret = {}
    for pkg_name, info in package_info.items():
        version = _extract_version(info)
        __salt__["pkg_resource.add_pkg"](ret, pkg_name, version)

    __salt__["pkg_resource.sort_pkglist"](ret)
    __context__["pkg.list_pkgs"] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__["pkg_resource.stringify"](ret)

    return ret


def version(*names, **kwargs):
    """
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    """
    return __salt__["pkg_resource.version"](*names, **kwargs)


def latest_version(*names, **kwargs):
    """
    Return the latest version of the named package available for upgrade or
    installation.

    Since Nix doesn't have a simple way to query the latest available version
    without performing a search, this queries ``nix search`` for each package.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> ...
    """
    refresh = salt.utils.data.is_true(kwargs.get("refresh", True))
    if refresh:
        refresh_db()

    installed = list_pkgs()
    ret = {}

    for name in names:
        cmd = [os.path.join(_nix_home(), "nix"), "search", "nixpkgs", name, "--json"]
        out = _run(cmd)
        if out["retcode"] != 0:
            ret[name] = ""
            continue

        try:
            search_results = salt.utils.json.loads(out["stdout"])
        except ValueError:
            ret[name] = ""
            continue

        # Search results are keyed by attribute path, e.g. "legacyPackages.x86_64-linux.vim"
        # Find the best match for the package name
        best_version = ""
        for attr_path, info in search_results.items():
            pkg_attr = attr_path.rsplit(".", 1)[-1] if "." in attr_path else attr_path
            if pkg_attr == name:
                best_version = info.get("version", "")
                break
        else:
            # If no exact match, take the first result
            for info in search_results.values():
                best_version = info.get("version", "")
                break

        # If the installed version matches the latest, return empty string
        if name in installed and installed[name] == best_version:
            ret[name] = ""
        else:
            ret[name] = best_version

    if len(names) == 1:
        return ret.get(names[0], "")
    return ret


# available_version is being deprecated
available_version = salt.utils.functools.alias_function(
    latest_version, "available_version"
)


def refresh_db(**kwargs):
    """
    Nix doesn't have a traditional package database to refresh,
    but this updates the flake registry / channel.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    """
    cmd = [os.path.join(_nix_home(), "nix"), "flake", "prefetch", "nixpkgs"]
    out = _run(cmd)
    return out["retcode"] == 0


def uninstall(*pkgs):
    """
    Erases a package from the current nix profile.
    Nix uninstalls work differently than other package managers, and the symlinks in the profile are removed,
    while the actual package remains.
    There is also a ``pkg.purge`` function, to clear the package cache of unused packages.

    :type pkgs: list(str)
    :param pkgs:
        List, single package to uninstall

    :return: Packages that have been uninstalled
    :rtype: list(str)

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.uninstall vim
        salt '*' pkg.uninstall vim git
    """

    return remove(pkgs=pkgs)


def remove(name=None, pkgs=None, **kwargs):
    """
    Removes packages with ``nix profile remove``.

    :param str name:
        Package to remove

    :param list pkgs:
        List of packages to remove

    :return: A dict containing the changes

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove vim
        salt '*' pkg.remove pkgs='[vim, git]'
    """
    try:
        pkg_params = __salt__["pkg_resource.parse_targets"](name, pkgs, **kwargs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    logger.debug("Initial packages: %s", old)

    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    logger.info("Removing packages: %s", targets)

    cmd = _nix_profile()
    cmd.append("remove")
    cmd.extend(list(targets))

    out = _run(cmd)
    if out["retcode"] != 0 and out["stderr"]:
        errors = [out["stderr"]]
    else:
        errors = []

    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    logger.debug("Final packages: %s", new)

    ret = salt.utils.data.compare_dicts(old, new)
    logger.debug("Package changes: %s", ret)

    if errors:
        raise CommandExecutionError(
            "Problem encountered removing package(s)",
            info={"errors": errors, "changes": ret},
        )

    return ret


def collect_garbage():
    """
    Completely removed all currently 'uninstalled' packages in the nix store.

    Tells the user how many store paths were removed and how much space was freed.

    :return: How much space was freed and how many derivations were removed
    :rtype: str

    .. warning::
       This is a destructive action on the nix store.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.collect_garbage
    """
    cmd = _nix_collect_garbage()
    cmd.append("--delete-old")

    out = _run(cmd)

    return out["stdout"].splitlines()
