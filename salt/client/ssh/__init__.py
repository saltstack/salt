# -*- coding: utf-8 -*-
'''
Create ssh executor system
'''
# Import python libs
import os
import tarfile
import tempfile
import json
import getpass
import shutil
import copy
import time
import multiprocessing
import re
import logging
import yaml

# Import salt libs
import salt.client.ssh.shell
import salt.client.ssh.wrapper
import salt.utils
import salt.utils.thin
import salt.utils.verify
import salt.utils.event
import salt.roster
import salt.state
import salt.loader
import salt.minion
import salt.exceptions

# This is just a delimiter to distinguish the beginning of salt STDOUT.  There
# is no special meaning
RSTR = '_edbc7885e4f9aac9b83b35999b68d015148caf467b78fa39c05f669c0ff89878'


# This shim facilitates remote salt-call operations
# - Explicitly invokes Bourne shell for universal compatibility
#
# 1. Identify a suitable python
# 2. Test for remote salt-call and version if present
# 3. Signal to (re)deploy if missing or out of date
#    - If this is a a first deploy, then test python version
# 4. Perform salt-call

# Note there are two levels of formatting.
# - First format pass inserts salt version and delimiter
# - Second pass at run-time and inserts optional "sudo" and command
SSH_SHIM = '''/bin/sh << 'EOF'
      for py_candidate in \\
            python27      \\
            python2.7     \\
            python26      \\
            python2.6     \\
            python2       \\
            python        ;
      do
         if [ $(which $py_candidate 2>/dev/null) ]
         then
               PYTHON=$(which $py_candidate)
               break
         fi
      done
      SALT=/tmp/.salt/salt-call
      if [ {{2}} = 'md5' ]
      then
         for md5_candidate in \\
            md5sum            \\
            md5               ;
         do
            if [ $(which $md5_candidate 2>/dev/null) ]
            then
                SUMCHECK=$(which $md5_candidate)
                break
            fi
         done
      else
         SUMCHECK={{2}}
      fi

      if [ $SUMCHECK = '/sbin/md5' ]
      then
         CUT_MARK=4
      else
         CUT_MARK=1
      fi

      if [ -f $SALT ]
      then
         if [ $(cat /tmp/.salt/version) != {0} ]
         then
            {{0}} rm -rf /tmp/.salt && install -m 0700 -d /tmp/.salt
            if [ $? -ne 0 ]; then
                exit 1
            fi
            echo "{1}"
            echo "deploy"
            exit 1
         fi
      else
         PY_TOO_OLD=$($PYTHON -c 'import sys; print sys.hexversion < 0x02060000')
         if [ $PY_TOO_OLD = 'True' ];
         then
            echo "Python too old" >&2
            exit 1
         fi
         if [ -f /tmp/.salt/salt-thin.tgz ]
         then
             [ $($SUMCHECK /tmp/.salt/salt-thin.tgz | cut -f$CUT_MARK -d' ') = {{3}} ] && {{0}} tar opxzvf /tmp/.salt/salt-thin.tgz -C /tmp/.salt
         else
             install -m 0700 -d /tmp/.salt
             echo "{1}"
             echo "deploy"
             exit 1
         fi
      fi
      echo '{{4}}' > /tmp/.salt/minion
      echo "{1}"
      {{0}} $PYTHON $SALT --local --out json -l quiet {{1}} -c /tmp/.salt
EOF'''.format(salt.__version__, RSTR)

log = logging.getLogger(__name__)


class SSH(object):
    '''
    Create an SSH execution system
    '''
    def __init__(self, opts):
        self.verify_env()
        if salt.utils.verify.verify_socket(
                opts['interface'],
                opts['publish_port'],
                opts['ret_port']):
            self.event = salt.utils.event.MasterEvent(opts['sock_dir'])
        else:
            self.event = None
        self.opts = opts
        tgt_type = self.opts['selected_target_option'] \
                if self.opts['selected_target_option'] else 'glob'
        self.roster = salt.roster.Roster(opts)
        self.targets = self.roster.targets(
                self.opts['tgt'],
                tgt_type)
        priv = self.opts.get(
                'ssh_priv',
                os.path.join(
                    self.opts['pki_dir'],
                    'ssh',
                    'salt-ssh.rsa'
                    )
                )
        if not os.path.isfile(priv):
            salt.client.ssh.shell.gen_key(priv)
        self.defaults = {
                'user': self.opts.get('ssh_user', 'root'),
                'port': self.opts.get('ssh_port', '22'),
                'passwd': self.opts.get('ssh_passwd', ''),
                'priv': priv,
                'timeout': self.opts.get('ssh_timeout', 60),
                'sudo': self.opts.get('ssh_sudo', False),
                }
        self.serial = salt.payload.Serial(opts)

    def verify_env(self):
        '''
        Verify that salt-ssh is ready to run
        '''
        if not salt.utils.which('sshpass'):
            log.warning('Warning:  sshpass is not present, so password-based '
                        'authentication is not available.')

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
            return '{0} root@master'.format(fp_.read().split()[1])

    def key_deploy(self, host, ret):
        '''
        Deploy the SSH key if the minions don't auth
        '''
        if not isinstance(ret[host], basestring):
            if self.opts.get('ssh_key_deploy'):
                target = self.targets[host]
                if 'passwd' in target:
                    self._key_deploy_run(host, target, False)
            return ret
        if ret[host].startswith('Permission denied'):
            target = self.targets[host]
            # permission denied, attempt to auto deploy ssh key
            print(('Permission denied for host {0}, do you want to deploy '
                   'the salt-ssh key? (password required):').format(host))
            deploy = raw_input('[Y/n]')
            if deploy.startswith(('n', 'N')):
                return ret
            target['passwd'] = getpass.getpass(
                    'Password for {0}@{1}:'.format(target['user'], host)
                )
            return self._key_deploy_run(host, target, True)
        return ret

    def _key_deploy_run(self, host, target, re_run=True):
        '''
        The ssh-copy-id routine
        '''
        arg_str = 'ssh.set_auth_key {0} {1}'.format(
                target.get('user', 'root'),
                self.get_pubkey())

        single = Single(
                self.opts,
                arg_str,
                host,
                **target)
        if salt.utils.which('ssh-copy-id'):
            # we have ssh-copy-id, use it!
            single.shell.copy_id()
        else:
            ret = single.run()
        if re_run:
            target.pop('passwd')
            single = Single(
                    self.opts,
                    self.opts['arg_str'],
                    host,
                    **target)
            stdout, stderr = single.cmd_block()
            try:
                data = salt.utils.find_json(stdout)
                return {host: data.get('local', data)}
            except Exception:
                if stderr:
                    return {host: stderr}
                return {host: 'Bad Return'}
        return ret

    def handle_routine(self, que, opts, host, target):
        '''
        Run the routine in a "Thread", put a dict on the queue
        '''
        opts = copy.deepcopy(opts)
        single = Single(
                opts,
                opts['arg_str'],
                host,
                **target)
        ret = {'id': single.id}
        stdout, stderr = single.run()
        if stdout.startswith('deploy'):
            single.deploy()
            stdout, stderr = single.run()
        # This job is done, yield
        try:
            if not stdout and stderr:
                if 'Permission denied' in stderr:
                    ret['ret'] = 'Permission denied'
                else:
                    ret['ret'] = stderr
            else:
                data = salt.utils.find_json(stdout)
                if len(data) < 2 and 'local' in data:
                    ret['ret'] = data['local']
                else:
                    ret['ret'] = data
        except Exception:
            ret['ret'] = stdout
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
        while True:
            if len(running) < self.opts.get('ssh_max_procs', 25) and not init:
                try:
                    host = next(target_iter)
                except StopIteration:
                    init = True
                    continue
                for default in self.defaults:
                    if not default in self.targets[host]:
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
        jid_dir = salt.utils.jid_dir(
                jid,
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        if not os.path.isdir(jid_dir):
            log.error(
                'An inconsistency occurred, a job was received with a job id '
                'that is not present on the master: {0}'.format(jid)
            )
            return False
        if os.path.exists(os.path.join(jid_dir, 'nocache')):
            return
        hn_dir = os.path.join(jid_dir, id_)
        if not os.path.isdir(hn_dir):
            os.makedirs(hn_dir)
        # Otherwise the minion has already returned this jid and it should
        # be dropped
        else:
            log.error(
                'An extra return was detected from minion {0}, please verify '
                'the minion, this could be a replay attack'.format(
                    id_
                )
            )
            return False

        self.serial.dump(
            ret,
            # Use atomic open here to avoid the file being read before it's
            # completely written to. Refs #1935
            salt.utils.atomicfile.atomic_open(
                os.path.join(hn_dir, 'return.p'), 'w+'
            )
        )

    def run(self):
        '''
        Execute the overall routine
        '''
        jid = salt.utils.prep_jid(
                self.opts['cachedir'],
                self.opts['hash_type'],
                self.opts['user'])
        if self.opts.get('verbose'):
            msg = 'Executing job with jid {0}'.format(jid)
            print(msg)
            print('-' * len(msg) + '\n')
            print('')
        for ret in self.handle_ssh():
            host = ret.keys()[0]
            #self.cache_job(jid, host, ret)
            ret = self.key_deploy(host, ret)
            salt.output.display_output(
                    ret,
                    self.opts.get('output', 'nested'),
                    self.opts)
            if self.event:
                self.event.fire_event(
                        ret,
                        salt.utils.event.tagify(
                            [jid, 'ret', host],
                            'job'))


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
            arg_str,
            id_,
            host,
            user=None,
            port=None,
            passwd=None,
            priv=None,
            timeout=None,
            sudo=False,
            tty=False,
            **kwargs):
        self.opts = opts
        self.arg_str = arg_str
        self.fun, self.arg = self.__arg_comps()
        self.id = id_

        args = {'host': host,
                'user': user,
                'port': port,
                'passwd': passwd,
                'priv': priv,
                'timeout': timeout,
                'sudo': sudo,
                'tty': tty}
        self.shell = salt.client.ssh.shell.Shell(opts, **args)
        self.minion_config = yaml.dump(
                {
                    'root_dir': '/tmp/.salt/running_data',
                    'id': self.id,
                }).strip()
        self.target = kwargs
        self.target.update(args)
        self.serial = salt.payload.Serial(opts)
        self.wfuncs = salt.loader.ssh_wrapper(opts)

    def __arg_comps(self):
        '''
        Return the function name and the arg list
        '''
        comps = self.arg_str.split()
        fun = comps[0] if comps else ''
        arg = comps[1:]
        return fun, arg

    def deploy(self):
        '''
        Deploy salt-thin
        '''
        thin = salt.utils.thin.gen_thin(self.opts['cachedir'])
        self.shell.send(
                thin,
                '/tmp/.salt/salt-thin.tgz')
        return True

    def run(self, deploy_attempted=False):
        '''
        Execute the routine, the routine can be either:
        1. Execute a raw shell command
        2. Execute a wrapper func
        3. Execute a remote Salt command

        If a (re)deploy is needed, then retry the operation after a deploy
        attempt

        Returns tuple of (stdout, stderr)
        '''
        stdout, stderr = None, None
        arg_str = self.arg_str

        if self.opts.get('raw_shell'):
            if not arg_str.startswith(('"', "'")) and not arg_str.endswith(('"', "'")):
                arg_str = "'{0}'".format(arg_str)
            stdout, stderr = self.shell.exec_cmd(arg_str)

        elif self.fun in self.wfuncs:
            stdout, stderr = self.run_wfunc()

        else:
            stdout, stderr = self.cmd_block()

        if stdout.startswith('deploy') and not deploy_attempted:
            self.deploy()
            return self.run(deploy_attempted=True)

        return stdout, stderr

    def run_wfunc(self):
        '''
        Execute a wrapper function

        Returns tuple of (json_data, '')
        '''
        # Ensure that opts/grains are up to date
        # Execute routine
        cdir = os.path.join(self.opts['cachedir'], 'minions', self.id)
        if not os.path.isdir(cdir):
            os.makedirs(cdir)
        datap = os.path.join(cdir, 'data.p')
        refresh = False
        if not os.path.isfile(datap):
            refresh = True
        else:
            passed_time = (time.time() - os.stat(datap).st_mtime) / 60
            if (passed_time > self.opts.get('cache_life', 60)):
                refresh = True
        if self.opts.get('refresh_cache'):
            refresh = True
        if refresh:
            # Make the datap
            # TODO: Auto expire the datap
            pre_wrapper = salt.client.ssh.wrapper.FunctionWrapper(
                self.opts,
                self.id,
                **self.target)
            opts_pkg = pre_wrapper['test.opts_pkg']()
            opts_pkg['file_roots'] = self.opts['file_roots']
            opts_pkg['pillar_roots'] = self.opts['pillar_roots']
            pillar = salt.pillar.Pillar(
                    opts_pkg,
                    opts_pkg['grains'],
                    opts_pkg['id'],
                    opts_pkg.get('environment', 'base')
                    )
            pillar_data = pillar.compile_pillar()

            # TODO: cache minion opts in datap in master.py
            with salt.utils.fopen(datap, 'w+') as fp_:
                fp_.write(
                        self.serial.dumps(
                            {'opts': opts_pkg,
                                'grains': opts_pkg['grains'],
                                'pillar': pillar_data}
                            )
                        )
        with salt.utils.fopen(datap, 'r') as fp_:
            data = self.serial.load(fp_)
        opts = data.get('opts', {})
        opts['grains'] = data.get('grains')
        opts['pillar'] = data.get('pillar')
        wrapper = salt.client.ssh.wrapper.FunctionWrapper(
            opts,
            self.id,
            **self.target)
        self.wfuncs = salt.loader.ssh_wrapper(opts, wrapper)
        wrapper.wfuncs = self.wfuncs
        ret = json.dumps(self.wfuncs[self.fun](*self.arg))
        return ret, ''

    def cmd(self):
        '''
        Prepare the pre-check command to send to the subsystem
        '''
        # 1. check if python is on the target
        # 2. check is salt-call is on the target
        # 3. deploy salt-thin
        # 4. execute command
        if self.arg_str.startswith('state.highstate'):
            self.highstate_seed()
        if self.arg_str.startswith('state.sls'):
            args, kwargs = salt.minion.parse_args_and_kwargs(
                    self.sls_seed, self.arg)
            self.sls_seed(*args, **kwargs)
        sudo = 'sudo' if self.target['sudo'] else ''
        thin_sum = salt.utils.thin.thin_sum(
                self.opts['cachedir'],
                self.opts['hash_type'])
        cmd = SSH_SHIM.format(
                sudo,
                self.arg_str,
                self.opts['hash_type'],
                thin_sum,
                self.minion_config)
        for stdout, stderr in self.shell.exec_nb_cmd(cmd):
            yield stdout, stderr

    def cmd_block(self, is_retry=False):
        '''
        Prepare the pre-check command to send to the subsystem
        '''
        # 1. check if python is on the target
        # 2. check is salt-call is on the target
        # 3. deploy salt-thin
        # 4. execute command
        if self.arg_str.startswith('cmd.run'):
            cmd_args = ' '.join(self.arg_str.split()[1:])
            if not cmd_args.startswith("'") and not cmd_args.endswith("'"):
                self.arg_str = "cmd.run '{0}'".format(cmd_args)
        sudo = 'sudo' if self.target['sudo'] else ''
        thin_sum = salt.utils.thin.thin_sum(
                self.opts['cachedir'],
                self.opts['hash_type'])
        cmd = SSH_SHIM.format(
                sudo,
                self.arg_str,
                self.opts['hash_type'],
                thin_sum,
                self.minion_config)
        log.debug("Performing shimmed command as follows:\n{0}".format(cmd))
        stdout, stderr = self.shell.exec_cmd(cmd)

        log.debug("STDOUT {1}\n{0}".format(stdout, self.target['host']))
        log.debug("STDERR {1}\n{0}".format(stderr, self.target['host']))

        error = self.categorize_shim_errors(stdout, stderr)
        if error:
            return "ERROR: {0}".format(error), stderr

        if RSTR in stdout:
            stdout = stdout.split(RSTR)[1].strip()
        if stdout.startswith('deploy'):
            self.deploy()
            stdout, stderr = self.shell.exec_cmd(cmd)
            if RSTR in stdout:
                stdout = stdout.split(RSTR)[1].strip()

        return stdout, stderr

    def categorize_shim_errors(self, stdout, stderr):
        perm_error_fmt = "Permissions problem, target user may need "\
                         "to be root or use sudo:\n {0}"
        if stderr.startswith('Permission denied'):
            return None
        errors = [
            ("sudo: no tty present and no askpass program specified",
                "sudo expected a password, NOPASSWD required"),
            ("Python too old",
                "salt requires python 2.6 or better on target hosts"),
            ("sudo: sorry, you must have a tty to run sudo",
                "sudo is configured with requiretty"),
            ("Failed to open log file",
                perm_error_fmt.format(stderr)),
            ("Permission denied:.*/salt",
                perm_error_fmt.format(stderr)),
            ("Failed to create directory path.*/salt",
                perm_error_fmt.format(stderr)),
            ]

        for error in errors:
            if re.search(error[0], stderr):
                return error[1]
        return None

    def sls_seed(self,
                 mods,
                 saltenv='base',
                 test=None,
                 exclude=None,
                 env=None,
                 **kwargs):
        '''
        Create the seed file for a state.sls run
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
        # Backwards compatibility
        saltenv = env

        wrapper = salt.client.ssh.wrapper.FunctionWrapper(
                self.opts,
                self.id,
                **self.target)
        minion_opts = copy.deepcopy(self.opts)
        minion_opts.update(wrapper['test.opts_pkg']())
        pillar = kwargs.get('pillar', {})
        st_ = SSHHighState(minion_opts, pillar, wrapper)
        if isinstance(mods, str):
            mods = mods.split(',')
        high, errors = st_.render_highstate({saltenv: mods})
        if exclude:
            if isinstance(exclude, str):
                exclude = exclude.split(',')
            if '__exclude__' in high:
                high['__exclude__'].extend(exclude)
            else:
                high['__exclude__'] = exclude
        high, ext_errors = st_.state.reconcile_extend(high)
        errors += ext_errors
        errors += st_.state.verify_high(high)
        if errors:
            return errors
        high, req_in_errors = st_.state.requisite_in(high)
        errors += req_in_errors
        high = st_.state.apply_exclude(high)
        # Verify that the high data is structurally sound
        if errors:
            return errors
        # Compile and verify the raw chunks
        chunks = st_.state.compile_high_data(high)
        file_refs = lowstate_file_refs(chunks)
        trans_tar = prep_trans_tar(self.opts, chunks, file_refs)
        self.shell.send(
                trans_tar,
                '/tmp/salt_state.tgz')
        self.arg_str = 'state.pkg /tmp/salt_state.tgz test={0}'.format(test)


class SSHState(salt.state.State):
    '''
    Create a State object which wraps the SSH functions for state operations
    '''
    def __init__(self, opts, pillar=None, wrapper=None):
        self.wrapper = wrapper
        super(SSHState, self).__init__(opts, pillar)

    def load_modules(self, data=None):
        '''
        Load up the modules for remote compilation via ssh
        '''
        self.functions = self.wrapper
        self.states = salt.loader.states(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)

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


class SSHHighState(salt.state.BaseHighState):
    '''
    Used to compile the highstate on the master
    '''
    stack = []

    def __init__(self, opts, pillar=None, wrapper=None):
        self.client = salt.fileclient.LocalClient(opts)
        salt.state.BaseHighState.__init__(self, opts)
        self.state = SSHState(opts, pillar, wrapper)
        self.matcher = salt.minion.Matcher(self.opts)


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


def prep_trans_tar(opts, chunks, file_refs):
    '''
    Generate the execution package from the env file refs and a low state
    data structure
    '''
    gendir = tempfile.mkdtemp()
    trans_tar = salt.utils.mkstemp()
    file_client = salt.fileclient.LocalClient(opts)
    lowfn = os.path.join(gendir, 'lowstate.json')
    with open(lowfn, 'w+') as fp_:
        fp_.write(json.dumps(chunks))
    for saltenv in file_refs:
        env_root = os.path.join(gendir, saltenv)
        if not os.path.isdir(env_root):
            os.makedirs(env_root)
        for ref in file_refs[saltenv]:
            for name in ref:
                short = name[7:]
                path = file_client.cache_file(name, saltenv)
                if path:
                    tgt = os.path.join(env_root, short)
                    tgt_dir = os.path.dirname(tgt)
                    if not os.path.isdir(tgt_dir):
                        os.makedirs(tgt_dir)
                    shutil.copy(path, tgt)
                    break
                files = file_client.cache_dir(name, saltenv, True)
                if files:
                    for filename in files:
                        tgt = os.path.join(
                                env_root,
                                short,
                                filename[filename.find(short) + len(short):],
                                )
                        tgt_dir = os.path.dirname(tgt)
                        if not os.path.isdir(tgt_dir):
                            os.makedirs(tgt_dir)
                        shutil.copy(path, tgt)
                    break
    cwd = os.getcwd()
    os.chdir(gendir)
    with tarfile.open(trans_tar, 'w:gz') as tfp:
        for root, dirs, files in os.walk(gendir):
            for name in files:
                full = os.path.join(root, name)
                tfp.add(full[len(gendir):].lstrip(os.sep))
    os.chdir(cwd)
    shutil.rmtree(gendir)
    return trans_tar
