'''
The ssh client wrapper system contains the routines that are used to alter
how executions are run in the salt-ssh system, this allows for state routines
to be easily rewritten to execute in a way that makes them do the same tasks
as ZeroMQ salt, but via ssh.
'''
# Import python libs
import json

# Import salt libs
import salt.loader
import salt.utils
import salt.client.ssh


class FunctionWrapper(dict):
    '''
    Create an object that acts like the salt function dict and makes function
    calls remotely via the SSH shell system
    '''
    def __init__(
            self,
            opts,
            id_,
            host,
            **kwargs):
        super(FunctionWrapper, self).__init__()
        self.opts = opts
        self.kwargs = {'id_': id_,
                       'host': host}
        self.kwargs.update(kwargs)

    def __getitem__(self, cmd):
        '''
        Return the function call to simulate the salt local lookup system
        '''
        def caller(*args, **kwargs):
            '''
            The remote execution function
            '''
            arg_str = '{0} '.format(cmd)
            for arg in args:
                arg_str += '{0} '.format(arg)
            for key, val in kwargs.items():
                arg_str += '{0}={1} '.format(key, val)
            single = salt.client.ssh.Single(self.opts, arg_str, **self.kwargs)
            ret = single.cmd_block()
            if ret.startswith('deploy'):
                single.deploy()
                ret = single.cmd_block()
            return json.loads(ret, object_hook=salt.utils.decode_dict)
        return caller
