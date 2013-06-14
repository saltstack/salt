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
import getpass

# Import salt libs
import salt.config
import salt.payload
import salt.utils
import salt.utils.verify
import salt.utils.event
import salt.utils.minions
from salt.exceptions import SaltInvocationError
from salt.exceptions import EauthAuthenticationError

# Try to import range from https://github.com/ytoolshed/range
HAS_RANGE = False
try:
    import seco.range
    HAS_RANGE = True
except ImportError:
    pass


def condition_kwarg(arg, kwarg):
    '''
    Return a single arg structure for the publisher to safely use
    '''
    if isinstance(kwarg, dict):
        kw_ = []
        for key, val in kwarg.items():
            kw_.append('{0}={1}'.format(key, val))
        return list(arg) + kw_
    return arg


class LocalClient(object):
    '''
    Connect to the salt master via the local server and via root
    '''
    def __init__(self, c_path='/etc/salt/master', mopts=None):
        if mopts:
            self.opts = mopts
        else:
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
            print("Range server exception: {0}".format(err))
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
            **kwargs):
        '''
        Prep the job dir and send minions the pub.
        Returns a dict of (checked) pub_data or an empty dict.
        '''
        jid = ''

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
        Execute a command and get back the jid, don't wait for anything
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
        Execute a command on a random subset of the targetted systems, pass
        in the subset via the sub option to signify the number of systems to
        execute on.
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
        Execute a batch command
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
        Execute a salt command and return.
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
        Execute a salt command and return data conditioned for command line
        output
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
        Execute a salt command and return an iterator to return data as it is
        received
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
            yield pub_data
        else:
            for fn_ret in self.get_iter_returns(pub_data['jid'],
                                                pub_data['minions'],
                                                timeout,
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
        This method starts off a watcher looking at the return data for
        a specified jid, it returns all of the information for the jid
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
                if verbose:
                    if tgt_type in ('glob', 'pcre', 'list'):
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
        '''
        if not isinstance(minions, set):
            if isinstance(minions, basestring):
                minions = set([minions])
            elif isinstance(minions, (list, tuple)):
                minions = set(list(minions))

        if timeout is None:
            timeout = self.opts['timeout']
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
        # Wait for the hosts to check in
        while True:
            raw = self.event.get_event(timeout, jid)
            if raw is not None:
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
                            time.sleep(1)
                            continue
                    break
                continue
            # Then event system timeout was reached and nothing was returned
            if len(found.intersection(minions)) >= len(minions):
                # All minions have returned, break out of the loop
                if self.opts['order_masters']:
                    if syndic_wait < self.opts.get('syndic_wait', 1):
                        syndic_wait += 1
                        time.sleep(1)
                        continue
                break
            if glob.glob(wtag) and int(time.time()) <= start + timeout + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if int(time.time()) > start + timeout:
                # The timeout has been reached, check the jid to see if the
                # timeout needs to be increased
                jinfo = self.gather_job_info(jid, tgt, tgt_type, **kwargs)
                more_time = False
                for id_ in jinfo:
                    if jinfo[id_]:
                        more_time = True
                if more_time:
                    timeout += inc_timeout
                    continue
                break
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
        found = set()
        ret = {}
        wtag = os.path.join(jid_dir, 'wtag*')
        # Check to see if the jid is real, if not return the empty dict
        if not os.path.isdir(jid_dir):
            return ret
        # Wait for the hosts to check in
        while True:
            raw = self.event.get_event(timeout, jid)
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
            if glob.glob(wtag) and int(time.time()) <= start + timeout + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if int(time.time()) > start + timeout:
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
        found = set()
        ret = {}
        wtag = os.path.join(jid_dir, 'wtag*')
        # Check to see if the jid is real, if not return the empty dict
        if not os.path.isdir(jid_dir):
            return ret
        # Wait for the hosts to check in
        while True:
            raw = self.event.get_event(timeout, jid)
            if raw is not None:
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
            if glob.glob(wtag) and int(time.time()) <= start + timeout + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if int(time.time()) > start + timeout:
                if verbose:
                    if tgt_type in ('glob', 'pcre', 'list'):
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
        # Wait for the hosts to check in
        syndic_wait = 0
        while True:
            raw = self.event.get_event(timeout, jid)
            if raw is not None:
                if 'minions' in raw.get('data', {}):
                    minions.update(raw['data']['minions'])
                    continue
                if 'syndic' in raw:
                    minions.update(raw['syndic'])
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
                            time.sleep(1)
                            continue
                    break
                continue
            # Then event system timeout was reached and nothing was returned
            if len(found.intersection(minions)) >= len(minions):
                # All minions have returned, break out of the loop
                if self.opts['order_masters']:
                    if syndic_wait < self.opts.get('syndic_wait', 1):
                        syndic_wait += 1
                        time.sleep(1)
                        continue
                break
            if glob.glob(wtag) and int(time.time()) <= start + timeout + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
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
                if verbose:
                    if tgt_type in ('glob', 'pcre', 'list'):
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

        sreq = salt.payload.SREQ(
            'tcp://{0[interface]}:{0[ret_port]}'.format(self.opts),
        )
        payload = sreq.send('clear', payload_kwargs)

        if not payload:
            # The master key could have changed out from under us! Regen
            # and try again if the key has changed
            key = self.__read_master_key()
            if key == self.key:
                return payload
            self.key = key
            payload_kwargs['key'] = self.key
            payload = sreq.send('clear', payload_kwargs)
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
    Create an object used to call salt functions directly on a minion
    '''
    def __init__(self, c_path='/etc/salt/minion'):
        self.opts = salt.config.minion_config(c_path)
        self.sminion = salt.minion.SMinion(self.opts)

    def function(self, fun, *args, **kwargs):
        '''
        Call a single salt function
        '''
        func = self.sminion.functions[fun]
        args, kwargs = salt.minion.parse_args_and_kwargs(func, args, kwargs)
        return func(*args, **kwargs)
