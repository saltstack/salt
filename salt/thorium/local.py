"""
Run remote execution commands via the local client
"""

import salt.client


def cmd(name, tgt, func, arg=(), tgt_type="glob", ret="", kwarg=None, **kwargs):
    """
    Execute a remote execution command

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
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": True}
    with salt.client.get_local_client(mopts=__opts__) as client:
        jid = client.cmd_async(
            tgt, func, arg, tgt_type=tgt_type, ret=ret, kwarg=kwarg, **kwargs
        )
        ret["changes"]["jid"] = jid
    return ret
