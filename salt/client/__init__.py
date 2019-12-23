# -*- coding: utf-8 -*-
'''
The client module is used to create a client connection to the publisher
The data structure needs to be:
    {'enc': 'clear',
     'load': {'fun': '<mod.callable>',
              'arg':, ('arg1', 'arg2', ...),
              'tgt': '<glob or id>',
              'key': '<read in the key file>'}
'''

# The components here are simple, and they need to be and stay simple, we
# want a client to have 3 external concerns, and maybe a forth configurable
# option.
# The concerns are:
# 1. Who executes the command?
# 2. What is the function being run?
# 3. What arguments need to be passed to the function?
# 4. How long do we wait for all of the replies?
#
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import time
import random
import logging
from datetime import datetime

# Import salt libs
import salt.config
import salt.cache
import salt.defaults.exitcodes
import salt.payload
import salt.transport.client
import salt.loader
import salt.utils.args
import salt.utils.event
import salt.utils.files
import salt.utils.jid
import salt.utils.minions
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.user
import salt.utils.verify
import salt.utils.zeromq
import salt.syspaths as syspaths
from salt.exceptions import (
    AuthenticationError,
    AuthorizationError,
    EauthAuthenticationError,
    PublishError,
    SaltInvocationError,
    SaltReqTimeoutError,
    SaltClientError
)

# Import third party libs
from salt.ext import six
# pylint: disable=import-error

# Try to import range from https://github.com/ytoolshed/range
HAS_RANGE = False
try:
    import seco.range
    HAS_RANGE = True
except ImportError:
    pass
# pylint: enable=import-error

# Import tornado
import tornado.gen  # pylint: disable=F0401

log = logging.getLogger(__name__)


def get_local_client(
        c_path=os.path.join(syspaths.CONFIG_DIR, 'master'),
        mopts=None,
        skip_perm_errors=False,
        io_loop=None,
        auto_reconnect=False):
    '''
    .. versionadded:: 2014.7.0

    Read in the config and return the correct LocalClient object based on
    the configured transport

    :param IOLoop io_loop: io_loop used for events.
                           Pass in an io_loop if you want asynchronous
                           operation for obtaining events. Eg use of
                           set_event_handler() API. Otherwise, operation
                           will be synchronous.
    '''
    if mopts:
        opts = mopts
    else:
        # Late import to prevent circular import
        import salt.config
        opts = salt.config.client_config(c_path)

    # TODO: AIO core is separate from transport
    return LocalClient(
        mopts=opts,
        skip_perm_errors=skip_perm_errors,
        io_loop=io_loop,
        auto_reconnect=auto_reconnect)


class LocalClient(object):
    '''
    The interface used by the :command:`salt` CLI tool on the Salt Master

    ``LocalClient`` is used to send a command to Salt minions to execute
    :ref:`execution modules <all-salt.modules>` and return the results to the
    Salt Master.

    Importing and using ``LocalClient`` must be done on the same machine as the
    Salt Master and it must be done using the same user that the Salt Master is
    running as. (Unless :conf_master:`external_auth` is configured and
    authentication credentials are included in the execution).

    .. note::
        The LocalClient uses a Tornado IOLoop, this can create issues when
        using the LocalClient inside an existing IOLoop. If creating the
        LocalClient in partnership with another IOLoop either create the
        IOLoop before creating the LocalClient, or when creating the IOLoop
        use ioloop.current() which will return the ioloop created by
        LocalClient.

    .. code-block:: python

        import salt.client

        local = salt.client.LocalClient()
        local.cmd('*', 'test.fib', [10])
    '''
    def __init__(self,
                 c_path=os.path.join(syspaths.CONFIG_DIR, 'master'),
                 mopts=None, skip_perm_errors=False,
                 io_loop=None, keep_loop=False, auto_reconnect=False):
        '''
        :param IOLoop io_loop: io_loop used for events.
                               Pass in an io_loop if you want asynchronous
                               operation for obtaining events. Eg use of
                               set_event_handler() API. Otherwise,
                               operation will be synchronous.
        '''
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
        self.serial = salt.payload.Serial(self.opts)
        self.salt_user = salt.utils.user.get_specific_user()
        self.skip_perm_errors = skip_perm_errors
        self.key = self.__read_master_key()
        self.auto_reconnect = auto_reconnect
        self.event = salt.utils.event.get_event(
                'master',
                self.opts['sock_dir'],
                self.opts['transport'],
                opts=self.opts,
                listen=False,
                io_loop=io_loop,
                keep_loop=keep_loop)
        self.utils = salt.loader.utils(self.opts)
        self.functions = salt.loader.minion_mods(self.opts, utils=self.utils)
        self.returners = salt.loader.returners(self.opts, self.functions)

    def __read_master_key(self):
        '''
        Read in the rotating master authentication key
        '''
        key_user = self.salt_user
        if key_user == 'root':
            if self.opts.get('user', 'root') != 'root':
                key_user = self.opts.get('user', 'root')
        if key_user.startswith('sudo_'):
            key_user = self.opts.get('user', 'root')
        if salt.utils.platform.is_windows():
            # The username may contain '\' if it is in Windows
            # 'DOMAIN\username' format. Fix this for the keyfile path.
            key_user = key_user.replace('\\', '_')
        keyfile = os.path.join(self.opts['cachedir'],
                               '.{0}_key'.format(key_user))
        try:
            # Make sure all key parent directories are accessible
            salt.utils.verify.check_path_traversal(self.opts['cachedir'],
                                                   key_user,
                                                   self.skip_perm_errors)
            with salt.utils.files.fopen(keyfile, 'r') as key:
                return salt.utils.stringutils.to_unicode(key.read())
        except (OSError, IOError, SaltClientError):
            # Fall back to eauth
            return ''

    def _convert_range_to_list(self, tgt):
        '''
        convert a seco.range range into a list target
        '''
        range_ = seco.range.Range(self.opts['range_server'])
        try:
            return range_.expand(tgt)
        except seco.range.RangeException as err:
            print('Range server exception: {0}'.format(err))
            return []

    def _get_timeout(self, timeout):
        '''
        Return the timeout to use
        '''
        if timeout is None:
            return self.opts['timeout']
        if isinstance(timeout, int):
            return timeout
        if isinstance(timeout, six.string_types):
            try:
                return int(timeout)
            except ValueError:
                return self.opts['timeout']
        # Looks like the timeout is invalid, use config
        return self.opts['timeout']

    def gather_job_info(self, jid, tgt, tgt_type, listen=True, **kwargs):
        '''
        Return the information about a given job
        '''
        log.debug('Checking whether jid %s is still running', jid)
        timeout = int(kwargs.get('gather_job_timeout', self.opts['gather_job_timeout']))

        pub_data = self.run_job(tgt,
                                'saltutil.find_job',
                                arg=[jid],
                                tgt_type=tgt_type,
                                timeout=timeout,
                                listen=listen,
                                **kwargs
                               )

        if 'jid' in pub_data:
            self.event.subscribe(pub_data['jid'])

        return pub_data

    def _check_pub_data(self, pub_data, listen=True):
        '''
        Common checks on the pub_data data structure returned from running pub
        '''
        if pub_data == '':
            # Failed to authenticate, this could be a bunch of things
            raise EauthAuthenticationError(
                'Failed to authenticate! This is most likely because this '
                'user is not permitted to execute commands, but there is a '
                'small possibility that a disk error occurred (check '
                'disk/inode usage).'
            )

        # Failed to connect to the master and send the pub
        if 'error' in pub_data:
            print(pub_data['error'])
            log.debug('_check_pub_data() error: %s', pub_data['error'])
            return {}
        elif 'jid' not in pub_data:
            return {}
        if pub_data['jid'] == '0':
            print('Failed to connect to the Master, '
                  'is the Salt Master running?')
            return {}

        # If we order masters (via a syndic), don't short circuit if no minions
        # are found
        if not self.opts.get('order_masters'):
            # Check for no minions
            if not pub_data['minions']:
                print('No minions matched the target. '
                      'No command was sent, no jid was assigned.')
                return {}

        # don't install event subscription listeners when the request is asynchronous
        # and doesn't care. this is important as it will create event leaks otherwise
        if not listen:
            return pub_data

        if self.opts.get('order_masters'):
            self.event.subscribe('syndic/.*/{0}'.format(pub_data['jid']), 'regex')

        self.event.subscribe('salt/job/{0}'.format(pub_data['jid']))

        return pub_data

    def run_job(
            self,
            tgt,
            fun,
            arg=(),
            tgt_type='glob',
            ret='',
            timeout=None,
            jid='',
            kwarg=None,
            listen=False,
            **kwargs):
        '''
        Asynchronously send a command to connected minions

        Prep the job directory and publish a command to any targeted minions.

        :return: A dictionary of (validated) ``pub_data`` or an empty
            dictionary on failure. The ``pub_data`` contains the job ID and a
            list of all minions that are expected to return data.

        .. code-block:: python

            >>> local.run_job('*', 'test.sleep', [300])
            {'jid': '20131219215650131543', 'minions': ['jerry']}
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)

        try:
            pub_data = self.pub(
                tgt,
                fun,
                arg,
                tgt_type,
                ret,
                jid=jid,
                timeout=self._get_timeout(timeout),
                listen=listen,
                **kwargs)
        except SaltClientError:
            # Re-raise error with specific message
            raise SaltClientError(
                'The salt master could not be contacted. Is master running?'
            )
        except AuthenticationError as err:
            six.reraise(*sys.exc_info())
        except AuthorizationError as err:
            six.reraise(*sys.exc_info())
        except Exception as general_exception:
            # Convert to generic client error and pass along message
            raise SaltClientError(general_exception)

        return self._check_pub_data(pub_data, listen=listen)

    def gather_minions(self, tgt, expr_form):
        _res = salt.utils.minions.CkMinions(self.opts).check_minions(tgt, tgt_type=expr_form)
        return _res['minions']

    @tornado.gen.coroutine
    def run_job_async(
            self,
            tgt,
            fun,
            arg=(),
            tgt_type='glob',
            ret='',
            timeout=None,
            jid='',
            kwarg=None,
            listen=True,
            io_loop=None,
            **kwargs):
        '''
        Asynchronously send a command to connected minions

        Prep the job directory and publish a command to any targeted minions.

        :return: A dictionary of (validated) ``pub_data`` or an empty
            dictionary on failure. The ``pub_data`` contains the job ID and a
            list of all minions that are expected to return data.

        .. code-block:: python

            >>> local.run_job_async('*', 'test.sleep', [300])
            {'jid': '20131219215650131543', 'minions': ['jerry']}
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)

        try:
            pub_data = yield self.pub_async(
                  tgt,
                  fun,
                  arg,
                  tgt_type,
                  ret,
                  jid=jid,
                  timeout=self._get_timeout(timeout),
                  io_loop=io_loop,
                  listen=listen,
                  **kwargs)
        except SaltClientError:
            # Re-raise error with specific message
            raise SaltClientError(
                'The salt master could not be contacted. Is master running?'
            )
        except AuthenticationError as err:
            raise AuthenticationError(err)
        except AuthorizationError as err:
            raise AuthorizationError(err)
        except Exception as general_exception:
            # Convert to generic client error and pass along message
            raise SaltClientError(general_exception)

        raise tornado.gen.Return(self._check_pub_data(pub_data, listen=listen))

    def cmd_async(
            self,
            tgt,
            fun,
            arg=(),
            tgt_type='glob',
            ret='',
            jid='',
            kwarg=None,
            **kwargs):
        '''
        Asynchronously send a command to connected minions

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :returns: A job ID or 0 on failure.

        .. code-block:: python

            >>> local.cmd_async('*', 'test.sleep', [300])
            '20131219215921857715'
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)
        pub_data = self.run_job(tgt,
                                fun,
                                arg,
                                tgt_type,
                                ret,
                                jid=jid,
                                listen=False,
                                **kwargs)
        try:
            return pub_data['jid']
        except KeyError:
            return 0

    def cmd_subset(
            self,
            tgt,
            fun,
            arg=(),
            tgt_type='glob',
            ret='',
            kwarg=None,
            sub=3,
            cli=False,
            progress=False,
            full_return=False,
            **kwargs):
        '''
        Execute a command on a random subset of the targeted systems

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :param sub: The number of systems to execute on
        :param cli: When this is set to True, a generator is returned,
                    otherwise a dictionary of the minion returns is returned

        .. code-block:: python

            >>> SLC.cmd_subset('*', 'test.ping', sub=1)
            {'jerry': True}
        '''
        minion_ret = self.cmd(tgt,
                              'sys.list_functions',
                              tgt_type=tgt_type,
                              **kwargs)
        minions = list(minion_ret)
        random.shuffle(minions)
        f_tgt = []
        for minion in minions:
            if fun in minion_ret[minion]:
                f_tgt.append(minion)
            if len(f_tgt) >= sub:
                break
        func = self.cmd
        if cli:
            func = self.cmd_cli
        return func(
                f_tgt,
                fun,
                arg,
                tgt_type='list',
                ret=ret,
                kwarg=kwarg,
                progress=progress,
                full_return=full_return,
                **kwargs)

    def cmd_batch(
            self,
            tgt,
            fun,
            arg=(),
            tgt_type='glob',
            ret='',
            kwarg=None,
            batch='10%',
            **kwargs):
        '''
        Iteratively execute a command on subsets of minions at a time

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :param batch: The batch identifier of systems to execute on

        :returns: A generator of minion returns

        .. code-block:: python

            >>> returns = local.cmd_batch('*', 'state.highstate', batch='10%')
            >>> for ret in returns:
            ...     print(ret)
            {'jerry': {...}}
            {'dave': {...}}
            {'stewart': {...}}
        '''
        # We need to re-import salt.utils.args here
        # even though it has already been imported.
        # when cmd_batch is called via the NetAPI
        # the module is unavailable.
        import salt.utils.args

        # Late import - not used anywhere else in this file
        import salt.cli.batch

        arg = salt.utils.args.condition_input(arg, kwarg)
        opts = {'tgt': tgt,
                'fun': fun,
                'arg': arg,
                'tgt_type': tgt_type,
                'ret': ret,
                'batch': batch,
                'failhard': kwargs.get('failhard', self.opts.get('failhard', False)),
                'raw': kwargs.get('raw', False)}

        if 'timeout' in kwargs:
            opts['timeout'] = kwargs['timeout']
        if 'gather_job_timeout' in kwargs:
            opts['gather_job_timeout'] = kwargs['gather_job_timeout']
        if 'batch_wait' in kwargs:
            opts['batch_wait'] = int(kwargs['batch_wait'])

        eauth = {}
        if 'eauth' in kwargs:
            eauth['eauth'] = kwargs.pop('eauth')
        if 'username' in kwargs:
            eauth['username'] = kwargs.pop('username')
        if 'password' in kwargs:
            eauth['password'] = kwargs.pop('password')
        if 'token' in kwargs:
            eauth['token'] = kwargs.pop('token')

        for key, val in six.iteritems(self.opts):
            if key not in opts:
                opts[key] = val
        batch = salt.cli.batch.Batch(opts, eauth=eauth, quiet=True)
        for ret in batch.run():
            yield ret

    def cmd(self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type='glob',
            ret='',
            jid='',
            full_return=False,
            kwarg=None,
            **kwargs):
        '''
        Synchronously execute a command on targeted minions

        The cmd method will execute and wait for the timeout period for all
        minions to reply, then it will return all minion data at once.

        .. code-block:: python

            >>> import salt.client
            >>> local = salt.client.LocalClient()
            >>> local.cmd('*', 'cmd.run', ['whoami'])
            {'jerry': 'root'}

        With extra keyword arguments for the command function to be run:

        .. code-block:: python

            local.cmd('*', 'test.arg', ['arg1', 'arg2'], kwarg={'foo': 'bar'})

        Compound commands can be used for multiple executions in a single
        publish. Function names and function arguments are provided in separate
        lists but the index values must correlate and an empty list must be
        used if no arguments are required.

        .. code-block:: python

            >>> local.cmd('*', [
                    'grains.items',
                    'sys.doc',
                    'cmd.run',
                ],
                [
                    [],
                    [],
                    ['uptime'],
                ])

        :param tgt: Which minions to target for the execution. Default is shell
            glob. Modified by the ``tgt_type`` option.
        :type tgt: string or list

        :param fun: The module and function to call on the specified minions of
            the form ``module.function``. For example ``test.ping`` or
            ``grains.items``.

            Compound commands
                Multiple functions may be called in a single publish by
                passing a list of commands. This can dramatically lower
                overhead and speed up the application communicating with Salt.

                This requires that the ``arg`` param is a list of lists. The
                ``fun`` list and the ``arg`` list must correlate by index
                meaning a function that does not take arguments must still have
                a corresponding empty list at the expected index.
        :type fun: string or list of strings

        :param arg: A list of arguments to pass to the remote function. If the
            function takes no arguments ``arg`` may be omitted except when
            executing a compound command.
        :type arg: list or list-of-lists

        :param timeout: Seconds to wait after the last minion returns but
            before all minions return.

        :param tgt_type: The type of ``tgt``. Allowed values:

            * ``glob`` - Bash glob completion - Default
            * ``pcre`` - Perl style regular expression
            * ``list`` - Python list of hosts
            * ``grain`` - Match based on a grain comparison
            * ``grain_pcre`` - Grain comparison with a regex
            * ``pillar`` - Pillar data comparison
            * ``pillar_pcre`` - Pillar data comparison with a regex
            * ``nodegroup`` - Match on nodegroup
            * ``range`` - Use a Range server for matching
            * ``compound`` - Pass a compound match string
            * ``ipcidr`` - Match based on Subnet (CIDR notation) or IPv4 address.

            .. versionchanged:: 2017.7.0
                Renamed from ``expr_form`` to ``tgt_type``

        :param ret: The returner to use. The value passed can be single
            returner, or a comma delimited list of returners to call in order
            on the minions

        :param kwarg: A dictionary with keyword arguments for the function.

        :param full_return: Output the job return only (default) or the full
            return including exit code and other job metadata.

        :param kwargs: Optional keyword arguments.
            Authentication credentials may be passed when using
            :conf_master:`external_auth`.

            For example: ``local.cmd('*', 'test.ping', username='saltdev',
            password='saltdev', eauth='pam')``.
            Or: ``local.cmd('*', 'test.ping',
            token='5871821ea51754fdcea8153c1c745433')``

        :returns: A dictionary with the result of the execution, keyed by
            minion ID. A compound command will return a sub-dictionary keyed by
            function name.
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)
        was_listening = self.event.cpub

        try:
            pub_data = self.run_job(tgt,
                                    fun,
                                    arg,
                                    tgt_type,
                                    ret,
                                    timeout,
                                    jid,
                                    listen=True,
                                    **kwargs)

            if not pub_data:
                return pub_data

            ret = {}
            for fn_ret in self.get_cli_event_returns(
                    pub_data['jid'],
                    pub_data['minions'],
                    self._get_timeout(timeout),
                    tgt,
                    tgt_type,
                    **kwargs):

                if fn_ret:
                    for mid, data in six.iteritems(fn_ret):
                        ret[mid] = (data if full_return
                                else data.get('ret', {}))

            for failed in list(set(pub_data['minions']) - set(ret)):
                ret[failed] = False
            return ret
        finally:
            if not was_listening:
                self.event.close_pub()

    def cmd_cli(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type='glob',
            ret='',
            verbose=False,
            kwarg=None,
            progress=False,
            **kwargs):
        '''
        Used by the :command:`salt` CLI. This method returns minion returns as
        they come back and attempts to block until all minions return.

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :param verbose: Print extra information about the running command
        :returns: A generator
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)
        was_listening = self.event.cpub

        try:
            self.pub_data = self.run_job(
                tgt,
                fun,
                arg,
                tgt_type,
                ret,
                timeout,
                listen=True,
                **kwargs)

            if not self.pub_data:
                yield self.pub_data
            else:
                try:
                    for fn_ret in self.get_cli_event_returns(
                            self.pub_data['jid'],
                            self.pub_data['minions'],
                            self._get_timeout(timeout),
                            tgt,
                            tgt_type,
                            verbose,
                            progress,
                            **kwargs):

                        if not fn_ret:
                            continue

                        yield fn_ret
                except KeyboardInterrupt:
                    raise SystemExit(
                        '\n'
                        'This job\'s jid is: {0}\n'
                        'Exiting gracefully on Ctrl-c\n'
                        'The minions may not have all finished running and any '
                        'remaining minions will return upon completion. To look '
                        'up the return data for this job later, run the following '
                        'command:\n\n'
                        'salt-run jobs.lookup_jid {0}'.format(self.pub_data['jid'])
                    )
        finally:
            if not was_listening:
                self.event.close_pub()

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
        Yields the individual minion returns as they come in

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        Normally :py:meth:`cmd_iter` does not yield results for minions that
        are not connected. If you want it to return results for disconnected
        minions set `expect_minions=True` in `kwargs`.

        :return: A generator yielding the individual minion returns

        .. code-block:: python

            >>> ret = local.cmd_iter('*', 'test.ping')
            >>> for i in ret:
            ...     print(i)
            {'jerry': {'ret': True}}
            {'dave': {'ret': True}}
            {'stewart': {'ret': True}}
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)
        was_listening = self.event.cpub

        try:
            pub_data = self.run_job(
                tgt,
                fun,
                arg,
                tgt_type,
                ret,
                timeout,
                listen=True,
                **kwargs)

            if not pub_data:
                yield pub_data
            else:
                if kwargs.get('yield_pub_data'):
                    yield pub_data
                for fn_ret in self.get_iter_returns(pub_data['jid'],
                                                    pub_data['minions'],
                                                    timeout=self._get_timeout(timeout),
                                                    tgt=tgt,
                                                    tgt_type=tgt_type,
                                                    **kwargs):
                    if not fn_ret:
                        continue
                    yield fn_ret
                self._clean_up_subscriptions(pub_data['jid'])
        finally:
            if not was_listening:
                self.event.close_pub()

    def cmd_iter_no_block(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type='glob',
            ret='',
            kwarg=None,
            show_jid=False,
            verbose=False,
            **kwargs):
        '''
        Yields the individual minion returns as they come in, or None
            when no returns are available.

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :returns: A generator yielding the individual minion returns, or None
            when no returns are available. This allows for actions to be
            injected in between minion returns.

        .. code-block:: python

            >>> ret = local.cmd_iter_no_block('*', 'test.ping')
            >>> for i in ret:
            ...     print(i)
            None
            {'jerry': {'ret': True}}
            {'dave': {'ret': True}}
            None
            {'stewart': {'ret': True}}
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)
        was_listening = self.event.cpub

        try:
            pub_data = self.run_job(
                tgt,
                fun,
                arg,
                tgt_type,
                ret,
                timeout,
                listen=True,
                **kwargs)

            if not pub_data:
                yield pub_data
            else:
                for fn_ret in self.get_iter_returns(pub_data['jid'],
                                                    pub_data['minions'],
                                                    timeout=timeout,
                                                    tgt=tgt,
                                                    tgt_type=tgt_type,
                                                    block=False,
                                                    **kwargs):
                    if fn_ret and any([show_jid, verbose]):
                        for minion in fn_ret:
                            fn_ret[minion]['jid'] = pub_data['jid']
                    yield fn_ret

                self._clean_up_subscriptions(pub_data['jid'])
        finally:
            if not was_listening:
                self.event.close_pub()

    def cmd_full_return(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type='glob',
            ret='',
            verbose=False,
            kwarg=None,
            **kwargs):
        '''
        Execute a salt command and return
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)
        was_listening = self.event.cpub

        try:
            pub_data = self.run_job(
                tgt,
                fun,
                arg,
                tgt_type,
                ret,
                timeout,
                listen=True,
                **kwargs)

            if not pub_data:
                return pub_data

            return (self.get_cli_static_event_returns(pub_data['jid'],
                                                      pub_data['minions'],
                                                      timeout,
                                                      tgt,
                                                      tgt_type,
                                                      verbose))
        finally:
            if not was_listening:
                self.event.close_pub()

    def get_cli_returns(
            self,
            jid,
            minions,
            timeout=None,
            tgt='*',
            tgt_type='glob',
            verbose=False,
            show_jid=False,
            **kwargs):
        '''
        Starts a watcher looking at the return data for a specified JID

        :returns: all of the information for the JID
        '''
        if verbose:
            msg = 'Executing job with jid {0}'.format(jid)
            print(msg)
            print('-' * len(msg) + '\n')
        elif show_jid:
            print('jid: {0}'.format(jid))
        if timeout is None:
            timeout = self.opts['timeout']
        fret = {}
        # make sure the minions is a set (since we do set operations on it)
        minions = set(minions)

        found = set()
        # start this before the cache lookup-- in case new stuff comes in
        event_iter = self.get_event_iter_returns(jid, minions, timeout=timeout)

        # get the info from the cache
        ret = self.get_cache_returns(jid)
        if ret != {}:
            found.update(set(ret))
            yield ret

        # if you have all the returns, stop
        if len(found.intersection(minions)) >= len(minions):
            raise StopIteration()

        # otherwise, get them from the event system
        for event in event_iter:
            if event != {}:
                found.update(set(event))
                yield event
            if len(found.intersection(minions)) >= len(minions):
                self._clean_up_subscriptions(jid)
                raise StopIteration()

    # TODO: tests!!
    def get_returns_no_block(
            self,
            tag,
            match_type=None):
        '''
        Raw function to just return events of jid excluding timeout logic

        Yield either the raw event data or None

        Pass a list of additional regular expressions as `tags_regex` to search
        the event bus for non-return data, such as minion lists returned from
        syndics.
        '''

        while True:
            raw = self.event.get_event(wait=0.01, tag=tag, match_type=match_type, full=True,
                                       no_block=True, auto_reconnect=self.auto_reconnect)
            yield raw

    def get_iter_returns(
            self,
            jid,
            minions,
            timeout=None,
            tgt='*',
            tgt_type='glob',
            expect_minions=False,
            block=True,
            **kwargs):
        '''
        Watch the event system and return job data as it comes in

        :returns: all of the information for the JID
        '''
        if not isinstance(minions, set):
            if isinstance(minions, six.string_types):
                minions = set([minions])
            elif isinstance(minions, (list, tuple)):
                minions = set(list(minions))

        if timeout is None:
            timeout = self.opts['timeout']
        gather_job_timeout = int(kwargs.get('gather_job_timeout', self.opts['gather_job_timeout']))
        start = int(time.time())

        # timeouts per minion, id_ -> timeout time
        minion_timeouts = {}

        found = set()
        missing = set()
        # Check to see if the jid is real, if not return the empty dict
        try:
            if self.returners['{0}.get_load'.format(self.opts['master_job_cache'])](jid) == {}:
                log.warning('jid does not exist')
                yield {}
                # stop the iteration, since the jid is invalid
                raise StopIteration()
        except Exception as exc:
            log.warning('Returner unavailable: %s', exc, exc_info_on_loglevel=logging.DEBUG)
        # Wait for the hosts to check in
        last_time = False
        # iterator for this job's return
        if self.opts['order_masters']:
            # If we are a MoM, we need to gather expected minions from downstreams masters.
            ret_iter = self.get_returns_no_block('(salt/job|syndic/.*)/{0}'.format(jid), 'regex')
        else:
            ret_iter = self.get_returns_no_block('salt/job/{0}'.format(jid))
        # iterator for the info of this job
        jinfo_iter = []
        # open event jids that need to be un-subscribed from later
        open_jids = set()
        timeout_at = time.time() + timeout
        gather_syndic_wait = time.time() + self.opts['syndic_wait']
        # are there still minions running the job out there
        # start as True so that we ping at least once
        minions_running = True
        log.debug(
            'get_iter_returns for jid %s sent to %s will timeout at %s',
            jid, minions, datetime.fromtimestamp(timeout_at).time()
        )
        while True:
            # Process events until timeout is reached or all minions have returned
            for raw in ret_iter:
                # if we got None, then there were no events
                if raw is None:
                    break
                if 'minions' in raw.get('data', {}):
                    minions.update(raw['data']['minions'])
                    if 'missing' in raw.get('data', {}):
                        missing.update(raw['data']['missing'])
                    continue
                if 'return' not in raw['data']:
                    continue
                if kwargs.get('raw', False):
                    found.add(raw['data']['id'])
                    yield raw
                else:
                    found.add(raw['data']['id'])
                    ret = {raw['data']['id']: {'ret': raw['data']['return']}}
                    if 'out' in raw['data']:
                        ret[raw['data']['id']]['out'] = raw['data']['out']
                    if 'retcode' in raw['data']:
                        ret[raw['data']['id']]['retcode'] = raw['data']['retcode']
                    if 'jid' in raw['data']:
                        ret[raw['data']['id']]['jid'] = raw['data']['jid']
                    if kwargs.get('_cmd_meta', False):
                        ret[raw['data']['id']].update(raw['data'])
                    log.debug('jid %s return from %s', jid, raw['data']['id'])
                    yield ret

            # if we have all of the returns (and we aren't a syndic), no need for anything fancy
            if len(found.intersection(minions)) >= len(minions) and not self.opts['order_masters']:
                # All minions have returned, break out of the loop
                log.debug('jid %s found all minions %s', jid, found)
                break
            elif len(found.intersection(minions)) >= len(minions) and self.opts['order_masters']:
                if len(found) >= len(minions) and len(minions) > 0 and time.time() > gather_syndic_wait:
                    # There were some minions to find and we found them
                    # However, this does not imply that *all* masters have yet responded with expected minion lists.
                    # Therefore, continue to wait up to the syndic_wait period (calculated in gather_syndic_wait) to see
                    # if additional lower-level masters deliver their lists of expected
                    # minions.
                    break
            # If we get here we may not have gathered the minion list yet. Keep waiting
            # for all lower-level masters to respond with their minion lists

            # let start the timeouts for all remaining minions

            for id_ in minions - found:
                # if we have a new minion in the list, make sure it has a timeout
                if id_ not in minion_timeouts:
                    minion_timeouts[id_] = time.time() + timeout

            # if the jinfo has timed out and some minions are still running the job
            # re-do the ping
            if time.time() > timeout_at and minions_running:
                # since this is a new ping, no one has responded yet
                jinfo = self.gather_job_info(jid, list(minions - found), 'list', **kwargs)
                minions_running = False
                # if we weren't assigned any jid that means the master thinks
                # we have nothing to send
                if 'jid' not in jinfo:
                    jinfo_iter = []
                else:
                    jinfo_iter = self.get_returns_no_block('salt/job/{0}'.format(jinfo['jid']))
                timeout_at = time.time() + gather_job_timeout
                # if you are a syndic, wait a little longer
                if self.opts['order_masters']:
                    timeout_at += self.opts.get('syndic_wait', 1)

            # check for minions that are running the job still
            for raw in jinfo_iter:
                # if there are no more events, lets stop waiting for the jinfo
                if raw is None:
                    break
                try:
                    if raw['data']['retcode'] > 0:
                        log.error('saltutil returning errors on minion %s', raw['data']['id'])
                        minions.remove(raw['data']['id'])
                        break
                except KeyError as exc:
                    # This is a safe pass. We're just using the try/except to
                    # avoid having to deep-check for keys.
                    missing_key = exc.__str__().strip('\'"')
                    if missing_key == 'retcode':
                        log.debug('retcode missing from client return')
                    else:
                        log.debug(
                            'Passing on saltutil error. Key \'%s\' missing '
                            'from client return. This may be an error in '
                            'the client.', missing_key
                        )
                # Keep track of the jid events to unsubscribe from later
                open_jids.add(jinfo['jid'])

                # TODO: move to a library??
                if 'minions' in raw.get('data', {}):
                    minions.update(raw['data']['minions'])
                    continue
                if 'syndic' in raw.get('data', {}):
                    minions.update(raw['syndic'])
                    continue
                if 'return' not in raw.get('data', {}):
                    continue

                # if the job isn't running there anymore... don't count
                if raw['data']['return'] == {}:
                    continue

                # if the minion throws an exception containing the word "return"
                # the master will try to handle the string as a dict in the next
                # step. Check if we have a string, log the issue and continue.
                if isinstance(raw['data']['return'], six.string_types):
                    log.error("unexpected return from minion: %s", raw)
                    continue

                if 'return' in raw['data']['return'] and \
                    raw['data']['return']['return'] == {}:
                    continue

                # if we didn't originally target the minion, lets add it to the list
                if raw['data']['id'] not in minions:
                    minions.add(raw['data']['id'])
                # update this minion's timeout, as long as the job is still running
                minion_timeouts[raw['data']['id']] = time.time() + timeout
                # a minion returned, so we know its running somewhere
                minions_running = True

            # if we have hit gather_job_timeout (after firing the job) AND
            # if we have hit all minion timeouts, lets call it
            now = time.time()
            # if we have finished waiting, and no minions are running the job
            # then we need to see if each minion has timedout
            done = (now > timeout_at) and not minions_running
            if done:
                # if all minions have timeod out
                for id_ in minions - found:
                    if now < minion_timeouts[id_]:
                        done = False
                        break
            if done:
                break

            # don't spin
            if block:
                time.sleep(0.01)
            else:
                yield

        # If there are any remaining open events, clean them up.
        if open_jids:
            for jid in open_jids:
                self.event.unsubscribe(jid)

        if expect_minions:
            for minion in list((minions - found)):
                yield {minion: {'failed': True}}

        # Filter out any minions marked as missing for which we received
        # returns (prevents false events sent due to higher-level masters not
        # knowing about lower-level minions).
        missing -= found

        # Report on missing minions
        if missing:
            for minion in missing:
                yield {minion: {'failed': True}}

    def get_returns(
            self,
            jid,
            minions,
            timeout=None):
        '''
        Get the returns for the command line interface via the event system
        '''
        minions = set(minions)
        if timeout is None:
            timeout = self.opts['timeout']
        start = int(time.time())
        timeout_at = start + timeout
        log.debug(
            'get_returns for jid %s sent to %s will timeout at %s',
            jid, minions, datetime.fromtimestamp(timeout_at).time()
        )

        found = set()
        ret = {}
        # Check to see if the jid is real, if not return the empty dict
        try:
            if self.returners['{0}.get_load'.format(self.opts['master_job_cache'])](jid) == {}:
                log.warning('jid does not exist')
                return ret
        except Exception as exc:
            raise SaltClientError('Master job cache returner [{0}] failed to verify jid. '
                                  'Exception details: {1}'.format(self.opts['master_job_cache'], exc))

        # Wait for the hosts to check in
        while True:
            time_left = timeout_at - int(time.time())
            wait = max(1, time_left)
            raw = self.event.get_event(wait, jid, auto_reconnect=self.auto_reconnect)
            if raw is not None and 'return' in raw:
                found.add(raw['id'])
                ret[raw['id']] = raw['return']
                if len(found.intersection(minions)) >= len(minions):
                    # All minions have returned, break out of the loop
                    log.debug('jid %s found all minions', jid)
                    break
                continue
            # Then event system timeout was reached and nothing was returned
            if len(found.intersection(minions)) >= len(minions):
                # All minions have returned, break out of the loop
                log.debug('jid %s found all minions', jid)
                break
            if int(time.time()) > timeout_at:
                log.info(
                    'jid %s minions %s did not return in time',
                    jid, (minions - found)
                )
                break
            time.sleep(0.01)
        return ret

    def get_full_returns(self, jid, minions, timeout=None):
        '''
        This method starts off a watcher looking at the return data for
        a specified jid, it returns all of the information for the jid
        '''
        # TODO: change this from ret to return... or the other way.
        #       Its inconsistent, we should pick one

        ret = {}
        # create the iterator-- since we want to get anyone in the middle
        event_iter = self.get_event_iter_returns(jid, minions, timeout=timeout)

        try:
            data = self.returners['{0}.get_jid'.format(self.opts['master_job_cache'])](jid)
        except Exception as exc:
            raise SaltClientError('Returner {0} could not fetch jid data. '
                                  'Exception details: {1}'.format(
                                      self.opts['master_job_cache'],
                                      exc))
        for minion in data:
            m_data = {}
            if 'return' in data[minion]:
                m_data['ret'] = data[minion].get('return')
            else:
                m_data['ret'] = data[minion].get('return')
            if 'out' in data[minion]:
                m_data['out'] = data[minion]['out']
            if minion in ret:
                ret[minion].update(m_data)
            else:
                ret[minion] = m_data

        # if we have all the minion returns, lets just return
        if len(set(ret).intersection(minions)) >= len(minions):
            return ret

        # otherwise lets use the listener we created above to get the rest
        for event_ret in event_iter:
            # if nothing in the event_ret, skip
            if event_ret == {}:
                time.sleep(0.02)
                continue
            for minion, m_data in six.iteritems(event_ret):
                if minion in ret:
                    ret[minion].update(m_data)
                else:
                    ret[minion] = m_data

            # are we done yet?
            if len(set(ret).intersection(minions)) >= len(minions):
                return ret

        # otherwise we hit the timeout, return what we have
        return ret

    def get_cache_returns(self, jid):
        '''
        Execute a single pass to gather the contents of the job cache
        '''
        ret = {}

        try:
            data = self.returners['{0}.get_jid'.format(self.opts['master_job_cache'])](jid)
        except Exception as exc:
            raise SaltClientError('Could not examine master job cache. '
                                  'Error occurred in {0} returner. '
                                  'Exception details: {1}'.format(self.opts['master_job_cache'],
                                                                  exc))
        for minion in data:
            m_data = {}
            if 'return' in data[minion]:
                m_data['ret'] = data[minion].get('return')
            else:
                m_data['ret'] = data[minion].get('return')
            if 'out' in data[minion]:
                m_data['out'] = data[minion]['out']
            if minion in ret:
                ret[minion].update(m_data)
            else:
                ret[minion] = m_data

        return ret

    def get_cli_static_event_returns(
            self,
            jid,
            minions,
            timeout=None,
            tgt='*',
            tgt_type='glob',
            verbose=False,
            show_timeout=False,
            show_jid=False):
        '''
        Get the returns for the command line interface via the event system
        '''
        log.trace('entered - function get_cli_static_event_returns()')
        minions = set(minions)
        if verbose:
            msg = 'Executing job with jid {0}'.format(jid)
            print(msg)
            print('-' * len(msg) + '\n')
        elif show_jid:
            print('jid: {0}'.format(jid))

        if timeout is None:
            timeout = self.opts['timeout']

        start = int(time.time())
        timeout_at = start + timeout
        found = set()
        ret = {}
        # Check to see if the jid is real, if not return the empty dict
        try:
            if self.returners['{0}.get_load'.format(self.opts['master_job_cache'])](jid) == {}:
                log.warning('jid does not exist')
                return ret
        except Exception as exc:
            raise SaltClientError('Load could not be retrieved from '
                                  'returner {0}. Exception details: {1}'.format(
                                      self.opts['master_job_cache'],
                                      exc))
        # Wait for the hosts to check in
        while True:
            # Process events until timeout is reached or all minions have returned
            time_left = timeout_at - int(time.time())
            # Wait 0 == forever, use a minimum of 1s
            wait = max(1, time_left)
            jid_tag = 'salt/job/{0}'.format(jid)
            raw = self.event.get_event(wait, jid_tag, auto_reconnect=self.auto_reconnect)
            if raw is not None and 'return' in raw:
                if 'minions' in raw.get('data', {}):
                    minions.update(raw['data']['minions'])
                    continue
                found.add(raw['id'])
                ret[raw['id']] = {'ret': raw['return']}
                ret[raw['id']]['success'] = raw.get('success', False)
                if 'out' in raw:
                    ret[raw['id']]['out'] = raw['out']
                if len(found.intersection(minions)) >= len(minions):
                    # All minions have returned, break out of the loop
                    break
                continue
            # Then event system timeout was reached and nothing was returned
            if len(found.intersection(minions)) >= len(minions):
                # All minions have returned, break out of the loop
                break
            if int(time.time()) > timeout_at:
                if verbose or show_timeout:
                    if self.opts.get('minion_data_cache', False) \
                            or tgt_type in ('glob', 'pcre', 'list'):
                        if len(found) < len(minions):
                            fail = sorted(list(minions.difference(found)))
                            for minion in fail:
                                ret[minion] = {
                                    'out': 'no_return',
                                    'ret': 'Minion did not return'
                                }
                break
            time.sleep(0.01)

        self._clean_up_subscriptions(jid)
        return ret

    def get_cli_event_returns(
            self,
            jid,
            minions,
            timeout=None,
            tgt='*',
            tgt_type='glob',
            verbose=False,
            progress=False,
            show_timeout=False,
            show_jid=False,
            **kwargs):
        '''
        Get the returns for the command line interface via the event system
        '''
        log.trace('func get_cli_event_returns()')

        if verbose:
            msg = 'Executing job with jid {0}'.format(jid)
            print(msg)
            print('-' * len(msg) + '\n')
        elif show_jid:
            print('jid: {0}'.format(jid))

        # lazy load the connected minions
        connected_minions = None
        return_count = 0

        for ret in self.get_iter_returns(jid,
                                         minions,
                                         timeout=timeout,
                                         tgt=tgt,
                                         tgt_type=tgt_type,
                                         # (gtmanfred) expect_minions is popped here incase it is passed from a client
                                         # call. If this is not popped, then it would be passed twice to
                                         # get_iter_returns.
                                         expect_minions=(kwargs.pop('expect_minions', False) or verbose or show_timeout),
                                         **kwargs
                                         ):
            log.debug('return event: %s', ret)
            return_count = return_count + 1
            if progress:
                for id_, min_ret in six.iteritems(ret):
                    if not min_ret.get('failed') is True:
                        yield {'minion_count': len(minions), 'return_count': return_count}
            # replace the return structure for missing minions
            for id_, min_ret in six.iteritems(ret):
                if min_ret.get('failed') is True:
                    if connected_minions is None:
                        connected_minions = salt.utils.minions.CkMinions(self.opts).connected_ids()
                    if self.opts['minion_data_cache'] \
                            and salt.cache.factory(self.opts).contains('minions/{0}'.format(id_), 'data') \
                            and connected_minions \
                            and id_ not in connected_minions:

                        yield {
                            id_: {
                                'out': 'no_return',
                                'ret': 'Minion did not return. [Not connected]',
                                'retcode': salt.defaults.exitcodes.EX_GENERIC
                            }
                        }
                    else:
                        # don't report syndics as unresponsive minions
                        if not os.path.exists(os.path.join(self.opts['syndic_dir'], id_)):
                            yield {
                                id_: {
                                    'out': 'no_return',
                                    'ret': 'Minion did not return. [No response]',
                                    'retcode': salt.defaults.exitcodes.EX_GENERIC
                                }
                            }
                else:
                    yield {id_: min_ret}

        self._clean_up_subscriptions(jid)

    def get_event_iter_returns(self, jid, minions, timeout=None):
        '''
        Gather the return data from the event system, break hard when timeout
        is reached.
        '''
        log.trace('entered - function get_event_iter_returns()')
        if timeout is None:
            timeout = self.opts['timeout']

        timeout_at = time.time() + timeout

        found = set()
        # Check to see if the jid is real, if not return the empty dict
        if self.returners['{0}.get_load'.format(self.opts['master_job_cache'])](jid) == {}:
            log.warning('jid does not exist')
            yield {}
            # stop the iteration, since the jid is invalid
            raise StopIteration()
        # Wait for the hosts to check in
        while True:
            raw = self.event.get_event(timeout, auto_reconnect=self.auto_reconnect)
            if raw is None or time.time() > timeout_at:
                # Timeout reached
                break
            if 'minions' in raw.get('data', {}):
                continue
            try:
                found.add(raw['id'])
                ret = {raw['id']: {'ret': raw['return']}}
            except KeyError:
                # Ignore other erroneous messages
                continue
            if 'out' in raw:
                ret[raw['id']]['out'] = raw['out']
            yield ret
            time.sleep(0.02)

    def _prep_pub(self,
                  tgt,
                  fun,
                  arg,
                  tgt_type,
                  ret,
                  jid,
                  timeout,
                  **kwargs):
        '''
        Set up the payload_kwargs to be sent down to the master
        '''
        if tgt_type == 'nodegroup':
            if tgt not in self.opts['nodegroups']:
                conf_file = self.opts.get(
                    'conf_file', 'the master config file'
                )
                raise SaltInvocationError(
                    'Node group {0} unavailable in {1}'.format(
                        tgt, conf_file
                    )
                )
            tgt = salt.utils.minions.nodegroup_comp(tgt,
                                                    self.opts['nodegroups'])
            tgt_type = 'compound'

        # Convert a range expression to a list of nodes and change expression
        # form to list
        if tgt_type == 'range' and HAS_RANGE:
            tgt = self._convert_range_to_list(tgt)
            tgt_type = 'list'

        # If an external job cache is specified add it to the ret list
        if self.opts.get('ext_job_cache'):
            if ret:
                ret += ',{0}'.format(self.opts['ext_job_cache'])
            else:
                ret = self.opts['ext_job_cache']

        # format the payload - make a function that does this in the payload
        #   module

        # Generate the standard keyword args to feed to format_payload
        payload_kwargs = {'cmd': 'publish',
                          'tgt': tgt,
                          'fun': fun,
                          'arg': arg,
                          'key': self.key,
                          'tgt_type': tgt_type,
                          'ret': ret,
                          'jid': jid}

        # if kwargs are passed, pack them.
        if kwargs:
            payload_kwargs['kwargs'] = kwargs

        # If we have a salt user, add it to the payload
        if self.opts['syndic_master'] and 'user' in kwargs:
            payload_kwargs['user'] = kwargs['user']
        elif self.salt_user:
            payload_kwargs['user'] = self.salt_user

        # If we're a syndication master, pass the timeout
        if self.opts['order_masters']:
            payload_kwargs['to'] = timeout

        return payload_kwargs

    def pub(self,
            tgt,
            fun,
            arg=(),
            tgt_type='glob',
            ret='',
            jid='',
            timeout=5,
            listen=False,
            **kwargs):
        '''
        Take the required arguments and publish the given command.
        Arguments:
            tgt:
                The tgt is a regex or a glob used to match up the ids on
                the minions. Salt works by always publishing every command
                to all of the minions and then the minions determine if
                the command is for them based on the tgt value.
            fun:
                The function name to be called on the remote host(s), this
                must be a string in the format "<modulename>.<function name>"
            arg:
                The arg option needs to be a tuple of arguments to pass
                to the calling function, if left blank
        Returns:
            jid:
                A string, as returned by the publisher, which is the job
                id, this will inform the client where to get the job results
            minions:
                A set, the targets that the tgt passed should match.
        '''
        # Make sure the publisher is running by checking the unix socket
        if (self.opts.get('ipc_mode', '') != 'tcp' and
                not os.path.exists(os.path.join(self.opts['sock_dir'],
                'publish_pull.ipc'))):
            log.error(
                'Unable to connect to the salt master publisher at %s',
                self.opts['sock_dir']
            )
            raise SaltClientError

        payload_kwargs = self._prep_pub(
                tgt,
                fun,
                arg,
                tgt_type,
                ret,
                jid,
                timeout,
                **kwargs)

        master_uri = 'tcp://{}:{}'.format(
            salt.utils.zeromq.ip_bracket(self.opts['interface']),
            six.text_type(self.opts['ret_port'])
        )

        with salt.transport.client.ReqChannel.factory(self.opts,
                                                      crypt='clear',
                                                      master_uri=master_uri) as channel:
            try:
                # Ensure that the event subscriber is connected.
                # If not, we won't get a response, so error out
                if listen and not self.event.connect_pub(timeout=timeout):
                    raise SaltReqTimeoutError()
                payload = channel.send(payload_kwargs, timeout=timeout)
            except SaltReqTimeoutError as err:
                log.error(err)
                raise SaltReqTimeoutError(
                    'Salt request timed out. The master is not responding. You '
                    'may need to run your command with `--async` in order to '
                    'bypass the congested event bus. With `--async`, the CLI tool '
                    'will print the job id (jid) and exit immediately without '
                    'listening for responses. You can then use '
                    '`salt-run jobs.lookup_jid` to look up the results of the job '
                    'in the job cache later.'
                )

            if not payload:
                # The master key could have changed out from under us! Regen
                # and try again if the key has changed
                key = self.__read_master_key()
                if key == self.key:
                    return payload
                self.key = key
                payload_kwargs['key'] = self.key
                payload = channel.send(payload_kwargs)

            error = payload.pop('error', None)
            if error is not None:
                if isinstance(error, dict):
                    err_name = error.get('name', '')
                    err_msg = error.get('message', '')
                    if err_name == 'AuthenticationError':
                        raise AuthenticationError(err_msg)
                    elif err_name == 'AuthorizationError':
                        raise AuthorizationError(err_msg)

                raise PublishError(error)

            if not payload:
                return payload

        return {'jid': payload['load']['jid'],
                'minions': payload['load']['minions']}

    @tornado.gen.coroutine
    def pub_async(self,
                  tgt,
                  fun,
                  arg=(),
                  tgt_type='glob',
                  ret='',
                  jid='',
                  timeout=5,
                  io_loop=None,
                  listen=True,
                  **kwargs):
        '''
        Take the required arguments and publish the given command.
        Arguments:
            tgt:
                The tgt is a regex or a glob used to match up the ids on
                the minions. Salt works by always publishing every command
                to all of the minions and then the minions determine if
                the command is for them based on the tgt value.
            fun:
                The function name to be called on the remote host(s), this
                must be a string in the format "<modulename>.<function name>"
            arg:
                The arg option needs to be a tuple of arguments to pass
                to the calling function, if left blank
        Returns:
            jid:
                A string, as returned by the publisher, which is the job
                id, this will inform the client where to get the job results
            minions:
                A set, the targets that the tgt passed should match.
        '''
        # Make sure the publisher is running by checking the unix socket
        if (self.opts.get('ipc_mode', '') != 'tcp' and
                not os.path.exists(os.path.join(self.opts['sock_dir'],
                'publish_pull.ipc'))):
            log.error(
                'Unable to connect to the salt master publisher at %s',
                self.opts['sock_dir']
            )
            raise SaltClientError

        payload_kwargs = self._prep_pub(
                tgt,
                fun,
                arg,
                tgt_type,
                ret,
                jid,
                timeout,
                **kwargs)

        master_uri = 'tcp://' + salt.utils.zeromq.ip_bracket(self.opts['interface']) + \
                     ':' + six.text_type(self.opts['ret_port'])

        with salt.transport.client.AsyncReqChannel.factory(self.opts,
                                                           io_loop=io_loop,
                                                           crypt='clear',
                                                           master_uri=master_uri) as channel:
            try:
                # Ensure that the event subscriber is connected.
                # If not, we won't get a response, so error out
                if listen and not self.event.connect_pub(timeout=timeout):
                    raise SaltReqTimeoutError()
                payload = yield channel.send(payload_kwargs, timeout=timeout)
            except SaltReqTimeoutError:
                raise SaltReqTimeoutError(
                    'Salt request timed out. The master is not responding. You '
                    'may need to run your command with `--async` in order to '
                    'bypass the congested event bus. With `--async`, the CLI tool '
                    'will print the job id (jid) and exit immediately without '
                    'listening for responses. You can then use '
                    '`salt-run jobs.lookup_jid` to look up the results of the job '
                    'in the job cache later.'
                )

            if not payload:
                # The master key could have changed out from under us! Regen
                # and try again if the key has changed
                key = self.__read_master_key()
                if key == self.key:
                    raise tornado.gen.Return(payload)
                self.key = key
                payload_kwargs['key'] = self.key
                payload = yield channel.send(payload_kwargs)

            error = payload.pop('error', None)
            if error is not None:
                if isinstance(error, dict):
                    err_name = error.get('name', '')
                    err_msg = error.get('message', '')
                    if err_name == 'AuthenticationError':
                        raise AuthenticationError(err_msg)
                    elif err_name == 'AuthorizationError':
                        raise AuthorizationError(err_msg)

                raise PublishError(error)

            if not payload:
                raise tornado.gen.Return(payload)

        raise tornado.gen.Return({'jid': payload['load']['jid'],
                                  'minions': payload['load']['minions']})

    # pylint: disable=W1701
    def __del__(self):
        # This IS really necessary!
        # When running tests, if self.events is not destroyed, we leak 2
        # threads per test case which uses self.client
        if hasattr(self, 'event'):
            # The call below will take care of calling 'self.event.destroy()'
            del self.event
    # pylint: enable=W1701

    def _clean_up_subscriptions(self, job_id):
        if self.opts.get('order_masters'):
            self.event.unsubscribe('syndic/.*/{0}'.format(job_id), 'regex')
        self.event.unsubscribe('salt/job/{0}'.format(job_id))


class FunctionWrapper(dict):
    '''
    Create a function wrapper that looks like the functions dict on the minion
    but invoked commands on the minion via a LocalClient.

    This allows SLS files to be loaded with an object that calls down to the
    minion when the salt functions dict is referenced.
    '''
    def __init__(self, opts, minion):
        super(FunctionWrapper, self).__init__()
        self.opts = opts
        self.minion = minion
        self.local = LocalClient(self.opts['conf_file'])
        self.functions = self.__load_functions()

    def __missing__(self, key):
        '''
        Since the function key is missing, wrap this call to a command to the
        minion of said key if it is available in the self.functions set
        '''
        if key not in self.functions:
            raise KeyError
        return self.run_key(key)

    def __load_functions(self):
        '''
        Find out what functions are available on the minion
        '''
        return set(self.local.cmd(self.minion,
                                  'sys.list_functions').get(self.minion, []))

    def run_key(self, key):
        '''
        Return a function that executes the arguments passed via the local
        client
        '''
        def func(*args, **kwargs):
            '''
            Run a remote call
            '''
            args = list(args)
            for _key, _val in kwargs:
                args.append('{0}={1}'.format(_key, _val))
            return self.local.cmd(self.minion, key, args)
        return func


class Caller(object):
    '''
    ``Caller`` is the same interface used by the :command:`salt-call`
    command-line tool on the Salt Minion.

    .. versionchanged:: 2015.8.0
        Added the ``cmd`` method for consistency with the other Salt clients.
        The existing ``function`` and ``sminion.functions`` interfaces still
        exist but have been removed from the docs.

    Importing and using ``Caller`` must be done on the same machine as a
    Salt Minion and it must be done using the same user that the Salt Minion is
    running as.

    Usage:

    .. code-block:: python

        import salt.client
        caller = salt.client.Caller()
        caller.cmd('test.ping')

    Note, a running master or minion daemon is not required to use this class.
    Running ``salt-call --local`` simply sets :conf_minion:`file_client` to
    ``'local'``. The same can be achieved at the Python level by including that
    setting in a minion config file.

    .. versionadded:: 2014.7.0
        Pass the minion config as the ``mopts`` dictionary.

    .. code-block:: python

        import salt.client
        import salt.config
        __opts__ = salt.config.minion_config('/etc/salt/minion')
        __opts__['file_client'] = 'local'
        caller = salt.client.Caller(mopts=__opts__)
    '''
    def __init__(self, c_path=os.path.join(syspaths.CONFIG_DIR, 'minion'),
            mopts=None):
        # Late-import of the minion module to keep the CLI as light as possible
        import salt.minion
        if mopts:
            self.opts = mopts
        else:
            self.opts = salt.config.minion_config(c_path)
        self.sminion = salt.minion.SMinion(self.opts)

    def cmd(self, fun, *args, **kwargs):
        '''
        Call an execution module with the given arguments and keyword arguments

        .. versionchanged:: 2015.8.0
            Added the ``cmd`` method for consistency with the other Salt clients.
            The existing ``function`` and ``sminion.functions`` interfaces still
            exist but have been removed from the docs.

        .. code-block:: python

            caller.cmd('test.arg', 'Foo', 'Bar', baz='Baz')

            caller.cmd('event.send', 'myco/myevent/something',
                data={'foo': 'Foo'}, with_env=['GIT_COMMIT'], with_grains=True)
        '''
        return self.sminion.functions[fun](*args, **kwargs)

    def function(self, fun, *args, **kwargs):
        '''
        Call a single salt function
        '''
        func = self.sminion.functions[fun]
        args, kwargs = salt.minion.load_args_and_kwargs(
            func,
            salt.utils.args.parse_input(args),
            kwargs)
        return func(*args, **kwargs)


class ProxyCaller(object):
    '''
    ``ProxyCaller`` is the same interface used by the :command:`salt-call`
    with the args ``--proxyid <proxyid>`` command-line tool on the Salt Proxy
    Minion.

    Importing and using ``ProxyCaller`` must be done on the same machine as a
    Salt Minion and it must be done using the same user that the Salt Minion is
    running as.

    Usage:

    .. code-block:: python

        import salt.client
        caller = salt.client.Caller()
        caller.cmd('test.ping')

    Note, a running master or minion daemon is not required to use this class.
    Running ``salt-call --local`` simply sets :conf_minion:`file_client` to
    ``'local'``. The same can be achieved at the Python level by including that
    setting in a minion config file.

    .. code-block:: python

        import salt.client
        import salt.config
        __opts__ = salt.config.proxy_config('/etc/salt/proxy', minion_id='quirky_edison')
        __opts__['file_client'] = 'local'
        caller = salt.client.ProxyCaller(mopts=__opts__)

    .. note::

        To use this for calling proxies, the :py:func:`is_proxy functions
        <salt.utils.platform.is_proxy>` requires that ``--proxyid`` be an
        argument on the commandline for the script this is used in, or that the
        string ``proxy`` is in the name of the script.
    '''
    def __init__(self, c_path=os.path.join(syspaths.CONFIG_DIR, 'proxy'), mopts=None):
        # Late-import of the minion module to keep the CLI as light as possible
        import salt.minion
        self.opts = mopts or salt.config.proxy_config(c_path)
        self.sminion = salt.minion.SProxyMinion(self.opts)

    def cmd(self, fun, *args, **kwargs):
        '''
        Call an execution module with the given arguments and keyword arguments

        .. code-block:: python

            caller.cmd('test.arg', 'Foo', 'Bar', baz='Baz')

            caller.cmd('event.send', 'myco/myevent/something',
                data={'foo': 'Foo'}, with_env=['GIT_COMMIT'], with_grains=True)
        '''
        func = self.sminion.functions[fun]
        data = {
          'arg': args,
          'fun': fun
        }
        data.update(kwargs)
        executors = getattr(self.sminion, 'module_executors', []) or \
                    self.opts.get('module_executors', ['direct_call'])
        if isinstance(executors, six.string_types):
            executors = [executors]
        for name in executors:
            fname = '{0}.execute'.format(name)
            if fname not in self.sminion.executors:
                raise SaltInvocationError("Executor '{0}' is not available".format(name))
            return_data = self.sminion.executors[fname](self.opts, data, func, args, kwargs)
            if return_data is not None:
                break
        return return_data
