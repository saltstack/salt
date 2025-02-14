"""
Manage account locks on AIX systems

.. versionadded:: 2018.3.0

:depends: none
"""

# Import python librarie
import logging

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "shadow"


def __virtual__():
    """
    Only load if kernel is AIX
    """
    if __grains__["kernel"] == "AIX":
        return __virtualname__
    return (
        False,
        "The aix_shadow execution module failed to load: "
        "only available on AIX systems.",
    )


def login_failures(user):
    """
    Query for all accounts which have 3 or more login failures.

    CLI Example:

    .. code-block:: bash

        salt <minion_id> shadow.login_failures ALL
    """

    cmd = f"lsuser -a unsuccessful_login_count {user}"
    cmd += " | grep -E 'unsuccessful_login_count=([3-9]|[0-9][0-9]+)'"
    out = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=True)

    ret = []

    lines = out["stdout"].splitlines()
    for line in lines:
        ret.append(line.split()[0])

    return ret


def locked(user):
    """
    Query for all accounts which are flagged as locked.

    CLI Example:

    .. code-block:: bash

        salt <minion_id> shadow.locked ALL
    """

    cmd = f"lsuser -a account_locked {user}"
    cmd += ' | grep "account_locked=true"'
    out = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=True)

    ret = []

    lines = out["stdout"].splitlines()
    for line in lines:
        ret.append(line.split()[0])

    return ret


def unlock(user):
    """
    Unlock user for locked account

    CLI Example:

    .. code-block:: bash

        salt <minion_id> shadow.unlock user
    """

    cmd = (
        "chuser account_locked=false {0} | "
        'chsec -f /etc/security/lastlog -a "unsuccessful_login_count=0" -s {0}'.format(
            user
        )
    )
    ret = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=True)

    return ret
