# -*- coding: utf-8 -*-
'''
Sudo executor module

@author: Dmitry Kuzmenko <dmitry.kuzmenko@dsr-company.com>
'''
# Import python libs
from __future__ import absolute_import
import json
try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

# Import salt libs
from salt.executors import ModuleExecutorBase
import salt.utils
import salt.syspaths

__virtualname__ = 'sudo'


def __virtual__():
    if salt.utils.which('sudo') and __opts__.get('sudo_user'):
        return __virtualname__
    return False


def get(*args, **kwargs):
    return SudoExecutor(*args, **kwargs)


class SudoExecutor(ModuleExecutorBase):
    '''
    Allow for the calling of execution modules via sudo.

    This module is invoked by the minion if the ``sudo_user`` minion config is
    present.

    Example minion config:

    .. code-block:: yaml

        sudo_user: saltdev

    Once this setting is made, any execution module call done by the minion will be
    run under ``sudo -u <sudo_user> salt-call``.  For example, with the above
    minion config,

    .. code-block:: bash

        salt sudo_minion cmd.run 'cat /etc/sudoers'

    is equivalent to

    .. code-block:: bash

        sudo -u saltdev salt-call cmd.run 'cat /etc/sudoers'

    being run on ``sudo_minion``.
    '''

    def __init__(self, opts, data, func, args, kwargs):
        '''
        Constructor
        '''
        super(SudoExecutor, self).__init__()
        self.cmd = ['sudo',
                    '-u', opts.get('sudo_user'),
                    'salt-call',
                    '--out', 'json',
                    '--metadata',
                    '-c', salt.syspaths.CONFIG_DIR,
                    '--',
                    data.get('fun')]
        if data['fun'] == 'state.sls':
            kwargs['concurrent'] = True
        for arg in args:
            self.cmd.append(_cmd_quote(str(arg)))
        for key in kwargs:
            self.cmd.append(_cmd_quote('{0}={1}'.format(key, kwargs[key])))

    def execute(self):
        '''
        Wrap a shell execution out to salt call with sudo

        Example:

        /etc/salt/minion

        .. code-block:: yaml

            sudo_user: saltdev

        .. code-block:: bash

            salt '*' test.ping  # is run as saltdev user
        '''

        cmd_ret = __salt__['cmd.run_all'](self.cmd, use_vt=True, python_shell=False)

        if cmd_ret['retcode'] == 0:
            cmd_meta = json.loads(cmd_ret['stdout'])['local']
            ret = cmd_meta['return']
            __context__['retcode'] = cmd_meta.get('retcode', 0)
        else:
            ret = cmd_ret['stderr']
            __context__['retcode'] = cmd_ret['retcode']

        return ret
