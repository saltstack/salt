"""
Support for Opkg

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.

.. versionadded:: 2016.3.0

.. note::

    For version comparison support on opkg < 0.3.4, the ``opkg-utils`` package
    must be installed.

"""

import copy
import errno
import logging
import os
import pathlib
import re
import shlex

import salt.utils.args
import salt.utils.data
import salt.utils.files
import salt.utils.itertools
import salt.utils.path
import salt.utils.pkg
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import CommandExecutionError, MinionError, SaltInvocationError

REPO_REGEXP = r'^#?\s*(src|src/gz)\s+([^\s<>]+|"[^<>]+")\s+[^\s<>]+'
OPKG_CONFDIR = "/etc/opkg"
ATTR_MAP = {
    "Architecture": "arch",
    "Homepage": "url",
    "Installed-Time": "install_date_time_t",
    "Maintainer": "packager",
    "Package": "name",
    "Section": "group",
}

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pkg"

NILRT_RESTARTCHECK_STATE_PATH = "/var/lib/salt/restartcheck_state"


def _get_nisysapi_conf_d_path():
    return "/usr/lib/{}/nisysapi/conf.d/experts/".format(
        "arm-linux-gnueabi"
        if "arm" in __grains__.get("cpuarch")
        else "x86_64-linux-gnu"
    )


def _update_nilrt_restart_state():
    """
    NILRT systems determine whether to reboot after various package operations
    including but not limited to kernel module installs/removals by checking
    specific file md5sums & timestamps. These files are touched/modified by
    the post-install/post-remove functions of their respective packages.

    The opkg module uses this function to store/update those file timestamps
    and checksums to be used later by the restartcheck module.

    """
    # TODO: This stat & md5sum should be replaced with _fingerprint_file call -W. Werner, 2020-08-18
    uname = __salt__["cmd.run_stdout"]("uname -r")
    __salt__["cmd.shell"](
        "stat -c %Y /lib/modules/{}/modules.dep >{}/modules.dep.timestamp".format(
            uname, NILRT_RESTARTCHECK_STATE_PATH
        )
    )
    __salt__["cmd.shell"](
        "md5sum /lib/modules/{}/modules.dep >{}/modules.dep.md5sum".format(
            uname, NILRT_RESTARTCHECK_STATE_PATH
        )
    )

    # We can't assume nisysapi.ini always exists like modules.dep
    nisysapi_path = "/usr/local/natinst/share/nisysapi.ini"
    if os.path.exists(nisysapi_path):
        # TODO: This stat & md5sum should be replaced with _fingerprint_file call -W. Werner, 2020-08-18
        __salt__["cmd.shell"](
            "stat -c %Y {} >{}/nisysapi.ini.timestamp".format(
                nisysapi_path, NILRT_RESTARTCHECK_STATE_PATH
            )
        )
        __salt__["cmd.shell"](
            "md5sum {} >{}/nisysapi.ini.md5sum".format(
                nisysapi_path, NILRT_RESTARTCHECK_STATE_PATH
            )
        )

    # Expert plugin files get added to a conf.d dir, so keep track of the total
    # no. of files, their timestamps and content hashes
    nisysapi_conf_d_path = _get_nisysapi_conf_d_path()

    if os.path.exists(nisysapi_conf_d_path):
        with salt.utils.files.fopen(
            "{}/sysapi.conf.d.count".format(NILRT_RESTARTCHECK_STATE_PATH), "w"
        ) as fcount:
            fcount.write(str(len(os.listdir(nisysapi_conf_d_path))))

        for fexpert in os.listdir(nisysapi_conf_d_path):
            _fingerprint_file(
                filename=pathlib.Path(nisysapi_conf_d_path, fexpert),
                fingerprint_dir=pathlib.Path(NILRT_RESTARTCHECK_STATE_PATH),
            )


def _fingerprint_file(*, filename, fingerprint_dir):
    """
    Compute stat & md5sum hash of provided ``filename``. Store
    the hash and timestamp in ``fingerprint_dir``.

    filename
        ``Path`` to the file to stat & hash.

    fingerprint_dir
        ``Path`` of the directory to store the stat and hash output files.
    """
    __salt__["cmd.shell"](
        "stat -c %Y {} > {}/{}.timestamp".format(
            filename, fingerprint_dir, filename.name
        )
    )
    __salt__["cmd.shell"](
        "md5sum {} > {}/{}.md5sum".format(filename, fingerprint_dir, filename.name)
    )


def _get_restartcheck_result(errors):
    """
    Return restartcheck result and append errors (if any) to ``errors``
    """
    rs_result = __salt__["restartcheck.restartcheck"](verbose=False)
    if isinstance(rs_result, dict) and "comment" in rs_result:
        errors.append(rs_result["comment"])
    return rs_result


def _process_restartcheck_result(rs_result):
    """
    Check restartcheck output to see if system/service restarts were requested
    and take appropriate action.
    """
    if "No packages seem to need to be restarted" in rs_result:
        return
    for rstr in rs_result:
        if "System restart required" in rstr:
            _update_nilrt_restart_state()
            __salt__["system.set_reboot_required_witnessed"]()
        else:
            service = os.path.join("/etc/init.d", rstr)
            if os.path.exists(service):
                __salt__["cmd.run"]([service, "restart"])


def __virtual__():
    """
    Confirm this module is on a nilrt based system
    """
    if __grains__.get("os_family") == "NILinuxRT":
        try:
            os.makedirs(NILRT_RESTARTCHECK_STATE_PATH)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                return (
                    False,
                    "Error creating {} (-{}): {}".format(
                        NILRT_RESTARTCHECK_STATE_PATH, exc.errno, exc.strerror
                    ),
                )
        # populate state dir if empty
        if not os.listdir(NILRT_RESTARTCHECK_STATE_PATH):
            _update_nilrt_restart_state()
        return __virtualname__

    if os.path.isdir(OPKG_CONFDIR):
        return __virtualname__
    return False, "Module opkg only works on OpenEmbedded based systems"


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
        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    """
    refresh = salt.utils.data.is_true(kwargs.pop("refresh", True))

    if len(names) == 0:
        return ""

    ret = {}
    for name in names:
        ret[name] = ""

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db()

    cmd = ["opkg", "list-upgradable"]
    out = __salt__["cmd.run_stdout"](cmd, output_loglevel="trace", python_shell=False)
    for line in salt.utils.itertools.split(out, "\n"):
        try:
            name, _oldversion, newversion = line.split(" - ")
            if name in names:
                ret[name] = newversion
        except ValueError:
            pass

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


# available_version is being deprecated
available_version = latest_version


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


def refresh_db(failhard=False, **kwargs):  # pylint: disable=unused-argument
    """
    Updates the opkg database to latest packages based upon repositories

    Returns a dict, with the keys being package databases and the values being
    the result of the update attempt. Values can be one of the following:

    - ``True``: Database updated successfully
    - ``False``: Problem updating database

    failhard
        If False, return results of failed lines as ``False`` for the package
        database that encountered the error.
        If True, raise an error with a list of the package databases that
        encountered errors.

        .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    """
    # Remove rtag file to keep multiple refreshes from happening in pkg states
    salt.utils.pkg.clear_rtag(__opts__)
    ret = {}
    error_repos = []
    cmd = ["opkg", "update"]
    # opkg returns a non-zero retcode when there is a failure to refresh
    # from one or more repos. Due to this, ignore the retcode.
    call = __salt__["cmd.run_all"](
        cmd,
        output_loglevel="trace",
        python_shell=False,
        ignore_retcode=True,
        redirect_stderr=True,
    )

    out = call["stdout"]
    prev_line = ""
    for line in salt.utils.itertools.split(out, "\n"):
        if "Inflating" in line:
            key = line.strip().split()[1][:-1]
            ret[key] = True
        elif "Updated source" in line:
            # Use the previous line.
            key = prev_line.strip().split()[1][:-1]
            ret[key] = True
        elif "Failed to download" in line:
            key = line.strip().split()[5].split(",")[0]
            ret[key] = False
            error_repos.append(key)
        prev_line = line

    if failhard and error_repos:
        raise CommandExecutionError(
            "Error getting repos: {}".format(", ".join(error_repos))
        )

    # On a non-zero exit code where no failed repos were found, raise an
    # exception because this appears to be a different kind of error.
    if call["retcode"] != 0 and not error_repos:
        raise CommandExecutionError(out)

    return ret


def _is_testmode(**kwargs):
    """
    Returns whether a test mode (noaction) operation was requested.
    """
    return bool(kwargs.get("test") or __opts__.get("test"))


def _append_noaction_if_testmode(cmd, **kwargs):
    """
    Adds the --noaction flag to the command if it's running in the test mode.
    """
    if _is_testmode(**kwargs):
        cmd.append("--noaction")


def _build_install_command_list(cmd_prefix, to_install, to_downgrade, to_reinstall):
    """
    Builds a list of install commands to be executed in sequence in order to process
    each of the to_install, to_downgrade, and to_reinstall lists.
    """
    cmds = []
    if to_install:
        cmd = copy.deepcopy(cmd_prefix)
        cmd.extend(to_install)
        cmds.append(cmd)
    if to_downgrade:
        cmd = copy.deepcopy(cmd_prefix)
        cmd.append("--force-downgrade")
        cmd.extend(to_downgrade)
        cmds.append(cmd)
    if to_reinstall:
        cmd = copy.deepcopy(cmd_prefix)
        cmd.append("--force-reinstall")
        cmd.extend(to_reinstall)
        cmds.append(cmd)

    return cmds


def _parse_reported_packages_from_install_output(output):
    """
    Parses the output of "opkg install" to determine what packages would have been
    installed by an operation run with the --noaction flag.

    We are looking for lines like:
        Installing <package> (<version>) on <target>
    or
        Upgrading <package> from <oldVersion> to <version> on root
    """
    reported_pkgs = {}
    install_pattern = re.compile(
        r"Installing\s(?P<package>.*?)\s\((?P<version>.*?)\)\son\s(?P<target>.*?)"
    )
    upgrade_pattern = re.compile(
        r"Upgrading\s(?P<package>.*?)\sfrom\s(?P<oldVersion>.*?)\sto\s(?P<version>.*?)\son\s(?P<target>.*?)"
    )
    for line in salt.utils.itertools.split(output, "\n"):
        match = install_pattern.match(line)
        if match is None:
            match = upgrade_pattern.match(line)
        if match:
            reported_pkgs[match.group("package")] = match.group("version")

    return reported_pkgs


def _execute_install_command(cmd, parse_output, errors, parsed_packages):
    """
    Executes a command for the install operation.
    If the command fails, its error output will be appended to the errors list.
    If the command succeeds and parse_output is true, updated packages will be appended
    to the parsed_packages dictionary.
    """
    out = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)
    if out["retcode"] != 0:
        if out["stderr"]:
            errors.append(out["stderr"])
        else:
            errors.append(out["stdout"])
    elif parse_output:
        parsed_packages.update(
            _parse_reported_packages_from_install_output(out["stdout"])
        )


def install(
    name=None, refresh=False, pkgs=None, sources=None, reinstall=False, **kwargs
):
    """
    Install the passed package, add refresh=True to update the opkg database.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to install packages from a
        software repository. To install a package file manually, use the
        "sources" option.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to refresh the package database before installing.

    version
        Install a specific version of the package, e.g. 1.2.3~0ubuntu0. Ignored
        if "pkgs" or "sources" is passed.

        .. versionadded:: 2017.7.0

    reinstall : False
        Specifying reinstall=True will use ``opkg install --force-reinstall``
        rather than simply ``opkg install`` for requested packages that are
        already installed.

        If a version is specified with the requested package, then ``opkg
        install --force-reinstall`` will only be used if the installed version
        matches the requested version.

        .. versionadded:: 2017.7.0


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-0ubuntu0"}]'

    sources
        A list of IPK packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.  Dependencies are automatically resolved
        and marked as auto-installed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.deb"},{"bar": "salt://bar.deb"}]'

    install_recommends
        Whether to install the packages marked as recommended. Default is True.

    only_upgrade
        Only upgrade the packages (disallow downgrades), if they are already
        installed. Default is False.

        .. versionadded:: 2017.7.0

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    """
    refreshdb = salt.utils.data.is_true(refresh)

    try:
        pkg_params, pkg_type = __salt__["pkg_resource.parse_targets"](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    cmd_prefix = ["opkg", "install"]
    to_install = []
    to_reinstall = []
    to_downgrade = []

    _append_noaction_if_testmode(cmd_prefix, **kwargs)
    if pkg_params is None or len(pkg_params) == 0:
        return {}
    elif pkg_type == "file":
        if reinstall:
            cmd_prefix.append("--force-reinstall")
        if not kwargs.get("only_upgrade", False):
            cmd_prefix.append("--force-downgrade")
        to_install.extend(pkg_params)
    elif pkg_type == "repository":
        if not kwargs.get("install_recommends", True):
            cmd_prefix.append("--no-install-recommends")
        for pkgname, pkgversion in pkg_params.items():
            if name and pkgs is None and kwargs.get("version") and len(pkg_params) == 1:
                # Only use the 'version' param if 'name' was not specified as a
                # comma-separated list
                version_num = kwargs["version"]
            else:
                version_num = pkgversion

            if version_num is None:
                # Don't allow downgrades if the version
                # number is not specified.
                if reinstall and pkgname in old:
                    to_reinstall.append(pkgname)
                else:
                    to_install.append(pkgname)
            else:
                pkgstr = "{}={}".format(pkgname, version_num)
                cver = old.get(pkgname, "")
                if (
                    reinstall
                    and cver
                    and salt.utils.versions.compare(
                        ver1=version_num, oper="==", ver2=cver, cmp_func=version_cmp
                    )
                ):
                    to_reinstall.append(pkgstr)
                elif not cver or salt.utils.versions.compare(
                    ver1=version_num, oper=">=", ver2=cver, cmp_func=version_cmp
                ):
                    to_install.append(pkgstr)
                else:
                    if not kwargs.get("only_upgrade", False):
                        to_downgrade.append(pkgstr)
                    else:
                        # This should cause the command to fail.
                        to_install.append(pkgstr)

    cmds = _build_install_command_list(
        cmd_prefix, to_install, to_downgrade, to_reinstall
    )

    if not cmds:
        return {}

    if refreshdb:
        refresh_db()

    errors = []
    is_testmode = _is_testmode(**kwargs)
    test_packages = {}
    for cmd in cmds:
        _execute_install_command(cmd, is_testmode, errors, test_packages)

    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    if is_testmode:
        new = copy.deepcopy(new)
        new.update(test_packages)

    ret = salt.utils.data.compare_dicts(old, new)

    if pkg_type == "file" and reinstall:
        # For file-based packages, prepare 'to_reinstall' to have a list
        # of all the package names that may have been reinstalled.
        # This way, we could include reinstalled packages in 'ret'.
        for pkgfile in to_install:
            # Convert from file name to package name.
            cmd = ["opkg", "info", pkgfile]
            out = __salt__["cmd.run_all"](
                cmd, output_loglevel="trace", python_shell=False
            )
            if out["retcode"] == 0:
                # Just need the package name.
                pkginfo_dict = _process_info_installed_output(out["stdout"], [])
                if pkginfo_dict:
                    to_reinstall.append(next(iter(pkginfo_dict)))

    for pkgname in to_reinstall:
        if pkgname not in ret or pkgname in old:
            ret.update(
                {pkgname: {"old": old.get(pkgname, ""), "new": new.get(pkgname, "")}}
            )

    rs_result = _get_restartcheck_result(errors)

    if errors:
        raise CommandExecutionError(
            "Problem encountered installing package(s)",
            info={"errors": errors, "changes": ret},
        )

    _process_restartcheck_result(rs_result)

    return ret


def _parse_reported_packages_from_remove_output(output):
    """
    Parses the output of "opkg remove" to determine what packages would have been
    removed by an operation run with the --noaction flag.

    We are looking for lines like
        Removing <package> (<version>) from <Target>...
    """
    reported_pkgs = {}
    remove_pattern = re.compile(
        r"Removing\s(?P<package>.*?)\s\((?P<version>.*?)\)\sfrom\s(?P<target>.*?)..."
    )
    for line in salt.utils.itertools.split(output, "\n"):
        match = remove_pattern.match(line)
        if match:
            reported_pkgs[match.group("package")] = ""

    return reported_pkgs


def remove(name=None, pkgs=None, **kwargs):  # pylint: disable=unused-argument
    """
    Remove packages using ``opkg remove``.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    remove_dependencies
        Remove package and all dependencies

        .. versionadded:: 2019.2.0

    auto_remove_deps
        Remove packages that were installed automatically to satisfy dependencies

        .. versionadded:: 2019.2.0

    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
        salt '*' pkg.remove pkgs='["foo", "bar"]' remove_dependencies=True auto_remove_deps=True
    """
    try:
        pkg_params = __salt__["pkg_resource.parse_targets"](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    cmd = ["opkg", "remove"]
    _append_noaction_if_testmode(cmd, **kwargs)
    if kwargs.get("remove_dependencies", False):
        cmd.append("--force-removal-of-dependent-packages")
    if kwargs.get("auto_remove_deps", False):
        cmd.append("--autoremove")
    cmd.extend(targets)

    out = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)
    if out["retcode"] != 0:
        if out["stderr"]:
            errors = [out["stderr"]]
        else:
            errors = [out["stdout"]]
    else:
        errors = []

    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    if _is_testmode(**kwargs):
        reportedPkgs = _parse_reported_packages_from_remove_output(out["stdout"])
        new = {k: v for k, v in new.items() if k not in reportedPkgs}
    ret = salt.utils.data.compare_dicts(old, new)

    rs_result = _get_restartcheck_result(errors)

    if errors:
        raise CommandExecutionError(
            "Problem encountered removing package(s)",
            info={"errors": errors, "changes": ret},
        )

    _process_restartcheck_result(rs_result)

    return ret


def purge(name=None, pkgs=None, **kwargs):  # pylint: disable=unused-argument
    """
    Package purges are not supported by opkg, this function is identical to
    :mod:`pkg.remove <salt.modules.opkg.remove>`.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    """
    return remove(name=name, pkgs=pkgs)


def upgrade(refresh=True, **kwargs):  # pylint: disable=unused-argument
    """
    Upgrades all packages via ``opkg upgrade``

    Returns a dictionary containing the changes:

    .. code-block:: python

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    """
    ret = {
        "changes": {},
        "result": True,
        "comment": "",
    }

    errors = []

    if salt.utils.data.is_true(refresh):
        refresh_db()

    old = list_pkgs()

    cmd = ["opkg", "upgrade"]
    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)
    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if result["retcode"] != 0:
        errors.append(result)

    rs_result = _get_restartcheck_result(errors)

    if errors:
        raise CommandExecutionError(
            "Problem encountered upgrading packages",
            info={"errors": errors, "changes": ret},
        )

    _process_restartcheck_result(rs_result)

    return ret


def hold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    """
    Set package in 'hold' state, meaning it will not be upgraded.

    name
        The name of the package, e.g., 'tmux'

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.hold <package name>

    pkgs
        A list of packages to hold. Must be passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.hold pkgs='["foo", "bar"]'
    """
    if not name and not pkgs and not sources:
        raise SaltInvocationError("One of name, pkgs, or sources must be specified.")
    if pkgs and sources:
        raise SaltInvocationError("Only one of pkgs or sources can be specified.")

    targets = []
    if pkgs:
        targets.extend(pkgs)
    elif sources:
        for source in sources:
            targets.append(next(iter(source)))
    else:
        targets.append(name)

    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target))

        ret[target] = {"name": target, "changes": {}, "result": False, "comment": ""}

        state = _get_state(target)
        if not state:
            ret[target]["comment"] = "Package {} not currently held.".format(target)
        elif state != "hold":
            if "test" in __opts__ and __opts__["test"]:
                ret[target].update(result=None)
                ret[target]["comment"] = "Package {} is set to be held.".format(target)
            else:
                result = _set_state(target, "hold")
                ret[target].update(changes=result[target], result=True)
                ret[target]["comment"] = "Package {} is now being held.".format(target)
        else:
            ret[target].update(result=True)
            ret[target]["comment"] = "Package {} is already set to be held.".format(
                target
            )
    return ret


def unhold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    """
    Set package current in 'hold' state to install state,
    meaning it will be upgraded.

    name
        The name of the package, e.g., 'tmux'

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.unhold <package name>

    pkgs
        A list of packages to hold. Must be passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.unhold pkgs='["foo", "bar"]'
    """
    if not name and not pkgs and not sources:
        raise SaltInvocationError("One of name, pkgs, or sources must be specified.")
    if pkgs and sources:
        raise SaltInvocationError("Only one of pkgs or sources can be specified.")

    targets = []
    if pkgs:
        targets.extend(pkgs)
    elif sources:
        for source in sources:
            targets.append(next(iter(source)))
    else:
        targets.append(name)

    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target))

        ret[target] = {"name": target, "changes": {}, "result": False, "comment": ""}

        state = _get_state(target)
        if not state:
            ret[target]["comment"] = "Package {} does not have a state.".format(target)
        elif state == "hold":
            if "test" in __opts__ and __opts__["test"]:
                ret[target].update(result=None)
                ret["comment"] = "Package {} is set not to be held.".format(target)
            else:
                result = _set_state(target, "ok")
                ret[target].update(changes=result[target], result=True)
                ret[target]["comment"] = "Package {} is no longer being held.".format(
                    target
                )
        else:
            ret[target].update(result=True)
            ret[target]["comment"] = "Package {} is already set not to be held.".format(
                target
            )
    return ret


def _get_state(pkg):
    """
    View package state from the opkg database

    Return the state of pkg
    """
    cmd = ["opkg", "status"]
    cmd.append(pkg)
    out = __salt__["cmd.run"](cmd, python_shell=False)
    state_flag = ""
    for line in salt.utils.itertools.split(out, "\n"):
        if line.startswith("Status"):
            _status, _state_want, state_flag, _state_status = line.split()

    return state_flag


def _set_state(pkg, state):
    """
    Change package state on the opkg database

    The state can be any of:

     - hold
     - noprune
     - user
     - ok
     - installed
     - unpacked

    This command is commonly used to mark a specific package to be held from
    being upgraded, that is, to be kept at a certain version.

    Returns a dict containing the package name, and the new and old
    versions.
    """
    ret = {}
    valid_states = ("hold", "noprune", "user", "ok", "installed", "unpacked")
    if state not in valid_states:
        raise SaltInvocationError("Invalid state: {}".format(state))
    oldstate = _get_state(pkg)
    cmd = ["opkg", "flag"]
    cmd.append(state)
    cmd.append(pkg)
    _out = __salt__["cmd.run"](cmd, python_shell=False)

    # Missing return value check due to opkg issue 160
    ret[pkg] = {"old": oldstate, "new": state}
    return ret


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
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs versions_as_list=True
    """
    versions_as_list = salt.utils.data.is_true(versions_as_list)
    # not yet implemented or not applicable
    if any(
        [salt.utils.data.is_true(kwargs.get(x)) for x in ("removed", "purge_desired")]
    ):
        return {}

    if "pkg.list_pkgs" in __context__:
        return _list_pkgs_from_context(versions_as_list)

    cmd = ["opkg", "list-installed"]
    ret = {}
    out = __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)
    for line in salt.utils.itertools.split(out, "\n"):
        # This is a continuation of package description
        if not line or line[0] == " ":
            continue

        # This contains package name, version, and description.
        # Extract the first two.
        pkg_name, pkg_version = line.split(" - ", 2)[:2]
        __salt__["pkg_resource.add_pkg"](ret, pkg_name, pkg_version)

    __salt__["pkg_resource.sort_pkglist"](ret)
    __context__["pkg.list_pkgs"] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__["pkg_resource.stringify"](ret)
    return ret


def list_upgrades(refresh=True, **kwargs):  # pylint: disable=unused-argument
    """
    List all available package upgrades.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    """
    ret = {}
    if salt.utils.data.is_true(refresh):
        refresh_db()

    cmd = ["opkg", "list-upgradable"]
    call = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    if call["retcode"] != 0:
        comment = ""
        if "stderr" in call:
            comment += call["stderr"]
        if "stdout" in call:
            comment += call["stdout"]
        raise CommandExecutionError(comment)
    else:
        out = call["stdout"]

    for line in out.splitlines():
        name, _oldversion, newversion = line.split(" - ")
        ret[name] = newversion

    return ret


def _convert_to_standard_attr(attr):
    """
    Helper function for _process_info_installed_output()

    Converts an opkg attribute name to a standard attribute
    name which is used across 'pkg' modules.
    """
    ret_attr = ATTR_MAP.get(attr, None)
    if ret_attr is None:
        # All others convert to lowercase
        return attr.lower()
    return ret_attr


def _process_info_installed_output(out, filter_attrs):
    """
    Helper function for info_installed()

    Processes stdout output from a single invocation of
    'opkg status'.
    """
    ret = {}
    name = None
    attrs = {}
    attr = None

    for line in salt.utils.itertools.split(out, "\n"):
        if line and line[0] == " ":
            # This is a continuation of the last attr
            if filter_attrs is None or attr in filter_attrs:
                line = line.strip()
                if attrs[attr]:
                    # If attr is empty, don't add leading newline
                    attrs[attr] += "\n"
                attrs[attr] += line
            continue
        line = line.strip()
        if not line:
            # Separator between different packages
            if name:
                ret[name] = attrs
            name = None
            attrs = {}
            attr = None
            continue
        key, value = line.split(":", 1)
        value = value.lstrip()
        attr = _convert_to_standard_attr(key)
        if attr == "name":
            name = value
        elif filter_attrs is None or attr in filter_attrs:
            attrs[attr] = value

    if name:
        ret[name] = attrs
    return ret


def info_installed(*names, **kwargs):
    """
    Return the information of the named package(s), installed on the system.

    .. versionadded:: 2017.7.0

    :param names:
        Names of the packages to get information about. If none are specified,
        will return information for all installed packages.

    :param attr:
        Comma-separated package attributes. If no 'attr' is specified, all available attributes returned.

        Valid attributes are:
            arch, conffiles, conflicts, depends, description, filename, group,
            install_date_time_t, md5sum, packager, provides, recommends,
            replaces, size, source, suggests, url, version

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.info_installed
        salt '*' pkg.info_installed attr=version,packager
        salt '*' pkg.info_installed <package1>
        salt '*' pkg.info_installed <package1> <package2> <package3> ...
        salt '*' pkg.info_installed <package1> attr=version,packager
        salt '*' pkg.info_installed <package1> <package2> <package3> ... attr=version,packager
    """
    attr = kwargs.pop("attr", None)
    if attr is None:
        filter_attrs = None
    elif isinstance(attr, str):
        filter_attrs = set(attr.split(","))
    else:
        filter_attrs = set(attr)

    ret = {}
    if names:
        # Specific list of names of installed packages
        for name in names:
            cmd = ["opkg", "status", name]
            call = __salt__["cmd.run_all"](
                cmd, output_loglevel="trace", python_shell=False
            )
            if call["retcode"] != 0:
                comment = ""
                if call["stderr"]:
                    comment += call["stderr"]
                else:
                    comment += call["stdout"]

                raise CommandExecutionError(comment)
            ret.update(_process_info_installed_output(call["stdout"], filter_attrs))
    else:
        # All installed packages
        cmd = ["opkg", "status"]
        call = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)
        if call["retcode"] != 0:
            comment = ""
            if call["stderr"]:
                comment += call["stderr"]
            else:
                comment += call["stdout"]

            raise CommandExecutionError(comment)
        ret.update(_process_info_installed_output(call["stdout"], filter_attrs))

    return ret


def upgrade_available(name, **kwargs):  # pylint: disable=unused-argument
    """
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    """
    return latest_version(name) != ""


def version_cmp(
    pkg1, pkg2, ignore_epoch=False, **kwargs
):  # pylint: disable=unused-argument
    """
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    ignore_epoch : False
        Set to ``True`` to ignore the epoch when comparing versions

        .. versionadded:: 2016.3.4

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '0.2.4-0' '0.2.4.1-0'
    """
    normalize = lambda x: str(x).split(":", 1)[-1] if ignore_epoch else str(x)
    pkg1 = normalize(pkg1)
    pkg2 = normalize(pkg2)

    output = __salt__["cmd.run_stdout"](
        ["opkg", "--version"], output_loglevel="trace", python_shell=False
    )
    opkg_version = output.split(" ")[2].strip()
    if salt.utils.versions.LooseVersion(
        opkg_version
    ) >= salt.utils.versions.LooseVersion("0.3.4"):
        cmd_compare = ["opkg", "compare-versions"]
    elif salt.utils.path.which("opkg-compare-versions"):
        cmd_compare = ["opkg-compare-versions"]
    else:
        log.warning(
            "Unable to find a compare-versions utility installed. Either upgrade opkg"
            " to version > 0.3.4 (preferred) or install the older opkg-compare-versions"
            " script."
        )
        return None

    for oper, ret in (("<<", -1), ("=", 0), (">>", 1)):
        cmd = cmd_compare[:]
        cmd.append(shlex.quote(pkg1))
        cmd.append(oper)
        cmd.append(shlex.quote(pkg2))
        retcode = __salt__["cmd.retcode"](
            cmd, output_loglevel="trace", ignore_retcode=True, python_shell=False
        )
        if retcode == 0:
            return ret
    return None


def _set_repo_option(repo, option):
    """
    Set the option to repo
    """
    if not option:
        return
    opt = option.split("=")
    if len(opt) != 2:
        return
    if opt[0] == "trusted":
        repo["trusted"] = opt[1] == "yes"
    else:
        repo[opt[0]] = opt[1]


def _set_repo_options(repo, options):
    """
    Set the options to the repo.
    """
    delimiters = "[", "]"
    pattern = "|".join(map(re.escape, delimiters))
    for option in options:
        splitted = re.split(pattern, option)
        for opt in splitted:
            _set_repo_option(repo, opt)


def _create_repo(line, filename):
    """
    Create repo
    """
    repo = {}
    if line.startswith("#"):
        repo["enabled"] = False
        line = line[1:]
    else:
        repo["enabled"] = True
    cols = salt.utils.args.shlex_split(line.strip())
    repo["compressed"] = not cols[0] in "src"
    repo["name"] = cols[1]
    repo["uri"] = cols[2]
    repo["file"] = os.path.join(OPKG_CONFDIR, filename)
    if len(cols) > 3:
        _set_repo_options(repo, cols[3:])
    return repo


def _read_repos(conf_file, repos, filename, regex):
    """
    Read repos from configuration file
    """
    for line in conf_file:
        line = salt.utils.stringutils.to_unicode(line)
        if not regex.search(line):
            continue
        repo = _create_repo(line, filename)

        # do not store duplicated uri's
        if repo["uri"] not in repos:
            repos[repo["uri"]] = [repo]


def list_repos(**kwargs):  # pylint: disable=unused-argument
    """
    Lists all repos on ``/etc/opkg/*.conf``

    CLI Example:

    .. code-block:: bash

       salt '*' pkg.list_repos
    """
    repos = {}
    regex = re.compile(REPO_REGEXP)
    for filename in os.listdir(OPKG_CONFDIR):
        if not filename.endswith(".conf"):
            continue
        with salt.utils.files.fopen(os.path.join(OPKG_CONFDIR, filename)) as conf_file:
            _read_repos(conf_file, repos, filename, regex)
    return repos


def get_repo(repo, **kwargs):  # pylint: disable=unused-argument
    """
    Display a repo from the ``/etc/opkg/*.conf``

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.get_repo repo
    """
    repos = list_repos()

    if repos:
        for source in repos.values():
            for sub in source:
                if sub["name"] == repo:
                    return sub
    return {}


def _del_repo_from_file(repo, filepath):
    """
    Remove a repo from filepath
    """
    with salt.utils.files.fopen(filepath) as fhandle:
        output = []
        regex = re.compile(REPO_REGEXP)
        for line in fhandle:
            line = salt.utils.stringutils.to_unicode(line)
            if regex.search(line):
                if line.startswith("#"):
                    line = line[1:]
                cols = salt.utils.args.shlex_split(line.strip())
                if repo != cols[1]:
                    output.append(salt.utils.stringutils.to_str(line))
    with salt.utils.files.fopen(filepath, "w") as fhandle:
        fhandle.writelines(output)


def _set_trusted_option_if_needed(repostr, trusted):
    """
    Set trusted option to repo if needed
    """
    if trusted is True:
        repostr += " [trusted=yes]"
    elif trusted is False:
        repostr += " [trusted=no]"
    return repostr


def _add_new_repo(repo, properties):
    """
    Add a new repo entry
    """
    repostr = "# " if not properties.get("enabled") else ""
    repostr += "src/gz " if properties.get("compressed") else "src "
    if " " in repo:
        repostr += '"' + repo + '" '
    else:
        repostr += repo + " "
    repostr += properties.get("uri")
    repostr = _set_trusted_option_if_needed(repostr, properties.get("trusted"))
    repostr += "\n"
    conffile = os.path.join(OPKG_CONFDIR, repo + ".conf")

    with salt.utils.files.fopen(conffile, "a") as fhandle:
        fhandle.write(salt.utils.stringutils.to_str(repostr))


def _mod_repo_in_file(repo, repostr, filepath):
    """
    Replace a repo entry in filepath with repostr
    """
    with salt.utils.files.fopen(filepath) as fhandle:
        output = []
        for line in fhandle:
            cols = salt.utils.args.shlex_split(
                salt.utils.stringutils.to_unicode(line).strip()
            )
            if repo not in cols:
                output.append(line)
            else:
                output.append(salt.utils.stringutils.to_str(repostr + "\n"))
    with salt.utils.files.fopen(filepath, "w") as fhandle:
        fhandle.writelines(output)


def del_repo(repo, **kwargs):  # pylint: disable=unused-argument
    """
    Delete a repo from ``/etc/opkg/*.conf``

    If the file does not contain any other repo configuration, the file itself
    will be deleted.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo repo
    """
    refresh = salt.utils.data.is_true(kwargs.get("refresh", True))
    repos = list_repos()
    if repos:
        deleted_from = dict()
        for repository in repos:
            source = repos[repository][0]
            if source["name"] == repo:
                deleted_from[source["file"]] = 0
                _del_repo_from_file(repo, source["file"])

        if deleted_from:
            ret = ""
            for repository in repos:
                source = repos[repository][0]
                if source["file"] in deleted_from:
                    deleted_from[source["file"]] += 1
            for repo_file, count in deleted_from.items():
                msg = "Repo '{}' has been removed from {}.\n"
                if count == 1 and os.path.isfile(repo_file):
                    msg = "File {1} containing repo '{0}' has been removed.\n"
                    try:
                        os.remove(repo_file)
                    except OSError:
                        pass
                ret += msg.format(repo, repo_file)
            if refresh:
                refresh_db()
            return ret

    return "Repo {} doesn't exist in the opkg repo lists".format(repo)


def mod_repo(repo, **kwargs):
    """
    Modify one or more values for a repo.  If the repo does not exist, it will
    be created, so long as uri is defined.

    The following options are available to modify a repo definition:

    repo
        alias by which opkg refers to the repo.
    uri
        the URI to the repo.
    compressed
        defines (True or False) if the index file is compressed
    enabled
        enable or disable (True or False) repository
        but do not remove if disabled.
    refresh
        enable or disable (True or False) auto-refresh of the repositories

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.mod_repo repo uri=http://new/uri
        salt '*' pkg.mod_repo repo enabled=False
    """
    repos = list_repos()
    found = False
    uri = ""
    if "uri" in kwargs:
        uri = kwargs["uri"]

    for repository in repos:
        source = repos[repository][0]
        if source["name"] == repo:
            found = True
            repostr = ""
            if "enabled" in kwargs and not kwargs["enabled"]:
                repostr += "# "
            if "compressed" in kwargs:
                repostr += "src/gz " if kwargs["compressed"] else "src"
            else:
                repostr += "src/gz" if source["compressed"] else "src"
            repo_alias = kwargs["alias"] if "alias" in kwargs else repo
            if " " in repo_alias:
                repostr += ' "{}"'.format(repo_alias)
            else:
                repostr += " {}".format(repo_alias)
            repostr += " {}".format(kwargs["uri"] if "uri" in kwargs else source["uri"])
            trusted = kwargs.get("trusted")
            repostr = (
                _set_trusted_option_if_needed(repostr, trusted)
                if trusted is not None
                else _set_trusted_option_if_needed(repostr, source.get("trusted"))
            )
            _mod_repo_in_file(repo, repostr, source["file"])
        elif uri and source["uri"] == uri:
            raise CommandExecutionError(
                "Repository '{}' already exists as '{}'.".format(uri, source["name"])
            )

    if not found:
        # Need to add a new repo
        if "uri" not in kwargs:
            raise CommandExecutionError(
                "Repository '{}' not found and no URI passed to create one.".format(
                    repo
                )
            )
        properties = {"uri": kwargs["uri"]}
        # If compressed is not defined, assume True
        properties["compressed"] = (
            kwargs["compressed"] if "compressed" in kwargs else True
        )
        # If enabled is not defined, assume True
        properties["enabled"] = kwargs["enabled"] if "enabled" in kwargs else True
        properties["trusted"] = kwargs.get("trusted")
        _add_new_repo(repo, properties)

    if "refresh" in kwargs:
        refresh_db()


def file_list(*packages, **kwargs):  # pylint: disable=unused-argument
    """
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's package database (not
    generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    """
    output = file_dict(*packages)
    files = []
    for package in list(output["packages"].values()):
        files.extend(package)
    return {"errors": output["errors"], "files": files}


def file_dict(*packages, **kwargs):  # pylint: disable=unused-argument
    """
    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of _every_ file on the system's
    package database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    """
    errors = []
    ret = {}
    cmd_files = ["opkg", "files"]

    if not packages:
        packages = list(list_pkgs().keys())

    for package in packages:
        files = []
        cmd = cmd_files[:]
        cmd.append(package)
        out = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)
        for line in out["stdout"].splitlines():
            if line.startswith("/"):
                files.append(line)
            elif line.startswith(" * "):
                errors.append(line[3:])
                break
            else:
                continue
        if files:
            ret[package] = files

    return {"errors": errors, "packages": ret}


def owner(*paths, **kwargs):  # pylint: disable=unused-argument
    """
    Return the name of the package that owns the file. Multiple file paths can
    be passed. Like :mod:`pkg.version <salt.modules.opkg.version`, if a single
    path is passed, a string will be returned, and if multiple paths are passed,
    a dictionary of file/package name pairs will be returned.

    If the file is not owned by a package, or is not present on the minion,
    then an empty string will be returned for that path.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.owner /usr/bin/apachectl
        salt '*' pkg.owner /usr/bin/apachectl /usr/bin/basename
    """
    if not paths:
        return ""
    ret = {}
    cmd_search = ["opkg", "search"]
    for path in paths:
        cmd = cmd_search[:]
        cmd.append(path)
        output = __salt__["cmd.run_stdout"](
            cmd, output_loglevel="trace", python_shell=False
        )
        if output:
            ret[path] = output.split(" - ")[0].strip()
        else:
            ret[path] = ""
    if len(ret) == 1:
        return next(iter(ret.values()))
    return ret


def version_clean(version):
    """
    Clean the version string removing extra data.
    There's nothing do to here for nipkg.py, therefore it will always
    return the given version.
    """
    return version


def check_extra_requirements(pkgname, pkgver):
    """
    Check if the installed package already has the given requirements.
    There's nothing do to here for nipkg.py, therefore it will always
    return True.
    """
    return True
