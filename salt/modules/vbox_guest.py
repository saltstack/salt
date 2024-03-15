"""
VirtualBox Guest Additions installer
"""

import contextlib
import functools
import glob
import logging
import os
import re
import tempfile

log = logging.getLogger(__name__)
__virtualname__ = "vbox_guest"
_additions_dir_prefix = "VBoxGuestAdditions"
_shared_folders_group = "vboxsf"


def __virtual__():
    """
    Set the vbox_guest module if the OS Linux
    """
    if __grains__.get("kernel", "") not in ("Linux",):
        return (
            False,
            "The vbox_guest execution module failed to load: only available on Linux"
            " systems.",
        )
    return __virtualname__


def additions_mount():
    """
    Mount VirtualBox Guest Additions CD to the temp directory.

    To connect VirtualBox Guest Additions via VirtualBox graphical interface
    press 'Host+D' ('Host' is usually 'Right Ctrl').

    CLI Example:

    .. code-block:: bash

        salt '*' vbox_guest.additions_mount

    :return: True or OSError exception
    """
    mount_point = tempfile.mkdtemp()
    ret = __salt__["mount.mount"](mount_point, "/dev/cdrom")
    if ret is True:
        return mount_point
    else:
        raise OSError(ret)


def additions_umount(mount_point):
    """
    Unmount VirtualBox Guest Additions CD from the temp directory.

    CLI Example:

    .. code-block:: bash

        salt '*' vbox_guest.additions_umount

    :param mount_point: directory VirtualBox Guest Additions is mounted to
    :return: True or an string with error
    """
    ret = __salt__["mount.umount"](mount_point)
    if ret:
        os.rmdir(mount_point)
    return ret


@contextlib.contextmanager
def _additions_mounted():
    mount_point = additions_mount()
    yield mount_point
    additions_umount(mount_point)


def _return_mount_error(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except OSError as e:
            return str(e)

    return wrapper


def _additions_install_program_path(mount_point):
    mount_points = {
        "Linux": "VBoxLinuxAdditions.run",
        "Solaris": "VBoxSolarisAdditions.pkg",
        "Windows": "VBoxWindowsAdditions.exe",
    }
    return os.path.join(mount_point, mount_points[__grains__.get("kernel", "")])


def _additions_install_opensuse(**kwargs):
    kernel_type = re.sub(r"^(\d|\.|-)*", "", __grains__.get("kernelrelease", ""))
    kernel_devel = f"kernel-{kernel_type}-devel"
    return __states__["pkg.installed"](None, pkgs=["make", "gcc", kernel_devel])


def _additions_install_ubuntu(**kwargs):
    return __states__["pkg.installed"](None, pkgs=["dkms"])


def _additions_install_fedora(**kwargs):
    return __states__["pkg.installed"](None, pkgs=["dkms", "gcc"])


def _additions_install_linux(mount_point, **kwargs):
    reboot = kwargs.pop("reboot", False)
    restart_x11 = kwargs.pop("restart_x11", False)
    upgrade_os = kwargs.pop("upgrade_os", False)
    if upgrade_os:
        __salt__["pkg.upgrade"]()
    # dangerous: do not call variable `os` as it will hide os module
    guest_os = __grains__.get("os", "")
    if guest_os == "openSUSE":
        _additions_install_opensuse(**kwargs)
    elif guest_os == "ubuntu":
        _additions_install_ubuntu(**kwargs)
    elif guest_os == "fedora":
        _additions_install_fedora(**kwargs)
    else:
        log.warning("%s is not fully supported yet.", guest_os)
    installer_path = _additions_install_program_path(mount_point)
    installer_ret = __salt__["cmd.run_all"](installer_path)
    if installer_ret["retcode"] in (0, 1):
        if reboot:
            __salt__["system.reboot"]()
        elif restart_x11:
            raise NotImplementedError("Restarting x11 is not supported yet.")
        else:
            # VirtualBox script enables module itself, need to restart OS
            # anyway, probably don't need that.
            # for service in ('vboxadd', 'vboxadd-service', 'vboxadd-x11'):
            #     __salt__['service.start'](service)
            pass
        return additions_version()
    elif installer_ret["retcode"] in (127, "127"):
        return (
            "'{}' not found on CD. Make sure that VirtualBox Guest "
            "Additions CD is attached to the CD IDE Controller.".format(
                os.path.basename(installer_path)
            )
        )
    else:
        return installer_ret["stderr"]


@_return_mount_error
def additions_install(**kwargs):
    """
    Install VirtualBox Guest Additions. Uses the CD, connected by VirtualBox.

    To connect VirtualBox Guest Additions via VirtualBox graphical interface
    press 'Host+D' ('Host' is usually 'Right Ctrl').

    See https://www.virtualbox.org/manual/ch04.html#idp52733088 for more details.

    CLI Example:

    .. code-block:: bash

        salt '*' vbox_guest.additions_install
        salt '*' vbox_guest.additions_install reboot=True
        salt '*' vbox_guest.additions_install upgrade_os=True

    :param reboot: reboot computer to complete installation
    :type reboot: bool
    :param upgrade_os: upgrade OS (to ensure the latests version of kernel and developer tools are installed)
    :type upgrade_os: bool
    :return: version of VirtualBox Guest Additions or string with error
    """
    with _additions_mounted() as mount_point:
        kernel = __grains__.get("kernel", "")
        if kernel == "Linux":
            return _additions_install_linux(mount_point, **kwargs)


def _additions_dir():
    root = "/opt"
    dirs = glob.glob(os.path.join(root, _additions_dir_prefix) + "*")
    if dirs:
        return dirs[0]
    else:
        raise OSError("No VirtualBox Guest Additions dirs found!")


def _additions_remove_linux_run(cmd):
    uninstaller_ret = __salt__["cmd.run_all"](cmd)
    return uninstaller_ret["retcode"] in (0,)


def _additions_remove_linux(**kwargs):
    try:
        return _additions_remove_linux_run(
            os.path.join(_additions_dir(), "uninstall.sh")
        )
    except OSError:
        return False


def _additions_remove_linux_use_cd(mount_point, **kwargs):
    force = kwargs.pop("force", False)
    args = ""
    if force:
        args += "--force"
    return _additions_remove_linux_run(
        "{program} uninstall {args}".format(
            program=_additions_install_program_path(mount_point), args=args
        )
    )


@_return_mount_error
def _additions_remove_use_cd(**kwargs):
    """
    Remove VirtualBox Guest Additions.

    It uses the CD, connected by VirtualBox.
    """

    with _additions_mounted() as mount_point:
        kernel = __grains__.get("kernel", "")
        if kernel == "Linux":
            return _additions_remove_linux_use_cd(mount_point, **kwargs)


def additions_remove(**kwargs):
    """
    Remove VirtualBox Guest Additions.

    Firstly it tries to uninstall itself by executing
    '/opt/VBoxGuestAdditions-VERSION/uninstall.run uninstall'.
    It uses the CD, connected by VirtualBox if it failes.

    CLI Example:

    .. code-block:: bash

        salt '*' vbox_guest.additions_remove
        salt '*' vbox_guest.additions_remove force=True

    :param force: force VirtualBox Guest Additions removing
    :type force: bool
    :return: True if VirtualBox Guest Additions were removed successfully else False

    """
    kernel = __grains__.get("kernel", "")
    if kernel == "Linux":
        ret = _additions_remove_linux()
    if not ret:
        ret = _additions_remove_use_cd(**kwargs)
    return ret


def additions_version():
    """
    Check VirtualBox Guest Additions version.

    CLI Example:

    .. code-block:: bash

        salt '*' vbox_guest.additions_version

    :return: version of VirtualBox Guest Additions or False if they are not installed
    """
    try:
        d = _additions_dir()
    except OSError:
        return False
    if d and len(os.listdir(d)) > 0:
        return re.sub(rf"^{_additions_dir_prefix}-", "", os.path.basename(d))
    return False


def grant_access_to_shared_folders_to(name, users=None):
    """
    Grant access to auto-mounted shared folders to the users.

    User is specified by its name. To grant access for several users use argument `users`.
    Access will be denied to the users not listed in `users` argument.

    See https://www.virtualbox.org/manual/ch04.html#sf_mount_auto for more details.

    CLI Example:

    .. code-block:: bash

        salt '*' vbox_guest.grant_access_to_shared_folders_to fred
        salt '*' vbox_guest.grant_access_to_shared_folders_to users ['fred', 'roman']

    :param name: name of the user to grant access to auto-mounted shared folders to
    :type name: str
    :param users: list of names of users to grant access to auto-mounted shared folders to (if specified, `name` will not be taken into account)
    :type users: list of str
    :return: list of users who have access to auto-mounted shared folders
    """
    if users is None:
        users = [name]
    if __salt__["group.members"](_shared_folders_group, ",".join(users)):
        return users
    else:
        if not __salt__["group.info"](_shared_folders_group):
            if not additions_version:
                return (
                    "VirtualBox Guest Additions are not installed. Ιnstall "
                    "them firstly. You can do it with the help of command "
                    "vbox_guest.additions_install."
                )
            else:
                return (
                    "VirtualBox Guest Additions seems to be installed, but "
                    "group '{}' not found. Check your installation and fix "
                    "it. You can uninstall VirtualBox Guest Additions with "
                    "the help of command :py:func:`vbox_guest.additions_remove "
                    "<salt.modules.vbox_guest.additions_remove> (it has "
                    "`force` argument to fix complex situations; use "
                    "it with care) and then install it again. You can do "
                    "it with the help of :py:func:`vbox_guest.additions_install "
                    "<salt.modules.vbox_guest.additions_install>`."
                    "".format(_shared_folders_group)
                )
        else:
            return "Cannot replace members of the '{}' group.".format(
                _shared_folders_group
            )


def list_shared_folders_users():
    """
    List users who have access to auto-mounted shared folders.

    See https://www.virtualbox.org/manual/ch04.html#sf_mount_auto for more details.

    CLI Example:

    .. code-block:: bash

        salt '*' vbox_guest.list_shared_folders_users

    :return: list of users who have access to auto-mounted shared folders
    """
    try:
        return __salt__["group.info"](_shared_folders_group)["members"]
    except KeyError:
        return []
