# -*- coding: utf-8 -*-
"""
Homebrew for macOS

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import copy
import functools
import logging
import re

# Import salt libs
import salt.utils.data
import salt.utils.functools
import salt.utils.json
import salt.utils.path
import salt.utils.pkg
import salt.utils.versions
from salt.exceptions import CommandExecutionError, MinionError

# Import third party libs
from salt.ext import six
from salt.ext.six.moves import zip

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Confine this module to Mac OS with Homebrew.
    """

    if salt.utils.path.which("brew") and __grains__["os"] == "MacOS":
        return __virtualname__
    return (
        False,
        "The brew module could not be loaded: brew not found or grain os != MacOS",
    )


def _list_taps():
    """
    List currently installed brew taps
    """
    cmd = "tap"
    return _call_brew(cmd)["stdout"].splitlines()


def _tap(tap, runas=None):
    """
    Add unofficial GitHub repos to the list of formulas that brew tracks,
    updates, and installs from.
    """
    if tap in _list_taps():
        return True

    cmd = "tap {0}".format(tap)
    try:
        _call_brew(cmd)
    except CommandExecutionError:
        log.error('Failed to tap "%s"', tap)
        return False

    return True


def _homebrew_bin():
    """
    Returns the full path to the homebrew binary in the PATH
    """
    ret = __salt__["cmd.run"]("brew --prefix", output_loglevel="trace")
    ret += "/bin/brew"
    return ret


def _call_brew(cmd, failhard=True):
    """
    Calls the brew command with the user account of brew
    """
    user = __salt__["file.get_user"](_homebrew_bin())
    runas = user if user != __opts__["user"] else None
    cmd = "{} {}".format(salt.utils.path.which("brew"), cmd)
    result = __salt__["cmd.run_all"](
        cmd, runas=runas, output_loglevel="trace", python_shell=False
    )
    if failhard and result["retcode"] != 0:
        raise CommandExecutionError("Brew command failed", info={"result": result})
    return result


def list_pkgs(versions_as_list=False, **kwargs):
    """
    List the packages currently installed in a dict::

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

    if "pkg.list_pkgs" in __context__:
        if versions_as_list:
            return __context__["pkg.list_pkgs"]
        else:
            ret = copy.deepcopy(__context__["pkg.list_pkgs"])
            __salt__["pkg_resource.stringify"](ret)
            return ret

    ret = {}
    cmd = "info --json=v1 --installed"
    package_info = salt.utils.json.loads(_call_brew(cmd)["stdout"])

    for package in package_info:
        # Brew allows multiple versions of the same package to be installed.
        # Salt allows for this, so it must be accounted for.
        versions = [v["version"] for v in package["installed"]]
        # Brew allows for aliasing of packages, all of which will be
        # installable from a Salt call, so all names must be accounted for.
        names = package["aliases"] + [package["name"], package["full_name"]]
        # Create a list of tuples containing all possible combinations of
        # names and versions, because all are valid.
        combinations = [(n, v) for n in names for v in versions]

        for name, version in combinations:
            __salt__["pkg_resource.add_pkg"](ret, name, version)

    # Grab packages from brew cask, if available.
    # Brew Cask doesn't provide a JSON interface, must be parsed the old way.
    try:
        cask_cmd = "cask list --versions"
        out = _call_brew(cask_cmd)["stdout"]

        for line in out.splitlines():
            try:
                name_and_versions = line.split(" ")
                pkg_name = name_and_versions[0]

                # Get cask namespace
                info_cmd = "cask info {}".format(pkg_name)
                match = re.search(
                    r"^From: .*/(.+?)/homebrew-(.+?)/.*$",
                    _call_brew(info_cmd)["stdout"],
                    re.MULTILINE,
                )
                if match:
                    namespace = "/".join(
                        (match.group(1).lower(), match.group(2).lower())
                    )
                else:
                    namespace = "homebrew/cask"

                name = "/".join((namespace, pkg_name))
                installed_versions = name_and_versions[1:]
                key_func = functools.cmp_to_key(salt.utils.versions.version_cmp)
                newest_version = sorted(installed_versions, key=key_func).pop()
            except ValueError:
                continue
            __salt__["pkg_resource.add_pkg"](ret, name, newest_version)
    except CommandExecutionError:
        pass

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
        salt '*' pkg.version <package1> <package2> <package3>
    """
    return __salt__["pkg_resource.version"](*names, **kwargs)


def latest_version(*names, **kwargs):
    """
    Return the latest version of the named package available for upgrade or
    installation

    Currently chooses stable versions, falling back to devel if that does not
    exist.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3>
    """
    refresh = salt.utils.data.is_true(kwargs.pop("refresh", True))
    if refresh:
        refresh_db()

    def get_version(pkg_info):
        # Perhaps this will need an option to pick devel by default
        return pkg_info["versions"]["stable"] or pkg_info["versions"]["devel"]

    versions_dict = dict(
        (key, get_version(val)) for key, val in six.iteritems(_info(*names))
    )

    if len(names) == 1:
        return next(six.itervalues(versions_dict))
    else:
        return versions_dict


# available_version is being deprecated
available_version = salt.utils.functools.alias_function(
    latest_version, "available_version"
)


def remove(name=None, pkgs=None, **kwargs):
    """
    Removes packages with ``brew uninstall``.

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
        name, pkgs = _fix_cask_namespace(name, pkgs)
        pkg_params = __salt__["pkg_resource.parse_targets"](name, pkgs, **kwargs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    cmd = "uninstall {0}".format(" ".join(targets))

    out = _call_brew(cmd)
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


def refresh_db():
    """
    Update the homebrew package repository.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    """
    # Remove rtag file to keep multiple refreshes from happening in pkg states
    salt.utils.pkg.clear_rtag(__opts__)
    cmd = "update"
    if _call_brew(cmd)["retcode"]:
        log.error("Failed to update")
        return False

    return True


def _info(*pkgs):
    """
    Get all info brew can provide about a list of packages.

    Does not do any kind of processing, so the format depends entirely on
    the output brew gives. This may change if a new version of the format is
    requested.

    On failure, returns an empty dict and logs failure.
    On success, returns a dict mapping each item in pkgs to its corresponding
    object in the output of 'brew info'.

    Caveat: If one of the packages does not exist, no packages will be
            included in the output.
    """
    cmd = "info --json=v1 {0}".format(" ".join(pkgs))
    brew_result = _call_brew(cmd)
    if brew_result["retcode"]:
        log.error("Failed to get info about packages: %s", " ".join(pkgs))
        return {}
    output = salt.utils.json.loads(brew_result["stdout"])
    return dict(zip(pkgs, output))


def install(name=None, pkgs=None, taps=None, options=None, **kwargs):
    """
    Install the passed package(s) with ``brew install``

    name
        The name of the formula to be installed. Note that this parameter is
        ignored if "pkgs" is passed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    taps
        Unofficial GitHub repos to use when updating and installing formulas.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> tap='<tap>'
            salt '*' pkg.install zlib taps='homebrew/dupes'
            salt '*' pkg.install php54 taps='["josegonzalez/php", "homebrew/dupes"]'

    options
        Options to pass to brew. Only applies to initial install. Due to how brew
        works, modifying chosen options requires a full uninstall followed by a
        fresh install. Note that if "pkgs" is used, all options will be passed
        to all packages. Unrecognized options for a package will be silently
        ignored by brew.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> tap='<tap>'
            salt '*' pkg.install php54 taps='["josegonzalez/php", "homebrew/dupes"]' options='["--with-fpm"]'

    Multiple Package Installation Options:

    pkgs
        A list of formulas to install. Must be passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo","bar"]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install 'package package package'
    """
    try:
        name, pkgs = _fix_cask_namespace(name, pkgs)
        pkg_params, pkg_type = __salt__["pkg_resource.parse_targets"](
            name, pkgs, kwargs.get("sources", {})
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    formulas = " ".join(pkg_params)
    old = list_pkgs()

    # Ensure we've tapped the repo if necessary
    if taps:
        if not isinstance(taps, list):
            # Feels like there is a better way to allow for tap being
            # specified as both a string and a list
            taps = [taps]

        for tap in taps:
            _tap(tap)

    if options:
        cmd = "install {0} {1}".format(formulas, " ".join(options))
    else:
        cmd = "install {0}".format(formulas)

    out = _call_brew(cmd)
    if out["retcode"] != 0 and out["stderr"]:
        errors = [out["stderr"]]
    else:
        errors = []

    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            "Problem encountered installing package(s)",
            info={"errors": errors, "changes": ret},
        )

    return ret


def list_upgrades(refresh=True, **kwargs):  # pylint: disable=W0613
    """
    Check whether or not an upgrade is available for all packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    """
    if refresh:
        refresh_db()

    res = _call_brew("outdated --json=v1")
    ret = {}

    try:
        data = salt.utils.json.loads(res["stdout"])
    except ValueError as err:
        msg = 'unable to interpret output from "brew outdated": {0}'.format(err)
        log.error(msg)
        raise CommandExecutionError(msg)

    for pkg in data:
        # current means latest available to brew
        ret[pkg["name"]] = pkg["current_version"]
    return ret


def upgrade_available(pkg):
    """
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    """
    return pkg in list_upgrades()


def upgrade(refresh=True):
    """
    Upgrade outdated, unpinned brews.

    refresh
        Fetch the newest version of Homebrew and all formulae from GitHub before installing.

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

    old = list_pkgs()

    if salt.utils.data.is_true(refresh):
        refresh_db()

    result = _call_brew("upgrade", failhard=False)
    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if result["retcode"] != 0:
        raise CommandExecutionError(
            "Problem encountered upgrading packages",
            info={"changes": ret, "result": result},
        )

    return ret


def info_installed(*names):
    """
    Return the information of the named package(s) installed on the system.

    .. versionadded:: 2016.3.1

    names
        The names of the packages for which to return information.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.info_installed <package1>
        salt '*' pkg.info_installed <package1> <package2> <package3> ...
    """
    return _info(*names)


def _fix_cask_namespace(name=None, pkgs=None):
    """
    Check if provided packages contains the old version of brew-cask namespace
    and replace it by the new one.

    This function also warns about the correct namespace for this packages
    and it will stop working with the release of Sodium.

    :param name: The name of the package to check
    :param pkgs: A list of packages to check

    :return: name and pkgs with the mocked namespace
    """

    show_warning = False

    if name and name.startswith("caskroom/cask/"):
        show_warning = True
        name = name.replace("caskroom/cask/", "homebrew/cask/")

    if pkgs:
        pkgs_ = []
        for pkg in pkgs:
            if isinstance(pkg, str) and pkg.startswith("caskroom/cask/"):
                show_warning = True
                pkg = pkg.replace("caskroom/cask/", "homebrew/cask/")
                pkgs_.append(pkg)
            else:
                pkgs_.append(pkg)
                continue
        pkgs = pkgs_

    if show_warning:
        salt.utils.versions.warn_until(
            "Sodium",
            "The 'caskroom/cask/' namespace for brew-cask packages "
            "is deprecated. Use 'homebrew/cask/' instead.",
        )

    return name, pkgs
