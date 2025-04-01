"""
Sudo executor module
"""

import shlex

import salt.syspaths
import salt.utils.json
import salt.utils.path

__virtualname__ = "sudo"


def __virtual__():
    if salt.utils.path.which("sudo") and __opts__.get("sudo_user"):
        return __virtualname__
    return False


def execute(opts, data, func, args, kwargs):
    """
    Allow for the calling of execution modules via sudo.

    This module is invoked by the minion if the ``sudo_user`` minion config is
    present.

    Example minion config:

    .. code-block:: yaml

        sudo_user: saltdev

    Once this setting is made, any execution module call done by the minion will be
    run under ``sudo -u <sudo_user> salt-call``.  For example, with the above
    minion config,

    .. code-block:: bash

        salt sudo_minion cmd.run 'cat /etc/sudoers'

    is equivalent to

    .. code-block:: bash

        sudo -u saltdev salt-call cmd.run 'cat /etc/sudoers'

    being run on ``sudo_minion``.
    """
    cmd = [
        "sudo",
        "-u",
        opts.get("sudo_user"),
        "salt-call",
        "--out",
        "json",
        "--metadata",
        "-c",
        opts.get("config_dir"),
        "--",
        data.get("fun"),
    ]
    if data["fun"] in ("state.sls", "state.highstate", "state.apply"):
        kwargs["concurrent"] = True
    for arg in args:
        cmd.append(shlex.quote(str(arg)))
    for key in kwargs:
        cmd.append(shlex.quote(f"{key}={kwargs[key]}"))

    cmd_ret = __salt__["cmd.run_all"](cmd, use_vt=True, python_shell=False)

    if cmd_ret["retcode"] == 0:
        cmd_meta = salt.utils.json.loads(cmd_ret["stdout"])["local"]
        ret = cmd_meta["return"]
        __context__["retcode"] = cmd_meta.get("retcode", 0)
    else:
        ret = cmd_ret["stderr"]
        __context__["retcode"] = cmd_ret["retcode"]

    return ret
