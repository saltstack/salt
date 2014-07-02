# -*- coding: utf-8 -*-
'''
Modules used to control the master itself
'''
#import python libs
import collections

import os
# Import salt libs
from salt import syspaths
import salt.config
import salt.loader
import salt.payload
import salt.utils
import salt.exceptions
from salt.utils.error import raise_error
from salt.utils.event import tagify


class WheelClient(object):
    '''
    An interface to Salt's wheel modules

    :ref:`Wheel modules <all-salt.wheel>` interact with various parts of the
    Salt Master.

    Importing and using ``WheelClient`` must be done on the same machine as the
    Salt Master and it must be done using the same user that the Salt Master is
    running as. Unless :conf_master:`external_auth` is configured and the user
    is authorized to execute wheel functions: (``@wheel``).
    '''
    def __init__(self, opts=None):
        if not opts:
            opts = salt.config.client_config(
                    os.environ.get(
                        'SALT_MASTER_CONFIG',
                        os.path.join(syspaths.CONFIG_DIR, 'master')
                        )
                    )

        self.opts = opts
        self.w_funcs = salt.loader.wheels(opts)

    def get_docs(self):
        '''
        Return a dictionary of functions and the inline documentation for each
        '''
        ret = [(fun, self.w_funcs[fun].__doc__)
                for fun in sorted(self.w_funcs)]

        return dict(ret)

    def call_func(self, fun, **kwargs):
        '''
        Execute a wheel function

        .. code-block:: python

            >>> opts = salt.config.master_config('/etc/salt/master')
            >>> wheel = salt.wheel.Wheel(opts)
            >>> wheel.call_func('key.list_all')
            {'local': ['master.pem', 'master.pub'],
            'minions': ['jerry'],
            'minions_pre': [],
            'minions_rejected': []}
        '''
        if fun not in self.w_funcs:
            return 'Unknown wheel function'
        f_call = salt.utils.format_call(self.w_funcs[fun], kwargs)
        return self.w_funcs[fun](*f_call.get('args', ()), **f_call.get('kwargs', {}))

    def master_call(self, **kwargs):
        '''
        Execute a wheel function through the master network interface (eauth).
        '''
        load = kwargs
        load['cmd'] = 'wheel'
        sreq = salt.payload.SREQ(
                'tcp://{0[interface]}:{0[ret_port]}'.format(self.opts),
                )
        ret = sreq.send('clear', load)
        if isinstance(ret, collections.Mapping):
            if 'error' in ret:
                raise_error(**ret['error'])
        return ret

    def cmd_sync(self, low):
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
        sevent = salt.utils.event.get_event('master', self.opts['sock_dir'],
                self.opts['transport'])
        job = self.master_call(**low)
        ret_tag = tagify('ret', base=job['tag'])

        while True:
            ret = sevent.get_event(full=True)
            if ret is None:
                continue

            if ret['tag'] == ret_tag:
                return ret['data']['return']

Wheel = WheelClient  # for backward-compat
