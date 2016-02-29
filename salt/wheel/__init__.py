# -*- coding: utf-8 -*-
'''
Modules used to control the master itself
'''
from __future__ import absolute_import
#import python libs
import os
import collections

# Import salt libs
from salt import syspaths
import salt.config
import salt.loader
from salt.client import mixins
from salt.utils.error import raise_error


class WheelClient(mixins.SyncClientMixin, mixins.AsyncClientMixin, object):
    '''
    An interface to Salt's wheel modules

    :ref:`Wheel modules <all-salt.wheel>` interact with various parts of the
    Salt Master.

    Importing and using ``WheelClient`` must be done on the same machine as the
    Salt Master and it must be done using the same user that the Salt Master is
    running as. Unless :conf_master:`external_auth` is configured and the user
    is authorized to execute wheel functions: (``@wheel``).

    Usage:

    .. code-block:: python

        import salt.config
        import salt.wheel
        opts = salt.config.master_config('/etc/salt/master')
        wheel = salt.wheel.WheelClient(opts)
    '''
    client = 'wheel'
    tag_prefix = 'wheel'

    def __init__(self, opts=None):
        self.opts = opts
        self.functions = salt.loader.wheels(opts)

    # TODO: remove/deprecate
    def call_func(self, fun, **kwargs):
        '''
        Backwards compatibility
        '''
        return self.low(fun, kwargs)

    # TODO: Inconsistent with runner client-- the runner client's master_call gives
    # an async return, unlike this
    def master_call(self, **kwargs):
        '''
        Execute a wheel function through the master network interface (eauth).
        '''
        load = kwargs
        load['cmd'] = 'wheel'
        master_uri = 'tcp://' + salt.utils.ip_bracket(self.opts['interface']) + \
                                                      ':' + str(self.opts['ret_port'])
        channel = salt.transport.Channel.factory(self.opts,
                                                 crypt='clear',
                                                 master_uri=master_uri)
        ret = channel.send(load)
        if isinstance(ret, collections.Mapping):
            if 'error' in ret:
                raise_error(**ret['error'])
        return ret

    def cmd_sync(self, low, timeout=None):
        '''
        Execute a wheel function synchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized to execute runner functions: (``@wheel``).

        .. code-block:: python

            >>> wheel.cmd_sync({
            'fun': 'key.finger',
            'match': 'jerry',
            'eauth': 'auto',
            'username': 'saltdev',
            'password': 'saltdev',
            })
            {'minions': {'jerry': '5d:f6:79:43:5e:d4:42:3f:57:b8:45:a8:7e:a4:6e:ca'}}
        '''
        return self.master_call(**low)

    # TODO: Inconsistent with runner client-- that one uses the master_call function
    # and runs within the master daemon. Need to pick one...
    def cmd_async(self, low):
        '''
        Execute a function asynchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized

        .. code-block:: python

            >>> wheel.cmd_async({
                'fun': 'key.finger',
                'match': 'jerry',
                'eauth': 'auto',
                'username': 'saltdev',
                'password': 'saltdev',
            })
            {'jid': '20131219224744416681', 'tag': 'salt/wheel/20131219224744416681'}
        '''
        fun = low.pop('fun')
        return self.async(fun, low)

    def cmd(self, fun, arg=None, pub_data=None, kwarg=None):
        '''
        Execute a function

        .. code-block:: python

            >>> wheel.cmd('key.finger', ['jerry'])
            {'minions': {'jerry': '5d:f6:79:43:5e:d4:42:3f:57:b8:45:a8:7e:a4:6e:ca'}}
        '''
        super(WheelClient, self).cmd(fun, arg, pub_data, kwarg)


Wheel = WheelClient  # for backward-compat
