# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
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
                 c_path=os.path.join(syspaths.CONFIG_DIR, u'master'),
                 mopts=None,
                 disable_custom_roster=False):
        if mopts:
            self.opts = mopts
        else:
            if os.path.isdir(c_path):
                log.warning(
                    u'%s expects a file path not a directory path(%s) to '
                    u'its \'c_path\' keyword argument',
                    self.__class__.__name__, c_path
                )
            self.opts = salt.config.client_config(c_path)

        # Salt API should never offer a custom roster!
        self.opts[u'__disable_custom_roster'] = disable_custom_roster

    def _prep_ssh(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type=u'glob',
            kwarg=None,
            **kwargs):
        '''
        Prepare the arguments
        '''
        if u'expr_form' in kwargs:
            salt.utils.versions.warn_until(
                u'Fluorine',
                u'The target type should be passed using the \'tgt_type\' '
                u'argument instead of \'expr_form\'. Support for using '
                u'\'expr_form\' will be removed in Salt Fluorine.'
            )
            tgt_type = kwargs.pop(u'expr_form')

        opts = copy.deepcopy(self.opts)
        opts.update(kwargs)
        if timeout:
            opts[u'timeout'] = timeout
        arg = salt.utils.args.condition_input(arg, kwarg)
        opts[u'argv'] = [fun] + arg
        opts[u'selected_target_option'] = tgt_type
        opts[u'tgt'] = tgt
        opts[u'arg'] = arg
        return salt.client.ssh.SSH(opts)

    def cmd_iter(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type=u'glob',
            ret=u'',
            kwarg=None,
            **kwargs):
        '''
        Execute a single command via the salt-ssh subsystem and return a
        generator

        .. versionadded:: 2015.5.0
        '''
        if u'expr_form' in kwargs:
            salt.utils.versions.warn_until(
                u'Fluorine',
                u'The target type should be passed using the \'tgt_type\' '
                u'argument instead of \'expr_form\'. Support for using '
                u'\'expr_form\' will be removed in Salt Fluorine.'
            )
            tgt_type = kwargs.pop(u'expr_form')

        ssh = self._prep_ssh(
                tgt,
                fun,
                arg,
                timeout,
                tgt_type,
                kwarg,
                **kwargs)
        for ret in ssh.run_iter(jid=kwargs.get(u'jid', None)):
            yield ret

    def cmd(self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type=u'glob',
            kwarg=None,
            **kwargs):
        '''
        Execute a single command via the salt-ssh subsystem and return all
        routines at once

        .. versionadded:: 2015.5.0
        '''
        if u'expr_form' in kwargs:
            salt.utils.versions.warn_until(
                u'Fluorine',
                u'The target type should be passed using the \'tgt_type\' '
                u'argument instead of \'expr_form\'. Support for using '
                u'\'expr_form\' will be removed in Salt Fluorine.'
            )
            tgt_type = kwargs.pop(u'expr_form')

        ssh = self._prep_ssh(
                tgt,
                fun,
                arg,
                timeout,
                tgt_type,
                kwarg,
                **kwargs)
        final = {}
        for ret in ssh.run_iter(jid=kwargs.get(u'jid', None)):
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

        for ignore in [u'tgt', u'fun', u'arg', u'timeout', u'tgt_type', u'kwarg']:
            if ignore in kwargs:
                del kwargs[ignore]

        return self.cmd(low[u'tgt'],
                        low[u'fun'],
                        low.get(u'arg', []),
                        low.get(u'timeout'),
                        low.get(u'tgt_type'),
                        low.get(u'kwarg'),
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
            tgt_type=u'glob',
            ret=u'',
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
        if u'expr_form' in kwargs:
            salt.utils.versions.warn_until(
                u'Fluorine',
                u'The target type should be passed using the \'tgt_type\' '
                u'argument instead of \'expr_form\'. Support for using '
                u'\'expr_form\' will be removed in Salt Fluorine.'
            )
            tgt_type = kwargs.pop(u'expr_form')
        minion_ret = self.cmd(tgt,
                              u'sys.list_functions',
                              tgt_type=tgt_type,
                              **kwargs)
        minions = list(minion_ret)
        random.shuffle(minions)
        f_tgt = []
        for minion in minions:
            if fun in minion_ret[minion][u'return']:
                f_tgt.append(minion)
            if len(f_tgt) >= sub:
                break
        return self.cmd_iter(f_tgt, fun, arg, timeout, tgt_type=u'list', ret=ret, kwarg=kwarg, **kwargs)
