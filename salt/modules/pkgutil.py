# -*- coding: utf-8 -*-
"""
Pkgutil support for Solaris

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import copy

# Import salt libs
import salt.utils.data
import salt.utils.functools
import salt.utils.pkg
import salt.utils.versions
from salt.exceptions import CommandExecutionError, MinionError
from salt.ext import six

# Define the module's virtual name
__virtualname__ = "pkgutil"


def __virtual__():
    """
    Set the virtual pkg module if the os is Solaris
    """
    if __grains__["os_family"] == "Solaris":
        return __virtualname__
    return (
        False,
        "The pkgutil execution module cannot be loaded: "
        "only available on Solaris systems.",
    )


def refresh_db():
    """
    Updates the pkgutil repo database (pkgutil -U)

    CLI Example:

    .. code-block:: bash

        salt '*' pkgutil.refresh_db
    """
    # Remove rtag file to keep multiple refreshes from happening in pkg states
    salt.utils.pkg.clear_rtag(__opts__)
    return __salt__["cmd.retcode"]("/opt/csw/bin/pkgutil -U") == 0


def upgrade_available(name):
    """
    Check if there is an upgrade available for a certain package

    CLI Example:

    .. code-block:: bash

        salt '*' pkgutil.upgrade_available CSWpython
    """
    version_num = None
    cmd = "/opt/csw/bin/pkgutil -c --parse --single {0}".format(name)
    out = __salt__["cmd.run_stdout"](cmd)
    if out:
        version_num = out.split()[2].strip()
    if version_num:
        if version_num == "SAME":
            return ""
        else:
            return version_num
    return ""


def list_upgrades(refresh=True, **kwargs):  # pylint: disable=W0613
    """
    List all available package upgrades on this system

    CLI Example:

    .. code-block:: bash

        salt '*' pkgutil.list_upgrades
    """
    if salt.utils.data.is_true(refresh):
        refresh_db()
    upgrades = {}
    lines = __salt__["cmd.run_stdout"]("/opt/csw/bin/pkgutil -A --parse").splitlines()
    for line in lines:
        comps = line.split("\t")
        if comps[2] == "SAME":
            continue
        if comps[2] == "not installed":
            continue
        upgrades[comps[0]] = comps[1]
    return upgrades


def upgrade(refresh=True):
    """
    Upgrade all of the packages to the latest available version.

    Returns a dict containing the changes::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkgutil.upgrade
    """
    if salt.utils.data.is_true(refresh):
        refresh_db()

    old = list_pkgs()

    # Install or upgrade the package
    # If package is already installed
    cmd = "/opt/csw/bin/pkgutil -yu"
    __salt__["cmd.run_all"](cmd)
    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    return salt.utils.data.compare_dicts(old, new)


def list_pkgs(versions_as_list=False, **kwargs):
    """
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs versions_as_list=True
    """
    versions_as_list = salt.utils.data.is_true(versions_as_list)
    # 'removed' not yet implemented or not applicable
    if salt.utils.data.is_true(kwargs.get("removed")):
        return {}

    if "pkg.list_pkgs" in __context__:
        if versions_as_list:
            return __context__["pkg.list_pkgs"]
        else:
            ret = copy.deepcopy(__context__["pkg.list_pkgs"])
            __salt__["pkg_resource.stringify"](ret)
            return ret

    ret = {}
    cmd = "/usr/bin/pkginfo -x"

    # Package information returned two lines per package. On even-offset
    # lines, the package name is in the first column. On odd-offset lines, the
    # package version is in the second column.
    lines = __salt__["cmd.run"](cmd).splitlines()
    for index, line in enumerate(lines):
        if index % 2 == 0:
            name = line.split()[0].strip()
        if index % 2 == 1:
            version_num = line.split()[1].strip()
            __salt__["pkg_resource.add_pkg"](ret, name, version_num)

    __salt__["pkg_resource.sort_pkglist"](ret)
    __context__["pkg.list_pkgs"] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__["pkg_resource.stringify"](ret)
    return ret


def version(*names, **kwargs):
    """
    Returns a version if the package is installed, else returns an empty string

    CLI Example:

    .. code-block:: bash

        salt '*' pkgutil.version CSWpython
    """
    return __salt__["pkg_resource.version"](*names, **kwargs)


def latest_version(*names, **kwargs):
    """
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkgutil.latest_version CSWpython
        salt '*' pkgutil.latest_version <package1> <package2> <package3> ...
    """
    refresh = salt.utils.data.is_true(kwargs.pop("refresh", True))

    if not names:
        return ""
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ""

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db()

    pkgs = list_pkgs()
    cmd = "/opt/csw/bin/pkgutil -a --parse {0}".format(" ".join(names))
    output = __salt__["cmd.run_all"](cmd).get("stdout", "").splitlines()
    for line in output:
        try:
            name, version_rev = line.split()[1:3]
        except ValueError:
            continue

        if name in names:
            cver = pkgs.get(name, "")
            nver = version_rev.split(",")[0]
            if not cver or salt.utils.versions.compare(ver1=cver, oper="<", ver2=nver):
                # Remove revision for version comparison
                ret[name] = version_rev

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


# available_version is being deprecated
available_version = salt.utils.functools.alias_function(
    latest_version, "available_version"
)


def install(name=None, refresh=False, version=None, pkgs=None, **kwargs):
    """
    Install packages using the pkgutil tool.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install <package_name>
        salt '*' pkg.install SMClgcc346


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from OpenCSW. Must be passed as a python
        list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    """
    if refresh:
        refresh_db()

    try:
        # Ignore 'sources' argument
        pkg_params = __salt__["pkg_resource.parse_targets"](name, pkgs, **kwargs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    if pkgs is None and version and len(pkg_params) == 1:
        pkg_params = {name: version}
    targets = []
    for param, pkgver in six.iteritems(pkg_params):
        if pkgver is None:
            targets.append(param)
        else:
            targets.append("{0}-{1}".format(param, pkgver))

    cmd = "/opt/csw/bin/pkgutil -yu {0}".format(" ".join(targets))
    old = list_pkgs()
    __salt__["cmd.run_all"](cmd)
    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    return salt.utils.data.compare_dicts(old, new)


def remove(name=None, pkgs=None, **kwargs):
    """
    Remove a package and all its dependencies which are not in use by other
    packages.

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

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    """
    try:
        pkg_params = __salt__["pkg_resource.parse_targets"](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    cmd = "/opt/csw/bin/pkgutil -yr {0}".format(" ".join(targets))
    __salt__["cmd.run_all"](cmd)
    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    return salt.utils.data.compare_dicts(old, new)


def purge(name=None, pkgs=None, **kwargs):
    """
    Package purges are not supported, this function is identical to
    ``remove()``.

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
    return remove(name=name, pkgs=pkgs)
