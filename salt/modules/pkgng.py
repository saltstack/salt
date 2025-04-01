"""
Support for ``pkgng``, the new package manager for FreeBSD

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.

.. warning::

    This module has been completely rewritten. Up to and including version
    0.17.x, it was available as the ``pkgng`` module, (``pkgng.install``,
    ``pkgng.delete``, etc.), but moving forward this module will no longer be
    available as ``pkgng``, as it will behave like a normal Salt ``pkg``
    provider. The documentation below should not be considered to apply to this
    module in versions <= 0.17.x. If your minion is running a 0.17.x release or
    older, then the documentation for this module can be viewed using the
    :mod:`sys.doc <salt.modules.sys.doc>` function:

    .. code-block:: bash

        salt bsdminion sys.doc pkgng


This module provides an interface to ``pkg(8)``. It acts as the default
package provider for FreeBSD 10 and newer. For FreeBSD hosts which have
been upgraded to use pkgng, you will need to override the ``pkg`` provider
by setting the :conf_minion:`providers` parameter in your Minion config
file, in order to use this module to manage packages, like so:

.. code-block:: yaml

    providers:
      pkg: pkgng

"""

import copy
import logging
import os
import re

import salt.utils.data
import salt.utils.files
import salt.utils.functools
import salt.utils.itertools
import salt.utils.pkg
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import CommandExecutionError, MinionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Load as 'pkg' on FreeBSD 10 and greater.
    Load as 'pkg' on DragonFly BSD.
    Load as 'pkg' on FreeBSD 9 when config option
    ``providers:pkg`` is set to 'pkgng'.
    """
    if __grains__["kernel"] == "DragonFly":
        return __virtualname__
    if __grains__["os"] == "FreeBSD" and float(__grains__["osrelease"]) >= 10:
        return __virtualname__
    if __grains__["os"] == "FreeBSD" and int(__grains__["osmajorrelease"]) == 9:
        providers = {}
        if "providers" in __opts__:
            providers = __opts__["providers"]
        log.debug("__opts__.providers: %s", providers)
        if providers and "pkg" in providers and providers["pkg"] == "pkgng":
            log.debug(
                "Configuration option 'providers:pkg' is set to "
                "'pkgng', using 'pkgng' in favor of 'freebsdpkg'."
            )
            return __virtualname__
    return (
        False,
        "The pkgng execution module cannot be loaded: only available "
        "on FreeBSD 10 or FreeBSD 9 with providers.pkg set to pkgng.",
    )


def _pkg(jail=None, chroot=None, root=None):
    """
    Returns the prefix for a pkg command, using -j if a jail is specified, or
    -c if chroot is specified.
    """
    ret = ["pkg"]
    if jail:
        ret.extend(["-j", jail])
    elif chroot:
        ret.extend(["-c", chroot])
    elif root:
        ret.extend(["-r", root])
    return ret


def _get_pkgng_version(jail=None, chroot=None, root=None):
    """
    return the version of 'pkg'
    """
    cmd = _pkg(jail, chroot, root) + ["--version"]
    return __salt__["cmd.run"](cmd).strip()


def _get_version(name, results):
    """
    ``pkg search`` will return all packages for which the pattern is a match.
    Narrow this down and return the package version, or None if no exact match.
    """
    for line in salt.utils.itertools.split(results, "\n"):
        if not line:
            continue
        try:
            pkgname, pkgver = line.rsplit("-", 1)
        except ValueError:
            continue
        if pkgname == name:
            return pkgver
    return None


def _contextkey(jail=None, chroot=None, root=None, prefix="pkg.list_pkgs"):
    """
    As this module is designed to manipulate packages in jails and chroots, use
    the passed jail/chroot to ensure that a key in the __context__ dict that is
    unique to that jail/chroot is used.
    """
    if jail:
        return str(prefix) + f".jail_{jail}"
    elif chroot:
        return str(prefix) + f".chroot_{chroot}"
    elif root:
        return str(prefix) + f".root_{root}"
    return prefix


def parse_config(file_name="/usr/local/etc/pkg.conf"):
    """
    Return dict of uncommented global variables.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.parse_config

    ``NOTE:`` not working properly right now
    """
    ret = {}
    if not os.path.isfile(file_name):
        return f"Unable to find {file_name} on file system"

    with salt.utils.files.fopen(file_name) as ifile:
        for line in ifile:
            line = salt.utils.stringutils.to_unicode(line)
            if line.startswith("#") or line.startswith("\n"):
                pass
            else:
                key, value = line.split("\t")
                ret[key] = value
    ret["config_file"] = file_name
    return ret


def version(*names, **kwargs):
    """
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    .. note::

        This function can accessed using ``pkg.info`` in addition to
        ``pkg.version``, to more closely match the CLI usage of ``pkg(8)``.

    jail
        Get package version information for the specified jail

    chroot
        Get package version information for the specified chroot (ignored if
        ``jail`` is specified)

    root
        Get package version information for the specified root (ignored if
        ``jail`` is specified)

    with_origin : False
        Return a nested dictionary containing both the origin name and version
        for each specified package.

        .. versionadded:: 2014.1.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package name> jail=<jail name or id>
        salt '*' pkg.version <package1> <package2> <package3> ...
    """
    with_origin = kwargs.pop("with_origin", False)
    ret = __salt__["pkg_resource.version"](*names, **kwargs)
    if not salt.utils.data.is_true(with_origin):
        return ret
    # Put the return value back into a dict since we're adding a subdict
    if len(names) == 1:
        ret = {names[0]: ret}
    origins = __context__.get("pkg.origin", {})
    return {x: {"origin": origins.get(x, ""), "version": y} for x, y in ret.items()}


# Support pkg.info get version info, since this is the CLI usage
info = salt.utils.functools.alias_function(version, "info")


def refresh_db(jail=None, chroot=None, root=None, force=False, **kwargs):
    """
    Refresh PACKAGESITE contents

    .. note::

        This function can accessed using ``pkg.update`` in addition to
        ``pkg.refresh_db``, to more closely match the CLI usage of ``pkg(8)``.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db

    jail
        Refresh the pkg database within the specified jail

    chroot
        Refresh the pkg database within the specified chroot (ignored if
        ``jail`` is specified)

    root
        Refresh the pkg database within the specified root (ignored if
        ``jail`` is specified)

    force
        Force a full download of the repository catalog without regard to the
        respective ages of the local and remote copies of the catalog.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.refresh_db force=True
    """
    # Remove rtag file to keep multiple refreshes from happening in pkg states
    salt.utils.pkg.clear_rtag(__opts__)
    cmd = _pkg(jail, chroot, root)
    cmd.append("update")
    if force:
        cmd.append("-f")
    return __salt__["cmd.retcode"](cmd, python_shell=False) == 0


# Support pkg.update to refresh the db, since this is the CLI usage
update = salt.utils.functools.alias_function(refresh_db, "update")


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
        salt '*' pkg.latest_version <package name> jail=<jail name or id>
        salt '*' pkg.latest_version <package name> chroot=/path/to/chroot
    """
    if not names:
        return ""
    ret = {}

    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ""
    jail = kwargs.get("jail")
    chroot = kwargs.get("chroot")
    refresh = kwargs.get("refresh")
    root = kwargs.get("root")
    pkgs = list_pkgs(jail=jail, chroot=chroot, root=root)

    for name in names:
        cmd = _pkg(jail, chroot, root) + ["search", "-eqS"]
        if "/" in name:
            # FreeBSD's pkg supports searching by origin, like java/openjdk7
            cmd.append("origin")
        else:
            cmd.append("name")
        if not salt.utils.data.is_true(refresh):
            cmd.append("-U")
        cmd.append(name)

        pkg_output = __salt__["cmd.run"](
            cmd, python_shell=False, output_loglevel="trace"
        )
        if pkg_output != "":
            pkgver = pkg_output.rsplit("-", 1)[1]
            installed = pkgs.get(name)
            if not installed:
                ret[name] = pkgver
            else:
                if not salt.utils.versions.compare(
                    ver1=installed, oper=">=", ver2=pkgver
                ):
                    ret[name] = pkgver

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


# available_version is being deprecated
available_version = salt.utils.functools.alias_function(
    latest_version, "available_version"
)


def _list_pkgs_from_context(
    versions_as_list, contextkey_pkg, contextkey_origins, with_origin
):
    """
    Use pkg list from __context__
    """
    ret = copy.deepcopy(__context__[contextkey_pkg])
    if not versions_as_list:
        __salt__["pkg_resource.stringify"](ret)
    if salt.utils.data.is_true(with_origin):
        origins = __context__.get(contextkey_origins, {})
        return {x: {"origin": origins.get(x, ""), "version": y} for x, y in ret.items()}
    return ret


def list_pkgs(
    versions_as_list=False,
    jail=None,
    chroot=None,
    root=None,
    with_origin=False,
    **kwargs,
):
    """
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    jail
        List the packages in the specified jail

    chroot
        List the packages in the specified chroot (ignored if ``jail`` is
        specified)

    root
        List the packages in the specified root (ignored if ``jail`` is
        specified)

    with_origin : False
        Return a nested dictionary containing both the origin name and version
        for each installed package.

        .. versionadded:: 2014.1.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs jail=<jail name or id>
        salt '*' pkg.list_pkgs chroot=/path/to/chroot
    """
    # not yet implemented or not applicable
    if any(
        [salt.utils.data.is_true(kwargs.get(x)) for x in ("removed", "purge_desired")]
    ):
        return {}

    versions_as_list = salt.utils.data.is_true(versions_as_list)
    contextkey_pkg = _contextkey(jail, chroot, root)
    contextkey_origins = _contextkey(jail, chroot, root, prefix="pkg.origin")

    if contextkey_pkg in __context__ and kwargs.get("use_context", True):
        return _list_pkgs_from_context(
            versions_as_list, contextkey_pkg, contextkey_origins, with_origin
        )

    ret = {}
    origins = {}
    out = __salt__["cmd.run_stdout"](
        _pkg(jail, chroot, root) + ["info", "-ao"],
        output_loglevel="trace",
        python_shell=False,
    )
    for line in salt.utils.itertools.split(out, "\n"):
        if not line:
            continue
        try:
            pkg, origin = line.split()
            pkgname, pkgver = pkg.rsplit("-", 1)
        except ValueError:
            continue
        __salt__["pkg_resource.add_pkg"](ret, pkgname, pkgver)
        origins[pkgname] = origin

    __salt__["pkg_resource.sort_pkglist"](ret)
    __context__[contextkey_pkg] = copy.deepcopy(ret)
    __context__[contextkey_origins] = origins
    if not versions_as_list:
        __salt__["pkg_resource.stringify"](ret)
    if salt.utils.data.is_true(with_origin):
        return {x: {"origin": origins.get(x, ""), "version": y} for x, y in ret.items()}
    return ret


def update_package_site(new_url):
    """
    Updates remote package repo URL, PACKAGESITE var to be exact.

    Must use ``http://``, ``ftp://``, or ``https://`` protocol

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.update_package_site http://127.0.0.1/
    """
    config_file = parse_config()["config_file"]
    __salt__["file.sed"](config_file, "PACKAGESITE.*", f"PACKAGESITE\t : {new_url}")

    # add change return later
    return True


def stats(local=False, remote=False, jail=None, chroot=None, root=None, bytes=False):
    """
    Return pkgng stats.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.stats

    local
        Display stats only for the local package database.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.stats local=True

    remote
        Display stats only for the remote package database(s).

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.stats remote=True

    bytes
        Display disk space usage in bytes only.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.stats bytes=True

    jail
        Retrieve stats from the specified jail.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.stats jail=<jail name or id>
            salt '*' pkg.stats jail=<jail name or id> local=True
            salt '*' pkg.stats jail=<jail name or id> remote=True

    chroot
        Retrieve stats from the specified chroot (ignored if ``jail`` is
        specified).

    root
        Retrieve stats from the specified root (ignored if ``jail`` is
        specified).

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.stats chroot=/path/to/chroot
            salt '*' pkg.stats chroot=/path/to/chroot local=True
            salt '*' pkg.stats chroot=/path/to/chroot remote=True
    """

    opts = ""
    if local:
        opts += "l"
    if remote:
        opts += "r"
    if bytes:
        opts += "b"

    cmd = _pkg(jail, chroot, root)
    cmd.append("stats")
    if opts:
        cmd.append("-" + opts)
    out = __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)
    return [x.strip("\t") for x in salt.utils.itertools.split(out, "\n")]


def backup(file_name, jail=None, chroot=None, root=None):
    """
    Export installed packages into yaml+mtree file

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.backup /tmp/pkg

    jail
        Backup packages from the specified jail. Note that this will run the
        command within the jail, and so the path to the backup file will be
        relative to the root of the jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.backup /tmp/pkg jail=<jail name or id>

    chroot
        Backup packages from the specified chroot (ignored if ``jail`` is
        specified). Note that this will run the command within the chroot, and
        so the path to the backup file will be relative to the root of the
        chroot.

    root
        Backup packages from the specified root (ignored if ``jail`` is
        specified). Note that this will run the command within the root, and
        so the path to the backup file will be relative to the root of the
        root.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.backup /tmp/pkg chroot=/path/to/chroot
    """
    ret = __salt__["cmd.run"](
        _pkg(jail, chroot, root) + ["backup", "-d", file_name],
        output_loglevel="trace",
        python_shell=False,
    )
    return ret.split("...")[1]


def restore(file_name, jail=None, chroot=None, root=None):
    """
    Reads archive created by pkg backup -d and recreates the database.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.restore /tmp/pkg

    jail
        Restore database to the specified jail. Note that this will run the
        command within the jail, and so the path to the file from which the pkg
        database will be restored is relative to the root of the jail.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.restore /tmp/pkg jail=<jail name or id>

    chroot
        Restore database to the specified chroot (ignored if ``jail`` is
        specified). Note that this will run the command within the chroot, and
        so the path to the file from which the pkg database will be restored is
        relative to the root of the chroot.

    root
        Restore database to the specified root (ignored if ``jail`` is
        specified). Note that this will run the command within the root, and
        so the path to the file from which the pkg database will be restored is
        relative to the root of the root.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.restore /tmp/pkg chroot=/path/to/chroot
    """
    return __salt__["cmd.run"](
        _pkg(jail, chroot, root) + ["backup", "-r", file_name],
        output_loglevel="trace",
        python_shell=False,
    )


def audit(jail=None, chroot=None, root=None):
    """
    Audits installed packages against known vulnerabilities

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.audit

    jail
        Audit packages within the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.audit jail=<jail name or id>

    chroot
        Audit packages within the specified chroot (ignored if ``jail`` is
        specified)

    root
        Audit packages within the specified root (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.audit chroot=/path/to/chroot
    """
    return __salt__["cmd.run"](
        _pkg(jail, chroot, root) + ["audit", "-F"],
        output_loglevel="trace",
        python_shell=False,
    )


def install(
    name=None,
    fromrepo=None,
    pkgs=None,
    sources=None,
    jail=None,
    chroot=None,
    root=None,
    orphan=False,
    force=False,
    glob=False,
    local=False,
    dryrun=False,
    quiet=False,
    reinstall_requires=False,
    regex=False,
    pcre=False,
    batch=False,
    **kwargs,
):
    """
    Install package(s) from a repository

    name
        The name of the package to install

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    jail
        Install the package into the specified jail

    chroot
        Install the package into the specified chroot (ignored if ``jail`` is
        specified)

    root
        Install the package into the specified root (ignored if ``jail`` is
        specified)

    orphan
        Mark the installed package as orphan. Will be automatically removed
        if no other packages depend on them. For more information please
        refer to ``pkg-autoremove(8)``.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> orphan=True

    force
        Force the reinstallation of the package if already installed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> force=True

    glob
        Treat the package names as shell glob patterns.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> glob=True

    local
        Do not update the repository catalogs with ``pkg-update(8)``.  A
        value of ``True`` here is equivalent to using the ``-U`` flag with
        ``pkg install``.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> local=True

    dryrun
        Dru-run mode. The list of changes to packages is always printed,
        but no changes are actually made.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> dryrun=True

    quiet
        Force quiet output, except when dryrun is used, where pkg install
        will always show packages to be installed, upgraded or deleted.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> quiet=True

    reinstall_requires
        When used with force, reinstalls any packages that require the
        given package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> reinstall_requires=True force=True

        .. versionchanged:: 2014.7.0
            ``require`` kwarg renamed to ``reinstall_requires``

    fromrepo
        In multi-repo mode, override the pkg.conf ordering and only attempt
        to download packages from the named repository.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> fromrepo=repo

    regex
        Treat the package names as a regular expression

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <regular expression> regex=True

    pcre
        Treat the package names as extended regular expressions.

        CLI Example:

        .. code-block:: bash


    batch
        Use BATCH=true for pkg install, skipping all questions.
        Be careful when using in production.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> batch=True
    """
    try:
        pkg_params, pkg_type = __salt__["pkg_resource.parse_targets"](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if not pkg_params:
        return {}

    env = {}
    opts = "y"
    if salt.utils.data.is_true(orphan):
        opts += "A"
    if salt.utils.data.is_true(force):
        opts += "f"
    if salt.utils.data.is_true(glob):
        opts += "g"
    if salt.utils.data.is_true(local):
        opts += "U"
    if salt.utils.data.is_true(dryrun):
        opts += "n"
    if salt.utils.data.is_true(quiet):
        opts += "q"
    if salt.utils.data.is_true(reinstall_requires):
        opts += "R"
    if salt.utils.data.is_true(regex):
        opts += "x"
    if salt.utils.data.is_true(pcre):
        opts += "X"
    if salt.utils.data.is_true(batch):
        env = {"BATCH": "true", "ASSUME_ALWAYS_YES": "YES"}

    old = list_pkgs(jail=jail, chroot=chroot, root=root)

    if pkg_type == "file":
        pkg_cmd = "add"
        # pkg add has smaller set of options (i.e. no -y or -n), filter below
        opts = "".join([opt for opt in opts if opt in "AfIMq"])
        targets = pkg_params
    elif pkg_type == "repository":
        pkg_cmd = "install"
        if pkgs is None and kwargs.get("version") and len(pkg_params) == 1:
            # Only use the 'version' param if 'name' was not specified as a
            # comma-separated list
            pkg_params = {name: kwargs.get("version")}
        targets = []
        for param, version_num in pkg_params.items():
            if version_num is None:
                targets.append(param)
            else:
                targets.append(f"{param}-{version_num}")
    else:
        raise CommandExecutionError("Problem encountered installing package(s)")

    cmd = _pkg(jail, chroot, root)
    cmd.append(pkg_cmd)
    if fromrepo:
        cmd.extend(["-r", fromrepo])
    if opts:
        cmd.append("-" + opts)
    cmd.extend(targets)

    if pkg_cmd == "add" and salt.utils.data.is_true(dryrun):
        # pkg add doesn't have a dry-run mode, so echo out what will be run
        return " ".join(cmd)

    out = __salt__["cmd.run_all"](
        cmd, output_loglevel="trace", python_shell=False, env=env
    )

    if out["retcode"] != 0 and out["stderr"]:
        errors = [out["stderr"]]
    else:
        errors = []

    __context__.pop(_contextkey(jail, chroot, root), None)
    __context__.pop(_contextkey(jail, chroot, root, prefix="pkg.origin"), None)
    new = list_pkgs(jail=jail, chroot=chroot, root=root)
    ret = salt.utils.data.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            "Problem encountered installing package(s)",
            info={"errors": errors, "changes": ret},
        )

    return ret


def remove(
    name=None,
    pkgs=None,
    jail=None,
    chroot=None,
    root=None,
    all_installed=False,
    force=False,
    glob=False,
    dryrun=False,
    recurse=False,
    regex=False,
    pcre=False,
    **kwargs,
):
    """
    Remove a package from the database and system

    .. note::

        This function can accessed using ``pkg.delete`` in addition to
        ``pkg.remove``, to more closely match the CLI usage of ``pkg(8)``.

    name
        The package to remove

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.remove <package name>

    jail
        Delete the package from the specified jail

    chroot
        Delete the package from the specified chroot (ignored if ``jail`` is
        specified)

    root
        Delete the package from the specified root (ignored if ``jail`` is
        specified)

    all_installed
        Deletes all installed packages from the system and empties the
        database. USE WITH CAUTION!

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.remove all all_installed=True force=True

    force
        Forces packages to be removed despite leaving unresolved
        dependencies.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.remove <package name> force=True

    glob
        Treat the package names as shell glob patterns.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.remove <package name> glob=True

    dryrun
        Dry run mode. The list of packages to delete is always printed, but
        no packages are actually deleted.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.remove <package name> dryrun=True

    recurse
        Delete all packages that require the listed package as well.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.remove <package name> recurse=True

    regex
        Treat the package names as regular expressions.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.remove <regular expression> regex=True

    pcre
        Treat the package names as extended regular expressions.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.remove <extended regular expression> pcre=True
    """
    del kwargs  # Unused parameter

    try:
        pkg_params = __salt__["pkg_resource.parse_targets"](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    targets = []
    old = list_pkgs(jail=jail, chroot=chroot, root=root, with_origin=True)
    for pkg in pkg_params.items():
        # FreeBSD pkg supports `openjdk` and `java/openjdk7` package names
        if pkg[0].find("/") > 0:
            origin = pkg[0]
            pkg = [k for k, v in old.items() if v["origin"] == origin][0]

        if pkg[0] in old:
            targets.append(pkg[0])

    if not targets:
        return {}

    opts = ""
    if salt.utils.data.is_true(all_installed):
        opts += "a"
    if salt.utils.data.is_true(force):
        opts += "f"
    if salt.utils.data.is_true(glob):
        opts += "g"
    if salt.utils.data.is_true(dryrun):
        opts += "n"
    if not salt.utils.data.is_true(dryrun):
        opts += "y"
    if salt.utils.data.is_true(recurse):
        opts += "R"
    if salt.utils.data.is_true(regex):
        opts += "x"
    if salt.utils.data.is_true(pcre):
        opts += "X"

    cmd = _pkg(jail, chroot, root)
    cmd.append("delete")
    if opts:
        cmd.append("-" + opts)
    cmd.extend(targets)

    out = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    if out["retcode"] != 0 and out["stderr"]:
        errors = [out["stderr"]]
    else:
        errors = []

    __context__.pop(_contextkey(jail, chroot, root), None)
    __context__.pop(_contextkey(jail, chroot, root, prefix="pkg.origin"), None)
    new = list_pkgs(jail=jail, chroot=chroot, root=root, with_origin=True)
    ret = salt.utils.data.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            "Problem encountered removing package(s)",
            info={"errors": errors, "changes": ret},
        )

    return ret


# Support pkg.delete to remove packages, since this is the CLI usage
delete = salt.utils.functools.alias_function(remove, "delete")
# No equivalent to purge packages, use remove instead
purge = salt.utils.functools.alias_function(remove, "purge")


def upgrade(*names, **kwargs):
    """
    Upgrade named or all packages (run a ``pkg upgrade``). If <package name> is
    omitted, the operation is executed on all packages.

    Returns a dictionary containing the changes:

    .. code-block:: python

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade <package name>

    jail
        Audit packages within the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.upgrade <package name> jail=<jail name or id>

    chroot
        Audit packages within the specified chroot (ignored if ``jail`` is
        specified)

    root
        Audit packages within the specified root (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.upgrade <package name> chroot=/path/to/chroot


    Any of the below options can also be used with ``jail`` or ``chroot``.

    force
        Force reinstalling/upgrading the whole set of packages.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.upgrade <package name> force=True

    local
        Do not update the repository catalogs with ``pkg-update(8)``. A value
        of ``True`` here is equivalent to using the ``-U`` flag with ``pkg
        upgrade``.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.upgrade <package name> local=True

    dryrun
        Dry-run mode: show what packages have updates available, but do not
        perform any upgrades. Repository catalogs will be updated as usual
        unless the local option is also given.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.upgrade <package name> dryrun=True

    fromrepo
        In multi-repo mode, override the pkg.conf ordering and only attempt
        to upgrade packages from the named repository.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.upgrade <package name> fromrepo=repo

    fetchonly
        Do not perform installation of packages, merely fetch
        packages that should be upgraded and detect possible conflicts.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.upgrade <package name> fetchonly=True
    """
    jail = kwargs.pop("jail", None)
    chroot = kwargs.pop("chroot", None)
    root = kwargs.pop("root", None)
    fromrepo = kwargs.pop("fromrepo", None)
    force = kwargs.pop("force", False)
    local = kwargs.pop("local", False)
    dryrun = kwargs.pop("dryrun", False)
    fetchonly = kwargs.pop("fetchonly", False)
    pkgs = kwargs.pop("pkgs", [])
    opts = ""
    if force:
        opts += "f"
    if local:
        opts += "U"
    if fetchonly:
        opts += "F"
    if dryrun:
        opts += "n"
    if not dryrun:
        opts += "y"

    cmd = _pkg(jail, chroot, root)
    cmd.append("upgrade")
    if opts:
        cmd.append("-" + opts)
    if names:
        cmd.extend(names)
    if pkgs:
        cmd.extend(pkgs)
    if fromrepo:
        cmd.extend(["--repository", fromrepo])

    old = list_pkgs()
    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)
    __context__.pop(_contextkey(jail, chroot, root), None)
    __context__.pop(_contextkey(jail, chroot, root, prefix="pkg.origin"), None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if result["retcode"] != 0:
        raise CommandExecutionError(
            "Problem encountered upgrading packages",
            info={"changes": ret, "result": result},
        )

    return ret


def clean(jail=None, chroot=None, root=None, clean_all=False, dryrun=False):
    """
    Cleans the local cache of fetched remote packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.clean

    jail
        Cleans the package cache in the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.clean jail=<jail name or id>

    chroot
        Cleans the package cache in the specified chroot (ignored if ``jail``
        is specified)

    root
        Cleans the package cache in the specified root (ignored if ``jail``
        is specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.clean chroot=/path/to/chroot

    clean_all
        Clean all packages from the local cache (not just those that have been
        superseded by newer versions).

        CLI Example:

        .. code-block:: bash

        salt '*' pkg.clean clean_all=True

    dryrun
        Dry-run mode. This list of changes to the local cache is always
        printed, but no changes are actually made.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.clean dryrun=True
    """
    opts = ""
    if clean_all:
        opts += "a"
    if dryrun:
        opts += "n"
    else:
        opts += "y"

    cmd = _pkg(jail, chroot, root)
    cmd.append("clean")
    if opts:
        cmd.append("-" + opts)
    return __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)


def autoremove(jail=None, chroot=None, root=None, dryrun=False):
    """
    Delete packages which were automatically installed as dependencies and are
    not required anymore.

    dryrun
        Dry-run mode. The list of changes to packages is always printed,
        but no changes are actually made.

    CLI Example:

    .. code-block:: bash

         salt '*' pkg.autoremove
         salt '*' pkg.autoremove jail=<jail name or id>
         salt '*' pkg.autoremove dryrun=True
         salt '*' pkg.autoremove jail=<jail name or id> dryrun=True
    """
    opts = ""
    if dryrun:
        opts += "n"
    else:
        opts += "y"

    cmd = _pkg(jail, chroot, root)
    cmd.append("autoremove")
    if opts:
        cmd.append("-" + opts)
    return __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)


def check(
    jail=None,
    chroot=None,
    root=None,
    depends=False,
    recompute=False,
    checksum=False,
    checklibs=False,
):
    """
    Sanity checks installed packages

    jail
        Perform the sanity check in the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.check jail=<jail name or id>

    chroot
        Perform the sanity check in the specified chroot (ignored if ``jail``
        is specified)

    root
        Perform the sanity check in the specified root (ignored if ``jail``
        is specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.check chroot=/path/to/chroot


    Of the below, at least one must be set to ``True``.

    depends
        Check for and install missing dependencies.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.check depends=True

    recompute
        Recompute sizes and checksums of installed packages.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.check recompute=True

    checksum
        Find invalid checksums for installed packages.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.check checksum=True

    checklibs
        Regenerates the library dependency metadata for a package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.check checklibs=True

    """
    if not any((depends, recompute, checksum, checklibs)):
        return "One of depends, recompute, checksum or checklibs must be set to True"

    opts = ""
    if depends:
        opts += "dy"
    if recompute:
        opts += "r"
    if checksum:
        opts += "s"
    if checklibs:
        opts += "B"

    cmd = _pkg(jail, chroot, root)
    cmd.append("check")
    if opts:
        cmd.append("-" + opts)
    return __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)


def which(path, jail=None, chroot=None, root=None, origin=False, quiet=False):
    """
    Displays which package installed a specific file

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.which <file name>

    jail
        Perform the check in the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.which <file name> jail=<jail name or id>

    chroot
        Perform the check in the specified chroot (ignored if ``jail`` is
        specified)

    root
        Perform the check in the specified root (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.which <file name> chroot=/path/to/chroot


    origin
        Shows the origin of the package instead of name-version.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.which <file name> origin=True

    quiet
        Quiet output.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.which <file name> quiet=True
    """
    opts = ""
    if quiet:
        opts += "q"
    if origin:
        opts += "o"

    cmd = _pkg(jail, chroot, root)
    cmd.append("which")
    if opts:
        cmd.append("-" + opts)
    cmd.append(path)
    return __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)


def search(
    name,
    jail=None,
    chroot=None,
    root=None,
    exact=False,
    glob=False,
    regex=False,
    pcre=False,
    comment=False,
    desc=False,
    full=False,
    depends=False,
    size=False,
    quiet=False,
    origin=False,
    prefix=False,
):
    """
    Searches in remote package repositories

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.search pattern

    jail
        Perform the search using the ``pkg.conf(5)`` from the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern jail=<jail name or id>

    chroot
        Perform the search using the ``pkg.conf(5)`` from the specified chroot
        (ignored if ``jail`` is specified)

    root
        Perform the search using the ``pkg.conf(5)`` from the specified root
        (ignored if ``jail`` is specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern chroot=/path/to/chroot

    exact
        Treat pattern as exact pattern.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern exact=True

    glob
        Treat pattern as a shell glob pattern.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern glob=True

    regex
        Treat pattern as a regular expression.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern regex=True

    pcre
        Treat pattern as an extended regular expression.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern pcre=True

    comment
        Search for pattern in the package comment one-line description.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern comment=True

    desc
        Search for pattern in the package description.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern desc=True

    full
        Displays full information about the matching packages.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern full=True

    depends
        Displays the dependencies of pattern.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern depends=True

    size
        Displays the size of the package

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern size=True

    quiet
        Be quiet. Prints only the requested information without displaying
        many hints.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern quiet=True

    origin
        Displays pattern origin.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern origin=True

    prefix
        Displays the installation prefix for each package matching pattern.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.search pattern prefix=True
    """

    opts = ""
    if exact:
        opts += "e"
    if glob:
        opts += "g"
    if regex:
        opts += "x"
    if pcre:
        opts += "X"
    if comment:
        opts += "c"
    if desc:
        opts += "D"
    if full:
        opts += "f"
    if depends:
        opts += "d"
    if size:
        opts += "s"
    if quiet:
        opts += "q"
    if origin:
        opts += "o"
    if prefix:
        opts += "p"

    cmd = _pkg(jail, chroot, root)
    cmd.append("search")
    if opts:
        cmd.append("-" + opts)
    cmd.append(name)
    return __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)


def fetch(
    name,
    jail=None,
    chroot=None,
    root=None,
    fetch_all=False,
    quiet=False,
    fromrepo=None,
    glob=True,
    regex=False,
    pcre=False,
    local=False,
    depends=False,
):
    """
    Fetches remote packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.fetch <package name>

    jail
        Fetch package in the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.fetch <package name> jail=<jail name or id>

    chroot
        Fetch package in the specified chroot (ignored if ``jail`` is
        specified)

    root
        Fetch package in the specified root (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.fetch <package name> chroot=/path/to/chroot

    fetch_all
        Fetch all packages.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.fetch <package name> fetch_all=True

    quiet
        Quiet mode. Show less output.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.fetch <package name> quiet=True

    fromrepo
        Fetches packages from the given repo if multiple repo support
        is enabled. See ``pkg.conf(5)``.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.fetch <package name> fromrepo=repo

    glob
        Treat pkg_name as a shell glob pattern.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.fetch <package name> glob=True

    regex
        Treat pkg_name as a regular expression.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.fetch <regular expression> regex=True

    pcre
        Treat pkg_name is an extended regular expression.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.fetch <extended regular expression> pcre=True

    local
        Skip updating the repository catalogs with pkg-update(8). Use the
        local cache only.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.fetch <package name> local=True

    depends
        Fetch the package and its dependencies as well.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.fetch <package name> depends=True
    """
    opts = ""
    if fetch_all:
        opts += "a"
    if quiet:
        opts += "q"
    if glob:
        opts += "g"
    if regex:
        opts += "x"
    if pcre:
        opts += "X"
    if local:
        opts += "L"
    if depends:
        opts += "d"

    cmd = _pkg(jail, chroot, root)
    cmd.extend(["fetch", "-y"])
    if fromrepo:
        cmd.extend(["-r", fromrepo])
    if opts:
        cmd.append("-" + opts)
    cmd.append(name)
    return __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)


def updating(name, jail=None, chroot=None, root=None, filedate=None, filename=None):
    """'
    Displays UPDATING entries of software packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.updating foo

    jail
        Perform the action in the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.updating foo jail=<jail name or id>

    chroot
        Perform the action in the specified chroot (ignored if ``jail`` is
        specified)

    root
        Perform the action in the specified root (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.updating foo chroot=/path/to/chroot

    filedate
        Only entries newer than date are shown. Use a YYYYMMDD date format.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.updating foo filedate=20130101

    filename
        Defines an alternative location of the UPDATING file.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.updating foo filename=/tmp/UPDATING
    """

    opts = ""
    if filedate:
        opts += f"d {filedate}"
    if filename:
        opts += f"f {filename}"

    cmd = _pkg(jail, chroot, root)
    cmd.append("updating")
    if opts:
        cmd.append("-" + opts)
    cmd.append(name)
    return __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)


def hold(name=None, pkgs=None, **kwargs):  # pylint: disable=W0613
    """
    Version-lock packages

    .. note::
        This function is provided primarily for compatibility with some
        parts of :py:mod:`states.pkg <salt.states.pkg>`.
        Consider using Consider using :py:func:`pkg.lock <salt.modules.pkgng.lock>` instead. instead.

    name
        The name of the package to be held.

    Multiple Package Options:

    pkgs
        A list of packages to hold. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.hold <package name>
        salt '*' pkg.hold pkgs='["foo", "bar"]'
    """
    targets = []
    if pkgs:
        targets.extend(pkgs)
    else:
        targets.append(name)

    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target.keys()))

        ret[target] = {"name": target, "changes": {}, "result": False, "comment": ""}

        if not locked(target, **kwargs):
            if "test" in __opts__ and __opts__["test"]:
                ret[target].update(result=None)
                ret[target]["comment"] = f"Package {target} is set to be held."
            else:
                if lock(target, **kwargs):
                    ret[target].update(result=True)
                    ret[target]["comment"] = "Package {} is now being held.".format(
                        target
                    )
                    ret[target]["changes"]["new"] = "hold"
                    ret[target]["changes"]["old"] = ""
                else:
                    ret[target]["comment"] = "Package {} was unable to be held.".format(
                        target
                    )
        else:
            ret[target].update(result=True)
            ret[target]["comment"] = "Package {} is already set to be held.".format(
                target
            )
    return ret


def unhold(name=None, pkgs=None, **kwargs):  # pylint: disable=W0613
    """
    Remove version locks

    .. note::
        This function is provided primarily for compatibility with some parts of
        :py:mod:`states.pkg <salt.states.pkg>`.  Consider using
        :py:func:`pkg.unlock <salt.modules.pkgng.unlock>` instead.

    name
        The name of the package to be unheld

    Multiple Package Options:

    pkgs
        A list of packages to unhold. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.unhold <package name>
        salt '*' pkg.unhold pkgs='["foo", "bar"]'
    """
    targets = []
    if pkgs:
        targets.extend(pkgs)
    else:
        targets.append(name)

    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target.keys()))

        ret[target] = {"name": target, "changes": {}, "result": False, "comment": ""}

        if locked(target, **kwargs):
            if __opts__["test"]:
                ret[target].update(result=None)
                ret[target]["comment"] = "Package {} is set to be unheld.".format(
                    target
                )
            else:
                if unlock(target, **kwargs):
                    ret[target].update(result=True)
                    ret[target]["comment"] = "Package {} is no longer held.".format(
                        target
                    )
                    ret[target]["changes"]["new"] = ""
                    ret[target]["changes"]["old"] = "hold"
                else:
                    ret[target][
                        "comment"
                    ] = f"Package {target} was unable to be unheld."
        else:
            ret[target].update(result=True)
            ret[target]["comment"] = f"Package {target} is not being held."
    return ret


def list_locked(**kwargs):
    """
    Query the package database those packages which are
    locked against reinstallation, modification or deletion.

    Returns returns a list of package names with version strings

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_locked

    jail
        List locked packages within the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.list_locked jail=<jail name or id>

    chroot
        List locked packages within the specified chroot (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.list_locked chroot=/path/to/chroot

    root
        List locked packages within the specified root (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.list_locked root=/path/to/chroot

    """
    return [
        f"{pkgname}-{version(pkgname, **kwargs)}"
        for pkgname in _lockcmd("lock", name=None, **kwargs)
    ]


def locked(name, **kwargs):
    """
    Query the package database to determine if the named package
    is locked against reinstallation, modification or deletion.

    Returns True if the named package is locked, False otherwise.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.locked <package name>

    jail
        Test if a package is locked within the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.locked <package name> jail=<jail name or id>

    chroot
        Test if a package is locked within the specified chroot (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.locked <package name> chroot=/path/to/chroot

    root
        Test if a package is locked within the specified root (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.locked <package name> root=/path/to/chroot

    """
    if name in _lockcmd("lock", name=None, **kwargs):
        return True

    return False


def lock(name, **kwargs):
    """
    Lock the named package against reinstallation, modification or deletion.

    Returns True if the named package was successfully locked.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.lock <package name>

    jail
        Lock packages within the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.lock <package name> jail=<jail name or id>

    chroot
        Lock packages within the specified chroot (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.lock <package name> chroot=/path/to/chroot

    root
        Lock packages within the specified root (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.lock <package name> root=/path/to/chroot

    """
    if name in _lockcmd("lock", name, **kwargs):
        return True

    return False


def unlock(name, **kwargs):
    """
    Unlock the named package against reinstallation, modification or deletion.

    Returns True if the named package was successfully unlocked.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.unlock <package name>

    jail
        Unlock packages within the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.unlock <package name> jail=<jail name or id>

    chroot
        Unlock packages within the specified chroot (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.unlock <package name> chroot=/path/to/chroot

    root
        Unlock packages within the specified root (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.unlock <package name> root=/path/to/chroot

    """
    if name in _lockcmd("unlock", name, **kwargs):
        return False

    return True


def _lockcmd(subcmd, pkgname=None, **kwargs):
    """
    Helper function for lock and unlock commands, because their syntax is identical.

    Run the lock/unlock command, and return a list of locked packages
    """

    jail = kwargs.pop("jail", None)
    chroot = kwargs.pop("chroot", None)
    root = kwargs.pop("root", None)

    locked_pkgs = []

    cmd = _pkg(jail, chroot, root)
    cmd.append(subcmd)
    cmd.append("-y")
    cmd.append("--quiet")
    cmd.append("--show-locked")

    if pkgname:
        cmd.append(pkgname)

    out = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    if out["retcode"] != 0:
        raise CommandExecutionError(
            f"Problem encountered {subcmd}ing packages", info={"result": out}
        )

    for line in salt.utils.itertools.split(out["stdout"], "\n"):
        if not line:
            continue
        try:
            pkgname = line.rsplit("-", 1)[0]
        except ValueError:
            continue
        locked_pkgs.append(pkgname)

    log.debug("Locked packages: %s", ", ".join(locked_pkgs))
    return locked_pkgs


def list_upgrades(refresh=True, **kwargs):
    """
    List those packages for which an upgrade is available

    The ``fromrepo`` argument is also supported, as used in pkg states.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades

    jail
        List upgrades within the specified jail

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.list_upgrades jail=<jail name or id>

    chroot
        List upgrades within the specified chroot (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.list_upgrades chroot=/path/to/chroot

    root
        List upgrades within the specified root (ignored if ``jail`` is
        specified)

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.list_upgrades root=/path/to/chroot

    """
    jail = kwargs.pop("jail", None)
    chroot = kwargs.pop("chroot", None)
    root = kwargs.pop("root", None)
    fromrepo = kwargs.pop("fromrepo", None)

    cmd = _pkg(jail, chroot, root)
    cmd.extend(["upgrade", "--dry-run", "--quiet"])

    if not refresh:
        cmd.append("--no-repo-update")
    if fromrepo:
        cmd.extend(["--repository", fromrepo])

    out = __salt__["cmd.run_stdout"](
        cmd, output_loglevel="trace", python_shell=False, ignore_retcode=True
    )

    return {
        pkgname: pkgstat["version"]["new"]
        for pkgname, pkgstat in _parse_upgrade(out)["upgrade"].items()
    }


def _parse_upgrade(stdout):
    """
    Parse the output from the ``pkg upgrade --dry-run`` command

    Returns a dictionary of the expected actions:

    .. code-block:: yaml

        'upgrade':
          pkgname:
            'repo': repository
            'reason': reason
            'version':
              'current': n.n.n
              'new': n.n.n
        'install':
          pkgname:
            'repo': repository
            'reason': reason
            'version':
              'current': n.n.n
        'reinstall':
          pkgname:
            'repo': repository
            'reason': reason
            'version':
              'current': n.n.n
        'downgrade':
          pkgname:
            'repo': repository
            'reason': reason
            'version':
              'current': n.n.n
              'new': n.n.n
        'remove':
          pkgname:
            'repo': repository
            'reason': reason
            'version':
              'current': n.n.n
    """
    # Match strings like 'python36: 3.6.3 -> 3.6.4 [FreeBSD]'
    upgrade_regex = re.compile(
        r"^\s+([^:]+):\s([0-9a-z_,.]+)\s+->\s+([0-9a-z_,.]+)\s*(\[([^]]+)\])?\s*(\(([^)]+)\))?"
    )
    # Match strings like 'rubygem-bcrypt_pbkdf: 1.0.0 [FreeBSD]'
    install_regex = re.compile(
        r"^\s+([^:]+):\s+([0-9a-z_,.]+)\s*(\[([^]]+)\])?\s*(\(([^)]+)\))?"
    )
    # Match strings like 'py27-yaml-3.11_2 [FreeBSD] (direct dependency changed: py27-setuptools)'
    reinstall_regex = re.compile(
        r"^\s+(\S+)-(?<=-)([0-9a-z_,.]+)\s*(\[([^]]+)\])?\s*(\(([^)]+)\))?"
    )

    result = {
        "upgrade": {},
        "install": {},
        "reinstall": {},
        "remove": {},
        "downgrade": {},
    }
    action = None
    for line in salt.utils.itertools.split(stdout, "\n"):

        if not line:
            action = None
            continue

        if line == "Installed packages to be UPGRADED:":
            action = "upgrade"
            continue

        if line == "New packages to be INSTALLED:":
            action = "install"
            continue

        if line == "Installed packages to be REINSTALLED:":
            action = "reinstall"
            continue

        if line == "Installed packages to be REMOVED:":
            action = "remove"
            continue

        if line == "Installed packages to be DOWNGRADED:":
            action = "downgrade"
            continue

        if action == "upgrade" or action == "downgrade":
            match = upgrade_regex.match(line)
            if match:
                result[action][match.group(1)] = {
                    "version": {"current": match.group(2), "new": match.group(3)},
                    "repo": match.group(5),
                    "reason": match.group(7),
                }
            else:
                log.error("Unable to parse %s: '%s'", action, line)

        if action == "install":
            match = install_regex.match(line)
            if match:
                result[action][match.group(1)] = {
                    "version": {"current": match.group(2)},
                    "repo": match.group(4),
                    "reason": match.group(6),
                }
            else:
                log.error("Unable to parse %s: '%s'", action, line)

        if (action == "reinstall") or (action == "remove"):
            match = reinstall_regex.match(line)
            if match:
                result[action][match.group(1)] = {
                    "version": {"current": match.group(2)},
                    "repo": match.group(4),
                    "reason": match.group(6),
                }
            else:
                log.error("Unable to parse %s: '%s'", action, line)

    return result


def version_cmp(pkg1, pkg2, ignore_epoch=False, **kwargs):
    """
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '2.1.11' '2.1.12'
    """
    del ignore_epoch  # Unused parameter

    # Don't worry about ignore_epoch since we're shelling out to pkg.
    sym = {
        "<": -1,
        ">": 1,
        "=": 0,
    }
    try:
        cmd = ["pkg", "version", "--test-version", pkg1, pkg2]
        ret = __salt__["cmd.run_all"](
            cmd, output_loglevel="trace", python_shell=False, ignore_retcode=True
        )
        if ret["stdout"] in sym:
            return sym[ret["stdout"]]

    except Exception as exc:  # pylint: disable=broad-except
        log.error(exc)

    return None
