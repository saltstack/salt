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
    Manage calls to the salt wheel system
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

    def master_call(self, fun, **kwargs):
        '''
        Send a function call to a wheel module through the master network interface
        '''
        load = kwargs
        load['cmd'] = 'wheel'
        load['fun'] = fun
        sreq = salt.payload.SREQ(
                'tcp://{0[interface]}:{0[ret_port]}'.format(self.opts),
                )
        ret = sreq.send('clear', load)
        if ret == '':
            raise salt.exceptions.EauthAuthenticationError
        return ret
