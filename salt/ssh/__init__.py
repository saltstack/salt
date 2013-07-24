'''
Create ssh executor system
'''
# Import python libs
import os
import json
import getpass

# Import salt libs
import salt.ssh.shell
import salt.utils.thin
import salt.roster
import salt.state
import salt.loader


class SSH(object):
    '''
    Create an ssh execution system
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
            salt.ssh.shell.gen_key(priv)
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
        Return the keystring for the ssh public key
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
        Deploy the ssh key if the minions don't auth
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
            single.cmd()
            target.pop('passwd')
            single = Single(
                    self.opts,
                    self.opts['arg_str'],
                    host,
                    **target)
            return single.cmd()
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

                single = Single(
                        self.opts,
                        self.opts['arg_str'],
                        host,
                        **self.targets[host])
                running[host] = {'iter': single.cmd(),
                                 'single': single}
            for host in running:
                stdout, stderr = next(running[host]['iter'])
                if stdout == 'deploy':
                    running[host]['single'].deploy()
                    running[host]['iter'] = single.cmd()
                elif stdout is None and stderr is None:
                    continue
                else:
                    # This job is done, yield
                    try:
                        if not stdout and stderr:
                            yield {running[host]['single'].id: stderr}
                        else:
                            data = json.dumps(stdout)
                            if 'local' in data:
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

    def run(self):
        '''
        Execute the overall routine
        '''
        for ret in self.process():
            host = ret.keys()[0]
            ret = self.key_deploy(host, ret)
            salt.output.display_output(
                    ret,
                    self.opts.get('output', 'nested'),
                    self.opts)


class Single():
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
        self.id = id_
        self.extra = kwargs
        self.shell = salt.ssh.shell.Shell(
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

    def deploy(self):
        '''
        Deploy salt-thin
        '''
        thin = salt.utils.thin.gen_thin(self.opts['cachedir'])
        self.shell.send(
                thin,
                '/tmp/salt-thin.tgz')
        self.shell.exec_cmd(
                'tar xvf /tmp/salt-thin.tgz -C /tmp && rm /tmp/salt-thin.tgz'
                )
        return True

    def cmd(self):
        '''
        Prepare the precheck command to send to the subsystem
        '''
        # 1. check if python is on the target
        # 2. check is salt-call is on the target
        # 3. deploy salt-thin
        # 4. execute command
        cmd = (' << "EOF"\n'
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
               'elif [ -f /tmp/salt-call ] \n'
               'then\n'
               '    SALT=/tmp/salt-call\n'
               'else\n'
               '    echo "deploy"\n'
               '    exit 1\n'
               'fi\n'
               '$PYTHON $SALT --local --out json -l quiet {0}\n'
               'EOF').format(self.arg_str)
        if self.arg_str.startswith('state.highstate'):
            self.highstate_seed()
        for stdout, stderr in self.shell.exec_nb_cmd(cmd):
            if stdout is None and stderr is None:
                yield None, None
            else:
                yield stdout, stderr

    def highstate_seed(self):
        '''
        Generate an archive file which contains the instructions and files
        to execute a state run on a remote system
        '''
        wrapper = FunctionWrapper(self.opts, self.target['id'], **self.target)
        st_ = SSHHighState(self.opts, None, wrapper)
        lowstate = st_.compile_low_chunks()
        #file_refs = salt.utils.lowstate_file_refs(lowstate)


class FunctionWrapper(dict):
    '''
    Create an object that acts like the salt function dict and makes function
    calls remotely via the ssh shell system
    '''
    def __init__(
            self,
            opts,
            id_,
            host,
            **kwargs):
        super(FunctionWrapper, self).__init__()
        self.opts = opts
        self.kwargs = {'id_': id_,
                       'host': host}
        self.kwargs.update(kwargs)

    def __getitem__(self, cmd):
        '''
        Return the function call to simulate the salt local lookup system
        '''
        def caller(args, kwargs):
            '''
            The remote execution function
            '''
            arg_str = '{0} '.format(cmd)
            for arg in args:
                arg_str += '{0} '.format(arg)
            for key, val in kwargs.items():
                arg_str += '{0}={1} '.format(key, val)
            single = Single(self.opts, arg_str, **kwargs)
            ret = single.cmd()
            return ret[single.id]
        return caller


class SSHState(salt.state.State):
    '''
    Create a State object which wraps the ssh functions for state operations
    '''
    def __init__(self, opts, pillar=None, wrapper=None):
        opts['grains'] = wrapper['grains.items']()
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
