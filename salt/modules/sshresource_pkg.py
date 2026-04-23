"""
Execution module override for the ``ssh`` resource type — ``pkg.*`` surface.

Implements package management against SSH resources by running the
appropriate package-manager commands on the remote host via the SSH Shell
transport.  Mirrors the interface of ``salt.modules.aptpkg`` /
``salt.modules.yumpkg`` for the functions most commonly called by state
modules (``pkg.installed``, ``pkg.removed``, etc.).

The managing minion detects the remote OS family from the resource grains
and dispatches to the correct package-manager command set at call time.
"""

import logging

# __resource_funcs__ is injected by the per-type loader at runtime.
# pylint: disable=undefined-variable

log = logging.getLogger(__name__)

__virtualname__ = "pkg"


def __virtual__():
    if __opts__.get("resource_type") == "ssh":  # pylint: disable=undefined-variable
        return __virtualname__
    return False, "sshresource_pkg: only loads in an ssh-resource-type loader."


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run(cmd, timeout=None):
    """Run a shell command on the remote resource, return (stdout, retcode)."""
    result = __resource_funcs__["ssh.cmd_run"](
        cmd, timeout=timeout
    )  # pylint: disable=undefined-variable
    return result.get("stdout", ""), result.get("retcode", 1)


def _pkg_manager():
    """
    Return the package-manager command appropriate for the remote OS.

    Inspects the ``os_family`` grain so we can support both Debian/Ubuntu
    (``apt-get``) and RedHat/CentOS (``yum`` / ``dnf``) targets.
    """
    grains = (
        __grains__ if isinstance(__grains__, dict) else __grains__.value()
    )  # pylint: disable=undefined-variable
    os_family = grains.get("os_family", "").lower()
    if os_family in ("debian", "ubuntu"):
        return "apt-get"
    if os_family in ("redhat", "centos", "fedora", "suse"):
        return "yum"
    # Fallback: try apt-get then yum
    return "apt-get"


# ---------------------------------------------------------------------------
# pkg.* surface
# ---------------------------------------------------------------------------


def install(name=None, pkgs=None, sources=None, **kwargs):
    """
    Install one or more packages on the SSH resource.

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:node1' pkg.install curl
        salt -C 'T@ssh:node1' pkg.install pkgs='[curl, git]'
    """
    pkg_mgr = _pkg_manager()
    if pkgs:
        names = " ".join(pkgs if isinstance(pkgs, list) else [pkgs])
    elif name:
        names = name
    else:
        return {}

    env = "DEBIAN_FRONTEND=noninteractive " if "apt" in pkg_mgr else ""
    cmd = f"{env}{pkg_mgr} install -y {names}"
    stdout, retcode = _run(cmd, timeout=kwargs.get("timeout"))

    if retcode != 0:
        log.warning("pkg.install failed for %s: %s", names, stdout)
        return {"result": False, "comment": stdout}
    return {"result": True, "comment": stdout}


def remove(name=None, pkgs=None, **kwargs):
    """
    Remove one or more packages from the SSH resource.

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:node1' pkg.remove curl
    """
    pkg_mgr = _pkg_manager()
    if pkgs:
        names = " ".join(pkgs if isinstance(pkgs, list) else [pkgs])
    elif name:
        names = name
    else:
        return {}

    cmd = f"{pkg_mgr} remove -y {names}"
    stdout, retcode = _run(cmd, timeout=kwargs.get("timeout"))

    if retcode != 0:
        log.warning("pkg.remove failed for %s: %s", names, stdout)
        return {"result": False, "comment": stdout}
    return {"result": True, "comment": stdout}


def version(*names, **kwargs):
    """
    Return the installed version of the given package(s).

    Returns a string for a single package or a dict for multiple packages.

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:node1' pkg.version curl
    """
    grains = (
        __grains__ if isinstance(__grains__, dict) else __grains__.value()
    )  # pylint: disable=undefined-variable
    os_family = grains.get("os_family", "").lower()

    versions = {}
    for name in names:
        if os_family in ("debian", "ubuntu"):
            stdout, retcode = _run(
                f"dpkg-query -W -f='${{Version}}' {name} 2>/dev/null"
            )
        else:
            stdout, retcode = _run(
                f"rpm -q --queryformat '%{{VERSION}}' {name} 2>/dev/null"
            )
        versions[name] = stdout.strip() if retcode == 0 else ""

    if len(names) == 1:
        return versions[names[0]]
    return versions


def list_pkgs(**kwargs):
    """
    List all installed packages on the SSH resource.

    Returns a dict of ``{name: version}``.

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:node1' pkg.list_pkgs
    """
    grains = (
        __grains__ if isinstance(__grains__, dict) else __grains__.value()
    )  # pylint: disable=undefined-variable
    os_family = grains.get("os_family", "").lower()

    if os_family in ("debian", "ubuntu"):
        stdout, _ = _run("dpkg-query -W -f='${Package} ${Version}\\n'")
    else:
        stdout, _ = _run("rpm -qa --queryformat '%{NAME} %{VERSION}-%{RELEASE}\\n'")

    pkgs = {}
    for line in stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            pkgs[parts[0]] = parts[1]
    return pkgs
