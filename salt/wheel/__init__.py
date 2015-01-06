# -*- coding: utf-8 -*-
'''
Modules used to control the master itself
'''
from __future__ import absolute_import
#import python libs
import os

# Import salt libs
from salt import syspaths
import salt.config
import salt.loader
from salt.client import mixins


class WheelClient(mixins.SyncClientMixin, mixins.AsyncClientMixin, object):
    '''
    An interface to Salt's wheel modules

    :ref:`Wheel modules <all-salt.wheel>` interact with various parts of the
    Salt Master.

    Importing and using ``WheelClient`` must be done on the same machine as the
    Salt Master and it must be done using the same user that the Salt Master is
    running as. Unless :conf_master:`external_auth` is configured and the user
    is authorized to execute wheel functions: (``@wheel``).
    '''
    client = 'wheel'
    tag_prefix = 'wheel'

    def __init__(self, opts=None):
        super(WheelClient, self).__init__(opts)
        self.functions = salt.loader.wheels(opts)

    # TODO: remove/deprecate
    def call_func(self, fun, **kwargs):
        '''
        Backwards compatibility
        '''
        return self.low(fun, kwargs)


Wheel = WheelClient  # for backward-compat
