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
# The concerns are
# 1. Who executes the command?
# 2. what is the function being run?
# 3. What arguments need to be passed to the function?
# 4. How long do we wait for all of the replies?
#
# Next there are a number of tasks, first we need some kind of authentication
# This Client initially will be the master root client, which will run as the
# root user on the master server.
# BUT we also want a client to be able to work over the network, so that
# controllers can exist within disparate applications.
# The problem is that this is a security nightmare, so I am going to start
# small, and only start with the ability to execute salt commands locally.
# This means that the primary client to build is, the LocalClient

import os
import re
import sys
import glob
import time
import datetime

# Import zmq modules
import zmq

# Import salt modules
import salt.config
import salt.payload
from salt.exceptions import SaltClientError, SaltInvocationError


def prep_jid(cachedir):
    '''
    Parses the job return directory, generates a job id and sets up the
    job id directory.
    '''
    jid_root = os.path.join(cachedir, 'jobs')
    jid = datetime.datetime.strftime(
        datetime.datetime.now(), '%Y%m%d%H%M%S%f'
    )
    jid_dir = os.path.join(jid_root, jid)
    if not os.path.isdir(jid_dir):
        os.makedirs(jid_dir)
    else:
        return prep_jid(cachedir)
    return jid


class LocalClient(object):
    '''
    Connect to the salt master via the local server and via root
    '''
    def __init__(self, c_path='/etc/salt/master'):
        self.opts = salt.config.master_config(c_path)
        self.serial = salt.payload.Serial(self.opts)
        self.key = self.__read_master_key()

    def __read_master_key(self):
        '''
        Read in the rotating master authentication key
        '''
        try:
            keyfile = os.path.join(self.opts['cachedir'], '.root_key')
            key = open(keyfile, 'r').read()
            return key
        except (OSError, IOError):
            raise SaltClientError('Problem reading the salt root key. Are you root?')

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
            if expr.count(fn_):
                if not ret.count(fn_):
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

    def cmd(
        self,
        tgt,
        fun,
        arg=(),
        timeout=5,
        expr_form='glob',
        ret=''):
        '''
        Execute a salt command and return.
        '''
        jid = prep_jid(self.opts['cachedir'])
        pub_data = self.pub(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            jid=jid,
            timeout=timeout)
        return self.get_returns(pub_data['jid'], pub_data['minions'], timeout)

    def cmd_full_return(
        self,
        tgt,
        fun,
        arg=(),
        timeout=5,
        expr_form='glob',
        ret=''):
        '''
        Execute a salt command and return
        '''
        jid = prep_jid(self.opts['cachedir'])
        pub_data = self.pub(
            tgt,
            fun,
            arg,
            expr_form,
            ret,
            jid=jid,
            timeout=timeout)
        return (self.get_full_returns(pub_data['jid'],
                pub_data['minions'], timeout))

    def get_returns(self, jid, minions, timeout=5):
        '''
        This method starts off a watcher looking at the return data for a
        specified jid
        '''
        jid_dir = os.path.join(self.opts['cachedir'], 'jobs', jid)
        start = 999999999999
        gstart = int(time.time())
        ret = {}
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
                        except:
                            pass
            if ret and start == 999999999999:
                start = int(time.time())
            if len(ret) >= len(minions):
                return ret
            if int(time.time()) > start + timeout:
                return ret
            if int(time.time()) > gstart + timeout and not ret:
                # No minions have replied within the specified global timeout,
                # return an empty dict
                return ret
            time.sleep(0.02)

    def get_full_returns(self, jid, minions, timeout=5):
        '''
        This method starts off a watcher looking at the return data for a
        specified jid, it returns all of the information for the jid
        '''
        jid_dir = os.path.join(self.opts['cachedir'], 'jobs', jid)
        start = 999999999999
        gstart = int(time.time())
        ret = {}
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
                        except:
                            pass
            if ret and start == 999999999999:
                start = int(time.time())
            if len(ret) >= len(minions):
                return ret
            if int(time.time()) > start + timeout:
                return ret
            if int(time.time()) > gstart + timeout and not ret:
                # No minions have replied within the specified global timeout,
                # return an empty dict
                return ret
            time.sleep(0.02)

    def find_cmd(self, cmd):
        '''
        Hunt through the old salt calls for when cmd was run, return a dict:
        {'<jid>': <return_obj>}
        '''
        job_dir = os.path.join(self.opts['cachedir'], 'jobs')
        ret = {}
        for jid in os.listdir(job_dir):
            jid_dir = os.path.join(job_dir, jid)
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
                except:
                    continue
            else:
                continue
        return ret

    def check_minions(self, expr, expr_form='glob'):
        '''
        Check the passed regex against the available minions' public
        keys stored for authentication. This should return a set of ids
        which match the regex, this will then be used to parse the
        returns to make sure everyone has checked back in.
        '''
        return {'glob': self._check_glob_minions,
                'pcre': self._check_pcre_minions,
                'list': self._check_list_minions,
                'grain': self._check_grain_minions,
                'exsel': self._check_grain_minions,
                'compound': self._check_grain_minions,
                }[expr_form](expr)

    def pub(self, tgt, fun, arg=(), expr_form='glob',
            ret='', jid='', timeout=5):
        '''
        Take the required arguments and publish the given command.
        Arguments:
            tgt:
                The tgt is a regex or a glob used to match up the ids on
                the minions. Salt works by always publishing every command to
                all of the minions and then the minions determine if the
                command is for them based on the tgt value.
            fun:
                The function name to be called on the remote host(s), this must
                be a string in the format "<modulename>.<function name>"
            arg:
                The arg option needs to be a tuple of arguments to pass to the
                calling function, if left blank
        Returns:
            jid:
                A string, as returned by the publisher, which is the job id,
                this will inform the client where to get the job results
            minions:
                A set, the targets that the tgt passed should match.
        '''
        if expr_form == 'nodegroup':
            if tgt not in self.opts['nodegroups']:
                conf_file = self.opts.get('conf_file', 'the master config file')
                err = 'Node group {0} unavailable in {1}'.format(tgt, conf_file)
                raise SaltInvocationError(err)
            tgt = self.opts['nodegroups'][tgt]
            expr_form = 'compound'

        # Run a check_minions, if no minions match return False
        # format the payload - make a function that does this in the payload
        #   module
        # make the zmq client
        # connect to the req server
        # send!
        # return what we get back
        minions = self.check_minions(tgt, expr_form)

        if not minions:
            return {'jid': '',
                    'minions': minions}
        if self.opts['order_masters']:
            package = salt.payload.format_payload(
                    'clear',
                    cmd='publish',
                    tgt=tgt,
                    fun=fun,
                    arg=arg,
                    key=self.key,
                    tgt_type=expr_form,
                    ret=ret,
                    jid=jid,
                    to=timeout)
        else:
            package = salt.payload.format_payload(
                    'clear',
                    cmd='publish',
                    tgt=tgt,
                    fun=fun,
                    arg=arg,
                    key=self.key,
                    tgt_type=expr_form,
                    jid=jid,
                    ret=ret)
        # Prep zmq
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.linger = 0
        socket.connect(
                'tcp://{0[interface]}:{0[ret_port]}'.format(
                    self.opts
                    )
                )
        socket.send(package)
        payload = None
        for ind in range(100):
            try:
                payload = self.serial.loads(
                        socket.recv(
                            zmq.NOBLOCK
                            )
                        )
                break
            except zmq.core.error.ZMQError:
                time.sleep(0.01)
        if not payload:
            return {'jid': '0', 'minions': []}
        return {'jid': payload['load']['jid'],
                'minions': minions}
