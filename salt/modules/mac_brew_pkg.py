"""
Homebrew for macOS

It is recommended for the ``salt-minion`` to have the ``HOMEBREW_PREFIX``
environment variable set.

This will ensure that Salt uses the correct path for the ``brew`` binary.

Typically, this is set to ``/usr/local`` for Intel Macs and ``/opt/homebrew``
for Apple Silicon Macs.

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import copy
import logging
import os

import salt.utils.data
import salt.utils.functools
import salt.utils.json
import salt.utils.path
import salt.utils.pkg
import salt.utils.versions
from salt.exceptions import CommandExecutionError, MinionError, SaltInvocationError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Confine this module to macOS with Homebrew.
    """
    if __grains__["os"] != "MacOS":
        return False, "brew module is macos specific"
    if not _homebrew_bin():
        return False, "The 'brew' binary was not found"
    return __virtualname__


def _list_taps():
    """
    List currently installed brew taps
    """
    return _call_brew("tap")["stdout"].splitlines()


def _list_pinned():
    """
    List currently pinned formulas
    """
    return _call_brew("list", "--pinned")["stdout"].splitlines()


def _pin(pkg, runas=None):
    """
    Pin pkg
    """
    try:
        _call_brew("pin", pkg)
    except CommandExecutionError:
        log.error('Failed to pin "%s"', pkg)
        return False

    return True


def _unpin(pkg, runas=None):
    """
    Pin pkg
    """
    try:
        _call_brew("unpin", pkg)
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

    try:
        _call_brew("tap", tap)
    except CommandExecutionError:
        log.error('Failed to tap "%s"', tap)
        return False

    return True


def _homebrew_os_bin():
    """
    Fetch PATH binary brew full path eg: /usr/local/bin/brew (symbolic link)
    """

    original_path = os.environ.get("PATH")
    try:
        # Add "/opt/homebrew" temporary to the PATH for Apple Silicon if
        # the PATH does not include "/opt/homebrew"
        current_path = original_path or ""
        homebrew_path = "/opt/homebrew/bin"
        if homebrew_path not in current_path.split(os.path.pathsep):
            extended_path = os.path.pathsep.join([current_path, homebrew_path])
            os.environ["PATH"] = extended_path.lstrip(os.path.pathsep)

        # Search for the brew executable in the current PATH
        brew = salt.utils.path.which("brew")
    finally:
        # Restore original PATH
        if original_path is None:
            del os.environ["PATH"]
        else:
            os.environ["PATH"] = original_path

    return brew


def _homebrew_bin():
    """
    Returns the full path to the homebrew binary in the homebrew installation folder
    """
    ret = homebrew_prefix()
    if ret is not None:
        ret += "/bin/brew"
    else:
        log.warning("Failed to find homebrew prefix")

    return ret


def _call_brew(*cmd, failhard=True):
    """
    Calls the brew command with the user account of brew
    """
    brew_exec = _homebrew_bin()

    user = __salt__["file.get_user"](brew_exec)
    runas = user if user != __opts__["user"] else None
    _cmd = []
    if runas:
        _cmd = [f"sudo -i -n -H -u {runas} -- "]
    _cmd = _cmd + [brew_exec] + list(cmd)
    _cmd = " ".join(_cmd)

    runas = None
    result = __salt__["cmd.run_all"](
        cmd=_cmd,
        runas=runas,
        output_loglevel="trace",
        python_shell=False,
    )
    if failhard and result["retcode"] != 0:
        raise CommandExecutionError("Brew command failed", info={"result": result})
    return result


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


def homebrew_prefix():
    """
    Returns the full path to the homebrew prefix.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.homebrew_prefix
    """

    # If HOMEBREW_PREFIX env variable is present, use it
    env_homebrew_prefix = "HOMEBREW_PREFIX"
    if env_homebrew_prefix in os.environ:
        log.debug("%s is set. Using it for homebrew prefix.", env_homebrew_prefix)
        return os.environ[env_homebrew_prefix]

    # Try brew --prefix otherwise
    try:
        log.debug("Trying to find homebrew prefix by running 'brew --prefix'")

        brew = _homebrew_os_bin()
        if brew is not None:
            # Check if the found brew command is the right one
            import salt.modules.cmdmod
            import salt.modules.file

            runas = salt.modules.file.get_user(brew)
            ret = salt.modules.cmdmod.run(
                "brew --prefix", runas=runas, output_loglevel="trace", raise_err=True
            )

            return ret
    except CommandExecutionError as exc:
        log.debug(
            "Unable to find homebrew prefix by running 'brew --prefix'. Error: %s", exc
        )

    return None


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

    if "pkg.list_pkgs" in __context__ and kwargs.get("use_context", True):
        return _list_pkgs_from_context(versions_as_list)

    ret = {}
    package_info = salt.utils.json.loads(
        _call_brew("info", "--json=v2", "--installed")["stdout"]
    )

    for package in package_info["formulae"]:
        # Brew allows multiple versions of the same package to be installed.
        # Salt allows for this, so it must be accounted for.
        pkg_versions = [v["version"] for v in package["installed"]]
        # Brew allows for aliasing of packages, all of which will be
        # installable from a Salt call, so all names must be accounted for.
        pkg_names = package["aliases"] + [package["name"], package["full_name"]]
        # Create a list of tuples containing all possible combinations of
        # names and versions, because all are valid.
        combinations = [(n, v) for n in pkg_names for v in pkg_versions]

        for pkg_name, pkg_version in combinations:
            __salt__["pkg_resource.add_pkg"](ret, pkg_name, pkg_version)

    for package in package_info["casks"]:
        pkg_version = package["installed"]
        pkg_names = {package["full_token"], package["token"]}
        pkg_tap = package.get("tap", None)
        # The following name is appended to maintain backward compatibility
        # with old salt formulas. Since full_token and token are the same
        # for official taps (homebrew/*).
        if not pkg_tap:
            # Tap is null when the package is from homebrew/cask.
            pkg_tap = "homebrew/cask"
        pkg_names.add("/".join([pkg_tap, package["token"]]))
        for pkg_name in pkg_names:
            __salt__["pkg_resource.add_pkg"](ret, pkg_name, pkg_version)

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


def latest_version(*names, options=None, **kwargs):
    """
    Return the latest version of the named package available for upgrade or
    installation

    Currently chooses stable versions, falling back to devel if that does not
    exist.

    options
        List of string with additional options to pass to brew.
        Useful to remove ambiguous packages that can conflict between formulae and casks.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3>
        salt '*' pkg.latest_version <package name> options='["--cask"]'
    """
    refresh = salt.utils.data.is_true(kwargs.pop("refresh", True))
    if refresh:
        refresh_db()

    def get_version(pkg_info):
        if "versions" in pkg_info.keys():
            # Typically, formulae uses the 'versions' token
            # Perhaps this will need an option to pick devel by default
            pkg_version = (
                pkg_info["versions"]["stable"] or pkg_info["versions"]["devel"]
            )
            if pkg_info["versions"]["bottle"] and pkg_info["revision"] >= 1:
                pkg_version = f"{pkg_version}_{pkg_info['revision']}"
            return pkg_version

        if "version" in pkg_info.keys():
            # Typically, casks use the 'version' token
            return pkg_info["version"]

        return None

    versions_dict = {
        key: get_version(val) for key, val in _info(*names, options=options).items()
    }

    if len(names) == 1:
        return next(iter(versions_dict.values()))

    return versions_dict


# available_version is being deprecated
available_version = salt.utils.functools.alias_function(
    latest_version, "available_version"
)


def remove(name=None, pkgs=None, options=None, **kwargs):
    """
    Removes packages with ``brew uninstall``.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    options
        List of string with additional options to pass to brew.
        Useful to remove ambiguous packages that can conflict between formulae and casks.

        .. versionadded:: 3008.0

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
        salt '*' pkg.remove pkgs='["foo", "bar"]' options='["--cask"]'
    """
    try:
        pkg_params = __salt__["pkg_resource.parse_targets"](name, pkgs, **kwargs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    cmd = ["uninstall"]
    if options:
        cmd.extend(options)
    cmd.extend(list(targets))

    out = _call_brew(*cmd)
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
    if _call_brew("update")["retcode"]:
        log.error("Failed to update")
        return False

    return True


def _info(*pkgs, options=None):
    """
    Get all info brew can provide about a list of packages.

    Does not do any kind of processing, so the format depends entirely on
    the output brew gives. This may change if a new version of the format is
    requested.

    On failure, returns an empty dict and logs failure.
    On success, returns a dict mapping each item in pkgs to its corresponding
    object in the output of 'brew info'.

    options
        List of string with additional options to pass to brew.
        Useful to remove ambiguous packages that can conflict between formulae and casks.

        .. versionadded:: 3008.0

    Caveat: If one of the packages does not exist, no packages will be
            included in the output.
    """
    cmd = ["info", "--json=v2"]
    if options:
        cmd.extend(options)

    brew_result = _call_brew(*cmd, *pkgs)
    if brew_result["retcode"]:
        log.error("Failed to get info about packages: %s", " ".join(pkgs))
        return {}
    output = salt.utils.json.loads(brew_result["stdout"])

    meta_info = {
        "formulae": ["name", "full_name", "aliases"],
        "casks": ["token", "full_token"],
    }

    pkgs_info = dict()
    for tap, keys in meta_info.items():
        data = output[tap]
        if len(data) == 0:
            continue

        for _pkg in data:
            pkg_names = []
            for key in keys:
                pkg_names.append(_pkg[key])
            pkg_names = set(salt.utils.data.flatten(pkg_names))

            for name in pkg_names:
                if name in pkgs:
                    pkgs_info[name] = _pkg

    return pkgs_info


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
        ignored by brew. It can also be used to avoid conflicts between formulae
        and casks.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> tap='<tap>'
            salt '*' pkg.install php54 taps='["josegonzalez/php", "homebrew/dupes"]' options='["--with-fpm"]'
            salt '*' pkg.install cdalvaro/tap/salt options='["--cask"]'

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

    cmd = ["install"]
    cmd.extend(list(pkg_params))

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
        cmd.extend(options)

    out = _call_brew(*cmd)
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


def list_upgrades(
    refresh=True, include_casks=False, options=None, **kwargs
):  # pylint: disable=W0613
    """
    Check whether or not an upgrade is available for all packages

    refresh
        Update the Homebrew's package repository before listing upgrades.

    include_casks
        Whether to include casks in the list of upgrades.

    options
        List of string with additional options to pass to brew.
        Useful to remove ambiguous packages that can conflict between formulae and casks.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
        salt '*' pkg.list_upgrades include_casks=True
        salt '*' pkg.list_upgrades include_casks=True options='["--greedy"]'
    """
    if refresh:
        refresh_db()

    cmd = ["outdated", "--json=v2"]
    if options:
        cmd.extend(options)

    res = _call_brew(*cmd)
    ret = {}

    try:
        data = salt.utils.json.loads(res["stdout"])
    except ValueError as err:
        msg = f'unable to interpret output from "brew outdated": {err}'
        log.error(msg)
        raise CommandExecutionError(msg)

    for pkg in data["formulae"]:
        # current means latest available to brew
        ret[pkg["name"]] = pkg["current_version"]

    if include_casks:
        for pkg in data["casks"]:
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
    return pkg in list_upgrades(**kwargs)


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

    options
        List of string with additional options to pass to brew.
        Useful to remove ambiguous packages that can conflict between formulae and casks.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.info_installed <package1>
        salt '*' pkg.info_installed <package1> <package2> <package3> ...
        salt '*' pkg.info_installed <package1> options='["--cask"]'
    """
    return _info(*names, **kwargs)


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
            ret[target]["comment"] = f"Package {target} does not have a state."
        elif target not in pinned:
            if "test" in __opts__ and __opts__["test"]:
                ret[target].update(result=None)
                ret[target]["comment"] = f"Package {target} is set to be held."
            else:
                result = _pin(target)
                if result:
                    changes = {"old": "install", "new": "hold"}
                    ret[target].update(changes=changes, result=True)
                    ret[target]["comment"] = f"Package {target} is now being held."
                else:
                    ret[target].update(result=False)
                    ret[target]["comment"] = f"Unable to hold package {target}."
        else:
            ret[target].update(result=True)
            ret[target]["comment"] = f"Package {target} is already set to be held."
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
            ret[target]["comment"] = f"Package {target} does not have a state."
        elif target in pinned:
            if "test" in __opts__ and __opts__["test"]:
                ret[target].update(result=None)
                ret[target]["comment"] = f"Package {target} is set to be unheld."
            else:
                result = _unpin(target)
                if result:
                    changes = {"old": "hold", "new": "install"}
                    ret[target].update(changes=changes, result=True)
                    ret[target][
                        "comment"
                    ] = f"Package {target} is no longer being held."
                else:
                    ret[target].update(result=False)
                    ret[target]["comment"] = f"Unable to unhold package {target}."
        else:
            ret[target].update(result=True)
            ret[target]["comment"] = f"Package {target} is already set not to be held."
    return ret


unpin = unhold
