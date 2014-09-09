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
from __future__ import print_function
import os
import time
import copy
import logging
from datetime import datetime
from salt._compat import string_types

# Import salt libs
import salt.config
import salt.payload
import salt.transport
import salt.loader
import salt.utils
import salt.utils.args
import salt.utils.event
import salt.utils.minions
import salt.utils.verify
import salt.syspaths as syspaths
from salt.exceptions import (
    EauthAuthenticationError, SaltInvocationError, SaltReqTimeoutError
)

# Try to import range from https://github.com/ytoolshed/range
HAS_RANGE = False
try:
    import seco.range
    HAS_RANGE = True
except ImportError:
    pass

log = logging.getLogger(__name__)


def get_local_client(
        c_path=os.path.join(syspaths.CONFIG_DIR, 'master'),
        mopts=None,
        skip_perm_errors=False):
    '''
    .. versionadded:: 2014.7.0

    Read in the config and return the correct LocalClient object based on
    the configured transport
    '''
    if mopts:
        opts = mopts
    else:
        import salt.config
        opts = salt.config.client_config(c_path)
    if opts['transport'] == 'raet':
        import salt.client.raet
        return salt.client.raet.LocalClient(mopts=opts)
    elif opts['transport'] == 'zeromq':
        return LocalClient(mopts=opts, skip_perm_errors=skip_perm_errors)


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

    .. code-block:: python

        import salt.client

        local = salt.client.LocalClient()
        local.cmd('*', 'test.fib', [10])
    '''
    def __init__(self,
                 c_path=os.path.join(syspaths.CONFIG_DIR, 'master'),
                 mopts=None, skip_perm_errors=False):
        if mopts:
            self.opts = mopts
        else:
            if os.path.isdir(c_path):
                log.warning(
                    '{0} expects a file path not a directory path({1}) to '
                    'it\'s \'c_path\' keyword argument'.format(
                        self.__class__.__name__, c_path
                    )
                )
            self.opts = salt.config.client_config(c_path)
        self.serial = salt.payload.Serial(self.opts)
        self.salt_user = self.__get_user()
        self.skip_perm_errors = skip_perm_errors
        self.key = self.__read_master_key()
        self.event = salt.utils.event.get_event(
                'master',
                self.opts['sock_dir'],
                self.opts['transport'],
                listen=not self.opts.get('__worker', False))

        self.returners = salt.loader.returners(self.opts, {})

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
        keyfile = os.path.join(self.opts['cachedir'],
                               '.{0}_key'.format(key_user))
        # Make sure all key parent directories are accessible
        salt.utils.verify.check_path_traversal(self.opts['cachedir'],
                                               key_user,
                                               self.skip_perm_errors)

        try:
            with salt.utils.fopen(keyfile, 'r') as key:
                return key.read()
        except (OSError, IOError):
            # Fall back to eauth
            return ''

    def __get_user(self):
        '''
        Determine the current user running the salt command
        '''
        user = salt.utils.get_user()
        # if our user is root, look for other ways to figure out
        # who we are
        env_vars = ('SUDO_USER',)
        if user == 'root' or user == self.opts['user']:
            for evar in env_vars:
                if evar in os.environ:
                    return 'sudo_{0}'.format(os.environ[evar])
        return user

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
        if isinstance(timeout, string_types):
            try:
                return int(timeout)
            except ValueError:
                return self.opts['timeout']
        # Looks like the timeout is invalid, use config
        return self.opts['timeout']

    def gather_job_info(self, jid, tgt, tgt_type, minions, **kwargs):
        '''
        Return the information about a given job
        '''
        log.debug('Checking whether jid {0} is still running'.format(jid))
        timeout = self.opts['gather_job_timeout']

        pub_data = self.run_job(tgt,
                                'saltutil.find_job',
                                arg=[jid],
                                expr_form=tgt_type,
                                timeout=timeout,
                               )

        if not pub_data:
            return pub_data

        minions.update(pub_data['minions'])

        return self.get_returns(pub_data['jid'],
                                minions,
                                self._get_timeout(timeout),
                                pending_tags=[jid])

    def _check_pub_data(self, pub_data):
        '''
        Common checks on the pub_data data structure returned from running pub
        '''
        if not pub_data:
            # Failed to autnenticate, this could be a bunch of things
            raise EauthAuthenticationError(
                'Failed to authenticate!  This is most likely because this '
                'user is not permitted to execute commands, but there is a '
                'small possibility that a disk error ocurred (check '
                'disk/inode usage).'
            )

        # Failed to connect to the master and send the pub
        if 'jid' not in pub_data:
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

        return pub_data

    def run_job(
            self,
            tgt,
            fun,
            arg=(),
            expr_form='glob',
            ret='',
            timeout=None,
            kwarg=None,
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
        jid = ''

        # Subscribe to all events and subscribe as early as possible
        self.event.subscribe(jid)

        pub_data = self.pub(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            jid=jid,
            timeout=self._get_timeout(timeout),
            **kwargs)

        return self._check_pub_data(pub_data)

    def cmd_async(
            self,
            tgt,
            fun,
            arg=(),
            expr_form='glob',
            ret='',
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
                                expr_form,
                                ret,
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
            expr_form='glob',
            ret='',
            kwarg=None,
            sub=3,
            cli=False,
            **kwargs):
        '''
        Execute a command on a random subset of the targeted systems

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :param sub: The number of systems to execute on

        .. code-block:: python

            >>> SLC.cmd_subset('*', 'test.ping', sub=1)
            {'jerry': True}
        '''
        group = self.cmd(tgt, 'sys.list_functions', expr_form=expr_form)
        f_tgt = []
        for minion, ret in group.items():
            if len(f_tgt) >= sub:
                break
            if fun in ret:
                f_tgt.append(minion)
        func = self.cmd
        if cli:
            func = self.cmd_cli
        return func(
                f_tgt,
                fun,
                arg,
                expr_form='list',
                ret=ret,
                kwarg=kwarg,
                **kwargs)

    def cmd_batch(
            self,
            tgt,
            fun,
            arg=(),
            expr_form='glob',
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

            >>> returns = local.cmd_batch('*', 'state.highstate', bat='10%')
            >>> for return in returns:
            ...     print return
            {'jerry': {...}}
            {'dave': {...}}
            {'stewart': {...}}
        '''
        import salt.cli.batch
        arg = salt.utils.args.condition_input(arg, kwarg)
        opts = {'tgt': tgt,
                'fun': fun,
                'arg': arg,
                'expr_form': expr_form,
                'ret': ret,
                'batch': batch,
                'raw': kwargs.get('raw', False)}
        for key, val in self.opts.items():
            if key not in opts:
                opts[key] = val
        batch = salt.cli.batch.Batch(opts, quiet=True)
        for ret in batch.run():
            yield ret

    def cmd(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            expr_form='glob',
            ret='',
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
            glob. Modified by the ``expr_form`` option.
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

        :param expr_form: The type of ``tgt``. Allowed values:

            * ``glob`` - Bash glob completion - Default
            * ``pcre`` - Perl style regular expression
            * ``list`` - Python list of hosts
            * ``grain`` - Match based on a grain comparison
            * ``grain_pcre`` - Grain comparison with a regex
            * ``pillar`` - Pillar data comparison
            * ``nodegroup`` - Match on nodegroup
            * ``range`` - Use a Range server for matching
            * ``compound`` - Pass a compound match string

        :param ret: The returner to use. The value passed can be single
            returner, or a comma delimited list of returners to call in order
            on the minions

        :param kwarg: A dictionary with keyword arguments for the function.

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
        pub_data = self.run_job(tgt,
                                fun,
                                arg,
                                expr_form,
                                ret,
                                timeout,
                                **kwargs)

        if not pub_data:
            return pub_data

        ret = {}
        for fn_ret in self.get_cli_event_returns(
                pub_data['jid'],
                pub_data['minions'],
                self._get_timeout(timeout),
                tgt,
                expr_form,
                **kwargs):

            if fn_ret:
                for mid, data in fn_ret.items():
                    ret[mid] = data.get('ret', {})

        return ret

    def cmd_cli(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            expr_form='glob',
            ret='',
            verbose=False,
            kwarg=None,
            **kwargs):
        '''
        Used by the :command:`salt` CLI. This method returns minion returns as
        the come back and attempts to block until all minions return.

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :param verbose: Print extra information about the running command
        :returns: A generator
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)
        pub_data = self.run_job(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            timeout,
            **kwargs)

        if not pub_data:
            yield pub_data
        else:
            try:
                for fn_ret in self.get_cli_event_returns(
                        pub_data['jid'],
                        pub_data['minions'],
                        self._get_timeout(timeout),
                        tgt,
                        expr_form,
                        verbose,
                        **kwargs):

                    if not fn_ret:
                        continue

                    yield fn_ret
            except KeyboardInterrupt:
                msg = ('Exiting on Ctrl-C\nThis job\'s jid is:\n{0}\n'
                       'The minions may not have all finished running and any '
                       'remaining minions will return upon completion. To '
                       'look up the return data for this job later run:\n'
                       'salt-run jobs.lookup_jid {0}').format(pub_data['jid'])
                raise SystemExit(msg)

    def cmd_iter(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            expr_form='glob',
            ret='',
            kwarg=None,
            **kwargs):
        '''
        Yields the individual minion returns as they come in

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :return: A generator

        .. code-block:: python

            >>> ret = local.cmd_iter('*', 'test.ping')
            >>> for i in ret:
            ...     print i
            {'jerry': {'ret': True}}
            {'dave': {'ret': True}}
            {'stewart': {'ret': True}}
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)
        pub_data = self.run_job(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            timeout,
            **kwargs)

        if not pub_data:
            yield pub_data
        else:
            for fn_ret in self.get_iter_returns(pub_data['jid'],
                                                pub_data['minions'],
                                                self._get_timeout(timeout),
                                                tgt,
                                                expr_form,
                                                **kwargs):
                if not fn_ret:
                    continue
                yield fn_ret

    def cmd_iter_no_block(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            expr_form='glob',
            ret='',
            kwarg=None,
            **kwargs):
        '''
        Blocks while waiting for individual minions to return.

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :returns: None until the next minion returns. This allows for actions
            to be injected in between minion returns.

        .. code-block:: python

            >>> ret = local.cmd_iter('*', 'test.ping')
            >>> for i in ret:
            ...     print i
            None
            {'jerry': {'ret': True}}
            {'dave': {'ret': True}}
            None
            {'stewart': {'ret': True}}
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)
        pub_data = self.run_job(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            timeout,
            **kwargs)

        if not pub_data:
            yield pub_data
        else:
            for fn_ret in self.get_iter_returns(pub_data['jid'],
                                                pub_data['minions'],
                                                timeout,
                                                tgt,
                                                expr_form,
                                                **kwargs):
                yield fn_ret

    def cmd_full_return(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            expr_form='glob',
            ret='',
            verbose=False,
            kwarg=None,
            **kwargs):
        '''
        Execute a salt command and return
        '''
        arg = salt.utils.args.condition_input(arg, kwarg)
        pub_data = self.run_job(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            timeout,
            **kwargs)

        if not pub_data:
            return pub_data

        return (self.get_cli_static_event_returns(pub_data['jid'],
                                                  pub_data['minions'],
                                                  timeout,
                                                  tgt,
                                                  expr_form,
                                                  verbose))

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
            found.update(set(ret.keys()))
            yield ret

        # if you have all the returns, stop
        if len(found.intersection(minions)) >= len(minions):
            raise StopIteration()

        # otherwise, get them from the event system
        for event in event_iter:
            if event != {}:
                found.update(set(event.keys()))
                yield event
            if len(found.intersection(minions)) >= len(minions):
                raise StopIteration()

    def get_iter_returns(
            self,
            jid,
            minions,
            timeout=None,
            tgt='*',
            tgt_type='glob',
            expect_minions=False,
            **kwargs):
        '''
        Watch the event system and return job data as it comes in

        :returns: all of the information for the JID
        '''
        if not isinstance(minions, set):
            if isinstance(minions, string_types):
                minions = set([minions])
            elif isinstance(minions, (list, tuple)):
                minions = set(list(minions))

        if timeout is None:
            timeout = self.opts['timeout']
        start = int(time.time())
        timeout_at = start + timeout
        found = set()
        # Check to see if the jid is real, if not return the empty dict
        if not self.returners['{0}.get_load'.format(self.opts['master_job_cache'])](jid) != {}:
            log.warning('jid does not exist')
            yield {}
            # stop the iteration, since the jid is invalid
            raise StopIteration()
        # Wait for the hosts to check in
        syndic_wait = 0
        last_time = False
        log.debug(
            'get_iter_returns for jid {0} sent to {1} will timeout at {2}'.format(
                jid, minions, datetime.fromtimestamp(timeout_at).time()
            )
        )
        while True:
            # Process events until timeout is reached or all minions have returned
            time_left = timeout_at - int(time.time())
            # Wait 0 == forever, use a minimum of 1s
            wait = max(1, time_left)
            raw = None
            # Look for events if we haven't yet found all the minions or if we are still waiting for
            # the syndics to report on how many minions they have forwarded the command to
            if (len(found.intersection(minions)) < len(minions) or
                    (self.opts['order_masters'] and syndic_wait < self.opts.get('syndic_wait', 1))):
                raw = self.event.get_event(wait, jid)
            if raw is not None:
                if 'minions' in raw.get('data', {}):
                    minions.update(raw['data']['minions'])
                    continue
                if 'syndic' in raw:
                    minions.update(raw['syndic'])
                    continue
                if 'return' not in raw:
                    continue
                if kwargs.get('raw', False):
                    found.add(raw['id'])
                    yield raw
                else:
                    found.add(raw['id'])
                    ret = {raw['id']: {'ret': raw['return']}}
                    if 'out' in raw:
                        ret[raw['id']]['out'] = raw['out']
                    log.debug('jid {0} return from {1}'.format(jid, raw['id']))
                    yield ret
                if len(found.intersection(minions)) >= len(minions):
                    # All minions have returned, break out of the loop
                    log.debug('jid {0} found all minions {1}'.format(jid, found))
                    if self.opts['order_masters']:
                        if syndic_wait < self.opts.get('syndic_wait', 1):
                            syndic_wait += 1
                            timeout_at = int(time.time()) + 1
                            log.debug('jid {0} syndic_wait {1} will now timeout at {2}'.format(
                                      jid, syndic_wait, datetime.fromtimestamp(timeout_at).time()))
                            continue
                    break
                continue
            # Then event system timeout was reached and nothing was returned
            if len(found.intersection(minions)) >= len(minions):
                # All minions have returned, break out of the loop
                log.debug('jid {0} found all minions {1}'.format(jid, found))
                if self.opts['order_masters']:
                    if syndic_wait < self.opts.get('syndic_wait', 1):
                        syndic_wait += 1
                        timeout_at = int(time.time()) + 1
                        log.debug(
                            'jid {0} syndic_wait {1} will now timeout at {2}'.format(
                                jid, syndic_wait, datetime.fromtimestamp(timeout_at).time()
                            )
                        )
                        continue
                break
            if last_time:
                if len(found) < len(minions):
                    log.info(
                        'jid {0} minions {1} did not return in time'.format(
                            jid, (minions - found)
                        )
                    )
                if expect_minions:
                    for minion in list((minions - found)):
                        yield {minion: {'failed': True}}
                break
            if int(time.time()) > timeout_at:
                # The timeout has been reached, check the jid to see if the
                # timeout needs to be increased
                jinfo = self.gather_job_info(jid, tgt, tgt_type, minions - found, **kwargs)
                still_running = [id_ for id_, jdat in jinfo.iteritems()
                                 if jdat
                                 ]
                if still_running:
                    timeout_at = int(time.time()) + timeout
                    log.debug(
                        'jid {0} still running on {1} will now timeout at {2}'.format(
                            jid, still_running, datetime.fromtimestamp(timeout_at).time()
                        )
                    )
                    continue
                else:
                    last_time = True
                    log.debug('jid {0} not running on any minions last time'.format(jid))
                    continue
            time.sleep(0.01)

    def get_returns(
            self,
            jid,
            minions,
            timeout=None,
            pending_tags=None):
        '''
        Get the returns for the command line interface via the event system
        '''
        minions = set(minions)
        if timeout is None:
            timeout = self.opts['timeout']
        start = int(time.time())
        timeout_at = start + timeout
        log.debug(
            'get_returns for jid {0} sent to {1} will timeout at {2}'.format(
                jid, minions, datetime.fromtimestamp(timeout_at).time()
            )
        )

        found = set()
        ret = {}
        # Check to see if the jid is real, if not return the empty dict
        if not self.returners['{0}.get_load'.format(self.opts['master_job_cache'])](jid) != {}:
            log.warning('jid does not exist')
            return ret

        # Wait for the hosts to check in
        while True:
            time_left = timeout_at - int(time.time())
            wait = max(1, time_left)
            raw = self.event.get_event(wait, jid)
            if raw is not None and 'return' in raw:
                found.add(raw['id'])
                ret[raw['id']] = raw['return']
                if len(found.intersection(minions)) >= len(minions):
                    # All minions have returned, break out of the loop
                    log.debug('jid {0} found all minions'.format(jid))
                    break
                continue
            # Then event system timeout was reached and nothing was returned
            if len(found.intersection(minions)) >= len(minions):
                # All minions have returned, break out of the loop
                log.debug('jid {0} found all minions'.format(jid))
                break
            if int(time.time()) > timeout_at:
                log.info(
                    'jid {0} minions {1} did not return in time'.format(
                        jid, (minions - found)
                    )
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

        data = self.returners['{0}.get_jid'.format(self.opts['master_job_cache'])](jid)
        for minion in data:
            m_data = {}
            if u'return' in data[minion]:
                m_data['ret'] = data[minion].get(u'return')
            else:
                m_data['ret'] = data[minion].get('return')
            if 'out' in data[minion]:
                m_data['out'] = data[minion]['out']
            if minion in ret:
                ret[minion].update(m_data)
            else:
                ret[minion] = m_data

        # if we have all the minion returns, lets just return
        if len(set(ret.keys()).intersection(minions)) >= len(minions):
            return ret

        # otherwise lets use the listener we created above to get the rest
        for event_ret in event_iter:
            # if nothing in the event_ret, skip
            if event_ret == {}:
                time.sleep(0.02)
                continue
            for minion, m_data in event_ret.iteritems():
                if minion in ret:
                    ret[minion].update(m_data)
                else:
                    ret[minion] = m_data

            # are we done yet?
            if len(set(ret.keys()).intersection(minions)) >= len(minions):
                return ret

        # otherwise we hit the timeout, return what we have
        return ret

    def get_cache_returns(self, jid):
        '''
        Execute a single pass to gather the contents of the job cache
        '''
        ret = {}

        data = self.returners['{0}.get_jid'.format(self.opts['master_job_cache'])](jid)
        for minion in data:
            m_data = {}
            if u'return' in data[minion]:
                m_data['ret'] = data[minion].get(u'return')
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
        if not self.returners['{0}.get_load'.format(self.opts['master_job_cache'])](jid) != {}:
            log.warning('jid does not exist')
            return ret
        # Wait for the hosts to check in
        while True:
            # Process events until timeout is reached or all minions have returned
            time_left = timeout_at - int(time.time())
            # Wait 0 == forever, use a minimum of 1s
            wait = max(1, time_left)
            raw = self.event.get_event(wait, jid)
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
        return ret

    def get_cli_event_returns(
            self,
            jid,
            minions,
            timeout=None,
            tgt='*',
            tgt_type='glob',
            verbose=False,
            show_timeout=False,
            show_jid=False,
            **kwargs):
        '''
        Get the returns for the command line interface via the event system
        '''
        log.trace('func get_cli_event_returns()')
        if not isinstance(minions, set):
            if isinstance(minions, string_types):
                minions = set([minions])
            elif isinstance(minions, (list, tuple)):
                minions = set(list(minions))

        if verbose:
            msg = 'Executing job with jid {0}'.format(jid)
            print(msg)
            print('-' * len(msg) + '\n')
        elif show_jid:
            print('jid: {0}'.format(jid))

        if timeout is None:
            timeout = self.opts['timeout']

        start = time.time()
        timeout_at = start + timeout
        found = set()
        # Check to see if the jid is real, if not return the empty dict
        if not self.returners['{0}.get_load'.format(self.opts['master_job_cache'])](jid) != {}:
            log.warning('jid does not exist')
            yield {}
            # stop the iteration, since the jid is invalid
            raise StopIteration()

        # Wait for the hosts to check in
        syndic_wait = 0
        last_time = False
        while True:
            # Process events until timeout is reached or all minions have returned
            time_left = timeout_at - time.time()
            # Wait 0 == forever, use a minimum of 1s
            wait = max(1, time_left)
            raw = self.event.get_event(wait, jid)
            log.trace('get_cli_event_returns() called self.event.get_event() and received: raw={0}'.format(raw))
            if raw is not None:
                if 'minions' in raw.get('data', {}):
                    minions.update(raw['data']['minions'])
                    continue
                if 'syndic' in raw:
                    minions.update(raw['syndic'])
                    continue
                if 'return' not in raw:
                    continue

                found.add(raw.get('id'))
                ret = {raw['id']: {'ret': raw['return']}}
                if 'out' in raw:
                    ret[raw['id']]['out'] = raw['out']
                if 'retcode' in raw:
                    ret[raw['id']]['retcode'] = raw['retcode']
                log.trace('raw = {0}'.format(raw))
                log.trace('ret = {0}'.format(ret))
                log.trace('yeilding \'ret\'')
                yield ret
                if len(found.intersection(minions)) >= len(minions):
                    # All minions have returned, break out of the loop
                    if self.opts['order_masters']:
                        if syndic_wait < self.opts.get('syndic_wait', 1):
                            syndic_wait += 1
                            timeout_at = time.time() + 1
                            continue
                    break
                continue
            # Then event system timeout was reached and nothing was returned
            if len(found.intersection(minions)) >= len(minions):
                # All minions have returned, break out of the loop
                if self.opts['order_masters']:
                    if syndic_wait < self.opts.get('syndic_wait', 1):
                        syndic_wait += 1
                        timeout_at = time.time() + 1
                        continue
                break
            if last_time:
                if verbose or show_timeout:
                    if self.opts.get('minion_data_cache', False) \
                            or tgt_type in ('glob', 'pcre', 'list'):
                        if len(found) < len(minions):
                            fail = sorted(list(minions.difference(found)))
                            # May incur heavy disk access
                            connected_minions = salt.utils.minions.CkMinions(self.opts).connected_ids()
                            for failed in fail:
                                if connected_minions and failed not in connected_minions:
                                    yield {failed: {'out': 'no_return',
                                                    'ret': 'Minion did not return. [Not connected]'}}
                                else:
                                    yield({
                                        failed: {
                                            'out': 'no_return',
                                            'ret': 'Minion did not return. [No response]'
                                        }
                                    })
                break
            if time.time() > timeout_at:
                # The timeout has been reached, check the jid to see if the
                # timeout needs to be increased
                jinfo = self.gather_job_info(jid, tgt, tgt_type, minions - found, **kwargs)
                more_time = False
                for id_ in jinfo:
                    if jinfo[id_]:
                        if verbose:
                            print(
                                'Execution is still running on {0}'.format(id_)
                            )
                        more_time = True
                if not more_time:
                    cache_jinfo = self.get_cache_returns(jid)
                    for id_ in cache_jinfo:
                        if id_ == tgt:
                            found.add(cache_jinfo.get('id'))
                            ret = {id_: {'ret': cache_jinfo[id_]['ret']}}
                            if 'out' in cache_jinfo[id_]:
                                ret[id_]['out'] = cache_jinfo[id_]['out']
                            if 'retcode' in cache_jinfo[id_]:
                                ret[id_]['retcode'] = cache_jinfo[id_]['retcode']
                            yield ret
                if more_time:
                    timeout_at = time.time() + timeout
                    continue
                else:
                    last_time = True
            time.sleep(0.01)

    def get_event_iter_returns(self, jid, minions, timeout=None):
        '''
        Gather the return data from the event system, break hard when timeout
        is reached.
        '''
        log.trace('entered - function get_event_iter_returns()')
        if timeout is None:
            timeout = self.opts['timeout']

        found = set()
        # Check to see if the jid is real, if not return the empty dict
        if not self.returners['{0}.get_load'.format(self.opts['master_job_cache'])](jid) != {}:
            log.warning('jid does not exist')
            yield {}
            # stop the iteration, since the jid is invalid
            raise StopIteration()
        # Wait for the hosts to check in
        while True:
            raw = self.event.get_event(timeout)
            if raw is None:
                # Timeout reached
                break
            if 'minions' in raw.get('data', {}):
                continue
            found.add(raw['id'])
            ret = {raw['id']: {'ret': raw['return']}}
            if 'out' in raw:
                ret[raw['id']]['out'] = raw['out']
            yield ret
            time.sleep(0.02)

    def _prep_pub(self,
                  tgt,
                  fun,
                  arg,
                  expr_form,
                  ret,
                  jid,
                  timeout,
                  **kwargs):
        '''
        Set up the payload_kwargs to be sent down to the master
        '''
        if expr_form == 'nodegroup':
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
            expr_form = 'compound'

        # Convert a range expression to a list of nodes and change expression
        # form to list
        if expr_form == 'range' and HAS_RANGE:
            tgt = self._convert_range_to_list(tgt)
            expr_form = 'list'

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
                          'tgt_type': expr_form,
                          'ret': ret,
                          'jid': jid}

        # if kwargs are passed, pack them.
        if kwargs:
            payload_kwargs['kwargs'] = kwargs

        # If we have a salt user, add it to the payload
        if self.salt_user:
            payload_kwargs['user'] = self.salt_user

        # If we're a syndication master, pass the timeout
        if self.opts['order_masters']:
            payload_kwargs['to'] = timeout

        return payload_kwargs

    def pub(self,
            tgt,
            fun,
            arg=(),
            expr_form='glob',
            ret='',
            jid='',
            timeout=5,
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
        if not os.path.exists(os.path.join(self.opts['sock_dir'],
                                           'publish_pull.ipc')):
            log.error(
                'Unable to connect to the publisher! '
                'You do not have permissions to access '
                '{0}'.format(self.opts['sock_dir'])
            )
            return {'jid': '0', 'minions': []}

        payload_kwargs = self._prep_pub(
                tgt,
                fun,
                arg,
                expr_form,
                ret,
                jid,
                timeout,
                **kwargs)

        master_uri = 'tcp://' + salt.utils.ip_bracket(self.opts['interface']) + \
                     ':' + str(self.opts['ret_port'])
        sreq = salt.transport.Channel.factory(self.opts, crypt='clear', master_uri=master_uri)

        try:
            payload = sreq.send(payload_kwargs)
        except SaltReqTimeoutError:
            log.error(
                'Salt request timed out. If this error persists, '
                'worker_threads may need to be increased.'
            )
            return {}

        if not payload:
            # The master key could have changed out from under us! Regen
            # and try again if the key has changed
            key = self.__read_master_key()
            if key == self.key:
                return payload
            self.key = key
            payload_kwargs['key'] = self.key
            payload = sreq.send(payload_kwargs)
            if not payload:
                return payload

        # We have the payload, let's get rid of SREQ fast(GC'ed faster)
        del sreq

        return {'jid': payload['load']['jid'],
                'minions': payload['load']['minions']}

    def __del__(self):
        # This IS really necessary!
        # When running tests, if self.events is not destroyed, we leak 2
        # threads per test case which uses self.client
        if hasattr(self, 'event'):
            # The call bellow will take care of calling 'self.event.destroy()'
            del self.event


class SSHClient(object):
    '''
    Create a client object for executing routines via the salt-ssh backend
    '''
    def __init__(self,
                 c_path=os.path.join(syspaths.CONFIG_DIR, 'master'),
                 mopts=None):
        if mopts:
            self.opts = mopts
        else:
            if os.path.isdir(c_path):
                log.warning(
                    '{0} expects a file path not a directory path({1}) to '
                    'it\'s \'c_path\' keyword argument'.format(
                        self.__class__.__name__, c_path
                    )
                )
            self.opts = salt.config.client_config(c_path)

    def _prep_ssh(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            expr_form='glob',
            kwarg=None,
            **kwargs):
        '''
        Prepare the arguments
        '''
        opts = copy.deepcopy(self.opts)
        opts.update(kwargs)
        if timeout:
            opts['timeout'] = timeout
        arg = salt.utils.args.condition_input(arg, kwarg)
        opts['argv'] = [fun] + arg
        opts['selected_target_option'] = expr_form
        opts['tgt'] = tgt
        opts['arg'] = arg
        return salt.client.ssh.SSH(opts)

    def cmd_iter(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            expr_form='glob',
            ret='',
            kwarg=None,
            **kwargs):
        '''
        Execute a single command via the salt-ssh subsystem and return a
        generator
        '''
        ssh = self._prep_ssh(
                tgt,
                fun,
                arg,
                timeout,
                expr_form,
                kwarg,
                **kwargs)
        for ret in ssh.run_iter():
            yield ret

    def cmd(
            self,
            tgt,
            fun,
            arg=(),
            timeout=None,
            expr_form='glob',
            kwarg=None,
            **kwargs):
        '''
        Execute a single command via the salt-ssh subsystem and return all
        routines at once
        '''
        ssh = self._prep_ssh(
                tgt,
                fun,
                arg,
                timeout,
                expr_form,
                kwarg,
                **kwargs)
        final = {}
        for ret in ssh.run_iter():
            final.update(ret)
        return final


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

    Importing and using ``Caller`` must be done on the same machine as a
    Salt Minion and it must be done using the same user that the Salt Minion is
    running as.

    Usage:

    .. code-block:: python

        import salt.client
        caller = salt.client.Caller()
        caller.function('test.ping')

        # Or call objects directly
        caller.sminion.functions['cmd.run']('ls -l')

    Note, a running master or minion daemon is not required to use this class.
    Running ``salt-call --local`` simply sets :conf_minion:`file_client` to
    ``'local'``. The same can be achieved at the Python level by including that
    setting in a minion config file.

    Instantiate a new Caller() instance using a file system path to the minion
    config file:

    .. code-block:: python

        caller = salt.client.Caller('/path/to/custom/minion_config')
        caller.sminion.functions['grains.items']()

    Instantiate a new Caller() instance using a dictionary of the minion
    config:

    .. versionadded:: 2014.7.0
        Pass the minion config as a dictionary.

    .. code-block:: python

        import salt.client
        import salt.config

        opts = salt.config.minion_config('/etc/salt/minion')
        opts['file_client'] = 'local'
        caller = salt.client.Caller(mopts=opts)
        caller.sminion.functions['grains.items']()

    '''
    def __init__(self, c_path=os.path.join(syspaths.CONFIG_DIR, 'minion'),
            mopts=None):
        if mopts:
            self.opts = mopts
        else:
            self.opts = salt.config.minion_config(c_path)
        self.sminion = salt.minion.SMinion(self.opts)

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
