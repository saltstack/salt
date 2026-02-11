"""
Generic package functions for salt-ssh in bundled (onedir) environments.

This module exists as a **fallback** for salt-ssh runs where the normal OS
package provider (for example, ``yumpkg``) cannot be loaded because optional
system bindings are missing from the bundled Python environment. A common
symptom is:

    ``'pkg.version' is not available.``

The aim is not to fully replace native providers, but to ensure that simple
read-only functions used during Jinja/state rendering (like ``pkg.version``)
remain available under salt-ssh.
"""

import fnmatch
import logging

import salt.utils.data
import salt.utils.path
import salt.utils.pkg
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Only load as a fallback for salt-ssh when running from a bundled (onedir)
    Python where the normal provider cannot load.
    """
    # Be conservative: this module should not replace native providers on
    # regular minions.
    if __opts__.get("file_client", "remote") != "local":
        return (False, "pkg fallback only loads for file_client=local (salt-ssh)")

    if not salt.utils.pkg.check_bundled():
        return (False, "pkg fallback only loads in bundled (onedir) environments")

    # If system bindings are available, allow the native provider to load.
    if not salt.utils.pkg.onedir_missing_pkg_bindings():
        return (False, "native pkg provider bindings are available")

    return __virtualname__


def _parse_rpm_qa(output):
    """
    Parse ``rpm -qa`` output which is formatted as ``name<TAB>version``.
    """
    pkgs = {}
    for line in salt.utils.stringutils.to_str(output).splitlines():
        if not line.strip():
            continue
        try:
            name, ver = line.split("\t", 1)
        except ValueError:
            continue
        pkgs.setdefault(name, []).append(ver)
    return pkgs


def _parse_dpkg_query(output):
    """
    Parse ``dpkg-query`` output which is formatted as ``name<TAB>version``.
    """
    pkgs = {}
    for line in salt.utils.stringutils.to_str(output).splitlines():
        if not line.strip():
            continue
        try:
            name, ver = line.split("\t", 1)
        except ValueError:
            continue
        pkgs.setdefault(name, []).append(ver)
    return pkgs


def list_pkgs(versions_as_list=False, **kwargs):
    """
    List installed packages using system package manager CLI tools.

    This is a limited implementation intended for salt-ssh Jinja/state rendering.
    """
    __salt__["cmd.retcode"]  # make sure cmd module is available
    versions_as_list = salt.utils.data.is_true(versions_as_list)

    if salt.utils.path.which("rpm"):
        out = __salt__["cmd.run_stdout"](
            ["rpm", "-qa", "--qf", r"%{NAME}\t%{VERSION}-%{RELEASE}\n"],
            python_shell=False,
            ignore_retcode=False,
        )
        pkgs = _parse_rpm_qa(out)
    elif salt.utils.path.which("dpkg-query"):
        out = __salt__["cmd.run_stdout"](
            ["dpkg-query", "-W", "-f=${Package}\t${Version}\n"],
            python_shell=False,
            ignore_retcode=False,
        )
        pkgs = _parse_dpkg_query(out)
    else:
        raise CommandExecutionError(
            "No supported package query command found (rpm or dpkg-query)"
        )

    if not versions_as_list:
        # Reduce lists to the first version string, aligning with typical pkg providers
        for name, vers in list(pkgs.items()):
            pkgs[name] = vers[0] if vers else ""
    return pkgs


def version(*names, **kwargs):
    """
    Return installed version(s) for the named package(s).

    Matches the common ``pkg.version`` behavior: for one name, returns a string;
    for multiple names, returns a dict.
    """
    versions_as_list = salt.utils.data.is_true(kwargs.pop("versions_as_list", False))
    pkgs = list_pkgs(versions_as_list=True, **kwargs)

    ret = {}
    pkg_glob = False
    for name in names:
        if "*" in name:
            pkg_glob = True
            for match in fnmatch.filter(pkgs, name):
                ret[match] = pkgs.get(match, [])
        else:
            ret[name] = pkgs.get(name, [])

    if not versions_as_list:
        for k in list(ret):
            v = ret[k]
            ret[k] = v[0] if v else ""

    if len(ret) == 1 and not pkg_glob:
        return next(iter(ret.values()), "")
    return ret


