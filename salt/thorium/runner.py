# -*- coding: utf-8 -*-
"""
React by calling asynchronous runners
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# import salt libs
import salt.runner


def cmd(name, func=None, arg=(), **kwargs):
    """
    Execute a runner asynchronous:

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
            - kwargs:
                provider: my-ec2-config
                instances: myinstance
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
