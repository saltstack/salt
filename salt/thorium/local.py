"""
Run remote execution commands from Thorium via the local client.

This module is the Thorium bridge into normal execution modules. Use it when a
Thorium formula should cause work to happen on one or more minions after a
check, timer, or event gate succeeds.
"""

import salt.client


def cmd(name, tgt, func, arg=(), tgt_type="glob", ret="", kwarg=None, **kwargs):
    """
    Execute an asynchronous remote execution command.

    The state return contains the queued JID, which makes this state useful as
    the action stage of a Thorium pipeline.

    USAGE:

    .. code-block:: yaml

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.sleep
            - arg:
              - 30

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.sleep
            - kwarg:
              length: 30

        gated_restart:
          local.cmd:
            - tgt: 'G@roles:web'
            - tgt_type: compound
            - func: service.restart
            - arg:
              - nginx
            - require:
              - timer: cooldown
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": True}
    with salt.client.get_local_client(mopts=__opts__) as client:
        jid = client.cmd_async(
            tgt, func, arg, tgt_type=tgt_type, ret=ret, kwarg=kwarg, **kwargs
        )
        ret["changes"]["jid"] = jid
    return ret
