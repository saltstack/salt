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

import os
import re
import sys
import glob
import time
import getpass

# Import zmq modules
import zmq

# Import salt modules
import salt.config
import salt.payload
import salt.utils
import salt.utils.verify
import salt.utils.event
from salt.exceptions import SaltClientError, SaltInvocationError

# Try to import range from https://github.com/ytoolshed/range
RANGE = False
try:
    import seco.range
    RANGE = True
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
    def __init__(self, c_path='/etc/salt/master'):
        self.opts = salt.config.master_config(c_path)
        self.serial = salt.payload.Serial(self.opts)
        self.key = self.__read_master_key()
        self.salt_user = self.__get_user()
        self.event = salt.utils.event.MasterEvent(self.opts['sock_dir'])

    def __read_master_key(self):
        '''
        Read in the rotating master authentication key
        '''
        keyfile = os.path.join(self.opts['cachedir'], '.root_key')
        # Make sure all key parent directories are accessible
        user = self.opts.get('user', 'root')
        salt.utils.verify.check_parent_dirs(keyfile, user)

        try:
            with open(keyfile, 'r') as KEY:
                return KEY.read()
        except (OSError, IOError):
            # In theory, this should never get hit. Belt & suspenders baby!
            raise SaltClientError(('Problem reading the salt root key. Are'
                                   ' you root?'))

    def __get_user(self):
        '''
        Determine the current user running the salt command
        '''
        user = getpass.getuser()
        # if our user is root, look for other ways to figure out
        # who we are
        if user == 'root':
            env_vars = ['SUDO_USER', 'USER', 'USERNAME']
            for evar in env_vars:
                if evar in os.environ:
                    return os.environ[evar]
            return None
        # If the running user is just the specified user in the
        # conf file, don't pass the user as it's implied.
        elif user == self.opts['user']:
            return None
        return user

    def _check_glob_minions(self, expr):
        '''
        Return the minions found by looking via globs
        '''
        cwd = os.getcwd()
        try:
            os.chdir(os.path.join(self.opts['pki_dir'], 'minions'))
        except OSError:
            err = ('The Salt Master has not been set up on this system, '
                   'a salt-master needs to be running to use the salt command')
            sys.stderr.write(err)
            sys.exit(2)
        ret = set(glob.glob(expr))
        os.chdir(cwd)
        return ret

    def _check_list_minions(self, expr):
        '''
        Return the minions found by looking via a list
        '''
        ret = []
        for fn_ in os.listdir(os.path.join(self.opts['pki_dir'], 'minions')):
            if fn_ in expr:
                if fn_ not in ret:
                    ret.append(fn_)
        return ret

    def _check_pcre_minions(self, expr):
        '''
        Return the minions found by looking via regular expressions
        '''
        ret = set()
        cwd = os.getcwd()
        os.chdir(os.path.join(self.opts['pki_dir'], 'minions'))
        reg = re.compile(expr)
        for fn_ in os.listdir('.'):
            if reg.match(fn_):
                ret.add(fn_)
        os.chdir(cwd)
        return ret

    def _check_grain_minions(self, expr):
        '''
        Return the minions found by looking via a list
        '''
        return os.listdir(os.path.join(self.opts['pki_dir'], 'minions'))

    def _convert_range_to_list(self, tgt):
        range = seco.range.Range(self.opts['range_server'])
        try:
            return range.expand(tgt)
        except seco.range.RangeException as e:
            print(("Range server exception: {0}".format(e)))
            return []

    def gather_job_info(self, jid, tgt, tgt_type):
        '''
        Return the information about a given job
        '''
        return self.cmd(
                tgt,
                'saltutil.find_job',
                [jid],
                2,
                tgt_type)

    def cmd(
        self,
        tgt,
        fun,
        arg=(),
        timeout=None,
        expr_form='glob',
        ret='',
        kwarg=None):
        '''
        Execute a salt command and return.
        '''
        arg = condition_kwarg(arg, kwarg)
        if timeout is None:
            timeout = self.opts['timeout']
        jid = salt.utils.prep_jid(
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        pub_data = self.pub(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            jid=jid,
            timeout=timeout)
        if pub_data['jid'] == '0':
            # Failed to connect to the master and send the pub
            return {}
        elif not pub_data['jid']:
            return {}
        return self.get_returns(pub_data['jid'], pub_data['minions'], timeout)

    def cmd_cli(
        self,
        tgt,
        fun,
        arg=(),
        timeout=None,
        expr_form='glob',
        ret='',
        verbose=False,
        kwarg=None):
        '''
        Execute a salt command and return data conditioned for command line
        output
        '''
        arg = condition_kwarg(arg, kwarg)
        if timeout is None:
            timeout = self.opts['timeout']
        jid = salt.utils.prep_jid(
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        pub_data = self.pub(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            jid=jid,
            timeout=timeout)
        if pub_data['jid'] == '0':
            print('Failed to connect to the Master, is the Salt Master running?')
            yield {}
        elif not pub_data['jid']:
            print('No minions match the target')
            yield {}
        else:
            for fn_ret in self.get_cli_event_returns(pub_data['jid'],
                    pub_data['minions'],
                    timeout,
                    tgt,
                    expr_form,
                    verbose):
                if not fn_ret:
                    continue
                yield fn_ret

    def cmd_iter(
        self,
        tgt,
        fun,
        arg=(),
        timeout=None,
        expr_form='glob',
        ret='',
        kwarg=None):
        '''
        Execute a salt command and return an iterator to return data as it is
        received
        '''
        arg = condition_kwarg(arg, kwarg)
        if timeout is None:
            timeout = self.opts['timeout']
        jid = salt.utils.prep_jid(
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        pub_data = self.pub(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            jid=jid,
            timeout=timeout)
        if pub_data['jid'] == '0':
            # Failed to connect to the master and send the pub
            yield {}
        elif not pub_data['jid']:
            yield {}
        else:
            for fn_ret in self.get_iter_returns(pub_data['jid'],
                    pub_data['minions'],
                    timeout):
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
        kwarg=None):
        '''
        Execute a salt command and return
        '''
        arg = condition_kwarg(arg, kwarg)
        if timeout is None:
            timeout = self.opts['timeout']
        jid = salt.utils.prep_jid(
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        pub_data = self.pub(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            jid=jid,
            timeout=timeout)
        if pub_data['jid'] == '0':
            # Failed to connect to the master and send the pub
            yield {}
        elif not pub_data['jid']:
            yield {}
        else:
            for fn_ret in self.get_iter_returns(pub_data['jid'],
                    pub_data['minions'],
                    timeout):
                yield fn_ret

    def cmd_full_return(
        self,
        tgt,
        fun,
        arg=(),
        timeout=None,
        expr_form='glob',
        ret='',
        kwarg=None):
        '''
        Execute a salt command and return
        '''
        arg = condition_kwarg(arg, kwarg)
        if timeout is None:
            timeout = self.opts['timeout']
        jid = salt.utils.prep_jid(
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        pub_data = self.pub(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            jid=jid,
            timeout=timeout)
        if pub_data['jid'] == '0':
            # Failed to connect to the master and send the pub
            return {}
        elif not pub_data['jid']:
            return {}
        return (self.get_full_returns(pub_data['jid'],
                pub_data['minions'], timeout))

    def get_cli_returns(
            self,
            jid,
            minions,
            timeout=None,
            tgt='*',
            tgt_type='glob',
            verbose=False):
        '''
        This method starts off a watcher looking at the return data for
        a specified jid, it returns all of the information for the jid
        '''
        if verbose:
            print('Executing job with jid {0}'.format(jid))
            print('------------------------------------\n')
        if timeout is None:
            timeout = self.opts['timeout']
        fret = {}
        inc_timeout = timeout
        jid_dir = salt.utils.jid_dir(
                jid,
                self.opts['cachedir'],
                self.opts['hash_type']
                )
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
                            ret_data = self.serial.load(open(retp, 'r'))
                            if ret_data is None:
                                # Sometimes the ret data is read at the wrong
                                # time and returns None, do a quick re-read
                                if check:
                                    check = False
                                    continue
                            ret[fn_] = {'ret': ret_data}
                            if os.path.isfile(outp):
                                ret[fn_]['out'] = self.serial.load(open(outp, 'r'))
                        except Exception:
                            pass
                    found.add(fn_)
                    fret.update(ret)
                    yield ret
            if glob.glob(wtag) and not int(time.time()) > start + timeout + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if len(fret) >= len(minions):
                # All minions have returned, break out of the loop
                break
            if int(time.time()) > start + timeout:
                # The timeout has been reached, check the jid to see if the
                # timeout needs to be increased
                jinfo = self.gather_job_info(jid, tgt, tgt_type)
                more_time = False
                for id_ in jinfo:
                    if jinfo[id_]:
                        if verbose:
                            print('Execution is still running on {0}'.format(id_))
                        more_time = True
                if more_time:
                    timeout += inc_timeout
                    continue
                if verbose:
                    if tgt_type == 'glob' or tgt_type == 'pcre':
                        if not len(fret) >= len(minions):
                            print('\nThe following minions did not return:')
                            fail = sorted(list(minions.difference(found)))
                            for minion in fail:
                                print(minion)
                break
            time.sleep(0.01)

    def get_iter_returns(self, jid, minions, timeout=None):
        '''
        This method starts off a watcher looking at the return data for
        a specified jid, it returns all of the information for the jid
        '''
        if timeout is None:
            timeout = self.opts['timeout']
        jid_dir = salt.utils.jid_dir(
                jid,
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        start = 999999999999
        gstart = int(time.time())
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
                            ret_data = self.serial.load(open(retp, 'r'))
                            ret[fn_] = {'ret': ret_data}
                            if os.path.isfile(outp):
                                ret[fn_]['out'] = self.serial.load(open(outp, 'r'))
                        except Exception:
                            pass
                    found.add(fn_)
                    yield ret
            if ret and start == 999999999999:
                start = int(time.time())
            if glob.glob(wtag) and not int(time.time()) > start + timeout + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if len(ret) >= len(minions):
                break
            if int(time.time()) > start + timeout:
                break
            if int(time.time()) > gstart + timeout and not ret:
                # No minions have replied within the specified global timeout,
                # return an empty dict
                break
            yield None
            time.sleep(0.02)

    def get_returns(self, jid, minions, timeout=None):
        '''
        This method starts off a watcher looking at the return data for
        a specified jid
        '''
        if timeout is None:
            timeout = self.opts['timeout']
        jid_dir = salt.utils.jid_dir(
                jid,
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        start = 999999999999
        gstart = int(time.time())
        ret = {}
        wtag = os.path.join(jid_dir, 'wtag*')
        # If jid == 0, there is no payload
        if int(jid) == 0:
            return ret
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
                    if not os.path.isfile(retp):
                        continue
                    while fn_ not in ret:
                        try:
                            ret[fn_] = self.serial.load(open(retp, 'r'))
                        except Exception:
                            pass
            if ret and start == 999999999999:
                start = int(time.time())
            if glob.glob(wtag) and not int(time.time()) > start + timeout + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if len(ret) >= len(minions):
                # All Minions have returned
                return ret
            if int(time.time()) > start + timeout:
                # The timeout has been reached
                return ret
            if int(time.time()) > gstart + timeout and not ret:
                # No minions have replied within the specified global timeout,
                # return an empty dict
                return ret
            time.sleep(0.02)

    def get_full_returns(self, jid, minions, timeout=None):
        '''
        This method starts off a watcher looking at the return data for
        a specified jid, it returns all of the information for the jid
        '''
        if timeout is None:
            timeout = self.opts['timeout']
        jid_dir = salt.utils.jid_dir(
                jid,
                self.opts['cachedir'],
                self.opts['hash_type']
                )
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
                            ret_data = self.serial.load(open(retp, 'r'))
                            ret[fn_] = {'ret': ret_data}
                            if os.path.isfile(outp):
                                ret[fn_]['out'] = self.serial.load(open(outp, 'r'))
                        except Exception:
                            pass
            if ret and start == 999999999999:
                start = int(time.time())
            if glob.glob(wtag) and not int(time.time()) > start + timeout + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if len(ret) >= len(minions):
                return ret
            if int(time.time()) > start + timeout:
                return ret
            if int(time.time()) > gstart + timeout and not ret:
                # No minions have replied within the specified global timeout,
                # return an empty dict
                return ret
            time.sleep(0.02)

    def get_cli_event_returns(
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
        if verbose:
            print('Executing job with jid {0}'.format(jid))
            print('------------------------------------\n')
        if timeout is None:
            timeout = self.opts['timeout']
        inc_timeout = timeout
        jid_dir = salt.utils.jid_dir(
                jid,
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        start = int(time.time())
        found = set()
        wtag = os.path.join(jid_dir, 'wtag*')
        # Check to see if the jid is real, if not return the empty dict
        if not os.path.isdir(jid_dir):
            yield {}
        # Wait for the hosts to check in
        while True:
            raw = self.event.get_event(timeout, jid)
            if not raw is None:
                found.add(raw['id'])
                ret = {raw['id']: {'ret': raw['return']}}
                if 'out' in raw:
                    ret[raw['id']]['out'] = raw['out']
                yield ret
                continue
            # Then event system timeout was reached and nothing was returned
            if len(found) >= len(minions):
                # All minions have returned, break out of the loop
                break
            if glob.glob(wtag) and not int(time.time()) > start + timeout + 1:
                # The timeout +1 has not been reached and there is still a
                # write tag for the syndic
                continue
            if int(time.time()) > start + timeout:
                # The timeout has been reached, check the jid to see if the
                # timeout needs to be increased
                jinfo = self.gather_job_info(jid, tgt, tgt_type)
                more_time = False
                for id_ in jinfo:
                    if jinfo[id_]:
                        if verbose:
                            print('Execution is still running on {0}'.format(id_))
                        more_time = True
                if more_time:
                    timeout += inc_timeout
                    continue
                if verbose:
                    if tgt_type == 'glob' or tgt_type == 'pcre':
                        if not len(found) >= len(minions):
                            print('\nThe following minions did not return:')
                            fail = sorted(list(minions.difference(found)))
                            for minion in fail:
                                print(minion)
                break
            time.sleep(0.01)

    def get_event_iter_returns(self, jid, minions, timeout=None):
        '''
        Gather the return data from the event system, break hard when timeout
        is reached.
        '''
        if timeout is None:
            timeout = self.opts['timeout']
        jid_dir = salt.utils.jid_dir(
                jid,
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        start = 999999999999
        gstart = int(time.time())
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
            found.add(raw['id'])
            ret = {raw['id']: {'ret': raw['return']}}
            if 'out' in raw:
                ret[raw['id']]['out'] = raw['out']
            yield ret
            time.sleep(0.02)


    def find_cmd(self, cmd):
        '''
        Hunt through the old salt calls for when cmd was run, return a dict:
        {'<jid>': <return_obj>}
        '''
        job_dir = os.path.join(self.opts['cachedir'], 'jobs')
        ret = {}
        for jid in os.listdir(job_dir):
            jid_dir = salt.utils.jid_dir(
                    jid,
                    self.opts['cachedir'],
                    self.opts['hash_type']
                    )
            loadp = os.path.join(jid_dir, '.load.p')
            if os.path.isfile(loadp):
                try:
                    load = self.serial.load(open(loadp, 'r'))
                    if load['fun'] == cmd:
                        # We found a match! Add the return values
                        ret[jid] = {}
                        for host in os.listdir(jid_dir):
                            host_dir = os.path.join(jid_dir, host)
                            retp = os.path.join(host_dir, 'return.p')
                            if not os.path.isfile(retp):
                                continue
                            ret[jid][host] = self.serial.load(open(retp))
                except Exception:
                    continue
            else:
                continue
        return ret

    def check_minions(self, expr, expr_form='glob'):
        '''
        Check the passed regex against the available minions' public keys
        stored for authentication. This should return a set of ids which
        match the regex, this will then be used to parse the returns to
        make sure everyone has checked back in.
        '''
        return {'glob': self._check_glob_minions,
                'pcre': self._check_pcre_minions,
                'list': self._check_list_minions,
                'grain': self._check_grain_minions,
                'grain_pcre': self._check_grain_minions,
                'exsel': self._check_grain_minions,
                'pillar': self._check_grain_minions,
                'compound': self._check_grain_minions,
                }[expr_form](expr)

    def pub(self, tgt, fun, arg=(), expr_form='glob',
            ret='', jid='', timeout=5):
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
        if not os.path.exists(
                os.path.join(
                    self.opts['sock_dir'],
                    'publish_pull.ipc'
                    )
                ):
            return {'jid': '0', 'minions': []}

        if expr_form == 'nodegroup':
            if tgt not in self.opts['nodegroups']:
                conf_file = self.opts.get('conf_file', 'the master config file')
                err = 'Node group {0} unavailable in {1}'.format(tgt, conf_file)
                raise SaltInvocationError(err)
            tgt = self.opts['nodegroups'][tgt]
            expr_form = 'compound'

        # Convert a range expression to a list of nodes and change expression
        # form to list
        if expr_form == 'range' and RANGE:
            tgt = self._convert_range_to_list(tgt)
            expr_form = 'list'

        # Run a check_minions, if no minions match return False
        # format the payload - make a function that does this in the payload
        #   module
        # make the zmq client
        # connect to the req server
        # send!
        # return what we get back
        minions = self.check_minions(tgt, expr_form)

        if self.opts['order_masters']:
            # If we're a master of masters, ignore the check_minion and
            # set the minions to the target.  This speeds up wait time
            # for lists and ranges and makes regex and other expression
            # forms possible
            minions = tgt
        elif not minions:
            return {'jid': None,
                    'minions': minions}

        # Generate the standard keyword args to feed to format_payload
        payload_kwargs = {'cmd': 'publish',
                           'tgt': tgt,
                           'fun': fun,
                           'arg': arg,
                           'key': self.key,
                           'tgt_type': expr_form,
                           'ret': ret,
                           'jid': jid}

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
        return {'jid': payload['load']['jid'],
                'minions': minions}


class FunctionWrapper(dict):
    '''
    Create a function wrapper that looks like the functions dict on the minion
    but invoked commands on the minion via a LocalClient.

    This allows SLS files to be loaded with an object that calls down to the
    minion when the salt functions dict is referenced.
    '''
    def __init__(self, opts, minion):
        self.opts = opts
        self.minion = minion
        self.local = LocalClient(self.opts['conf_file'])
        self.functions = self.__load_functions()

    def __missing__(self, key):
        '''
        Since the function key is missing, wrap this call to a command to the
        minion of said key if it is available in the self.functions set
        '''
        if not key in self.functions:
            raise KeyError
        return self.run_key(key)

    def __load_functions(self):
        '''
        Find out what functions are available on the minion
        '''
        return set(
                self.local.cmd(
                    self.minion,
                    'sys.list_functions'
                    ).get(self.minion, [])
                )

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
        args, kw = salt.minion.detect_kwargs(func, args, kwargs)
        return func(*args, **kw)
