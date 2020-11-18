"""
Homebrew for macOS

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import copy
import functools
import logging
import re

import salt.utils.data
import salt.utils.functools
import salt.utils.json
import salt.utils.path
import salt.utils.pkg
import salt.utils.versions
from salt.exceptions import CommandExecutionError, MinionError, SaltInvocationError
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


def _list_pinned():
    """
    List currently pinned formulas
    """
    cmd = "list --pinned"
    return _call_brew(cmd)["stdout"].splitlines()


def _pin(pkg, runas=None):
    """
    Pin pkg
    """
    cmd = "pin {}".format(pkg)
    try:
        _call_brew(cmd)
    except CommandExecutionError:
        log.error('Failed to pin "%s"', pkg)
        return False

    return True


def _unpin(pkg, runas=None):
    """
    Pin pkg
    """
    cmd = "unpin {}".format(pkg)
    try:
        _call_brew(cmd)
    except CommandExecutionError:
        log.error('Failed to unpin "%s"', pkg)
        return False

    return True


def _tap(tap, runas=None):
    """
    Add unofficial GitHub repos to the list of formulas that brew tracks,
    updates, and installs from.
    """
    if tap in _list_taps():
        return True

    cmd = "tap {}".format(tap)
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

    versions_dict = {key: get_version(val) for key, val in _info(*names).items()}

    if len(names) == 1:
        return next(iter(versions_dict.values()))
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
        pkg_params = __salt__["pkg_resource.parse_targets"](name, pkgs, **kwargs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    cmd = "uninstall {}".format(" ".join(targets))

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


def refresh_db(**kwargs):
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
    cmd = "info --json=v1 {}".format(" ".join(pkgs))
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
        pkg_params, pkg_type = __salt__["pkg_resource.parse_targets"](
            name, pkgs, kwargs.get("sources", {})
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if not pkg_params:
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
        cmd = "install {} {}".format(formulas, " ".join(options))
    else:
        cmd = "install {}".format(formulas)

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
        msg = 'unable to interpret output from "brew outdated": {}'.format(err)
        log.error(msg)
        raise CommandExecutionError(msg)

    for pkg in data:
        # current means latest available to brew
        ret[pkg["name"]] = pkg["current_version"]
    return ret


def upgrade_available(pkg, **kwargs):
    """
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    """
    return pkg in list_upgrades()


def upgrade(refresh=True, **kwargs):
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


def info_installed(*names, **kwargs):
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


def hold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    """
    Set package in 'hold' state, meaning it will not be upgraded.

    .. versionadded:: 3001

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
    pinned = _list_pinned()
    installed = list_pkgs()
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target))

        ret[target] = {"name": target, "changes": {}, "result": False, "comment": ""}

        if target not in installed:
            ret[target]["comment"] = "Package {} does not have a state.".format(target)
        elif target not in pinned:
            if "test" in __opts__ and __opts__["test"]:
                ret[target].update(result=None)
                ret[target]["comment"] = "Package {} is set to be held.".format(target)
            else:
                result = _pin(target)
                if result:
                    changes = {"old": "install", "new": "hold"}
                    ret[target].update(changes=changes, result=True)
                    ret[target]["comment"] = "Package {} is now being held.".format(
                        target
                    )
                else:
                    ret[target].update(result=False)
                    ret[target]["comment"] = "Unable to hold package {}.".format(target)
        else:
            ret[target].update(result=True)
            ret[target]["comment"] = "Package {} is already set to be held.".format(
                target
            )
    return ret


pin = hold


def unhold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    """
    Set package current in 'hold' state to install state,
    meaning it will be upgraded.

    .. versionadded:: 3001

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
    pinned = _list_pinned()
    installed = list_pkgs()
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target))

        ret[target] = {"name": target, "changes": {}, "result": False, "comment": ""}

        if target not in installed:
            ret[target]["comment"] = "Package {} does not have a state.".format(target)
        elif target in pinned:
            if "test" in __opts__ and __opts__["test"]:
                ret[target].update(result=None)
                ret[target]["comment"] = "Package {} is set to be unheld.".format(
                    target
                )
            else:
                result = _unpin(target)
                if result:
                    changes = {"old": "hold", "new": "install"}
                    ret[target].update(changes=changes, result=True)
                    ret[target][
                        "comment"
                    ] = "Package {} is no longer being held.".format(target)
                else:
                    ret[target].update(result=False)
                    ret[target]["comment"] = "Unable to unhold package {}.".format(
                        target
                    )
        else:
            ret[target].update(result=True)
            ret[target]["comment"] = "Package {} is already set not to be held.".format(
                target
            )
    return ret


unpin = unhold
