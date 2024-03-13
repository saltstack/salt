"""
Package support for Solaris

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
import salt.utils.files
import salt.utils.functools
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, MinionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Set the virtual pkg module if the os is Solaris
    """
    if (
        __grains__["os_family"] == "Solaris"
        and float(__grains__["kernelrelease"]) <= 5.10
    ):
        return __virtualname__
    return (
        False,
        "The solarispkg execution module failed to load: only available "
        "on Solaris <= 10.",
    )


def _write_adminfile(kwargs):
    """
    Create a temporary adminfile based on the keyword arguments passed to
    pkg.install.
    """
    # Set the adminfile default variables
    email = kwargs.get("email", "")
    instance = kwargs.get("instance", "quit")
    partial = kwargs.get("partial", "nocheck")
    runlevel = kwargs.get("runlevel", "nocheck")
    idepend = kwargs.get("idepend", "nocheck")
    rdepend = kwargs.get("rdepend", "nocheck")
    space = kwargs.get("space", "nocheck")
    setuid = kwargs.get("setuid", "nocheck")
    conflict = kwargs.get("conflict", "nocheck")
    action = kwargs.get("action", "nocheck")
    basedir = kwargs.get("basedir", "default")

    # Make tempfile to hold the adminfile contents.
    adminfile = salt.utils.files.mkstemp(prefix="salt-")

    def _write_line(fp_, line):
        fp_.write(salt.utils.stringutils.to_str(line))

    with salt.utils.files.fopen(adminfile, "w") as fp_:
        _write_line(fp_, f"email={email}\n")
        _write_line(fp_, f"instance={instance}\n")
        _write_line(fp_, f"partial={partial}\n")
        _write_line(fp_, f"runlevel={runlevel}\n")
        _write_line(fp_, f"idepend={idepend}\n")
        _write_line(fp_, f"rdepend={rdepend}\n")
        _write_line(fp_, f"space={space}\n")
        _write_line(fp_, f"setuid={setuid}\n")
        _write_line(fp_, f"conflict={conflict}\n")
        _write_line(fp_, f"action={action}\n")
        _write_line(fp_, f"basedir={basedir}\n")

    return adminfile


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
    List the packages currently installed as a dict:

    .. code-block:: python

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
    cmd = "/usr/bin/pkginfo -x"

    # Package information returned two lines per package. On even-offset
    # lines, the package name is in the first column. On odd-offset lines, the
    # package version is in the second column.
    lines = __salt__["cmd.run"](
        cmd, output_loglevel="trace", python_shell=False
    ).splitlines()
    for index, line in enumerate(lines):
        if index % 2 == 0:
            name = line.split()[0].strip()
        if index % 2 == 1:
            version_num = line.split()[1].strip()
            __salt__["pkg_resource.add_pkg"](ret, name, version_num)

    __salt__["pkg_resource.sort_pkglist"](ret)
    __context__["pkg.list_pkgs"] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__["pkg_resource.stringify"](ret)
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

    NOTE: As package repositories are not presently supported for Solaris
    pkgadd, this function will always return an empty string for a given
    package.
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


def upgrade_available(name, **kwargs):
    """
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    """
    return latest_version(name) != ""


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


def install(name=None, sources=None, saltenv="base", **kwargs):
    """
    Install the passed package. Can install packages from the following
    sources:

    * Locally (package already exists on the minion
    * HTTP/HTTPS server
    * FTP server
    * Salt master

    Returns a dict containing the new package names and versions:

    .. code-block:: python

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Examples:

    .. code-block:: bash

        # Installing a data stream pkg that already exists on the minion

        salt '*' pkg.install sources='[{"<pkg name>": "/dir/on/minion/<pkg filename>"}]'
        salt '*' pkg.install sources='[{"SMClgcc346": "/var/spool/pkg/gcc-3.4.6-sol10-sparc-local.pkg"}]'

        # Installing a data stream pkg that exists on the salt master

        salt '*' pkg.install sources='[{"<pkg name>": "salt://pkgs/<pkg filename>"}]'
        salt '*' pkg.install sources='[{"SMClgcc346": "salt://pkgs/gcc-3.4.6-sol10-sparc-local.pkg"}]'

    CLI Example:

    .. code-block:: bash

        # Installing a data stream pkg that exists on a HTTP server
        salt '*' pkg.install sources='[{"<pkg name>": "http://packages.server.com/<pkg filename>"}]'
        salt '*' pkg.install sources='[{"SMClgcc346": "http://packages.server.com/gcc-3.4.6-sol10-sparc-local.pkg"}]'

    If working with solaris zones and you want to install a package only in the
    global zone you can pass 'current_zone_only=True' to salt to have the
    package only installed in the global zone. (Behind the scenes this is
    passing '-G' to the pkgadd command.) Solaris default when installing a
    package in the global zone is to install it in all zones. This overrides
    that and installs the package only in the global.

    CLI Example:

    .. code-block:: bash

        # Installing a data stream package only in the global zone:
        salt 'global_zone' pkg.install sources='[{"SMClgcc346": "/var/spool/pkg/gcc-3.4.6-sol10-sparc-local.pkg"}]' current_zone_only=True

    By default salt automatically provides an adminfile, to automate package
    installation, with these options set::

        email=
        instance=quit
        partial=nocheck
        runlevel=nocheck
        idepend=nocheck
        rdepend=nocheck
        space=nocheck
        setuid=nocheck
        conflict=nocheck
        action=nocheck
        basedir=default

    You can override any of these options in two ways. First you can optionally
    pass any of the options as a kwarg to the module/state to override the
    default value or you can optionally pass the 'admin_source' option
    providing your own adminfile to the minions.

    Note: You can find all of the possible options to provide to the adminfile
    by reading the admin man page:

    .. code-block:: bash

        man -s 4 admin

    CLI Example:

    .. code-block:: bash

        # Overriding the 'instance' adminfile option when calling the module directly
        salt '*' pkg.install sources='[{"<pkg name>": "salt://pkgs/<pkg filename>"}]' instance="overwrite"

    SLS Example:

    .. code-block:: yaml

        # Overriding the 'instance' adminfile option when used in a state

        SMClgcc346:
          pkg.installed:
            - sources:
              - SMClgcc346: salt://srv/salt/pkgs/gcc-3.4.6-sol10-sparc-local.pkg
            - instance: overwrite

    .. note::
        The ID declaration is ignored, as the package name is read from the
        ``sources`` parameter.

    CLI Example:

    .. code-block:: bash

        # Providing your own adminfile when calling the module directly

        salt '*' pkg.install sources='[{"<pkg name>": "salt://pkgs/<pkg filename>"}]' admin_source='salt://pkgs/<adminfile filename>'

        # Providing your own adminfile when using states

        <pkg name>:
          pkg.installed:
            - sources:
              - <pkg name>: salt://pkgs/<pkg filename>
            - admin_source: salt://pkgs/<adminfile filename>

    .. note::
        The ID declaration is ignored, as the package name is read from the
        ``sources`` parameter.
    """
    if salt.utils.data.is_true(kwargs.get("refresh")):
        log.warning("'refresh' argument not implemented for solarispkg module")

    # pkgs is not supported, but must be passed here for API compatibility
    pkgs = kwargs.pop("pkgs", None)
    try:
        pkg_params, pkg_type = __salt__["pkg_resource.parse_targets"](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if not pkg_params:
        return {}

    if not sources:
        log.error('"sources" param required for solaris pkg_add installs')
        return {}

    try:
        if "admin_source" in kwargs:
            adminfile = __salt__["cp.cache_file"](kwargs["admin_source"], saltenv)
        else:
            adminfile = _write_adminfile(kwargs)

        old = list_pkgs()
        cmd_prefix = ["/usr/sbin/pkgadd", "-n", "-a", adminfile]

        # Only makes sense in a global zone but works fine in non-globals.
        if kwargs.get("current_zone_only") in (True, "True"):
            cmd_prefix.append("-G ")

        errors = []
        for pkg in pkg_params:
            cmd = cmd_prefix + ["-d", pkg, "all"]
            # Install the package{s}
            out = __salt__["cmd.run_all"](
                cmd, output_loglevel="trace", python_shell=False
            )

            if out["retcode"] != 0 and out["stderr"]:
                errors.append(out["stderr"])

        __context__.pop("pkg.list_pkgs", None)
        new = list_pkgs()
        ret = salt.utils.data.compare_dicts(old, new)

        if errors:
            raise CommandExecutionError(
                "Problem encountered installing package(s)",
                info={"errors": errors, "changes": ret},
            )
    finally:
        # Remove the temp adminfile
        if "admin_source" not in kwargs:
            try:
                os.remove(adminfile)
            except (NameError, OSError):
                pass

    return ret


def remove(name=None, pkgs=None, saltenv="base", **kwargs):
    """
    Remove packages with pkgrm

    name
        The name of the package to be deleted

    By default salt automatically provides an adminfile, to automate package
    removal, with these options set::

        email=
        instance=quit
        partial=nocheck
        runlevel=nocheck
        idepend=nocheck
        rdepend=nocheck
        space=nocheck
        setuid=nocheck
        conflict=nocheck
        action=nocheck
        basedir=default

    You can override any of these options in two ways. First you can optionally
    pass any of the options as a kwarg to the module/state to override the
    default value or you can optionally pass the 'admin_source' option
    providing your own adminfile to the minions.

    Note: You can find all of the possible options to provide to the adminfile
    by reading the admin man page:

    .. code-block:: bash

        man -s 4 admin


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove SUNWgit
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    """
    try:
        pkg_params = __salt__["pkg_resource.parse_targets"](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    try:
        if "admin_source" in kwargs:
            adminfile = __salt__["cp.cache_file"](kwargs["admin_source"], saltenv)
        else:
            # Make tempfile to hold the adminfile contents.
            adminfile = _write_adminfile(kwargs)

        # Remove the package
        cmd = ["/usr/sbin/pkgrm", "-n", "-a", adminfile] + targets
        out = __salt__["cmd.run_all"](cmd, python_shell=False, output_loglevel="trace")

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
    finally:
        # Remove the temp adminfile
        if "admin_source" not in kwargs:
            try:
                os.remove(adminfile)
            except (NameError, OSError):
                pass

    return ret


def purge(name=None, pkgs=None, **kwargs):
    """
    Package purges are not supported, this function is identical to
    ``remove()``.

    name
        The name of the package to be deleted


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
    return remove(name=name, pkgs=pkgs, **kwargs)
