"""
Manage Linux kernel packages on YUM-based systems
"""

import functools
import logging

import salt.modules.yumpkg
import salt.utils.data
import salt.utils.functools
import salt.utils.systemd
from salt.exceptions import CommandExecutionError
from salt.utils.versions import LooseVersion

log = logging.getLogger(__name__)

__virtualname__ = "kernelpkg"

# Import functions from yumpkg
# pylint: disable=invalid-name, protected-access
_yum = salt.utils.functools.namespaced_function(salt.modules.yumpkg._yum, globals())
# pylint: enable=invalid-name, protected-access


def __virtual__():
    """
    Load this module on RedHat-based systems only
    """
    if __grains__.get("os_family", "") == "RedHat":
        return __virtualname__
    elif __grains__.get("os", "").lower() in (
        "amazon",
        "xcp",
        "xenserver",
        "virtuozzolinux",
    ):
        return __virtualname__

    return False, "Module kernelpkg_linux_yum: no YUM based system detected"


def active():
    """
    Return the version of the running kernel.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.active
    """
    if "pkg.normalize_name" in __salt__:
        return __salt__["pkg.normalize_name"](__grains__["kernelrelease"])

    return __grains__["kernelrelease"]


def list_installed():
    """
    Return a list of all installed kernels.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.list_installed
    """
    result = __salt__["pkg.version"](_package_name(), versions_as_list=True)
    if result is None:
        return []

    return sorted(result, key=functools.cmp_to_key(_cmp_version))


def latest_available():
    """
    Return the version of the latest kernel from the package repositories.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.latest_available
    """
    result = __salt__["pkg.latest_version"](_package_name())
    if result == "":
        result = latest_installed()
    return result


def latest_installed():
    """
    Return the version of the latest installed kernel.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.latest_installed

    .. note::
        This function may not return the same value as
        :py:func:`~salt.modules.kernelpkg_linux_yum.active` if a new kernel
        has been installed and the system has not yet been rebooted.
        The :py:func:`~salt.modules.kernelpkg_linux_yum.needs_reboot` function
        exists to detect this condition.
    """
    pkgs = list_installed()
    if pkgs:
        return pkgs[-1]

    return None


def needs_reboot():
    """
    Detect if a new kernel version has been installed but is not running.
    Returns True if a new kernel is installed, False otherwise.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.needs_reboot
    """
    return LooseVersion(active()) < LooseVersion(latest_installed())


def upgrade(reboot=False, at_time=None):
    """
    Upgrade the kernel and optionally reboot the system.

    reboot : False
        Request a reboot if a new kernel is available.

    at_time : immediate
        Schedule the reboot at some point in the future. This argument
        is ignored if ``reboot=False``. See
        :py:func:`~salt.modules.system.reboot` for more details
        on this argument.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.upgrade
        salt '*' kernelpkg.upgrade reboot=True at_time=1

    .. note::
        An immediate reboot often shuts down the system before the minion has a
        chance to return, resulting in errors. A minimal delay (1 minute) is
        useful to ensure the result is delivered to the master.
    """
    result = __salt__["pkg.upgrade"](name=_package_name())
    _needs_reboot = needs_reboot()

    ret = {
        "upgrades": result,
        "active": active(),
        "latest_installed": latest_installed(),
        "reboot_requested": reboot,
        "reboot_required": _needs_reboot,
    }

    if reboot and _needs_reboot:
        log.warning("Rebooting system due to kernel upgrade")
        __salt__["system.reboot"](at_time=at_time)

    return ret


def upgrade_available():
    """
    Detect if a new kernel version is available in the repositories.
    Returns True if a new kernel is available, False otherwise.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.upgrade_available
    """
    return LooseVersion(latest_available()) > LooseVersion(latest_installed())


def remove(release):
    """
    Remove a specific version of the kernel.

    release
        The release number of an installed kernel. This must be the entire release
        number as returned by :py:func:`~salt.modules.kernelpkg_linux_yum.list_installed`,
        not the package name.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.remove 3.10.0-327.el7
    """
    if release not in list_installed():
        raise CommandExecutionError(f"Kernel release '{release}' is not installed")

    if release == active():
        raise CommandExecutionError("Active kernel cannot be removed")

    target = f"{_package_name()}-{release}"
    log.info("Removing kernel package %s", target)
    old = __salt__["pkg.list_pkgs"]()

    # Build the command string
    cmd = []
    if salt.utils.systemd.has_scope(__context__) and __salt__["config.get"](
        "systemd.scope", True
    ):
        cmd.extend(["systemd-run", "--scope"])
    cmd.extend([_yum(), "-y", "remove", target])  # pylint: disable=not-callable

    # Execute the command
    out = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    # Look for the changes in installed packages
    __context__.pop("pkg.list_pkgs", None)
    new = __salt__["pkg.list_pkgs"]()
    ret = salt.utils.data.compare_dicts(old, new)

    # Look for command execution errors
    if out["retcode"] != 0:
        raise CommandExecutionError(
            "Error occurred removing package(s)",
            info={"errors": [out["stderr"]], "changes": ret},
        )

    return {"removed": [target]}


def cleanup(keep_latest=True):
    """
    Remove all unused kernel packages from the system.

    keep_latest : True
        In the event that the active kernel is not the latest one installed, setting this to True
        will retain the latest kernel package, in addition to the active one. If False, all kernel
        packages other than the active one will be removed.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.cleanup
    """
    removed = []

    # Loop over all installed kernel packages
    for kernel in list_installed():

        # Keep the active kernel package
        if kernel == active():
            continue

        # Optionally keep the latest kernel package
        if keep_latest and kernel == latest_installed():
            continue

        # Remove the kernel package
        removed.extend(remove(kernel)["removed"])

    return {"removed": removed}


def _package_name():
    """
    Return static string for the package name
    """
    return "kernel"


def _cmp_version(item1, item2):
    """
    Compare function for package version sorting
    """
    vers1 = LooseVersion(item1)
    vers2 = LooseVersion(item2)

    if vers1 < vers2:
        return -1
    if vers1 > vers2:
        return 1
    return 0
