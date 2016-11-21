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
        fun=None,
        arg=(),
        **kwargs):
    '''
    Execute a runner async:

    USAGE:

    .. code-block:: yaml

        run_cloud:
          runner.cmd:
            - fun: cloud.create
            - arg:
                - my-ec2-config
                - myinstance

        run_cloud:
          runner.cmd:
            - fun: cloud.create
            - kwargs:
                provider: my-ec2-config
                instances: myinstance
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if fun is None:
        fun = name
    client = salt.runner.RunnerClient(__opts__)
    low = {'fun': fun,
            'arg': arg,
            'kwargs': kwargs}
    client.cmd_async(low)
    return ret
