"""
Module for rebootmgr
:maintainer:    Alberto Planas <aplanas@suse.com>
:maturity:      new
:depends:       None
:platform:      Linux

.. versionadded:: 3004
"""

import logging
import re

import salt.exceptions

log = logging.getLogger(__name__)


def __virtual__():
    """rebootmgrctl command is required."""
    if __utils__["path.which"]("rebootmgrctl") is not None:
        return True
    else:
        return (False, "Module rebootmgt requires the command rebootmgrctl")


def _cmd(cmd, retcode=False):
    """Utility function to run commands."""
    result = __salt__["cmd.run_all"](cmd)
    if retcode:
        return result["retcode"]

    if result["retcode"]:
        raise salt.exceptions.CommandExecutionError(result["stderr"])

    return result["stdout"]


def version():
    """Return the version of rebootmgrd

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr version

    """
    cmd = ["rebootmgrctl", "--version"]

    return _cmd(cmd).split()[-1]


def is_active():
    """Check if the rebootmgrd is running and active or not.

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr is_active

    """
    cmd = ["rebootmgrctl", "is_active", "--quiet"]

    return _cmd(cmd, retcode=True) == 0


def reboot(order=None):
    """Tells rebootmgr to schedule a reboot.

    With the [now] option, a forced reboot is done, no lock from etcd
    is requested and a set maintenance window is ignored. With the
    [fast] option, a lock from etcd is requested if needed, but a
    defined maintenance window is ignored.

    order
        If specified, can be "now" or "fast"

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr reboot
        salt microos rebootmgt reboot order=now

    """
    if order and order not in ("now", "fast"):
        raise salt.exceptions.CommandExecutionError(
            "Order parameter, if specified, must be 'now' or 'fast'"
        )

    cmd = ["rebootmgrctl", "reboot"]
    if order:
        cmd.append(order)

    return _cmd(cmd)


def cancel():
    """Cancels an already running reboot.

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr cancel

    """
    cmd = ["rebootmgrctl", "cancel"]

    return _cmd(cmd)


def status():
    """Returns the current status of rebootmgrd.

    Valid returned values are:
      0 - No reboot requested
      1 - Reboot requested
      2 - Reboot requested, waiting for maintenance window
      3 - Reboot requested, waiting for etcd lock.

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr status

    """
    cmd = ["rebootmgrctl", "status", "--quiet"]

    return _cmd(cmd, retcode=True)


def set_strategy(strategy=None):
    """A new strategy to reboot the machine is set and written into
    /etc/rebootmgr.conf.

    strategy
        If specified, must be one of those options:

        best-effort - This is the default strategy. If etcd is
            running, etcd-lock is used. If no etcd is running, but a
            maintenance window is specified, the strategy will be
            maint-window. If no maintenance window is specified, the
            machine is immediately rebooted (instantly).

        etcd-lock - A lock at etcd for the specified lock-group will
            be acquired before reboot. If a maintenance window is
            specified, the lock is only acquired during this window.

        maint-window - Reboot does happen only during a specified
            maintenance window. If no window is specified, the
            instantly strategy is followed.

        instantly - Other services will be informed that a reboot will
            happen. Reboot will be done without getting any locks or
            waiting for a maintenance window.

        off - Reboot requests are temporary
            ignored. /etc/rebootmgr.conf is not modified.

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr set_strategy stragegy=off

    """
    if strategy and strategy not in (
        "best-effort",
        "etcd-lock",
        "maint-window",
        "instantly",
        "off",
    ):
        raise salt.exceptions.CommandExecutionError("Strategy parameter not valid")

    cmd = ["rebootmgrctl", "set-strategy"]
    if strategy:
        cmd.append(strategy)

    return _cmd(cmd)


def get_strategy():
    """The currently used reboot strategy of rebootmgrd will be printed.

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr get_strategy

    """
    cmd = ["rebootmgrctl", "get-strategy"]

    return _cmd(cmd).split(":")[-1].strip()


def set_window(time, duration):
    """Set's the maintenance window.

    time
        The format of time is the same as described in
        systemd.time(7).

    duration
         The format of duration is "[XXh][YYm]".

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr set_window time="Thu,Fri 2020-*-1,5 11:12:13" duration=1h

    """
    cmd = ["rebootmgrctl", "set-window", time, duration]

    return _cmd(cmd)


def get_window():
    """The currently set maintenance window will be printed.

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr get_window

    """
    cmd = ["rebootmgrctl", "get-window"]
    window = _cmd(cmd)

    return dict(
        zip(
            ("time", "duration"),
            re.search(
                r"Maintenance window is set to (.*), lasting (.*).", window
            ).groups(),
        )
    )


def set_group(group):
    """Set the group, to which this machine belongs to get a reboot lock
       from etcd.

    group
        Group name

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr set_group group=group_1

    """
    cmd = ["rebootmgrctl", "set-group", group]

    return _cmd(cmd)


def get_group():
    """The currently set lock group for etcd.

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr get_group

    """
    cmd = ["rebootmgrctl", "get-group"]
    group = _cmd(cmd)

    return re.search(r"Etcd lock group is set to (.*)", group).groups()[0]


def set_max(max_locks, group=None):
    """Set the maximal number of hosts in a group, which are allowed to
       reboot at the same time.

    number
        Maximal number of hosts in a group

    group
        Group name

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr set_max 4

    """
    cmd = ["rebootmgrctl", "set-max"]
    if group:
        cmd.extend(["--group", group])
    cmd.append(max_locks)

    return _cmd(cmd)


def lock(machine_id=None, group=None):
    """Lock a machine. If no group is specified, the local default group
       will be used. If no machine-id is specified, the local machine
       will be locked.

    machine_id
        The machine-id is a network wide, unique ID. Per default the
        ID from /etc/machine-id is used.

    group
        Group name

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr lock group=group1

    """
    cmd = ["rebootmgrctl", "lock"]
    if group:
        cmd.extend(["--group", group])
    if machine_id:
        cmd.append(machine_id)

    return _cmd(cmd)


def unlock(machine_id=None, group=None):
    """Unlock a machine. If no group is specified, the local default group
       will be used. If no machine-id is specified, the local machine
       will be locked.

    machine_id
        The machine-id is a network wide, unique ID. Per default the
        ID from /etc/machine-id is used.

    group
        Group name

    CLI Example:

    .. code-block:: bash

        salt microos rebootmgr unlock group=group1

    """
    cmd = ["rebootmgrctl", "unlock"]
    if group:
        cmd.extend(["--group", group])
    if machine_id:
        cmd.append(machine_id)

    return _cmd(cmd)
