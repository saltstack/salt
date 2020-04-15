# -*- coding: utf-8 -*-
"""
Package support for AIX

.. important::
    If you feel that Salt should be using this module to manage filesets or
    rpm packages on a minion, and it is using a different module (or gives an
    error similar to *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import copy
import logging
import os

# Import salt libs
import salt.utils.data
import salt.utils.functools
import salt.utils.path
import salt.utils.pkg
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Set the virtual pkg module if the os is AIX
    """
    if __grains__["os_family"] == "AIX":
        return __virtualname__
    return (False, "Did not load AIX module on non-AIX OS.")


def _check_pkg(target):
    """
    Return name, version and if rpm package for specified target
    """
    ret = {}
    cmd = ["/usr/bin/lslpp", "-Lc", target]
    lines = __salt__["cmd.run"](cmd, python_shell=False).splitlines()

    name = ""
    version_num = ""
    rpmpkg = False
    for line in lines:
        if line.startswith("#"):
            continue

        comps = line.split(":")
        if len(comps) < 7:
            raise CommandExecutionError(
                "Error occurred finding fileset/package",
                info={"errors": comps[1].strip()},
            )

        # handle first matching line
        if "R" in comps[6]:
            name = comps[0]
            rpmpkg = True
        else:
            name = comps[1]  # use fileset rather than rpm package

        version_num = comps[2]
        break

    return name, version_num, rpmpkg


def _is_installed_rpm(name):
    """
    Returns True if the rpm package is installed. Otherwise returns False.
    """
    cmd = ["/usr/bin/rpm", "-q", name]
    return __salt__["cmd.retcode"](cmd) == 0


def list_pkgs(versions_as_list=False, **kwargs):
    """
    List the filesets/rpm packages currently installed as a dict:

    .. code-block:: python

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    """
    ret = {}
    versions_as_list = salt.utils.data.is_true(versions_as_list)
    # not yet implemented or not applicable
    if any(
        [salt.utils.data.is_true(kwargs.get(x)) for x in ("removed", "purge_desired")]
    ):
        return ret

    if "pkg.list_pkgs" in __context__:
        if versions_as_list:
            return __context__["pkg.list_pkgs"]
        else:
            ret = copy.deepcopy(__context__["pkg.list_pkgs"])
            __salt__["pkg_resource.stringify"](ret)
            return ret

    # cmd returns information colon delimited in a single linei, format
    #   Package Name:Fileset:Level:State:PTF Id:Fix State:Type:Description:
    #       Destination Dir.:Uninstaller:Message Catalog:Message Set:
    #       Message Number:Parent:Automatic:EFIX Locked:Install Path:Build Date
    # Example:
    #   xcursor:xcursor-1.1.7-3:1.1.7-3: : :C:R:X Cursor library: :\
    #       /bin/rpm -e xcursor: : : : :0: :(none):Mon May  8 15:18:35 CDT 2017
    #   bos:bos.rte.libcur:7.1.5.0: : :C:F:libcurses Library: : : : : : :0:0:/:1731
    #
    # where Type codes: F -- Installp Fileset, P -- Product, C -- Component,
    #                   T -- Feature, R -- RPM Package
    cmd = "/usr/bin/lslpp -Lc"
    lines = __salt__["cmd.run"](cmd, python_shell=False).splitlines()

    for line in lines:
        if line.startswith("#"):
            continue

        comps = line.split(":")
        if len(comps) < 7:
            continue

        if "R" in comps[6]:
            name = comps[0]
        else:
            name = comps[1]  # use fileset rather than rpm package

        version_num = comps[2]
        __salt__["pkg_resource.add_pkg"](ret, name, version_num)

    __salt__["pkg_resource.sort_pkglist"](ret)
    __context__["pkg.list_pkgs"] = copy.deepcopy(ret)

    if not versions_as_list:
        __salt__["pkg_resource.stringify"](ret)

    return ret


def version(*names, **kwargs):
    """
    Common interface for obtaining the version of installed fileset/rpm package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version vim
        salt '*' pkg.version foo bar baz
    """
    return __salt__["pkg_resource.version"](*names, **kwargs)


def _is_installed(name, **kwargs):
    """
    Returns True if the fileset/rpm package is installed. Otherwise returns False.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg._is_installed bash
    """
    cmd = ["/usr/bin/lslpp", "-Lc", name]
    return __salt__["cmd.retcode"](cmd) == 0


def install(name=None, refresh=False, pkgs=None, version=None, test=False, **kwargs):
    """
    Install the named fileset(s)/rpm package(s).

    name
        The name of the fileset or rpm package to be installed.

    refresh
        Whether or not to update the yum database before executing.


    Multiple Package Installation Options:

    pkgs
        A list of filesets and/or rpm packages to install.
        Must be passed as a python list. The ``name`` parameter will be
        ignored if this option is passed.

    version
        Install a specific version of a fileset/rpm package.
        (Unused at present).

    test
        Verify that command functions correctly:

    Returns a dict containing the new fileset(s)/rpm package(s) names and versions:

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install /stage/middleware/AIX/bash-4.2-3.aix6.1.ppc.rpm
        salt '*' pkg.install /stage/middleware/AIX/bash-4.2-3.aix6.1.ppc.rpm refresh=True
        salt '*' pkg.install /stage/middleware/AIX/VIOS2211_update/tpc_4.1.1.85.bff
        salt '*' pkg.install /stage/middleware/AIX/Xlc/usr/sys/inst.images/xlC.rte
        salt '*' pkg.install /stage/middleware/AIX/Firefox/ppc-AIX53/Firefox.base
        salt '*' pkg.install pkgs='["foo", "bar"]'
    """
    targets = salt.utils.args.split_input(pkgs) if pkgs else [name]
    if not targets:
        return {}

    if pkgs:
        log.debug(
            "Removing these fileset(s)/rpm package(s) {0}: {1}".format(name, targets)
        )

    # Get a list of the currently installed pkgs.
    old = list_pkgs()

    # Install the fileset or rpm package(s)
    errors = []
    for target in targets:
        filename = os.path.basename(target)
        if filename.endswith(".rpm"):
            if _is_installed_rpm(filename.split(".aix")[0]):
                continue

            cmdflags = " -Uivh "
            if test:
                cmdflags += " --test"

            cmd = ["/usr/bin/rpm", cmdflags, target]
            out = __salt__["cmd.run_all"](cmd, output_loglevel="trace")
        else:
            if _is_installed(target):
                continue

            cmd = "/usr/sbin/installp -acYXg"
            if test:
                cmd += "p"
            cmd += " -d "
            dirpath = os.path.dirname(target)
            cmd += dirpath + " " + filename
            out = __salt__["cmd.run_all"](cmd, output_loglevel="trace")

        if 0 != out["retcode"]:
            errors.append(out["stderr"])

    # Get a list of the packages after the uninstall
    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            "Problems encountered installing filesets(s)/package(s)",
            info={"changes": ret, "errors": errors},
        )

    # No error occurred
    if test:
        return "Test succeeded."

    return ret


def remove(name=None, pkgs=None, **kwargs):
    """
    Remove specified fileset(s)/rpm package(s).

    name
        The name of the fileset or rpm package to be deleted.


    Multiple Package Options:

    pkgs
        A list of filesets and/or rpm packages to delete.
        Must be passed as a python list. The ``name`` parameter will be
        ignored if this option is passed.


    Returns a list containing the removed packages.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <fileset/rpm package name>
        salt '*' pkg.remove tcsh
        salt '*' pkg.remove xlC.rte
        salt '*' pkg.remove Firefox.base.adt
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    """
    targets = salt.utils.args.split_input(pkgs) if pkgs else [name]
    if not targets:
        return {}

    if pkgs:
        log.debug(
            "Removing these fileset(s)/rpm package(s) {0}: {1}".format(name, targets)
        )

    errors = []

    # Get a list of the currently installed pkgs.
    old = list_pkgs()

    # Remove the fileset or rpm package(s)
    for target in targets:
        try:
            named, versionpkg, rpmpkg = _check_pkg(target)
        except CommandExecutionError as exc:
            if exc.info:
                errors.append(exc.info["errors"])
            continue

        if rpmpkg:
            cmd = ["/usr/bin/rpm", "-e", named]
            out = __salt__["cmd.run_all"](cmd, output_loglevel="trace")
        else:
            cmd = ["/usr/sbin/installp", "-u", named]
            out = __salt__["cmd.run_all"](cmd, output_loglevel="trace")

    # Get a list of the packages after the uninstall
    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            "Problems encountered removing filesets(s)/package(s)",
            info={"changes": ret, "errors": errors},
        )

    return ret


def latest_version(*names, **kwargs):
    """
    Return the latest version of the named fileset/rpm package available for
    upgrade or installation. If more than one fileset/rpm package name is
    specified, a dict of name/version pairs is returned.

    If the latest version of a given fileset/rpm package is already installed,
    an empty string will be returned for that package.


    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...

    NOTE: Repositories are not presently supported for AIX.
    This function will always return an empty string for a given
    fileset/rpm package.
    """
    kwargs.pop("refresh", True)

    ret = {}
    if not names:
        return ""
    for name in names:
        ret[name] = ""

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


# available_version is being deprecated
available_version = salt.utils.functools.alias_function(
    latest_version, "available_version"
)


def upgrade_available(name):
    """
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    """
    return latest_version(name) != ""
