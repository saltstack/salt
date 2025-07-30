"""
Module to provide information about minions and handle killing and restarting
minions
"""

import os
import sys
import time

import salt.key
import salt.utils.data
import salt.utils.systemd
from salt.exceptions import CommandExecutionError

# Don't shadow built-ins.
__func_alias__ = {"list_": "list"}


def _is_systemd_system():
    """
    Check if the system uses systemd
    """
    is_linux = __grains__.get("kernel") == "Linux"
    is_booted = salt.utils.systemd.booted(__context__)
    if is_linux and is_booted:
        return True
    return False


def _is_windows_system():
    """
    Check if the system is Windows
    """
    return __grains__.get("kernel") == "Windows"


def list_():
    """
    Return a list of accepted, denied, unaccepted and rejected keys.
    This is the same output as `salt-key -L`

    CLI Example:

    .. code-block:: bash

        salt 'master' minion.list
    """
    pki_dir = __salt__["config.get"]("pki_dir", "")

    # We have to replace the minion/master directories
    pki_dir = pki_dir.replace("minion", "master")

    # The source code below is (nearly) a copy of salt.key.Key.list_keys
    key_dirs = _check_minions_directories(pki_dir)

    ret = {}

    for dir_ in key_dirs:
        ret[os.path.basename(dir_)] = []
        try:
            for fn_ in salt.utils.data.sorted_ignorecase(os.listdir(dir_)):
                if not fn_.startswith("."):
                    if os.path.isfile(os.path.join(dir_, fn_)):
                        ret[os.path.basename(dir_)].append(fn_)
        except OSError:
            # key dir kind is not created yet, just skip
            continue

    return ret


def _check_minions_directories(pki_dir):
    """
    Return the minion keys directory paths.

    This function is a copy of salt.key.Key._check_minions_directories.
    """
    minions_accepted = os.path.join(pki_dir, salt.key.Key.ACC)
    minions_pre = os.path.join(pki_dir, salt.key.Key.PEND)
    minions_rejected = os.path.join(pki_dir, salt.key.Key.REJ)
    minions_denied = os.path.join(pki_dir, salt.key.Key.DEN)

    return minions_accepted, minions_pre, minions_rejected, minions_denied


def kill(timeout=15):
    """
    Kill the salt minion.

    timeout
        int seconds to wait for the minion to die.

    If you have a monitor that restarts ``salt-minion`` when it dies then this is
    a great way to restart after a minion upgrade.

    CLI Example:

    .. code-block:: bash

        salt minion[12] minion.kill

        minion1:
            ----------
            killed:
                7874
            retcode:
                0
        minion2:
            ----------
            killed:
                29071
            retcode:
                0

    The result of the salt command shows the process ID of the minions and the
    results of a kill signal to the minion in as the ``retcode`` value: ``0``
    is success, anything else is a failure.
    """

    ret = {
        "killed": None,
        "retcode": 1,
    }
    comment = []
    pid = __grains__.get("pid")
    if not pid:
        comment.append('Unable to find "pid" in grains')
        ret["retcode"] = salt.defaults.exitcodes.EX_SOFTWARE
    else:
        if "ps.kill_pid" not in __salt__:
            comment.append("Missing command: ps.kill_pid")
            ret["retcode"] = salt.defaults.exitcodes.EX_SOFTWARE
        else:
            # The retcode status comes from the first kill signal
            ret["retcode"] = int(not __salt__["ps.kill_pid"](pid))

            # If the signal was successfully delivered then wait for the
            # process to die - check by sending signals until signal delivery
            # fails.
            if ret["retcode"]:
                comment.append("ps.kill_pid failed")
            else:
                for _ in range(timeout):
                    time.sleep(1)
                    signaled = __salt__["ps.kill_pid"](pid)
                    if not signaled:
                        ret["killed"] = pid
                        break
                else:
                    # The process did not exit before the timeout
                    comment.append("Timed out waiting for minion to exit")
                    ret["retcode"] = salt.defaults.exitcodes.EX_TEMPFAIL

    if comment:
        ret["comment"] = comment
    return ret


def restart():
    """
    Restart the salt minion.

    The method to restart the minion will be chosen as follows:

    - If ``minion_restart_command`` is set in the minion configuration then
    the command specified will be used to restart the minion.

    - If the minion is running as a Systemd service then the minion will be
    restarted using the systemd_service module

    - If the minion is running as a Windows service then the minion will be
    restarted using the win_service module

    - If the salt-minion process is running in daemon mode (the ``-d``
    argument is present in ``argv``) then the minion will be killed and
    restarted using the same command line arguments, if possible.

    - If the salt-minion process is running in the foreground (the ``-d``
    argument is not present in ``argv``) then the minion will be killed but not
    restarted. This behavior is intended for minion processes that are managed
    by a process supervisor.

    CLI Example:

    .. code-block:: bash

        salt minion[12] minion.restart

        minion1:
            ----------
            comment:
                - Restart using process argv:
                -     /home/omniture/install/bin/salt-minion
                -     -d
                -     -c
                -     /home/omniture/install/etc/salt
            killed:
                10070
            restart:
                ----------
                stderr:
                stdout:
            retcode:
                0
        minion2:
            ----------
            comment:
                - Using configuration minion_restart_command:
                -     /home/omniture/install/bin/salt-minion
                -     --not-an-option
                -     -d
                -     -c
                -     /home/omniture/install/etc/salt
                - Restart failed
            killed:
                10896
            restart:
                ----------
                stderr:
                    Usage: salt-minion

                    salt-minion: error: no such option: --not-an-option
                stdout:
            retcode:
                64

    The result of the command shows the process ID of ``minion1`` that is
    shutdown (killed) and the results of the restart.  If there is a failure
    in the restart it will be reflected in a non-zero ``retcode`` and possibly
    output in the ``stderr`` and/or ``stdout`` values along with addition
    information in the ``comment`` field as is demonstrated with ``minion2``.
    """

    should_kill = True
    should_restart = True
    comment = []
    ret = {
        "killed": None,
        "restart": {},
        "service_restart": {},
        "retcode": 0,
    }

    restart_cmd = __salt__["config.get"]("minion_restart_command")
    if restart_cmd:
        comment.append("Using configuration minion_restart_command:")
        comment.extend([f"    {arg}" for arg in restart_cmd])
    elif _is_systemd_system():
        # If we are using systemd then we will restart the minion using
        # service.restart (systemd_service.restart)
        comment.append("Using systemctl to restart salt-minion")
        should_kill = False
        should_restart = False
    elif _is_windows_system():
        # If we are on Windows then we will restart the minion using
        # service.restart (win_service.restart)
        comment.append("Using windows service manager to restart salt-minion")
        should_kill = False
        should_restart = False
    else:
        if "-d" in sys.argv:
            restart_cmd = sys.argv
            comment.append("Restart using process argv:")
            comment.extend([f"    {arg}" for arg in restart_cmd])
        else:
            should_restart = False
            comment.append(
                "Not running in daemon mode - will not restart process after killing"
            )

    if should_kill:
        ret.update(kill())
        if "comment" in ret and ret["comment"]:
            if isinstance(ret["comment"], str):
                comment.append(ret["comment"])
            else:
                comment.extend(ret["comment"])
        if ret["retcode"]:
            comment.append("Kill failed - not restarting")
            should_restart = False

    if should_restart:
        ret["restart"] = __salt__["cmd.run_all"](restart_cmd, env=os.environ)
        # Do not want to mislead users to think that the returned PID from
        # cmd.run_all() is the PID of the new salt minion - just delete the
        # returned PID.
        if "pid" in ret["restart"]:
            del ret["restart"]["pid"]
        if ret["restart"].get("retcode", None):
            comment.append("Restart failed")
            ret["retcode"] = ret["restart"]["retcode"]
        if "retcode" in ret["restart"]:
            # Just want a single retcode
            del ret["restart"]["retcode"]

    if not restart_cmd:
        if _is_systemd_system():
            try:
                ret["service_restart"]["result"] = __salt__["service.restart"](
                    "salt-minion", no_block=True
                )
            except CommandExecutionError as e:
                comment.append("Service restart failed")
                ret["service_restart"]["result"] = False
                ret["service_restart"]["stderr"] = str(e)
                ret["retcode"] = salt.defaults.exitcodes.EX_SOFTWARE
        elif _is_windows_system():
            ret["service_restart"]["result"] = __salt__["service.restart"](
                "salt-minion"
            )
            if not ret["service_restart"]:
                comment.append("Service restart failed")
                ret["retcode"] = salt.defaults.exitcodes.EX_SOFTWARE

    if comment:
        ret["comment"] = comment

    return ret
