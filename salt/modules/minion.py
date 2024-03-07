"""
Module to provide information about minions
"""

import os
import sys
import time

import salt.key
import salt.utils.data

# Don't shadow built-ins.
__func_alias__ = {"list_": "list"}


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
    Kill and restart the salt minion.

    The configuration key ``minion_restart_command`` is an argv list for the
    command to restart the minion.  If ``minion_restart_command`` is not
    specified or empty then the ``argv`` of the current process will be used.

    if the configuration value ``minion_restart_command`` is not set and the
    ``-d`` (daemonize) argument is missing from ``argv`` then the minion
    *will* be killed but will *not* be restarted and will require the parent
    process to perform the restart.  This behavior is intended for managed
    salt minion processes.

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
        "retcode": 0,
    }

    restart_cmd = __salt__["config.get"]("minion_restart_command")
    if restart_cmd:
        comment.append("Using configuration minion_restart_command:")
        comment.extend([f"    {arg}" for arg in restart_cmd])
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

    if comment:
        ret["comment"] = comment

    return ret
