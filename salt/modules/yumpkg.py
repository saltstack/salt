"""
Support for YUM/DNF

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.

.. note::
    DNF is fully supported as of version 2015.5.10 and 2015.8.4 (partial
    support for DNF was initially added in 2015.8.0), and DNF is used
    automatically in place of YUM in Fedora 22 and newer.

.. versionadded:: 3003
    Support for ``tdnf`` on Photon OS.
"""


import configparser
import contextlib
import datetime
import fnmatch
import itertools
import logging
import os
import re
import string

import salt.utils.args
import salt.utils.data
import salt.utils.decorators.path
import salt.utils.environment
import salt.utils.files
import salt.utils.functools
import salt.utils.itertools
import salt.utils.lazy
import salt.utils.path
import salt.utils.pkg
import salt.utils.pkg.rpm
import salt.utils.systemd
import salt.utils.versions
from salt.exceptions import CommandExecutionError, MinionError, SaltInvocationError
from salt.utils.versions import LooseVersion as _LooseVersion

try:
    import yum

    HAS_YUM = True
except ImportError:
    HAS_YUM = False


log = logging.getLogger(__name__)

__HOLD_PATTERN = r"[\w+]+(?:[.-][^-]+)*"

PKG_ARCH_SEPARATOR = "."

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Confine this module to yum based systems
    """
    if __opts__.get("yum_provider") == "yumpkg_api":
        return (False, "Module yumpkg: yumpkg_api provider not available")
    try:
        os_grain = __grains__["os"].lower()
        os_family = __grains__["os_family"].lower()
    except Exception:  # pylint: disable=broad-except
        return (False, "Module yumpkg: no yum based system detected")

    enabled = ("amazon", "xcp", "xenserver", "virtuozzolinux", "virtuozzo")
    if os_family == "redhat" or os_grain in enabled:
        if _yum() is None:
            return (False, "DNF nor YUM found")
        return __virtualname__
    return (False, "Module yumpkg: no yum based system detected")


def _strip_headers(output, *args):
    if not args:
        args_lc = (
            "installed packages",
            "available packages",
            "available upgrades",
            "updated packages",
            "upgraded packages",
        )
    else:
        args_lc = [x.lower() for x in args]
    ret = ""
    for line in salt.utils.itertools.split(output, "\n"):
        if line.lower() not in args_lc:
            ret += line + "\n"
    return ret


def _get_copr_repo(copr):
    copr = copr.split(":", 1)[1]
    copr = copr.split("/", 1)
    return "copr:copr.fedorainfracloud.org:{}:{}".format(copr[0], copr[1])


def _get_hold(line, pattern=__HOLD_PATTERN, full=True):
    """
    Resolve a package name from a line containing the hold expression. If the
    regex is not matched, None is returned.

    yum ==> 2:vim-enhanced-7.4.629-5.el6.*
    dnf ==> vim-enhanced-2:7.4.827-1.fc22.*
    """
    if full:
        if _yum() == "dnf":
            lock_re = r"({}-\S+)".format(pattern)
        else:
            lock_re = r"(\d+:{}-\S+)".format(pattern)
    else:
        if _yum() == "dnf":
            lock_re = r"({}-\S+)".format(pattern)
        else:
            lock_re = r"\d+:({}-\S+)".format(pattern)

    match = re.search(lock_re, line)
    if match:
        if not full:
            woarch = match.group(1).rsplit(".", 1)[0]
            worel = woarch.rsplit("-", 1)[0]
            return worel.rsplit("-", 1)[0]
        else:
            return match.group(1)
    return None


def _yum():
    """
    Determine package manager name (yum or dnf),
    depending on the executable existence in $PATH.
    """

    # Do import due to function clonning to kernelpkg_linux_yum mod
    import os

    def _check(file):
        return (
            os.path.exists(file)
            and os.access(file, os.F_OK | os.X_OK)
            and not os.path.isdir(file)
        )

    # allow calling function outside execution module
    try:
        context = __context__
    except NameError:
        context = {}

    contextkey = "yum_bin"
    if contextkey not in context:
        for dir in os.environ.get("PATH", os.defpath).split(os.pathsep):
            if _check(os.path.join(dir, "dnf")):
                context[contextkey] = "dnf"
                break
            elif _check(os.path.join(dir, "yum")):
                context[contextkey] = "yum"
                break
            elif _check(os.path.join(dir, "tdnf")):
                context[contextkey] = "tdnf"
                break
    return context.get(contextkey)


def _call_yum(args, **kwargs):
    """
    Call yum/dnf.
    """
    params = {
        "output_loglevel": "trace",
        "python_shell": False,
        "env": salt.utils.environment.get_module_environment(globals()),
    }
    params.update(kwargs)
    cmd = []
    if salt.utils.systemd.has_scope(__context__) and __salt__["config.get"](
        "systemd.scope", True
    ):
        cmd.extend(["systemd-run", "--scope"])
    cmd.append(_yum())
    cmd.extend(args)

    return __salt__["cmd.run_all"](cmd, **params)


def _yum_pkginfo(output):
    """
    Parse yum/dnf output (which could contain irregular line breaks if package
    names are long) retrieving the name, version, etc., and return a list of
    pkginfo namedtuples.
    """
    cur = {}
    keys = itertools.cycle(("name", "version", "repoid"))
    values = salt.utils.itertools.split(_strip_headers(output))
    osarch = __grains__["osarch"]
    for (key, value) in zip(keys, values):
        if key == "name":
            try:
                cur["name"], cur["arch"] = value.rsplit(".", 1)
            except ValueError:
                cur["name"] = value
                cur["arch"] = osarch
            cur["name"] = salt.utils.pkg.rpm.resolve_name(
                cur["name"], cur["arch"], osarch
            )
        else:
            if key == "version":
                # Suppport packages with no 'Release' parameter
                value = value.rstrip("-")
            elif key == "repoid":
                # Installed packages show a '@' at the beginning
                value = value.lstrip("@")
            cur[key] = value
            if key == "repoid":
                # We're done with this package, create the pkginfo namedtuple
                pkginfo = salt.utils.pkg.rpm.pkginfo(**cur)
                # Clear the dict for the next package
                cur = {}
                # Yield the namedtuple
                if pkginfo is not None:
                    yield pkginfo


def _versionlock_pkg(grains=None):
    """
    Determine versionlock plugin package name
    """
    if grains is None:
        grains = __grains__
    if _yum() == "dnf":
        if grains["os"].lower() == "fedora":
            return (
                "python3-dnf-plugin-versionlock"
                if int(grains.get("osrelease")) >= 26
                else "python3-dnf-plugins-extras-versionlock"
            )
        if int(grains.get("osmajorrelease")) >= 8:
            return "python3-dnf-plugin-versionlock"
        return "python2-dnf-plugin-versionlock"
    elif _yum() == "tdnf":
        raise SaltInvocationError("Cannot proceed, no versionlock for tdnf")
    else:
        return (
            "yum-versionlock"
            if int(grains.get("osmajorrelease")) == 5
            else "yum-plugin-versionlock"
        )


def _check_versionlock():
    """
    Ensure that the appropriate versionlock plugin is present
    """
    vl_plugin = _versionlock_pkg()
    if vl_plugin not in list_pkgs():
        raise SaltInvocationError(
            "Cannot proceed, {} is not installed.".format(vl_plugin)
        )


def _get_options(**kwargs):
    """
    Returns a list of options to be used in the yum/dnf command, based on the
    kwargs passed.
    """
    # Get repo options from the kwargs
    fromrepo = kwargs.pop("fromrepo", "")
    repo = kwargs.pop("repo", "")
    disablerepo = kwargs.pop("disablerepo", "")
    enablerepo = kwargs.pop("enablerepo", "")
    disableexcludes = kwargs.pop("disableexcludes", "")
    branch = kwargs.pop("branch", "")
    setopt = kwargs.pop("setopt", None)
    if setopt is None:
        setopt = []
    else:
        setopt = salt.utils.args.split_input(setopt)
    get_extra_options = kwargs.pop("get_extra_options", False)

    # Support old 'repo' argument
    if repo and not fromrepo:
        fromrepo = repo

    ret = []

    if fromrepo:
        log.info("Restricting to repo '%s'", fromrepo)
        ret.extend(["--disablerepo=*", "--enablerepo={}".format(fromrepo)])
    else:
        if disablerepo:
            targets = (
                [disablerepo] if not isinstance(disablerepo, list) else disablerepo
            )
            log.info("Disabling repo(s): %s", ", ".join(targets))
            ret.extend(["--disablerepo={}".format(x) for x in targets])
        if enablerepo:
            targets = [enablerepo] if not isinstance(enablerepo, list) else enablerepo
            log.info("Enabling repo(s): %s", ", ".join(targets))
            ret.extend(["--enablerepo={}".format(x) for x in targets])

    if disableexcludes:
        log.info("Disabling excludes for '%s'", disableexcludes)
        ret.append("--disableexcludes={}".format(disableexcludes))

    if branch:
        log.info("Adding branch '%s'", branch)
        ret.append("--branch={}".format(branch))

    for item in setopt:
        ret.extend(["--setopt", str(item)])

    if get_extra_options:
        # sorting here to make order uniform, makes unit testing more reliable
        for key in sorted(kwargs):
            if key.startswith("__"):
                continue
            value = kwargs[key]
            if isinstance(value, str):
                log.info("Found extra option --%s=%s", key, value)
                ret.append("--{}={}".format(key, value))
            elif value is True:
                log.info("Found extra option --%s", key)
                ret.append("--{}".format(key))
        if ret:
            log.info("Adding extra options: %s", ret)

    return ret


def _get_yum_config():
    """
    Returns a dict representing the yum config options and values.

    We try to pull all of the yum config options into a standard dict object.
    This is currently only used to get the reposdir settings, but could be used
    for other things if needed.

    If the yum python library is available, use that, which will give us all of
    the options, including all of the defaults not specified in the yum config.
    Additionally, they will all be of the correct object type.

    If the yum library is not available, we try to read the yum.conf
    directly ourselves with a minimal set of "defaults".
    """
    # in case of any non-fatal failures, these defaults will be used
    conf = {
        "reposdir": ["/etc/yum/repos.d", "/etc/yum.repos.d"],
    }

    if HAS_YUM:
        try:
            yb = yum.YumBase()
            yb.preconf.init_plugins = False
            for name, value in yb.conf.items():
                conf[name] = value
        except (AttributeError, yum.Errors.ConfigError) as exc:
            raise CommandExecutionError("Could not query yum config: {}".format(exc))
        except yum.Errors.YumBaseError as yum_base_error:
            raise CommandExecutionError(
                "Error accessing yum or rpmdb: {}".format(yum_base_error)
            )
    else:
        # fall back to parsing the config ourselves
        # Look for the config the same order yum does
        fn = None
        paths = (
            "/etc/yum/yum.conf",
            "/etc/yum.conf",
            "/etc/dnf/dnf.conf",
            "/etc/tdnf/tdnf.conf",
        )
        for path in paths:
            if os.path.exists(path):
                fn = path
                break

        if not fn:
            raise CommandExecutionError(
                "No suitable yum config file found in: {}".format(paths)
            )

        cp = configparser.ConfigParser()
        try:
            cp.read(fn)
        except OSError as exc:
            raise CommandExecutionError("Unable to read from {}: {}".format(fn, exc))

        if cp.has_section("main"):
            for opt in cp.options("main"):
                if opt in ("reposdir", "commands", "excludes"):
                    # these options are expected to be lists
                    conf[opt] = [x.strip() for x in cp.get("main", opt).split(",")]
                else:
                    conf[opt] = cp.get("main", opt)
        else:
            log.warning(
                "Could not find [main] section in %s, using internal " "defaults", fn
            )

    return conf


def _get_yum_config_value(name):
    """
    Look for a specific config variable and return its value
    """
    conf = _get_yum_config()
    if name in conf.keys():
        return conf.get(name)
    return None


def _normalize_basedir(basedir=None):
    """
    Takes a basedir argument as a string or a list. If the string or list is
    empty, then look up the default from the 'reposdir' option in the yum
    config.

    Returns a list of directories.
    """
    # if we are passed a string (for backward compatibility), convert to a list
    if isinstance(basedir, str):
        basedir = [x.strip() for x in basedir.split(",")]

    if basedir is None:
        basedir = []

    # nothing specified, so use the reposdir option as the default
    if not basedir:
        basedir = _get_yum_config_value("reposdir")

    if not isinstance(basedir, list) or not basedir:
        raise SaltInvocationError("Could not determine any repo directories")

    return basedir


def normalize_name(name):
    """
    Strips the architecture from the specified package name, if necessary.
    Circumstances where this would be done include:

    * If the arch is 32 bit and the package name ends in a 32-bit arch.
    * If the arch matches the OS arch, or is ``noarch``.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.normalize_name zsh.x86_64
    """
    try:
        arch = name.rsplit(PKG_ARCH_SEPARATOR, 1)[-1]
        if arch not in salt.utils.pkg.rpm.ARCHES + ("noarch",):
            return name
    except ValueError:
        return name
    if arch in (__grains__["osarch"], "noarch") or salt.utils.pkg.rpm.check_32(
        arch, osarch=__grains__["osarch"]
    ):
        return name[: -(len(arch) + 1)]
    return name


def parse_arch(name):
    """
    Parse name and architecture from the specified package name.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.parse_arch zsh.x86_64
    """
    _name, _arch = None, None
    try:
        _name, _arch = name.rsplit(PKG_ARCH_SEPARATOR, 1)
    except ValueError:
        pass
    if _arch not in salt.utils.pkg.rpm.ARCHES + ("noarch",):
        _name = name
        _arch = None
    return {"name": _name, "arch": _arch}


def latest_version(*names, **kwargs):
    """
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    A specific repo can be requested using the ``fromrepo`` keyword argument,
    and the ``disableexcludes`` option is also supported.

    .. versionadded:: 2014.7.0
        Support for the ``disableexcludes`` option

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package name> fromrepo=epel-testing
        salt '*' pkg.latest_version <package name> disableexcludes=main
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    """
    refresh = salt.utils.data.is_true(kwargs.pop("refresh", True))
    if len(names) == 0:
        return ""

    options = _get_options(**kwargs)

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db(**kwargs)

    cur_pkgs = list_pkgs(versions_as_list=True)

    # Get available versions for specified package(s)
    cmd = ["--quiet"]
    cmd.extend(options)
    cmd.extend(["list", "available"])
    cmd.extend(names)
    out = _call_yum(cmd, ignore_retcode=True)
    if out["retcode"] != 0:
        if out["stderr"]:
            # Check first if this is just a matter of the packages being
            # up-to-date.
            if not all([x in cur_pkgs for x in names]):
                log.error(
                    "Problem encountered getting latest version for the "
                    "following package(s): %s. Stderr follows: \n%s",
                    ", ".join(names),
                    out["stderr"],
                )
        updates = []
    else:
        # Sort by version number (highest to lowest) for loop below
        updates = sorted(
            _yum_pkginfo(out["stdout"]),
            key=lambda pkginfo: _LooseVersion(pkginfo.version),
            reverse=True,
        )

    def _check_cur(pkg):
        if pkg.name in cur_pkgs:
            for installed_version in cur_pkgs[pkg.name]:
                # If any installed version is greater than (or equal to) the
                # one found by yum/dnf list available, then it is not an
                # upgrade.
                if salt.utils.versions.compare(
                    ver1=installed_version,
                    oper=">=",
                    ver2=pkg.version,
                    cmp_func=version_cmp,
                ):
                    return False
            # pkg.version is greater than all installed versions
            return True
        else:
            # Package is not installed
            return True

    ret = {}
    for name in names:
        # Derive desired pkg arch (for arch-specific packages) based on the
        # package name(s) passed to the function. On a 64-bit OS, "pkgame"
        # would be assumed to match the osarch, while "pkgname.i686" would
        # have an arch of "i686". This desired arch is then compared against
        # the updates derived from _yum_pkginfo() above, so that we can
        # distinguish an update for a 32-bit version of a package from its
        # 64-bit counterpart.
        try:
            arch = name.rsplit(".", 1)[-1]
            if arch not in salt.utils.pkg.rpm.ARCHES:
                arch = __grains__["osarch"]
        except ValueError:
            arch = __grains__["osarch"]

        # This loop will iterate over the updates derived by _yum_pkginfo()
        # above, which have been sorted descendingly by version number,
        # ensuring that the latest available version for the named package is
        # examined first. The call to _check_cur() will ensure that a package
        # seen by yum as "available" will only be detected as an upgrade if it
        # has a version higher than all currently-installed versions of the
        # package.
        for pkg in (x for x in updates if x.name == name):
            # This if/or statement makes sure that we account for noarch
            # packages as well as arch-specific packages.
            if (
                pkg.arch == "noarch"
                or pkg.arch == arch
                or salt.utils.pkg.rpm.check_32(pkg.arch)
            ):
                if _check_cur(pkg):
                    ret[name] = pkg.version
                    # no need to check another match, if there was one
                    break
        else:
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
    return latest_version(name, **kwargs) != ""


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


def version_cmp(pkg1, pkg2, ignore_epoch=False, **kwargs):
    """
    .. versionadded:: 2015.5.4

    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    ignore_epoch : False
        Set to ``True`` to ignore the epoch when comparing versions

        .. versionadded:: 2015.8.10,2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '0.2-001' '0.2.0.1-002'
    """

    return __salt__["lowpkg.version_cmp"](pkg1, pkg2, ignore_epoch=ignore_epoch)


def list_pkgs(versions_as_list=False, **kwargs):
    """
    List the packages currently installed as a dict. By default, the dict
    contains versions as a comma separated string::

        {'<package_name>': '<version>[,<version>...]'}

    versions_as_list:
        If set to true, the versions are provided as a list

        {'<package_name>': ['<version>', '<version>']}

    attr:
        If a list of package attributes is specified, returned value will
        contain them in addition to version, eg.::

        {'<package_name>': [{'version' : 'version', 'arch' : 'arch'}]}

        Valid attributes are: ``epoch``, ``version``, ``release``, ``arch``,
        ``install_date``, ``install_date_time_t``.

        If ``all`` is specified, all valid attributes will be returned.

            .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs attr=version,arch
        salt '*' pkg.list_pkgs attr='["version", "arch"]'
    """
    versions_as_list = salt.utils.data.is_true(versions_as_list)
    # not yet implemented or not applicable
    if any(
        [salt.utils.data.is_true(kwargs.get(x)) for x in ("removed", "purge_desired")]
    ):
        return {}

    attr = kwargs.get("attr")
    if attr is not None:
        attr = salt.utils.args.split_input(attr)

    contextkey = "pkg.list_pkgs"

    if contextkey not in __context__:
        ret = {}
        cmd = [
            "rpm",
            "-qa",
            "--queryformat",
            salt.utils.pkg.rpm.QUERYFORMAT.replace("%{REPOID}", "(none)") + "\n",
        ]
        output = __salt__["cmd.run"](cmd, python_shell=False, output_loglevel="trace")
        for line in output.splitlines():
            pkginfo = salt.utils.pkg.rpm.parse_pkginfo(
                line, osarch=__grains__["osarch"]
            )
            if pkginfo is not None:
                # see rpm version string rules available at https://goo.gl/UGKPNd
                pkgver = pkginfo.version
                epoch = None
                release = None
                if ":" in pkgver:
                    epoch, pkgver = pkgver.split(":", 1)
                if "-" in pkgver:
                    pkgver, release = pkgver.split("-", 1)
                all_attr = {
                    "epoch": epoch,
                    "version": pkgver,
                    "release": release,
                    "arch": pkginfo.arch,
                    "install_date": pkginfo.install_date,
                    "install_date_time_t": pkginfo.install_date_time_t,
                }
                __salt__["pkg_resource.add_pkg"](ret, pkginfo.name, all_attr)

        for pkgname in ret:
            ret[pkgname] = sorted(ret[pkgname], key=lambda d: d["version"])

        __context__[contextkey] = ret

    return __salt__["pkg_resource.format_pkg_list"](
        __context__[contextkey], versions_as_list, attr
    )


def list_repo_pkgs(*args, **kwargs):
    """
    .. versionadded:: 2014.1.0
    .. versionchanged:: 2014.7.0
        All available versions of each package are now returned. This required
        a slight modification to the structure of the return dict. The return
        data shown below reflects the updated return dict structure. Note that
        packages which are version-locked using :py:mod:`pkg.hold
        <salt.modules.yumpkg.hold>` will only show the currently-installed
        version, as locking a package will make other versions appear
        unavailable to yum/dnf.
    .. versionchanged:: 2017.7.0
        By default, the versions for each package are no longer organized by
        repository. To get results organized by repository, use
        ``byrepo=True``.

    Returns all available packages. Optionally, package names (and name globs)
    can be passed and the results will be filtered to packages matching those
    names. This is recommended as it speeds up the function considerably.

    .. warning::
        Running this function on RHEL/CentOS 6 and earlier will be more
        resource-intensive, as the version of yum that ships with older
        RHEL/CentOS has no yum subcommand for listing packages from a
        repository. Thus, a ``yum list installed`` and ``yum list available``
        are run, which generates a lot of output, which must then be analyzed
        to determine which package information to include in the return data.

    This function can be helpful in discovering the version or repo to specify
    in a :mod:`pkg.installed <salt.states.pkg.installed>` state.

    The return data will be a dictionary mapping package names to a list of
    version numbers, ordered from newest to oldest. If ``byrepo`` is set to
    ``True``, then the return dictionary will contain repository names at the
    top level, and each repository will map packages to lists of version
    numbers. For example:

    .. code-block:: python

        # With byrepo=False (default)
        {
            'bash': ['4.1.2-15.el6_5.2',
                     '4.1.2-15.el6_5.1',
                     '4.1.2-15.el6_4'],
            'kernel': ['2.6.32-431.29.2.el6',
                       '2.6.32-431.23.3.el6',
                       '2.6.32-431.20.5.el6',
                       '2.6.32-431.20.3.el6',
                       '2.6.32-431.17.1.el6',
                       '2.6.32-431.11.2.el6',
                       '2.6.32-431.5.1.el6',
                       '2.6.32-431.3.1.el6',
                       '2.6.32-431.1.2.0.1.el6',
                       '2.6.32-431.el6']
        }
        # With byrepo=True
        {
            'base': {
                'bash': ['4.1.2-15.el6_4'],
                'kernel': ['2.6.32-431.el6']
            },
            'updates': {
                'bash': ['4.1.2-15.el6_5.2', '4.1.2-15.el6_5.1'],
                'kernel': ['2.6.32-431.29.2.el6',
                           '2.6.32-431.23.3.el6',
                           '2.6.32-431.20.5.el6',
                           '2.6.32-431.20.3.el6',
                           '2.6.32-431.17.1.el6',
                           '2.6.32-431.11.2.el6',
                           '2.6.32-431.5.1.el6',
                           '2.6.32-431.3.1.el6',
                           '2.6.32-431.1.2.0.1.el6']
            }
        }

    fromrepo : None
        Only include results from the specified repo(s). Multiple repos can be
        specified, comma-separated.

    enablerepo (ignored if ``fromrepo`` is specified)
        Specify a disabled package repository (or repositories) to enable.
        (e.g., ``yum --enablerepo='somerepo'``)

        .. versionadded:: 2017.7.0

    disablerepo (ignored if ``fromrepo`` is specified)
        Specify an enabled package repository (or repositories) to disable.
        (e.g., ``yum --disablerepo='somerepo'``)

        .. versionadded:: 2017.7.0

    byrepo : False
        When ``True``, the return data for each package will be organized by
        repository.

        .. versionadded:: 2017.7.0

    cacheonly : False
        When ``True``, the repo information will be retrieved from the cached
        repo metadata. This is equivalent to passing the ``-C`` option to
        yum/dnf.

        .. versionadded:: 2017.7.0

    setopt
        A comma-separated or Python list of key=value options. This list will
        be expanded and ``--setopt`` prepended to each in the yum/dnf command
        that is run.

        .. versionadded:: 2019.2.0

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_repo_pkgs
        salt '*' pkg.list_repo_pkgs foo bar baz
        salt '*' pkg.list_repo_pkgs 'samba4*' fromrepo=base,updates
        salt '*' pkg.list_repo_pkgs 'python2-*' byrepo=True
    """
    byrepo = kwargs.pop("byrepo", False)
    cacheonly = kwargs.pop("cacheonly", False)
    fromrepo = kwargs.pop("fromrepo", "") or ""
    disablerepo = kwargs.pop("disablerepo", "") or ""
    enablerepo = kwargs.pop("enablerepo", "") or ""

    repo_arg = _get_options(fromrepo=fromrepo, **kwargs)

    if fromrepo and not isinstance(fromrepo, list):
        try:
            fromrepo = [x.strip() for x in fromrepo.split(",")]
        except AttributeError:
            fromrepo = [x.strip() for x in str(fromrepo).split(",")]

    if disablerepo and not isinstance(disablerepo, list):
        try:
            disablerepo = [x.strip() for x in disablerepo.split(",") if x != "*"]
        except AttributeError:
            disablerepo = [x.strip() for x in str(disablerepo).split(",") if x != "*"]

    if enablerepo and not isinstance(enablerepo, list):
        try:
            enablerepo = [x.strip() for x in enablerepo.split(",") if x != "*"]
        except AttributeError:
            enablerepo = [x.strip() for x in str(enablerepo).split(",") if x != "*"]

    if fromrepo:
        repos = fromrepo
    else:
        repos = [
            repo_name
            for repo_name, repo_info in list_repos().items()
            if repo_name in enablerepo
            or (
                repo_name not in disablerepo
                and str(repo_info.get("enabled", "1")) == "1"
            )
        ]

    ret = {}

    def _check_args(args, name):
        """
        Do glob matching on args and return True if a match was found.
        Otherwise, return False
        """
        for arg in args:
            if fnmatch.fnmatch(name, arg):
                return True
        return False

    def _parse_output(output, strict=False):
        for pkg in _yum_pkginfo(output):
            if strict and (pkg.repoid not in repos or not _check_args(args, pkg.name)):
                continue
            repo_dict = ret.setdefault(pkg.repoid, {})
            version_list = repo_dict.setdefault(pkg.name, set())
            version_list.add(pkg.version)

    yum_version = (
        None
        if _yum() != "yum"
        else _LooseVersion(
            __salt__["cmd.run"](["yum", "--version"], python_shell=False)
            .splitlines()[0]
            .strip()
        )
    )
    # Really old version of yum; does not even have --showduplicates option
    if yum_version and yum_version < _LooseVersion("3.2.13"):
        cmd_prefix = ["--quiet"]
        if cacheonly:
            cmd_prefix.append("-C")
        cmd_prefix.append("list")
        for pkg_src in ("installed", "available"):
            # Check installed packages first
            out = _call_yum(cmd_prefix + [pkg_src], ignore_retcode=True)
            if out["retcode"] == 0:
                _parse_output(out["stdout"], strict=True)
    # The --showduplicates option is added in 3.2.13, but the
    # repository-packages subcommand is only in 3.4.3 and newer
    elif yum_version and yum_version < _LooseVersion("3.4.3"):
        cmd_prefix = ["--quiet", "--showduplicates"]
        if cacheonly:
            cmd_prefix.append("-C")
        cmd_prefix.append("list")
        for pkg_src in ("installed", "available"):
            # Check installed packages first
            out = _call_yum(cmd_prefix + [pkg_src], ignore_retcode=True)
            if out["retcode"] == 0:
                _parse_output(out["stdout"], strict=True)
    else:
        for repo in repos:
            cmd = ["--quiet", "--showduplicates", "repository-packages", repo, "list"]
            if cacheonly:
                cmd.append("-C")
            # Can't concatenate because args is a tuple, using list.extend()
            cmd.extend(args)
            out = _call_yum(cmd, ignore_retcode=True)
            if out["retcode"] != 0 and "Error:" in out["stdout"]:
                continue
            _parse_output(out["stdout"])

    if byrepo:
        for reponame in ret:
            # Sort versions newest to oldest
            for pkgname in ret[reponame]:
                sorted_versions = sorted(
                    [_LooseVersion(x) for x in ret[reponame][pkgname]], reverse=True
                )
                ret[reponame][pkgname] = [x.vstring for x in sorted_versions]
        return ret
    else:
        byrepo_ret = {}
        for reponame in ret:
            for pkgname in ret[reponame]:
                byrepo_ret.setdefault(pkgname, []).extend(ret[reponame][pkgname])
        for pkgname in byrepo_ret:
            sorted_versions = sorted(
                [_LooseVersion(x) for x in byrepo_ret[pkgname]], reverse=True
            )
            byrepo_ret[pkgname] = [x.vstring for x in sorted_versions]
        return byrepo_ret


def list_upgrades(refresh=True, **kwargs):
    """
    Check whether or not an upgrade is available for all packages

    The ``fromrepo``, ``enablerepo``, and ``disablerepo`` arguments are
    supported, as used in pkg states, and the ``disableexcludes`` option is
    also supported.

    .. versionadded:: 2014.7.0
        Support for the ``disableexcludes`` option

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    """
    options = _get_options(**kwargs)

    if salt.utils.data.is_true(refresh):
        refresh_db(check_update=False, **kwargs)

    cmd = ["--quiet"]
    cmd.extend(options)
    cmd.extend(["list", "upgrades" if _yum() == "dnf" else "updates"])
    out = _call_yum(cmd, ignore_retcode=True)
    if out["retcode"] != 0 and "Error:" in out:
        return {}

    return {x.name: x.version for x in _yum_pkginfo(out["stdout"])}


# Preserve expected CLI usage (yum list updates)
list_updates = salt.utils.functools.alias_function(list_upgrades, "list_updates")


def list_downloaded(**kwargs):
    """
    .. versionadded:: 2017.7.0

    List prefetched packages downloaded by Yum in the local disk.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.list_downloaded
    """
    CACHE_DIR = os.path.join("/var/cache/", _yum())

    ret = {}
    for root, dirnames, filenames in salt.utils.path.os_walk(CACHE_DIR):
        for filename in fnmatch.filter(filenames, "*.rpm"):
            package_path = os.path.join(root, filename)
            pkg_info = __salt__["lowpkg.bin_pkg_info"](package_path)
            pkg_timestamp = int(os.path.getctime(package_path))
            ret.setdefault(pkg_info["name"], {})[pkg_info["version"]] = {
                "path": package_path,
                "size": os.path.getsize(package_path),
                "creation_date_time_t": pkg_timestamp,
                "creation_date_time": datetime.datetime.fromtimestamp(
                    pkg_timestamp
                ).isoformat(),
            }
    return ret


def info_installed(*names, **kwargs):
    """
    .. versionadded:: 2015.8.1

    Return the information of the named package(s), installed on the system.

    :param all_versions:
        Include information for all versions of the packages installed on the minion.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.info_installed <package1>
        salt '*' pkg.info_installed <package1> <package2> <package3> ...
        salt '*' pkg.info_installed <package1> <package2> <package3> all_versions=True
    """
    all_versions = kwargs.get("all_versions", False)
    ret = dict()
    for pkg_name, pkgs_nfo in __salt__["lowpkg.info"](*names, **kwargs).items():
        pkg_nfo = pkgs_nfo if all_versions else [pkgs_nfo]
        for _nfo in pkg_nfo:
            t_nfo = dict()
            # Translate dpkg-specific keys to a common structure
            for key, value in _nfo.items():
                if key == "source_rpm":
                    t_nfo["source"] = value
                else:
                    t_nfo[key] = value
            if not all_versions:
                ret[pkg_name] = t_nfo
            else:
                ret.setdefault(pkg_name, []).append(t_nfo)
    return ret


def refresh_db(**kwargs):
    """
    Check the yum repos for updated packages

    Returns:

    - ``True``: Updates are available
    - ``False``: An error occurred
    - ``None``: No updates are available

    repo
        Refresh just the specified repo

    disablerepo
        Do not refresh the specified repo

    enablerepo
        Refresh a disabled repo using this option

    branch
        Add the specified branch when refreshing

    disableexcludes
        Disable the excludes defined in your config files. Takes one of three
        options:
        - ``all`` - disable all excludes
        - ``main`` - disable excludes defined in [main] in yum.conf
        - ``repoid`` - disable excludes defined for that repo

    setopt
        A comma-separated or Python list of key=value options. This list will
        be expanded and ``--setopt`` prepended to each in the yum/dnf command
        that is run.

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    """
    # Remove rtag file to keep multiple refreshes from happening in pkg states
    salt.utils.pkg.clear_rtag(__opts__)
    retcodes = {
        100: True,
        0: None,
        1: False,
    }

    ret = True
    check_update_ = kwargs.pop("check_update", True)
    options = _get_options(**kwargs)

    clean_cmd = ["--quiet", "--assumeyes", "clean", "expire-cache"]
    clean_cmd.extend(options)
    _call_yum(clean_cmd, ignore_retcode=True)

    if check_update_:
        update_cmd = ["--quiet", "--assumeyes", "check-update"]
        if (
            __grains__.get("os_family") == "RedHat"
            and __grains__.get("osmajorrelease") == 7
        ):
            # This feature is disabled because it is not used by Salt and adds a
            # lot of extra time to the command with large repos like EPEL
            update_cmd.append("--setopt=autocheck_running_kernel=false")
        update_cmd.extend(options)
        ret = retcodes.get(_call_yum(update_cmd, ignore_retcode=True)["retcode"], False)

    return ret


def clean_metadata(**kwargs):
    """
    .. versionadded:: 2014.1.0

    Cleans local yum metadata. Functionally identical to :mod:`refresh_db()
    <salt.modules.yumpkg.refresh_db>`.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.clean_metadata
    """
    return refresh_db(**kwargs)


class AvailablePackages(salt.utils.lazy.LazyDict):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._args = args
        self._kwargs = kwargs

    def _load(self, key):
        self._load_all()
        return True

    def _load_all(self):
        self._dict = list_repo_pkgs(*self._args, **self._kwargs)
        self.loaded = True


def install(
    name=None,
    refresh=False,
    skip_verify=False,
    pkgs=None,
    sources=None,
    downloadonly=False,
    reinstall=False,
    normalize=True,
    update_holds=False,
    saltenv="base",
    ignore_epoch=False,
    **kwargs
):
    """
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any yum/dnf commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Install the passed package(s), add refresh=True to clean the yum database
    before package is installed.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to install packages from a
        software repository. To install a package file manually, use the
        "sources" option.

        32-bit packages can be installed on 64-bit systems by appending the
        architecture designation (``.i686``, ``.i586``, etc.) to the end of the
        package name.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to update the yum database before executing.

    reinstall
        Specifying reinstall=True will use ``yum reinstall`` rather than
        ``yum install`` for requested packages that are already installed.

        If a version is specified with the requested package, then
        ``yum reinstall`` will only be used if the installed version
        matches the requested version.

        Works with ``sources`` when the package header of the source can be
        matched to the name and version of an installed package.

        .. versionadded:: 2014.7.0

    skip_verify
        Skip the GPG verification check (e.g., ``--nogpgcheck``)

    downloadonly
        Only download the packages, do not install.

    version
        Install a specific version of the package, e.g. 1.2.3-4.el5. Ignored
        if "pkgs" or "sources" is passed.

        .. versionchanged:: 2018.3.0
            version can now contain comparison operators (e.g. ``>1.2.3``,
            ``<=2.0``, etc.)

    update_holds : False
        If ``True``, and this function would update the package version, any
        packages held using the yum/dnf "versionlock" plugin will be unheld so
        that they can be updated. Otherwise, if this function attempts to
        update a held package, the held package(s) will be skipped and an
        error will be raised.

        .. versionadded:: 2016.11.0

    setopt
        A comma-separated or Python list of key=value options. This list will
        be expanded and ``--setopt`` prepended to each in the yum/dnf command
        that is run.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install foo setopt='obsoletes=0,plugins=0'

        .. versionadded:: 2019.2.0

    Repository Options:

    fromrepo
        Specify a package repository (or repositories) from which to install.
        (e.g., ``yum --disablerepo='*' --enablerepo='somerepo'``)

    enablerepo (ignored if ``fromrepo`` is specified)
        Specify a disabled package repository (or repositories) to enable.
        (e.g., ``yum --enablerepo='somerepo'``)

    disablerepo (ignored if ``fromrepo`` is specified)
        Specify an enabled package repository (or repositories) to disable.
        (e.g., ``yum --disablerepo='somerepo'``)

    disableexcludes
        Disable exclude from main, for a repo or for everything.
        (e.g., ``yum --disableexcludes='main'``)

        .. versionadded:: 2014.7.0

    ignore_epoch : False
        Only used when the version of a package is specified using a comparison
        operator (e.g. ``>4.1``). If set to ``True``, then the epoch will be
        ignored when comparing the currently-installed version to the desired
        version.

        .. versionadded:: 2018.3.0


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list. A specific version number can be specified
        by using a single-element dict representing the package and its
        version.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-4.el5"}]'

    sources
        A list of RPM packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.rpm"}, {"bar": "salt://bar.rpm"}]'

    normalize : True
        Normalize the package name by removing the architecture. This is useful
        for poorly created packages which might include the architecture as an
        actual part of the name such as kernel modules which match a specific
        kernel version.

        .. code-block:: bash

            salt -G role:nsd pkg.install gpfs.gplbin-2.6.32-279.31.1.el6.x86_64 normalize=False

        .. versionadded:: 2014.7.0

    diff_attr:
        If a list of package attributes is specified, returned value will
        contain them, eg.::

            {'<package>': {
                'old': {
                    'version': '<old-version>',
                    'arch': '<old-arch>'},

                'new': {
                    'version': '<new-version>',
                    'arch': '<new-arch>'}}}

        Valid attributes are: ``epoch``, ``version``, ``release``, ``arch``,
        ``install_date``, ``install_date_time_t``.

        If ``all`` is specified, all valid attributes will be returned.

        .. versionadded:: 2018.3.0

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    If an attribute list in diff_attr is specified, the dict will also contain
    any specified attribute, eg.::

        {'<package>': {
            'old': {
                'version': '<old-version>',
                'arch': '<old-arch>'},

            'new': {
                'version': '<new-version>',
                'arch': '<new-arch>'}}}
    """
    options = _get_options(**kwargs)

    if salt.utils.data.is_true(refresh):
        refresh_db(**kwargs)
    reinstall = salt.utils.data.is_true(reinstall)

    try:
        pkg_params, pkg_type = __salt__["pkg_resource.parse_targets"](
            name, pkgs, sources, saltenv=saltenv, normalize=normalize, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    version_num = kwargs.get("version")

    diff_attr = kwargs.get("diff_attr")
    old = (
        list_pkgs(versions_as_list=False, attr=diff_attr)
        if not downloadonly
        else list_downloaded()
    )
    # Use of __context__ means no duplicate work here, just accessing
    # information already in __context__ from the previous call to list_pkgs()
    old_as_list = (
        list_pkgs(versions_as_list=True) if not downloadonly else list_downloaded()
    )

    to_install = []
    to_downgrade = []
    to_reinstall = []
    _available = {}
    # The above three lists will be populated with tuples containing the
    # package name and the string being used for this particular package
    # modification. The reason for this method is that the string we use for
    # installation, downgrading, or reinstallation will be different than the
    # package name in a couple cases:
    #
    #   1) A specific version is being targeted. In this case the string being
    #      passed to install/downgrade/reinstall will contain the version
    #      information after the package name.
    #   2) A binary package is being installed via the "sources" param. In this
    #      case the string being passed will be the path to the local copy of
    #      the package in the minion cachedir.
    #
    # The reason that we need both items is to be able to modify the installed
    # version of held packages.
    if pkg_type == "repository":
        has_wildcards = []
        has_comparison = []
        for pkgname, pkgver in pkg_params.items():
            try:
                if "*" in pkgver:
                    has_wildcards.append(pkgname)
                elif pkgver.startswith("<") or pkgver.startswith(">"):
                    has_comparison.append(pkgname)
            except (TypeError, ValueError):
                continue
        _available = AvailablePackages(
            *has_wildcards + has_comparison, byrepo=False, **kwargs
        )
        pkg_params_items = pkg_params.items()
    elif pkg_type == "advisory":
        pkg_params_items = []
        cur_patches = list_patches()
        for advisory_id in pkg_params:
            if advisory_id not in cur_patches:
                raise CommandExecutionError(
                    'Advisory id "{}" not found'.format(advisory_id)
                )
            else:
                pkg_params_items.append(advisory_id)
    else:
        pkg_params_items = []
        for pkg_source in pkg_params:
            if "lowpkg.bin_pkg_info" in __salt__:
                rpm_info = __salt__["lowpkg.bin_pkg_info"](pkg_source)
            else:
                rpm_info = None
            if rpm_info is None:
                log.error(
                    "pkg.install: Unable to get rpm information for %s. "
                    "Version comparisons will be unavailable, and return "
                    "data may be inaccurate if reinstall=True.",
                    pkg_source,
                )
                pkg_params_items.append([pkg_source])
            else:
                pkg_params_items.append(
                    [rpm_info["name"], pkg_source, rpm_info["version"]]
                )

    errors = []
    for pkg_item_list in pkg_params_items:
        if pkg_type == "repository":
            pkgname, version_num = pkg_item_list
        elif pkg_type == "advisory":
            pkgname = pkg_item_list
            version_num = None
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
                    to_reinstall.append((pkgname, pkgname))
                else:
                    to_install.append((pkgname, pkgname))
            elif pkg_type == "advisory":
                to_install.append((pkgname, pkgname))
            else:
                to_install.append((pkgname, pkgpath))
        else:
            # If we are installing a package file and not one from the repo,
            # and version_num is not None, then we can assume that pkgname is
            # not None, since the only way version_num is not None is if RPM
            # metadata parsing was successful.
            if pkg_type == "repository":
                # yum/dnf does not support comparison operators. If the version
                # starts with an equals sign, ignore it.
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
                            "No version matching '{}{}' could be found "
                            "(available: {})".format(
                                pkgname,
                                version_num,
                                ", ".join(candidates) if candidates else None,
                            )
                        )
                        continue
                    else:
                        version_num = target
                if _yum() == "yum":
                    # yum install does not support epoch without the arch, and
                    # we won't know what the arch will be when it's not
                    # provided. It could either be the OS architecture, or
                    # 'noarch', and we don't make that distinction in the
                    # pkg.list_pkgs return data.
                    if ignore_epoch is True:
                        version_num = version_num.split(":", 1)[-1]
                arch = ""
                try:
                    namepart, archpart = pkgname.rsplit(".", 1)
                except ValueError:
                    pass
                else:
                    if archpart in salt.utils.pkg.rpm.ARCHES:
                        arch = "." + archpart
                        pkgname = namepart

                if "*" in version_num:
                    # Resolve wildcard matches
                    candidates = _available.get(pkgname, [])
                    match = salt.utils.itertools.fnmatch_multiple(
                        candidates, version_num
                    )
                    if match is not None:
                        version_num = match
                    else:
                        errors.append(
                            "No version matching '{}' found for package "
                            "'{}' (available: {})".format(
                                version_num,
                                pkgname,
                                ", ".join(candidates) if candidates else "none",
                            )
                        )
                        continue

                if ignore_epoch is True:
                    pkgstr = "{}-{}{}".format(pkgname, version_num, arch)
                else:
                    pkgstr = "{}-{}{}".format(
                        pkgname, version_num.split(":", 1)[-1], arch
                    )

            else:
                pkgstr = pkgpath

            # Lambda to trim the epoch from the currently-installed version if
            # no epoch is specified in the specified version
            cver = old_as_list.get(pkgname, [])
            if reinstall and cver:
                for ver in cver:
                    if salt.utils.versions.compare(
                        ver1=version_num,
                        oper="==",
                        ver2=ver,
                        cmp_func=version_cmp,
                        ignore_epoch=ignore_epoch,
                    ):
                        # This version is already installed, so we need to
                        # reinstall.
                        to_reinstall.append((pkgname, pkgstr))
                        break
            else:
                if not cver:
                    to_install.append((pkgname, pkgstr))
                else:
                    for ver in cver:
                        if salt.utils.versions.compare(
                            ver1=version_num,
                            oper=">=",
                            ver2=ver,
                            cmp_func=version_cmp,
                            ignore_epoch=ignore_epoch,
                        ):
                            to_install.append((pkgname, pkgstr))
                            break
                    else:
                        if pkgname is not None:
                            if re.match("^kernel(|-devel)$", pkgname):
                                # kernel and kernel-devel support multiple
                                # installs as their paths do not conflict.
                                # Performing a yum/dnf downgrade will be a
                                # no-op so just do an install instead. It will
                                # fail if there are other interdependencies
                                # that have conflicts, and that's OK. We don't
                                # want to force anything, we just want to
                                # properly handle it if someone tries to
                                # install a kernel/kernel-devel of a lower
                                # version than the currently-installed one.
                                # TODO: find a better way to determine if a
                                # package supports multiple installs.
                                to_install.append((pkgname, pkgstr))
                            else:
                                # None of the currently-installed versions are
                                # greater than the specified version, so this
                                # is a downgrade.
                                to_downgrade.append((pkgname, pkgstr))

    def _add_common_args(cmd):
        """
        DRY function to add args common to all yum/dnf commands
        """
        cmd.extend(options)
        if skip_verify:
            cmd.append("--nogpgcheck")
        if downloadonly:
            cmd.append("--downloadonly")

    try:
        holds = list_holds(full=False)
    except SaltInvocationError:
        holds = []
        log.debug(
            "Failed to get holds, versionlock plugin is probably not " "installed"
        )
    unhold_prevented = []

    @contextlib.contextmanager
    def _temporarily_unhold(pkgs, targets):
        """
        Temporarily unhold packages that need to be updated. Add any
        successfully-removed ones (and any packages not in the list of current
        holds) to the list of targets.
        """
        to_unhold = {}
        for pkgname, pkgstr in pkgs:
            if pkgname in holds:
                if update_holds:
                    to_unhold[pkgname] = pkgstr
                else:
                    unhold_prevented.append(pkgname)
            else:
                targets.append(pkgstr)

        if not to_unhold:
            yield
        else:
            log.debug("Unholding packages: %s", ", ".join(to_unhold))
            try:
                # Using list() here for python3 compatibility, dict.keys() no
                # longer returns a list in python3.
                unhold_names = list(to_unhold.keys())
                for unheld_pkg, outcome in unhold(pkgs=unhold_names).items():
                    if outcome["result"]:
                        # Package was successfully unheld, add to targets
                        targets.append(to_unhold[unheld_pkg])
                    else:
                        # Failed to unhold package
                        errors.append(unheld_pkg)
                yield
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(
                    "Error encountered unholding packages {}: {}".format(
                        ", ".join(to_unhold), exc
                    )
                )
            finally:
                hold(pkgs=unhold_names)

    targets = []
    with _temporarily_unhold(to_install, targets):
        if targets:
            if pkg_type == "advisory":
                targets = ["--advisory={}".format(t) for t in targets]
            cmd = ["-y"]
            if _yum() == "dnf":
                cmd.extend(["--best", "--allowerasing"])
            _add_common_args(cmd)
            cmd.append("install" if pkg_type != "advisory" else "update")
            cmd.extend(targets)
            out = _call_yum(cmd, ignore_retcode=False, redirect_stderr=True)
            if out["retcode"] != 0:
                errors.append(out["stdout"])

    targets = []
    with _temporarily_unhold(to_downgrade, targets):
        if targets:
            cmd = ["-y"]
            _add_common_args(cmd)
            cmd.append("downgrade")
            cmd.extend(targets)
            out = _call_yum(cmd, redirect_stderr=True)
            if out["retcode"] != 0:
                errors.append(out["stdout"])

    targets = []
    with _temporarily_unhold(to_reinstall, targets):
        if targets:
            cmd = ["-y"]
            _add_common_args(cmd)
            cmd.append("reinstall")
            cmd.extend(targets)
            out = _call_yum(cmd, redirect_stderr=True)
            if out["retcode"] != 0:
                errors.append(out["stdout"])

    __context__.pop("pkg.list_pkgs", None)
    new = (
        list_pkgs(versions_as_list=False, attr=diff_attr)
        if not downloadonly
        else list_downloaded()
    )

    ret = salt.utils.data.compare_dicts(old, new)

    for pkgname, _ in to_reinstall:
        if pkgname not in ret or pkgname in old:
            ret.update(
                {pkgname: {"old": old.get(pkgname, ""), "new": new.get(pkgname, "")}}
            )

    if unhold_prevented:
        errors.append(
            "The following package(s) could not be updated because they are "
            "being held: {}. Set 'update_holds' to True to temporarily "
            "unhold these packages so that they can be updated.".format(
                ", ".join(unhold_prevented)
            )
        )

    if errors:
        raise CommandExecutionError(
            "Error occurred installing{} package(s)".format(
                "/reinstalling" if to_reinstall else ""
            ),
            info={"errors": errors, "changes": ret},
        )

    return ret


def upgrade(
    name=None,
    pkgs=None,
    refresh=True,
    skip_verify=False,
    normalize=True,
    minimal=False,
    obsoletes=True,
    **kwargs
):
    """
    Run a full system upgrade (a ``yum upgrade`` or ``dnf upgrade``), or
    upgrade specified packages. If the packages aren't installed, they will
    not be installed.

    .. versionchanged:: 2014.7.0
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any yum/dnf commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    .. versionchanged:: 2019.2.0
        Added ``obsoletes`` and ``minimal`` arguments

    Returns a dictionary containing the changes:

    .. code-block:: python

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}


    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
        salt '*' pkg.upgrade name=openssl

    Repository Options:

    fromrepo
        Specify a package repository (or repositories) from which to install.
        (e.g., ``yum --disablerepo='*' --enablerepo='somerepo'``)

    enablerepo (ignored if ``fromrepo`` is specified)
        Specify a disabled package repository (or repositories) to enable.
        (e.g., ``yum --enablerepo='somerepo'``)

    disablerepo (ignored if ``fromrepo`` is specified)
        Specify an enabled package repository (or repositories) to disable.
        (e.g., ``yum --disablerepo='somerepo'``)

    disableexcludes
        Disable exclude from main, for a repo or for everything.
        (e.g., ``yum --disableexcludes='main'``)

        .. versionadded:: 2014.7

    name
        The name of the package to be upgraded. Note that this parameter is
        ignored if "pkgs" is passed.

        32-bit packages can be upgraded on 64-bit systems by appending the
        architecture designation (``.i686``, ``.i586``, etc.) to the end of the
        package name.

        Warning: if you forget 'name=' and run pkg.upgrade openssl, ALL packages
        are upgraded. This will be addressed in next releases.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.upgrade name=openssl

        .. versionadded:: 2016.3.0

    pkgs
        A list of packages to upgrade from a software repository. Must be
        passed as a python list. A specific version number can be specified
        by using a single-element dict representing the package and its
        version. If the package was not already installed on the system,
        it will not be installed.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.upgrade pkgs='["foo", "bar"]'
            salt '*' pkg.upgrade pkgs='["foo", {"bar": "1.2.3-4.el5"}]'

        .. versionadded:: 2016.3.0

    normalize : True
        Normalize the package name by removing the architecture. This is useful
        for poorly created packages which might include the architecture as an
        actual part of the name such as kernel modules which match a specific
        kernel version.

        .. code-block:: bash

            salt -G role:nsd pkg.upgrade gpfs.gplbin-2.6.32-279.31.1.el6.x86_64 normalize=False

        .. versionadded:: 2016.3.0

    minimal : False
        Use upgrade-minimal instead of upgrade (e.g., ``yum upgrade-minimal``)
        Goes to the 'newest' package match which fixes a problem that affects your system.

        .. code-block:: bash

            salt '*' pkg.upgrade minimal=True

        .. versionadded:: 2019.2.0

    obsoletes : True
        Controls whether yum/dnf should take obsoletes into account and remove them.
        If set to ``False`` yum will use ``update`` instead of ``upgrade``
        and dnf will be run with ``--obsoletes=False``

        .. code-block:: bash

            salt '*' pkg.upgrade obsoletes=False

        .. versionadded:: 2019.2.0

    setopt
        A comma-separated or Python list of key=value options. This list will
        be expanded and ``--setopt`` prepended to each in the yum/dnf command
        that is run.

        .. versionadded:: 2019.2.0

    .. note::
        To add extra arguments to the ``yum upgrade`` command, pass them as key
        word arguments. For arguments without assignments, pass ``True``

    .. code-block:: bash

        salt '*' pkg.upgrade security=True exclude='kernel*'
    """
    options = _get_options(get_extra_options=True, **kwargs)

    if salt.utils.data.is_true(refresh):
        refresh_db(**kwargs)

    old = list_pkgs()

    targets = []
    if name or pkgs:
        try:
            pkg_params = __salt__["pkg_resource.parse_targets"](
                name=name, pkgs=pkgs, sources=None, normalize=normalize, **kwargs
            )[0]
        except MinionError as exc:
            raise CommandExecutionError(exc)

        if pkg_params:
            # Calling list.extend() on a dict will extend it using the
            # dictionary's keys.
            targets.extend(pkg_params)

    cmd = ["--quiet", "-y"]
    cmd.extend(options)
    if skip_verify:
        cmd.append("--nogpgcheck")
    if obsoletes:
        cmd.append("upgrade" if not minimal else "upgrade-minimal")
    else:
        # do not force the removal of obsolete packages
        if _yum() == "dnf":
            # for dnf we can just disable obsoletes
            cmd.append("--obsoletes=False")
            cmd.append("upgrade" if not minimal else "upgrade-minimal")
        else:
            # for yum we have to use update instead of upgrade
            cmd.append("update" if not minimal else "update-minimal")
    cmd.extend(targets)
    result = _call_yum(cmd)
    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if result["retcode"] != 0:
        raise CommandExecutionError(
            "Problem encountered upgrading packages",
            info={"changes": ret, "result": result},
        )

    return ret


def update(
    name=None,
    pkgs=None,
    refresh=True,
    skip_verify=False,
    normalize=True,
    minimal=False,
    obsoletes=False,
    **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Calls :py:func:`pkg.upgrade <salt.modules.yumpkg.upgrade>` with
    ``obsoletes=False``. Mirrors the CLI behavior of ``yum update``.
    See :py:func:`pkg.upgrade <salt.modules.yumpkg.upgrade>` for
    further documentation.

    .. code-block:: bash

        salt '*' pkg.update
    """
    return upgrade(
        name, pkgs, refresh, skip_verify, normalize, minimal, obsoletes, **kwargs
    )


def remove(name=None, pkgs=None, **kwargs):  # pylint: disable=W0613
    """
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any yum/dnf commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Remove packages

    name
        The name of the package to be removed


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
        pkg_params = __salt__["pkg_resource.parse_targets"](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = []
    for target in pkg_params:
        # Check if package version set to be removed is actually installed:
        # old[target] contains a comma-separated list of installed versions
        if target in old and not pkg_params[target]:
            targets.append(target)
        elif target in old and pkg_params[target] in old[target].split(","):
            arch = ""
            pkgname = target
            try:
                namepart, archpart = target.rsplit(".", 1)
            except ValueError:
                pass
            else:
                if archpart in salt.utils.pkg.rpm.ARCHES:
                    arch = "." + archpart
                    pkgname = namepart
            targets.append("{}-{}{}".format(pkgname, pkg_params[target], arch))
    if not targets:
        return {}

    out = _call_yum(["-y", "remove"] + targets)
    if out["retcode"] != 0 and out["stderr"]:
        errors = [out["stderr"]]
    else:
        errors = []

    __context__.pop("pkg.list_pkgs", None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            "Error occurred removing package(s)",
            info={"errors": errors, "changes": ret},
        )

    return ret


def purge(name=None, pkgs=None, **kwargs):  # pylint: disable=W0613
    """
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any yum/dnf commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Package purges are not supported by yum, this function is identical to
    :mod:`pkg.remove <salt.modules.yumpkg.remove>`.

    name
        The name of the package to be purged


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
    return remove(name=name, pkgs=pkgs)


def hold(
    name=None, pkgs=None, sources=None, normalize=True, **kwargs
):  # pylint: disable=W0613
    """
    .. versionadded:: 2014.7.0

    Version-lock packages

    .. note::
        Requires the appropriate ``versionlock`` plugin package to be installed:

        - On RHEL 5: ``yum-versionlock``
        - On RHEL 6 & 7: ``yum-plugin-versionlock``
        - On Fedora: ``python-dnf-plugins-extras-versionlock``


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
    _check_versionlock()

    if not name and not pkgs and not sources:
        raise SaltInvocationError("One of name, pkgs, or sources must be specified.")
    if pkgs and sources:
        raise SaltInvocationError("Only one of pkgs or sources can be specified.")

    targets = []
    if pkgs:
        targets.extend(pkgs)
    elif sources:
        for source in sources:
            targets.append(next(iter(source.keys())))
    else:
        targets.append(name)

    current_locks = list_holds(full=False)
    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target.keys()))

        ret[target] = {"name": target, "changes": {}, "result": False, "comment": ""}

        if target not in current_locks:
            if "test" in __opts__ and __opts__["test"]:
                ret[target].update(result=None)
                ret[target]["comment"] = "Package {} is set to be held.".format(target)
            else:
                out = _call_yum(["versionlock", target])
                if out["retcode"] == 0:
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


def unhold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    """
    .. versionadded:: 2014.7.0

    Remove version locks

    .. note::
        Requires the appropriate ``versionlock`` plugin package to be installed:

        - On RHEL 5: ``yum-versionlock``
        - On RHEL 6 & 7: ``yum-plugin-versionlock``
        - On Fedora: ``python-dnf-plugins-extras-versionlock``


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
    _check_versionlock()

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

    # Yum's versionlock plugin doesn't support passing just the package name
    # when removing a lock, so we need to get the full list and then use
    # fnmatch below to find the match.
    current_locks = list_holds(full=_yum() == "yum")

    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target.keys()))

        ret[target] = {"name": target, "changes": {}, "result": False, "comment": ""}

        if _yum() == "dnf":
            search_locks = [x for x in current_locks if x == target]
        else:
            # To accommodate yum versionlock's lack of support for removing
            # locks using just the package name, we have to use fnmatch to do
            # glob matching on the target name, and then for each matching
            # expression double-check that the package name (obtained via
            # _get_hold()) matches the targeted package.
            search_locks = [
                x
                for x in current_locks
                if fnmatch.fnmatch(x, "*{}*".format(target))
                and target == _get_hold(x, full=False)
            ]

        if search_locks:
            if __opts__["test"]:
                ret[target].update(result=None)
                ret[target]["comment"] = "Package {} is set to be unheld.".format(
                    target
                )
            else:
                out = _call_yum(["versionlock", "delete"] + search_locks)
                if out["retcode"] == 0:
                    ret[target].update(result=True)
                    ret[target]["comment"] = "Package {} is no longer held.".format(
                        target
                    )
                    ret[target]["changes"]["new"] = ""
                    ret[target]["changes"]["old"] = "hold"
                else:
                    ret[target][
                        "comment"
                    ] = "Package {} was unable to be " "unheld.".format(target)
        else:
            ret[target].update(result=True)
            ret[target]["comment"] = "Package {} is not being held.".format(target)
    return ret


def list_holds(pattern=__HOLD_PATTERN, full=True):
    r"""
    .. versionchanged:: 2016.3.0,2015.8.4,2015.5.10
        Function renamed from ``pkg.get_locked_pkgs`` to ``pkg.list_holds``.

    List information on locked packages

    .. note::
        Requires the appropriate ``versionlock`` plugin package to be installed:

        - On RHEL 5: ``yum-versionlock``
        - On RHEL 6 & 7: ``yum-plugin-versionlock``
        - On Fedora: ``python-dnf-plugins-extras-versionlock``

    pattern : \w+(?:[.-][^-]+)*
        Regular expression used to match the package name

    full : True
        Show the full hold definition including version and epoch. Set to
        ``False`` to return just the name of the package(s) being held.


    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_holds
        salt '*' pkg.list_holds full=False
    """
    _check_versionlock()

    out = __salt__["cmd.run"]([_yum(), "versionlock", "list"], python_shell=False)
    ret = []
    for line in salt.utils.itertools.split(out, "\n"):
        match = _get_hold(line, pattern=pattern, full=full)
        if match is not None:
            ret.append(match)
    return ret


get_locked_packages = salt.utils.functools.alias_function(
    list_holds, "get_locked_packages"
)


def verify(*names, **kwargs):
    """
    .. versionadded:: 2014.1.0

    Runs an rpm -Va on a system, and returns the results in a dict

    Pass options to modify rpm verify behavior using the ``verify_options``
    keyword argument

    Files with an attribute of config, doc, ghost, license or readme in the
    package header can be ignored using the ``ignore_types`` keyword argument

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.verify
        salt '*' pkg.verify httpd
        salt '*' pkg.verify 'httpd postfix'
        salt '*' pkg.verify 'httpd postfix' ignore_types=['config','doc']
        salt '*' pkg.verify 'httpd postfix' verify_options=['nodeps','nosize']
    """
    return __salt__["lowpkg.verify"](*names, **kwargs)


def group_list():
    """
    .. versionadded:: 2014.1.0

    Lists all groups known by yum on this system

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_list
    """
    ret = {
        "installed": [],
        "available": [],
        "installed environments": [],
        "available environments": [],
        "available languages": {},
    }

    section_map = {
        "installed groups:": "installed",
        "available groups:": "available",
        "installed environment groups:": "installed environments",
        "available environment groups:": "available environments",
        "available language groups:": "available languages",
    }

    out = __salt__["cmd.run_stdout"](
        [_yum(), "grouplist", "hidden"], output_loglevel="trace", python_shell=False
    )
    key = None
    for line in salt.utils.itertools.split(out, "\n"):
        line_lc = line.lower()
        if line_lc == "done":
            break

        section_lookup = section_map.get(line_lc)
        if section_lookup is not None and section_lookup != key:
            key = section_lookup
            continue

        # Ignore any administrative comments (plugin info, repo info, etc.)
        if key is None:
            continue

        line = line.strip()
        if key != "available languages":
            ret[key].append(line)
        else:
            match = re.match(r"(.+) \[(.+)\]", line)
            if match:
                name, lang = match.groups()
                ret[key][line] = {"name": name, "language": lang}
    return ret


def group_info(name, expand=False, ignore_groups=None):
    """
    .. versionadded:: 2014.1.0
    .. versionchanged:: 3001,2016.3.0,2015.8.4,2015.5.10
        The return data has changed. A new key ``type`` has been added to
        distinguish environment groups from package groups. Also, keys for the
        group name and group ID have been added. The ``mandatory packages``,
        ``optional packages``, and ``default packages`` keys have been renamed
        to ``mandatory``, ``optional``, and ``default`` for accuracy, as
        environment groups include other groups, and not packages. Finally,
        this function now properly identifies conditional packages.

    Lists packages belonging to a certain group

    name
        Name of the group to query

    expand : False
        If the specified group is an environment group, then the group will be
        expanded and the return data will include package names instead of
        group names.

        .. versionadded:: 2016.3.0

    ignore_groups : None
        This parameter can be used to pass a list of groups to ignore when
        expanding subgroups. It is used during recursion in order to prevent
        expanding the same group multiple times.

        .. versionadded:: 3001

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_info 'Perl Support'
    """
    pkgtypes = ("mandatory", "optional", "default", "conditional")
    ret = {}
    for pkgtype in pkgtypes:
        ret[pkgtype] = set()

    cmd = [_yum(), "--quiet", "groupinfo", name]
    out = __salt__["cmd.run_stdout"](cmd, output_loglevel="trace", python_shell=False)

    g_info = {}
    for line in salt.utils.itertools.split(out, "\n"):
        try:
            key, value = [x.strip() for x in line.split(":")]
            g_info[key.lower()] = value
        except ValueError:
            continue

    if "environment group" in g_info:
        ret["type"] = "environment group"
    elif "group" in g_info:
        ret["type"] = "package group"

    ret["group"] = g_info.get("environment group") or g_info.get("group")
    ret["id"] = g_info.get("environment-id") or g_info.get("group-id")
    if not ret["group"] and not ret["id"]:
        raise CommandExecutionError("Group '{}' not found".format(name))

    ret["description"] = g_info.get("description", "")

    completed_groups = ignore_groups or []
    pkgtypes_capturegroup = "(" + "|".join(pkgtypes) + ")"
    for pkgtype in pkgtypes:
        target_found = False
        for line in salt.utils.itertools.split(out, "\n"):
            line = line.strip().lstrip(string.punctuation)
            match = re.match(
                pkgtypes_capturegroup + r" (?:groups|packages):\s*$", line.lower()
            )
            if match:
                if target_found:
                    # We've reached a new section, break from loop
                    break
                else:
                    if match.group(1) == pkgtype:
                        # We've reached the targeted section
                        target_found = True
                    continue
            if target_found:
                if expand and ret["type"] == "environment group":
                    if not line or line in completed_groups:
                        continue
                    log.trace(
                        'Adding group "%s" to completed list: %s',
                        line,
                        completed_groups,
                    )
                    completed_groups.append(line)
                    # Using the @ prefix on the group here in order to prevent multiple matches
                    # being returned, such as with gnome-desktop
                    expanded = group_info(
                        "@" + line, expand=True, ignore_groups=completed_groups
                    )
                    # Don't shadow the pkgtype variable from the outer loop
                    for p_type in pkgtypes:
                        ret[p_type].update(set(expanded[p_type]))
                else:
                    ret[pkgtype].add(line)

    for pkgtype in pkgtypes:
        ret[pkgtype] = sorted(ret[pkgtype])

    return ret


def group_diff(name):
    """
    .. versionadded:: 2014.1.0
    .. versionchanged:: 2016.3.0,2015.8.4,2015.5.10
        Environment groups are now supported. The key names have been renamed,
        similar to the changes made in :py:func:`pkg.group_info
        <salt.modules.yumpkg.group_info>`.

    Lists which of a group's packages are installed and which are not
    installed

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_diff 'Perl Support'
    """
    pkgtypes = ("mandatory", "optional", "default", "conditional")
    ret = {}
    for pkgtype in pkgtypes:
        ret[pkgtype] = {"installed": [], "not installed": []}

    pkgs = list_pkgs()
    group_pkgs = group_info(name, expand=True)
    for pkgtype in pkgtypes:
        for member in group_pkgs.get(pkgtype, []):
            if member in pkgs:
                ret[pkgtype]["installed"].append(member)
            else:
                ret[pkgtype]["not installed"].append(member)
    return ret


def group_install(name, skip=(), include=(), **kwargs):
    """
    .. versionadded:: 2014.1.0

    Install the passed package group(s). This is basically a wrapper around
    :py:func:`pkg.install <salt.modules.yumpkg.install>`, which performs
    package group resolution for the user. This function is currently
    considered experimental, and should be expected to undergo changes.

    name
        Package group to install. To install more than one group, either use a
        comma-separated list or pass the value as a python list.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.group_install 'Group 1'
            salt '*' pkg.group_install 'Group 1,Group 2'
            salt '*' pkg.group_install '["Group 1", "Group 2"]'

    skip
        Packages that would normally be installed by the package group
        ("default" packages), which should not be installed. Can be passed
        either as a comma-separated list or a python list.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.group_install 'My Group' skip='foo,bar'
            salt '*' pkg.group_install 'My Group' skip='["foo", "bar"]'

    include
        Packages which are included in a group, which would not normally be
        installed by a ``yum groupinstall`` ("optional" packages). Note that
        this will not enforce group membership; if you include packages which
        are not members of the specified groups, they will still be installed.
        Can be passed either as a comma-separated list or a python list.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.group_install 'My Group' include='foo,bar'
            salt '*' pkg.group_install 'My Group' include='["foo", "bar"]'

    .. note::
        Because this is essentially a wrapper around pkg.install, any argument
        which can be passed to pkg.install may also be included here, and it
        will be passed along wholesale.
    """
    groups = name.split(",") if isinstance(name, str) else name

    if not groups:
        raise SaltInvocationError("no groups specified")
    elif not isinstance(groups, list):
        raise SaltInvocationError("'groups' must be a list")

    # pylint: disable=maybe-no-member
    if isinstance(skip, str):
        skip = skip.split(",")
    if not isinstance(skip, (list, tuple)):
        raise SaltInvocationError("'skip' must be a list")

    if isinstance(include, str):
        include = include.split(",")
    if not isinstance(include, (list, tuple)):
        raise SaltInvocationError("'include' must be a list")
    # pylint: enable=maybe-no-member

    targets = []
    for group in groups:
        group_detail = group_info(group)
        targets.extend(group_detail.get("mandatory", []))
        targets.extend(
            [pkg for pkg in group_detail.get("default", []) if pkg not in skip]
        )
    if include:
        targets.extend(include)

    # Don't install packages that are already installed, install() isn't smart
    # enough to make this distinction.
    pkgs = [x for x in targets if x not in list_pkgs()]
    if not pkgs:
        return {}

    return install(pkgs=pkgs, **kwargs)


groupinstall = salt.utils.functools.alias_function(group_install, "groupinstall")


def list_repos(basedir=None, **kwargs):
    """
    Lists all repos in <basedir> (default: all dirs in `reposdir` yum option).

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_repos
        salt '*' pkg.list_repos basedir=/path/to/dir
        salt '*' pkg.list_repos basedir=/path/to/dir,/path/to/another/dir
    """

    basedirs = _normalize_basedir(basedir)
    repos = {}
    log.debug("Searching for repos in %s", basedirs)
    for bdir in basedirs:
        if not os.path.exists(bdir):
            continue
        for repofile in os.listdir(bdir):
            repopath = "{}/{}".format(bdir, repofile)
            if not repofile.endswith(".repo"):
                continue
            filerepos = _parse_repo_file(repopath)[1]
            for reponame in filerepos:
                repo = filerepos[reponame]
                repo["file"] = repopath
                repos[reponame] = repo
    return repos


def get_repo(repo, basedir=None, **kwargs):  # pylint: disable=W0613
    """
    Display a repo from <basedir> (default basedir: all dirs in ``reposdir``
    yum option).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.get_repo myrepo
        salt '*' pkg.get_repo myrepo basedir=/path/to/dir
        salt '*' pkg.get_repo myrepo basedir=/path/to/dir,/path/to/another/dir
    """
    repos = list_repos(basedir)

    if repo.startswith("copr:"):
        repo = _get_copr_repo(repo)

    # Find out what file the repo lives in
    repofile = ""
    for list_repo in repos:
        if list_repo == repo:
            repofile = repos[list_repo]["file"]

    if repofile:
        # Return just one repo
        filerepos = _parse_repo_file(repofile)[1]
        return filerepos[repo]
    return {}


def del_repo(repo, basedir=None, **kwargs):  # pylint: disable=W0613
    """
    Delete a repo from <basedir> (default basedir: all dirs in `reposdir` yum
    option).

    If the .repo file in which the repo exists does not contain any other repo
    configuration, the file itself will be deleted.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo myrepo
        salt '*' pkg.del_repo myrepo basedir=/path/to/dir
        salt '*' pkg.del_repo myrepo basedir=/path/to/dir,/path/to/another/dir
    """

    if repo.startswith("copr:"):
        repo = _get_copr_repo(repo)

    # this is so we know which dirs are searched for our error messages below
    basedirs = _normalize_basedir(basedir)
    repos = list_repos(basedirs)

    if repo not in repos:
        return "Error: the {} repo does not exist in {}".format(repo, basedirs)

    # Find out what file the repo lives in
    repofile = ""
    for arepo in repos:
        if arepo == repo:
            repofile = repos[arepo]["file"]

    # See if the repo is the only one in the file
    onlyrepo = True
    for arepo in repos:
        if arepo == repo:
            continue
        if repos[arepo]["file"] == repofile:
            onlyrepo = False

    # If this is the only repo in the file, delete the file itself
    if onlyrepo:
        os.remove(repofile)
        return "File {} containing repo {} has been removed".format(repofile, repo)

    # There must be other repos in this file, write the file with them
    header, filerepos = _parse_repo_file(repofile)
    content = header
    for stanza in filerepos.keys():
        if stanza == repo:
            continue
        comments = ""
        if "comments" in filerepos[stanza].keys():
            comments = salt.utils.pkg.rpm.combine_comments(
                filerepos[stanza]["comments"]
            )
            del filerepos[stanza]["comments"]
        content += "\n[{}]".format(stanza)
        for line in filerepos[stanza]:
            # A whitespace is needed at the beginning of the new line in order
            # to avoid breaking multiple line values allowed on repo files.
            value = filerepos[stanza][line]
            if isinstance(value, str) and "\n" in value:
                value = "\n ".join(value.split("\n"))
            content += "\n{}={}".format(line, value)
        content += "\n{}\n".format(comments)

    with salt.utils.files.fopen(repofile, "w") as fileout:
        fileout.write(salt.utils.stringutils.to_str(content))

    return "Repo {} has been removed from {}".format(repo, repofile)


def mod_repo(repo, basedir=None, **kwargs):
    """
    Modify one or more values for a repo. If the repo does not exist, it will
    be created, so long as the following values are specified:

    repo
        name by which the yum refers to the repo
    name
        a human-readable name for the repo
    baseurl
        the URL for yum to reference
    mirrorlist
        the URL for yum to reference

    Key/Value pairs may also be removed from a repo's configuration by setting
    a key to a blank value. Bear in mind that a name cannot be deleted, and a
    baseurl can only be deleted if a mirrorlist is specified (or vice versa).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.mod_repo reponame enabled=1 gpgcheck=1
        salt '*' pkg.mod_repo reponame basedir=/path/to/dir enabled=1
        salt '*' pkg.mod_repo reponame baseurl= mirrorlist=http://host.com/
    """
    # Filter out '__pub' arguments, as well as saltenv
    repo_opts = {
        x: kwargs[x] for x in kwargs if not x.startswith("__") and x not in ("saltenv",)
    }

    if all(x in repo_opts for x in ("mirrorlist", "baseurl")):
        raise SaltInvocationError(
            "Only one of 'mirrorlist' and 'baseurl' can be specified"
        )

    use_copr = False
    if repo.startswith("copr:"):
        copr_name = repo.split(":", 1)[1]
        repo = _get_copr_repo(repo)
        use_copr = True

    # Build a list of keys to be deleted
    todelete = []
    # list() of keys because the dict could be shrinking in the for loop.
    for key in list(repo_opts):
        if repo_opts[key] != 0 and not repo_opts[key]:
            del repo_opts[key]
            todelete.append(key)

    # Add baseurl or mirrorlist to the 'todelete' list if the other was
    # specified in the repo_opts
    if "mirrorlist" in repo_opts:
        todelete.append("baseurl")
    elif "baseurl" in repo_opts:
        todelete.append("mirrorlist")

    # Fail if the user tried to delete the name
    if "name" in todelete:
        raise SaltInvocationError("The repo name cannot be deleted")

    # Give the user the ability to change the basedir
    repos = {}
    basedirs = _normalize_basedir(basedir)
    repos = list_repos(basedirs)

    repofile = ""
    header = ""
    filerepos = {}
    if repo not in repos:
        # If the repo doesn't exist, create it in a new file in the first
        # repo directory that exists
        newdir = None
        for d in basedirs:
            if os.path.exists(d):
                newdir = d
                break
        if not newdir:
            raise SaltInvocationError(
                "The repo does not exist and needs to be created, but none "
                "of the following basedir directories exist: {}".format(basedirs)
            )
        repofile = "{}/{}.repo".format(newdir, repo)
        if use_copr:
            # Is copr plugin installed?
            copr_plugin_name = ""
            if _yum() == "dnf":
                copr_plugin_name = "dnf-plugins-core"
            else:
                copr_plugin_name = "yum-plugin-copr"

            if not __salt__["pkg_resource.version"](copr_plugin_name):
                raise SaltInvocationError(
                    "{} must be installed to use COPR".format(copr_plugin_name)
                )

            # Enable COPR
            out = _call_yum(["copr", "enable", copr_name, "-y"])
            if out["retcode"]:
                raise CommandExecutionError(
                    "Unable to add COPR '{}'. '{}' exited with "
                    "status {!s}: '{}' ".format(
                        copr_name, _yum(), out["retcode"], out["stderr"]
                    )
                )
            # Repo has been added, update repos list
            repos = list_repos(basedirs)
            repofile = repos[repo]["file"]
            header, filerepos = _parse_repo_file(repofile)
        else:
            repofile = "{}/{}.repo".format(newdir, repo)

            if "name" not in repo_opts:
                raise SaltInvocationError(
                    "The repo does not exist and needs to be created, but a name "
                    "was not given"
                )

            if "baseurl" not in repo_opts and "mirrorlist" not in repo_opts:
                raise SaltInvocationError(
                    "The repo does not exist and needs to be created, but either "
                    "a baseurl or a mirrorlist needs to be given"
                )
            filerepos[repo] = {}
    else:
        # The repo does exist, open its file
        repofile = repos[repo]["file"]
        header, filerepos = _parse_repo_file(repofile)

    # Error out if they tried to delete baseurl or mirrorlist improperly
    if "baseurl" in todelete:
        if "mirrorlist" not in repo_opts and "mirrorlist" not in filerepos[repo]:
            raise SaltInvocationError(
                "Cannot delete baseurl without specifying mirrorlist"
            )
    if "mirrorlist" in todelete:
        if "baseurl" not in repo_opts and "baseurl" not in filerepos[repo]:
            raise SaltInvocationError(
                "Cannot delete mirrorlist without specifying baseurl"
            )

    # Delete anything in the todelete list
    for key in todelete:
        if key in filerepos[repo].copy().keys():
            del filerepos[repo][key]

    _bool_to_str = lambda x: "1" if x else "0"
    # Old file or new, write out the repos(s)
    filerepos[repo].update(repo_opts)
    content = header
    for stanza in filerepos.keys():
        comments = salt.utils.pkg.rpm.combine_comments(
            filerepos[stanza].pop("comments", [])
        )
        content += "[{}]\n".format(stanza)
        for line in filerepos[stanza].keys():
            # A whitespace is needed at the beginning of the new line in order
            # to avoid breaking multiple line values allowed on repo files.
            value = filerepos[stanza][line]
            if isinstance(value, str) and "\n" in value:
                value = "\n ".join(value.split("\n"))
            content += "{}={}\n".format(
                line, value if not isinstance(value, bool) else _bool_to_str(value)
            )
        content += comments + "\n"

    with salt.utils.files.fopen(repofile, "w") as fileout:
        fileout.write(salt.utils.stringutils.to_str(content))

    return {repofile: filerepos}


def _parse_repo_file(filename):
    """
    Turn a single repo file into a dict
    """
    parsed = configparser.ConfigParser()
    config = {}

    try:
        parsed.read(filename)
    except configparser.MissingSectionHeaderError as err:
        log.error("Failed to parse file %s, error: %s", filename, err.message)
        return ("", {})

    for section in parsed._sections:
        section_dict = dict(parsed._sections[section])
        section_dict.pop("__name__", None)
        config[section] = section_dict

    # Try to extract header comments, as well as comments for each repo. Read
    # from the beginning of the file and assume any leading comments are
    # header comments. Continue to read each section header and then find the
    # comments for each repo.
    headers = ""
    section = None
    with salt.utils.files.fopen(filename, "r") as repofile:
        for line in repofile:
            line = salt.utils.stringutils.to_unicode(line)
            line = line.strip()
            if line.startswith("#"):
                if section is None:
                    headers += line + "\n"
                else:
                    try:
                        comments = config[section].setdefault("comments", [])
                        comments.append(line[1:].lstrip())
                    except KeyError:
                        log.debug(
                            "Found comment in %s which does not appear to "
                            "belong to any repo section: %s",
                            filename,
                            line,
                        )
            elif line.startswith("[") and line.endswith("]"):
                section = line[1:-1]

    return (headers, salt.utils.data.decode(config))


def file_list(*packages, **kwargs):
    """
    .. versionadded:: 2014.1.0

    List the files that belong to a package. Not specifying any packages will
    return a list of *every* file on the system's rpm database (not generally
    recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    """
    return __salt__["lowpkg.file_list"](*packages)


def file_dict(*packages, **kwargs):
    """
    .. versionadded:: 2014.1.0

    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of *every* file on the system's
    rpm database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    """
    return __salt__["lowpkg.file_dict"](*packages)


def owner(*paths, **kwargs):
    """
    .. versionadded:: 2014.7.0

    Return the name of the package that owns the file. Multiple file paths can
    be passed. Like :mod:`pkg.version <salt.modules.yumpkg.version>`, if a
    single path is passed, a string will be returned, and if multiple paths are
    passed, a dictionary of file/package name pairs will be returned.

    If the file is not owned by a package, or is not present on the minion,
    then an empty string will be returned for that path.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.owner /usr/bin/apachectl
        salt '*' pkg.owner /usr/bin/apachectl /etc/httpd/conf/httpd.conf
    """
    if not paths:
        return ""
    ret = {}
    cmd_prefix = ["rpm", "-qf", "--queryformat", "%{name}"]
    for path in paths:
        ret[path] = __salt__["cmd.run_stdout"](
            cmd_prefix + [path], output_loglevel="trace", python_shell=False
        )
        if "not owned" in ret[path].lower():
            ret[path] = ""
    if len(ret) == 1:
        return next(iter(ret.values()))
    return ret


def modified(*packages, **flags):
    """
    List the modified files that belong to a package. Not specifying any packages
    will return a list of _all_ modified files on the system's RPM database.

    .. versionadded:: 2015.5.0

    Filtering by flags (True or False):

    size
        Include only files where size changed.

    mode
        Include only files which file's mode has been changed.

    checksum
        Include only files which MD5 checksum has been changed.

    device
        Include only files which major and minor numbers has been changed.

    symlink
        Include only files which are symbolic link contents.

    owner
        Include only files where owner has been changed.

    group
        Include only files where group has been changed.

    time
        Include only files where modification time of the file has been
        changed.

    capabilities
        Include only files where capabilities differ or not. Note: supported
        only on newer RPM versions.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.modified
        salt '*' pkg.modified httpd
        salt '*' pkg.modified httpd postfix
        salt '*' pkg.modified httpd owner=True group=False
    """

    return __salt__["lowpkg.modified"](*packages, **flags)


@salt.utils.decorators.path.which("yumdownloader")
def download(*packages, **kwargs):
    """
    .. versionadded:: 2015.5.0

    Download packages to the local disk. Requires ``yumdownloader`` from
    ``yum-utils`` package.

    .. note::

        ``yum-utils`` will already be installed on the minion if the package
        was installed from the Fedora / EPEL repositories.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.download httpd
        salt '*' pkg.download httpd postfix
    """
    if not packages:
        raise SaltInvocationError("No packages were specified")

    CACHE_DIR = "/var/cache/yum/packages"
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    cached_pkgs = os.listdir(CACHE_DIR)
    to_purge = []
    for pkg in packages:
        to_purge.extend(
            [
                os.path.join(CACHE_DIR, x)
                for x in cached_pkgs
                if x.startswith("{}-".format(pkg))
            ]
        )
    for purge_target in set(to_purge):
        log.debug("Removing cached package %s", purge_target)
        try:
            os.unlink(purge_target)
        except OSError as exc:
            log.error("Unable to remove %s: %s", purge_target, exc)

    cmd = ["yumdownloader", "-q", "--destdir={}".format(CACHE_DIR)]
    cmd.extend(packages)
    __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)
    ret = {}
    for dld_result in os.listdir(CACHE_DIR):
        if not dld_result.endswith(".rpm"):
            continue
        pkg_name = None
        pkg_file = None
        for query_pkg in packages:
            if dld_result.startswith("{}-".format(query_pkg)):
                pkg_name = query_pkg
                pkg_file = dld_result
                break
        if pkg_file is not None:
            ret[pkg_name] = os.path.join(CACHE_DIR, pkg_file)

    if not ret:
        raise CommandExecutionError(
            "Unable to download any of the following packages: {}".format(
                ", ".join(packages)
            )
        )

    failed = [x for x in packages if x not in ret]
    if failed:
        ret["_error"] = "The following package(s) failed to download: {}".format(
            ", ".join(failed)
        )
    return ret


def diff(*paths, **kwargs):
    """
    Return a formatted diff between current files and original in a package.
    NOTE: this function includes all files (configuration and not), but does
    not work on binary content.

    :param path: Full path to the installed file
    :return: Difference string or raises and exception if examined file is binary.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.diff /etc/apache2/httpd.conf /etc/sudoers
    """
    ret = {}

    pkg_to_paths = {}
    for pth in paths:
        pth_pkg = __salt__["lowpkg.owner"](pth)
        if not pth_pkg:
            ret[pth] = os.path.exists(pth) and "Not managed" or "N/A"
        else:
            if pkg_to_paths.get(pth_pkg) is None:
                pkg_to_paths[pth_pkg] = []
            pkg_to_paths[pth_pkg].append(pth)

    if pkg_to_paths:
        local_pkgs = __salt__["pkg.download"](*pkg_to_paths.keys())
        for pkg, files in pkg_to_paths.items():
            for path in files:
                ret[path] = (
                    __salt__["lowpkg.diff"](local_pkgs[pkg]["path"], path)
                    or "Unchanged"
                )

    return ret


def _get_patches(installed_only=False):
    """
    List all known patches in repos.
    """
    patches = {}

    cmd = [_yum(), "--quiet", "updateinfo", "list", "all"]
    ret = __salt__["cmd.run_stdout"](cmd, python_shell=False)
    for line in salt.utils.itertools.split(ret, os.linesep):
        inst, advisory_id, sev, pkg = re.match(
            r"([i|\s]) ([^\s]+) +([^\s]+) +([^\s]+)", line
        ).groups()
        if advisory_id not in patches:
            patches[advisory_id] = {
                "installed": True if inst == "i" else False,
                "summary": [pkg],
            }
        else:
            patches[advisory_id]["summary"].append(pkg)
            if inst != "i":
                patches[advisory_id]["installed"] = False

    if installed_only:
        patches = {k: v for k, v in patches.items() if v["installed"]}
    return patches


def list_patches(refresh=False, **kwargs):
    """
    .. versionadded:: 2017.7.0

    List all known advisory patches from available repos.

    refresh
        force a refresh if set to True.
        If set to False (default) it depends on yum if a refresh is
        executed.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_patches
    """
    if refresh:
        refresh_db()

    return _get_patches()


def list_installed_patches(**kwargs):
    """
    .. versionadded:: 2017.7.0

    List installed advisory patches on the system.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_installed_patches
    """
    return _get_patches(installed_only=True)
