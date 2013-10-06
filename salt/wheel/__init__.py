# -*- coding: utf-8 -*-
'''
Modules used to control the master itself
'''

# Import salt libs
import salt.loader
import salt.payload
import salt.utils
import salt.exceptions


class Wheel(object):
    '''
    ``WheelClient`` is an interface to Salt's :ref:`wheel modules
    <all-salt.wheel>`. Wheel modules interact with various parts of the Salt
    Master.

    Importing and using ``WheelClient`` must be done on the same machine as the
    Salt Master and it must be done using the same user that the Salt Master is
    running as.
    '''
    def __init__(self, opts):
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
        Execute a master control function
        '''
        if fun not in self.w_funcs:
            return 'Unknown wheel function'
        f_call = salt.utils.format_call(self.w_funcs[fun], kwargs)
        return self.w_funcs[fun](*f_call.get('args', ()), **f_call.get('kwargs', {}))

    def master_call(self, **kwargs):
        '''
        Send a function call to a wheel module through the master network interface
        Expects that one of the kwargs is key 'fun' whose value is the namestring
        of the function to call
        '''
        load = kwargs
        load['cmd'] = 'wheel'
        sreq = salt.payload.SREQ(
                'tcp://{0[interface]}:{0[ret_port]}'.format(self.opts),
                )
        ret = sreq.send('clear', load)
        if ret == '':
            raise salt.exceptions.EauthAuthenticationError
        return ret
