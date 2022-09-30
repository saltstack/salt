"""
Support for reboot, shutdown, etc

This module is assumes we are using solaris-like shutdown

.. versionadded:: 2016.3.0
"""

import salt.utils.path
import salt.utils.platform

# Define the module's virtual name
__virtualname__ = "system"


def __virtual__():
    """
    Only supported on Solaris-like systems
    """
    if not salt.utils.platform.is_sunos() or not salt.utils.path.which("shutdown"):
        return (
            False,
            "The system execution module failed to load: only available on "
            "Solaris-like ystems with shutdown command.",
        )
    return __virtualname__


def halt():
    """
    Halt a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.halt
    """
    return shutdown()


def init(state):
    """
    Change the system runlevel on sysV compatible systems

    CLI Example:

    state : string
        Init state

    .. code-block:: bash

        salt '*' system.init 3

    .. note:

        state 0
            Stop the operating system.

        state 1
            State 1 is referred to as the administrative state. In
            state 1 file systems required for multi-user operations
            are mounted, and logins requiring access to multi-user
            file systems can be used. When the system comes up from
            firmware mode into state 1, only the console is active
            and other multi-user (state 2) services are unavailable.
            Note that not all user processes are stopped when
            transitioning from multi-user state to state 1.

        state s, S
            State s (or S) is referred to as the single-user state.
            All user processes are stopped on transitions to this
            state. In the single-user state, file systems required
            for multi-user logins are unmounted and the system can
            only be accessed through the console. Logins requiring
            access to multi-user file systems cannot be used.

       state 5
            Shut the machine down so that it is safe to remove the
            power. Have the machine remove power, if possible. The
            rc0 procedure is called to perform this task.

       state 6
             Stop the operating system and reboot to the state defined
             by the initdefault entry in /etc/inittab. The rc6
             procedure is called to perform this task.
    """
    cmd = ["shutdown", "-i", state, "-g", "0", "-y"]
    ret = __salt__["cmd.run"](cmd, python_shell=False)
    return ret


def poweroff():
    """
    Poweroff a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.poweroff
    """
    return shutdown()


def reboot(delay=0, message=None):
    """
    Reboot the system

    delay : int
        Optional wait time in seconds before the system will be rebooted.
    message : string
        Optional message to broadcast before rebooting.

    CLI Example:

    .. code-block:: bash

        salt '*' system.reboot
        salt '*' system.reboot 60 "=== system upgraded ==="
    """
    cmd = ["shutdown", "-i", "6", "-g", delay, "-y"]
    if message:
        cmd.append(message)
    ret = __salt__["cmd.run"](cmd, python_shell=False)
    return ret


def shutdown(delay=0, message=None):
    """
    Shutdown a running system

    delay : int
        Optional wait time in seconds before the system will be shutdown.
    message : string
        Optional message to broadcast before rebooting.

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown
        salt '*' system.shutdown 60 "=== disk replacement ==="
    """
    cmd = ["shutdown", "-i", "5", "-g", delay, "-y"]
    if message:
        cmd.append(message)
    ret = __salt__["cmd.run"](cmd, python_shell=False)
    return ret
