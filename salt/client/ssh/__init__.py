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

# Import salt libs
import salt.client.ssh.shell
import salt.client.ssh.wrapper
import salt.utils
import salt.utils.thin
import salt.roster
import salt.state
import salt.loader
import salt.minion

HEREDOC = (' << "EOF"\n'
           'if [ `type -p python2` ]\n'
           'then\n'
           '    PYTHON=python2\n'
           'elif [ `type -p python26` ]\n'
            'then\n'
           '    PYTHON=python26\n'
           'elif [ `type -p python27` ]\n'
           'then\n'
           '    PYTHON=python27\n'
           'fi\n'
           'if hash salt-call\n'
           'then\n'
           '    SALT=$(type -p salt-call)\n'
           'elif [ -f /tmp/.salt/salt-call ] \n'
           'then\n'
           '    if [[ $(cat /tmp/.salt/version) != {0} ]]\n'
           '    then\n'
           '        rm -rf /tmp/.salt\n'
           '        mkdir -p /tmp/.salt\n'
           '        echo "deploy"\n'
           '        exit 1\n'
           '    fi\n'
           '    SALT=/tmp/.salt/salt-call\n'
           'else\n'
           '    mkdir -p /tmp/.salt\n'
           '    echo "deploy"\n'
           '    exit 1\n'
           'fi\n'
           '$PYTHON $SALT --local --out json -l quiet {{0}}\n'
           'EOF').format(salt.__version__)


class SSH(object):
    '''
    Create an SSH execution system
    '''
    def __init__(self, opts):
        self.opts = opts
        tgt_type = self.opts['selected_target_option'] if self.opts['selected_target_option'] else 'glob'
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

    def get_pubkey(self):
        '''
        Return the keystring for the SSH public key
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
            return ret
        if ret[host].startswith('Permission denied'):
            target = self.targets[host]
            # permission denied, attempt to auto deploy ssh key
            print(('Permission denied for host {0}, do you want to '
                    'deploy the salt-ssh key?').format(host))
            deploy = raw_input('[Y/n]')
            if deploy.startswith(('n', 'N')):
                return ret
            target['passwd'] = getpass.getpass(
                    'Password for {0}:'.format(host)
                    )
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
                ret = single.cmd_block()
                if ret[0].startswith('deploy'):
                    single.deploy()
                    ret = single.cmd_block()
            target.pop('passwd')
            single = Single(
                    self.opts,
                    self.opts['arg_str'],
                    host,
                    **target)
            stdout, stderr = single.cmd_block()
            try:
                data = json.loads(stdout)
                if 'local' in data:
                    return {host: data['local']}
                else:
                    return {host: data}
            except Exception:
                return {host: 'Bad Return'}
        return ret

    def process(self):
        '''
        Execute the desired routine on the specified systems
        '''
        running = {}
        target_iter = self.targets.__iter__()
        done = set()
        while True:
            if len(running) < self.opts.get('ssh_max_procs', 5):
                try:
                    host = next(target_iter)
                except StopIteration:
                    pass
                for default in self.defaults:
                    if not default in self.targets[host]:
                        self.targets[host][default] = self.defaults[default]

                if host not in running:
                    single = Single(
                            self.opts,
                            self.opts['arg_str'],
                            host,
                            **self.targets[host])
                    running[host] = {'iter': single.cmd(),
                                     'single': single}
            for host in running:
                stdout, stderr = next(running[host]['iter'])
                if stdout is None and stderr is None:
                    continue
                if stdout.startswith('deploy'):
                    running[host]['single'].deploy()
                    running[host]['iter'] = single.cmd()
                else:
                    # This job is done, yield
                    try:
                        if not stdout and stderr:
                            yield {running[host]['single'].id: stderr}
                        else:
                            data = json.loads(stdout)
                            if len(data) < 2 and 'local' in data:
                                yield {running[host]['single'].id: data['local']}
                            else:
                                yield {running[host]['single'].id: data}
                    except Exception:
                        yield {running[host]['single'].id: 'Bad Return'}
                    done.add(host)
            for host in done:
                if host in running:
                    running.pop(host)
            if len(done) >= len(self.targets):
                break

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
                data = json.loads(stdout)
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
        rouintes
        '''
        que = multiprocessing.Queue()
        running = {}
        target_iter = self.targets.__iter__()
        rets = set()
        init = False
        while True:
            if len(running) < self.opts.get('ssh_max_procs', 5) and not init:
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
                routine = multiprocessing.Process(target=self.handle_routine, args=args)
                routine.start()
                running[host] = {'thread': routine}
                continue
            ret = {}
            try:
                ret = que.get(False)
            except Exception:
                pass
            for host in running:
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

    def run(self):
        '''
        Execute the overall routine
        '''
        for ret in self.handle_ssh():
            host = ret.keys()[0]
            ret = self.key_deploy(host, ret)
            salt.output.display_output(
                    ret,
                    self.opts.get('output', 'nested'),
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
            arg_str,
            id_,
            host,
            user=None,
            port=None,
            passwd=None,
            priv=None,
            timeout=None,
            sudo=False,
            **kwargs):
        self.opts = opts
        self.arg_str = arg_str
        self.fun, self.arg = self.__arg_comps()
        self.id = id_
        self.extra = kwargs
        self.shell = salt.client.ssh.shell.Shell(
                host,
                user,
                port,
                passwd,
                priv,
                timeout,
                sudo)
        self.target = self.extra
        self.target['host'] = host
        self.target['user'] = user
        self.target['port'] = port
        self.target['passwd'] = passwd
        self.target['priv'] = priv
        self.target['timeout'] = timeout
        self.target['sudo'] = sudo
        self.serial = salt.payload.Serial(opts)
        self.wfuncs = salt.loader.ssh_wrapper(opts)

    def __arg_comps(self):
        '''
        Return the function name and the arg list
        '''
        fun = ''
        arg = []
        comps = self.arg_str.split()
        if len(comps) > 0:
            fun = comps[0]
        if len(comps) > 1:
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
        self.shell.exec_cmd(
                'tar xvf /tmp/.salt/salt-thin.tgz -C /tmp/.salt && rm /tmp/.salt/salt-thin.tgz'
                )
        return True

    def run(self):
        '''
        Execute the routine, the routine can be either:
        1. Execute a remote Salt command
        2. Execute a raw shell command
        3. Execute a wrapper func
        '''
        if self.opts.get('raw_shell'):
            return self.shell.exec_cmd(self.arg_str)
        elif self.fun in self.wfuncs:
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
                if ((time.time() - os.stat(datap).st_mtime) / 60 > self.opts.get('cache_life', 60)):
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
        else:
            return self.cmd_block()

    def cmd(self):
        '''
        Prepare the precheck command to send to the subsystem
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
        cmd = HEREDOC.format(self.arg_str)
        for stdout, stderr in self.shell.exec_nb_cmd(cmd):
            if stdout is None and stderr is None:
                yield None, None
            else:
                yield stdout, stderr

    def cmd_block(self):
        '''
        Prepare the precheck command to send to the subsystem
        '''
        # 1. check if python is on the target
        # 2. check is salt-call is on the target
        # 3. deploy salt-thin
        # 4. execute command
        cmd = HEREDOC.format(self.arg_str)
        stdout, stderr = self.shell.exec_cmd(cmd)
        if stdout.startswith('deploy'):
            self.deploy()
            stdout, stderr = self.shell.exec_cmd(cmd)
        return stdout, stderr

    def sls_seed(self, mods, env='base', test=None, exclude=None, **kwargs):
        '''
        Create the seed file for a state.sls run
        '''
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
        high, errors = st_.render_highstate({env: mods})
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
        env = 'base'
        crefs = []
        for state in chunk:
            if state == '__env__':
                env = chunk[state]
            elif state.startswith('__'):
                continue
            crefs.extend(salt_refs(chunk[state]))
        if crefs:
            if not env in refs:
                refs[env] = []
            refs[env].append(crefs)
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
    for env in file_refs:
        env_root = os.path.join(gendir, env)
        if not os.path.isdir(env_root):
            os.makedirs(env_root)
        for ref in file_refs[env]:
            for name in ref:
                short = name[7:]
                path = file_client.cache_file(name, env)
                if path:
                    tgt = os.path.join(env_root, short)
                    tgt_dir = os.path.dirname(tgt)
                    if not os.path.isdir(tgt_dir):
                        os.makedirs(tgt_dir)
                    shutil.copy(path, tgt)
                    break
                files = file_client.cache_dir(name, env, True)
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
