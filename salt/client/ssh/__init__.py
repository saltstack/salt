# -*- coding: utf-8 -*-
'''
Create ssh executor system
'''
# Import python libs
from __future__ import print_function
import copy
import getpass
import json
import logging
import multiprocessing
import subprocess
import hashlib
import tarfile
import os
import re
import time
import yaml
import uuid

# Import salt libs
import salt.client.ssh.shell
import salt.client.ssh.wrapper
import salt.config
import salt.exceptions
import salt.exitcodes
import salt.log
import salt.loader
import salt.minion
import salt.roster
import salt.state
import salt.utils
import salt.utils.args
import salt.utils.event
import salt.utils.atomicfile
import salt.utils.thin
import salt.utils.verify
import salt.utils.network
from salt._compat import string_types
from salt.utils import is_windows

try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

# The directory where salt thin is deployed
DEFAULT_THIN_DIR = '/tmp/.%%USER%%_%%FQDNUUID%%__salt'

# RSTR is just a delimiter to distinguish the beginning of salt STDOUT
# and STDERR.  There is no special meaning.  Messages prior to RSTR in
# stderr and stdout are either from SSH or from the shim.
#
# RSTR on both stdout and stderr:
#    no errors in SHIM - output after RSTR is from salt
# No RSTR in stderr, RSTR in stdout:
#    no errors in SSH_SH_SHIM, but SHIM commands for salt master are after
#    RSTR in stdout
# No RSTR in stderr, no RSTR in stdout:
#    Failure in SHIM
# RSTR in stderr, No RSTR in stdout:
#    Undefined behavior
RSTR = '_edbc7885e4f9aac9b83b35999b68d015148caf467b78fa39c05f669c0ff89878'

# The regex to find RSTR in output - Must be on an output line by itself
# NOTE - must use non-grouping match groups or output splitting will fail.
RSTR_RE = r'(?:^|\r?\n)' + RSTR + '(?:\r?\n|$)'

# METHODOLOGY:
#
#   1) Make the _thinnest_ /bin/sh shim (SSH_SH_SHIM) to find the python
#      interpreter and get it invoked
#   2) Once a qualified python is found start it with the SSH_PY_SHIM
#   3) The shim is converted to a single semicolon separated line, so
#      some constructs are needed to keep it clean.

# NOTE:
#   * SSH_SH_SHIM is generic and can be used to load+exec *any* python
#     script on the target.
#   * SSH_PY_SHIM is in a separate file rather than stuffed in a string
#     in salt/client/ssh/__init__.py - this makes testing *easy* because
#     it can be invoked directly.
#   * SSH_PY_SHIM is base64 encoded and formatted into the SSH_SH_SHIM
#     string.  This makes the python script "armored" so that it can
#     all be passed in the SSH command and will not need special quoting
#     (which likely would be impossibe to do anyway)
#   * The formatted SSH_SH_SHIM with the SSH_PY_SHIM payload is a bit
#     big (~7.5k).  If this proves problematic for an SSH command we
#     might try simply invoking "/bin/sh -s" and passing the formatted
#     SSH_SH_SHIM on SSH stdin.

# NOTE: there are two passes of formatting:
# 1) Substitute in static values
#   - EX_THIN_PYTHON_OLD  - exit code if a suitable python is not found
# 2) Substitute in instance-specific commands
#   - DEBUG       - enable shim debugging (any non-zero string enables)
#   - SUDO        - load python and execute as root (any non-zero string enables)
#   - SSH_PY_CODE - base64-encoded python code to execute
#   - SSH_PY_ARGS - arguments to pass to python code

# This shim generically loads python code . . . and *no* more.
# - Uses /bin/sh for maximum compatibility - then jumps to
#   python for ultra-maximum compatibility.
#
# 1. Identify a suitable python
# 2. Jump to python

SSH_SH_SHIM = r'''/bin/sh << 'EOF'
set -e
set -u
DEBUG="{{DEBUG}}"
if [ -n "$DEBUG" ]
then set -x
fi
SUDO=""
if [ -n "{{SUDO}}" ]
then SUDO="sudo "
fi
EX_PYTHON_OLD={EX_THIN_PYTHON_OLD}
PYTHON_CMDS="python27 python2.7 python26 python2.6 python2 python"
for py_cmd in $PYTHON_CMDS
do if "$py_cmd" -c "import sys; sys.exit(not sys.hexversion >= 0x02060000);" >/dev/null 2>&1
then py_cmd_path=`"$py_cmd" -c 'import sys; print sys.executable;'`
exec $SUDO "$py_cmd_path" -c 'exec """{{SSH_PY_CODE}}""".decode("base64")'
exit 0
else continue
fi
done
echo "ERROR: Unable to locate appropriate python command" >&2
exit $EX_PYTHON_OLD
EOF'''.format(
    EX_THIN_PYTHON_OLD=salt.exitcodes.EX_THIN_PYTHON_OLD,
)

if not is_windows():
    shim_file = os.path.join(os.path.dirname(__file__), 'ssh_py_shim.py')
    if not os.path.exists(shim_file):
        # On esky builds we only have the .pyc file
        shim_file += "c"
    with open(shim_file) as ssh_py_shim:
        SSH_PY_SHIM = ssh_py_shim.read()

log = logging.getLogger(__name__)


class SSH(object):
    '''
    Create an SSH execution system
    '''
    def __init__(self, opts):
        pull_sock = os.path.join(opts['sock_dir'], 'master_event_pull.ipc')
        if os.path.isfile(pull_sock) and HAS_ZMQ:
            self.event = salt.utils.event.get_event(
                    'master',
                    opts['sock_dir'],
                    opts['transport'],
                    opts=opts,
                    listen=False)
        else:
            self.event = None
        self.opts = opts
        self.opts['_ssh_version'] = ssh_version()
        self.tgt_type = self.opts['selected_target_option'] \
                if self.opts['selected_target_option'] else 'glob'
        self.roster = salt.roster.Roster(opts, opts.get('roster'))
        self.targets = self.roster.targets(
                self.opts['tgt'],
                self.tgt_type)
        priv = self.opts.get(
                'ssh_priv',
                os.path.join(
                    self.opts['pki_dir'],
                    'ssh',
                    'salt-ssh.rsa'
                    )
                )
        if not os.path.isfile(priv):
            try:
                salt.client.ssh.shell.gen_key(priv)
            except OSError:
                raise salt.exceptions.SaltClientError('salt-ssh could not be run because it could not generate keys.\n\nYou can probably resolve this by executing this script with increased permissions via sudo or by running as root.\nYou could also use the \'-c\' option to supply a configuration directory that you have permissions to read and write to.')
        self.defaults = {
            'user': self.opts.get(
                'ssh_user',
                salt.config.DEFAULT_MASTER_OPTS['ssh_user']
            ),
            'port': self.opts.get(
                'ssh_port',
                salt.config.DEFAULT_MASTER_OPTS['ssh_port']
            ),
            'passwd': self.opts.get(
                'ssh_passwd',
                salt.config.DEFAULT_MASTER_OPTS['ssh_passwd']
            ),
            'priv': priv,
            'timeout': self.opts.get(
                'ssh_timeout',
                salt.config.DEFAULT_MASTER_OPTS['ssh_timeout']
            ) + self.opts.get(
                'timeout',
                salt.config.DEFAULT_MASTER_OPTS['timeout']
            ),
            'sudo': self.opts.get(
                'ssh_sudo',
                salt.config.DEFAULT_MASTER_OPTS['ssh_sudo']
            ),
        }
        if self.opts.get('rand_thin_dir'):
            self.defaults['thin_dir'] = os.path.join(
                    '/tmp',
                    '.{0}'.format(uuid.uuid4().hex[:6]))
            self.opts['wipe_ssh'] = 'True'
        self.serial = salt.payload.Serial(opts)
        self.returners = salt.loader.returners(self.opts, {})
        self.fsclient = salt.fileclient.FSClient(self.opts)
        self.mods = mod_data(self.fsclient)

    def get_pubkey(self):
        '''
        Return the key string for the SSH public key
        '''
        priv = self.opts.get(
                'ssh_priv',
                os.path.join(
                    self.opts['pki_dir'],
                    'ssh',
                    'salt-ssh.rsa'
                    )
                )
        pub = '{0}.pub'.format(priv)
        with open(pub, 'r') as fp_:
            return '{0} rsa root@master'.format(fp_.read().split()[1])

    def key_deploy(self, host, ret):
        '''
        Deploy the SSH key if the minions don't auth
        '''
        if not isinstance(ret[host], dict):
            if self.opts.get('ssh_key_deploy'):
                target = self.targets[host]
                if 'passwd' in target:
                    self._key_deploy_run(host, target, False)
            return ret
        if ret[host].get('stderr', '').count('Permission denied'):
            target = self.targets[host]
            # permission denied, attempt to auto deploy ssh key
            print(('Permission denied for host {0}, do you want to deploy '
                   'the salt-ssh key? (password required):').format(host))
            deploy = raw_input('[Y/n] ')
            if deploy.startswith(('n', 'N')):
                return ret
            target['passwd'] = getpass.getpass(
                    'Password for {0}@{1}: '.format(target['user'], host)
                )
            return self._key_deploy_run(host, target, True)
        return ret

    def _key_deploy_run(self, host, target, re_run=True):
        '''
        The ssh-copy-id routine
        '''
        argv = [
            'ssh.set_auth_key',
            target.get('user', 'root'),
            self.get_pubkey(),
        ]

        single = Single(
                self.opts,
                argv,
                host,
                mods=self.mods,
                fsclient=self.fsclient,
                **target)
        if salt.utils.which('ssh-copy-id'):
            # we have ssh-copy-id, use it!
            stdout, stderr, retcode = single.shell.copy_id()
        else:
            stdout, stderr, retcode = single.run()
        if re_run:
            target.pop('passwd')
            single = Single(
                    self.opts,
                    self.opts['argv'],
                    host,
                    mods=self.mods,
                    fsclient=self.fsclient,
                    **target)
            stdout, stderr, retcode = single.cmd_block()
            try:
                data = salt.utils.find_json(stdout)
                return {host: data.get('local', data)}
            except Exception:
                if stderr:
                    return {host: stderr}
                return {host: 'Bad Return'}
        if os.EX_OK != retcode:
            return {host: stderr}
        return {host: stdout}

    def handle_routine(self, que, opts, host, target):
        '''
        Run the routine in a "Thread", put a dict on the queue
        '''
        opts = copy.deepcopy(opts)
        single = Single(
                opts,
                opts['argv'],
                host,
                mods=self.mods,
                fsclient=self.fsclient,
                **target)
        ret = {'id': single.id}
        stdout, stderr, retcode = single.run()
        # This job is done, yield
        try:
            data = salt.utils.find_json(stdout)
            if len(data) < 2 and 'local' in data:
                ret['ret'] = data['local']
            else:
                ret['ret'] = {
                    'stdout': stdout,
                    'stderr': stderr,
                    'retcode': retcode,
                }
        except Exception:
            ret['ret'] = {
                'stdout': stdout,
                'stderr': stderr,
                'retcode': retcode,
            }
        que.put(ret)

    def handle_ssh(self):
        '''
        Spin up the needed threads or processes and execute the subsequent
        routines
        '''
        que = multiprocessing.Queue()
        running = {}
        target_iter = self.targets.__iter__()
        returned = set()
        rets = set()
        init = False
        if not self.targets:
            raise salt.exceptions.SaltClientError('No matching targets found in roster.')
        while True:
            if len(running) < self.opts.get('ssh_max_procs', 25) and not init:
                try:
                    host = next(target_iter)
                except StopIteration:
                    init = True
                    continue
                for default in self.defaults:
                    if default not in self.targets[host]:
                        self.targets[host][default] = self.defaults[default]
                args = (
                        que,
                        self.opts,
                        host,
                        self.targets[host],
                        )
                routine = multiprocessing.Process(
                                target=self.handle_routine,
                                args=args)
                routine.start()
                running[host] = {'thread': routine}
                continue
            ret = {}
            try:
                ret = que.get(False)
                if 'id' in ret:
                    returned.add(ret['id'])
            except Exception:
                pass
            for host in running:
                if host in returned:
                    if not running[host]['thread'].is_alive():
                        running[host]['thread'].join()
                        rets.add(host)
            for host in rets:
                if host in running:
                    running.pop(host)
            if ret:
                if not isinstance(ret, dict):
                    continue
                yield {ret['id']: ret['ret']}
            if len(rets) >= len(self.targets):
                break

    def run_iter(self):
        '''
        Execute and yield returns as they come in, do not print to the display
        '''
        for ret in self.handle_ssh():
            yield ret

    def cache_job(self, jid, id_, ret):
        '''
        Cache the job information
        '''
        self.returners['{0}.returner'.format(self.opts['master_job_cache'])]({'jid': jid,
                                                                                      'id': id_,
                                                                                      'return': ret})

    def run(self):
        '''
        Execute the overall routine
        '''
        fstr = '{0}.prep_jid'.format(self.opts['master_job_cache'])
        jid = self.returners[fstr]()

        # Save the invocation information
        argv = self.opts['argv']

        if self.opts['raw_shell']:
            fun = 'ssh._raw'
            args = argv
        else:
            fun = argv[0] if argv else ''
            args = argv[1:]

        job_load = {
            'jid': jid,
            'tgt_type': self.tgt_type,
            'tgt': self.opts['tgt'],
            'user': self.opts['user'],
            'fun': fun,
            'arg': args,
            }

        # save load to the master job cache
        self.returners['{0}.save_load'.format(self.opts['master_job_cache'])](jid, job_load)

        if self.opts.get('verbose'):
            msg = 'Executing job with jid {0}'.format(jid)
            print(msg)
            print('-' * len(msg) + '\n')
            print('')
        sret = {}
        outputter = self.opts.get('output', 'nested')
        for ret in self.handle_ssh():
            host = ret.keys()[0]
            self.cache_job(jid, host, ret[host])
            ret = self.key_deploy(host, ret)
            if not isinstance(ret[host], dict):
                p_data = {host: ret[host]}
            elif 'return' not in ret[host]:
                p_data = ret
            else:
                outputter = ret[host].get('out', self.opts.get('output', 'nested'))
                p_data = {host: ret[host].get('return', {})}
            if self.opts.get('static'):
                sret.update(p_data)
            else:
                salt.output.display_output(
                        p_data,
                        outputter,
                        self.opts)
            if self.event:
                self.event.fire_event(
                        ret,
                        salt.utils.event.tagify(
                            [jid, 'ret', host],
                            'job'))
        if self.opts.get('static'):
            salt.output.display_output(
                    sret,
                    outputter,
                    self.opts)


class Single(object):
    '''
    Hold onto a single ssh execution
    '''
    # 1. Get command ready
    # 2. Check if target has salt
    # 3. deploy salt-thin
    # 4. execute requested command via salt-thin
    def __init__(
            self,
            opts,
            argv,
            id_,
            host,
            user=None,
            port=None,
            passwd=None,
            priv=None,
            timeout=None,
            sudo=False,
            tty=False,
            mods=None,
            fsclient=None,
            **kwargs):
        self.opts = opts
        if kwargs.get('wipe'):
            self.wipe = 'False'
        else:
            self.wipe = 'True' if self.opts.get('wipe_ssh') else 'False'
        if kwargs.get('thin_dir'):
            self.thin_dir = kwargs['thin_dir']
        else:
            if user:
                thin_dir = DEFAULT_THIN_DIR.replace('%%USER%%', user)
            else:
                thin_dir = DEFAULT_THIN_DIR.replace('%%USER%%', 'root')
            self.thin_dir = thin_dir.replace(
                '%%FQDNUUID%%',
                uuid.uuid3(uuid.NAMESPACE_DNS,
                           salt.utils.network.get_fqhostname()).hex[:6]
            )
        self.opts['thin_dir'] = self.thin_dir
        self.fsclient = fsclient
        self.context = {'master_opts': self.opts,
                        'fileclient': self.fsclient}

        if isinstance(argv, string_types):
            self.argv = [argv]
        else:
            self.argv = argv

        self.fun, self.args, self.kwargs = self.__arg_comps()
        self.id = id_

        self.mods = mods if isinstance(mods, dict) else {}
        args = {'host': host,
                'user': user,
                'port': port,
                'passwd': passwd,
                'priv': priv,
                'timeout': timeout,
                'sudo': sudo,
                'tty': tty,
                'mods': self.mods}
        self.minion_config = yaml.dump(
                {
                    'root_dir': os.path.join(self.thin_dir, 'running_data'),
                    'id': self.id,
                    'sock_dir': '/',
                }, width=1000).strip()
        self.target = kwargs
        self.target.update(args)
        self.serial = salt.payload.Serial(opts)
        self.wfuncs = salt.loader.ssh_wrapper(opts, None, self.context)
        self.shell = salt.client.ssh.shell.Shell(opts, **args)

    def __arg_comps(self):
        '''
        Return the function name and the arg list
        '''
        fun = self.argv[0] if self.argv else ''
        args = []
        kws = {}
        for arg in self.argv[1:]:
            # FIXME - there is a bug here that will steal a non-keyword argument.
            # example:
            #
            # .. code-block:: bash
            #
            #     salt-ssh '*' cmd.run_all 'n=$((RANDOM%8)); exit $n'
            #
            # The 'n=' appears to be a keyword argument, but it is
            # simply the argument!
            if re.match(r'\w+=', arg):
                (key, val) = arg.split('=', 1)
                kws[key] = val
            else:
                args.append(arg)
        return fun, args, kws

    def _escape_arg(self, arg):
        '''
        Properly escape argument to protect special characters from shell
        interpretation.  This avoids having to do tricky argument quoting.

        Effectively just escape all characters in the argument that are not
        alphanumeric!
        '''
        return ''.join(['\\' + char if re.match(r'\W', char) else char for char in arg])

    def deploy(self):
        '''
        Deploy salt-thin
        '''
        if self.opts.get('_caller_cachedir'):
            cachedir = self.opts.get('_caller_cachedir')
        else:
            cachedir = self.opts['cachedir']
        thin = salt.utils.thin.gen_thin(cachedir)
        self.shell.send(
            thin,
            os.path.join(self.thin_dir, 'salt-thin.tgz'),
        )
        self.deploy_ext()
        return True

    def deploy_ext(self):
        '''
        Deploy the ext_mods tarball
        '''
        if self.mods.get('file'):
            self.shell.send(
                self.mods['file'],
                os.path.join(self.thin_dir, 'salt-ext_mods.tgz'),
            )
        return True

    def run(self, deploy_attempted=False):
        '''
        Execute the routine, the routine can be either:
        1. Execute a raw shell command
        2. Execute a wrapper func
        3. Execute a remote Salt command

        If a (re)deploy is needed, then retry the operation after a deploy
        attempt

        Returns tuple of (stdout, stderr, retcode)
        '''
        stdout = stderr = retcode = None

        if self.opts.get('raw_shell'):
            cmd_str = ' '.join([self._escape_arg(arg) for arg in self.argv])
            stdout, stderr, retcode = self.shell.exec_cmd(cmd_str)

        elif self.fun in self.wfuncs:
            stdout = self.run_wfunc()

        else:
            stdout, stderr, retcode = self.cmd_block()

        return stdout, stderr, retcode

    def run_wfunc(self):
        '''
        Execute a wrapper function

        Returns tuple of (json_data, '')
        '''
        # Ensure that opts/grains are up to date
        # Execute routine
        data_cache = False
        data = None
        cdir = os.path.join(self.opts['cachedir'], 'minions', self.id)
        if not os.path.isdir(cdir):
            os.makedirs(cdir)
        datap = os.path.join(cdir, 'ssh_data.p')
        refresh = False
        if not os.path.isfile(datap):
            refresh = True
        else:
            passed_time = (time.time() - os.stat(datap).st_mtime) / 60
            if passed_time > self.opts.get('cache_life', 60):
                refresh = True

        if self.opts.get('refresh_cache'):
            refresh = True
        conf_grains = {}
        #Save conf file grains before they get clobbered
        if 'ssh_grains' in self.opts:
            conf_grains = self.opts['ssh_grains']
        if not data_cache:
            refresh = True
        if refresh:
            # Make the datap
            # TODO: Auto expire the datap
            pre_wrapper = salt.client.ssh.wrapper.FunctionWrapper(
                self.opts,
                self.id,
                fsclient=self.fsclient,
                **self.target)
            opts_pkg = pre_wrapper['test.opts_pkg']()
            opts_pkg['file_roots'] = self.opts['file_roots']
            opts_pkg['pillar_roots'] = self.opts['pillar_roots']
            opts_pkg['ext_pillar'] = self.opts['ext_pillar']
            opts_pkg['_ssh_version'] = self.opts['_ssh_version']
            if '_caller_cachedir' in self.opts:
                opts_pkg['_caller_cachedir'] = self.opts['_caller_cachedir']
            else:
                opts_pkg['_caller_cachedir'] = self.opts['cachedir']
            # Use the ID defined in the roster file
            opts_pkg['id'] = self.id

            if '_error' in opts_pkg:
                #Refresh failed
                ret = json.dumps({'local': opts_pkg})
                return ret

            pillar = salt.pillar.Pillar(
                    opts_pkg,
                    opts_pkg['grains'],
                    opts_pkg['id'],
                    opts_pkg.get('environment', 'base')
                    )
            pillar_dirs = {}
            pillar_data = pillar.compile_pillar(pillar_dirs=pillar_dirs)

            # TODO: cache minion opts in datap in master.py
            data = {'opts': opts_pkg,
                    'grains': opts_pkg['grains'],
                    'pillar': pillar_data}
            if data_cache:
                with salt.utils.fopen(datap, 'w+b') as fp_:
                    fp_.write(
                            self.serial.dumps(data)
                            )
        if not data and data_cache:
            with salt.utils.fopen(datap, 'rb') as fp_:
                data = self.serial.load(fp_)
        opts = data.get('opts', {})
        opts['grains'] = data.get('grains')

        # Restore master grains
        for grain in conf_grains:
            opts['grains'][grain] = conf_grains[grain]
        # Enable roster grains support
        if 'grains' in self.target:
            for grain in self.target['grains']:
                opts['grains'][grain] = self.target['grains'][grain]

        opts['pillar'] = data.get('pillar')
        wrapper = salt.client.ssh.wrapper.FunctionWrapper(
            opts,
            self.id,
            fsclient=self.fsclient,
            **self.target)
        self.wfuncs = salt.loader.ssh_wrapper(opts, wrapper, self.context)
        wrapper.wfuncs = self.wfuncs
        try:
            result = self.wfuncs[self.fun](*self.args, **self.kwargs)
        except TypeError as exc:
            result = 'TypeError encountered executing {0}: {1}'.format(self.fun, exc)
        except Exception as exc:
            result = 'An Exception occurred while executing {0}: {1}'.format(self.fun, exc)
        # Mimic the json data-structure that "salt-call --local" will
        # emit (as seen in ssh_py_shim.py)
        if isinstance(result, dict) and 'local' in result:
            ret = json.dumps({'local': result['local']})
        else:
            ret = json.dumps({'local': {'return': result}})
        return ret

    def _cmd_str(self):
        '''
        Prepare the command string
        '''
        sudo = 'sudo' if self.target['sudo'] else ''
        if '_caller_cachedir' in self.opts:
            cachedir = self.opts['_caller_cachedir']
        else:
            cachedir = self.opts['cachedir']
        thin_sum = salt.utils.thin.thin_sum(cachedir, 'sha1')
        debug = ''
        if salt.log.LOG_LEVELS['debug'] >= salt.log.LOG_LEVELS[self.opts['log_level']]:
            debug = '1'
        arg_str = '''
OPTIONS = OBJ()
OPTIONS.config = '{0}'
OPTIONS.delimiter = '{1}'
OPTIONS.saltdir = '{2}'
OPTIONS.checksum = '{3}'
OPTIONS.hashfunc = '{4}'
OPTIONS.version = '{5}'
OPTIONS.ext_mods = '{6}'
OPTIONS.wipe = {7}
ARGS = {8}\n'''.format(self.minion_config,
                         RSTR,
                         self.thin_dir,
                         thin_sum,
                         'sha1',
                         salt.__version__,
                         self.mods.get('version', ''),
                         self.wipe,
                         self.argv)
        py_code = SSH_PY_SHIM.replace('#%%OPTS', arg_str)
        py_code_enc = py_code.encode('base64')

        cmd = SSH_SH_SHIM.format(
            DEBUG=debug,
            SUDO=sudo,
            SSH_PY_CODE=py_code_enc,
        )

        return cmd

    def cmd(self):
        '''
        Prepare the pre-check command to send to the subsystem
        '''
        if self.fun.startswith('state.highstate'):
            self.highstate_seed()
        elif self.fun.startswith('state.sls'):
            args, kwargs = salt.minion.load_args_and_kwargs(
                self.sls_seed,
                salt.utils.args.parse_input(self.args)
            )
            self.sls_seed(*args, **kwargs)
        cmd_str = self._cmd_str()

        for stdout, stderr, retcode in self.shell.exec_nb_cmd(cmd_str):
            yield stdout, stderr, retcode

    def cmd_block(self, is_retry=False):
        '''
        Prepare the pre-check command to send to the subsystem
        '''
        # 1. execute SHIM + command
        # 2. check if SHIM returns a master request or if it completed
        # 3. handle any master request
        # 4. re-execute SHIM + command
        # 5. split SHIM results from command results
        # 6. return command results

        log.debug('Performing shimmed, blocking command as follows:\n{0}'.format(' '.join(self.argv)))
        cmd_str = self._cmd_str()
        stdout, stderr, retcode = self.shell.exec_cmd(cmd_str)

        log.debug('STDOUT {1}\n{0}'.format(stdout, self.target['host']))
        log.debug('STDERR {1}\n{0}'.format(stderr, self.target['host']))
        log.debug('RETCODE {1}: {0}'.format(retcode, self.target['host']))

        error = self.categorize_shim_errors(stdout, stderr, retcode)
        if error:
            if error == 'Undefined SHIM state':
                self.deploy()
                stdout, stderr, retcode = self.shell.exec_cmd(cmd_str)
                if not re.search(RSTR_RE, stdout) or not re.search(RSTR_RE, stderr):
                    # If RSTR is not seen in both stdout and stderr then there
                    # was a thin deployment problem.
                    return 'ERROR: Failure deploying thin, undefined state: {0}'.format(stdout), stderr, retcode
                stdout = re.split(RSTR_RE, stdout, 1)[1].strip()
                stderr = re.split(RSTR_RE, stderr, 1)[1].strip()
            else:
                return 'ERROR: {0}'.format(error), stderr, retcode

        # FIXME: this discards output from ssh_shim if the shim succeeds.  It should
        # always save the shim output regardless of shim success or failure.
        if re.search(RSTR_RE, stdout):
            stdout = re.split(RSTR_RE, stdout, 1)[1].strip()
        else:
            # This is actually an error state prior to the shim but let it fall through
            pass

        if re.search(RSTR_RE, stderr):
            # Found RSTR in stderr which means SHIM completed and only
            # and remaining output is only from salt.
            stderr = re.split(RSTR_RE, stderr, 1)[1].strip()

        else:
            # RSTR was found in stdout but not stderr - which means there
            # is a SHIM command for the master.
            shim_command = re.split(r'\r?\n', stdout, 1)[0].strip()
            if 'deploy' == shim_command and retcode == salt.exitcodes.EX_THIN_DEPLOY:
                self.deploy()
                stdout, stderr, retcode = self.shell.exec_cmd(cmd_str)
                if not re.search(RSTR_RE, stdout) or not re.search(RSTR_RE, stderr):
                    # If RSTR is not seen in both stdout and stderr then there
                    # was a thin deployment problem.
                    return 'ERROR: Failure deploying thin: {0}\n{1}'.format(stdout, stderr), stderr, retcode
                stdout = re.split(RSTR_RE, stdout, 1)[1].strip()
                stderr = re.split(RSTR_RE, stderr, 1)[1].strip()
            elif 'ext_mods' == shim_command:
                self.deploy_ext()
                stdout, stderr, retcode = self.shell.exec_cmd(cmd_str)
                if not re.search(RSTR_RE, stdout) or not re.search(RSTR_RE, stderr):
                    # If RSTR is not seen in both stdout and stderr then there
                    # was a thin deployment problem.
                    return 'ERROR: Failure deploying ext_mods: {0}'.format(stdout), stderr, retcode
                stdout = re.split(RSTR_RE, stdout, 1)[1].strip()
                stderr = re.split(RSTR_RE, stderr, 1)[1].strip()

        return stdout, stderr, retcode

    def categorize_shim_errors(self, stdout, stderr, retcode):
        if re.search(RSTR_RE, stdout) and stdout != RSTR+'\n':
            # RSTR was found in stdout which means that the shim
            # functioned without *errors* . . . but there may be shim
            # commands, unless the only thing we found is RSTR
            return None

        if re.search(RSTR_RE, stderr):
            # Undefined state
            return 'Undefined SHIM state'

        if stderr.startswith('Permission denied'):
            # SHIM was not even reached
            return None

        perm_error_fmt = 'Permissions problem, target user may need '\
                         'to be root or use sudo:\n {0}'

        errors = [
            (
                (),
                'sudo: no tty present and no askpass program specified',
                'sudo expected a password, NOPASSWD required'
            ),
            (
                (salt.exitcodes.EX_THIN_PYTHON_OLD,),
                'Python interpreter is too old',
                'salt requires python 2.6 or newer on target hosts'
            ),
            (
                (salt.exitcodes.EX_THIN_CHECKSUM,),
                'checksum mismatched',
                'The salt thin transfer was corrupted'
            ),
            (
                (os.EX_CANTCREAT,),
                'salt path .* exists but is not a directory',
                'A necessary path for salt thin unexpectedly exists:\n ' + stderr,
            ),
            (
                (),
                'sudo: sorry, you must have a tty to run sudo',
                'sudo is configured with requiretty'
            ),
            (
                (),
                'Failed to open log file',
                perm_error_fmt.format(stderr)
            ),
            (
                (),
                'Permission denied:.*/salt',
                perm_error_fmt.format(stderr)
            ),
            (
                (),
                'Failed to create directory path.*/salt',
                perm_error_fmt.format(stderr)
            ),
            (
                (os.EX_SOFTWARE,),
                'exists but is not',
                'An internal error occurred with the shim, please investigate:\n ' + stderr,
            ),
        ]

        for error in errors:
            if retcode in error[0] or re.search(error[1], stderr):
                return error[2]
        return None

    def check_refresh(self, data, ret):
        '''
        Stub out check_refresh
        '''
        return

    def module_refresh(self):
        '''
        Module refresh is not needed, stub it out
        '''
        return


def lowstate_file_refs(chunks):
    '''
    Create a list of file ref objects to reconcile
    '''
    refs = {}
    for chunk in chunks:
        saltenv = 'base'
        crefs = []
        for state in chunk:
            if state == '__env__':
                saltenv = chunk[state]
            elif state == 'saltenv':
                saltenv = chunk[state]
            elif state.startswith('__'):
                continue
            crefs.extend(salt_refs(chunk[state]))
        if crefs:
            if saltenv not in refs:
                refs[saltenv] = []
            refs[saltenv].append(crefs)
    return refs


def salt_refs(data):
    '''
    Pull salt file references out of the states
    '''
    proto = 'salt://'
    ret = []
    if isinstance(data, str):
        if data.startswith(proto):
            return [data]
    if isinstance(data, list):
        for comp in data:
            if isinstance(comp, str):
                if comp.startswith(proto):
                    ret.append(comp)
    return ret


def mod_data(fsclient):
    '''
    Generate the module arguments for the shim data
    '''
    # TODO, change out for a fileserver backend
    sync_refs = [
            'modules',
            'states',
            'grains',
            'renderers',
            'returners',
            ]
    ret = {}
    envs = fsclient.envs()
    ver_base = ''
    for env in envs:
        files = fsclient.file_list(env)
        for ref in sync_refs:
            mods_data = {}
            pref = '_{0}'.format(ref)
            for fn_ in sorted(files):
                if fn_.startswith(pref):
                    if fn_.endswith(('.py', '.so', '.pyx')):
                        full = 'salt://{0}'.format(fn_)
                        mod_path = fsclient.cache_file(full, env)
                        if not os.path.isfile(mod_path):
                            continue
                        mods_data[os.path.basename(fn_)] = mod_path
                        chunk = salt.utils.get_hash(mod_path)
                        ver_base += chunk
            if mods_data:
                if ref in ret:
                    ret[ref].update(mods_data)
                else:
                    ret[ref] = mods_data
    if not ret:
        return {}
    ver = hashlib.sha1(ver_base).hexdigest()
    ext_tar_path = os.path.join(
            fsclient.opts['cachedir'],
            'ext_mods.{0}.tgz'.format(ver))
    mods = {'version': ver,
            'file': ext_tar_path}
    if os.path.isfile(ext_tar_path):
        return mods
    tfp = tarfile.open(ext_tar_path, 'w:gz')
    verfile = os.path.join(fsclient.opts['cachedir'], 'ext_mods.ver')
    with salt.utils.fopen(verfile, 'w+') as fp_:
        fp_.write(ver)
    tfp.add(verfile, 'ext_version')
    for ref in ret:
        for fn_ in ret[ref]:
            tfp.add(ret[ref][fn_], os.path.join(ref, fn_))
    tfp.close()
    return mods


def ssh_version():
    '''
    Returns the version of the installed ssh command
    '''
    # This function needs more granular checks and to be validated against
    # older versions of ssh
    ret = subprocess.Popen(
            ['ssh', '-V'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE).communicate()
    try:
        return ret[1].split(',')[0].split('_')[1]
    except IndexError:
        return '2.0'
