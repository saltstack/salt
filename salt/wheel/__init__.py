# -*- coding: utf-8 -*-
'''
Modules used to control the master itself
'''
from __future__ import absolute_import
#import python libs
import collections
import os
import time

# Import salt libs
from salt import syspaths
import salt.config
import salt.loader
import salt.payload
import salt.utils
from salt.client import mixins
from salt.utils.error import raise_error
from salt.utils.event import tagify


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
        if not opts:
            opts = salt.config.client_config(
                    os.environ.get(
                        'SALT_MASTER_CONFIG',
                        os.path.join(syspaths.CONFIG_DIR, 'master')
                        )
                    )

        self.opts = opts
        self.functions = salt.loader.wheels(opts)


Wheel = WheelClient  # for backward-compat
