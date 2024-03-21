"""
Support for APT (Advanced Packaging Tool)

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import copy
import datetime
import fnmatch
import logging
import os
import pathlib
import re
import shutil
import time
from urllib.error import HTTPError
from urllib.request import Request as _Request
from urllib.request import urlopen as _urlopen

import salt.config
import salt.syspaths
import salt.utils.args
import salt.utils.data
import salt.utils.environment
import salt.utils.files
import salt.utils.functools
import salt.utils.itertools
import salt.utils.json
import salt.utils.path
import salt.utils.pkg
import salt.utils.pkg.deb
import salt.utils.stringutils
import salt.utils.systemd
import salt.utils.versions
import salt.utils.yaml
from salt.exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    MinionError,
    SaltInvocationError,
)
from salt.modules.cmdmod import _parse_env
from salt.utils.pkg.deb import SourceEntry, SourcesList

log = logging.getLogger(__name__)

APT_LISTS_PATH = "/var/lib/apt/lists"
PKG_ARCH_SEPARATOR = ":"

# Source format for urllib fallback on PPA handling
LP_SRC_FORMAT = "deb http://ppa.launchpad.net/{0}/{1}/ubuntu {2} main"
LP_PVT_SRC_FORMAT = "deb https://{0}private-ppa.launchpad.net/{1}/{2}/ubuntu {3} main"

_MODIFY_OK = frozenset(
    ["uri", "comps", "architectures", "disabled", "file", "dist", "signedby"]
)
DPKG_ENV_VARS = {
    "APT_LISTBUGS_FRONTEND": "none",
    "APT_LISTCHANGES_FRONTEND": "none",
    "DEBIAN_FRONTEND": "noninteractive",
    "UCF_FORCE_CONFFOLD": "1",
}

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Confirm this module is on a Debian-based system
    """
    # If your minion is running an OS which is Debian-based but does not have
    # an "os_family" grain of Debian, then the proper fix is NOT to check for
    # the minion's "os_family" grain here in the __virtual__. The correct fix
    # is to add the value from the minion's "os" grain to the _OS_FAMILY_MAP
    # dict in salt/grains/core.py, so that we assign the correct "os_family"
    # grain to the minion.
    if __grains__.get("os_family") == "Debian":
        return __virtualname__
    return False, "The pkg module could not be loaded: unsupported OS family"


def __init__(opts):
    """
    For Debian and derivative systems, set up
    a few env variables to keep apt happy and
    non-interactive.
    """
    if __virtual__() == __virtualname__:
        # Export these puppies so they persist
        os.environ.update(DPKG_ENV_VARS)


def _get_ppa_info_from_launchpad(owner_name, ppa_name):
    """
    Idea from softwareproperties.ppa.
    Uses urllib2 which sacrifices server cert verification.

    This is used as fall-back code or for secure PPAs

    :param owner_name:
    :param ppa_name:
    :return:
    """

    lp_url = f"https://launchpad.net/api/1.0/~{owner_name}/+archive/{ppa_name}"
    request = _Request(lp_url, headers={"Accept": "application/json"})
    lp_page = _urlopen(request)
    return salt.utils.json.load(lp_page)


def _call_apt(args, scope=True, **kwargs):
    """
    Call apt* utilities.
    """
    cmd = []
    if (
        scope
        and salt.utils.systemd.has_scope(__context__)
        and __salt__["config.get"]("systemd.scope", True)
    ):
        cmd.extend(["systemd-run", "--scope", "--description", f'"{__name__}"'])
    cmd.extend(args)

    params = {
        "output_loglevel": "trace",
        "python_shell": False,
        "env": salt.utils.environment.get_module_environment(globals()),
    }
    params.update(kwargs)

    cmd_ret = __salt__["cmd.run_all"](cmd, **params)
    count = 0
    while "Could not get lock" in cmd_ret.get("stderr", "") and count < 10:
        count += 1
        log.warning("Waiting for dpkg lock release: retrying... %s/100", count)
        time.sleep(2**count)
        cmd_ret = __salt__["cmd.run_all"](cmd, **params)
    return cmd_ret


def normalize_name(name):
    """
    Strips the architecture from the specified package name, if necessary.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.normalize_name zsh:amd64
    """
    try:
        pkgname, pkgarch = name.rsplit(PKG_ARCH_SEPARATOR, 1)
    except ValueError:
        pkgname = name
        pkgarch = __grains__["osarch"]

    return pkgname if pkgarch in (__grains__["osarch"], "all", "any") else name


def parse_arch(name):
    """
    Parse name and architecture from the specified package name.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.parse_arch zsh:amd64
    """
    try:
        _name, _arch = name.rsplit(PKG_ARCH_SEPARATOR, 1)
    except ValueError:
        _name, _arch = name, None
    return {"name": _name, "arch": _arch}


def latest_version(*names, **kwargs):
    """
    .. versionchanged:: 3007.0

    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    A specific repo can be requested using the ``fromrepo`` keyword argument.

    cache_valid_time

        .. versionadded:: 2016.11.0

        Skip refreshing the package database if refresh has already occurred within
        <value> seconds

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package name> fromrepo=unstable
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    """
    refresh = salt.utils.data.is_true(kwargs.pop("refresh", True))
    show_installed = salt.utils.data.is_true(kwargs.pop("show_installed", False))
    if "repo" in kwargs:
        raise SaltInvocationError(
            "The 'repo' argument is invalid, use 'fromrepo' instead"
        )
    fromrepo = kwargs.pop("fromrepo", None)
    cache_valid_time = kwargs.pop("cache_valid_time", 0)

    if not names:
        return ""
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ""
    pkgs = list_pkgs(versions_as_list=True)
    repo = ["-o", f"APT::Default-Release={fromrepo}"] if fromrepo else None

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db(cache_valid_time)

    cmd = ["apt-cache", "-q", "policy"]
    cmd.extend(names)
    if repo is not None:
        cmd.extend(repo)
    out = _call_apt(cmd, scope=False)

    short_names = [nom.split(":", maxsplit=1)[0] for nom in names]

    candidates = {}
    for line in salt.utils.itertools.split(out["stdout"], "\n"):
        if line.endswith(":") and line[:-1] in short_names:
            this_pkg = names[short_names.index(line[:-1])]
        elif "Candidate" in line:
            candidate = ""
            comps = line.split()
            if len(comps) >= 2:
                candidate = comps[-1]
                if candidate.lower() == "(none)":
                    candidate = ""
            candidates[this_pkg] = candidate

    for name in names:
        installed = pkgs.get(name, [])
        if not installed:
            ret[name] = candidates.get(name, "")
        elif installed and show_installed:
            ret[name] = candidates.get(name, "")
        elif candidates.get(name):
            # If there are no installed versions that are greater than or equal
            # to the install candidate, then the candidate is an upgrade, so
            # add it to the return dict
            if not any(
                salt.utils.versions.compare(
                    ver1=x,
                    oper=">=",
                    ver2=candidates.get(name, ""),
                    cmp_func=version_cmp,
                )
                for x in installed
            ):
                ret[name] = candidates.get(name, "")

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


# available_version is being deprecated
available_version = salt.utils.functools.alias_function(
    latest_version, "available_version"
)


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


def refresh_db(cache_valid_time=0, failhard=False, **kwargs):
    """
    Updates the APT database to latest packages based upon repositories

    Returns a dict, with the keys being package databases and the values being
    the result of the update attempt. Values can be one of the following:

    - ``True``: Database updated successfully
    - ``False``: Problem updating database
    - ``None``: Database already up-to-date

    cache_valid_time

        .. versionadded:: 2016.11.0

        Skip refreshing the package database if refresh has already occurred within
        <value> seconds

    failhard

        If False, return results of Err lines as ``False`` for the package database that
        encountered the error.
        If True, raise an error with a list of the package databases that encountered
        errors.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    """
    # Remove rtag file to keep multiple refreshes from happening in pkg states
    salt.utils.pkg.clear_rtag(__opts__)
    failhard = salt.utils.data.is_true(failhard)
    ret = {}
    error_repos = list()

    if cache_valid_time:
        try:
            latest_update = os.stat(APT_LISTS_PATH).st_mtime
            now = time.time()
            log.debug(
                "now: %s, last update time: %s, expire after: %s seconds",
                now,
                latest_update,
                cache_valid_time,
            )
            if latest_update + cache_valid_time > now:
                return ret
        except TypeError as exp:
            log.warning(
                "expected integer for cache_valid_time parameter, failed with: %s", exp
            )
        except OSError as exp:
            log.warning("could not stat cache directory due to: %s", exp)

    call = _call_apt(["apt-get", "-q", "update"], scope=False)
    if call["retcode"] != 0:
        comment = ""
        if "stderr" in call:
            comment += call["stderr"]

        raise CommandExecutionError(comment)
    else:
        out = call["stdout"]

    for line in out.splitlines():
        cols = line.split()
        if not cols:
            continue
        ident = " ".join(cols[1:])
        if "Get" in cols[0]:
            # Strip filesize from end of line
            ident = re.sub(r" \[.+B\]$", "", ident)
            ret[ident] = True
        elif "Ign" in cols[0]:
            ret[ident] = False
        elif "Hit" in cols[0]:
            ret[ident] = None
        elif "Err" in cols[0]:
            ret[ident] = False
            error_repos.append(ident)

    if failhard and error_repos:
        raise CommandExecutionError(f"Error getting repos: {', '.join(error_repos)}")

    return ret


def install(
    name=None,
    refresh=False,
    fromrepo=None,
    skip_verify=False,
    debconf=None,
    pkgs=None,
    sources=None,
    reinstall=False,
    downloadonly=False,
    ignore_epoch=False,
    **kwargs,
):
    """
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any apt-get/dpkg commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Install the passed package, add refresh=True to update the dpkg database.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to install packages from a
        software repository. To install a package file manually, use the
        "sources" option.

        32-bit packages can be installed on 64-bit systems by appending the
        architecture designation (``:i386``, etc.) to the end of the package
        name.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to refresh the package database before installing.

    cache_valid_time

        .. versionadded:: 2016.11.0

        Skip refreshing the package database if refresh has already occurred within
        <value> seconds

    fromrepo
        Specify a package repository to install from
        (e.g., ``apt-get -t unstable install somepackage``)

    skip_verify
        Skip the GPG verification check (e.g., ``--allow-unauthenticated``, or
        ``--force-bad-verify`` for install from package file).

    debconf
        Provide the path to a debconf answers file, processed before
        installation.

    version
        Install a specific version of the package, e.g. 1.2.3~0ubuntu0. Ignored
        if "pkgs" or "sources" is passed.

        .. versionchanged:: 2018.3.0
            version can now contain comparison operators (e.g. ``>1.2.3``,
            ``<=2.0``, etc.)

    reinstall : False
        Specifying reinstall=True will use ``apt-get install --reinstall``
        rather than simply ``apt-get install`` for requested packages that are
        already installed.

        If a version is specified with the requested package, then ``apt-get
        install --reinstall`` will only be used if the installed version
        matches the requested version.

        .. versionadded:: 2015.8.0

    ignore_epoch : False
        Only used when the version of a package is specified using a comparison
        operator (e.g. ``>4.1``). If set to ``True``, then the epoch will be
        ignored when comparing the currently-installed version to the desired
        version.

        .. versionadded:: 2018.3.0

    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-0ubuntu0"}]'

    sources
        A list of DEB packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.  Dependencies are automatically resolved
        and marked as auto-installed.

        32-bit packages can be installed on 64-bit systems by appending the
        architecture designation (``:i386``, etc.) to the end of the package
        name.

        .. versionchanged:: 2014.7.0

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.deb"},{"bar": "salt://bar.deb"}]'

    force_yes
        Passes ``--force-yes`` to the apt-get command.  Don't use this unless
        you know what you're doing.

        .. versionadded:: 0.17.4

    install_recommends
        Whether to install the packages marked as recommended.  Default is True.

        .. versionadded:: 2015.5.0

    only_upgrade
        Only upgrade the packages, if they are already installed. Default is False.

        .. versionadded:: 2015.5.0

    force_conf_new
        Always install the new version of any configuration files.

        .. versionadded:: 2015.8.0

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    """
    _refresh_db = False
    if salt.utils.data.is_true(refresh):
        _refresh_db = True
        if "version" in kwargs and kwargs["version"]:
            _refresh_db = False
            _latest_version = latest_version(name, refresh=False, show_installed=True)
            _version = kwargs.get("version")
            # If the versions don't match, refresh is True, otherwise no need
            # to refresh
            if not _latest_version == _version:
                _refresh_db = True

        if pkgs:
            _refresh_db = False
            for pkg in pkgs:
                if isinstance(pkg, dict):
                    _name = next(iter(pkg.keys()))
                    _latest_version = latest_version(
                        _name, refresh=False, show_installed=True
                    )
                    _version = pkg[_name]
                    # If the versions don't match, refresh is True, otherwise
                    # no need to refresh
                    if not _latest_version == _version:
                        _refresh_db = True
                else:
                    # No version specified, so refresh should be True
                    _refresh_db = True

    if debconf:
        __salt__["debconf.set_file"](debconf)

    try:
        pkg_params, pkg_type = __salt__["pkg_resource.parse_targets"](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    # Support old "repo" argument
    repo = kwargs.get("repo", "")
    if not fromrepo and repo:
        fromrepo = repo

    if not pkg_params:
        return {}

    cmd_prefix = []

    old = list_pkgs()
    targets = []
    downgrade = []
    to_reinstall = {}
    errors = []
    if pkg_type == "repository":
        pkg_params_items = list(pkg_params.items())
        has_comparison = [
            x
            for x, y in pkg_params_items
            if y is not None and (y.startswith("<") or y.startswith(">"))
        ]
        _available = (
            list_repo_pkgs(*has_comparison, byrepo=False, **kwargs)
            if has_comparison
            else {}
        )
    else:
        pkg_params_items = []
        # we don't need to do the test below for every package in the list.
        # it either exists or doesn't. test once then loop.
        if "lowpkg.bin_pkg_info" in __salt__:
            for pkg_source in pkg_params:
                deb_info = __salt__["lowpkg.bin_pkg_info"](pkg_source)
                pkg_params_items.append(
                    [deb_info["name"], pkg_source, deb_info["version"]]
                )
        else:
            for pkg_source in pkg_params:
                log.error(
                    "pkg.install: Unable to get deb information for %s. "
                    "Version comparisons will be unavailable.",
                    pkg_source,
                )
                pkg_params_items.append([pkg_source])

    # Build command prefix
    cmd_prefix.extend(["apt-get", "-q", "-y"])
    if kwargs.get("force_yes", False):
        cmd_prefix.append("--force-yes")
    if "force_conf_new" in kwargs and kwargs["force_conf_new"]:
        cmd_prefix.extend(["-o", "DPkg::Options::=--force-confnew"])
    else:
        cmd_prefix.extend(
            [
                "-o",
                "DPkg::Options::=--force-confold",
                "-o",
                "DPkg::Options::=--force-confdef",
            ]
        )
    if "install_recommends" in kwargs:
        if not kwargs["install_recommends"]:
            cmd_prefix.append("--no-install-recommends")
        else:
            cmd_prefix.append("--install-recommends")
    if "only_upgrade" in kwargs and kwargs["only_upgrade"]:
        cmd_prefix.append("--only-upgrade")
    if skip_verify:
        cmd_prefix.append("--allow-unauthenticated")
    if fromrepo and pkg_type == "repository":
        cmd_prefix.extend(["-t", fromrepo])
    cmd_prefix.append("install")
    for pkg_item_list in pkg_params_items:
        if pkg_type == "repository":
            pkgname, version_num = pkg_item_list
            if name and pkgs is None and kwargs.get("version") and len(pkg_params) == 1:
                # Only use the 'version' param if 'name' was not specified as a
                # comma-separated list
                version_num = kwargs["version"]
        else:
            try:
                pkgname, pkgpath, version_num = pkg_item_list
            except ValueError:
                pkgname = None
                pkgpath = pkg_item_list[0]
                version_num = None

        if version_num is None:
            if pkg_type == "repository":
                if reinstall and pkgname in old:
                    to_reinstall[pkgname] = pkgname
                else:
                    targets.append(pkgname)
            else:
                targets.append(pkgpath)
        else:
            # If we are installing a package file and not one from the repo,
            # and version_num is not None, then we can assume that pkgname is
            # not None, since the only way version_num is not None is if DEB
            # metadata parsing was successful.
            if pkg_type == "repository":
                # Remove leading equals sign(s) to keep from building a pkgstr
                # with multiple equals (which would be invalid)
                version_num = version_num.lstrip("=")
                if pkgname in has_comparison:
                    candidates = _available.get(pkgname, [])
                    target = salt.utils.pkg.match_version(
                        version_num,
                        candidates,
                        cmp_func=version_cmp,
                        ignore_epoch=ignore_epoch,
                    )
                    if target is None:
                        errors.append(
                            f"No version matching '{pkgname}{version_num}' could be found "
                            f"(available: {', '.join(candidates) if candidates else None})"
                        )
                        continue
                    else:
                        version_num = target
                pkgstr = f"{pkgname}={version_num}"
            else:
                pkgstr = pkgpath

            cver = old.get(pkgname, "")
            if (
                reinstall
                and cver
                and salt.utils.versions.compare(
                    ver1=version_num, oper="==", ver2=cver, cmp_func=version_cmp
                )
            ):
                to_reinstall[pkgname] = pkgstr
            elif not cver or salt.utils.versions.compare(
                ver1=version_num, oper=">=", ver2=cver, cmp_func=version_cmp
            ):
                targets.append(pkgstr)
            else:
                downgrade.append(pkgstr)

    if fromrepo and not sources:
        log.info("Targeting repo '%s'", fromrepo)

    cmds = []
    all_pkgs = []
    if targets:
        all_pkgs.extend(targets)
        cmd = copy.deepcopy(cmd_prefix)
        cmd.extend(targets)
        cmds.append(cmd)

    if downgrade:
        cmd = copy.deepcopy(cmd_prefix)
        if pkg_type == "repository" and "--force-yes" not in cmd:
            # Downgrading requires --force-yes. Insert this before 'install'
            cmd.insert(-1, "--force-yes")
        cmd.extend(downgrade)
        cmds.append(cmd)

    if downloadonly:
        cmd.append("--download-only")

    if to_reinstall:
        all_pkgs.extend(to_reinstall)
        cmd = copy.deepcopy(cmd_prefix)
        if not sources:
            cmd.append("--reinstall")
        cmd.extend([x for x in to_reinstall.values()])
        cmds.append(cmd)

    if not cmds:
        ret = {}
    else:
        cache_valid_time = kwargs.pop("cache_valid_time", 0)
        if _refresh_db:
            refresh_db(cache_valid_time)

        env = _parse_env(kwargs.get("env"))
        env.update(DPKG_ENV_VARS.copy())

        hold_pkgs = get_selections(state="hold").get("hold", [])
        # all_pkgs contains the argument to be passed to apt-get install, which
        # when a specific version is requested will be in the format
        # name=version.  Strip off the '=' if present so we can compare the
        # held package names against the packages we are trying to install.
        targeted_names = [x.split("=")[0] for x in all_pkgs]
        to_unhold = [x for x in hold_pkgs if x in targeted_names]

        if to_unhold:
            unhold(pkgs=to_unhold)

        for cmd in cmds:
            out = _call_apt(cmd, **kwargs)
            if out["retcode"] != 0 and out["stderr"]:
                errors.append(out["stderr"])

        __context__.pop("pkg.list_pkgs", None)
        new = list_pkgs()
        ret = salt.utils.data.compare_dicts(old, new)

        for pkgname in to_reinstall:
            if pkgname not in ret or pkgname in old:
                ret.update(
                    {
                        pkgname: {
                            "old": old.get(pkgname, ""),
                            "new": new.get(pkgname, ""),
                        }
                    }
                )

        if to_unhold:
            hold(pkgs=to_unhold)

    if errors:
        raise CommandExecutionError(
            "Problem encountered installing package(s)",
            info={"errors": errors, "changes": ret},
        )

    return ret


def _uninstall(action="remove", name=None, pkgs=None, **kwargs):
    """
    remove and purge do identical things but with different apt-get commands,
    this function performs the common logic.
    """
    try:
        pkg_params = __salt__["pkg_resource.parse_targets"](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    old_removed = list_pkgs(removed=True)
    targets = salt.utils.pkg.match_wildcard(old, pkg_params)
    if action == "purge":
        targets.update(salt.utils.pkg.match_wildcard(old_removed, pkg_params))
    if not targets:
        return {}
    cmd = ["apt-get", "-q", "-y", action]
    cmd.extend(targets)
    env = _parse_env(kwargs.get("env"))
    env.update(DPKG_ENV_VARS.copy())
    out = _call_apt(cmd, env=env)
    if out["retcode"] != 0 and out["stderr"]:
        errors = [out["stderr"]]
    else:
        errors = []

    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    new_removed = list_pkgs(removed=True)

    changes = salt.utils.data.compare_dicts(old, new)
    if action == "purge":
        ret = {
            "removed": salt.utils.data.compare_dicts(old_removed, new_removed),
            "installed": changes,
        }
    else:
        ret = changes

    if errors:
        raise CommandExecutionError(
            "Problem encountered removing package(s)",
            info={"errors": errors, "changes": ret},
        )

    return ret


def autoremove(list_only=False, purge=False):
    """
    .. versionadded:: 2015.5.0

    Remove packages not required by another package using ``apt-get
    autoremove``.

    list_only : False
        Only retrieve the list of packages to be auto-removed, do not actually
        perform the auto-removal.

    purge : False
        Also remove package config data when autoremoving packages.

        .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.autoremove
        salt '*' pkg.autoremove list_only=True
        salt '*' pkg.autoremove purge=True
    """
    cmd = []
    if list_only:
        ret = []
        cmd.extend(["apt-get", "--assume-no"])
        if purge:
            cmd.append("--purge")
        cmd.append("autoremove")
        out = _call_apt(cmd, ignore_retcode=True)["stdout"]
        found = False
        for line in out.splitlines():
            if found is True:
                if line.startswith(" "):
                    ret.extend(line.split())
                else:
                    found = False
            elif "The following packages will be REMOVED:" in line:
                found = True
        ret.sort()
        return ret
    else:
        old = list_pkgs()
        cmd.extend(["apt-get", "--assume-yes"])
        if purge:
            cmd.append("--purge")
        cmd.append("autoremove")
        _call_apt(cmd, ignore_retcode=True)
        __context__.pop("pkg.list_pkgs", None)
        new = list_pkgs()
        return salt.utils.data.compare_dicts(old, new)


def remove(name=None, pkgs=None, **kwargs):
    """
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any apt-get/dpkg commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Remove packages using ``apt-get remove``.

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
    return _uninstall(action="remove", name=name, pkgs=pkgs, **kwargs)


def purge(name=None, pkgs=None, **kwargs):
    """
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any apt-get/dpkg commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Remove packages via ``apt-get purge`` along with all configuration files.

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
    return _uninstall(action="purge", name=name, pkgs=pkgs, **kwargs)


def upgrade(refresh=True, dist_upgrade=False, **kwargs):
    """
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any apt-get/dpkg commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Upgrades all packages via ``apt-get upgrade`` or ``apt-get dist-upgrade``
    if  ``dist_upgrade`` is ``True``.

    Returns a dictionary containing the changes:

    .. code-block:: python

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}

    dist_upgrade
        Whether to perform the upgrade using dist-upgrade vs upgrade.  Default
        is to use upgrade.

        .. versionadded:: 2014.7.0

    refresh : True
        If ``True``, the apt cache will be refreshed first. By default,
        this is ``True`` and a refresh is performed.

    cache_valid_time

        .. versionadded:: 2016.11.0

        Skip refreshing the package database if refresh has already occurred within
        <value> seconds

    download_only (or downloadonly)
        Only download the packages, don't unpack or install them. Use
        downloadonly to be in line with yum and zypper module.

        .. versionadded:: 2018.3.0

    force_conf_new
        Always install the new version of any configuration files.

        .. versionadded:: 2015.8.0

    allow_downgrades
        Allow apt to downgrade packages without a prompt.

        .. versionadded:: 3005

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    """
    cache_valid_time = kwargs.pop("cache_valid_time", 0)
    if salt.utils.data.is_true(refresh):
        refresh_db(cache_valid_time)

    old = list_pkgs()
    if "force_conf_new" in kwargs and kwargs["force_conf_new"]:
        dpkg_options = ["--force-confnew"]
    else:
        dpkg_options = ["--force-confold", "--force-confdef"]
    cmd = [
        "apt-get",
        "-q",
        "-y",
    ]
    for option in dpkg_options:
        cmd.append("-o")
        cmd.append(f"DPkg::Options::={option}")

    if kwargs.get("force_yes", False):
        cmd.append("--force-yes")
    if kwargs.get("skip_verify", False):
        cmd.append("--allow-unauthenticated")
    if kwargs.get("download_only", False) or kwargs.get("downloadonly", False):
        cmd.append("--download-only")
    if kwargs.get("allow_downgrades", False):
        cmd.append("--allow-downgrades")

    cmd.append("dist-upgrade" if dist_upgrade else "upgrade")
    result = _call_apt(cmd, env=DPKG_ENV_VARS.copy())
    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if result["retcode"] != 0:
        raise CommandExecutionError(
            "Problem encountered upgrading packages",
            info={"changes": ret, "result": result},
        )

    return ret


def hold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    """
    .. versionadded:: 2014.7.0

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

        state = get_selections(pattern=target, state="hold")
        if not state:
            ret[target]["comment"] = f"Package {target} not currently held."
        elif not salt.utils.data.is_true(state.get("hold", False)):
            if "test" in __opts__ and __opts__["test"]:
                ret[target].update(result=None)
                ret[target]["comment"] = f"Package {target} is set to be held."
            else:
                result = set_selections(selection={"hold": [target]})
                ret[target].update(changes=result[target], result=True)
                ret[target]["comment"] = f"Package {target} is now being held."
        else:
            ret[target].update(result=True)
            ret[target]["comment"] = f"Package {target} is already set to be held."
    return ret


def unhold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    """
    .. versionadded:: 2014.7.0

    Set package current in 'hold' state to install state,
    meaning it will be upgraded.

    name
        The name of the package, e.g., 'tmux'

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.unhold <package name>

    pkgs
        A list of packages to unhold. Must be passed as a python list.

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

        state = get_selections(pattern=target)
        if not state:
            ret[target]["comment"] = f"Package {target} does not have a state."
        elif salt.utils.data.is_true(state.get("hold", False)):
            if "test" in __opts__ and __opts__["test"]:
                ret[target].update(result=None)
                ret[target]["comment"] = f"Package {target} is set not to be held."
            else:
                result = set_selections(selection={"install": [target]})
                ret[target].update(changes=result[target], result=True)
                ret[target]["comment"] = f"Package {target} is no longer being held."
        else:
            ret[target].update(result=True)
            ret[target]["comment"] = f"Package {target} is already set not to be held."
    return ret


def _list_pkgs_from_context(versions_as_list, removed, purge_desired):
    """
    Use pkg list from __context__
    """
    if removed:
        ret = copy.deepcopy(__context__["pkg.list_pkgs"]["removed"])
    else:
        ret = copy.deepcopy(__context__["pkg.list_pkgs"]["purge_desired"])
        if not purge_desired:
            ret.update(__context__["pkg.list_pkgs"]["installed"])
    if not versions_as_list:
        __salt__["pkg_resource.stringify"](ret)
    return ret


def list_pkgs(
    versions_as_list=False, removed=False, purge_desired=False, **kwargs
):  # pylint: disable=W0613
    """
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    removed
        If ``True``, then only packages which have been removed (but not
        purged) will be returned.

    purge_desired
        If ``True``, then only packages which have been marked to be purged,
        but can't be purged due to their status as dependencies for other
        installed packages, will be returned. Note that these packages will
        appear in installed

        .. versionchanged:: 2014.1.1

            Packages in this state now correctly show up in the output of this
            function.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs versions_as_list=True
    """
    versions_as_list = salt.utils.data.is_true(versions_as_list)
    removed = salt.utils.data.is_true(removed)
    purge_desired = salt.utils.data.is_true(purge_desired)

    if "pkg.list_pkgs" in __context__ and kwargs.get("use_context", True):
        return _list_pkgs_from_context(versions_as_list, removed, purge_desired)

    ret = {"installed": {}, "removed": {}, "purge_desired": {}}
    cmd = [
        "dpkg-query",
        "--showformat",
        "${Status} ${Package} ${Version} ${Architecture}\n",
        "-W",
    ]

    out = __salt__["cmd.run_stdout"](cmd, output_loglevel="trace", python_shell=False)
    # Typical lines of output:
    # install ok installed zsh 4.3.17-1ubuntu1 amd64
    # deinstall ok config-files mc 3:4.8.1-2ubuntu1 amd64
    for line in out.splitlines():
        cols = line.split()
        try:
            linetype, status, name, version_num, arch = (
                cols[x] for x in (0, 2, 3, 4, 5)
            )
        except (ValueError, IndexError):
            continue
        if __grains__.get("cpuarch", "") == "x86_64":
            osarch = __grains__.get("osarch", "")
            if arch != "all" and osarch == "amd64" and osarch != arch:
                name += f":{arch}"
        if cols:
            if ("install" in linetype or "hold" in linetype) and "installed" in status:
                __salt__["pkg_resource.add_pkg"](ret["installed"], name, version_num)
            elif "deinstall" in linetype:
                __salt__["pkg_resource.add_pkg"](ret["removed"], name, version_num)
            elif "purge" in linetype and status == "installed":
                __salt__["pkg_resource.add_pkg"](
                    ret["purge_desired"], name, version_num
                )

    for pkglist_type in ("installed", "removed", "purge_desired"):
        __salt__["pkg_resource.sort_pkglist"](ret[pkglist_type])

    __context__["pkg.list_pkgs"] = copy.deepcopy(ret)

    if removed:
        ret = ret["removed"]
    else:
        ret = copy.deepcopy(__context__["pkg.list_pkgs"]["purge_desired"])
        if not purge_desired:
            ret.update(__context__["pkg.list_pkgs"]["installed"])
    if not versions_as_list:
        __salt__["pkg_resource.stringify"](ret)
    return ret


def _get_upgradable(dist_upgrade=True, **kwargs):
    """
    Utility function to get upgradable packages

    Sample return data:
    { 'pkgname': '1.2.3-45', ... }
    """

    cmd = ["apt-get", "--just-print"]
    if dist_upgrade:
        cmd.append("dist-upgrade")
    else:
        cmd.append("upgrade")
    try:
        cmd.extend(["-o", f"APT::Default-Release={kwargs['fromrepo']}"])
    except KeyError:
        pass

    call = _call_apt(cmd)
    if call["retcode"] != 0:
        msg = "Failed to get upgrades"
        for key in ("stderr", "stdout"):
            if call[key]:
                msg += ": " + call[key]
                break
        raise CommandExecutionError(msg)
    else:
        out = call["stdout"]

    # rexp parses lines that look like the following:
    # Conf libxfont1 (1:1.4.5-1 Debian:testing [i386])
    rexp = re.compile(r"(?m)^Conf ([^ ]+) \(([^ ]+)")  # Package name  # Version
    keys = ["name", "version"]

    def _get(line, k):
        return line[keys.index(k)]

    upgrades = rexp.findall(out)

    ret = {}
    for line in upgrades:
        name = _get(line, "name")
        version_num = _get(line, "version")
        ret[name] = version_num

    return ret


def list_upgrades(refresh=True, dist_upgrade=True, **kwargs):
    """
    List all available package upgrades.

    refresh
        Whether to refresh the package database before listing upgrades.
        Default: True.

    cache_valid_time

        .. versionadded:: 2016.11.0

        Skip refreshing the package database if refresh has already occurred within
        <value> seconds

    dist_upgrade
        Whether to list the upgrades using dist-upgrade vs upgrade.  Default is
        to use dist-upgrade.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    """
    cache_valid_time = kwargs.pop("cache_valid_time", 0)
    if salt.utils.data.is_true(refresh):
        refresh_db(cache_valid_time)
    return _get_upgradable(dist_upgrade, **kwargs)


def upgrade_available(name, **kwargs):
    """
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    """
    return latest_version(name) != ""


def version_cmp(pkg1, pkg2, ignore_epoch=False, **kwargs):
    """
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    ignore_epoch : False
        Set to ``True`` to ignore the epoch when comparing versions

        .. versionadded:: 2015.8.10,2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '0.2.4-0ubuntu1' '0.2.4.1-0ubuntu1'
    """

    def normalize(x):
        return str(x).split(":", 1)[-1] if ignore_epoch else str(x)

    # both apt_pkg.version_compare and _cmd_quote need string arguments.
    pkg1 = normalize(pkg1)
    pkg2 = normalize(pkg2)

    # if we have apt_pkg, this will be quickier this way
    # and also do not rely on shell.
    try:
        for oper, ret in (("lt", -1), ("eq", 0), ("gt", 1)):
            cmd = ["dpkg", "--compare-versions", pkg1, oper, pkg2]
            retcode = __salt__["cmd.retcode"](
                cmd, output_loglevel="trace", python_shell=False, ignore_retcode=True
            )
            if retcode == 0:
                return ret
    except Exception as exc:  # pylint: disable=broad-except
        log.error(exc)
    return None


def _split_repo_str(repo):
    """
    Return APT source entry as a dictionary
    """
    entry = SourceEntry(repo)
    invalid = entry.invalid
    signedby = entry.signedby

    return {
        "invalid": invalid,
        "type": entry.type,
        "architectures": entry.architectures,
        "uri": entry.uri,
        "dist": entry.dist,
        "comps": entry.comps,
        "signedby": signedby,
    }


def _consolidate_repo_sources(sources):
    """
    Consolidate APT sources.
    """
    if not isinstance(sources, SourcesList):
        raise TypeError(f"'{type(sources)}' not a '{SourcesList}'")

    consolidated = {}
    delete_files = set()
    base_file = SourceEntry("").file

    repos = [s for s in sources.list if not s.invalid]

    for repo in repos:
        key = str(
            (
                getattr(repo, "architectures", []),
                repo.disabled,
                repo.type,
                repo.uri,
                repo.dist,
            )
        )
        if key in consolidated:
            combined = consolidated[key]
            combined_comps = set(repo.comps).union(set(combined.comps))
            consolidated[key].comps = list(combined_comps)
        else:
            consolidated[key] = SourceEntry(repo.line)

        if repo.file != base_file:
            delete_files.add(repo.file)

    sources.list = list(consolidated.values())
    sources.save()
    for file_ in delete_files:
        try:
            os.remove(file_)
        except OSError:
            pass
    return sources


def list_repo_pkgs(*args, **kwargs):  # pylint: disable=unused-import
    """
    .. versionadded:: 2017.7.0

    Returns all available packages. Optionally, package names (and name globs)
    can be passed and the results will be filtered to packages matching those
    names.

    This function can be helpful in discovering the version or repo to specify
    in a :mod:`pkg.installed <salt.states.pkg.installed>` state.

    The return data will be a dictionary mapping package names to a list of
    version numbers, ordered from newest to oldest. For example:

    .. code-block:: python

        {
            'bash': ['4.3-14ubuntu1.1',
                     '4.3-14ubuntu1'],
            'nginx': ['1.10.0-0ubuntu0.16.04.4',
                      '1.9.15-0ubuntu1']
        }

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_repo_pkgs
        salt '*' pkg.list_repo_pkgs foo bar baz
    """
    if args:
        # Get only information about packages in args
        cmd = ["apt-cache", "show"] + [arg for arg in args]
    else:
        # Get information about all available packages
        cmd = ["apt-cache", "dump"]

    out = _call_apt(cmd, scope=False, ignore_retcode=True)

    ret = {}
    pkg_name = None
    new_pkg = re.compile("^Package: (.+)")
    for line in salt.utils.itertools.split(out["stdout"], "\n"):
        if not line.strip():
            continue
        try:
            cur_pkg = new_pkg.match(line).group(1)
        except AttributeError:
            pass
        else:
            if cur_pkg != pkg_name:
                pkg_name = cur_pkg
                continue
        comps = line.strip().split(None, 1)
        if comps[0] == "Version:":
            ret.setdefault(pkg_name, []).append(comps[1])

    return ret


def _skip_source(source):
    """
    Decide to skip source or not.

    :param source:
    :return:
    """
    if source.invalid:
        if (
            source.uri
            and source.type
            and source.type in ("deb", "deb-src", "rpm", "rpm-src")
        ):
            pieces = source.mysplit(source.line)
            if pieces[1].strip()[0] == "[":
                options = pieces.pop(1).strip("[]").split()
                if len(options) > 0:
                    log.debug(
                        "Source %s will be included although is marked invalid",
                        source.uri,
                    )
                    return False
            return True
        else:
            return True
    return False


def list_repos(**kwargs):
    """
    Lists all repos in the sources.list (and sources.lists.d) files

    CLI Example:

    .. code-block:: bash

       salt '*' pkg.list_repos
       salt '*' pkg.list_repos disabled=True
    """
    repos = {}
    sources = SourcesList()
    for source in sources.list:
        if _skip_source(source):
            continue
        signedby = source.signedby
        repo = {}
        repo["file"] = source.file
        repo["comps"] = getattr(source, "comps", [])
        repo["disabled"] = source.disabled
        repo["dist"] = source.dist
        repo["type"] = source.type
        repo["uri"] = source.uri
        repo["line"] = source.line.strip()
        repo["architectures"] = getattr(source, "architectures", [])
        repo["signedby"] = signedby
        repos.setdefault(source.uri, []).append(repo)
    return repos


def get_repo(repo, **kwargs):
    """
    Display a repo from the sources.list / sources.list.d

    The repo passed in needs to be a complete repo entry.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.get_repo "myrepo definition"
    """
    ppa_auth = kwargs.get("ppa_auth", None)
    # we have to be clever about this since the repo definition formats
    # are a bit more "loose" than in some other distributions
    if repo.startswith("ppa:") and __grains__["os"] in ("Ubuntu", "Mint", "neon"):
        # This is a PPA definition meaning special handling is needed
        # to derive the name.
        dist = __grains__["oscodename"]
        owner_name, ppa_name = repo[4:].split("/")
        if ppa_auth:
            auth_info = f"{ppa_auth}@"
            repo = LP_PVT_SRC_FORMAT.format(auth_info, owner_name, ppa_name, dist)
        else:
            repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)

    repos = list_repos()

    if repos:
        try:
            repo_entry = _split_repo_str(repo)
            if ppa_auth:
                uri_match = re.search("(http[s]?://)(.+)", repo_entry["uri"])
                if uri_match:
                    if not uri_match.group(2).startswith(ppa_auth):
                        repo_entry["uri"] = (
                            f"{uri_match.group(1)}{ppa_auth}@{uri_match.group(2)}"
                        )
        except SyntaxError:
            raise CommandExecutionError(
                f"Error: repo '{repo}' is not a well formatted definition"
            )

        for source in repos.values():
            for sub in source:
                if (
                    sub["type"] == repo_entry["type"]
                    and sub["uri"].rstrip("/") == repo_entry["uri"].rstrip("/")
                    and sub["dist"] == repo_entry["dist"]
                ):
                    if not repo_entry["comps"]:
                        return sub
                    for comp in repo_entry["comps"]:
                        if comp in sub.get("comps", []):
                            return sub
    return {}


def del_repo(repo, **kwargs):
    """
    Delete a repo from the sources.list / sources.list.d

    If the .list file is in the sources.list.d directory
    and the file that the repo exists in does not contain any other
    repo configuration, the file itself will be deleted.

    The repo passed in must be a fully formed repository definition
    string.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo "myrepo definition"
    """
    is_ppa = False
    if repo.startswith("ppa:") and __grains__["os"] in ("Ubuntu", "Mint", "neon"):
        # This is a PPA definition meaning special handling is needed
        # to derive the name.
        is_ppa = True
        dist = __grains__["oscodename"]
        owner_name, ppa_name = repo[4:].split("/")
        if "ppa_auth" in kwargs:
            auth_info = f"{kwargs['ppa_auth']}@"
            repo = LP_PVT_SRC_FORMAT.format(auth_info, dist, owner_name, ppa_name)
        else:
            repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)

    sources = SourcesList()
    repos = [s for s in sources.list if not s.invalid]
    if repos:
        deleted_from = dict()
        try:
            repo_entry = _split_repo_str(repo)
        except SyntaxError:
            raise SaltInvocationError(
                f"Error: repo '{repo}' not a well formatted definition"
            )

        for source in repos:
            if (
                source.type == repo_entry["type"]
                and source.architectures == repo_entry["architectures"]
                and source.uri.rstrip("/") == repo_entry["uri"].rstrip("/")
                and source.dist == repo_entry["dist"]
            ):

                s_comps = set(source.comps)
                r_comps = set(repo_entry["comps"])
                if s_comps.intersection(r_comps) or (not s_comps and not r_comps):
                    deleted_from[source.file] = 0
                    source.comps = list(s_comps.difference(r_comps))
                    if not source.comps:
                        try:
                            sources.remove(source)
                        except ValueError:
                            pass
            # PPAs are special and can add deb-src where expand_ppa_line
            # doesn't always reflect this.  Lets just cleanup here for good
            # measure
            if (
                is_ppa
                and repo_entry["type"] == "deb"
                and source.type == "deb-src"
                and source.uri == repo_entry["uri"]
                and source.dist == repo_entry["dist"]
            ):

                s_comps = set(source.comps)
                r_comps = set(repo_entry["comps"])
                if s_comps.intersection(r_comps) or (not s_comps and not r_comps):
                    deleted_from[source.file] = 0
                    source.comps = list(s_comps.difference(r_comps))
                    if not source.comps:
                        try:
                            sources.remove(source)
                        except ValueError:
                            pass
            sources.save()
        if deleted_from:
            ret = ""
            for source in sources:
                if source.file in deleted_from:
                    deleted_from[source.file] += 1
            for repo_file, count in deleted_from.items():
                msg = "Repo '{0}' has been removed from {1}.\n"
                if count == 0 and "sources.list.d/" in repo_file:
                    if os.path.isfile(repo_file):
                        msg = "File {1} containing repo '{0}' has been removed."
                        try:
                            os.remove(repo_file)
                        except OSError:
                            pass
                ret += msg.format(repo, repo_file)
            # explicit refresh after a repo is deleted
            refresh_db()
            return ret

    raise CommandExecutionError(f"Repo {repo} doesn't exist in the sources.list(s)")


def _convert_if_int(value):
    """
    .. versionadded:: 2017.7.0

    Convert to an int if necessary.

    :param str value: The value to check/convert.

    :return: The converted or passed value.
    :rtype: bool|int|str
    """
    try:
        value = int(str(value))
    except ValueError:
        pass
    return value


def _parse_repo_keys_output(cmd_ret):
    """ """
    ret = dict()
    repo_keys = list()

    lines = [line for line in cmd_ret.splitlines() if line.strip()]

    # Reference for the meaning of each item in the colon-separated
    # record can be found here: https://goo.gl/KIZbvp
    for line in lines:
        items = [
            _convert_if_int(item.strip()) if item.strip() else None
            for item in line.split(":")
        ]
        key_props = dict()

        if len(items) < 2:
            log.debug("Skipping line: %s", line)
            continue

        if items[0] in ("pub", "sub"):
            key_props.update(
                {
                    "algorithm": items[3],
                    "bits": items[2],
                    "capability": items[11],
                    "date_creation": items[5],
                    "date_expiration": items[6],
                    "keyid": str(items[4]),
                    "validity": items[1],
                }
            )

            if items[0] == "pub":
                repo_keys.append(key_props)
            else:
                repo_keys[-1]["subkey"] = key_props
        elif items[0] == "fpr":
            if repo_keys[-1].get("subkey", False):
                repo_keys[-1]["subkey"].update({"fingerprint": items[9]})
            else:
                repo_keys[-1].update({"fingerprint": items[9]})
        elif items[0] == "uid":
            repo_keys[-1].update({"uid": items[9], "uid_hash": items[7]})

    for repo_key in repo_keys:
        ret[repo_key["keyid"]] = repo_key
    return ret


def get_repo_keys(aptkey=True, keydir=None):
    """
    .. versionadded:: 2017.7.0

    List known repo key details.
    :param bool aptkey: Use the binary apt-key.
    :param str keydir: The directory path to save keys. The default directory
    is /etc/apt/keyrings/ which is the recommended path
    for adding third party keys. This argument is only used
    when aptkey is False.

    :return: A dictionary containing the repo keys.
    :rtype: dict

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.get_repo_keys
    """
    if not salt.utils.path.which("apt-key"):
        aptkey = False

    if not aptkey:
        if not keydir:
            keydir = pathlib.Path("/etc", "apt", "keyrings")
        if not isinstance(keydir, pathlib.Path):
            keydir = pathlib.Path(keydir)

        if not keydir.is_dir():
            log.error(
                "The directory %s does not exist. Please create this directory only writable by root",
                keydir,
            )
            return False

        ret_output = []
        for file in os.listdir(str(keydir)):
            key_file = keydir / file
            cmd_ret = __salt__["cmd.run_all"](
                [
                    "gpg",
                    "--no-default-keyring",
                    "--keyring",
                    key_file,
                    "--list-keys",
                    "--with-colons",
                ]
            )
            ret_output.append(cmd_ret["stdout"])

        ret = _parse_repo_keys_output(" ".join(ret_output))
    # The double usage of '--with-fingerprint' is necessary in order to
    # retrieve the fingerprint of the subkey.
    else:
        cmd = [
            "apt-key",
            "adv",
            "--batch",
            "--list-public-keys",
            "--with-fingerprint",
            "--with-fingerprint",
            "--with-colons",
            "--fixed-list-mode",
        ]

        cmd_ret = _call_apt(cmd, scope=False)
        if cmd_ret["retcode"] != 0:
            log.error(cmd_ret["stderr"])
            return ret

        ret = _parse_repo_keys_output(cmd_ret["stdout"])
    return ret


def _decrypt_key(key):
    """
    Check if the key needs to be decrypted. If it needs
    to be decrypt it, do so with the gpg binary.
    """
    try:
        with salt.utils.files.fopen(key, "r") as fp:
            if fp.read().strip("-").startswith("BEGIN PGP"):
                if not salt.utils.path.which("gpg"):
                    log.error(
                        "Detected an ASCII armored key %s and the gpg binary is not available. Not decrypting the key.",
                        key,
                    )
                    return False
                decrypted_key = str(key) + ".decrypted"
                cmd = ["gpg", "--yes", "--output", decrypted_key, "--dearmor", key]
                if not __salt__["cmd.run_all"](cmd)["retcode"] == 0:
                    log.error("Failed to decrypt the key %s", key)
                return decrypted_key
    except UnicodeDecodeError:
        log.debug("Key is not ASCII Armored. Do not need to decrypt")
    return key


def add_repo_key(
    path=None,
    text=None,
    keyserver=None,
    keyid=None,
    saltenv="base",
    aptkey=True,
    keydir=None,
    keyfile=None,
):
    """
    .. versionadded:: 2017.7.0

    Add a repo key using ``apt-key add``.

    :param str path: The path of the key file to import.
    :param str text: The key data to import, in string form.
    :param str keyserver: The server to download the repo key specified by the keyid.
    :param str keyid: The key id of the repo key to add.
    :param str saltenv: The environment the key file resides in.
    :param bool aptkey: Use the binary apt-key.
    :param str keydir: The directory path to save keys. The default directory
                       is /etc/apt/keyrings/ which is the recommended path
                       for adding third party keys. This argument is only used
                       when aptkey is False.

    :param str keyfile: The name of the key to add. This is only required when
                        aptkey is False and you are using a keyserver. This
                        argument is only used when aptkey is False.

    :return: A boolean representing whether the repo key was added.
    :rtype: bool

    .. warning::
       The apt-key binary is deprecated and will last be available
       in Debian 11 and Ubuntu 22.04. It is recommended to use aptkey=False
       when using this module.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.add_repo_key 'salt://apt/sources/test.key'

        salt '*' pkg.add_repo_key text="'$KEY1'"

        salt '*' pkg.add_repo_key keyserver='keyserver.example' keyid='0000AAAA'
    """
    if not keydir:
        keydir = pathlib.Path("/etc", "apt", "keyrings")
    if not isinstance(keydir, pathlib.Path):
        keydir = pathlib.Path(keydir)
    if not aptkey and not keydir.is_dir():
        log.error(
            "The directory %s does not exist. Please create this directory only writable by root",
            keydir,
        )
        return False

    if not salt.utils.path.which("apt-key"):
        aptkey = False
    cmd = ["apt-key"]
    kwargs = {}

    # If the keyid is provided or determined, check it against the existing
    # repo key ids to determine whether it needs to be imported.
    if keyid:
        for current_keyid in get_repo_keys(aptkey=aptkey, keydir=keydir):
            if current_keyid[-(len(keyid)) :] == keyid:
                log.debug("The keyid '%s' already present: %s", keyid, current_keyid)
                return True

    if path:
        cached_source_path = __salt__["cp.cache_file"](path, saltenv)

        if not cached_source_path:
            log.error("Unable to get cached copy of file: %s", path)
            return False

        if not aptkey:
            key = _decrypt_key(cached_source_path)
            if not key:
                return False
            key = pathlib.Path(str(key))
            if not keyfile:
                keyfile = key.name
                if keyfile.endswith(".decrypted"):
                    keyfile = keyfile[:-10]
            shutil.copyfile(str(key), str(keydir / keyfile))
            return True
        else:
            cmd.extend(["add", cached_source_path])
    elif text:
        log.debug("Received value: %s", text)

        cmd.extend(["add", "-"])
        kwargs.update({"stdin": text})
    elif keyserver:
        if not keyid:
            error_msg = f"No keyid or keyid too short for keyserver: {keyserver}"
            raise SaltInvocationError(error_msg)

        if not aptkey:
            if not keyfile:
                log.error(
                    "You must define the name of the key file to save the key. See keyfile argument"
                )
                return False
            cmd = [
                "gpg",
                "--no-default-keyring",
                "--keyring",
                keydir / keyfile,
                "--keyserver",
                keyserver,
                "--recv-keys",
                keyid,
            ]
        else:
            cmd.extend(["adv", "--batch", "--keyserver", keyserver, "--recv", keyid])
    elif keyid:
        error_msg = f"No keyserver specified for keyid: {keyid}"
        raise SaltInvocationError(error_msg)
    else:
        raise TypeError(
            f"{add_repo_key.__name__}() takes at least 1 argument (0 given)"
        )

    cmd_ret = _call_apt(cmd, **kwargs)

    if cmd_ret["retcode"] == 0:
        return True
    log.error("Unable to add repo key: %s", cmd_ret["stderr"])
    return False


def _get_key_from_id(keydir, keyid):
    """
    Find and return the key file from the keyid.
    """
    if not len(keyid) in (8, 16):
        log.error("The keyid needs to be either 8 or 16 characters")
        return False
    for file in os.listdir(str(keydir)):
        key_file = keydir / file
        key_output = __salt__["cmd.run_all"](
            [
                "gpg",
                "--no-default-keyring",
                "--keyring",
                key_file,
                "--list-keys",
                "--with-colons",
            ]
        )
        ret = _parse_repo_keys_output(key_output["stdout"])
        for key in ret:
            if ret[key]["keyid"].endswith(keyid):
                return key_file
    log.error("Could not find the key file for keyid: %s", keyid)
    return False


def del_repo_key(name=None, aptkey=True, keydir=None, **kwargs):
    """
    .. versionadded:: 2015.8.0

    Remove a repo key using ``apt-key del``

    name
        Repo from which to remove the key. Unnecessary if ``keyid`` is passed.

    keyid
        The KeyID of the GPG key to remove

    keyid_ppa : False
        If set to ``True``, the repo's GPG key ID will be looked up from
        ppa.launchpad.net and removed.

        .. note::

            Setting this option to ``True`` requires that the ``name`` param
            also be passed.

    aptkey
        Use the binary apt-key.

    keydir
        The directory path to save keys. The default directory
        is /etc/apt/keyrings/ which is the recommended path
        for adding third party keys.

    .. warning::
       The apt-key binary is deprecated and will last be available
       in Debian 11 and Ubuntu 22.04. It is recommended to use aptkey=False
       when using this module.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo_key keyid=0123ABCD
        salt '*' pkg.del_repo_key name='ppa:foo/bar' keyid_ppa=True
    """
    if not keydir:
        keydir = pathlib.Path("/etc", "apt", "keyrings")
    if not isinstance(keydir, pathlib.Path):
        keydir = pathlib.Path(keydir)
    if not aptkey and not keydir.is_dir():
        log.error(
            "The directory %s does not exist. Please create this directory only writable by root",
            keydir,
        )
        return False

    if not salt.utils.path.which("apt-key"):
        aptkey = False

    if kwargs.get("keyid_ppa", False):
        if isinstance(name, str) and name.startswith("ppa:"):
            owner_name, ppa_name = name[4:].split("/")
            ppa_info = _get_ppa_info_from_launchpad(owner_name, ppa_name)
            keyid = ppa_info["signing_key_fingerprint"][-8:]
        else:
            raise SaltInvocationError("keyid_ppa requires that a PPA be passed")
    else:
        if "keyid" in kwargs:
            keyid = kwargs.get("keyid")
        else:
            raise SaltInvocationError("keyid or keyid_ppa and PPA name must be passed")

    if not aptkey:
        key_file = _get_key_from_id(keydir=keydir, keyid=keyid)
        if not key_file:
            return False
        pathlib.Path(key_file).unlink()
    else:
        result = _call_apt(["apt-key", "del", keyid], scope=False)
        if result["retcode"] != 0:
            msg = "Failed to remove keyid {0}"
            if result["stderr"]:
                msg += ": {}".format(result["stderr"])
            raise CommandExecutionError(msg)
    return keyid


def mod_repo(repo, saltenv="base", aptkey=True, **kwargs):
    """
    Modify one or more values for a repo.  If the repo does not exist, it will
    be created, so long as the definition is well formed.  For Ubuntu the
    ``ppa:<project>/repo`` format is acceptable. ``ppa:`` format can only be
    used to create a new repository.

    The following options are available to modify a repo definition:

    architectures
        A comma-separated list of supported architectures, e.g. ``amd64`` If
        this option is not set, all architectures (configured in the system)
        will be used.

    comps
        A comma separated list of components for the repo, e.g. ``main``

    file
        A file name to be used

    keyserver
        Keyserver to get gpg key from

    keyid
        Key ID or a list of key IDs to load with the ``keyserver`` argument

    key_url
        URL to a GPG key to add to the APT GPG keyring

    key_text
        GPG key in string form to add to the APT GPG keyring

        .. versionadded:: 2018.3.0

    consolidate : False
        If ``True``, will attempt to de-duplicate and consolidate sources

    comments
        Sometimes you want to supply additional information, but not as
        enabled configuration. All comments provided here will be joined
        into a single string and appended to the repo configuration with a
        comment marker (#) before it.

        .. versionadded:: 2015.8.9

    refresh : True
        Enable or disable (True or False) refreshing of the apt package
        database. The previous ``refresh_db`` argument was deprecated in
        favor of ``refresh```. The ``refresh_db`` argument will still
        continue to work to ensure backwards compatibility, but please
        change to using the preferred ``refresh``.

    .. note::
        Due to the way keys are stored for APT, there is a known issue where
        the key won't be updated unless another change is made at the same
        time. Keys should be properly added on initial configuration.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.mod_repo 'myrepo definition' uri=http://new/uri
        salt '*' pkg.mod_repo 'myrepo definition' comps=main,universe
    """
    if "refresh_db" in kwargs:
        refresh = kwargs["refresh_db"]
    else:
        refresh = kwargs.get("refresh", True)

    if not salt.utils.path.which("apt-key"):
        aptkey = False

    # to ensure no one sets some key values that _shouldn't_ be changed on the
    # object itself, this is just a white-list of "ok" to set properties
    if repo.startswith("ppa:"):
        if __grains__["os"] in ("Ubuntu", "Mint", "neon"):
            # secure PPAs cannot be supported as of the time of this code
            # implementation via apt-add-repository.  The code path for
            # secure PPAs should be the same as urllib method
            if salt.utils.path.which("apt-add-repository") and "ppa_auth" not in kwargs:
                repo_info = get_repo(repo)
                if repo_info:
                    return {repo: repo_info}
                else:
                    env = None
                    http_proxy_url = _get_http_proxy_url()
                    if http_proxy_url:
                        env = {
                            "http_proxy": http_proxy_url,
                            "https_proxy": http_proxy_url,
                        }
                    if float(__grains__["osrelease"]) < 12.04:
                        cmd = ["apt-add-repository", repo]
                    else:
                        cmd = ["apt-add-repository", "-y", repo]
                    out = _call_apt(cmd, env=env, scope=False, **kwargs)
                    if out["retcode"]:
                        raise CommandExecutionError(
                            f"Unable to add PPA '{repo[4:]}'. '{cmd}' exited with status {out['retcode']!s}: '{out['stderr']}'"
                        )
                    # explicit refresh when a repo is modified.
                    if refresh:
                        refresh_db()
                    return {repo: out}
            else:

                # fall back to urllib style
                try:
                    owner_name, ppa_name = repo[4:].split("/", 1)
                except ValueError:
                    raise CommandExecutionError(
                        f"Unable to get PPA info from argument. Expected format \"<PPA_OWNER>/<PPA_NAME>\" (e.g. saltstack/salt) not found.  Received '{repo[4:]}' instead."
                    )
                dist = __grains__["oscodename"]
                # ppa has a lot of implicit arguments. Make them explicit.
                # These will defer to any user-defined variants
                kwargs["dist"] = dist
                ppa_auth = ""
                if "file" not in kwargs:
                    filename = (
                        f"/etc/apt/sources.list.d/{owner_name}-{ppa_name}-{dist}.list"
                    )
                    kwargs["file"] = filename
                try:
                    launchpad_ppa_info = _get_ppa_info_from_launchpad(
                        owner_name, ppa_name
                    )
                    if "ppa_auth" not in kwargs:
                        kwargs["keyid"] = launchpad_ppa_info["signing_key_fingerprint"]
                    else:
                        if "keyid" not in kwargs:
                            raise CommandExecutionError(
                                f"Private PPAs require a keyid to be specified: {owner_name}/{ppa_name}"
                            )
                except HTTPError as exc:
                    raise CommandExecutionError(
                        f"Launchpad does not know about {owner_name}/{ppa_name}: {exc}"
                    )
                except IndexError as exc:
                    raise CommandExecutionError(
                        f"Launchpad knows about {owner_name}/{ppa_name} but did not return a fingerprint. Please set keyid manually: {exc}"
                    )

                if "keyserver" not in kwargs:
                    kwargs["keyserver"] = "keyserver.ubuntu.com"
                if "ppa_auth" in kwargs:
                    if not launchpad_ppa_info["private"]:
                        raise CommandExecutionError(
                            f"PPA is not private but auth credentials passed: {repo}"
                        )
                # assign the new repo format to the "repo" variable
                # so we can fall through to the "normal" mechanism
                # here.
                if "ppa_auth" in kwargs:
                    ppa_auth = f"{kwargs['ppa_auth']}@"
                    repo = LP_PVT_SRC_FORMAT.format(
                        ppa_auth, owner_name, ppa_name, dist
                    )
                else:
                    repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)
        else:
            raise CommandExecutionError(
                f'cannot parse "ppa:" style repo definitions: {repo}'
            )

    sources = SourcesList()
    if kwargs.get("consolidate", False):
        # attempt to de-dup and consolidate all sources
        # down to entries in sources.list
        # this option makes it easier to keep the sources
        # list in a "sane" state.
        #
        # this should remove duplicates, consolidate comps
        # for a given source down to one line
        # and eliminate "invalid" and comment lines
        #
        # the second side effect is removal of files
        # that are not the main sources.list file
        sources = _consolidate_repo_sources(sources)

    repos = []
    for source in sources:
        repos.append(source)

    mod_source = None
    try:
        repo_entry = _split_repo_str(repo)
        if repo_entry.get("invalid"):
            raise SaltInvocationError(
                f"Name {repo} is not valid. This must be the complete repo entry as seen in the sources file"
            )
    except SyntaxError:
        raise SyntaxError(f"Error: repo '{repo}' not a well formatted definition")

    full_comp_list = {comp.strip() for comp in repo_entry["comps"]}
    no_proxy = __salt__["config.option"]("no_proxy")

    kwargs["signedby"] = (
        pathlib.Path(repo_entry["signedby"]) if repo_entry["signedby"] else ""
    )

    if not aptkey and not kwargs["signedby"]:
        raise SaltInvocationError("missing 'signedby' option when apt-key is missing")

    if "keyid" in kwargs:
        keyid = kwargs.pop("keyid", None)
        keyserver = kwargs.pop("keyserver", None)
        if not keyid or not keyserver:
            error_str = "both keyserver and keyid options required."
            raise NameError(error_str)
        if not isinstance(keyid, list):
            keyid = [keyid]

        for key in keyid:
            if isinstance(
                key, int
            ):  # yaml can make this an int, we need the hex version
                key = hex(key)
            if not aptkey:
                imported = False
                output = get_repo_keys(aptkey=aptkey, keydir=kwargs["signedby"].parent)
                if output.get(key):
                    imported = True
            else:
                cmd = ["apt-key", "export", key]
                output = __salt__["cmd.run_stdout"](cmd, python_shell=False, **kwargs)
                imported = output.startswith("-----BEGIN PGP")
            if keyserver:
                if not imported:
                    http_proxy_url = _get_http_proxy_url()
                    if http_proxy_url and keyserver not in no_proxy:
                        cmd = [
                            "apt-key",
                            "adv",
                            "--batch",
                            "--keyserver-options",
                            f"http-proxy={http_proxy_url}",
                            "--keyserver",
                            keyserver,
                            "--logger-fd",
                            "1",
                            "--recv-keys",
                            key,
                        ]
                    else:
                        if not aptkey:
                            key_file = kwargs["signedby"]
                            if not add_repo_key(
                                keyid=key,
                                keyserver=keyserver,
                                aptkey=False,
                                keydir=key_file.parent,
                                keyfile=key_file,
                            ):
                                raise CommandExecutionError(
                                    f"Error: Could not add key: {key}"
                                )

                        else:
                            cmd = [
                                "apt-key",
                                "adv",
                                "--batch",
                                "--keyserver",
                                keyserver,
                                "--logger-fd",
                                "1",
                                "--recv-keys",
                                key,
                            ]
                            ret = _call_apt(cmd, scope=False, **kwargs)
                            if ret["retcode"] != 0:
                                raise CommandExecutionError(
                                    f"Error: key retrieval failed: {ret['stdout']}"
                                )

    elif "key_url" in kwargs:
        key_url = kwargs["key_url"]
        fn_ = pathlib.Path(__salt__["cp.cache_file"](key_url, saltenv))
        if not fn_:
            raise CommandExecutionError(f"Error: file not found: {key_url}")

        if kwargs["signedby"] and fn_.name != kwargs["signedby"].name:
            # override the signedby defined in the name with the
            # one defined in kwargs.
            new_path = fn_.parent / kwargs["signedby"].name
            fn_.rename(new_path)
            fn_ = new_path

        if not aptkey:
            func_kwargs = {}
            if kwargs.get("signedby"):
                func_kwargs["keydir"] = kwargs.get("signedby").parent

            if not add_repo_key(path=str(fn_), aptkey=False, **func_kwargs):
                raise CommandExecutionError(f"Error: Could not add key: {str(fn_)}")
        else:
            cmd = ["apt-key", "add", str(fn_)]
            out = __salt__["cmd.run_stdout"](cmd, python_shell=False, **kwargs)
            if not out.upper().startswith("OK"):
                raise CommandExecutionError(f"Error: failed to add key from {key_url}")

    elif "key_text" in kwargs:
        key_text = kwargs["key_text"]
        cmd = ["apt-key", "add", "-"]
        out = __salt__["cmd.run_stdout"](
            cmd, stdin=key_text, python_shell=False, **kwargs
        )
        if not out.upper().startswith("OK"):
            raise CommandExecutionError(f"Error: failed to add key:\n{key_text}")

    if "comps" in kwargs:
        kwargs["comps"] = [comp.strip() for comp in kwargs["comps"].split(",")]
        full_comp_list |= set(kwargs["comps"])
    else:
        kwargs["comps"] = list(full_comp_list)

    if "architectures" in kwargs:
        kwargs["architectures"] = kwargs["architectures"].split(",")
    else:
        kwargs["architectures"] = repo_entry["architectures"]

    if "disabled" in kwargs:
        kwargs["disabled"] = salt.utils.data.is_true(kwargs["disabled"])
    elif "enabled" in kwargs:
        kwargs["disabled"] = not salt.utils.data.is_true(kwargs["enabled"])

    kw_type = kwargs.get("type")
    kw_dist = kwargs.get("dist")

    for apt_source in repos:
        # This series of checks will identify the starting source line
        # and the resulting source line.  The idea here is to ensure
        # we are not returning bogus data because the source line
        # has already been modified on a previous run.
        repo_matches = (
            apt_source.type == repo_entry["type"]
            and apt_source.uri.rstrip("/") == repo_entry["uri"].rstrip("/")
            and apt_source.dist == repo_entry["dist"]
        )
        kw_matches = apt_source.dist == kw_dist and apt_source.type == kw_type

        if repo_matches or kw_matches:
            for comp in full_comp_list:
                if comp in getattr(apt_source, "comps", []):
                    mod_source = apt_source
            if not apt_source.comps:
                mod_source = apt_source
            if kwargs["architectures"] != apt_source.architectures:
                mod_source = apt_source
            if mod_source:
                break

    if "comments" in kwargs:
        kwargs["comments"] = salt.utils.pkg.deb.combine_comments(kwargs["comments"])

    repo_source_entry = SourceEntry(repo)
    if not mod_source:
        mod_source = SourceEntry(repo)
        if "comments" in kwargs:
            mod_source.comment = kwargs["comments"]
        sources.list.append(mod_source)
    elif "comments" in kwargs:
        mod_source.comment = kwargs["comments"]

    mod_source.line = repo_source_entry.line
    if not mod_source.line.endswith("\n"):
        mod_source.line = mod_source.line + "\n"

    for key in kwargs:
        if key in _MODIFY_OK and hasattr(mod_source, key):
            setattr(mod_source, key, kwargs[key])

    if mod_source.uri != repo_entry["uri"]:
        mod_source.uri = repo_entry["uri"]
        mod_source.line = mod_source.str()

    sources.save()
    # on changes, explicitly refresh
    if refresh:
        refresh_db()

    signedby = mod_source.signedby

    return {
        repo: {
            "architectures": getattr(mod_source, "architectures", []),
            "comps": mod_source.comps,
            "disabled": mod_source.disabled,
            "file": mod_source.file,
            "type": mod_source.type,
            "uri": mod_source.uri,
            "line": mod_source.line,
            "signedby": signedby,
        }
    }


def file_list(*packages, **kwargs):
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
    return __salt__["lowpkg.file_list"](*packages)


def file_dict(*packages, **kwargs):
    """
    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of _every_ file on the system's
    package database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_dict httpd
        salt '*' pkg.file_dict httpd postfix
        salt '*' pkg.file_dict
    """
    return __salt__["lowpkg.file_dict"](*packages)


def _expand_repo_def(os_name, os_codename=None, **kwargs):
    """
    Take a repository definition and expand it to the full pkg repository dict
    that can be used for comparison.  This is a helper function to make
    the Debian/Ubuntu apt sources sane for comparison in the pkgrepo states.

    This is designed to be called from pkgrepo states and will have little use
    being called on the CLI.
    """
    if "repo" not in kwargs:
        raise SaltInvocationError("missing 'repo' argument")

    sanitized = {}
    repo = kwargs["repo"]
    if repo.startswith("ppa:") and os_name in ("Ubuntu", "Mint", "neon"):
        dist = os_codename
        owner_name, ppa_name = repo[4:].split("/", 1)
        if "ppa_auth" in kwargs:
            auth_info = "{}@".format(kwargs["ppa_auth"])
            repo = LP_PVT_SRC_FORMAT.format(auth_info, owner_name, ppa_name, dist)
        else:
            repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)

        if "file" not in kwargs:
            kwargs["file"] = (
                f"/etc/apt/sources.list.d/{owner_name}-{ppa_name}-{dist}.list"
            )

    source_entry = SourceEntry(repo)
    for list_args in ("architectures", "comps"):
        if list_args in kwargs:
            kwargs[list_args] = [
                kwarg.strip() for kwarg in kwargs[list_args].split(",")
            ]
    for kwarg in _MODIFY_OK:
        if kwarg in kwargs:
            setattr(source_entry, kwarg, kwargs[kwarg])

    source_list = SourcesList()
    kwargs = {}
    signedby = source_entry.signedby
    kwargs["signedby"] = signedby

    _source_entry = source_list.add(
        type=source_entry.type,
        uri=source_entry.uri,
        dist=source_entry.dist,
        orig_comps=getattr(source_entry, "comps", []),
        architectures=getattr(source_entry, "architectures", []),
        **kwargs,
    )
    if hasattr(_source_entry, "set_enabled"):
        _source_entry.set_enabled(not source_entry.disabled)
    else:
        _source_entry.disabled = source_entry.disabled
        _source_entry.line = _source_entry.repo_line()

    sanitized["file"] = _source_entry.file
    sanitized["comps"] = getattr(_source_entry, "comps", [])
    sanitized["disabled"] = _source_entry.disabled
    sanitized["dist"] = _source_entry.dist
    sanitized["type"] = _source_entry.type
    sanitized["uri"] = _source_entry.uri
    sanitized["line"] = _source_entry.line.strip()
    sanitized["architectures"] = getattr(_source_entry, "architectures", [])
    sanitized["signedby"] = signedby

    return sanitized


def _parse_selections(dpkgselection):
    """
    Parses the format from ``dpkg --get-selections`` and return a format that
    pkg.get_selections and pkg.set_selections work with.
    """
    ret = {}
    if isinstance(dpkgselection, str):
        dpkgselection = dpkgselection.split("\n")
    for line in dpkgselection:
        if line:
            _pkg, _state = line.split()
            if _state in ret:
                ret[_state].append(_pkg)
            else:
                ret[_state] = [_pkg]
    return ret


def get_selections(pattern=None, state=None):
    """
    View package state from the dpkg database.

    Returns a dict of dicts containing the state, and package names:

    .. code-block:: python

        {'<host>':
            {'<state>': ['pkg1',
                         ...
                        ]
            },
            ...
        }

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.get_selections
        salt '*' pkg.get_selections 'python-*'
        salt '*' pkg.get_selections state=hold
        salt '*' pkg.get_selections 'openssh*' state=hold
    """
    ret = {}
    cmd = ["dpkg", "--get-selections"]
    cmd.append(pattern if pattern else "*")
    stdout = __salt__["cmd.run_stdout"](
        cmd, output_loglevel="trace", python_shell=False
    )
    ret = _parse_selections(stdout)
    if state:
        return {state: ret.get(state, [])}
    return ret


# TODO: allow state=None to be set, and that *args will be set to that state
# TODO: maybe use something similar to pkg_resources.pack_pkgs to allow a list
# passed to selection, with the default state set to whatever is passed by the
# above, but override that if explicitly specified
# TODO: handle path to selection file from local fs as well as from salt file
# server
def set_selections(path=None, selection=None, clear=False, saltenv="base"):
    """
    Change package state in the dpkg database.

    The state can be any one of, documented in ``dpkg(1)``:

    - install
    - hold
    - deinstall
    - purge

    This command is commonly used to mark specific packages to be held from
    being upgraded, that is, to be kept at a certain version. When a state is
    changed to anything but being held, then it is typically followed by
    ``apt-get -u dselect-upgrade``.

    Note: Be careful with the ``clear`` argument, since it will start
    with setting all packages to deinstall state.

    Returns a dict of dicts containing the package names, and the new and old
    versions:

    .. code-block:: python

        {'<host>':
            {'<package>': {'new': '<new-state>',
                           'old': '<old-state>'}
            },
            ...
        }

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.set_selections selection='{"install": ["netcat"]}'
        salt '*' pkg.set_selections selection='{"hold": ["openssh-server", "openssh-client"]}'
        salt '*' pkg.set_selections salt://path/to/file
        salt '*' pkg.set_selections salt://path/to/file clear=True
    """
    ret = {}
    if not path and not selection:
        return ret
    if path and selection:
        err = (
            "The 'selection' and 'path' arguments to "
            "pkg.set_selections are mutually exclusive, and cannot be "
            "specified together"
        )
        raise SaltInvocationError(err)

    if isinstance(selection, str):
        try:
            selection = salt.utils.yaml.safe_load(selection)
        except (
            salt.utils.yaml.parser.ParserError,
            salt.utils.yaml.scanner.ScannerError,
        ) as exc:
            raise SaltInvocationError(f"Improperly-formatted selection: {exc}")

    if path:
        path = __salt__["cp.cache_file"](path, saltenv)
        with salt.utils.files.fopen(path, "r") as ifile:
            content = [salt.utils.stringutils.to_unicode(x) for x in ifile.readlines()]
        selection = _parse_selections(content)

    if selection:
        valid_states = ("install", "hold", "deinstall", "purge")
        bad_states = [x for x in selection if x not in valid_states]
        if bad_states:
            raise SaltInvocationError(f"Invalid state(s): {', '.join(bad_states)}")

        if clear:
            cmd = ["dpkg", "--clear-selections"]
            if not __opts__["test"]:
                result = _call_apt(cmd, scope=False)
                if result["retcode"] != 0:
                    err = "Running dpkg --clear-selections failed: {}".format(
                        result["stderr"]
                    )
                    log.error(err)
                    raise CommandExecutionError(err)

        sel_revmap = {}
        for _state, _pkgs in get_selections().items():
            sel_revmap.update({_pkg: _state for _pkg in _pkgs})

        for _state, _pkgs in selection.items():
            for _pkg in _pkgs:
                if _state == sel_revmap.get(_pkg):
                    continue
                cmd = ["dpkg", "--set-selections"]
                cmd_in = f"{_pkg} {_state}"
                if not __opts__["test"]:
                    result = _call_apt(cmd, scope=False, stdin=cmd_in)
                    if result["retcode"] != 0:
                        log.error("failed to set state %s for package %s", _state, _pkg)
                    else:
                        ret[_pkg] = {"old": sel_revmap.get(_pkg), "new": _state}
    return ret


def owner(*paths, **kwargs):
    """
    .. versionadded:: 2014.7.0

    Return the name of the package that owns the file. Multiple file paths can
    be passed. Like :mod:`pkg.version <salt.modules.aptpkg.version>`, if a
    single path is passed, a string will be returned, and if multiple paths are
    passed, a dictionary of file/package name pairs will be returned.

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
    for path in paths:
        cmd = ["dpkg", "-S", path]
        output = __salt__["cmd.run_stdout"](
            cmd, output_loglevel="trace", python_shell=False
        )
        ret[path] = output.split(":")[0]
        if "no path found" in ret[path].lower():
            ret[path] = ""
    if len(ret) == 1:
        return next(iter(ret.values()))
    return ret


def show(*names, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Runs an ``apt-cache show`` on the passed package names, and returns the
    results in a nested dictionary. The top level of the return data will be
    the package name, with each package name mapping to a dictionary of version
    numbers to any additional information returned by ``apt-cache show``.

    filter
        An optional comma-separated list (or quoted Python list) of
        case-insensitive keys on which to filter. This allows one to restrict
        the information returned for each package to a smaller selection of
        pertinent items.

    refresh : False
        If ``True``, the apt cache will be refreshed first. By default, no
        refresh is performed.

    CLI Examples:

    .. code-block:: bash

        salt myminion pkg.show gawk
        salt myminion pkg.show 'nginx-*'
        salt myminion pkg.show 'nginx-*' filter=description,provides
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    refresh = kwargs.pop("refresh", False)
    filter_ = salt.utils.args.split_input(
        kwargs.pop("filter", []),
        lambda x: str(x) if not isinstance(x, str) else x.lower(),
    )
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    if refresh:
        refresh_db()

    if not names:
        return {}

    result = _call_apt(["apt-cache", "show"] + list(names), scope=False)

    def _add(ret, pkginfo):
        name = pkginfo.pop("Package", None)
        version = pkginfo.pop("Version", None)
        if name is not None and version is not None:
            ret.setdefault(name, {}).setdefault(version, {}).update(pkginfo)

    def _check_filter(key):
        key = key.lower()
        return True if key in ("package", "version") or not filter_ else key in filter_

    ret = {}
    pkginfo = {}
    for line in salt.utils.itertools.split(result["stdout"], "\n"):
        line = line.strip()
        if line:
            try:
                key, val = (x.strip() for x in line.split(":", 1))
            except ValueError:
                pass
            else:
                if _check_filter(key):
                    pkginfo[key] = val
        else:
            # We've reached a blank line, which separates packages
            _add(ret, pkginfo)
            # Clear out the pkginfo dict for the next package
            pkginfo = {}
            continue

    # Make sure to add whatever was in the pkginfo dict when we reached the end
    # of the output.
    _add(ret, pkginfo)

    return ret


def info_installed(*names, **kwargs):
    """
    Return the information of the named package(s) installed on the system.

    .. versionadded:: 2015.8.1

    names
        The names of the packages for which to return information.

    failhard
        Whether to throw an exception if none of the packages are installed.
        Defaults to True.

        .. versionadded:: 2016.11.3

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.info_installed <package1>
        salt '*' pkg.info_installed <package1> <package2> <package3> ...
        salt '*' pkg.info_installed <package1> failhard=false
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    failhard = kwargs.pop("failhard", True)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    ret = dict()
    for pkg_name, pkg_nfo in __salt__["lowpkg.info"](*names, failhard=failhard).items():
        t_nfo = dict()
        if pkg_nfo.get("status", "ii")[1] != "i":
            continue  # return only packages that are really installed
        # Translate dpkg-specific keys to a common structure
        for key, value in pkg_nfo.items():
            if key == "package":
                t_nfo["name"] = value
            elif key == "origin":
                t_nfo["vendor"] = value
            elif key == "section":
                t_nfo["group"] = value
            elif key == "maintainer":
                t_nfo["packager"] = value
            elif key == "homepage":
                t_nfo["url"] = value
            elif key == "status":
                continue  # only installed pkgs are returned, no need for status
            else:
                t_nfo[key] = value

        ret[pkg_name] = t_nfo

    return ret


def _get_http_proxy_url():
    """
    Returns the http_proxy_url if proxy_username, proxy_password, proxy_host, and proxy_port
    config values are set.

    Returns a string.
    """
    http_proxy_url = ""
    host = __salt__["config.option"]("proxy_host")
    port = __salt__["config.option"]("proxy_port")
    username = __salt__["config.option"]("proxy_username")
    password = __salt__["config.option"]("proxy_password")

    # Set http_proxy_url for use in various internet facing actions...eg apt-key adv
    if host and port:
        if username and password:
            http_proxy_url = f"http://{username}:{password}@{host}:{port}"
        else:
            http_proxy_url = f"http://{host}:{port}"

    return http_proxy_url


def list_downloaded(root=None, **kwargs):
    """
    .. versionadded:: 3000

    List prefetched packages downloaded by apt in the local disk.

    root
        operate on a different root directory.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_downloaded
    """
    CACHE_DIR = "/var/cache/apt"
    if root:
        CACHE_DIR = os.path.join(root, os.path.relpath(CACHE_DIR, os.path.sep))

    ret = {}
    for root, dirnames, filenames in salt.utils.path.os_walk(CACHE_DIR):
        for filename in fnmatch.filter(filenames, "*.deb"):
            package_path = os.path.join(root, filename)
            pkg_info = __salt__["lowpkg.bin_pkg_info"](package_path)
            pkg_timestamp = int(os.path.getctime(package_path))
            ret.setdefault(pkg_info["name"], {})[pkg_info["version"]] = {
                "path": package_path,
                "size": os.path.getsize(package_path),
                "creation_date_time_t": pkg_timestamp,
                "creation_date_time": datetime.datetime.utcfromtimestamp(
                    pkg_timestamp
                ).isoformat(),
            }
    return ret


def services_need_restart(**kwargs):
    """
    .. versionadded:: 3003

    List services that use files which have been changed by the
    package manager. It might be needed to restart them.

    Requires checkrestart from the debian-goodies package.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.services_need_restart
    """
    if not salt.utils.path.which_bin(["checkrestart"]):
        raise CommandNotFoundError(
            "'checkrestart' is needed. It is part of the 'debian-goodies' "
            "package which can be installed from official repositories."
        )

    cmd = ["checkrestart", "--machine", "--package"]
    services = set()

    cr_output = __salt__["cmd.run_stdout"](cmd, python_shell=False)
    for line in cr_output.split("\n"):
        if not line.startswith("SERVICE:"):
            continue
        end_of_name = line.find(",")
        service = line[8:end_of_name]  # skip "SERVICE:"
        services.add(service)

    return list(services)


def which(path):
    """
    Displays which package installed a specific file

    CLI Examples:

    .. code-block:: bash

        salt * pkg.which <file name>
    """
    filepath = pathlib.Path(path)
    cmd = ["dpkg"]
    if filepath.is_absolute():
        if filepath.exists():
            cmd.extend(["-S", str(filepath)])
        else:
            log.debug("%s does not exist", filepath)
            return False
    else:
        log.debug("%s is not absolute path", filepath)
        return False
    cmd_ret = _call_apt(cmd)
    if "no path found matching pattern" in cmd_ret["stdout"]:
        return None
    pkg = cmd_ret["stdout"].split(":")[0]
    return pkg
