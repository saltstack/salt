# -*- coding: utf-8 -*-
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


class FunctionWrapper(object):
    '''
    Create an object that acts like the salt function dict and makes function
    calls remotely via the SSH shell system
    '''
    def __init__(
            self,
            opts,
            id_,
            host,
            wfuncs=None,
            **kwargs):
        super(FunctionWrapper, self).__init__()
        self.wfuncs = wfuncs if isinstance(wfuncs, dict) else {}
        self.opts = opts
        self.kwargs = {'id_': id_,
                       'host': host}
        self.kwargs.update(kwargs)

    def __getitem__(self, cmd):
        '''
        Return the function call to simulate the salt local lookup system
        '''
        if cmd in self.wfuncs:
            return self.wfuncs[cmd]

        def caller(*args, **kwargs):
            '''
            The remote execution function
            '''
            arg_str = ['{0} '.format(cmd)]
            for arg in args:
                arg_str.append('{0} '.format(arg))
            for key, val in kwargs.items():
                arg_str.append('{0}={1} '.format(key, val))
            single = salt.client.ssh.Single(
                    self.opts,
                    ''.join(arg_str),
                    **self.kwargs
            )
            stdout, stderr = single.cmd_block()
            if stdout.startswith('deploy'):
                single.deploy()
                stdout, stderr = single.cmd_block()
            ret = json.loads(stdout, object_hook=salt.utils.decode_dict)
            if len(ret) < 2 and 'local' in ret:
                ret = ret['local']
            return ret
        return caller
