"""
Installation of packages using OS package managers such as yum or apt-get
=========================================================================

.. note::
    On minions running systemd>=205, as of version 2015.8.12, 2016.3.3, and
    2016.11.0, `systemd-run(1)`_ is now used to isolate commands which modify
    installed packages from the ``salt-minion`` daemon's control group. This is
    done to keep systemd from killing the package manager commands spawned by
    Salt, when Salt updates itself (see ``KillMode`` in the `systemd.kill(5)`_
    manpage for more information). If desired, usage of `systemd-run(1)`_ can
    be suppressed by setting a :mod:`config option <salt.modules.config.get>`
    called ``systemd.scope``, with a value of ``False`` (no quotes).

.. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
.. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

Salt can manage software packages via the pkg state module, packages can be
set up to be installed, latest, removed and purged. Package management
declarations are typically rather simple:

.. code-block:: yaml

    vim:
      pkg.installed

A more involved example involves pulling from a custom repository.

.. code-block:: yaml

    base:
      pkgrepo.managed:
        - name: ppa:wolfnet/logstash
        - dist: precise
        - file: /etc/apt/sources.list.d/logstash.list
        - keyid: 28B04E4A
        - keyserver: keyserver.ubuntu.com

    logstash:
      pkg.installed:
        - fromrepo: ppa:wolfnet/logstash

Multiple packages can also be installed with the use of the pkgs
state module

.. code-block:: yaml

    dotdeb.repo:
      pkgrepo.managed:
        - name: deb http://packages.dotdeb.org wheezy-php55 all
        - dist: wheezy-php55
        - file: /etc/apt/sources.list.d/dotbeb.list
        - keyid: 89DF5277
        - keyserver: keys.gnupg.net
        - refresh_db: true

    php.packages:
      pkg.installed:
        - fromrepo: wheezy-php55
        - pkgs:
          - php5-fpm
          - php5-cli
          - php5-curl

.. warning::

    Make sure the package name has the correct case for package managers which are
    case-sensitive (such as :mod:`pkgng <salt.modules.pkgng>`).
"""

import fnmatch
import logging
import os
import re

import salt.utils.args
import salt.utils.pkg
import salt.utils.platform
import salt.utils.versions
from salt.exceptions import CommandExecutionError, MinionError, SaltInvocationError
from salt.modules.pkg_resource import _repack_pkgs
from salt.output import nested
from salt.utils.functools import namespaced_function
from salt.utils.odict import OrderedDict as _OrderedDict

_repack_pkgs = namespaced_function(_repack_pkgs, globals())

if salt.utils.platform.is_windows():
    from salt.modules.win_pkg import (
        _get_latest_pkg_version,
        _get_package_info,
        _get_repo_details,
        _refresh_db_conditional,
        _repo_process_pkg_sls,
        _reverse_cmp_pkg_versions,
        genrepo,
        get_repo_data,
        refresh_db,
    )

    _get_package_info = namespaced_function(_get_package_info, globals())
    get_repo_data = namespaced_function(get_repo_data, globals())
    _get_repo_details = namespaced_function(_get_repo_details, globals())
    _refresh_db_conditional = namespaced_function(_refresh_db_conditional, globals())
    refresh_db = namespaced_function(refresh_db, globals())
    genrepo = namespaced_function(genrepo, globals())
    _repo_process_pkg_sls = namespaced_function(_repo_process_pkg_sls, globals())
    _get_latest_pkg_version = namespaced_function(_get_latest_pkg_version, globals())
    _reverse_cmp_pkg_versions = namespaced_function(
        _reverse_cmp_pkg_versions, globals()
    )

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only make these states available if a pkg provider has been detected or
    assigned for this minion
    """
    if "pkg.install" in __salt__:
        return True
    return (False, "pkg module could not be loaded")


def _get_comparison_spec(pkgver):
    """
    Return a tuple containing the comparison operator and the version. If no
    comparison operator was passed, the comparison is assumed to be an "equals"
    comparison, and "==" will be the operator returned.
    """
    oper, verstr = salt.utils.pkg.split_comparison(pkgver.strip())
    if oper in ("=", ""):
        oper = "=="
    return oper, verstr


def _check_ignore_epoch(oper, desired_version, ignore_epoch=None):
    """
    Conditionally ignore epoch, but only under all of the following
    circumstances:

    1. No value for ignore_epoch passed to state
    2. desired_version has no epoch
    3. oper does not contain a "<" or ">"
    """
    if ignore_epoch is not None:
        return ignore_epoch
    return "<" not in oper and ">" not in oper and ":" not in desired_version


def _parse_version_string(version_conditions_string):
    """
    Returns a list of two-tuples containing (operator, version).
    """
    result = []
    version_conditions_string = version_conditions_string.strip()
    if not version_conditions_string:
        return result
    for version_condition in version_conditions_string.split(","):
        operator_and_version = _get_comparison_spec(version_condition)
        result.append(operator_and_version)
    return result


def _fulfills_version_string(
    installed_versions,
    version_conditions_string,
    ignore_epoch=None,
    allow_updates=False,
):
    """
    Returns True if any of the installed versions match the specified version conditions,
    otherwise returns False.

    installed_versions
        The installed versions

    version_conditions_string
        The string containing all version conditions. E.G.
        1.2.3-4
        >=1.2.3-4
        >=1.2.3-4, <2.3.4-5
        >=1.2.3-4, <2.3.4-5, !=1.2.4-1

    ignore_epoch : None
        When a package version contains an non-zero epoch (e.g.
        ``1:3.14.159-2.el7``), and a specific version of a package is desired,
        set this option to ``True`` to ignore the epoch when comparing
        versions.

        .. versionchanged:: 3001
            If no value for this argument is passed to the state that calls
            this helper function, and ``version_conditions_string`` contains no
            epoch or greater-than/less-than, then the epoch will be ignored.

    allow_updates : False
        Allow the package to be updated outside Salt's control (e.g. auto updates on Windows).
        This means a package on the Minion can have a newer version than the latest available in
        the repository without enforcing a re-installation of the package.
        (Only applicable if only one strict version condition is specified E.G. version: 2.0.6~ubuntu3)
    """
    version_conditions = _parse_version_string(version_conditions_string)
    for installed_version in installed_versions:
        fullfills_all = True
        for operator, version_string in version_conditions:
            if allow_updates and len(version_conditions) == 1 and operator == "==":
                operator = ">="
            fullfills_all = fullfills_all and _fulfills_version_spec(
                [installed_version], operator, version_string, ignore_epoch=ignore_epoch
            )
        if fullfills_all:
            return True
    return False


def _fulfills_version_spec(versions, oper, desired_version, ignore_epoch=None):
    """
    Returns True if any of the installed versions match the specified version,
    otherwise returns False
    """
    cmp_func = __salt__.get("pkg.version_cmp")
    # stripping "with_origin" dict wrapper
    if salt.utils.platform.is_freebsd():
        if isinstance(versions, dict) and "version" in versions:
            versions = versions["version"]
    for ver in versions:
        if (
            oper == "==" and fnmatch.fnmatch(ver, desired_version)
        ) or salt.utils.versions.compare(
            ver1=ver,
            oper=oper,
            ver2=desired_version,
            cmp_func=cmp_func,
            ignore_epoch=_check_ignore_epoch(oper, desired_version, ignore_epoch),
        ):
            return True
    return False


def _find_unpurge_targets(desired, **kwargs):
    """
    Find packages which are marked to be purged but can't yet be removed
    because they are dependencies for other installed packages. These are the
    packages which will need to be 'unpurged' because they are part of
    pkg.installed states. This really just applies to Debian-based Linuxes.
    """
    return [
        x
        for x in desired
        if x in __salt__["pkg.list_pkgs"](purge_desired=True, **kwargs)
    ]


def _find_download_targets(
    name=None,
    version=None,
    pkgs=None,
    normalize=True,
    skip_suggestions=False,
    ignore_epoch=None,
    **kwargs,
):
    """
    Inspect the arguments to pkg.downloaded and discover what packages need to
    be downloaded. Return a dict of packages to download.
    """
    cur_pkgs = __salt__["pkg.list_downloaded"](**kwargs)
    if pkgs:
        # pylint: disable=not-callable
        to_download = _repack_pkgs(pkgs, normalize=normalize)
        # pylint: enable=not-callable

        if not to_download:
            # Badly-formatted SLS
            return {
                "name": name,
                "changes": {},
                "result": False,
                "comment": "Invalidly formatted pkgs parameter. See minion log.",
            }
    else:
        if normalize:
            _normalize_name = __salt__.get(
                "pkg.normalize_name", lambda pkgname: pkgname
            )
            to_download = {_normalize_name(name): version}
        else:
            to_download = {name: version}

        cver = cur_pkgs.get(name, {})
        if name in to_download:
            # Package already downloaded, no need to download again
            if cver and version in cver:
                return {
                    "name": name,
                    "changes": {},
                    "result": True,
                    "comment": (
                        "Version {} of package '{}' is already downloaded".format(
                            version, name
                        )
                    ),
                }

            # if cver is not an empty string, the package is already downloaded
            elif cver and version is None:
                # The package is downloaded
                return {
                    "name": name,
                    "changes": {},
                    "result": True,
                    "comment": f"Package {name} is already downloaded",
                }

    version_spec = False
    if not skip_suggestions:
        try:
            problems = _preflight_check(to_download, **kwargs)
        except CommandExecutionError:
            pass
        else:
            comments = []
            if problems.get("no_suggest"):
                comments.append(
                    "The following package(s) were not found, and no "
                    "possible matches were found in the package db: "
                    "{}".format(", ".join(sorted(problems["no_suggest"])))
                )
            if problems.get("suggest"):
                for pkgname, suggestions in problems["suggest"].items():
                    comments.append(
                        "Package '{}' not found (possible matches: {})".format(
                            pkgname, ", ".join(suggestions)
                        )
                    )
            if comments:
                if len(comments) > 1:
                    comments.append("")
                return {
                    "name": name,
                    "changes": {},
                    "result": False,
                    "comment": ". ".join(comments).rstrip(),
                }

    # Find out which packages will be targeted in the call to pkg.download
    # Check current downloaded versions against specified versions
    targets = {}
    problems = []
    for pkgname, pkgver in to_download.items():
        cver = cur_pkgs.get(pkgname, {})
        # Package not yet downloaded, so add to targets
        if not cver:
            targets[pkgname] = pkgver
            continue
        # No version specified but package is already downloaded
        elif cver and not pkgver:
            continue

        version_spec = True
        try:
            if not _fulfills_version_string(
                cver.keys(), pkgver, ignore_epoch=ignore_epoch
            ):
                targets[pkgname] = pkgver
        except CommandExecutionError as exc:
            problems.append(exc.strerror)
            continue

    if problems:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": " ".join(problems),
        }

    if not targets:
        # All specified packages are already downloaded
        msg = "All specified packages{} are already downloaded".format(
            " (matching specified versions)" if version_spec else ""
        )
        return {"name": name, "changes": {}, "result": True, "comment": msg}

    return targets


def _find_advisory_targets(name=None, advisory_ids=None, **kwargs):
    """
    Inspect the arguments to pkg.patch_installed and discover what advisory
    patches need to be installed. Return a dict of advisory patches to install.
    """
    cur_patches = __salt__["pkg.list_installed_patches"](**kwargs)
    if advisory_ids:
        to_download = advisory_ids
    else:
        to_download = [name]
        if cur_patches.get(name, {}):
            # Advisory patch already installed, no need to install it again
            return {
                "name": name,
                "changes": {},
                "result": True,
                "comment": f"Advisory patch {name} is already installed",
            }

    # Find out which advisory patches will be targeted in the call to pkg.install
    targets = []
    for patch_name in to_download:
        cver = cur_patches.get(patch_name, {})
        # Advisory patch not yet installed, so add to targets
        if not cver:
            targets.append(patch_name)
            continue

    if not targets:
        # All specified packages are already downloaded
        msg = "All specified advisory patches are already installed"
        return {"name": name, "changes": {}, "result": True, "comment": msg}

    return targets


def _find_remove_targets(
    name=None, version=None, pkgs=None, normalize=True, ignore_epoch=None, **kwargs
):
    """
    Inspect the arguments to pkg.removed and discover what packages need to
    be removed. Return a dict of packages to remove.
    """
    if __grains__["os"] == "FreeBSD":
        kwargs["with_origin"] = True
    cur_pkgs = __salt__["pkg.list_pkgs"](versions_as_list=True, **kwargs)
    if pkgs:
        # pylint: disable=not-callable
        to_remove = _repack_pkgs(pkgs, normalize=normalize)
        # pylint: enable=not-callable

        if not to_remove:
            # Badly-formatted SLS
            return {
                "name": name,
                "changes": {},
                "result": False,
                "comment": "Invalidly formatted pkgs parameter. See minion log.",
            }
    else:
        _normalize_name = __salt__.get("pkg.normalize_name", lambda pkgname: pkgname)
        to_remove = {_normalize_name(name): version}

    version_spec = False
    # Find out which packages will be targeted in the call to pkg.remove
    # Check current versions against specified versions
    targets = []
    problems = []
    for pkgname, pkgver in to_remove.items():
        # FreeBSD pkg supports `openjdk` and `java/openjdk7` package names
        origin = bool(re.search("/", pkgname))

        if __grains__["os"] == "FreeBSD" and origin:
            cver = [k for k, v in cur_pkgs.items() if v["origin"] == pkgname]
        else:
            cver = cur_pkgs.get(pkgname, [])

        # Package not installed, no need to remove
        if not cver:
            continue
        # No version specified and pkg is installed
        elif __salt__["pkg_resource.version_clean"](pkgver) is None:
            targets.append(pkgname)
            continue
        version_spec = True
        try:
            if _fulfills_version_string(cver, pkgver, ignore_epoch=ignore_epoch):
                targets.append(pkgname)
            else:
                log.debug(
                    "Current version (%s) did not match desired version "
                    "specification (%s), will not remove",
                    cver,
                    pkgver,
                )
        except CommandExecutionError as exc:
            problems.append(exc.strerror)
            continue

    if problems:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": " ".join(problems),
        }

    if not targets:
        # All specified packages are already absent
        msg = "All specified packages{} are already absent".format(
            " (matching specified versions)" if version_spec else ""
        )
        return {"name": name, "changes": {}, "result": True, "comment": msg}

    return targets


def _find_install_targets(
    name=None,
    version=None,
    pkgs=None,
    sources=None,
    skip_suggestions=False,
    pkg_verify=False,
    normalize=True,
    ignore_epoch=None,
    reinstall=False,
    refresh=False,
    **kwargs,
):
    """
    Inspect the arguments to pkg.installed and discover what packages need to
    be installed. Return a dict of desired packages
    """
    was_refreshed = False

    if all((pkgs, sources)):
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": 'Only one of "pkgs" and "sources" is permitted.',
        }

    # dict for packages that fail pkg.verify and their altered files
    altered_files = {}
    # Get the ignore_types list if any from the pkg_verify argument
    if isinstance(pkg_verify, list) and any(
        x.get("ignore_types") is not None
        for x in pkg_verify
        if isinstance(x, _OrderedDict) and "ignore_types" in x
    ):
        ignore_types = next(
            x.get("ignore_types") for x in pkg_verify if "ignore_types" in x
        )
    else:
        ignore_types = []

    # Get the verify_options list if any from the pkg_verify argument
    if isinstance(pkg_verify, list) and any(
        x.get("verify_options") is not None
        for x in pkg_verify
        if isinstance(x, _OrderedDict) and "verify_options" in x
    ):
        verify_options = next(
            x.get("verify_options") for x in pkg_verify if "verify_options" in x
        )
    else:
        verify_options = []

    if __grains__["os"] == "FreeBSD":
        kwargs["with_origin"] = True

    if salt.utils.platform.is_windows():
        # Windows requires a refresh to establish a pkg db if refresh=True, so
        # add it to the kwargs.
        kwargs["refresh"] = refresh

    resolve_capabilities = (
        kwargs.get("resolve_capabilities", False) and "pkg.list_provides" in __salt__
    )
    try:
        cur_pkgs = __salt__["pkg.list_pkgs"](versions_as_list=True, **kwargs)
        cur_prov = (
            resolve_capabilities and __salt__["pkg.list_provides"](**kwargs) or dict()
        )
    except CommandExecutionError as exc:
        return {"name": name, "changes": {}, "result": False, "comment": exc.strerror}

    if salt.utils.platform.is_windows() and kwargs.pop("refresh", False):
        # We already refreshed when we called pkg.list_pkgs
        was_refreshed = True
        refresh = False

    if any((pkgs, sources)):
        if pkgs:
            # pylint: disable=not-callable
            desired = _repack_pkgs(pkgs, normalize=normalize)
            # pylint: enable=not-callable
        elif sources:
            desired = __salt__["pkg_resource.pack_sources"](
                sources,
                normalize=normalize,
            )

        if not desired:
            # Badly-formatted SLS
            return {
                "name": name,
                "changes": {},
                "result": False,
                "comment": "Invalidly formatted '{}' parameter. See minion log.".format(
                    "pkgs" if pkgs else "sources"
                ),
            }

        to_unpurge = _find_unpurge_targets(desired, **kwargs)
    else:
        if salt.utils.platform.is_windows():
            # pylint: disable=not-callable
            pkginfo = _get_package_info(name, saltenv=kwargs["saltenv"])
            # pylint: enable=not-callable
            if not pkginfo:
                return {
                    "name": name,
                    "changes": {},
                    "result": False,
                    "comment": f"Package {name} not found in the repository.",
                }
            if version is None:
                # pylint: disable=not-callable
                version = _get_latest_pkg_version(pkginfo)
                # pylint: enable=not-callable

        if normalize:
            _normalize_name = __salt__.get(
                "pkg.normalize_name", lambda pkgname: pkgname
            )
            desired = {_normalize_name(name): version}
        else:
            desired = {name: version}

        to_unpurge = _find_unpurge_targets(desired, **kwargs)

        # FreeBSD pkg supports `openjdk` and `java/openjdk7` package names
        origin = bool(re.search("/", name))

        if __grains__["os"] == "FreeBSD" and origin:
            cver = [k for k, v in cur_pkgs.items() if v["origin"] == name]
        else:
            cver = cur_pkgs.get(name, [])

        if name not in to_unpurge:
            if version and version in cver and not reinstall and not pkg_verify:
                # The package is installed and is the correct version
                return {
                    "name": name,
                    "changes": {},
                    "result": True,
                    "comment": "Version {} of package '{}' is already installed".format(
                        version, name
                    ),
                }

            # if cver is not an empty string, the package is already installed
            elif cver and version is None and not reinstall and not pkg_verify:
                # The package is installed
                return {
                    "name": name,
                    "changes": {},
                    "result": True,
                    "comment": f"Package {name} is already installed",
                }

    version_spec = False
    if not sources:
        # Check for alternate package names if strict processing is not
        # enforced. Takes extra time. Disable for improved performance
        if not skip_suggestions:
            # Perform platform-specific pre-flight checks
            not_installed = {
                name: version
                for name, version in desired.items()
                if not (
                    name in cur_pkgs
                    and (
                        version is None
                        or _fulfills_version_string(
                            cur_pkgs[name], version, ignore_epoch=ignore_epoch
                        )
                    )
                )
            }
            if not_installed:
                try:
                    problems = _preflight_check(not_installed, **kwargs)
                except CommandExecutionError:
                    pass
                else:
                    comments = []
                    if problems.get("no_suggest"):
                        comments.append(
                            "The following package(s) were not found, and no "
                            "possible matches were found in the package db: "
                            "{}".format(", ".join(sorted(problems["no_suggest"])))
                        )
                    if problems.get("suggest"):
                        for pkgname, suggestions in problems["suggest"].items():
                            comments.append(
                                "Package '{}' not found (possible matches: {})".format(
                                    pkgname, ", ".join(suggestions)
                                )
                            )
                    if comments:
                        if len(comments) > 1:
                            comments.append("")
                        return {
                            "name": name,
                            "changes": {},
                            "result": False,
                            "comment": ". ".join(comments).rstrip(),
                        }

    # Resolve the latest package version for any packages with "latest" in the
    # package version
    wants_latest = [] if sources else [x for x, y in desired.items() if y == "latest"]
    if wants_latest:
        resolved_latest = __salt__["pkg.latest_version"](
            *wants_latest, refresh=refresh, **kwargs
        )
        if len(wants_latest) == 1:
            resolved_latest = {wants_latest[0]: resolved_latest}
        if refresh:
            was_refreshed = True
            refresh = False

        # pkg.latest_version returns an empty string when the package is
        # up-to-date. So check the currently-installed packages. If found, the
        # resolved latest version will be the currently installed one from
        # cur_pkgs. If not found, then the package doesn't exist and the
        # resolved latest version will be None.
        for key in resolved_latest:
            if not resolved_latest[key]:
                if key in cur_pkgs:
                    resolved_latest[key] = cur_pkgs[key][-1]
                else:
                    resolved_latest[key] = None
        # Update the desired versions with the ones we resolved
        desired.update(resolved_latest)

    # Find out which packages will be targeted in the call to pkg.install
    targets = {}
    to_reinstall = {}
    problems = []
    warnings = []
    failed_verify = False
    for package_name, version_string in desired.items():
        cver = cur_pkgs.get(package_name, [])
        if resolve_capabilities and not cver and package_name in cur_prov:
            cver = cur_pkgs.get(cur_prov.get(package_name)[0], [])

        # Package not yet installed, so add to targets
        if not cver:
            targets[package_name] = version_string
            continue
        if sources:
            if reinstall:
                to_reinstall[package_name] = version_string
                continue
            elif "lowpkg.bin_pkg_info" not in __salt__:
                continue
            # Metadata parser is available, cache the file and derive the
            # package's name and version
            err = "Unable to cache {0}: {1}"
            try:
                cached_path = __salt__["cp.cache_file"](
                    version_string,
                    saltenv=kwargs["saltenv"],
                    verify_ssl=kwargs.get("verify_ssl", True),
                )
            except CommandExecutionError as exc:
                problems.append(err.format(version_string, exc))
                continue
            if not cached_path:
                problems.append(err.format(version_string, "file not found"))
                continue
            elif not os.path.exists(cached_path):
                problems.append(f"{version_string} does not exist on minion")
                continue
            source_info = __salt__["lowpkg.bin_pkg_info"](cached_path)
            if source_info is None:
                warnings.append(f"Failed to parse metadata for {version_string}")
                continue
            else:
                verstr = source_info["version"]
        else:
            verstr = version_string
            if reinstall:
                to_reinstall[package_name] = version_string
                continue
            if not __salt__["pkg_resource.check_extra_requirements"](
                package_name, version_string
            ):
                targets[package_name] = version_string
                continue
            # No version specified and pkg is installed
            elif __salt__["pkg_resource.version_clean"](version_string) is None:
                if (not reinstall) and pkg_verify:
                    try:
                        verify_result = __salt__["pkg.verify"](
                            package_name,
                            ignore_types=ignore_types,
                            verify_options=verify_options,
                            **kwargs,
                        )
                    except (CommandExecutionError, SaltInvocationError) as exc:
                        failed_verify = exc.strerror
                        continue
                    if verify_result:
                        to_reinstall[package_name] = version_string
                        altered_files[package_name] = verify_result
                continue
        version_fulfilled = False
        allow_updates = bool(not sources and kwargs.get("allow_updates"))
        try:
            version_fulfilled = _fulfills_version_string(
                cver, verstr, ignore_epoch=ignore_epoch, allow_updates=allow_updates
            )
        except CommandExecutionError as exc:
            problems.append(exc.strerror)
            continue

        # Compare desired version against installed version.
        version_spec = True
        if not version_fulfilled:
            if reinstall:
                to_reinstall[package_name] = version_string
            else:
                version_conditions = _parse_version_string(version_string)
                if pkg_verify and any(
                    oper == "==" for oper, version in version_conditions
                ):
                    try:
                        verify_result = __salt__["pkg.verify"](
                            package_name,
                            ignore_types=ignore_types,
                            verify_options=verify_options,
                            **kwargs,
                        )
                    except (CommandExecutionError, SaltInvocationError) as exc:
                        failed_verify = exc.strerror
                        continue
                    if verify_result:
                        to_reinstall[package_name] = version_string
                        altered_files[package_name] = verify_result
                else:
                    log.debug(
                        "Current version (%s) did not match desired version "
                        "specification (%s), adding to installation targets",
                        cver,
                        version_string,
                    )
                    targets[package_name] = version_string

    if failed_verify:
        problems.append(failed_verify)

    if problems:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": " ".join(problems),
        }

    if not any((targets, to_unpurge, to_reinstall)):
        # All specified packages are installed
        msg = "All specified packages are already installed{0}"
        msg = msg.format(
            " and are at the desired version" if version_spec and not sources else ""
        )
        ret = {"name": name, "changes": {}, "result": True, "comment": msg}
        if warnings:
            ret.setdefault("warnings", []).extend(warnings)
        return ret

    return (
        desired,
        targets,
        to_unpurge,
        to_reinstall,
        altered_files,
        warnings,
        was_refreshed,
    )


def _verify_install(desired, new_pkgs, ignore_epoch=None, new_caps=None):
    """
    Determine whether or not the installed packages match what was requested in
    the SLS file.
    """
    _ok = []
    failed = []
    if not new_caps:
        new_caps = dict()
    for pkgname, pkgver in desired.items():
        # FreeBSD pkg supports `openjdk` and `java/openjdk7` package names.
        # Homebrew for Mac OSX does something similar with tap names
        # prefixing package names, separated with a slash.
        has_origin = "/" in pkgname

        if __grains__["os"] == "FreeBSD" and has_origin:
            cver = [k for k, v in new_pkgs.items() if v["origin"] == pkgname]
        elif __grains__["os"] == "MacOS" and has_origin:
            cver = new_pkgs.get(pkgname, new_pkgs.get(pkgname.split("/")[-1]))
        elif __grains__["os"] == "OpenBSD":
            cver = new_pkgs.get(pkgname.split("%")[0])
        elif __grains__["os_family"] == "Debian":
            cver = new_pkgs.get(pkgname.split("=")[0])
        else:
            cver = new_pkgs.get(pkgname)
            if not cver and pkgname in new_caps:
                cver = new_pkgs.get(new_caps.get(pkgname)[0])

        if not cver:
            failed.append(pkgname)
            continue
        elif pkgver == "latest":
            _ok.append(pkgname)
            continue
        elif not __salt__["pkg_resource.version_clean"](pkgver):
            _ok.append(pkgname)
            continue
        elif pkgver.endswith("*") and cver[0].startswith(pkgver[:-1]):
            _ok.append(pkgname)
            continue
        if _fulfills_version_string(cver, pkgver, ignore_epoch=ignore_epoch):
            _ok.append(pkgname)
        else:
            failed.append(pkgname)
    return _ok, failed


def _get_desired_pkg(name, desired):
    """
    Helper function that retrieves and nicely formats the desired pkg (and
    version if specified) so that helpful information can be printed in the
    comment for the state.
    """
    if not desired[name] or desired[name].startswith(("<", ">", "=")):
        oper = ""
    else:
        oper = "="
    return "{}{}{}".format(name, oper, "" if not desired[name] else desired[name])


def _preflight_check(desired, fromrepo, **kwargs):
    """
    Perform platform-specific checks on desired packages
    """
    if "pkg.check_db" not in __salt__:
        return {}
    ret = {"suggest": {}, "no_suggest": []}
    pkginfo = __salt__["pkg.check_db"](
        *list(desired.keys()), fromrepo=fromrepo, **kwargs
    )
    for pkgname in pkginfo:
        if pkginfo[pkgname]["found"] is False:
            if pkginfo[pkgname]["suggestions"]:
                ret["suggest"][pkgname] = pkginfo[pkgname]["suggestions"]
            else:
                ret["no_suggest"].append(pkgname)
    return ret


def _nested_output(obj):
    """
    Serialize obj and format for output
    """
    nested.__opts__ = __opts__
    ret = nested.output(obj).rstrip()
    return ret


def _resolve_capabilities(pkgs, refresh=False, **kwargs):
    """
    Resolve capabilities in ``pkgs`` and exchange them with real package
    names, when the result is distinct.
    This feature can be turned on while setting the paramter
    ``resolve_capabilities`` to True.

    Return the input dictionary with replaced capability names and as
    second return value a bool which say if a refresh need to be run.

    In case of ``resolve_capabilities`` is False (disabled) or not
    supported by the implementation the input is returned unchanged.
    """
    if not pkgs or "pkg.resolve_capabilities" not in __salt__:
        return pkgs, refresh

    ret = __salt__["pkg.resolve_capabilities"](pkgs, refresh=refresh, **kwargs)
    return ret, False


def _get_installable_versions(targets, current=None):
    """
    .. versionadded:: 3007.0

    Return a dictionary of changes that will be made to install a version of
    each target package specified in the ``targets`` dictionary.  If ``current``
    is specified, it should be a dictionary of package names to currently
    installed versions. The function returns a dictionary of changes, where the
    keys are the package names and the values are dictionaries with two keys:
    "old" and "new". The value for "old" is the currently installed version (if
    available) or an empty string, and the value for "new" is the latest
    available version of the package or "installed".

    :param targets: A dictionary where the keys are package names and the
                    values indicate a specific version or ``None`` if the
                    latest should be used.
    :type targets: dict
    :param current: A dictionary where the keys are package names and the
                    values are currently installed versions.
    :type current: dict or None
    :return: A dictionary of changes to be made to install a version of
             each package.
    :rtype: dict
    """
    if current is None:
        current = {}
    changes = installable_versions = {}
    latest_targets = [_get_desired_pkg(x, targets) for x, y in targets.items() if not y]
    latest_versions = __salt__["pkg.latest_version"](*latest_targets)
    if latest_targets:
        # single pkg returns str
        if isinstance(latest_versions, str):
            installable_versions = {latest_targets[0]: latest_versions}
        elif isinstance(latest_versions, dict):
            installable_versions = latest_versions
    explicit_targets = [
        _get_desired_pkg(x, targets) for x in targets if x not in latest_targets
    ]
    if explicit_targets:
        explicit_versions = __salt__["pkg.list_repo_pkgs"](*explicit_targets)
        for tgt, ver_list in explicit_versions.items():
            if ver_list:
                installable_versions[tgt] = ver_list[0]
    changes.update(
        {
            x: {
                "new": installable_versions.get(x) or "installed",
                "old": current.get(x, ""),
            }
            for x in targets
        }
    )
    return changes


def installed(
    name,
    version=None,
    refresh=None,
    fromrepo=None,
    skip_verify=False,
    skip_suggestions=False,
    pkgs=None,
    sources=None,
    allow_updates=False,
    pkg_verify=False,
    normalize=True,
    ignore_epoch=None,
    reinstall=False,
    update_holds=False,
    **kwargs,
):
    """
    .. versionchanged:: 3007.0

    Ensure that the package is installed, and that it is the correct version
    (if specified).

    .. note::
        Any argument which is either a) not explicitly defined for this state,
        or b) not a global state argument like ``saltenv``, or
        ``reload_modules``, will be passed through to the call to
        ``pkg.install`` to install the package(s). For example, you can include
        a ``disablerepo`` argument on platforms that use yum/dnf to disable
        that repo:

        .. code-block:: yaml

            mypkg:
              pkg.installed:
                - disablerepo: base,updates

        To see what is supported, check :ref:`this page <virtual-pkg>` to find
        the documentation for your platform's ``pkg`` module, then look at the
        documentation for the ``install`` function.

        Any argument that is passed through to the ``install`` function, which
        is not defined for that function, will be silently ignored.

    .. note::
        In Windows, some packages are installed using the task manager. The Salt
        minion installer does this. In that case, there is no way to know if the
        package installs correctly. All that can be reported is that the task
        that launches the installer started successfully.

    :param str name:
        The name of the package to be installed. This parameter is ignored if
        either "pkgs" or "sources" is used. Additionally, please note that this
        option can only be used to install packages from a software repository.
        To install a package file manually, use the "sources" option detailed
        below.

    :param str version:
        Install a specific version of a package. This option is ignored if
        "sources" is used. Currently, this option is supported
        for the following pkg providers: :mod:`apt <salt.modules.aptpkg>`,
        :mod:`ebuild <salt.modules.ebuild>`,
        :mod:`pacman <salt.modules.pacman>`,
        :mod:`pkgin <salt.modules.pkgin>`,
        :mod:`win_pkg <salt.modules.win_pkg>`,
        :mod:`yum <salt.modules.yumpkg>`, and
        :mod:`zypper <salt.modules.zypperpkg>`. The version number includes the
        release designation where applicable, to allow Salt to target a
        specific release of a given version. When in doubt, using the
        ``pkg.latest_version`` function for an uninstalled package will tell
        you the version available.

        .. code-block:: bash

            # salt myminion pkg.latest_version vim-enhanced
            myminion:
                2:7.4.160-1.el7

        .. important::
            As of version 2015.8.7, for distros which use yum/dnf, packages
            which have a version with a nonzero epoch (that is, versions which
            start with a number followed by a colon like in the
            ``pkg.latest_version`` output above) must have the epoch included
            when specifying the version number. For example:

            .. code-block:: yaml

                vim-enhanced:
                  pkg.installed:
                    - version: 2:7.4.160-1.el7

            In version 2015.8.9, an **ignore_epoch** argument has been added to
            :py:mod:`pkg.installed <salt.states.pkg.installed>`,
            :py:mod:`pkg.removed <salt.states.pkg.removed>`, and
            :py:mod:`pkg.purged <salt.states.pkg.purged>` states, which
            causes the epoch to be disregarded when the state checks to see if
            the desired version was installed.

        Also, while this function is not yet implemented for all pkg frontends,
        :mod:`pkg.list_repo_pkgs <salt.modules.yumpkg.list_repo_pkgs>` will
        show all versions available in the various repositories for a given
        package, irrespective of whether or not it is installed.

        .. code-block:: bash

            # salt myminion pkg.list_repo_pkgs bash
            myminion:
            ----------
                bash:
                    - 4.2.46-21.el7_3
                    - 4.2.46-20.el7_2

        This function was first added for :mod:`pkg.list_repo_pkgs
        <salt.modules.yumpkg.list_repo_pkgs>` in 2014.1.0, and was expanded to
        :py:func:`Debian/Ubuntu <salt.modules.aptpkg.list_repo_pkgs>` and
        :py:func:`Arch Linux <salt.modules.pacman.list_repo_pkgs>`-based
        distros in the 2017.7.0 release.

        The version strings returned by either of these functions can be used
        as version specifiers in pkg states.

        You can install a specific version when using the ``pkgs`` argument by
        including the version after the package:

        .. code-block:: yaml

            common_packages:
              pkg.installed:
                - pkgs:
                  - unzip
                  - dos2unix
                  - salt-minion: 2015.8.5-1.el6

        If the version given is the string ``latest``, the latest available
        package version will be installed à la ``pkg.latest``.

        **WILDCARD VERSIONS**

        As of the 2017.7.0 release, this state now supports wildcards in
        package versions for SUSE SLES/Leap/Tumbleweed, Debian/Ubuntu,
        RHEL/CentOS, Arch Linux, and their derivatives. Using wildcards can be
        useful for packages where the release name is built into the version in
        some way, such as for RHEL/CentOS which typically has version numbers
        like ``1.2.34-5.el7``. An example of the usage for this would be:

        .. code-block:: yaml

            mypkg:
              pkg.installed:
                - version: '1.2.34*'

        Keep in mind that using wildcard versions will result in a slower state
        run since Salt must gather the available versions of the specified
        packages and figure out which of them match the specified wildcard
        expression.

    :param bool refresh:
        This parameter controls whether or not the package repo database is
        updated prior to installing the requested package(s).

        If ``True``, the package database will be refreshed (``apt-get
        update`` or equivalent, depending on platform) before installing.

        If ``False``, the package database will *not* be refreshed before
        installing.

        If unset, then Salt treats package database refreshes differently
        depending on whether or not a ``pkg`` state has been executed already
        during the current Salt run. Once a refresh has been performed in a
        ``pkg`` state, for the remainder of that Salt run no other refreshes
        will be performed for ``pkg`` states which do not explicitly set
        ``refresh`` to ``True``. This prevents needless additional refreshes
        from slowing down the Salt run.

    :param str cache_valid_time:

        .. versionadded:: 2016.11.0

        This parameter sets the value in seconds after which the cache is
        marked as invalid, and a cache update is necessary. This overwrites
        the ``refresh`` parameter's default behavior.

        Example:

        .. code-block:: yaml

            httpd:
              pkg.installed:
                - fromrepo: mycustomrepo
                - skip_verify: True
                - skip_suggestions: True
                - version: 2.0.6~ubuntu3
                - refresh: True
                - cache_valid_time: 300
                - allow_updates: True
                - hold: False

        In this case, a refresh will not take place for 5 minutes since the last
        ``apt-get update`` was executed on the system.

        .. note::

            This parameter is available only on Debian based distributions and
            has no effect on the rest.

    :param str fromrepo:
        Specify a repository from which to install

        .. note::

            Distros which use APT (Debian, Ubuntu, etc.) do not have a concept
            of repositories, in the same way as YUM-based distros do. When a
            source is added, it is assigned to a given release. Consider the
            following source configuration:

            .. code-block:: text

                deb http://ppa.launchpad.net/saltstack/salt/ubuntu precise main

            The packages provided by this source would be made available via
            the ``precise`` release, therefore ``fromrepo`` would need to be
            set to ``precise`` for Salt to install the package from this
            source.

            Having multiple sources in the same release may result in the
            default install candidate being newer than what is desired. If this
            is the case, the desired version must be specified using the
            ``version`` parameter.

            If the ``pkgs`` parameter is being used to install multiple
            packages in the same state, then instead of using ``version``,
            use the method of version specification described in the **Multiple
            Package Installation Options** section below.

            Running the shell command ``apt-cache policy pkgname`` on a minion
            can help elucidate the APT configuration and aid in properly
            configuring states:

            .. code-block:: bash

                root@saltmaster:~# salt ubuntu01 cmd.run 'apt-cache policy ffmpeg'
                ubuntu01:
                    ffmpeg:
                    Installed: (none)
                    Candidate: 7:0.10.11-1~precise1
                    Version table:
                        7:0.10.11-1~precise1 0
                            500 http://ppa.launchpad.net/jon-severinsson/ffmpeg/ubuntu/ precise/main amd64 Packages
                        4:0.8.10-0ubuntu0.12.04.1 0
                            500 http://us.archive.ubuntu.com/ubuntu/ precise-updates/main amd64 Packages
                            500 http://security.ubuntu.com/ubuntu/ precise-security/main amd64 Packages
                        4:0.8.1-0ubuntu1 0
                            500 http://us.archive.ubuntu.com/ubuntu/ precise/main amd64 Packages

            The release is located directly after the source's URL. The actual
            release name is the part before the slash, so to install version
            **4:0.8.10-0ubuntu0.12.04.1** either ``precise-updates`` or
            ``precise-security`` could be used for the ``fromrepo`` value.

    :param bool skip_verify:
        Skip the GPG verification check for the package to be installed

    :param bool skip_suggestions:
        Force strict package naming. Disables lookup of package alternatives.

        .. versionadded:: 2014.1.1

    :param bool resolve_capabilities:
        Turn on resolving capabilities. This allow one to name "provides" or alias names for packages.

        .. versionadded:: 2018.3.0

    :param bool allow_updates:
        Allow the package to be updated outside Salt's control (e.g. auto
        updates on Windows). This means a package on the Minion can have a
        newer version than the latest available in the repository without
        enforcing a re-installation of the package.

        .. versionadded:: 2014.7.0

        Example:

        .. code-block:: yaml

            httpd:
              pkg.installed:
                - fromrepo: mycustomrepo
                - skip_verify: True
                - skip_suggestions: True
                - version: 2.0.6~ubuntu3
                - refresh: True
                - allow_updates: True
                - hold: False

    :param bool pkg_verify:

        .. versionadded:: 2014.7.0

        Use pkg.verify to check if already installed packages require
        reinstallion. Requested packages that are already installed and not
        targeted for up- or downgrade are verified with pkg.verify to determine
        if any file installed by the package have been modified or if package
        dependencies are not fulfilled. ``ignore_types`` and ``verify_options``
        can be passed to pkg.verify. See examples below. Currently, this option
        is supported for the following pkg providers:
        :mod:`yum <salt.modules.yumpkg>`,
        :mod:`zypperpkg <salt.modules.zypperpkg>`.

        Examples:

        .. code-block:: yaml

            httpd:
              pkg.installed:
                - version: 2.2.15-30.el6.centos
                - pkg_verify: True

        .. code-block:: yaml

            mypkgs:
              pkg.installed:
                - pkgs:
                  - foo
                  - bar: 1.2.3-4
                  - baz
                - pkg_verify:
                  - ignore_types:
                    - config
                    - doc

        .. code-block:: yaml

            mypkgs:
              pkg.installed:
                - pkgs:
                  - foo
                  - bar: 1.2.3-4
                  - baz
                - pkg_verify:
                  - ignore_types:
                    - config
                    - doc
                  - verify_options:
                    - nodeps
                    - nofiledigest

    :param list ignore_types:
        List of types to ignore when verifying the package

        .. versionadded:: 2014.7.0

    :param list verify_options:
        List of additional options to pass when verifying the package. These
        options will be added to the ``rpm -V`` command, prepended with ``--``
        (for example, when ``nodeps`` is passed in this option, ``rpm -V`` will
        be run with ``--nodeps``).

        .. versionadded:: 2016.11.0

    :param bool normalize:
        Normalize the package name by removing the architecture, if the
        architecture of the package is different from the architecture of the
        operating system. The ability to disable this behavior is useful for
        poorly-created packages which include the architecture as an actual
        part of the name, such as kernel modules which match a specific kernel
        version.

        .. versionadded:: 2014.7.0

        Example:

        .. code-block:: yaml

            gpfs.gplbin-2.6.32-279.31.1.el6.x86_64:
              pkg.installed:
                - normalize: False

    :param bool ignore_epoch:
        If this option is not explicitly set, and there is no epoch in the
        desired package version, the epoch will be implicitly ignored. Set this
        argument to ``True`` to explicitly ignore the epoch, and ``False`` to
        strictly enforce it.

        .. versionadded:: 2015.8.9

        .. versionchanged:: 3001
            In prior releases, the default behavior was to strictly enforce
            epochs unless this argument was set to ``True``.

    |

    **MULTIPLE PACKAGE INSTALLATION OPTIONS:**

    :param list pkgs:
        A list of packages to install from a software repository. All packages
        listed under ``pkgs`` will be installed via a single command.

        .. code-block:: yaml

            mypkgs:
              pkg.installed:
                - pkgs:
                  - foo
                  - bar
                  - baz
                - hold: True

        ``NOTE:`` For :mod:`apt <salt.modules.aptpkg>`,
        :mod:`ebuild <salt.modules.ebuild>`,
        :mod:`pacman <salt.modules.pacman>`,
        :mod:`winrepo <salt.modules.win_pkg>`,
        :mod:`yum <salt.modules.yumpkg>`, and
        :mod:`zypper <salt.modules.zypperpkg>`,
        version numbers can be specified
        in the ``pkgs`` argument. For example:

        .. code-block:: yaml

            mypkgs:
              pkg.installed:
                - pkgs:
                  - foo
                  - bar: 1.2.3-4
                  - baz

        Additionally, :mod:`ebuild <salt.modules.ebuild>`, :mod:`pacman
        <salt.modules.pacman>`, :mod:`zypper <salt.modules.zypperpkg>`,
        :mod:`yum/dnf <salt.modules.yumpkg>`, and :mod:`apt
        <salt.modules.aptpkg>` support the ``<``, ``<=``, ``>=``, and ``>``
        operators for more control over what versions will be installed. For
        example:

        .. code-block:: yaml

            mypkgs:
              pkg.installed:
                - pkgs:
                  - foo
                  - bar: '>=1.2.3-4'
                  - baz

        ``NOTE:`` When using comparison operators, the expression must be enclosed
        in quotes to avoid a YAML render error.

        With :mod:`ebuild <salt.modules.ebuild>` is also possible to specify a
        use flag list and/or if the given packages should be in
        package.accept_keywords file and/or the overlay from which you want the
        package to be installed. For example:

        .. code-block:: yaml

            mypkgs:
              pkg.installed:
                - pkgs:
                  - foo: '~'
                  - bar: '~>=1.2:slot::overlay[use,-otheruse]'
                  - baz

    :param list sources:
        A list of packages to install, along with the source URI or local path
        from which to install each package. In the example below, ``foo``,
        ``bar``, ``baz``, etc. refer to the name of the package, as it would
        appear in the output of the ``pkg.version`` or ``pkg.list_pkgs`` salt
        CLI commands.

        .. code-block:: yaml

            mypkgs:
              pkg.installed:
                - sources:
                  - foo: salt://rpms/foo.rpm
                  - bar: http://somesite.org/bar.rpm
                  - baz: ftp://someothersite.org/baz.rpm
                  - qux: /minion/path/to/qux.rpm

    **PLATFORM-SPECIFIC ARGUMENTS**

    These are specific to each OS. If it does not apply to the execution
    module for your OS, it is ignored.

    :param bool hold:
        Force the package to be held at the current installed version.

        Supported on YUM/DNF & APT based systems.

        .. versionadded:: 2014.7.0

        Supported on Zypper-based systems.

        .. versionadded:: 3003

    :param bool update_holds:
        If ``True``, and this function would update the package version, any
        packages which are being held will be temporarily unheld so that they
        can be updated. Otherwise, if this function attempts to update a held
        package, the held package(s) will be skipped and the state will fail.
        By default, this parameter is set to ``False``.

        Supported on YUM/DNF & APT based systems.

        .. versionadded:: 2016.11.0

        Supported on Zypper-based systems.

        .. versionadded:: 3003

    :param list names:
        A list of packages to install from a software repository. Each package
        will be installed individually by the package manager.

        .. warning::

            Unlike ``pkgs``, the ``names`` parameter cannot specify a version.
            In addition, it makes a separate call to the package management
            frontend to install each package, whereas ``pkgs`` makes just a
            single call. It is therefore recommended to use ``pkgs`` instead of
            ``names`` to install multiple packages, both for the additional
            features and the performance improvement that it brings.

    :param bool install_recommends:
        Whether to install the packages marked as recommended. Default is
        ``True``. Currently only works with APT-based systems.

        .. versionadded:: 2015.5.0

        .. code-block:: yaml

            httpd:
              pkg.installed:
                - install_recommends: False

    :param bool only_upgrade:
        Only upgrade the packages, if they are already installed. Default is
        ``False``. Currently only works with APT-based systems.

        .. versionadded:: 2015.5.0

        .. code-block:: yaml

            httpd:
              pkg.installed:
                - only_upgrade: True

        .. note::
            If this parameter is set to True and the package is not already
            installed, the state will fail.

    :param bool report_reboot_exit_codes:
       If the installer exits with a recognized exit code indicating that
       a reboot is required, the module function

           *win_system.set_reboot_required_witnessed*

       will be called, preserving the knowledge of this event
       for the remainder of the current boot session. For the time being,
       ``3010`` is the only recognized exit code,
       but this is subject to future refinement.
       The value of this param
       defaults to ``True``. This parameter has no effect
       on non-Windows systems.

       .. versionadded:: 2016.11.0

       .. code-block:: yaml

           ms vcpp installed:
             pkg.installed:
               - name: ms-vcpp
               - version: 10.0.40219
               - report_reboot_exit_codes: False

    :return:
        A dictionary containing the state of the software installation
    :rtype dict:

    .. note::

        The ``pkg.installed`` state supports the usage of ``reload_modules``.
        This functionality allows you to force Salt to reload all modules. In
        many cases, Salt is clever enough to transparently reload the modules.
        For example, if you install a package, Salt reloads modules because some
        other module or state might require the package which was installed.
        However, there are some edge cases where this may not be the case, which
        is what ``reload_modules`` is meant to resolve.

        You should only use ``reload_modules`` if your ``pkg.installed`` does some
        sort of installation where if you do not reload the modules future items
        in your state which rely on the software being installed will fail. Please
        see the :ref:`Reloading Modules <reloading-modules>` documentation for more
        information.

    .. seealso:: unless and onlyif

        If running pkg commands together with :ref:`aggregate <mod-aggregate-state>`
        isn't an option, you can use the :ref:`creates <creates-requisite>`,
        :ref:`unless <unless-requisite>`, or :ref:`onlyif <onlyif-requisite>`
        syntax to skip a full package run. This can be helpful in large environments
        with multiple states that include requisites for packages to be installed.

        .. code-block:: yaml

            # Using creates for a simple single-factor check
            install_nginx:
              pkg.installed:
                - name: nginx
                - creates:
                  - /etc/nginx/nginx.conf

        .. code-block:: yaml

            # Using file.file_exists for a single-factor check
            install_nginx:
              pkg.installed:
                - name: nginx
                - unless:
                  - fun: file.file_exists
                    args:
                      - /etc/nginx/nginx.conf

            # Using unless with a shell test
            install_nginx:
              pkg.installed:
                - name: nginx
                - unless: test -f /etc/nginx/nginx.conf

        .. code-block:: yaml

            # Using file.search for a two-factor check
            install_nginx:
              pkg.installed:
                - name: nginx
                - unless:
                  - fun: file.search
                    args:
                      - /etc/nginx/nginx.conf
                      - 'user www-data;'

        The above examples use different methods to reasonably ensure
        that a package has already been installed. First, with checking for a
        file that would be created with the package. Second, by checking for
        specific text within a file that would be created or managed by salt.
        With these requisists satisfied, creates/unless will return ``True`` and the
        ``pkg.installed`` state will be skipped.

        .. code-block:: bash

            # Example of state run without unless used
            salt 'saltdev' state.apply nginx
            saltdev:
            ----------
                      ID: install_nginx
                      Function: pkg.installed
                      Name: nginx
                      Result: True
                      Comment: All specified packages are already installed
                      Started: 20:11:56.388331
                      Duration: 4290.0 ms
                      Changes:

            # Example of state run using unless requisite
            salt 'saltdev' state.apply nginx
            saltdev:
            ----------
                      ID: install_nginx
                      Function: pkg.installed
                      Name: nginx
                      Result: True
                      Comment: unless condition is true
                      Started: 20:10:50.659215
                      Duration: 1530.0 ms
                      Changes:

        The result is a reduction of almost 3 seconds. In larger environments,
        small reductions in waiting time can add up.

        :ref:`Unless Requisite <unless-requisite>`
    """
    if isinstance(pkgs, list) and len(pkgs) == 0:
        return {
            "name": name,
            "changes": {},
            "result": True,
            "comment": "No packages to install provided",
        }

    # If just a name (and optionally a version) is passed, just pack them into
    # the pkgs argument.
    if name and not any((pkgs, sources)):
        if version:
            pkgs = [{name: version}]
            version = None
        else:
            pkgs = [name]

    kwargs["saltenv"] = __env__
    refresh = salt.utils.pkg.check_refresh(__opts__, refresh)

    # check if capabilities should be checked and modify the requested packages
    # accordingly.
    if pkgs:
        pkgs, refresh = _resolve_capabilities(pkgs, refresh=refresh, **kwargs)

    if not isinstance(pkg_verify, list):
        pkg_verify = pkg_verify is True
    if (pkg_verify or isinstance(pkg_verify, list)) and "pkg.verify" not in __salt__:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": "pkg.verify not implemented",
        }

    if not isinstance(version, str) and version is not None:
        version = str(version)

    kwargs["allow_updates"] = allow_updates

    result = _find_install_targets(
        name,
        version,
        pkgs,
        sources,
        fromrepo=fromrepo,
        skip_suggestions=skip_suggestions,
        pkg_verify=pkg_verify,
        normalize=normalize,
        ignore_epoch=ignore_epoch,
        reinstall=reinstall,
        refresh=refresh,
        **kwargs,
    )

    try:
        (
            desired,
            targets,
            to_unpurge,
            to_reinstall,
            altered_files,
            warnings,
            was_refreshed,
        ) = result
        if was_refreshed:
            refresh = False
    except ValueError:
        # _find_install_targets() found no targets or encountered an error

        # check that the hold function is available
        if "pkg.hold" in __salt__ and "hold" in kwargs:
            try:
                action = "pkg.hold" if kwargs["hold"] else "pkg.unhold"
                hold_ret = __salt__[action](name=name, pkgs=pkgs, sources=sources)
            except (CommandExecutionError, SaltInvocationError) as exc:
                return {
                    "name": name,
                    "changes": {},
                    "result": False,
                    "comment": str(exc),
                }

            if "result" in hold_ret and not hold_ret["result"]:
                return {
                    "name": name,
                    "changes": {},
                    "result": False,
                    "comment": (
                        "An error was encountered while "
                        "holding/unholding package(s): {}".format(hold_ret["comment"])
                    ),
                }
            else:
                modified_hold = [
                    hold_ret[x] for x in hold_ret if hold_ret[x]["changes"]
                ]
                not_modified_hold = [
                    hold_ret[x]
                    for x in hold_ret
                    if not hold_ret[x]["changes"] and hold_ret[x]["result"]
                ]
                failed_hold = [
                    hold_ret[x] for x in hold_ret if not hold_ret[x]["result"]
                ]

                for i in modified_hold:
                    result["comment"] += ".\n{}".format(i["comment"])
                    result["result"] = i["result"]
                    result["changes"][i["name"]] = i["changes"]

                for i in not_modified_hold:
                    result["comment"] += ".\n{}".format(i["comment"])
                    result["result"] = i["result"]

                for i in failed_hold:
                    result["comment"] += ".\n{}".format(i["comment"])
                    result["result"] = i["result"]
        return result

    if to_unpurge and "lowpkg.unpurge" not in __salt__:
        ret = {
            "name": name,
            "changes": {},
            "result": False,
            "comment": "lowpkg.unpurge not implemented",
        }
        if warnings:
            ret.setdefault("warnings", []).extend(warnings)
        return ret

    # Remove any targets not returned by _find_install_targets
    if pkgs:
        pkgs = [dict([(x, y)]) for x, y in targets.items()]
        pkgs.extend([dict([(x, y)]) for x, y in to_reinstall.items()])
    elif sources:
        oldsources = sources
        sources = [x for x in oldsources if next(iter(list(x.keys()))) in targets]
        sources.extend(
            [x for x in oldsources if next(iter(list(x.keys()))) in to_reinstall]
        )

    comment = []
    changes = {}
    if __opts__["test"]:
        if targets:
            if sources:
                installable_versions = {
                    x: {"new": "installed", "old": ""} for x in targets
                }
            else:
                installable_versions = _get_installable_versions(targets)
            changes.update(installable_versions)
            summary = ", ".join(targets)
            comment.append(
                f"The following packages would be installed/updated: {summary}"
            )
        if to_unpurge:
            comment.append(
                "The following packages would have their selection status "
                "changed from 'purge' to 'install': {}".format(", ".join(to_unpurge))
            )
            changes.update({x: {"new": "installed", "old": ""} for x in to_unpurge})
        if to_reinstall:
            # Add a comment for each package in to_reinstall with its
            # pkg.verify output
            if reinstall:
                reinstall_targets = []
                for reinstall_pkg in to_reinstall:
                    if sources:
                        reinstall_targets.append(reinstall_pkg)
                    else:
                        reinstall_targets.append(
                            _get_desired_pkg(reinstall_pkg, to_reinstall)
                        )
                    changes.update(
                        {x: {"new": "installed", "old": ""} for x in reinstall_targets}
                    )
                msg = "The following packages would be reinstalled: "
                msg += ", ".join(reinstall_targets)
                comment.append(msg)
            else:
                for reinstall_pkg in to_reinstall:
                    if sources:
                        pkgstr = reinstall_pkg
                    else:
                        pkgstr = _get_desired_pkg(reinstall_pkg, to_reinstall)
                    comment.append(
                        "Package '{}' would be reinstalled because the "
                        "following files have been altered:".format(pkgstr)
                    )
                    changes.update({reinstall_pkg: {}})
                    comment.append(_nested_output(altered_files[reinstall_pkg]))
        ret = {
            "name": name,
            "changes": changes,
            "result": None,
            "comment": "\n".join(comment),
        }
        if warnings:
            ret.setdefault("warnings", []).extend(warnings)
        return ret

    modified_hold = None
    not_modified_hold = None
    failed_hold = None
    if targets or to_reinstall:
        try:
            pkg_ret = __salt__["pkg.install"](
                name=None,
                refresh=refresh,
                version=version,
                fromrepo=fromrepo,
                skip_verify=skip_verify,
                pkgs=pkgs,
                sources=sources,
                reinstall=bool(to_reinstall),
                normalize=normalize,
                update_holds=update_holds,
                ignore_epoch=ignore_epoch,
                split_arch=False,
                **kwargs,
            )
        except CommandExecutionError as exc:
            ret = {"name": name, "result": False}
            if exc.info:
                # Get information for state return from the exception.
                ret["changes"] = exc.info.get("changes", {})
                ret["comment"] = exc.strerror_without_changes
            else:
                ret["changes"] = {}
                ret["comment"] = (
                    "An error was encountered while installing package(s): {}".format(
                        exc
                    )
                )
            if warnings:
                ret.setdefault("warnings", []).extend(warnings)
            return ret

        if refresh:
            refresh = False

        if isinstance(pkg_ret, dict):
            changes.update(pkg_ret)
        elif isinstance(pkg_ret, str):
            comment.append(pkg_ret)
            # Code below will be looking for a dictionary. If this is a string
            # it means that there was an exception raised and that no packages
            # changed, so now that we have added this error to the comments we
            # set this to an empty dictionary so that the code below which
            # checks reinstall targets works.
            pkg_ret = {}

    if "pkg.hold" in __salt__ and "hold" in kwargs:
        try:
            action = "pkg.hold" if kwargs["hold"] else "pkg.unhold"
            hold_ret = __salt__[action](name=name, pkgs=desired)
        except (CommandExecutionError, SaltInvocationError) as exc:
            comment.append(str(exc))
            ret = {
                "name": name,
                "changes": changes,
                "result": False,
                "comment": "\n".join(comment),
            }
            if warnings:
                ret.setdefault("warnings", []).extend(warnings)
            return ret
        else:
            if "result" in hold_ret and not hold_ret["result"]:
                ret = {
                    "name": name,
                    "changes": {},
                    "result": False,
                    "comment": (
                        "An error was encountered while "
                        "holding/unholding package(s): {}".format(hold_ret["comment"])
                    ),
                }
                if warnings:
                    ret.setdefault("warnings", []).extend(warnings)
                return ret
            else:
                modified_hold = [
                    hold_ret[x] for x in hold_ret if hold_ret[x]["changes"]
                ]
                not_modified_hold = [
                    hold_ret[x]
                    for x in hold_ret
                    if not hold_ret[x]["changes"] and hold_ret[x]["result"]
                ]
                failed_hold = [
                    hold_ret[x] for x in hold_ret if not hold_ret[x]["result"]
                ]

    if to_unpurge:
        changes["purge_desired"] = __salt__["lowpkg.unpurge"](*to_unpurge)

    # Analyze pkg.install results for packages in targets
    if sources:
        modified = [x for x in changes if x in targets]
        not_modified = [
            x for x in desired if x not in targets and x not in to_reinstall
        ]
        failed = [x for x in targets if x not in modified]
    else:
        if __grains__["os"] == "FreeBSD":
            kwargs["with_origin"] = True
        new_pkgs = __salt__["pkg.list_pkgs"](versions_as_list=True, **kwargs)
        if (
            kwargs.get("resolve_capabilities", False)
            and "pkg.list_provides" in __salt__
        ):
            new_caps = __salt__["pkg.list_provides"](**kwargs)
        else:
            new_caps = {}

        _ok, failed = _verify_install(
            desired, new_pkgs, ignore_epoch=ignore_epoch, new_caps=new_caps
        )
        modified = [x for x in _ok if x in targets]
        not_modified = [x for x in _ok if x not in targets and x not in to_reinstall]
        failed = [x for x in failed if x in targets]

    # When installing packages that use the task scheduler, we can only know
    # that the task was started, not that it installed successfully. This is
    # especially the case when upgrading the Salt minion on Windows as the
    # installer kills and unregisters the Salt minion service. We will only know
    # that the installation was successful if the minion comes back up. So, we
    # just want to report success in that scenario
    for item in failed:
        if item in changes and isinstance(changes[item], dict):
            if changes[item].get("install status", "") == "task started":
                modified.append(item)
                failed.remove(item)

    if modified:
        if sources:
            summary = ", ".join(modified)
        else:
            summary = ", ".join([_get_desired_pkg(x, desired) for x in modified])
        if len(summary) < 20:
            comment.append(f"The following packages were installed/updated: {summary}")
        else:
            comment.append(
                "{} targeted package{} {} installed/updated.".format(
                    len(modified),
                    "s" if len(modified) > 1 else "",
                    "were" if len(modified) > 1 else "was",
                )
            )

    if modified_hold:
        for i in modified_hold:
            change_name = i["name"]
            if change_name in changes:
                comment.append(i["comment"])
                if len(changes[change_name]["new"]) > 0:
                    changes[change_name]["new"] += "\n"
                changes[change_name]["new"] += "{}".format(i["changes"]["new"])
                if len(changes[change_name]["old"]) > 0:
                    changes[change_name]["old"] += "\n"
                changes[change_name]["old"] += "{}".format(i["changes"]["old"])
            else:
                comment.append(i["comment"])
                changes[change_name] = {}
                changes[change_name]["new"] = "{}".format(i["changes"]["new"])

    # Any requested packages that were not targeted for install or reinstall
    if not_modified:
        if sources:
            summary = ", ".join(not_modified)
        else:
            summary = ", ".join([_get_desired_pkg(x, desired) for x in not_modified])
        if len(not_modified) <= 20:
            comment.append(f"The following packages were already installed: {summary}")
        else:
            comment.append(
                "{} targeted package{} {} already installed".format(
                    len(not_modified),
                    "s" if len(not_modified) > 1 else "",
                    "were" if len(not_modified) > 1 else "was",
                )
            )

    if not_modified_hold:
        for i in not_modified_hold:
            comment.append(i["comment"])

    result = True

    if failed:
        if sources:
            summary = ", ".join(failed)
        else:
            summary = ", ".join([_get_desired_pkg(x, desired) for x in failed])
        comment.insert(0, f"The following packages failed to install/update: {summary}")
        result = False

    if failed_hold:
        for i in failed_hold:
            comment.append(i["comment"])
        result = False

    # Get the ignore_types list if any from the pkg_verify argument
    if isinstance(pkg_verify, list) and any(
        x.get("ignore_types") is not None
        for x in pkg_verify
        if isinstance(x, _OrderedDict) and "ignore_types" in x
    ):
        ignore_types = next(
            x.get("ignore_types") for x in pkg_verify if "ignore_types" in x
        )
    else:
        ignore_types = []

    # Get the verify_options list if any from the pkg_verify argument
    if isinstance(pkg_verify, list) and any(
        x.get("verify_options") is not None
        for x in pkg_verify
        if isinstance(x, _OrderedDict) and "verify_options" in x
    ):
        verify_options = next(
            x.get("verify_options") for x in pkg_verify if "verify_options" in x
        )
    else:
        verify_options = []

    # Rerun pkg.verify for packages in to_reinstall to determine failed
    modified = []
    failed = []
    for reinstall_pkg in to_reinstall:
        if reinstall:
            if reinstall_pkg in pkg_ret:
                modified.append(reinstall_pkg)
            else:
                failed.append(reinstall_pkg)
        elif pkg_verify:
            # No need to wrap this in a try/except because we would already
            # have caught invalid arguments earlier.
            verify_result = __salt__["pkg.verify"](
                reinstall_pkg,
                ignore_types=ignore_types,
                verify_options=verify_options,
                **kwargs,
            )
            if verify_result:
                failed.append(reinstall_pkg)
                altered_files[reinstall_pkg] = verify_result
            else:
                modified.append(reinstall_pkg)

    if modified:
        # Add a comment for each package in modified with its pkg.verify output
        for modified_pkg in modified:
            if sources:
                pkgstr = modified_pkg
            else:
                pkgstr = _get_desired_pkg(modified_pkg, desired)
            msg = f"Package {pkgstr} was reinstalled."
            if modified_pkg in altered_files:
                msg += " The following files were remediated:"
                comment.append(msg)
                comment.append(_nested_output(altered_files[modified_pkg]))
            else:
                comment.append(msg)

    if failed:
        # Add a comment for each package in failed with its pkg.verify output
        for failed_pkg in failed:
            if sources:
                pkgstr = failed_pkg
            else:
                pkgstr = _get_desired_pkg(failed_pkg, desired)
            msg = f"Reinstall was not successful for package {pkgstr}."
            if failed_pkg in altered_files:
                msg += " The following files could not be remediated:"
                comment.append(msg)
                comment.append(_nested_output(altered_files[failed_pkg]))
            else:
                comment.append(msg)
        result = False

    ret = {
        "name": name,
        "changes": changes,
        "result": result,
        "comment": "\n".join(comment),
    }
    if warnings:
        ret.setdefault("warnings", []).extend(warnings)
    return ret


def downloaded(
    name, version=None, pkgs=None, fromrepo=None, ignore_epoch=None, **kwargs
):
    """
    .. versionadded:: 2017.7.0

    Ensure that the package is downloaded, and that it is the correct version
    (if specified).

    .. note::
        Any argument which is either a) not explicitly defined for this state,
        or b) not a global state argument like ``saltenv``, or
        ``reload_modules``, will be passed through to the call to
        ``pkg.install`` to download the package(s). For example, you can include
        a ``disablerepo`` argument on platforms that use yum/dnf to disable
        that repo:

        .. code-block:: yaml

            mypkg:
              pkg.downloaded:
                - disablerepo: base,updates

        To see what is supported, check :ref:`this page <virtual-pkg>` to find
        the documentation for your platform's ``pkg`` module, then look at the
        documentation for the ``install`` function.

        Any argument that is passed through to the ``install`` function, which
        is not defined for that function, will be silently ignored.

    Currently supported for the following pkg providers:
    :mod:`yum <salt.modules.yumpkg>`, :mod:`zypper <salt.modules.zypperpkg>` and :mod:`apt <salt.modules.aptpkg>`

    :param str name:
        The name of the package to be downloaded. This parameter is ignored if
        either "pkgs" is used. Additionally, please note that this option can
        only be used to download packages from a software repository.

    :param str version:
        Download a specific version of a package.

        .. important::
            As of version 2015.8.7, for distros which use yum/dnf, packages
            which have a version with a nonzero epoch (that is, versions which
            start with a number followed by a colon must have the epoch included
            when specifying the version number. For example:

            .. code-block:: yaml

                vim-enhanced:
                  pkg.downloaded:
                    - version: 2:7.4.160-1.el7

            An **ignore_epoch** argument has been added to which causes the
            epoch to be disregarded when the state checks to see if the desired
            version was installed.

            You can install a specific version when using the ``pkgs`` argument by
            including the version after the package:

            .. code-block:: yaml

                common_packages:
                  pkg.downloaded:
                    - pkgs:
                      - unzip
                      - dos2unix
                      - salt-minion: 2015.8.5-1.el6

    :param bool resolve_capabilities:
        Turn on resolving capabilities. This allow one to name "provides" or alias names for packages.

        .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: yaml

        zsh:
          pkg.downloaded:
            - version: 5.0.5-4.63
            - fromrepo: "myrepository"
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if "pkg.list_downloaded" not in __salt__:
        ret["result"] = False
        ret["comment"] = "The pkg.downloaded state is not available on this platform"
        return ret

    if isinstance(pkgs, list) and len(pkgs) == 0:
        ret["result"] = True
        ret["comment"] = "No packages to download provided"
        return ret

    # If just a name (and optionally a version) is passed, just pack them into
    # the pkgs argument.
    if name and not pkgs:
        if version:
            pkgs = [{name: version}]
            version = None
        else:
            pkgs = [name]

    # It doesn't make sense here to received 'downloadonly' as kwargs
    # as we're explicitly passing 'downloadonly=True' to execution module.
    if "downloadonly" in kwargs:
        del kwargs["downloadonly"]

    pkgs, _refresh = _resolve_capabilities(pkgs, **kwargs)

    # Only downloading not yet downloaded packages
    targets = _find_download_targets(
        name, version, pkgs, fromrepo=fromrepo, ignore_epoch=ignore_epoch, **kwargs
    )
    if isinstance(targets, dict) and "result" in targets:
        return targets
    elif not isinstance(targets, dict):
        ret["result"] = False
        ret["comment"] = "An error was encountered while checking targets: {}".format(
            targets
        )
        return ret

    if __opts__["test"]:
        summary = ", ".join(targets)
        ret["comment"] = "The following packages would be downloaded: {}".format(
            summary
        )
        return ret

    try:
        pkg_ret = __salt__["pkg.install"](
            name=name,
            pkgs=pkgs,
            version=version,
            downloadonly=True,
            fromrepo=fromrepo,
            ignore_epoch=ignore_epoch,
            **kwargs,
        )
        ret["result"] = True
        ret["changes"].update(pkg_ret)
    except CommandExecutionError as exc:
        ret = {"name": name, "result": False}
        if exc.info:
            # Get information for state return from the exception.
            ret["changes"] = exc.info.get("changes", {})
            ret["comment"] = exc.strerror_without_changes
        else:
            ret["changes"] = {}
            ret["comment"] = (
                f"An error was encountered while downloading package(s): {exc}"
            )
        return ret

    new_pkgs = __salt__["pkg.list_downloaded"](**kwargs)
    _ok, failed = _verify_install(targets, new_pkgs, ignore_epoch=ignore_epoch)

    if failed:
        summary = ", ".join([_get_desired_pkg(x, targets) for x in failed])
        ret["result"] = False
        ret["comment"] = f"The following packages failed to download: {summary}"

    if not ret["changes"] and not ret["comment"]:
        ret["result"] = True
        ret["comment"] = "Packages downloaded: {}".format(", ".join(targets))

    return ret


def patch_installed(name, advisory_ids=None, downloadonly=None, **kwargs):
    """
    .. versionadded:: 2017.7.0

    Ensure that packages related to certain advisory ids are installed.

    .. note::
        Any argument which is either a) not explicitly defined for this state,
        or b) not a global state argument like ``saltenv``, or
        ``reload_modules``, will be passed through to the call to
        ``pkg.install`` to install the patch(es).

        To see what is supported, check :ref:`this page <virtual-pkg>` to find
        the documentation for your platform's ``pkg`` module, then look at the
        documentation for the ``install`` function.

        Any argument that is passed through to the ``install`` function, which
        is not defined for that function, will be silently ignored.

    Currently supported for the following pkg providers:
    :mod:`yum <salt.modules.yumpkg>` and :mod:`zypper <salt.modules.zypperpkg>`

    CLI Example:

    .. code-block:: yaml

        issue-foo-fixed:
          pkg.patch_installed:
            - advisory_ids:
              - SUSE-SLE-SERVER-12-SP2-2017-185
              - SUSE-SLE-SERVER-12-SP2-2017-150
              - SUSE-SLE-SERVER-12-SP2-2017-120
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if "pkg.list_patches" not in __salt__:
        ret["result"] = False
        ret["comment"] = (
            "The pkg.patch_installed state is not available on this platform"
        )
        return ret

    if isinstance(advisory_ids, list) and len(advisory_ids) == 0:
        ret["result"] = True
        ret["comment"] = "No advisory ids provided"
        return ret

    # Only downloading not yet downloaded packages
    targets = _find_advisory_targets(name, advisory_ids, **kwargs)
    if isinstance(targets, dict) and "result" in targets:
        return targets
    elif not isinstance(targets, list):
        ret["result"] = False
        ret["comment"] = "An error was encountered while checking targets: {}".format(
            targets
        )
        return ret

    if __opts__["test"]:
        summary = ", ".join(targets)
        ret["comment"] = (
            f"The following advisory patches would be downloaded: {summary}"
        )
        return ret

    try:
        pkg_ret = __salt__["pkg.install"](
            name=name, advisory_ids=advisory_ids, downloadonly=downloadonly, **kwargs
        )
        ret["result"] = True
        ret["changes"].update(pkg_ret)
    except CommandExecutionError as exc:
        ret = {"name": name, "result": False}
        if exc.info:
            # Get information for state return from the exception.
            ret["changes"] = exc.info.get("changes", {})
            ret["comment"] = exc.strerror_without_changes
        else:
            ret["changes"] = {}
            ret["comment"] = (
                f"An error was encountered while downloading package(s): {exc}"
            )
        return ret

    if not ret["changes"] and not ret["comment"]:
        status = "downloaded" if downloadonly else "installed"
        ret["result"] = True
        ret["comment"] = (
            "Advisory patch is not needed or related packages are already {}".format(
                status
            )
        )

    return ret


def patch_downloaded(name, advisory_ids=None, **kwargs):
    """
    .. versionadded:: 2017.7.0

    Ensure that packages related to certain advisory ids are downloaded.

    Currently supported for the following pkg providers:
    :mod:`yum <salt.modules.yumpkg>` and :mod:`zypper <salt.modules.zypperpkg>`

    CLI Example:

    .. code-block:: yaml

        preparing-to-fix-issues:
          pkg.patch_downloaded:
            - advisory_ids:
              - SUSE-SLE-SERVER-12-SP2-2017-185
              - SUSE-SLE-SERVER-12-SP2-2017-150
              - SUSE-SLE-SERVER-12-SP2-2017-120
    """
    if "pkg.list_patches" not in __salt__:
        return {
            "name": name,
            "result": False,
            "changes": {},
            "comment": (
                "The pkg.patch_downloaded state is not available on this platform"
            ),
        }

    # It doesn't make sense here to received 'downloadonly' as kwargs
    # as we're explicitly passing 'downloadonly=True' to execution module.
    if "downloadonly" in kwargs:
        del kwargs["downloadonly"]
    return patch_installed(
        name=name, advisory_ids=advisory_ids, downloadonly=True, **kwargs
    )


def latest(
    name,
    refresh=None,
    fromrepo=None,
    skip_verify=False,
    pkgs=None,
    watch_flags=True,
    **kwargs,
):
    """
    .. versionchanged:: 3007.0

    Ensure that the named package is installed and the latest available
    package. If the package can be updated, this state function will update
    the package. Generally it is better for the
    :mod:`installed <salt.states.pkg.installed>` function to be
    used, as :mod:`latest <salt.states.pkg.latest>` will update the package
    whenever a new package is available.

    .. note::
        Any argument which is either a) not explicitly defined for this state,
        or b) not a global state argument like ``saltenv``, or
        ``reload_modules``, will be passed through to the call to
        ``pkg.install`` to install the package(s). For example, you can include
        a ``disablerepo`` argument on platforms that use yum/dnf to disable
        that repo:

        .. code-block:: yaml

            mypkg:
              pkg.latest:
                - disablerepo: base,updates

        To see what is supported, check :ref:`this page <virtual-pkg>` to find
        the documentation for your platform's ``pkg`` module, then look at the
        documentation for the ``install`` function.

        Any argument that is passed through to the ``install`` function, which
        is not defined for that function, will be silently ignored.

    name
        The name of the package to maintain at the latest available version.
        This parameter is ignored if "pkgs" is used.

    fromrepo
        Specify a repository from which to install

    skip_verify
        Skip the GPG verification check for the package to be installed

    refresh
        This parameter controls whether or not the package repo database is
        updated prior to checking for the latest available version of the
        requested packages.

        If ``True``, the package database will be refreshed (``apt-get update``
        or equivalent, depending on platform) before checking for the latest
        available version of the requested packages.

        If ``False``, the package database will *not* be refreshed before
        checking.

        If unset, then Salt treats package database refreshes differently
        depending on whether or not a ``pkg`` state has been executed already
        during the current Salt run. Once a refresh has been performed in a
        ``pkg`` state, for the remainder of that Salt run no other refreshes
        will be performed for ``pkg`` states which do not explicitly set
        ``refresh`` to ``True``. This prevents needless additional refreshes
        from slowing down the Salt run.

    :param str cache_valid_time:

        .. versionadded:: 2016.11.0

        This parameter sets the value in seconds after which the cache is
        marked as invalid, and a cache update is necessary. This overwrites
        the ``refresh`` parameter's default behavior.

        Example:

        .. code-block:: yaml

            httpd:
              pkg.latest:
                - refresh: True
                - cache_valid_time: 300

        In this case, a refresh will not take place for 5 minutes since the last
        ``apt-get update`` was executed on the system.

        .. note::

            This parameter is available only on Debian based distributions and
            has no effect on the rest.

    :param bool resolve_capabilities:
        Turn on resolving capabilities. This allow one to name "provides" or alias names for packages.

        .. versionadded:: 2018.3.0

    Multiple Package Installation Options:

    (Not yet supported for: FreeBSD, OpenBSD, MacOS, and Solaris pkgutil)

    pkgs
        A list of packages to maintain at the latest available version.

    .. code-block:: yaml

        mypkgs:
          pkg.latest:
            - pkgs:
              - foo
              - bar
              - baz

    install_recommends
        Whether to install the packages marked as recommended. Default is
        ``True``. Currently only works with APT-based systems.

        .. versionadded:: 2015.5.0

    .. code-block:: yaml

        httpd:
          pkg.latest:
            - install_recommends: False

    only_upgrade
        Only upgrade the packages, if they are already installed. Default is
        ``False``. Currently only works with APT-based systems.

        .. versionadded:: 2015.5.0

    .. code-block:: yaml

        httpd:
          pkg.latest:
            - only_upgrade: True

    .. note::
        If this parameter is set to True and the package is not already
        installed, the state will fail.

    report_reboot_exit_codes
        If the installer exits with a recognized exit code indicating that
        a reboot is required, the module function

           *win_system.set_reboot_required_witnessed*

        will be called, preserving the knowledge of this event
        for the remainder of the current boot session. For the time being,
        ``3010`` is the only recognized exit code, but this
        is subject to future refinement. The value of this param
        defaults to ``True``. This parameter has no effect on
        non-Windows systems.

        .. versionadded:: 2016.11.0

        .. code-block:: yaml

           ms vcpp installed:
             pkg.latest:
               - name: ms-vcpp
               - report_reboot_exit_codes: False
    """
    refresh = salt.utils.pkg.check_refresh(__opts__, refresh)

    if kwargs.get("sources"):
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": 'The "sources" parameter is not supported.',
        }
    elif pkgs:
        desired_pkgs = list(_repack_pkgs(pkgs).keys())  # pylint: disable=not-callable
        if not desired_pkgs:
            # Badly-formatted SLS
            return {
                "name": name,
                "changes": {},
                "result": False,
                "comment": 'Invalidly formatted "pkgs" parameter. See minion log.',
            }
    else:
        if isinstance(pkgs, list) and len(pkgs) == 0:
            return {
                "name": name,
                "changes": {},
                "result": True,
                "comment": "No packages to install provided",
            }
        else:
            desired_pkgs = [name]

    kwargs["saltenv"] = __env__

    # check if capabilities should be checked and modify the requested packages
    # accordingly.
    desired_pkgs, refresh = _resolve_capabilities(
        desired_pkgs, refresh=refresh, **kwargs
    )

    try:
        avail = __salt__["pkg.latest_version"](
            *desired_pkgs, fromrepo=fromrepo, refresh=refresh, **kwargs
        )
    except CommandExecutionError as exc:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": (
                "An error was encountered while checking the "
                "newest available version of package(s): {}".format(exc)
            ),
        }

    try:
        cur = __salt__["pkg.version"](*desired_pkgs, **kwargs)
    except CommandExecutionError as exc:
        return {"name": name, "changes": {}, "result": False, "comment": exc.strerror}

    # Repack the cur/avail data if only a single package is being checked
    if isinstance(cur, str):
        cur = {desired_pkgs[0]: cur}
    if isinstance(avail, str):
        avail = {desired_pkgs[0]: avail}

    targets = {}
    problems = []
    for pkg in desired_pkgs:
        if not avail.get(pkg):
            # Package either a) is up-to-date, or b) does not exist
            if not cur.get(pkg):
                # Package does not exist
                msg = f"No information found for '{pkg}'."
                log.error(msg)
                problems.append(msg)
            elif (
                watch_flags
                and __grains__.get("os") == "Gentoo"
                and __salt__["portage_config.is_changed_uses"](pkg)
            ):
                # Package is up-to-date, but Gentoo USE flags are changing so
                # we need to add it to the targets
                targets[pkg] = cur[pkg]
        else:
            # Package either a) is not installed, or b) is installed and has an
            # upgrade available
            targets[pkg] = avail[pkg]

    if problems:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": " ".join(problems),
        }

    if targets:
        # Find up-to-date packages
        if not pkgs:
            # There couldn't have been any up-to-date packages if this state
            # only targeted a single package and is being allowed to proceed to
            # the install step.
            up_to_date = []
        else:
            up_to_date = [x for x in pkgs if x not in targets]

        if __opts__["test"]:
            comments = []
            comments.append(
                "The following packages would be installed/upgraded: "
                + ", ".join(sorted(targets))
            )
            if up_to_date:
                up_to_date_count = len(up_to_date)
                if up_to_date_count <= 10:
                    comments.append(
                        "The following packages are already up-to-date: "
                        + ", ".join([f"{x} ({cur[x]})" for x in sorted(up_to_date)])
                    )
                else:
                    comments.append(
                        f"{up_to_date_count} packages are already up-to-date"
                    )
            changes = _get_installable_versions(targets, cur)
            return {
                "name": name,
                "changes": changes,
                "result": None,
                "comment": "\n".join(comments),
            }

        if salt.utils.platform.is_windows():
            # pkg.install execution module on windows ensures the software
            # package is installed when no version is specified, it does not
            # upgrade the software to the latest. This is per the design.
            # Build updated list of pkgs *with verion number*, exclude
            # non-targeted ones
            targeted_pkgs = [{x: targets[x]} for x in targets]
        else:
            # Build updated list of pkgs to exclude non-targeted ones
            targeted_pkgs = list(targets)

        # No need to refresh, if a refresh was necessary it would have been
        # performed above when pkg.latest_version was run.
        try:
            changes = __salt__["pkg.install"](
                name=None,
                refresh=False,
                fromrepo=fromrepo,
                skip_verify=skip_verify,
                pkgs=targeted_pkgs,
                **kwargs,
            )
        except CommandExecutionError as exc:
            return {
                "name": name,
                "changes": {},
                "result": False,
                "comment": (
                    "An error was encountered while installing package(s): {}".format(
                        exc
                    )
                ),
            }

        if changes:
            # Find failed and successful updates
            failed = [
                x
                for x in targets
                if not changes.get(x)
                or changes[x].get("new") is not None
                and targets[x] not in changes[x].get("new").split(",")
                and targets[x] != "latest"
            ]
            successful = [x for x in targets if x not in failed]

            comments = []
            if failed:
                msg = "The following packages failed to update: {}".format(
                    ", ".join(sorted(failed))
                )
                comments.append(msg)
            if successful:
                msg = (
                    "The following packages were successfully "
                    "installed/upgraded: "
                    "{}".format(", ".join(sorted(successful)))
                )
                comments.append(msg)
            if up_to_date:
                if len(up_to_date) <= 10:
                    msg = "The following packages were already up-to-date: {}".format(
                        ", ".join(sorted(up_to_date))
                    )
                else:
                    msg = f"{len(up_to_date)} packages were already up-to-date "
                comments.append(msg)

            return {
                "name": name,
                "changes": changes,
                "result": False if failed else True,
                "comment": " ".join(comments),
            }
        else:
            if len(targets) > 10:
                comment = (
                    "{} targeted packages failed to update. "
                    "See debug log for details.".format(len(targets))
                )
            elif len(targets) > 1:
                comment = (
                    "The following targeted packages failed to update. "
                    "See debug log for details: ({}).".format(
                        ", ".join(sorted(targets))
                    )
                )
            else:
                comment = "Package {} failed to update.".format(
                    next(iter(list(targets.keys())))
                )
            if up_to_date:
                if len(up_to_date) <= 10:
                    comment += (
                        " The following packages were already up-to-date: {}".format(
                            ", ".join(sorted(up_to_date))
                        )
                    )
                else:
                    comment += "{} packages were already up-to-date".format(
                        len(up_to_date)
                    )

            return {
                "name": name,
                "changes": changes,
                "result": False,
                "comment": comment,
            }
    else:
        if len(desired_pkgs) > 10:
            comment = f"All {len(desired_pkgs)} packages are up-to-date."
        elif len(desired_pkgs) > 1:
            comment = "All packages are up-to-date ({}).".format(
                ", ".join(sorted(desired_pkgs))
            )
        else:
            comment = f"Package {desired_pkgs[0]} is already up-to-date"

        return {"name": name, "changes": {}, "result": True, "comment": comment}


def _uninstall(
    action="remove",
    name=None,
    version=None,
    pkgs=None,
    normalize=True,
    ignore_epoch=None,
    **kwargs,
):
    """
    Common function for package removal
    """
    if action not in ("remove", "purge"):
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": f"Invalid action '{action}'. This is probably a bug.",
        }

    try:
        pkg_params = __salt__["pkg_resource.parse_targets"](
            name, pkgs, normalize=normalize
        )[0]
    except MinionError as exc:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": f"An error was encountered while parsing targets: {exc}",
        }
    targets = _find_remove_targets(
        name, version, pkgs, normalize, ignore_epoch=ignore_epoch, **kwargs
    )
    if isinstance(targets, dict) and "result" in targets:
        if action == "purge":
            # found nothing, reset state return obj to empty list and check for removed to be purged
            targets = []
        else:
            return targets
    elif not isinstance(targets, list):
        if action == "purge":
            # found nothing, reset state return obj to empty list and check for removed to be purged
            targets = []
        else:
            return {
                "name": name,
                "changes": {},
                "result": False,
                "comment": "An error was encountered while checking targets: {}".format(
                    targets
                ),
            }
    if action == "purge":
        old_removed = __salt__["pkg.list_pkgs"](
            versions_as_list=True, removed=True, **kwargs
        )
        targets.extend([x for x in pkg_params if x in old_removed])
    targets.sort()

    if not targets:
        return {
            "name": name,
            "changes": {},
            "result": True,
            "comment": "None of the targeted packages are installed{}".format(
                " or partially installed" if action == "purge" else ""
            ),
        }

    if __opts__["test"]:
        _changes = {}
        _changes.update({x: {"new": f"{action}d", "old": ""} for x in targets})

        return {
            "name": name,
            "changes": _changes,
            "result": None,
            "comment": "The following packages will be {}d: {}.".format(
                action, ", ".join(targets)
            ),
        }

    changes = __salt__[f"pkg.{action}"](
        name, pkgs=pkgs, version=version, split_arch=False, **kwargs
    )
    new = __salt__["pkg.list_pkgs"](versions_as_list=True, **kwargs)
    failed = []
    for param in pkg_params:
        if __grains__["os_family"] in ["Suse", "RedHat"]:
            # Check if the package version set to be removed is actually removed:
            if param in new and not pkg_params[param]:
                failed.append(param)
            elif param in new and pkg_params[param] in new[param]:
                failed.append(param + "-" + pkg_params[param])
        elif param in new:
            failed.append(param)

    if action == "purge":
        new_removed = __salt__["pkg.list_pkgs"](
            versions_as_list=True, removed=True, **kwargs
        )
        failed.extend([x for x in pkg_params if x in new_removed])
    failed.sort()

    if failed:
        return {
            "name": name,
            "changes": changes,
            "result": False,
            "comment": "The following packages failed to {}: {}.".format(
                action, ", ".join(failed)
            ),
        }

    comments = []
    not_installed = sorted(x for x in pkg_params if x not in targets)
    if not_installed:
        comments.append(
            "The following packages were not installed: {}".format(
                ", ".join(not_installed)
            )
        )
        comments.append(
            "The following packages were {}d: {}.".format(action, ", ".join(targets))
        )
    else:
        comments.append(f"All targeted packages were {action}d.")

    return {
        "name": name,
        "changes": changes,
        "result": True,
        "comment": " ".join(comments),
    }


def removed(name, version=None, pkgs=None, normalize=True, ignore_epoch=None, **kwargs):
    """
    Verify that a package is not installed, calling ``pkg.remove`` if necessary
    to remove the package.

    name
        The name of the package to be removed.

    version
        The version of the package that should be removed. Don't do anything if
        the package is installed with an unmatching version.

        .. important::
            As of version 2015.8.7, for distros which use yum/dnf, packages
            which have a version with a nonzero epoch (that is, versions which
            start with a number followed by a colon like in the example above)
            must have the epoch included when specifying the version number.
            For example:

            .. code-block:: yaml

                vim-enhanced:
                  pkg.removed:
                    - version: 2:7.4.160-1.el7

            In version 2015.8.9, an **ignore_epoch** argument has been added to
            :py:mod:`pkg.installed <salt.states.pkg.installed>`,
            :py:mod:`pkg.removed <salt.states.pkg.removed>`, and
            :py:mod:`pkg.purged <salt.states.pkg.purged>` states, which
            causes the epoch to be disregarded when the state checks to see if
            the desired version was installed. If **ignore_epoch** was not set
            to ``True``, and instead of ``2:7.4.160-1.el7`` a version of
            ``7.4.160-1.el7`` were used, this state would report success since
            the actual installed version includes the epoch, and the specified
            version would not match.

    normalize : True
        Normalize the package name by removing the architecture, if the
        architecture of the package is different from the architecture of the
        operating system. The ability to disable this behavior is useful for
        poorly-created packages which include the architecture as an actual
        part of the name, such as kernel modules which match a specific kernel
        version.

        .. versionadded:: 2015.8.0

    ignore_epoch : None
        If this option is not explicitly set, and there is no epoch in the
        desired package version, the epoch will be implicitly ignored. Set this
        argument to ``True`` to explicitly ignore the epoch, and ``False`` to
        strictly enforce it.

        .. versionadded:: 2015.8.9

        .. versionchanged:: 3001
            In prior releases, the default behavior was to strictly enforce
            epochs unless this argument was set to ``True``.

    Multiple Package Options:

    pkgs
        A list of packages to remove. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed. It accepts
        version numbers as well.

        .. versionadded:: 0.16.0
    """
    kwargs["saltenv"] = __env__
    try:
        return _uninstall(
            action="remove",
            name=name,
            version=version,
            pkgs=pkgs,
            normalize=normalize,
            ignore_epoch=ignore_epoch,
            **kwargs,
        )
    except CommandExecutionError as exc:
        ret = {"name": name, "result": False}
        if exc.info:
            # Get information for state return from the exception.
            ret["changes"] = exc.info.get("changes", {})
            ret["comment"] = exc.strerror_without_changes
        else:
            ret["changes"] = {}
            ret["comment"] = (
                f"An error was encountered while removing package(s): {exc}"
            )
        return ret


def purged(name, version=None, pkgs=None, normalize=True, ignore_epoch=None, **kwargs):
    """
    Verify that a package is not installed, calling ``pkg.purge`` if necessary
    to purge the package. All configuration files are also removed.

    name
        The name of the package to be purged.

    version
        The version of the package that should be removed. Don't do anything if
        the package is installed with an unmatching version.

        .. important::
            As of version 2015.8.7, for distros which use yum/dnf, packages
            which have a version with a nonzero epoch (that is, versions which
            start with a number followed by a colon like in the example above)
            must have the epoch included when specifying the version number.
            For example:

            .. code-block:: yaml

                vim-enhanced:
                  pkg.purged:
                    - version: 2:7.4.160-1.el7

            In version 2015.8.9, an **ignore_epoch** argument has been added to
            :py:mod:`pkg.installed <salt.states.pkg.installed>`,
            :py:mod:`pkg.removed <salt.states.pkg.removed>`, and
            :py:mod:`pkg.purged <salt.states.pkg.purged>` states, which
            causes the epoch to be disregarded when the state checks to see if
            the desired version was installed. If **ignore_epoch** was not set
            to ``True``, and instead of ``2:7.4.160-1.el7`` a version of
            ``7.4.160-1.el7`` were used, this state would report success since
            the actual installed version includes the epoch, and the specified
            version would not match.

    normalize : True
        Normalize the package name by removing the architecture, if the
        architecture of the package is different from the architecture of the
        operating system. The ability to disable this behavior is useful for
        poorly-created packages which include the architecture as an actual
        part of the name, such as kernel modules which match a specific kernel
        version.

        .. versionadded:: 2015.8.0

    ignore_epoch : None
        If this option is not explicitly set, and there is no epoch in the
        desired package version, the epoch will be implicitly ignored. Set this
        argument to ``True`` to explicitly ignore the epoch, and ``False`` to
        strictly enforce it.

        .. versionadded:: 2015.8.9

        .. versionchanged:: 3001
            In prior releases, the default behavior was to strictly enforce
            epochs unless this argument was set to ``True``.

    Multiple Package Options:

    pkgs
        A list of packages to purge. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed. It accepts
        version numbers as well.

        .. versionadded:: 0.16.0
    """
    kwargs["saltenv"] = __env__
    try:
        return _uninstall(
            action="purge",
            name=name,
            version=version,
            pkgs=pkgs,
            normalize=normalize,
            ignore_epoch=ignore_epoch,
            **kwargs,
        )
    except CommandExecutionError as exc:
        ret = {"name": name, "result": False}
        if exc.info:
            # Get information for state return from the exception.
            ret["changes"] = exc.info.get("changes", {})
            ret["comment"] = exc.strerror_without_changes
        else:
            ret["changes"] = {}
            ret["comment"] = f"An error was encountered while purging package(s): {exc}"
        return ret


def uptodate(name, refresh=False, pkgs=None, **kwargs):
    """
    .. versionadded:: 2014.7.0
    .. versionchanged:: 2018.3.0

        Added support for the ``pkgin`` provider.

    Verify that the system is completely up to date.

    :param str name
        The name has no functional value and is only used as a tracking
        reference

    :param bool refresh
        refresh the package database before checking for new upgrades

    :param list pkgs
        list of packages to upgrade

    :param bool resolve_capabilities:
        Turn on resolving capabilities. This allow one to name "provides" or alias names for packages.

        .. versionadded:: 2018.3.0

    :param kwargs
        Any keyword arguments to pass through to the ``pkg`` module.

        For example, for apt systems: `dist_upgrade`, `cache_valid_time`, `force_conf_new`

        .. versionadded:: 2015.5.0
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": "Failed to update"}

    if "pkg.list_upgrades" not in __salt__:
        ret["comment"] = "State pkg.uptodate is not available"
        return ret

    # emerge --update doesn't appear to support repo notation
    if "fromrepo" in kwargs and __grains__["os"] == "Gentoo":
        ret["comment"] = "'fromrepo' argument not supported on this platform"
        return ret

    if isinstance(refresh, bool):
        pkgs, refresh = _resolve_capabilities(pkgs, refresh=refresh, **kwargs)
        try:
            packages = __salt__["pkg.list_upgrades"](refresh=refresh, **kwargs)
            expected = {
                pkgname: {
                    "new": pkgver,
                    "old": __salt__["pkg.version"](pkgname, **kwargs),
                }
                for pkgname, pkgver in packages.items()
            }
            if isinstance(pkgs, list):
                packages = [pkg for pkg in packages if pkg in pkgs]
                expected = {
                    pkgname: pkgver
                    for pkgname, pkgver in expected.items()
                    if pkgname in pkgs
                }
        except Exception as exc:  # pylint: disable=broad-except
            ret["comment"] = str(exc)
            return ret
    else:
        ret["comment"] = "refresh must be either True or False"
        return ret

    if not packages:
        ret["comment"] = "System is already up-to-date"
        ret["result"] = True
        return ret
    elif __opts__["test"]:
        ret["comment"] = "System update will be performed"
        ret["changes"] = expected
        ret["result"] = None
        return ret

    try:
        ret["changes"] = __salt__["pkg.upgrade"](refresh=refresh, pkgs=pkgs, **kwargs)
    except CommandExecutionError as exc:
        if exc.info:
            # Get information for state return from the exception.
            ret["changes"] = exc.info.get("changes", {})
            ret["comment"] = exc.strerror_without_changes
        else:
            ret["changes"] = {}
            ret["comment"] = f"An error was encountered while updating packages: {exc}"
        return ret

    # If a package list was provided, ensure those packages were updated
    missing = []
    if isinstance(pkgs, list):
        missing = [pkg for pkg in expected.keys() if pkg not in ret["changes"]]

    if missing:
        ret["comment"] = "The following package(s) failed to update: {}".format(
            ", ".join(missing)
        )
        ret["result"] = False
    else:
        ret["comment"] = "Upgrade ran successfully"
        ret["result"] = True

    return ret


def group_installed(name, skip=None, include=None, **kwargs):
    """
    .. versionadded:: 2015.8.0

    .. versionchanged:: 2016.11.0
        Added support in :mod:`pacman <salt.modules.pacman>`

    .. versionchanged:: 3006.2
        For RPM-based systems, support for ``fromrepo``, ``enablerepo``, and
        ``disablerepo`` (as used in :py:func:`pkg.install
        <salt.modules.yumpkg.install>`) has been added. This allows one to, for
        example, use ``enablerepo`` to perform a group install from a repo that
        is otherwise disabled.

    Ensure that an entire package group is installed. This state is currently
    only supported for the :mod:`yum <salt.modules.yumpkg>` and :mod:`pacman
    <salt.modules.pacman>` package managers.

    skip
        Packages that would normally be installed by the package group
        ("default" packages), which should not be installed.

        .. code-block:: yaml

            Load Balancer:
              pkg.group_installed:
                - skip:
                  - piranha

    include
        Packages which are included in a group, which would not normally be
        installed by a ``yum groupinstall`` ("optional" packages). Note that
        this will not enforce group membership; if you include packages which
        are not members of the specified groups, they will still be installed.

        .. code-block:: yaml

            Load Balancer:
              pkg.group_installed:
                - include:
                  - haproxy

        .. versionchanged:: 2016.3.0
            This option can no longer be passed as a comma-separated list, it
            must now be passed as a list (as shown in the above example).

    .. note::
        The below options are only supported on RPM-based systems

    fromrepo
        Restrict ``yum groupinfo`` to the specified repo(s).
        (e.g., ``yum --disablerepo='*' --enablerepo='somerepo'``)

        .. code-block:: yaml

            MyGroup:
              pkg.group_installed:
                - fromrepo: base,updates

        .. versionadded:: 3006.2

    enablerepo (ignored if ``fromrepo`` is specified)
        Specify a disabled package repository (or repositories) to enable.
        (e.g., ``yum --enablerepo='somerepo'``)

        .. code-block:: yaml

            MyGroup:
              pkg.group_installed:
                - enablerepo: myrepo

        .. versionadded:: 3006.2

    disablerepo (ignored if ``fromrepo`` is specified)
        Specify an enabled package repository (or repositories) to disable.
        (e.g., ``yum --disablerepo='somerepo'``)

        .. code-block:: yaml

            MyGroup:
              pkg.group_installed:
                - disablerepo: epel

        .. versionadded:: 3006.2

    .. note::
        Because this is essentially a wrapper around :py:func:`pkg.install
        <salt.modules.yumpkg.install>`, any argument which can be passed to
        pkg.install may also be included here, and it will be passed on to the
        call to :py:func:`pkg.install <salt.modules.yumpkg.install>`.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if "pkg.group_diff" not in __salt__:
        ret["comment"] = "pkg.group_install not available for this platform"
        return ret

    if skip is None:
        skip = []
    else:
        if not isinstance(skip, list):
            ret["comment"] = "skip must be formatted as a list"
            return ret
        for idx, item in enumerate(skip):
            if not isinstance(item, str):
                skip[idx] = str(item)

    if include is None:
        include = []
    else:
        if not isinstance(include, list):
            ret["comment"] = "include must be formatted as a list"
            return ret
        for idx, item in enumerate(include):
            if not isinstance(item, str):
                include[idx] = str(item)

    try:
        diff = __salt__["pkg.group_diff"](
            name, **salt.utils.args.clean_kwargs(**kwargs)
        )
    except (CommandExecutionError, TypeError) as err:
        if "unexpected keyword argument" in str(err):
            ret["comment"] = "Repo options are not supported on this platform"
        else:
            ret["comment"] = (
                f"An error was encountered while installing/updating group '{name}': {err}."
            )
        return ret

    mandatory = diff["mandatory"]["installed"] + diff["mandatory"]["not installed"]

    invalid_skip = [x for x in mandatory if x in skip]
    if invalid_skip:
        ret["comment"] = (
            "The following mandatory packages cannot be skipped: {}".format(
                ", ".join(invalid_skip)
            )
        )
        return ret

    targets = diff["mandatory"]["not installed"]
    targets.extend([x for x in diff["default"]["not installed"] if x not in skip])
    targets.extend(include)

    if not targets:
        ret["result"] = True
        ret["comment"] = f"Group '{name}' is already installed"
        return ret

    partially_installed = (
        diff["mandatory"]["installed"]
        or diff["default"]["installed"]
        or diff["optional"]["installed"]
    )

    if __opts__["test"]:
        ret["result"] = None
        if partially_installed:
            ret["comment"] = (
                f"Group '{name}' is partially installed and will be updated"
            )
        else:
            ret["comment"] = f"Group '{name}' will be installed"
        return ret

    try:
        ret["changes"] = __salt__["pkg.install"](pkgs=targets, **kwargs)
    except CommandExecutionError as exc:
        ret = {"name": name, "result": False}
        if exc.info:
            # Get information for state return from the exception.
            ret["changes"] = exc.info.get("changes", {})
            ret["comment"] = exc.strerror_without_changes
        else:
            ret["changes"] = {}
            ret["comment"] = (
                "An error was encountered while "
                "installing/updating group '{}': {}".format(name, exc)
            )
        return ret

    failed = [x for x in targets if x not in __salt__["pkg.list_pkgs"](**kwargs)]
    if failed:
        ret["comment"] = "Failed to install the following packages: {}".format(
            ", ".join(failed)
        )
        return ret

    ret["result"] = True
    ret["comment"] = "Group '{}' was {}".format(
        name, "updated" if partially_installed else "installed"
    )
    return ret


def mod_init(low):
    """
    Set a flag to tell the install functions to refresh the package database.
    This ensures that the package database is refreshed only once during
    a state run significantly improving the speed of package management
    during a state run.

    It sets a flag for a number of reasons, primarily due to timeline logic.
    When originally setting up the mod_init for pkg a number of corner cases
    arose with different package managers and how they refresh package data.

    It also runs the "ex_mod_init" from the package manager module that is
    currently loaded. The "ex_mod_init" is expected to work as a normal
    "mod_init" function.

    .. seealso::
       :py:func:`salt.modules.ebuild.ex_mod_init`

    """
    ret = True
    if "pkg.ex_mod_init" in __salt__:
        ret = __salt__["pkg.ex_mod_init"](low)

    if low["fun"] == "installed" or low["fun"] == "latest":
        salt.utils.pkg.write_rtag(__opts__)
        return ret
    return False


def mod_aggregate(low, chunks, running):
    """
    The mod_aggregate function which looks up all packages in the available
    low chunks and merges them into a single pkgs ref in the present low data
    """
    agg_enabled = [
        "installed",
        "latest",
        "removed",
        "purged",
    ]
    if low.get("fun") not in agg_enabled:
        return low
    is_sources = "sources" in low
    # use a dict instead of a set to maintain insertion order
    pkgs = {}
    for chunk in chunks:
        tag = __utils__["state.gen_tag"](chunk)
        if tag in running:
            # Already ran the pkg state, skip aggregation
            continue
        if chunk.get("state") == "pkg":
            if "__agg__" in chunk:
                continue
            # Check for the same function
            if chunk.get("fun") != low.get("fun"):
                continue
            # Check for the same repo
            if chunk.get("fromrepo") != low.get("fromrepo"):
                continue
            # If hold exists in the chunk, do not add to aggregation
            # otherwise all packages will be held or unheld.
            # setting a package to be held/unheld is not as
            # time consuming as installing/uninstalling.
            if "hold" in chunk:
                continue
            # Check first if 'sources' was passed so we don't aggregate pkgs
            # and sources together.
            if is_sources and "sources" in chunk:
                _combine_pkgs(pkgs, chunk["sources"])
                chunk["__agg__"] = True
            elif not is_sources:
                # Pull out the pkg names!
                if "pkgs" in chunk:
                    _combine_pkgs(pkgs, chunk["pkgs"])
                    chunk["__agg__"] = True
                elif "name" in chunk:
                    version = chunk.pop("version", None)
                    pkgs.setdefault(chunk["name"], set()).add(version)
                    chunk["__agg__"] = True
    if pkgs:
        pkg_type = "sources" if is_sources else "pkgs"
        low_pkgs = {}
        _combine_pkgs(low_pkgs, low.get(pkg_type, []))
        for pkg, values in pkgs.items():
            low_pkgs.setdefault(pkg, {None}).update(values)
        # the value is the version for pkgs and
        # the URI for sources
        low_pkgs_list = [
            name if value is None else {name: value}
            for name, values in pkgs.items()
            for value in values
        ]
        low[pkg_type] = low_pkgs_list
    return low


def _combine_pkgs(pkgs_dict, additional_pkgs_list):
    for item in additional_pkgs_list:
        if isinstance(item, str):
            pkgs_dict.setdefault(item, {None})
        else:
            for pkg, version in item:
                pkgs_dict.setdefault(pkg, {None}).add(version)


def mod_watch(name, **kwargs):
    """
    Install/reinstall a package based on a watch requisite

    .. note::
        This state exists to support special handling of the ``watch``
        :ref:`requisite <requisites>`. It should not be called directly.

        Parameters for this function should be set by the state being triggered.
    """
    sfun = kwargs.pop("sfun", None)
    mapfun = {
        "purged": purged,
        "latest": latest,
        "removed": removed,
        "installed": installed,
    }
    if sfun in mapfun:
        return mapfun[sfun](name, **kwargs)
    return {
        "name": name,
        "changes": {},
        "comment": f"pkg.{sfun} does not work with the watch requisite",
        "result": False,
    }


def mod_beacon(name, **kwargs):
    """
    Create a beacon to monitor a package or packages
    based on a beacon state argument.

    .. note::
        This state exists to support special handling of the ``beacon``
        state argument for supported state functions. It should not be called directly.

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    sfun = kwargs.pop("sfun", None)
    supported_funcs = ["installed", "removed"]

    if sfun in supported_funcs:
        if kwargs.get("beacon"):
            beacon_module = "pkg"

            beacon_name = f"beacon_{beacon_module}_{name}"

            beacon_kwargs = {
                "name": beacon_name,
                "pkgs": kwargs.get("pkgs", [name]),
                "interval": 60,
                "beacon_module": beacon_module,
            }

            ret = __states__["beacon.present"](**beacon_kwargs)
            return ret
        else:
            return {
                "name": name,
                "changes": {},
                "comment": "Not adding beacon.",
                "result": True,
            }

    else:
        return {
            "name": name,
            "changes": {},
            "comment": "pkg.{} does not work with the mod_beacon state function".format(
                sfun
            ),
            "result": False,
        }


def held(name, version=None, pkgs=None, replace=False, **kwargs):
    """
    .. versionadded:: 3005

    Set package in 'hold' state, meaning it will not be changed.

    :param str name:
        The name of the package to be held. This parameter is ignored
        if ``pkgs`` is used.

    :param str version:
        Hold a specific version of a package.
        Full description of this parameter is in `installed` function.

        .. note::

            This parameter make sense for Zypper-based systems.
            Ignored for YUM/DNF and APT

    :param list pkgs:
        A list of packages to be held. All packages listed under ``pkgs``
        will be held.

        .. code-block:: yaml

            mypkgs:
              pkg.held:
                - pkgs:
                  - foo
                  - bar: 1.2.3-4
                  - baz

        .. note::

            For Zypper-based systems the package could be held for
            the version specified. YUM/DNF and APT ingore it.

    :param bool replace:
        Force replacement of existings holds with specified.
        By default, this parameter is set to ``False``.
    """

    if isinstance(pkgs, list) and len(pkgs) == 0 and not replace:
        return {
            "name": name,
            "changes": {},
            "result": True,
            "comment": "No packages to be held provided",
        }

    # If just a name (and optionally a version) is passed, just pack them into
    # the pkgs argument.
    if name and pkgs is None:
        if version:
            pkgs = [{name: version}]
            version = None
        else:
            pkgs = [name]

    locks = {}
    vr_lock = False
    if "pkg.list_locks" in __salt__:
        locks = __salt__["pkg.list_locks"]()
        vr_lock = True
    elif "pkg.list_holds" in __salt__:
        _locks = __salt__["pkg.list_holds"](full=True)
        lock_re = re.compile(r"^(.+)-(\d+):(.*)\.\*")
        for lock in _locks:
            match = lock_re.match(lock)
            if match:
                epoch = match.group(2)
                if epoch == "0":
                    epoch = ""
                else:
                    epoch = f"{epoch}:"
                locks.update({match.group(1): {"version": f"{epoch}{match.group(3)}"}})
            else:
                locks.update({lock: {}})
    elif "pkg.get_selections" in __salt__:
        _locks = __salt__["pkg.get_selections"](state="hold")
        for lock in _locks.get("hold", []):
            locks.update({lock: {}})
    else:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": "No any function to get the list of held packages available.\n"
            "Check if the package manager supports package locking.",
        }

    if "pkg.hold" not in __salt__:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": "`hold` function is not implemented for the package manager.",
        }

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    comments = []

    held_pkgs = set()
    for pkg in pkgs:
        if isinstance(pkg, dict):
            (pkg_name, pkg_ver) = next(iter(pkg.items()))
        else:
            pkg_name = pkg
            pkg_ver = None
        lock_ver = None
        if pkg_name in locks and "version" in locks[pkg_name]:
            lock_ver = locks[pkg_name]["version"]
            lock_ver = lock_ver.lstrip("= ")
        held_pkgs.add(pkg_name)
        if pkg_name not in locks or (vr_lock and lock_ver != pkg_ver):
            if __opts__["test"]:
                if pkg_name in locks:
                    comments.append(
                        "The following package's hold rule would be updated: {}{}".format(
                            pkg_name,
                            "" if not pkg_ver else f" (version = {pkg_ver})",
                        )
                    )
                else:
                    comments.append(
                        "The following package would be held: {}{}".format(
                            pkg_name,
                            "" if not pkg_ver else f" (version = {pkg_ver})",
                        )
                    )
            else:
                unhold_ret = None
                if pkg_name in locks:
                    unhold_ret = __salt__["pkg.unhold"](name=name, pkgs=[pkg_name])
                hold_ret = __salt__["pkg.hold"](name=name, pkgs=[pkg])
                if not hold_ret.get(pkg_name, {}).get("result", False):
                    ret["result"] = False
                if (
                    unhold_ret
                    and unhold_ret.get(pkg_name, {}).get("result", False)
                    and hold_ret
                    and hold_ret.get(pkg_name, {}).get("result", False)
                ):
                    comments.append(f"Package {pkg_name} was updated with hold rule")
                elif hold_ret and hold_ret.get(pkg_name, {}).get("result", False):
                    comments.append(f"Package {pkg_name} is now being held")
                else:
                    comments.append(f"Package {pkg_name} was not held")
                ret["changes"].update(hold_ret)

    if replace:
        for pkg_name in locks:
            if locks[pkg_name].get("type", "package") != "package":
                continue
            if __opts__["test"]:
                if pkg_name not in held_pkgs:
                    comments.append(
                        f"The following package would be unheld: {pkg_name}"
                    )
            else:
                if pkg_name not in held_pkgs:
                    unhold_ret = __salt__["pkg.unhold"](name=name, pkgs=[pkg_name])
                    if not unhold_ret.get(pkg_name, {}).get("result", False):
                        ret["result"] = False
                    if unhold_ret and unhold_ret.get(pkg_name, {}).get("comment"):
                        comments.append(unhold_ret.get(pkg_name).get("comment"))
                    ret["changes"].update(unhold_ret)

    ret["comment"] = "\n".join(comments)
    if not (ret["changes"] or ret["comment"]):
        ret["comment"] = "No changes made"

    return ret


def unheld(name, version=None, pkgs=None, all=False, **kwargs):
    """
    .. versionadded:: 3005

    Unset package from 'hold' state, to allow operations with the package.

    :param str name:
        The name of the package to be unheld. This parameter is ignored
        if ``pkgs`` is used.

    :param str version:
        Unhold a specific version of a package.
        Full description of this parameter is in `installed` function.

        .. note::

            This parameter make sense for Zypper-based systems.
            Ignored for YUM/DNF and APT

    :param list pkgs:
        A list of packages to be unheld. All packages listed under ``pkgs``
        will be unheld.

        .. code-block:: yaml

            mypkgs:
              pkg.unheld:
                - pkgs:
                  - foo
                  - bar: 1.2.3-4
                  - baz

        .. note::

            For Zypper-based systems the package could be held for
            the version specified. YUM/DNF and APT ingore it.
            For ``unheld`` there is no need to specify the exact version
            to be unheld.

    :param bool all:
        Force removing of all existings locks.
        By default, this parameter is set to ``False``.
    """

    if isinstance(pkgs, list) and len(pkgs) == 0 and not all:
        return {
            "name": name,
            "changes": {},
            "result": True,
            "comment": "No packages to be unheld provided",
        }

    # If just a name (and optionally a version) is passed, just pack them into
    # the pkgs argument.
    if name and pkgs is None:
        pkgs = [{name: version}]
        version = None

    locks = {}
    vr_lock = False
    if "pkg.list_locks" in __salt__:
        locks = __salt__["pkg.list_locks"]()
        vr_lock = True
    elif "pkg.list_holds" in __salt__:
        _locks = __salt__["pkg.list_holds"](full=True)
        lock_re = re.compile(r"^(.+)-(\d+):(.*)\.\*")
        for lock in _locks:
            match = lock_re.match(lock)
            if match:
                epoch = match.group(2)
                if epoch == "0":
                    epoch = ""
                else:
                    epoch = f"{epoch}:"
                locks.update({match.group(1): {"version": f"{epoch}{match.group(3)}"}})
            else:
                locks.update({lock: {}})
    elif "pkg.get_selections" in __salt__:
        _locks = __salt__["pkg.get_selections"](state="hold")
        for lock in _locks.get("hold", []):
            locks.update({lock: {}})
    else:
        return {
            "name": name,
            "changes": {},
            "result": False,
            "comment": "No any function to get the list of held packages available.\n"
            "Check if the package manager supports package locking.",
        }

    dpkgs = {}
    for pkg in pkgs:
        if isinstance(pkg, dict):
            (pkg_name, pkg_ver) = next(iter(pkg.items()))
            dpkgs.update({pkg_name: pkg_ver})
        else:
            dpkgs.update({pkg: None})  # pylint: disable=unhashable-member

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    comments = []

    for pkg_name in locks:
        if locks[pkg_name].get("type", "package") != "package":
            continue
        lock_ver = None
        if vr_lock and "version" in locks[pkg_name]:
            lock_ver = locks[pkg_name]["version"]
            lock_ver = lock_ver.lstrip("= ")
        if all or (pkg_name in dpkgs and (not lock_ver or lock_ver == dpkgs[pkg_name])):
            if __opts__["test"]:
                comments.append(
                    "The following package would be unheld: {}{}".format(
                        pkg_name,
                        "" if not dpkgs.get(pkg_name) else f" (version = {lock_ver})",
                    )
                )
            else:
                unhold_ret = __salt__["pkg.unhold"](name=name, pkgs=[pkg_name])
                if not unhold_ret.get(pkg_name, {}).get("result", False):
                    ret["result"] = False
                if unhold_ret and unhold_ret.get(pkg_name, {}).get("comment"):
                    comments.append(unhold_ret.get(pkg_name).get("comment"))
                ret["changes"].update(unhold_ret)

    ret["comment"] = "\n".join(comments)
    if not (ret["changes"] or ret["comment"]):
        ret["comment"] = "No changes made"

    return ret
