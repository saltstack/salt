"""
Package support for OpenBSD

.. note::

    The package repository is configured on each host using ``/etc/installurl``
    from OpenBSD 6.1 onwards. Earlier releases relied on ``/etc/pkg.conf``.

.. versionchanged:: 2016.3.5

    Package versions on OpenBSD are not normally specified explicitly; instead
    packages may be available in multiple *flavors*, and *branches* which are
    specified by the format of the package name. This module allows you to use
    the same formatting as ``pkg_add(1)``, and will select the empty flavor and
    default branch by default. Examples:

    .. code-block:: yaml

      - rsync
      - vim--no_x11
      - ruby%2.3

"""

import copy
import logging
import re

import salt.utils.data
import salt.utils.versions
from salt.exceptions import CommandExecutionError, MinionError

log = logging.getLogger(__name__)

# FIXME: replace guesswork with `pkg_info -z` to correctly identify package
#        flavors and branches
__PKG_RE = re.compile("^((?:[^-]+|-(?![0-9]))+)-([0-9][^-]*)(?:-(.*))?$")

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Set the virtual pkg module if the os is OpenBSD
    """
    if __grains__["os"] == "OpenBSD":
        return __virtualname__
    return (
        False,
        "The openbsdpkg execution module cannot be loaded: "
        "only available on OpenBSD systems.",
    )


def _list_pkgs_from_context(versions_as_list):
    """
    Use pkg list from __context__
    """
    if versions_as_list:
        return __context__["pkg.list_pkgs"]
    else:
        ret = copy.deepcopy(__context__["pkg.list_pkgs"])
        __salt__["pkg_resource.stringify"](ret)
        return ret


def list_pkgs(versions_as_list=False, **kwargs):
    """
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    """
    versions_as_list = salt.utils.data.is_true(versions_as_list)
    # not yet implemented or not applicable
    if any(
        [salt.utils.data.is_true(kwargs.get(x)) for x in ("removed", "purge_desired")]
    ):
        return {}

    if "pkg.list_pkgs" in __context__ and kwargs.get("use_context", True):
        return _list_pkgs_from_context(versions_as_list)

    ret = {}
    cmd = "pkg_info -q -a"
    out = __salt__["cmd.run_stdout"](cmd, output_loglevel="trace")
    for line in out.splitlines():
        try:
            pkgname, pkgver, flavor = __PKG_RE.match(line).groups()
        except AttributeError:
            continue
        pkgname += "--{}".format(flavor) if flavor else ""
        __salt__["pkg_resource.add_pkg"](ret, pkgname, pkgver)

    __salt__["pkg_resource.sort_pkglist"](ret)
    __context__["pkg.list_pkgs"] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__["pkg_resource.stringify"](ret)
    return ret


def latest_version(*names, **kwargs):
    """
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
    """
    kwargs.pop("refresh", True)

    pkgs = list_pkgs()
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ""

        # Query the repository for the package name
        cmd = "pkg_info -Q {}".format(name)
        out = __salt__["cmd.run_stdout"](
            cmd, python_shell=False, output_loglevel="trace"
        )

        # Since we can only query instead of request the specific package
        # we'll have to go through the returned list and find what we
        # were looking for.
        # Keep in mind the match may be flavored.
        for line in out.splitlines():
            try:
                pkgname, pkgver, flavor = __PKG_RE.match(line).groups()
            except AttributeError:
                continue

            match = re.match(r".*\(installed\)$", pkgver)
            if match:
                # Package is explicitly marked as installed already,
                # so skip any further comparison and move on to the
                # next package to compare (if provided).
                break

            # First check if we need to look for flavors before
            # looking at unflavored packages.
            if "{}--{}".format(pkgname, flavor) == name:
                pkgname += "--{}".format(flavor)
            elif pkgname == name:
                pass
            else:
                # No match just move on.
                continue

            cur = pkgs.get(pkgname, "")
            if not cur or salt.utils.versions.compare(ver1=cur, oper="<", ver2=pkgver):
                ret[pkgname] = pkgver

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
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


def install(name=None, pkgs=None, sources=None, **kwargs):
    """
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example, Install one package:

    .. code-block:: bash

        salt '*' pkg.install <package name>

    CLI Example, Install more than one package:

    .. code-block:: bash

        salt '*' pkg.install pkgs='["<package name>", "<package name>"]'

    CLI Example, Install more than one package from a alternate source (e.g.
    salt file-server, HTTP, FTP, local filesystem):

    .. code-block:: bash

        salt '*' pkg.install sources='[{"<pkg name>": "salt://pkgs/<pkg filename>"}]'
    """
    try:
        pkg_params, pkg_type = __salt__["pkg_resource.parse_targets"](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    old = list_pkgs()
    errors = []
    for pkg in pkg_params:
        # A special case for OpenBSD package "branches" is also required in
        # salt/states/pkg.py
        if pkg_type == "repository":
            stem, branch = (pkg.split("%") + [""])[:2]
            base, flavor = (stem.split("--") + [""])[:2]
            pkg = "{}--{}%{}".format(base, flavor, branch)
        cmd = "pkg_add -x -I {}".format(pkg)
        out = __salt__["cmd.run_all"](cmd, python_shell=False, output_loglevel="trace")
        if out["retcode"] != 0 and out["stderr"]:
            errors.append(out["stderr"])

    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            "Problem encountered installing package(s)",
            info={"errors": errors, "changes": ret},
        )

    return ret


def remove(name=None, pkgs=None, purge=False, **kwargs):
    """
    Remove a single package with pkg_delete

    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    """
    try:
        pkg_params = [
            x.split("--")[0]
            for x in __salt__["pkg_resource.parse_targets"](name, pkgs)[0]
        ]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    cmd = ["pkg_delete", "-Ix", "-Ddependencies"]

    if purge:
        cmd.append("-cqq")

    cmd.extend(targets)

    out = __salt__["cmd.run_all"](cmd, python_shell=False, output_loglevel="trace")
    if out["retcode"] != 0 and out["stderr"]:
        errors = [out["stderr"]]
    else:
        errors = []

    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            "Problem encountered removing package(s)",
            info={"errors": errors, "changes": ret},
        )

    return ret


def purge(name=None, pkgs=None, **kwargs):
    """
    Remove a package and extra configuration files.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    """
    return remove(name=name, pkgs=pkgs, purge=True)


def upgrade_available(name, **kwargs):
    """
    Check whether or not an upgrade is available for a given package

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    """
    return latest_version(name) != ""


def upgrade(name=None, pkgs=None, **kwargs):
    """
    Run a full package upgrade (``pkg_add -u``), or upgrade a specific package
    if ``name`` or ``pkgs`` is provided.
    ``name`` is ignored when ``pkgs`` is specified.

    Returns a dictionary containing the changes:

    .. versionadded:: 2019.2.0

    .. code-block:: python

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
        salt '*' pkg.upgrade python%2.7
    """
    old = list_pkgs()

    cmd = ["pkg_add", "-Ix", "-u"]

    if kwargs.get("noop", False):
        cmd.append("-n")

    if pkgs:
        cmd.extend(pkgs)
    elif name:
        cmd.append(name)

    # Now run the upgrade, compare the list of installed packages before and
    # after and we have all the info we need.
    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if result["retcode"] != 0:
        raise CommandExecutionError(
            "Problem encountered upgrading packages",
            info={"changes": ret, "result": result},
        )

    return ret
