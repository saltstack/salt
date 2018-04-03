# -*- coding: utf-8 -*-
'''
The ssh client wrapper system contains the routines that are used to alter
how executions are run in the salt-ssh system, this allows for state routines
to be easily rewritten to execute in a way that makes them do the same tasks
as ZeroMQ salt, but via ssh.
'''

# Import python libs
from __future__ import absolute_import, print_function
import copy

# Import salt libs
import salt.loader
import salt.utils.data
import salt.utils.json
import salt.client.ssh

# Import 3rd-party libs
from salt.ext import six


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
            mods=None,
            fsclient=None,
            cmd_prefix=None,
            aliases=None,
            minion_opts=None,
            **kwargs):
        super(FunctionWrapper, self).__init__()
        self.cmd_prefix = cmd_prefix
        self.wfuncs = wfuncs if isinstance(wfuncs, dict) else {}
        self.opts = opts
        self.mods = mods if isinstance(mods, dict) else {}
        self.kwargs = {'id_': id_,
                       'host': host}
        self.fsclient = fsclient
        self.kwargs.update(kwargs)
        self.aliases = aliases
        if self.aliases is None:
            self.aliases = {}
        self.minion_opts = minion_opts

    def __contains__(self, key):
        '''
        We need to implement a __contains__ method, othwerwise when someone
        does a contains comparison python assumes this is a sequence, and does
        __getitem__ keys 0 and up until IndexError
        '''
        try:
            self[key]  # pylint: disable=W0104
            return True
        except KeyError:
            return False

    def __getitem__(self, cmd):
        '''
        Return the function call to simulate the salt local lookup system
        '''
        if '.' not in cmd and not self.cmd_prefix:
            # Form of salt.cmd.run in Jinja -- it's expecting a subdictionary
            # containing only 'cmd' module calls, in that case. Create a new
            # FunctionWrapper which contains the prefix 'cmd' (again, for the
            # salt.cmd.run example)
            kwargs = copy.deepcopy(self.kwargs)
            id_ = kwargs.pop('id_')
            host = kwargs.pop('host')
            return FunctionWrapper(self.opts,
                                   id_,
                                   host,
                                   wfuncs=self.wfuncs,
                                   mods=self.mods,
                                   fsclient=self.fsclient,
                                   cmd_prefix=cmd,
                                   aliases=self.aliases,
                                   minion_opts=self.minion_opts,
                                   **kwargs)

        if self.cmd_prefix:
            # We're in an inner FunctionWrapper as created by the code block
            # above. Reconstruct the original cmd in the form 'cmd.run' and
            # then evaluate as normal
            cmd = '{0}.{1}'.format(self.cmd_prefix, cmd)

        if cmd in self.wfuncs:
            return self.wfuncs[cmd]

        if cmd in self.aliases:
            return self.aliases[cmd]

        def caller(*args, **kwargs):
            '''
            The remote execution function
            '''
            argv = [cmd]
            argv.extend([salt.utils.json.dumps(arg) for arg in args])
            argv.extend(
                ['{0}={1}'.format(salt.utils.stringutils.to_str(key),
                                  salt.utils.json.dumps(val))
                 for key, val in six.iteritems(kwargs)]
            )
            single = salt.client.ssh.Single(
                    self.opts,
                    argv,
                    mods=self.mods,
                    wipe=True,
                    fsclient=self.fsclient,
                    minion_opts=self.minion_opts,
                    **self.kwargs
            )
            stdout, stderr, retcode = single.cmd_block()
            if stderr.count('Permission Denied'):
                return {'_error': 'Permission Denied',
                        'stdout': stdout,
                        'stderr': stderr,
                        'retcode': retcode}
            try:
                ret = salt.utils.json.loads(stdout)
                if len(ret) < 2 and 'local' in ret:
                    ret = ret['local']
                ret = ret.get('return', {})
            except ValueError:
                ret = {'_error': 'Failed to return clean data',
                       'stderr': stderr,
                       'stdout': stdout,
                       'retcode': retcode}
            return ret
        return caller

    def __setitem__(self, cmd, value):
        '''
        Set aliases for functions
        '''
        if '.' not in cmd and not self.cmd_prefix:
            # Form of salt.cmd.run in Jinja -- it's expecting a subdictionary
            # containing only 'cmd' module calls, in that case. We don't
            # support assigning directly to prefixes in this way
            raise KeyError('Cannot assign to module key {0} in the '
                           'FunctionWrapper'.format(cmd))

        if self.cmd_prefix:
            # We're in an inner FunctionWrapper as created by the first code
            # block in __getitem__. Reconstruct the original cmd in the form
            # 'cmd.run' and then evaluate as normal
            cmd = '{0}.{1}'.format(self.cmd_prefix, cmd)

        if cmd in self.wfuncs:
            self.wfuncs[cmd] = value

        # Here was assume `value` is a `caller` function from __getitem__.
        # We save it as an alias and then can return it when referenced
        # later in __getitem__
        self.aliases[cmd] = value

    def get(self, cmd, default):
        '''
        Mirrors behavior of dict.get
        '''
        if cmd in self:
            return self[cmd]
        else:
            return default
