"""
Package support for AIX

.. important::
    If you feel that Salt should be using this module to manage filesets or
    rpm packages on a minion, and it is using a different module (or gives an
    error similar to *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import copy
import logging
import os
import pathlib

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
    result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if 0 == result["retcode"]:
        name = ""
        version_num = ""
        rpmpkg = False
        lines = result["stdout"].splitlines()
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
    else:
        raise CommandExecutionError(
            "Error occurred finding fileset/package",
            info={"errors": result["stderr"].strip()},
        )


def _is_installed_rpm(name):
    """
    Returns True if the rpm package is installed. Otherwise returns False.
    """
    cmd = ["/usr/bin/rpm", "-q", name]
    return __salt__["cmd.retcode"](cmd) == 0


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

    if "pkg.list_pkgs" in __context__ and kwargs.get("use_context", True):
        return _list_pkgs_from_context(versions_as_list)

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
    Return the current installed version of the named fileset/rpm package
    If more than one fileset/rpm package name is specified a dict of
    name/version pairs is returned.

    .. versionchanged:: 3005

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...

    """
    kwargs.pop("refresh", True)

    ret = {}
    if not names:
        return ""
    for name in names:
        # AIX packaging includes info on filesets and rpms
        version_found = ""
        cmd = "lslpp -Lq {}".format(name)
        aix_info = __salt__["cmd.run_all"](cmd, python_shell=False)
        if 0 == aix_info["retcode"]:
            aix_info_list = aix_info["stdout"].split("\n")
            log.debug(
                "Returned AIX packaging information aix_info_list %s for name %s",
                aix_info_list,
                name,
            )
            for aix_line in aix_info_list:
                if name in aix_line:
                    aix_ver_list = aix_line.split()
                    log.debug(
                        "Processing name %s with AIX packaging version information %s",
                        name,
                        aix_ver_list,
                    )
                    version_found = aix_ver_list[1]
                    if version_found:
                        log.debug(
                            "Found name %s in AIX packaging information, version %s",
                            name,
                            version_found,
                        )
                        break
        else:
            log.debug("Could not find name %s in AIX packaging information", name)

        ret[name] = version_found

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


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

    .. versionchanged:: 3005

        preference to install rpm packages are to use in the following order:
            /opt/freeware/bin/dnf
            /opt/freeware/bin/yum
            /usr/bin/yum
            /usr/bin/rpm

    .. note:
        use of rpm to install implies that rpm's dependencies must have been previously installed.
        dnf and yum automatically install rpm's dependencies as part of the install process

        Alogrithm to install filesets or rpms is as follows:
            if ends with '.rte' or '.bff'
                process as fileset
            if ends with '.rpm'
                process as rpm
            if unrecognised or no file extension
                attempt process with dnf | yum
                failure implies attempt process as fileset

        Fileset needs to be available as a single path and filename
        compound filesets are not handled and are not supported.
        An example is bos.adt.insttools which is part of bos.adt.other and is installed as follows
        /usr/bin/installp -acXYg /cecc/repos/aix72/TL4/BASE/installp/ppc/bos.adt.other bos.adt.insttools

    name
        The name of the fileset or rpm package to be installed.

    refresh
        Whether or not to update the yum database before executing.


    pkgs
        A list of filesets and/or rpm packages to install.
        Must be passed as a python list. The ``name`` parameter will be
        ignored if this option is passed.

    version
        Install a specific version of a fileset/rpm package.
        (Unused at present).

    test
        Verify that command functions correctly.

    Returns a dict containing the new fileset(s)/rpm package(s) names and versions:

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install /stage/middleware/AIX/bash-4.2-3.aix6.1.ppc.rpm
        salt '*' pkg.install /stage/middleware/AIX/bash-4.2-3.aix6.1.ppc.rpm refresh=True
        salt '*' pkg.install /stage/middleware/AIX/VIOS2211_update/tpc_4.1.1.85.bff
        salt '*' pkg.install /cecc/repos/aix72/TL3/BASE/installp/ppc/bos.rte.printers_7.2.2.0.bff
        salt '*' pkg.install /stage/middleware/AIX/Xlc/usr/sys/inst.images/xlC.rte
        salt '*' pkg.install /stage/middleware/AIX/Firefox/ppc-AIX53/Firefox.base
        salt '*' pkg.install /cecc/repos/aix72/TL3/BASE/installp/ppc/bos.net
        salt '*' pkg.install pkgs='["foo", "bar"]'
        salt '*' pkg.install libxml2
    """
    targets = salt.utils.args.split_input(pkgs) if pkgs else [name]
    if not targets:
        return {}

    if pkgs:
        log.debug("Installing these fileset(s)/rpm package(s) %s: %s", name, targets)

    # Get a list of the currently installed pkgs.
    old = list_pkgs()

    # Install the fileset (normally ends with bff or rte) or rpm package(s)
    errors = []
    for target in targets:
        filename = os.path.basename(target)
        flag_fileset = False
        flag_actual_rpm = False
        flag_try_rpm_failed = False
        cmd = ""
        out = {}
        if filename.endswith(".bff") or filename.endswith(".rte"):
            flag_fileset = True
            log.debug("install identified %s as fileset", filename)
        else:
            if filename.endswith(".rpm"):
                flag_actual_rpm = True
                log.debug("install identified %s as rpm", filename)
            else:
                log.debug("install filename %s trying install as rpm", filename)

            # assume use dnf or yum
            cmdflags = "install "
            libpathenv = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
            if pathlib.Path("/opt/freeware/bin/dnf").is_file():
                cmdflags += "--allowerasing "
                cmdexe = "/opt/freeware/bin/dnf"
                if test:
                    cmdflags += "--assumeno "
                else:
                    cmdflags += "--assumeyes "
                if refresh:
                    cmdflags += "--refresh "

                cmd = "{} {} {}".format(cmdexe, cmdflags, target)
                out = __salt__["cmd.run_all"](
                    cmd,
                    python_shell=False,
                    env=libpathenv,
                    ignore_retcode=True,
                )

            elif pathlib.Path("/usr/bin/yum").is_file():
                # check for old yum first, removed if new dnf or yum
                cmdexe = "/usr/bin/yum"
                if test:
                    cmdflags += "--assumeno "
                else:
                    cmdflags += "--assumeyes "

                cmd = "{} {} {}".format(cmdexe, cmdflags, target)
                out = __salt__["cmd.run_all"](
                    cmd,
                    python_shell=False,
                    env=libpathenv,
                    ignore_retcode=True,
                )

            elif pathlib.Path("/opt/freeware/bin/yum").is_file():
                cmdflags += "--allowerasing "
                cmdexe = "/opt/freeware/bin/yum"
                if test:
                    cmdflags += "--assumeno "
                else:
                    cmdflags += "--assumeyes "
                if refresh:
                    cmdflags += "--refresh "

                cmd = "{} {} {}".format(cmdexe, cmdflags, target)
                out = __salt__["cmd.run_all"](
                    cmd,
                    python_shell=False,
                    env=libpathenv,
                    ignore_retcode=True,
                )

            else:
                cmdexe = "/usr/bin/rpm"
                cmdflags = "-Uivh "
                if test:
                    cmdflags += "--test"

                cmd = "{} {} {}".format(cmdexe, cmdflags, target)
                out = __salt__["cmd.run_all"](cmd, python_shell=False)

        if "retcode" in out and not (0 == out["retcode"] or 100 == out["retcode"]):
            if not flag_actual_rpm:
                flag_try_rpm_failed = True
                log.debug(
                    "install tried filename %s as rpm and failed, trying as fileset",
                    filename,
                )
            else:
                errors.append(out["stderr"])
                log.debug(
                    "install error rpm path, returned result %s, resultant errors %s",
                    out,
                    errors,
                )

        if flag_fileset or flag_try_rpm_failed:
            # either identified as fileset, or failed trying install as rpm, try as fileset

            cmd = "/usr/sbin/installp -acYXg"
            if test:
                cmd += "p"
            cmd += " -d "
            dirpath = os.path.dirname(target)
            cmd += dirpath + " " + filename
            log.debug("install fileset commanda to attempt %s", cmd)
            out = __salt__["cmd.run_all"](cmd, python_shell=False)
            if 0 != out["retcode"]:
                errors.append(out["stderr"])
                log.debug(
                    "install error fileset path, returned result %s, resultant errors %s",
                    out,
                    errors,
                )

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

    .. versionchanged:: 3005

        preference to install rpm packages are to use in the following order:
            /opt/freeware/bin/dnf
            /opt/freeware/bin/yum
            /usr/bin/yum
            /usr/bin/rpm

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
        log.debug("Removing these fileset(s)/rpm package(s) %s: %s", name, targets)

    errors = []

    # Get a list of the currently installed pkgs.
    old = list_pkgs()

    # Remove the fileset or rpm package(s)
    for target in targets:
        cmd = ""
        out = {}
        try:
            named, versionpkg, rpmpkg = _check_pkg(target)
        except CommandExecutionError as exc:
            if exc.info:
                errors.append(exc.info["errors"])
            continue

        if rpmpkg:

            # assume use dnf or yum
            cmdflags = "-y remove"
            libpathenv = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
            if pathlib.Path("/opt/freeware/bin/dnf").is_file():
                cmdexe = "/opt/freeware/bin/dnf"
                cmd = "{} {} {}".format(cmdexe, cmdflags, target)
                out = __salt__["cmd.run_all"](
                    cmd,
                    python_shell=False,
                    env=libpathenv,
                    ignore_retcode=True,
                )
            elif pathlib.Path("/opt/freeware/bin/yum").is_file():
                cmdexe = "/opt/freeware/bin/yum"
                cmd = "{} {} {}".format(cmdexe, cmdflags, target)
                out = __salt__["cmd.run_all"](
                    cmd,
                    python_shell=False,
                    env=libpathenv,
                    ignore_retcode=True,
                )
            elif pathlib.Path("/usr/bin/yum").is_file():
                cmdexe = "/usr/bin/yum"
                cmd = "{} {} {}".format(cmdexe, cmdflags, target)
                out = __salt__["cmd.run_all"](
                    cmd,
                    python_shell=False,
                    env=libpathenv,
                    ignore_retcode=True,
                )
            else:
                cmdexe = "/usr/bin/rpm"
                cmdflags = "-e"
                cmd = "{} {} {}".format(cmdexe, cmdflags, target)
                out = __salt__["cmd.run_all"](cmd, python_shell=False)
        else:
            cmd = ["/usr/sbin/installp", "-u", named]
            out = __salt__["cmd.run_all"](cmd, python_shell=False)

        log.debug("result of removal command %s, returned result %s", cmd, out)

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
    Return the latest available version of the named fileset/rpm package available for
    upgrade or installation. If more than one fileset/rpm package name is
    specified, a dict of name/version pairs is returned.

    If the latest version of a given fileset/rpm package is already installed,
    an empty string will be returned for that package.

    .. versionchanged:: 3005

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...

    Note: currently only functional for rpm packages due to filesets do not have a specific location to check
        Requires yum of dnf available in order to query a repository

    This function will always return an empty string for unfound fileset/rpm package.
    """
    kwargs.pop("refresh", True)

    ret = {}
    if not names:
        return ""
    for name in names:
        # AIX packaging includes info on filesets and rpms
        version_found = ""
        libpathenv = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
        if pathlib.Path("/opt/freeware/bin/dnf").is_file():
            cmdexe = "/opt/freeware/bin/dnf"
            cmd = "{} check-update {}".format(cmdexe, name)
            available_info = __salt__["cmd.run_all"](
                cmd, python_shell=False, env=libpathenv, ignore_retcode=True
            )
        elif pathlib.Path("/opt/freeware/bin/yum").is_file():
            cmdexe = "/opt/freeware/bin/yum"
            cmd = "{} check-update {}".format(cmdexe, name)
            available_info = __salt__["cmd.run_all"](
                cmd, python_shell=False, env=libpathenv, ignore_retcode=True
            )
        elif pathlib.Path("/usr/bin/yum").is_file():
            cmdexe = "/usr/bin/yum"
            cmd = "{} check-update {}".format(cmdexe, name)
            available_info = __salt__["cmd.run_all"](
                cmd, python_shell=False, env=libpathenv, ignore_retcode=True
            )
        else:
            # no yum found implies no repository support
            available_info = None

        log.debug(
            "latest_version dnf|yum check-update command returned information %s",
            available_info,
        )
        if available_info and (
            0 == available_info["retcode"] or 100 == available_info["retcode"]
        ):
            available_output = available_info["stdout"]
            if available_output:
                available_list = available_output.split()
                flag_found = False
                for name_chk in available_list:
                    # have viable check, note .ppc or .noarch
                    if name_chk.startswith(name):
                        # check full name
                        pkg_label = name_chk.split(".")
                        if name == pkg_label[0]:
                            flag_found = True
                    elif flag_found:
                        # version comes after name found
                        version_found = name_chk
                        break

        if version_found:
            log.debug(
                "latest_version result for name %s found version %s",
                name,
                version_found,
            )
        else:
            log.debug("Could not find AIX / RPM packaging version for %s", name)

        ret[name] = version_found

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


# available_version is being deprecated
available_version = salt.utils.functools.alias_function(
    latest_version, "available_version"
)


def upgrade_available(name, **kwargs):
    """
    Check whether or not an upgrade is available for a given package

    .. versionchanged:: 3005

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>

    Note: currently only functional for rpm packages due to filesets do not have a specific location to check
        Requires yum of dnf available in order to query a repository

    """
    # AIX packaging includes info on filesets and rpms
    rpm_found = False
    version_found = ""

    libpathenv = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
    if pathlib.Path("/opt/freeware/bin/dnf").is_file():
        cmdexe = "/opt/freeware/bin/dnf"
        cmd = "{} check-update {}".format(cmdexe, name)
        available_info = __salt__["cmd.run_all"](
            cmd, python_shell=False, env=libpathenv, ignore_retcode=True
        )
    elif pathlib.Path("/opt/freeware/bin/yum").is_file():
        cmdexe = "/opt/freeware/bin/yum"
        cmd = "{} check-update {}".format(cmdexe, name)
        available_info = __salt__["cmd.run_all"](
            cmd, python_shell=False, env=libpathenv, ignore_retcode=True
        )
    elif pathlib.Path("/usr/bin/yum").is_file():
        cmdexe = "/usr/bin/yum"
        cmd = "{} check-update {}".format(cmdexe, name)
        available_info = __salt__["cmd.run_all"](
            cmd, python_shell=False, env=libpathenv, ignore_retcode=True
        )
    else:
        # no yum found implies no repository support
        return False

    log.debug(
        "upgrade_available yum check-update command %s, returned information %s",
        cmd,
        available_info,
    )
    if 0 == available_info["retcode"] or 100 == available_info["retcode"]:
        available_output = available_info["stdout"]
        if available_output:
            available_list = available_output.split()
            flag_found = False
            for name_chk in available_list:
                # have viable check, note .ppc or .noarch
                if name_chk.startswith(name):
                    # check full name
                    pkg_label = name_chk.split(".")
                    if name == pkg_label[0]:
                        flag_found = True
                elif flag_found:
                    # version comes after name found
                    version_found = name_chk
                    break

        current_version = version(name)
        log.debug(
            "upgrade_available result for name %s, found current version %s, available version %s",
            name,
            current_version,
            version_found,
        )

    if version_found:
        return current_version != version_found
    else:
        log.debug("upgrade_available information for name %s was not found", name)
        return False
