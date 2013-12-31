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
# Next there are a number of tasks, first we need some kind of authentication
# This Client initially will be the master root client, which will run as
# the root user on the master server.
#
# BUT we also want a client to be able to work over the network, so that
# controllers can exist within disparate applications.
#
# The problem is that this is a security nightmare, so I am going to start
# small, and only start with the ability to execute salt commands locally.
# This means that the primary client to build is, the LocalClient

# Import python libs
import os
import glob
import time
import copy
import getpass
import logging

# Import salt libs
import salt.config
import salt.payload
import salt.transport
import salt.utils
import salt.utils.verify
import salt.utils.event
import salt.utils.minions
import salt.syspaths as syspaths
from salt.exceptions import SaltInvocationError
from salt.exceptions import EauthAuthenticationError

# Try to import range from https://github.com/ytoolshed/range
HAS_RANGE = False
try:
    import seco.range
    HAS_RANGE = True
except ImportError:
    pass

log = logging.getLogger(__name__)


def condition_kwarg(arg, kwarg):
    '''
    Return a single arg structure for the publisher to safely use
    '''
    if isinstance(kwarg, dict):
        kw_ = {'__kwarg__': True}
        for key, val in kwarg.items():
            kw_[key] = val
        return list(arg) + [kw_]
    return arg


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
        self.serial = salt.payload.Serial(self.opts)
        self.salt_user = self.__get_user()
        self.key = self.__read_master_key()
        self.event = salt.utils.event.LocalClientEvent(self.opts['sock_dir'])

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
        salt.utils.verify.check_path_traversal(self.opts['cachedir'], key_user)

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
        user = getpass.getuser()
        # if our user is root, look for other ways to figure out
        # who we are
        if (user == 'root' or user == self.opts['user']) and 'SUDO_USER' in os.environ:
            env_vars = ['SUDO_USER']
            for evar in env_vars:
                if evar in os.environ:
                    return 'sudo_{0}'.format(os.environ[evar])
            return user
        # If the running user is just the specified user in the
        # conf file, don't pass the user as it's implied.
        elif user == self.opts['user']:
            return user
        return user

    def _convert_range_to_list(self, tgt):
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
        if isinstance(timeout, str):
            try:
                return int(timeout)
            except ValueError:
                return self.opts['timeout']
        # Looks like the timeout is invalid, use config
        return self.opts['timeout']

    def gather_job_info(self, jid, tgt, tgt_type, **kwargs):
        '''
        Return the information about a given job
        '''
        jinfo = self.cmd(tgt,
                         'saltutil.find_job',
                         [jid],
                         2,
                         tgt_type,
                         **kwargs)
        return jinfo

    def _check_pub_data(self, pub_data):
        '''
        Common checks on the pub_data data structure returned from running pub
        '''
        if not pub_data:
            raise EauthAuthenticationError(
                'Failed to authenticate, is this user permitted to execute '
                'commands?'
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
        Asyncronously send a command to connected minions

        Prep the job directory and publish a command to any targeted minions.

        :return: A dictionary of (validated) ``pub_data`` or an empty
            dictionary on failure. The ``pub_data`` contains the job ID and a
            list of all minions that are expected to return data.

        .. code-block:: python

            >>> local.run_job('*', 'test.sleep', [300])
            {'jid': '20131219215650131543', 'minions': ['jerry']}
        '''
        arg = condition_kwarg(arg, kwarg)
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
        Asyncronously send a command to connected minions

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :returns: A job ID or 0 on failure.

        .. code-block:: python

            >>> local.cmd_async('*', 'test.sleep', [300])
            '20131219215921857715'
        '''
        arg = condition_kwarg(arg, kwarg)
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
        arg = condition_kwarg(arg, kwarg)
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
        batch = salt.cli.batch.Batch(opts, True)
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
        Syncronously execute a command on targeted minions

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

            * ``eauth`` - the external_auth backend
            * ``username`` and ``password``
            * ``token``

            .. code-block:: python

                >>> local.cmd('*', 'test.ping',
                        username='saltdev', password='saltdev', eauth='pam')

        :returns: A dictionary with the result of the execution, keyed by
            minion ID. A compound command will return a sub-dictionary keyed by
            function name.
        '''
        arg = condition_kwarg(arg, kwarg)
        pub_data = self.run_job(tgt,
                                fun,
                                arg,
                                expr_form,
                                ret,
                                timeout,
                                **kwargs)

        if not pub_data:
            return pub_data

        return self.get_returns(pub_data['jid'],
                                pub_data['minions'],
                                self._get_timeout(timeout))

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
        arg = condition_kwarg(arg, kwarg)
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
        arg = condition_kwarg(arg, kwarg)
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
        arg = condition_kwarg(arg, kwarg)
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
        arg = condition_kwarg(arg, kwarg)
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
            **kwargs):
        '''
        Starts a watcher looking at the return data for a specified JID

        :returns: all of the information for the JID
        '''
        if verbose:
            msg = 'Executing job with jid {0}'.format(jid)
            print(msg)
            print('-' * len(msg) + '\n')
        if timeout is None:
            timeout = self.opts['timeout']
        fret = {}
        inc_timeout = timeout
        jid_dir = salt.utils.jid_dir(jid,
                                     self.opts['cachedir'],
                                     self.opts['hash_type'])
        start = int(time.time())
        found = set()
        wtag = os.path.join(jid_dir, 'wtag*')
        # Check to see if the jid is real, if not return the empty dict
        if not os.path.isdir(jid_dir):
            yield {}
        last_time = False
        # Wait for the hosts to check in
        while True:
            for fn_ in os.listdir(jid_dir):
                ret = {}
                if fn_.startswith('.'):
                    continue
                if fn_ not in found:
                    retp = os.path.join(jid_dir, fn_, 'return.p')
                    outp = os.path.join(jid_dir, fn_, 'out.p')
                    if not os.path.isfile(retp):
                        continue
                    while fn_ not in ret:
                        try:
                            check = True
                            ret_data = self.serial.load(
                                salt.utils.fopen(retp, 'r')
                            )
                            if ret_data is None:
                                # Sometimes the ret data is read at the wrong
                                # time and returns None, do a quick re-read
                                if check:
                                    continue
                            ret[fn_] = {'ret': ret_data}
                            if os.path.isfile(outp):
                                ret[fn_]['out'] = self.serial.load(
                                    salt.utils.fopen(outp, 'r')
                                )
                        except Exception:
                            pass
                    found.add(fn_)
                    fret.update(ret)
                    yield ret
            if glob.glob(wtag) and int(time.time()) <= start + timeout + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if len(found.intersection(minions)) >= len(minions):
                # All minions have returned, break out of the loop
                break
            if last_time:
                if verbose:
                    if self.opts.get('minion_data_cache', False) \
                            or tgt_type in ('glob', 'pcre', 'list'):
                        if len(found.intersection(minions)) >= len(minions):
                            fail = sorted(list(minions.difference(found)))
                            for minion in fail:
                                yield({
                                    minion: {
                                        'out': 'no_return',
                                        'ret': 'Minion did not return'
                                    }
                                })
                break
            if int(time.time()) > start + timeout:
                # The timeout has been reached, check the jid to see if the
                # timeout needs to be increased
                jinfo = self.gather_job_info(jid, tgt, tgt_type, **kwargs)
                more_time = False
                for id_ in jinfo:
                    if jinfo[id_]:
                        if verbose:
                            print(
                                'Execution is still running on {0}'.format(id_)
                            )
                        more_time = True
                if more_time:
                    timeout += inc_timeout
                    continue
                else:
                    last_time = True
                    continue
            time.sleep(0.01)

    def get_iter_returns(
            self,
            jid,
            minions,
            timeout=None,
            tgt='*',
            tgt_type='glob',
            **kwargs):
        '''
        Watch the event system and return job data as it comes in

        :returns: all of the information for the JID
        '''
        if not isinstance(minions, set):
            if isinstance(minions, basestring):
                minions = set([minions])
            elif isinstance(minions, (list, tuple)):
                minions = set(list(minions))

        if timeout is None:
            timeout = self.opts['timeout']
        jid_dir = salt.utils.jid_dir(jid,
                                     self.opts['cachedir'],
                                     self.opts['hash_type'])
        start = int(time.time())
        timeout_at = start + timeout
        found = set()
        wtag = os.path.join(jid_dir, 'wtag*')
        # Check to see if the jid is real, if not return the empty dict
        if not os.path.isdir(jid_dir):
            yield {}
        # Wait for the hosts to check in
        syndic_wait = 0
        last_time = False
        while True:
            # Process events until timeout is reached or all minions have returned
            time_left = timeout_at - int(time.time())
            # Wait 0 == forever, use a minimum of 1s
            wait = max(1, time_left)
            raw = self.event.get_event(wait, jid)
            if raw is not None and 'id' in raw:
                if 'minions' in raw.get('data', {}):
                    minions.update(raw['data']['minions'])
                    continue
                if 'syndic' in raw:
                    minions.update(raw['syndic'])
                    continue
                if kwargs.get('raw', False):
                    found.add(raw['id'])
                    yield raw
                else:
                    found.add(raw['id'])
                    ret = {raw['id']: {'ret': raw['return']}}
                    if 'out' in raw:
                        ret[raw['id']]['out'] = raw['out']
                    yield ret
                if len(found.intersection(minions)) >= len(minions):
                    # All minions have returned, break out of the loop
                    if self.opts['order_masters']:
                        if syndic_wait < self.opts.get('syndic_wait', 1):
                            syndic_wait += 1
                            timeout_at = int(time.time()) + 1
                            continue
                    break
                continue
            # Then event system timeout was reached and nothing was returned
            if len(found.intersection(minions)) >= len(minions):
                # All minions have returned, break out of the loop
                if self.opts['order_masters']:
                    if syndic_wait < self.opts.get('syndic_wait', 1):
                        syndic_wait += 1
                        timeout_at = int(time.time()) + 1
                        continue
                break
            if glob.glob(wtag) and int(time.time()) <= timeout_at + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if last_time:
                break
            if int(time.time()) > timeout_at:
                # The timeout has been reached, check the jid to see if the
                # timeout needs to be increased
                jinfo = self.gather_job_info(jid, tgt, tgt_type, **kwargs)
                more_time = False
                for id_ in jinfo:
                    if jinfo[id_]:
                        more_time = True
                if more_time:
                    timeout_at = int(time.time()) + timeout
                    continue
                else:
                    last_time = True
                    continue
            time.sleep(0.01)

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
        jid_dir = salt.utils.jid_dir(jid,
                                     self.opts['cachedir'],
                                     self.opts['hash_type'])
        start = int(time.time())
        timeout_at = start + timeout
        found = set()
        ret = {}
        wtag = os.path.join(jid_dir, 'wtag*')
        # Check to see if the jid is real, if not return the empty dict
        if not os.path.isdir(jid_dir):
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
                    break
                continue
            # Then event system timeout was reached and nothing was returned
            if len(found.intersection(minions)) >= len(minions):
                # All minions have returned, break out of the loop
                break
            if glob.glob(wtag) and int(time.time()) <= timeout_at + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if int(time.time()) > timeout_at:
                break
            time.sleep(0.01)
        return ret

    def get_full_returns(self, jid, minions, timeout=None):
        '''
        This method starts off a watcher looking at the return data for
        a specified jid, it returns all of the information for the jid
        '''
        if timeout is None:
            timeout = self.opts['timeout']
        jid_dir = salt.utils.jid_dir(jid,
                                     self.opts['cachedir'],
                                     self.opts['hash_type'])
        start = 999999999999
        gstart = int(time.time())
        ret = {}
        wtag = os.path.join(jid_dir, 'wtag*')
        # Check to see if the jid is real, if not return the empty dict
        if not os.path.isdir(jid_dir):
            return ret
        # Wait for the hosts to check in
        while True:
            for fn_ in os.listdir(jid_dir):
                if fn_.startswith('.'):
                    continue
                if fn_ not in ret:
                    retp = os.path.join(jid_dir, fn_, 'return.p')
                    outp = os.path.join(jid_dir, fn_, 'out.p')
                    if not os.path.isfile(retp):
                        continue
                    while fn_ not in ret:
                        try:
                            ret_data = self.serial.load(
                                salt.utils.fopen(retp, 'r'))
                            ret[fn_] = {'ret': ret_data}
                            if os.path.isfile(outp):
                                ret[fn_]['out'] = self.serial.load(
                                    salt.utils.fopen(outp, 'r'))
                        except Exception:
                            pass
            if ret and start == 999999999999:
                start = int(time.time())
            if glob.glob(wtag) and int(time.time()) <= start + timeout + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if len(set(ret.keys()).intersection(minions)) >= len(minions):
                return ret
            if int(time.time()) > start + timeout:
                return ret
            if int(time.time()) > gstart + timeout and not ret:
                # No minions have replied within the specified global timeout,
                # return an empty dict
                return ret
            time.sleep(0.02)

    def get_cache_returns(self, jid):
        '''
        Execute a single pass to gather the contents of the job cache
        '''
        ret = {}
        jid_dir = salt.utils.jid_dir(jid,
                                     self.opts['cachedir'],
                                     self.opts['hash_type'])
        for fn_ in os.listdir(jid_dir):
            if fn_.startswith('.'):
                continue
            if fn_ not in ret:
                retp = os.path.join(jid_dir, fn_, 'return.p')
                outp = os.path.join(jid_dir, fn_, 'out.p')
                if not os.path.isfile(retp):
                    continue
                while fn_ not in ret:
                    try:
                        ret_data = self.serial.load(
                            salt.utils.fopen(retp, 'r'))
                        ret[fn_] = {'ret': ret_data}
                        if os.path.isfile(outp):
                            ret[fn_]['out'] = self.serial.load(
                                salt.utils.fopen(outp, 'r'))
                    except Exception:
                        pass
        return ret

    def get_cli_static_event_returns(
            self,
            jid,
            minions,
            timeout=None,
            tgt='*',
            tgt_type='glob',
            verbose=False):
        '''
        Get the returns for the command line interface via the event system
        '''
        minions = set(minions)
        if verbose:
            msg = 'Executing job with jid {0}'.format(jid)
            print(msg)
            print('-' * len(msg) + '\n')
        if timeout is None:
            timeout = self.opts['timeout']
        jid_dir = salt.utils.jid_dir(jid,
                                     self.opts['cachedir'],
                                     self.opts['hash_type'])
        start = int(time.time())
        timeout_at = start + timeout
        found = set()
        ret = {}
        wtag = os.path.join(jid_dir, 'wtag*')
        # Check to see if the jid is real, if not return the empty dict
        if not os.path.isdir(jid_dir):
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
            if glob.glob(wtag) and int(time.time()) <= timeout_at + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if int(time.time()) > timeout_at:
                if verbose:
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
            **kwargs):
        '''
        Get the returns for the command line interface via the event system
        '''
        if not isinstance(minions, set):
            if isinstance(minions, basestring):
                minions = set([minions])
            elif isinstance(minions, (list, tuple)):
                minions = set(list(minions))

        if verbose:
            msg = 'Executing job with jid {0}'.format(jid)
            print(msg)
            print('-' * len(msg) + '\n')
        if timeout is None:
            timeout = self.opts['timeout']
        jid_dir = salt.utils.jid_dir(jid,
                                     self.opts['cachedir'],
                                     self.opts['hash_type'])
        start = int(time.time())
        timeout_at = start + timeout
        found = set()
        wtag = os.path.join(jid_dir, 'wtag*')
        # Check to see if the jid is real, if not return the empty dict
        if not os.path.isdir(jid_dir):
            yield {}
        # Wait for the hosts to check in
        syndic_wait = 0
        last_time = False
        while True:
            # Process events until timeout is reached or all minions have returned
            time_left = timeout_at - int(time.time())
            # Wait 0 == forever, use a minimum of 1s
            wait = max(1, time_left)
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
                found.add(raw.get('id'))
                ret = {raw['id']: {'ret': raw['return']}}
                if 'out' in raw:
                    ret[raw['id']]['out'] = raw['out']
                yield ret
                if len(found.intersection(minions)) >= len(minions):
                    # All minions have returned, break out of the loop
                    if self.opts['order_masters']:
                        if syndic_wait < self.opts.get('syndic_wait', 1):
                            syndic_wait += 1
                            timeout_at = int(time.time()) + 1
                            continue
                    break
                continue
            # Then event system timeout was reached and nothing was returned
            if len(found.intersection(minions)) >= len(minions):
                # All minions have returned, break out of the loop
                if self.opts['order_masters']:
                    if syndic_wait < self.opts.get('syndic_wait', 1):
                        syndic_wait += 1
                        timeout_at = int(time.time()) + 1
                        continue
                break
            if glob.glob(wtag) and int(time.time()) <= timeout_at + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if last_time:
                if verbose or show_timeout:
                    if self.opts.get('minion_data_cache', False) \
                            or tgt_type in ('glob', 'pcre', 'list'):
                        if len(found) < len(minions):
                            fail = sorted(list(minions.difference(found)))
                            for minion in fail:
                                yield({
                                    minion: {
                                        'out': 'no_return',
                                        'ret': 'Minion did not return'
                                    }
                                })
                break
            if int(time.time()) > timeout_at:
                # The timeout has been reached, check the jid to see if the
                # timeout needs to be increased
                jinfo = self.gather_job_info(jid, tgt, tgt_type, **kwargs)
                more_time = False
                for id_ in jinfo:
                    if jinfo[id_]:
                        if verbose:
                            print(
                                'Execution is still running on {0}'.format(id_)
                            )
                        more_time = True
                if more_time:
                    timeout_at = int(time.time()) + timeout
                    continue
                else:
                    last_time = True
            time.sleep(0.01)

    def get_event_iter_returns(self, jid, minions, timeout=None):
        '''
        Gather the return data from the event system, break hard when timeout
        is reached.
        '''
        if timeout is None:
            timeout = self.opts['timeout']
        jid_dir = salt.utils.jid_dir(jid,
                                     self.opts['cachedir'],
                                     self.opts['hash_type'])
        found = set()
        # Check to see if the jid is real, if not return the empty dict
        if not os.path.isdir(jid_dir):
            yield {}
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
            return {'jid': '0', 'minions': []}

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
        # make the zmq client
        # connect to the req server
        # send!
        # return what we get back

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

        # sreq = salt.payload.SREQ(
        #     #'tcp://{0[interface]}:{0[ret_port]}'.format(self.opts),
        #     'tcp://' + salt.utils.ip_bracket(self.opts['interface']) +
        #     ':' + str(self.opts['ret_port']),
        # )
        master_uri = 'tcp://' + salt.utils.ip_bracket(self.opts['interface']) + \
                     ':' + str(self.opts['ret_port'])
        sreq = salt.transport.Channel.factory(self.opts, crypt='clear', master_uri=master_uri)
        payload = sreq.send(payload_kwargs)

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
        opts['timeout'] = timeout
        arg = condition_kwarg(arg, kwarg)
        opts['arg_str'] = '{0} {1}'.format(fun, ' '.join(arg))
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
    '''
    def __init__(self, c_path=os.path.join(syspaths.CONFIG_DIR, 'minion')):
        self.opts = salt.config.minion_config(c_path)
        self.sminion = salt.minion.SMinion(self.opts)

    def function(self, fun, *args, **kwargs):
        '''
        Call a single salt function
        '''
        func = self.sminion.functions[fun]
        args, kwargs = salt.minion.parse_args_and_kwargs(func, args, kwargs)
        return func(*args, **kwargs)
