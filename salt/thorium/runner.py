"""
React by calling asynchronous runners from Thorium.

Use this module when the reaction belongs on the master rather than on minions.
Typical uses include launching orchestration, scheduling cleanup, or invoking
other runner-based workflows after Thorium has aggregated and evaluated events.
"""

import salt.runner


def cmd(name, func=None, arg=(), **kwargs):
    """
    Execute a runner asynchronously.

    Any additional keyword arguments passed to this Thorium state are forwarded
    to the runner function.

    USAGE:

    .. code-block:: yaml

        run_cloud:
          runner.cmd:
            - func: cloud.create
            - arg:
                - my-ec2-config
                - myinstance

        run_cloud:
          runner.cmd:
            - func: cloud.create
            - provider: my-ec2-config
            - instances: myinstance

        orchestrate_remediation:
          runner.cmd:
            - func: state.orchestrate
            - mods: orch.remediate
            - pillar:
                target: db01
            - require:
              - check: sustained_high_load
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": True}
    if func is None:
        func = name
    local_opts = {}
    local_opts.update(__opts__)
    local_opts["async"] = True  # ensure this will be run asynchronous
    local_opts.update({"fun": func, "arg": arg, "kwarg": kwargs})
    runner = salt.runner.Runner(local_opts)
    runner.run()
    return ret
