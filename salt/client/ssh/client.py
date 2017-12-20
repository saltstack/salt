# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import copy
import logging
import random

# Import Salt libs
import salt.config
import salt.utils.versions
import salt.syspaths as syspaths
from salt.exceptions import SaltClientError  # Temporary

log = logging.getLogger(__name__)


class SSHClient(object):
    '''
    Create a client object for executing routines via the salt-ssh backend

    .. versionadded:: 2015.5.0
    '''
    def __init__(self,
                 c_path=os.path.join(syspaths.CONFIG_DIR, 'master'),
                 mopts=None,
                 disable_custom_roster=False):
        if mopts:
            self.opts = mopts
        else:
            if os.path.isdir(c_path):
                log.warning(
                    '%s expects a file path not a directory path(%s) to '
                    'its \'c_path\' keyword argument',
                    self.__class__.__name__, c_path
                )
            self.opts = salt.config.client_config(c_path)

        # Salt API should never offer a custom roster!
        self.opts['__disable_custom_roster'] = disable_custom_roster

    def _prep_ssh(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type='glob',
            kwarg=None,
            **kwargs):
        '''
        Prepare the arguments
        '''
        if 'expr_form' in kwargs:
            salt.utils.versions.warn_until(
                'Fluorine',
                'The target type should be passed using the \'tgt_type\' '
                'argument instead of \'expr_form\'. Support for using '
                '\'expr_form\' will be removed in Salt Fluorine.'
            )
            tgt_type = kwargs.pop('expr_form')

        opts = copy.deepcopy(self.opts)
        opts.update(kwargs)
        if timeout:
            opts['timeout'] = timeout
        arg = salt.utils.args.condition_input(arg, kwarg)
        opts['argv'] = [fun] + arg
        opts['selected_target_option'] = tgt_type
        opts['tgt'] = tgt
        opts['arg'] = arg
        return salt.client.ssh.SSH(opts)

    def cmd_iter(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type='glob',
            ret='',
            kwarg=None,
            **kwargs):
        '''
        Execute a single command via the salt-ssh subsystem and return a
        generator

        .. versionadded:: 2015.5.0
        '''
        if 'expr_form' in kwargs:
            salt.utils.versions.warn_until(
                'Fluorine',
                'The target type should be passed using the \'tgt_type\' '
                'argument instead of \'expr_form\'. Support for using '
                '\'expr_form\' will be removed in Salt Fluorine.'
            )
            tgt_type = kwargs.pop('expr_form')

        ssh = self._prep_ssh(
                tgt,
                fun,
                arg,
                timeout,
                tgt_type,
                kwarg,
                **kwargs)
        for ret in ssh.run_iter(jid=kwargs.get('jid', None)):
            yield ret

    def cmd(self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type='glob',
            kwarg=None,
            **kwargs):
        '''
        Execute a single command via the salt-ssh subsystem and return all
        routines at once

        .. versionadded:: 2015.5.0
        '''
        if 'expr_form' in kwargs:
            salt.utils.versions.warn_until(
                'Fluorine',
                'The target type should be passed using the \'tgt_type\' '
                'argument instead of \'expr_form\'. Support for using '
                '\'expr_form\' will be removed in Salt Fluorine.'
            )
            tgt_type = kwargs.pop('expr_form')

        ssh = self._prep_ssh(
                tgt,
                fun,
                arg,
                timeout,
                tgt_type,
                kwarg,
                **kwargs)
        final = {}
        for ret in ssh.run_iter(jid=kwargs.get('jid', None)):
            final.update(ret)
        return final

    def cmd_sync(self, low):
        '''
        Execute a salt-ssh call synchronously.

        .. versionadded:: 2015.5.0

        WARNING: Eauth is **NOT** respected

        .. code-block:: python

            client.cmd_sync({
                'tgt': 'silver',
                'fun': 'test.ping',
                'arg': (),
                'tgt_type'='glob',
                'kwarg'={}
                })
            {'silver': {'fun_args': [], 'jid': '20141202152721523072', 'return': True, 'retcode': 0, 'success': True, 'fun': 'test.ping', 'id': 'silver'}}
        '''

        kwargs = copy.deepcopy(low)

        for ignore in ['tgt', 'fun', 'arg', 'timeout', 'tgt_type', 'kwarg']:
            if ignore in kwargs:
                del kwargs[ignore]

        return self.cmd(low['tgt'],
                        low['fun'],
                        low.get('arg', []),
                        low.get('timeout'),
                        low.get('tgt_type'),
                        low.get('kwarg'),
                        **kwargs)

    def cmd_async(self, low, timeout=None):
        '''
        Execute aa salt-ssh asynchronously

        WARNING: Eauth is **NOT** respected

        .. code-block:: python

            client.cmd_sync({
                'tgt': 'silver',
                'fun': 'test.ping',
                'arg': (),
                'tgt_type'='glob',
                'kwarg'={}
                })
            {'silver': {'fun_args': [], 'jid': '20141202152721523072', 'return': True, 'retcode': 0, 'success': True, 'fun': 'test.ping', 'id': 'silver'}}
        '''
        # TODO Not implemented
        raise SaltClientError

    def cmd_subset(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type='glob',
            ret='',
            kwarg=None,
            sub=3,
            **kwargs):
        '''
        Execute a command on a random subset of the targeted systems

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :param sub: The number of systems to execute on

        .. code-block:: python

            >>> import salt.client.ssh.client
            >>> sshclient= salt.client.ssh.client.SSHClient()
            >>> sshclient.cmd_subset('*', 'test.ping', sub=1)
            {'jerry': True}

        .. versionadded:: 2017.7.0
        '''
        if 'expr_form' in kwargs:
            salt.utils.versions.warn_until(
                'Fluorine',
                'The target type should be passed using the \'tgt_type\' '
                'argument instead of \'expr_form\'. Support for using '
                '\'expr_form\' will be removed in Salt Fluorine.'
            )
            tgt_type = kwargs.pop('expr_form')
        minion_ret = self.cmd(tgt,
                              'sys.list_functions',
                              tgt_type=tgt_type,
                              **kwargs)
        minions = list(minion_ret)
        random.shuffle(minions)
        f_tgt = []
        for minion in minions:
            if fun in minion_ret[minion]['return']:
                f_tgt.append(minion)
            if len(f_tgt) >= sub:
                break
        return self.cmd_iter(f_tgt, fun, arg, timeout, tgt_type='list', ret=ret, kwarg=kwarg, **kwargs)
