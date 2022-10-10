"""
Support for rpm
"""

import datetime
import logging
import os
import re

import salt.utils.decorators.path
import salt.utils.itertools
import salt.utils.path
import salt.utils.pkg.rpm
import salt.utils.versions
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils.versions import LooseVersion

try:
    import rpm

    HAS_RPM = True
except ImportError:
    HAS_RPM = False

try:
    import rpmUtils.miscutils

    HAS_RPMUTILS = True
except ImportError:
    HAS_RPMUTILS = False

try:
    import rpm_vercmp

    HAS_PY_RPM = True
except ImportError:
    HAS_PY_RPM = False


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "lowpkg"


def __virtual__():
    """
    Confine this module to rpm based systems
    """
    if not salt.utils.path.which("rpm"):
        return (
            False,
            "The rpm execution module failed to load: rpm binary is not in the path.",
        )
    try:
        os_grain = __grains__["os"].lower()
        os_family = __grains__["os_family"].lower()
    except Exception:  # pylint: disable=broad-except
        return (
            False,
            "The rpm execution module failed to load: failed to detect os or os_family"
            " grains.",
        )

    enabled = (
        "amazon",
        "xcp",
        "xenserver",
        "virtuozzolinux",
        "virtuozzo",
        "issabel pbx",
        "openeuler",
    )

    if os_family in ["redhat", "suse"] or os_grain in enabled:
        return __virtualname__
    return (
        False,
        "The rpm execution module failed to load: only available on redhat/suse type"
        " systems or amazon, xcp, xenserver, virtuozzolinux, virtuozzo, issabel pbx or openeuler.",
    )


def bin_pkg_info(path, saltenv="base"):
    """
    .. versionadded:: 2015.8.0

    Parses RPM metadata and returns a dictionary of information about the
    package (name, version, etc.).

    path
        Path to the file. Can either be an absolute path to a file on the
        minion, or a salt fileserver URL (e.g. ``salt://path/to/file.rpm``).
        If a salt fileserver URL is passed, the file will be cached to the
        minion so that it can be examined.

    saltenv : base
        Salt fileserver environment from which to retrieve the package. Ignored
        if ``path`` is a local file path on the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.bin_pkg_info /root/salt-2015.5.1-2.el7.noarch.rpm
        salt '*' lowpkg.bin_pkg_info salt://salt-2015.5.1-2.el7.noarch.rpm
    """
    # If the path is a valid protocol, pull it down using cp.cache_file
    if __salt__["config.valid_fileproto"](path):
        newpath = __salt__["cp.cache_file"](path, saltenv)
        if not newpath:
            raise CommandExecutionError(
                "Unable to retrieve {} from saltenv '{}'".format(path, saltenv)
            )
        path = newpath
    else:
        if not os.path.exists(path):
            raise CommandExecutionError("{} does not exist on minion".format(path))
        elif not os.path.isabs(path):
            raise SaltInvocationError("{} does not exist on minion".format(path))

    # REPOID is not a valid tag for the rpm command. Remove it and replace it
    # with 'none'
    queryformat = salt.utils.pkg.rpm.QUERYFORMAT.replace("%{REPOID}", "none")
    output = __salt__["cmd.run_stdout"](
        ["rpm", "-qp", "--queryformat", queryformat, path],
        output_loglevel="trace",
        ignore_retcode=True,
        python_shell=False,
    )
    ret = {}
    pkginfo = salt.utils.pkg.rpm.parse_pkginfo(output, osarch=__grains__["osarch"])
    try:
        for field in pkginfo._fields:
            ret[field] = getattr(pkginfo, field)
    except AttributeError:
        # pkginfo is None
        return None
    return ret


def list_pkgs(*packages, **kwargs):
    """
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    root
        use root as top level directory (default: "/")

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.list_pkgs
    """
    pkgs = {}
    cmd = ["rpm"]
    if kwargs.get("root"):
        cmd.extend(["--root", kwargs["root"]])
    cmd.extend(["-q" if packages else "-qa", "--queryformat", r"%{NAME} %{VERSION}\n"])
    if packages:
        cmd.extend(packages)
    out = __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)
    for line in salt.utils.itertools.split(out, "\n"):
        if "is not installed" in line:
            continue
        comps = line.split()
        pkgs[comps[0]] = comps[1]
    return pkgs


def verify(*packages, **kwargs):
    """
    Runs an rpm -Va on a system, and returns the results in a dict

    root
        use root as top level directory (default: "/")

    Files with an attribute of config, doc, ghost, license or readme in the
    package header can be ignored using the ``ignore_types`` keyword argument

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.verify
        salt '*' lowpkg.verify httpd
        salt '*' lowpkg.verify httpd postfix
        salt '*' lowpkg.verify httpd postfix ignore_types=['config','doc']
    """
    ftypes = {"c": "config", "d": "doc", "g": "ghost", "l": "license", "r": "readme"}
    ret = {}
    ignore_types = kwargs.get("ignore_types", [])
    if not isinstance(ignore_types, (list, str)):
        raise SaltInvocationError(
            "ignore_types must be a list or a comma-separated string"
        )
    if isinstance(ignore_types, str):
        try:
            ignore_types = [x.strip() for x in ignore_types.split(",")]
        except AttributeError:
            ignore_types = [x.strip() for x in str(ignore_types).split(",")]

    verify_options = kwargs.get("verify_options", [])
    if not isinstance(verify_options, (list, str)):
        raise SaltInvocationError(
            "verify_options must be a list or a comma-separated string"
        )
    if isinstance(verify_options, str):
        try:
            verify_options = [x.strip() for x in verify_options.split(",")]
        except AttributeError:
            verify_options = [x.strip() for x in str(verify_options).split(",")]

    cmd = ["rpm"]
    if kwargs.get("root"):
        cmd.extend(["--root", kwargs["root"]])
    cmd.extend(["--" + x for x in verify_options])
    if packages:
        cmd.append("-V")
        # Can't concatenate a tuple, must do a list.extend()
        cmd.extend(packages)
    else:
        cmd.append("-Va")
    out = __salt__["cmd.run_all"](
        cmd, output_loglevel="trace", ignore_retcode=True, python_shell=False
    )

    if not out["stdout"].strip() and out["retcode"] != 0:
        # If there is no stdout and the retcode is 0, then verification
        # succeeded, but if the retcode is nonzero, then the command failed.
        msg = "Failed to verify package(s)"
        if out["stderr"]:
            msg += ": {}".format(out["stderr"])
        raise CommandExecutionError(msg)

    for line in salt.utils.itertools.split(out["stdout"], "\n"):
        fdict = {"mismatch": []}
        if "missing" in line:
            line = " " + line
            fdict["missing"] = True
            del fdict["mismatch"]
        fname = line[13:]
        if line[11:12] in ftypes:
            fdict["type"] = ftypes[line[11:12]]
        if "type" not in fdict or fdict["type"] not in ignore_types:
            if line[0:1] == "S":
                fdict["mismatch"].append("size")
            if line[1:2] == "M":
                fdict["mismatch"].append("mode")
            if line[2:3] == "5":
                fdict["mismatch"].append("md5sum")
            if line[3:4] == "D":
                fdict["mismatch"].append("device major/minor number")
            if line[4:5] == "L":
                fdict["mismatch"].append("readlink path")
            if line[5:6] == "U":
                fdict["mismatch"].append("user")
            if line[6:7] == "G":
                fdict["mismatch"].append("group")
            if line[7:8] == "T":
                fdict["mismatch"].append("mtime")
            if line[8:9] == "P":
                fdict["mismatch"].append("capabilities")
            ret[fname] = fdict
    return ret


def modified(*packages, **flags):
    """
    List the modified files that belong to a package. Not specifying any packages
    will return a list of _all_ modified files on the system's RPM database.

    .. versionadded:: 2015.5.0

    root
        use root as top level directory (default: "/")

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.modified httpd
        salt '*' lowpkg.modified httpd postfix
        salt '*' lowpkg.modified
    """
    cmd = ["rpm"]
    if flags.get("root"):
        cmd.extend(["--root", flags.pop("root")])
    cmd.append("-Va")
    cmd.extend(packages)
    ret = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    data = {}

    # If verification has an output, then it means it failed
    # and the return code will be 1. We are interested in any bigger
    # than 1 code.
    if ret["retcode"] > 1:
        del ret["stdout"]
        return ret
    elif not ret["retcode"]:
        return data

    ptrn = re.compile(r"\s+")
    changes = cfg = f_name = None
    for f_info in salt.utils.itertools.split(ret["stdout"], "\n"):
        f_info = ptrn.split(f_info)
        if len(f_info) == 3:  # Config file
            changes, cfg, f_name = f_info
        else:
            changes, f_name = f_info
            cfg = None
        keys = [
            "size",
            "mode",
            "checksum",
            "device",
            "symlink",
            "owner",
            "group",
            "time",
            "capabilities",
        ]
        changes = list(changes)
        if len(changes) == 8:  # Older RPMs do not support capabilities
            changes.append(".")
        stats = []
        for k, v in zip(keys, changes):
            if v != ".":
                stats.append(k)
        if cfg is not None:
            stats.append("config")
        data[f_name] = stats

    if not flags:
        return data

    # Filtering
    filtered_data = {}
    for f_name, stats in data.items():
        include = True
        for param, pval in flags.items():
            if param.startswith("_"):
                continue
            if (not pval and param in stats) or (pval and param not in stats):
                include = False
                break
        if include:
            filtered_data[f_name] = stats

    return filtered_data


def file_list(*packages, **kwargs):
    """
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's rpm database (not generally
    recommended).

    root
        use root as top level directory (default: "/")

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.file_list httpd
        salt '*' lowpkg.file_list httpd postfix
        salt '*' lowpkg.file_list
    """
    cmd = ["rpm"]
    if kwargs.get("root"):
        cmd.extend(["--root", kwargs["root"]])

    cmd.append("-ql" if packages else "-qla")
    if packages:
        # Can't concatenate a tuple, must do a list.extend()
        cmd.extend(packages)

    ret = __salt__["cmd.run"](
        cmd, output_loglevel="trace", python_shell=False
    ).splitlines()
    return {"errors": [], "files": ret}


def file_dict(*packages, **kwargs):
    """
    List the files that belong to a package, sorted by group. Not specifying
    any packages will return a list of _every_ file on the system's rpm
    database (not generally recommended).

    root
        use root as top level directory (default: "/")

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.file_dict httpd
        salt '*' lowpkg.file_dict httpd postfix
        salt '*' lowpkg.file_dict
    """
    errors = []
    ret = {}
    pkgs = {}
    cmd = ["rpm"]
    if kwargs.get("root"):
        cmd.extend(["--root", kwargs["root"]])
    cmd.extend(["-q" if packages else "-qa", "--queryformat", r"%{NAME} %{VERSION}\n"])
    if packages:
        cmd.extend(packages)
    out = __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)
    for line in salt.utils.itertools.split(out, "\n"):
        if "is not installed" in line:
            errors.append(line)
            continue
        comps = line.split()
        pkgs[comps[0]] = {"version": comps[1]}
    for pkg in pkgs:
        cmd = ["rpm"]
        if kwargs.get("root"):
            cmd.extend(["--root", kwargs["root"]])
        cmd.extend(["-ql", pkg])
        out = __salt__["cmd.run"](
            ["rpm", "-ql", pkg], output_loglevel="trace", python_shell=False
        )
        ret[pkg] = out.splitlines()
    return {"errors": errors, "packages": ret}


def owner(*paths, **kwargs):
    """
    Return the name of the package that owns the file. Multiple file paths can
    be passed. If a single path is passed, a string will be returned,
    and if multiple paths are passed, a dictionary of file/package name pairs
    will be returned.

    If the file is not owned by a package, or is not present on the minion,
    then an empty string will be returned for that path.

    root
        use root as top level directory (default: "/")

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.owner /usr/bin/apachectl
        salt '*' lowpkg.owner /usr/bin/apachectl /etc/httpd/conf/httpd.conf
    """
    if not paths:
        return ""
    ret = {}
    for path in paths:
        cmd = ["rpm"]
        if kwargs.get("root"):
            cmd.extend(["--root", kwargs["root"]])
        cmd.extend(["-qf", "--queryformat", "%{name}", path])
        ret[path] = __salt__["cmd.run_stdout"](
            cmd, output_loglevel="trace", python_shell=False
        )
        if "not owned" in ret[path].lower():
            ret[path] = ""
    if len(ret) == 1:
        return next(iter(ret.values()))
    return ret


@salt.utils.decorators.path.which("rpm2cpio")
@salt.utils.decorators.path.which("cpio")
@salt.utils.decorators.path.which("diff")
def diff(package_path, path):
    """
    Return a formatted diff between current file and original in a package.
    NOTE: this function includes all files (configuration and not), but does
    not work on binary content.

    :param package: Full pack of the RPM file
    :param path: Full path to the installed file
    :return: Difference or empty string. For binary files only a notification.

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.diff /path/to/apache2.rpm /etc/apache2/httpd.conf
    """

    cmd = (
        "rpm2cpio {0} "
        "| cpio -i --quiet --to-stdout .{1} "
        "| diff -u --label 'A {1}' --from-file=- --label 'B {1}' {1}"
    )
    res = __salt__["cmd.shell"](cmd.format(package_path, path), output_loglevel="trace")
    if res and res.startswith("Binary file"):
        return "File '{}' is binary and its content has been modified.".format(path)

    return res


def info(*packages, **kwargs):
    """
    Return a detailed package(s) summary information.
    If no packages specified, all packages will be returned.

    :param packages:

    :param attr:
        Comma-separated package attributes. If no 'attr' is specified, all available attributes returned.

        Valid attributes are:
            version, vendor, release, build_date, build_date_time_t, install_date, install_date_time_t,
            build_host, group, source_rpm, arch, epoch, size, license, signature, packager, url, summary, description.

    :param all_versions:
        Return information for all installed versions of the packages

    :param root:
        use root as top level directory (default: "/")

    :return:

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.info apache2 bash
        salt '*' lowpkg.info apache2 bash attr=version
        salt '*' lowpkg.info apache2 bash attr=version,build_date_iso,size
        salt '*' lowpkg.info apache2 bash attr=version,build_date_iso,size all_versions=True
    """
    all_versions = kwargs.get("all_versions", False)
    # LONGSIZE is not a valid tag for all versions of rpm. If LONGSIZE isn't
    # available, then we can just use SIZE for older versions. See Issue #31366.
    rpm_tags = __salt__["cmd.run_stdout"](
        ["rpm", "--querytags"], python_shell=False
    ).splitlines()
    if "LONGSIZE" in rpm_tags:
        size_tag = "%{LONGSIZE}"
    else:
        size_tag = "%{SIZE}"

    cmd = ["rpm"]
    if kwargs.get("root"):
        cmd.extend(["--root", kwargs["root"]])
    if packages:
        cmd.append("-q")
        cmd.extend(packages)
    else:
        cmd.append("-qa")

    # Construct query format
    attr_map = {
        "name": "name: %{NAME}\\n",
        "relocations": (
            "relocations: %|PREFIXES?{[%{PREFIXES} ]}:{(not relocatable)}|\\n"
        ),
        "version": "version: %{VERSION}\\n",
        "vendor": "vendor: %{VENDOR}\\n",
        "release": "release: %{RELEASE}\\n",
        "epoch": "%|EPOCH?{epoch: %{EPOCH}\\n}|",
        "build_date_time_t": "build_date_time_t: %{BUILDTIME}\\n",
        "build_date": "build_date: %{BUILDTIME}\\n",
        "install_date_time_t": (
            "install_date_time_t: %|INSTALLTIME?{%{INSTALLTIME}}:{(not installed)}|\\n"
        ),
        "install_date": (
            "install_date: %|INSTALLTIME?{%{INSTALLTIME}}:{(not installed)}|\\n"
        ),
        "build_host": "build_host: %{BUILDHOST}\\n",
        "group": "group: %{GROUP}\\n",
        "source_rpm": "source_rpm: %{SOURCERPM}\\n",
        "size": "size: " + size_tag + "\\n",
        "arch": "arch: %{ARCH}\\n",
        "license": "%|LICENSE?{license: %{LICENSE}\\n}|",
        "signature": (
            "signature:"
            " %|DSAHEADER?{%{DSAHEADER:pgpsig}}:{%|RSAHEADER?{%{RSAHEADER:pgpsig}}:"
            "{%|SIGGPG?{%{SIGGPG:pgpsig}}:{%|SIGPGP?{%{SIGPGP:pgpsig}}:{(none)}|}|}|}|\\n"
        ),
        "packager": "%|PACKAGER?{packager: %{PACKAGER}\\n}|",
        "url": "%|URL?{url: %{URL}\\n}|",
        "summary": "summary: %{SUMMARY}\\n",
        "description": "description:\\n%{DESCRIPTION}\\n",
        "edition": "edition: %|EPOCH?{%{EPOCH}:}|%{VERSION}-%{RELEASE}\\n",
    }

    attr = kwargs.get("attr", None) and kwargs["attr"].split(",") or None
    query = list()
    if attr:
        for attr_k in attr:
            if attr_k in attr_map and attr_k != "description":
                query.append(attr_map[attr_k])
        if not query:
            raise CommandExecutionError("No valid attributes found.")
        if "name" not in attr:
            attr.append("name")
            query.append(attr_map["name"])
        if "edition" not in attr:
            attr.append("edition")
            query.append(attr_map["edition"])
    else:
        for attr_k, attr_v in attr_map.items():
            if attr_k != "description":
                query.append(attr_v)
    if attr and "description" in attr or not attr:
        query.append(attr_map["description"])
    query.append("-----\\n")

    cmd = " ".join(cmd)
    call = __salt__["cmd.run_all"](
        cmd + " --queryformat '{}'".format("".join(query)),
        output_loglevel="trace",
        env={"TZ": "UTC"},
        clean_env=True,
        ignore_retcode=True,
    )
    out = call["stdout"]
    _ret = list()
    for pkg_info in re.split(r"----*", out):
        pkg_info = pkg_info.strip()
        if not pkg_info:
            continue
        pkg_info = pkg_info.split(os.linesep)
        if pkg_info[-1].lower().startswith("distribution"):
            pkg_info = pkg_info[:-1]

        pkg_data = dict()
        pkg_name = None
        descr_marker = False
        descr = list()
        for line in pkg_info:
            if descr_marker:
                descr.append(line)
                continue
            line = [item.strip() for item in line.split(":", 1)]
            if len(line) != 2:
                continue
            key, value = line
            if key == "description":
                descr_marker = True
                continue
            if key == "name":
                pkg_name = value

            # Convert Unix ticks into ISO time format
            if key in ["build_date", "install_date"]:
                try:
                    pkg_data[key] = (
                        datetime.datetime.utcfromtimestamp(int(value)).isoformat() + "Z"
                    )
                except ValueError:
                    log.warning('Could not convert "%s" into Unix time', value)
                continue

            # Convert Unix ticks into an Integer
            if key in ["build_date_time_t", "install_date_time_t"]:
                try:
                    pkg_data[key] = int(value)
                except ValueError:
                    log.warning('Could not convert "%s" into Unix time', value)
                continue
            if key not in ["description", "name"] and value:
                pkg_data[key] = value
        if attr and "description" in attr or not attr:
            pkg_data["description"] = os.linesep.join(descr)
        if pkg_name:
            pkg_data["name"] = pkg_name
            _ret.append(pkg_data)

    # Force-sort package data by version,
    # pick only latest versions
    # (in case multiple packages installed, e.g. kernel)
    ret = dict()
    for pkg_data in reversed(sorted(_ret, key=lambda x: LooseVersion(x["edition"]))):
        pkg_name = pkg_data.pop("name")
        # Filter out GPG public keys packages
        if pkg_name.startswith("gpg-pubkey"):
            continue
        if pkg_name not in ret:
            if all_versions:
                ret[pkg_name] = [pkg_data.copy()]
            else:
                ret[pkg_name] = pkg_data.copy()
                del ret[pkg_name]["edition"]
        elif all_versions:
            ret[pkg_name].append(pkg_data.copy())

    return ret


def version_cmp(ver1, ver2, ignore_epoch=False):
    """
    .. versionadded:: 2015.8.9

    Do a cmp-style comparison on two packages. Return -1 if ver1 < ver2, 0 if
    ver1 == ver2, and 1 if ver1 > ver2. Return None if there was a problem
    making the comparison.

    ignore_epoch : False
        Set to ``True`` to ignore the epoch when comparing versions

        .. versionadded:: 2015.8.10,2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '0.2-001' '0.2.0.1-002'
    """
    normalize = lambda x: str(x).split(":", 1)[-1] if ignore_epoch else str(x)
    ver1 = normalize(ver1)
    ver2 = normalize(ver2)

    try:
        cmp_func = None
        if HAS_RPM:
            try:
                cmp_func = rpm.labelCompare
            except AttributeError:
                # Catches corner case where someone has a module named "rpm" in
                # their pythonpath.
                log.debug(
                    "rpm module imported, but it does not have the "
                    "labelCompare function. Not using rpm.labelCompare for "
                    "version comparison."
                )
        elif HAS_PY_RPM:
            cmp_func = rpm_vercmp.vercmp
        else:
            log.warning(
                "Please install a package that provides rpm.labelCompare for "
                "more accurate version comparisons."
            )
        if cmp_func is None and HAS_RPMUTILS:
            try:
                cmp_func = rpmUtils.miscutils.compareEVR
            except AttributeError:
                log.debug("rpmUtils.miscutils.compareEVR is not available")

        if cmp_func is None:
            if salt.utils.path.which("rpmdev-vercmp"):
                log.warning(
                    "Installing the rpmdevtools package may surface dev tools in"
                    " production."
                )

                # rpmdev-vercmp always uses epochs, even when zero
                def _ensure_epoch(ver):
                    def _prepend(ver):
                        return "0:{}".format(ver)

                    try:
                        if ":" not in ver:
                            return _prepend(ver)
                    except TypeError:
                        return _prepend(ver)
                    return ver

                ver1 = _ensure_epoch(ver1)
                ver2 = _ensure_epoch(ver2)
                result = __salt__["cmd.run_all"](
                    ["rpmdev-vercmp", ver1, ver2],
                    python_shell=False,
                    redirect_stderr=True,
                    ignore_retcode=True,
                )
                # rpmdev-vercmp returns 0 on equal, 11 on greater-than, and
                # 12 on less-than.
                if result["retcode"] == 0:
                    return 0
                elif result["retcode"] == 11:
                    return 1
                elif result["retcode"] == 12:
                    return -1
                else:
                    # We'll need to fall back to salt.utils.versions.version_cmp()
                    log.warning(
                        "Failed to interpret results of rpmdev-vercmp output. "
                        "This is probably a bug, and should be reported. "
                        "Return code was %s. Output: %s",
                        result["retcode"],
                        result["stdout"],
                    )
            else:
                log.warning(
                    "Falling back on salt.utils.versions.version_cmp() for version"
                    " comparisons"
                )
        else:
            # If one EVR is missing a release but not the other and they
            # otherwise would be equal, ignore the release. This can happen if
            # e.g. you are checking if a package version 3.2 is satisfied by
            # 3.2-1.
            (ver1_e, ver1_v, ver1_r) = salt.utils.pkg.rpm.version_to_evr(ver1)
            (ver2_e, ver2_v, ver2_r) = salt.utils.pkg.rpm.version_to_evr(ver2)
            if not ver1_r or not ver2_r:
                ver1_r = ver2_r = ""

            if HAS_PY_RPM:
                # handle epoch version comparison first
                # rpm_vercmp.vercmp does not handle epoch version comparison
                ret = salt.utils.versions.version_cmp(ver1_e, ver2_e)
                if ret in (1, -1):
                    return ret
                cmp_result = cmp_func(ver1, ver2)
            else:
                cmp_result = cmp_func(
                    (ver1_e, ver1_v, ver1_r), (ver2_e, ver2_v, ver2_r)
                )
            if cmp_result not in (-1, 0, 1):
                raise CommandExecutionError(
                    "Comparison result '{}' is invalid".format(cmp_result)
                )
            return cmp_result

    except Exception as exc:  # pylint: disable=broad-except
        log.warning(
            "Failed to compare version '%s' to '%s' using RPM: %s", ver1, ver2, exc
        )

    # We would already have normalized the versions at the beginning of this
    # function if ignore_epoch=True, so avoid unnecessary work and just pass
    # False for this value.
    return salt.utils.versions.version_cmp(ver1, ver2, ignore_epoch=False)


def checksum(*paths, **kwargs):
    """
    Return if the signature of a RPM file is valid.

    root
        use root as top level directory (default: "/")

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.checksum /path/to/package1.rpm
        salt '*' lowpkg.checksum /path/to/package1.rpm /path/to/package2.rpm
    """
    ret = dict()

    if not paths:
        raise CommandExecutionError("No package files has been specified.")

    cmd = ["rpm"]
    if kwargs.get("root"):
        cmd.extend(["--root", kwargs["root"]])
    cmd.extend(["-K", "--quiet"])
    for package_file in paths:
        cmd_ = cmd + [package_file]
        ret[package_file] = bool(
            __salt__["file.file_exists"](package_file)
        ) and not __salt__["cmd.retcode"](
            cmd_, ignore_retcode=True, output_loglevel="trace", python_shell=False
        )

    return ret
