# -*- coding: utf-8 -*-
'''
React by calling async runners
'''
# Import python libs
from __future__ import absolute_import
# import salt libs
import salt.runner


def cmd(
        name,
        func=None,
        arg=(),
        **kwargs):
    '''
    Execute a runner async:

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
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if func is None:
        func = name
    client = salt.runner.RunnerClient(__opts__)
    low = {'fun': func,
           'arg': arg,
           'kwarg': kwargs}
    client.cmd_async(low)
    return ret
