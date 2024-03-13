"""
Package support for XBPS package manager (used by VoidLinux)

.. versionadded:: 2016.11.0
"""

# TODO: what about the initial acceptance of repo's fingerprint when adding a new repo?

import glob
import logging
import os
import re

import salt.utils.data
import salt.utils.decorators as decorators
import salt.utils.files
import salt.utils.path
import salt.utils.pkg
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, MinionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Set the virtual pkg module if the os is Void and xbps-install found
    """
    if __grains__["os"] in ("Void") and _check_xbps():
        return __virtualname__
    return (False, "Missing dependency: xbps-install")


@decorators.memoize
def _check_xbps():
    """
    Looks to see if xbps-install is present on the system, return full path
    """
    return salt.utils.path.which("xbps-install")


@decorators.memoize
def _get_version():
    """
    Get the xbps version
    """
    version_string = __salt__["cmd.run"](
        [_check_xbps(), "--version"], output_loglevel="trace"
    )
    if version_string is None:
        # Dunno why it would, but...
        return False

    VERSION_MATCH = re.compile(r"(?:XBPS:[\s]+)([\d.]+)(?:[\s]+.*)")
    version_match = VERSION_MATCH.search(version_string)
    if not version_match:
        return False

    return version_match.group(1).split(".")


def _rehash():
    """
    Recomputes internal hash table for the PATH variable.
    Used whenever a new command is created during the current
    session.
    """
    shell = __salt__["environ.get"]("SHELL")
    if shell.split("/")[-1] in ("csh", "tcsh"):
        __salt__["cmd.run"]("rehash", output_loglevel="trace")


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

    cmd = "xbps-query -l"
    ret = {}
    out = __salt__["cmd.run"](cmd, output_loglevel="trace")
    for line in out.splitlines():
        if not line:
            continue
        try:
            # xbps-query -l output sample:
            # ii desktop-file-utils-0.22_4  Utilities to ...
            #
            # XXX handle package status (like 'ii') ?
            pkg, ver = line.split(None)[1].rsplit("-", 1)
        except ValueError:
            log.error('xbps-query: Unexpected formatting in line: "%s"', line)

        __salt__["pkg_resource.add_pkg"](ret, pkg, ver)

    __salt__["pkg_resource.sort_pkglist"](ret)
    if not versions_as_list:
        __salt__["pkg_resource.stringify"](ret)
    return ret


def list_upgrades(refresh=True, **kwargs):
    """
    Check whether or not an upgrade is available for all packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    """

    # sample output of 'xbps-install -un':
    #     fuse-2.9.4_4 update i686 http://repo.voidlinux.eu/current 298133 91688
    #     xtools-0.34_1 update noarch http://repo.voidlinux.eu/current 21424 10752

    refresh = salt.utils.data.is_true(refresh)

    # Refresh repo index before checking for latest version available
    if refresh:
        refresh_db()

    ret = {}

    # retrieve list of updatable packages
    cmd = "xbps-install -un"
    out = __salt__["cmd.run"](cmd, output_loglevel="trace")
    for line in out.splitlines():
        if not line:
            continue
        pkg = "base-system"
        ver = "NonNumericValueIsError"
        try:
            pkg, ver = line.split()[0].rsplit("-", 1)
        except (ValueError, IndexError):
            log.error('xbps-query: Unexpected formatting in line: "%s"', line)
            continue

        log.trace("pkg=%s version=%s", pkg, ver)
        ret[pkg] = ver

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
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    """

    # Why using 'xbps-install -un' and not 'xbps-query -R':
    # if several repos, xbps-query will produces this kind of output,
    # that is difficult to handle correctly:
    #     [*] salt-2015.8.3_2 Remote execution system ...
    #     [-] salt-2015.8.3_1 Remote execution system ...
    #
    # XXX 'xbps-install -un pkg1 pkg2' won't produce any info on updatable pkg1
    #     if pkg2 is up-to-date. Bug of xbps 0.51, probably get fixed in 0.52.
    #     See related issue https://github.com/voidlinux/xbps/issues/145
    #
    # sample outputs of 'xbps-install -un':
    #     fuse-2.9.4_4 update i686 http://repo.voidlinux.eu/current 298133 91688
    #     xtools-0.34_1 update noarch http://repo.voidlinux.eu/current 21424 10752
    #     Package 'vim' is up to date.

    refresh = salt.utils.data.is_true(kwargs.pop("refresh", True))

    if not names:
        return ""

    # Refresh repo index before checking for latest version available
    if refresh:
        refresh_db()

    # Initialize the dict with empty strings
    ret = {}
    for name in names:
        ret[name] = ""

    # retrieve list of updatable packages
    # ignore return code since 'is up to date' case produces retcode==17 (xbps 0.51)
    cmd = ["xbps-install", "-un"]
    cmd.extend(names)
    out = __salt__["cmd.run"](cmd, ignore_retcode=True, output_loglevel="trace")
    for line in out.splitlines():
        if not line:
            continue
        if line.find(" is up to date.") != -1:
            continue
        # retrieve tuple pkgname version
        try:
            pkg, ver = line.split()[0].rsplit("-", 1)
        except (ValueError, IndexError):
            log.error('xbps-query: Unexpected formatting in line: "%s"', line)
            continue

        log.trace("pkg=%s version=%s", pkg, ver)
        if pkg in names:
            ret[pkg] = ver

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


# available_version is being deprecated
available_version = latest_version


def upgrade_available(name, **kwargs):
    """
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    """
    return latest_version(name) != ""


def refresh_db(**kwargs):
    """
    Update list of available packages from installed repos

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    """
    # Remove rtag file to keep multiple refreshes from happening in pkg states
    salt.utils.pkg.clear_rtag(__opts__)
    cmd = "xbps-install -Sy"
    call = __salt__["cmd.run_all"](cmd, output_loglevel="trace")
    if call["retcode"] != 0:
        comment = ""
        if "stderr" in call:
            comment += call["stderr"]

        raise CommandExecutionError(comment)

    return True


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


def upgrade(refresh=True, **kwargs):
    """
    Run a full system upgrade

    refresh
        Whether or not to refresh the package database before installing.
        Default is `True`.

    Returns a dictionary containing the changes:

    .. code-block:: python

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    """

    # XXX if xbps has to be upgraded, 2 times is required to fully upgrade
    # system: one for xbps, a subsequent one for all other packages. Not
    # handled in this code.

    old = list_pkgs()

    cmd = ["xbps-install", "-{}yu".format("S" if refresh else "")]
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


def install(name=None, refresh=False, fromrepo=None, pkgs=None, sources=None, **kwargs):
    """
    Install the passed package

    name
        The name of the package to be installed.

    refresh
        Whether or not to refresh the package database before installing.

    fromrepo
        Specify a package repository (url) to install from.


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo","bar"]'

    sources
        A list of packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.deb"},{"bar": "salt://bar.deb"}]'

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install <package name>
    """

    # XXX sources is not yet used in this code

    try:
        pkg_params, pkg_type = __salt__["pkg_resource.parse_targets"](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if not pkg_params:
        return {}

    if pkg_type != "repository":
        log.error('xbps: pkg_type "%s" not supported.', pkg_type)
        return {}

    cmd = ["xbps-install"]

    if refresh:
        cmd.append("-S")  # update repo db
    if fromrepo:
        cmd.append(f"--repository={fromrepo}")
    cmd.append("-y")  # assume yes when asked
    cmd.extend(pkg_params)

    old = list_pkgs()
    __salt__["cmd.run"](cmd, output_loglevel="trace")
    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()

    _rehash()
    return salt.utils.data.compare_dicts(old, new)


def remove(name=None, pkgs=None, recursive=True, **kwargs):
    """
    name
        The name of the package to be deleted.

    recursive
        Also remove dependent packages (not required elsewhere).
        Default mode: enabled.

    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    Returns a list containing the removed packages.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name> [recursive=False]
        salt '*' pkg.remove <package1>,<package2>,<package3> [recursive=False]
        salt '*' pkg.remove pkgs='["foo", "bar"]' [recursive=False]
    """

    try:
        pkg_params, pkg_type = __salt__["pkg_resource.parse_targets"](name, pkgs)
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if not pkg_params:
        return {}

    old = list_pkgs()

    # keep only installed packages
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    cmd = ["xbps-remove", "-y"]
    if recursive:
        cmd.append("-R")
    cmd.extend(targets)
    __salt__["cmd.run"](cmd, output_loglevel="trace")
    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()

    return salt.utils.data.compare_dicts(old, new)


def list_repos(**kwargs):
    """
    List all repos known by XBPS

    CLI Example:

    .. code-block:: bash

       salt '*' pkg.list_repos
    """
    repos = {}
    out = __salt__["cmd.run"]("xbps-query -L", output_loglevel="trace")
    for line in out.splitlines():
        repo = {}
        if not line:
            continue
        try:
            nb, url, rsa = line.strip().split(" ", 2)
        except ValueError:
            log.error(
                'Problem parsing xbps-query: Unexpected formatting in line: "%s"',
                line,
            )
        repo["nbpkg"] = int(nb) if nb.isdigit() else 0
        repo["url"] = url
        repo["rsasigned"] = True if rsa == "(RSA signed)" else False
        repos[repo["url"]] = repo
    return repos


def get_repo(repo, **kwargs):
    """
    Display information about the repo.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.get_repo 'repo-url'
    """
    repos = list_repos()
    if repo in repos:
        return repos[repo]
    return {}


def _locate_repo_files(repo, rewrite=False):
    """
    Find what file a repo is called in.

    Helper function for add_repo() and del_repo()

    repo
        url of the repo to locate (persistent).

    rewrite
        Whether to remove matching repository settings during this process.

    Returns a list of absolute paths.
    """

    ret_val = []
    files = []
    conf_dirs = ["/etc/xbps.d/", "/usr/share/xbps.d/"]
    name_glob = "*.conf"
    # Matches a line where first printing is "repository" and there is an equals
    # sign before the repo, an optional forwardslash at the end of the repo name,
    # and it's possible for there to be a comment after repository=repo
    regex = re.compile(r"\s*repository\s*=\s*" + repo + r"/?\s*(#.*)?$")

    for cur_dir in conf_dirs:
        files.extend(glob.glob(cur_dir + name_glob))

    for filename in files:
        write_buff = []
        with salt.utils.files.fopen(filename, "r") as cur_file:
            for line in cur_file:
                if regex.match(salt.utils.stringutils.to_unicode(line)):
                    ret_val.append(filename)
                else:
                    write_buff.append(line)
        if rewrite and filename in ret_val:
            if write_buff:
                with salt.utils.files.fopen(filename, "w") as rewrite_file:
                    rewrite_file.writelines(write_buff)
            else:  # Prune empty files
                os.remove(filename)

    return ret_val


def add_repo(repo, conffile="/usr/share/xbps.d/15-saltstack.conf"):
    """
    Add an XBPS repository to the system.

    repo
        url of repo to add (persistent).

    conffile
        path to xbps conf file to add this repo
        default: /usr/share/xbps.d/15-saltstack.conf

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.add_repo <repo url> [conffile=/path/to/xbps/repo.conf]
    """

    if not _locate_repo_files(repo):
        try:
            with salt.utils.files.fopen(conffile, "a+") as conf_file:
                conf_file.write(salt.utils.stringutils.to_str(f"repository={repo}\n"))
        except OSError:
            return False

    return True


def del_repo(repo, **kwargs):
    """
    Remove an XBPS repository from the system.

    repo
        url of repo to remove (persistent).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo <repo url>
    """

    try:
        _locate_repo_files(repo, rewrite=True)
    except OSError:
        return False
    else:
        return True
