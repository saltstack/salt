"""
Run remote execution commands via the local client
"""
# import python libs
import jinja2.nativetypes

# Import salt libs
import salt.client

jinja_env = jinja2.nativetypes.NativeEnvironment(
    variable_start_string="{|", variable_end_string="|}", autoescape=None
)


def cmd(name, tgt, func, tgt_type="glob", ret="", arg=(), kwarg=None, **kwargs):
    """
    Execute a remote execution command. The tgt, func, arg, and kwarg arguments
    can all be given jinja templates that take the register dictionary as
    context. The jinja variable delimiters used is '{| |}' in order to avoid
    clashing with compile-time rendering.

    tgt
        Target minion(s) to run the command on. Passed on to salt.client.LocalClient.cmd_async

    tgt_type : glob
        The type of minion targetting to use. Passed to salt.client.LocalClient.cmd_async
        Defaults to "glob".

    func
        The salt function to run, For example test.ping or grains.items

    arg
        List of positional arguments to pass to the function

    kwarg
        List of keyword arguments to pass to the function

    USAGE:

    .. code-block:: yaml

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

        # Embed registers in any parameter.
        # Assume 'region' and 'wait_time' have been set using reg, or calc.
        run_remote_args:
          local.cmd:
            - tgt: {|region['val']|}-*-minion
            - func: test.sleep
            - kwarg:
              length: {|wait_time['val']|}

    """
    ret = {"name": name, "changes": {}, "comment": "", "result": True}
    local = salt.client.get_local_client(mopts=__opts__)

    def _substitute_registers(parameter):
        return jinja_env.from_string(parameter).render(__reg__)

    tgt = _substitute_registers(tgt)
    func = _substitute_registers(func)
    arg = [_substitute_registers(x) for x in arg]
    if kwarg is not None:
        kwarg = {
            _substitute_registers(k): _substitute_registers(v) for k, v in kwarg.items()
        }

    jid = local.cmd_async(
        tgt, func, arg, tgt_type=tgt_type, ret=ret, kwarg=kwarg, **kwargs
    )
    ret["changes"]["jid"] = jid
    return ret
