"""
:maintainer:    Alberto Planas <aplanas@suse.com>
:maturity:      new
:depends:       None
:platform:      Linux
"""

import logging

import salt.exceptions

log = logging.getLogger(__name__)

# Define not exported variables from Salt, so this can be imported as
# a normal module
try:
    __salt__
    __utils__
except NameError:
    __salt__ = {}
    __utils__ = {}


def __virtual__():
    """
    transactional-update command is required.
    """
    if __utils__["path.which"]("transactional-update"):
        return True
    else:
        return (False, "Module transactional_update requires a transactional system")


def _global_params(self_update, snapshot=None):
    """Utility function to prepare common global parameters."""
    params = ["--non-interactive", "--drop-if-no-change"]
    if self_update is False:
        params.append("--no-selfupdate")
    if snapshot and snapshot != "continue":
        params.extend(["--continue", snapshot])
    elif snapshot:
        params.append("--continue")
    return params


def _pkg_params(pkg, pkgs, args):
    """Utility function to prepare common package parameters."""
    params = []

    if not pkg and not pkgs:
        raise salt.exceptions.CommandExecutionError("Provide pkg or pkgs parameters")

    if args and isinstance(args, str):
        params.extend(args.split())
    elif args and isinstance(args, list):
        params.extend(args)

    if pkg:
        params.append(pkg)

    if pkgs and isinstance(pkgs, str):
        params.extend(pkgs.split())
    elif pkgs and isinstance(pkgs, list):
        params.extend(pkgs)

    return params


def _cmd(cmd, retcode=False):
    """Utility function to run commands."""
    result = __salt__["cmd.run_all"](cmd)
    if retcode:
        return result["retcode"]

    if result["retcode"]:
        raise salt.exceptions.CommandExecutionError(result["stderr"])

    return result["stdout"]


def transactional():
    """Check if the system is a transactional system

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update transactional

    """
    return bool(__utils__["path.which"]("transactional-update"))


def in_transaction():
    """Check if Salt is executing while in a transaction

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update in_transaction

    """
    return transactional() and __salt__["chroot.in_chroot"]()


def cleanup(self_update=False):
    """Mark unused snapshots for snapper removal.

    If the current root filesystem is identical to the active root
    filesystem (means after a reboot, before transactional-update
    creates a new snapshot with updates), all old snapshots without a
    cleanup algorithm get a cleanup algorithm set. This is to make
    sure, that old snapshots will be deleted by snapper. See the
    section about cleanup algorithms in snapper(8).

    Also removes all unreferenced (and thus unused) /etc overlay
    directories in /var/lib/overlay.

    self_update
        Check for newer transactional-update versions.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update cleanup

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update))
    cmd.append("cleanup")
    return _cmd(cmd)


def grub_cfg(self_update=False, snapshot=None):
    """Regenerate grub.cfg

    grub2-mkconfig(8) is called to create a new /boot/grub2/grub.cfg
    configuration file for the bootloader.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update grub_cfg snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("grub.cfg")
    return _cmd(cmd)


def bootloader(self_update=False, snapshot=None):
    """Reinstall the bootloader

    Same as grub.cfg, but will also rewrite the bootloader itself.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update bootloader snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("bootloader")
    return _cmd(cmd)


def initrd(self_update=False, snapshot=None):
    """Regenerate initrd

    A new initrd is created in a snapshot.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update initrd snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("initrd")
    return _cmd(cmd)


def kdump(self_update=False, snapshot=None):
    """Regenerate kdump initrd

    A new initrd for kdump is created in a snapshot.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update kdump snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("kdump")
    return _cmd(cmd)


def run(command, self_update=False, snapshot=None):
    """Run a command in a new snapshot

    Execute the command inside a new snapshot. By default this snaphot
    will remain, but if --drop-if-no-chage is set, the new snapshot
    will be dropped if there is no change in the file system.

    command
        Command with parameters that will be executed (as string or
        array)

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update run "mkdir /tmp/dir" snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("run")
    if isinstance(command, str):
        cmd.extend(command.split())
    elif isinstance(command, list):
        cmd.extend(command)
    else:
        raise salt.exceptions.CommandExecutionError("Command parameter not recognized")
    return _cmd(cmd)


def reboot(self_update=False):
    """Reboot after update

    Trigger a reboot after updating the system.

    Several different reboot methods are supported, configurable via
    the REBOOT_METHOD configuration option in
    transactional-update.conf(5). By default rebootmgrd(8) will be
    used to reboot the system according to the configured policies if
    the service is running, otherwise systemctl reboot will be called.

    self_update
        Check for newer transactional-update versions.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update reboot

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update))
    cmd.append("reboot")
    return _cmd(cmd)


def dup(self_update=False, snapshot=None):
    """Call 'zypper dup'

    If new updates are available, a new snapshot is created and zypper
    dup --no-allow-vendor-change is used to update the
    snapshot. Afterwards, the snapshot is activated and will be used
    as the new root filesystem during next boot.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update dup snapshot="continue"
    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("dup")
    return _cmd(cmd)


def up(self_update=False, snapshot=None):
    """Call 'zypper up'

    If new updates are available, a new snapshot is created and zypper
    up is used to update the snapshot. Afterwards, the snapshot is
    activated and will be used as the new root filesystem during next
    boot.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update up snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("up")
    return _cmd(cmd)


def patch(self_update=False, snapshot=None):
    """Call 'zypper patch'

    If new updates are available, a new snapshot is created and zypper
    patch is used to update the snapshot. Afterwards, the snapshot is
    activated and will be used as the new root filesystem during next
    boot.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update patch snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("patch")
    return _cmd(cmd)


def migration(self_update=False, snapshot=None):
    """Updates systems registered via SCC / SMT

    On systems which are registered against the SUSE Customer Center
    (SCC) or SMT, a migration to a new version of the installed
    products can be made with this option.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update migration snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("migration")
    return _cmd(cmd)


def pkg_install(pkg=None, pkgs=None, args=None, self_update=False, snapshot=None):
    """Install individual packages

    Installs additional software. See the install description in the
    "Package Management Commands" section of zypper's man page for all
    available arguments.

    pkg
        Package name to install

    pkgs
        List of packages names to install

    args
        String or list of extra parameters for zypper

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update pkg_install pkg=emacs snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.extend(["pkg", "install"])
    cmd.extend(_pkg_params(pkg, pkgs, args))
    return _cmd(cmd)


def pkg_remove(pkg=None, pkgs=None, args=None, self_update=False, snapshot=None):
    """Remove individual packages

    Removes installed software. See the remove description in the
    "Package Management Commands" section of zypper's man page for all
    available arguments.

    pkg
        Package name to install

    pkgs
        List of packages names to install

    args
        String or list of extra parameters for zypper

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update pkg_remove pkg=vim snapshot="continue"
    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.extend(["pkg", "remove"])
    cmd.extend(_pkg_params(pkg, pkgs, args))
    return _cmd(cmd)


def pkg_update(pkg=None, pkgs=None, args=None, self_update=False, snapshot=None):
    """Updates individual packages

    Update selected software. See the update description in the
    "Update Management Commands" section of zypper's man page for all
    available arguments.

    pkg
        Package name to install

    pkgs
        List of packages names to install

    args
        String or list of extra parameters for zypper

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update pkg_update pkg=emacs snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.extend(["pkg", "update"])
    cmd.extend(_pkg_params(pkg, pkgs, args))
    return _cmd(cmd)


def rollback(snapshot=None):
    """Set the current, given or last working snapshot as default snapshot

    Sets the default root file system. On a read-only system the root
    file system is set directly using btrfs. On read-write systems
    snapper(8) rollback is called.

    If no snapshot number is given, the current root file system is
    set as the new default root file system. Otherwise number can
    either be a snapshot number (as displayed by snapper list) or the
    word last. last will try to reset to the latest working snapshot.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "last" to indicate the last working snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update rollback

    """
    if (
        snapshot
        and isinstance(snapshot, str)
        and snapshot != "last"
        and not snapshot.isnumeric()
    ):
        raise salt.exceptions.CommandExecutionError(
            "snapshot should be a number or 'last'"
        )
    cmd = ["transactional-update"]
    cmd.append("rollback")
    if snapshot:
        cmd.append(snapshot)
    return _cmd(cmd)


def pending_transaction():
    """Check if there is a pending transaction

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update pending_transaction

    """
    cmd = ["snapper", "--no-dbus", "list", "--columns", "number"]
    snapshots = _cmd(cmd)

    # If we are running inside a transaction, we do not have a good
    # way yet to detect a pending transaction
    if in_transaction():
        raise salt.exceptions.CommandExecutionError(
            "pending_transaction cannot be executed inside a transaction"
        )
    return any(snapshot.endswith("+") for snapshot in snapshots)
