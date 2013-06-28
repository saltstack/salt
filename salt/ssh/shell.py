'''
Manage transport commands via ssh
'''

# Import python libs
import time
import subprocess

# Import salt libs
import salt.utils
import salt.utils.nb_popen


class Shell(object):
    '''
    Create a shell connection object to encapsulate sssh executions
    '''
    def __init__(
            self,
            cmd,
            host,
            user=None,
            port=None,
            passwd=None,
            priv=None,
            timeout=None,
            sudo=False,
            tty=False):
        self.cmd = cmd
        self.host = host
        self.user = user
        self.port = port
        self.passwd = passwd
        self.priv = priv
        self.timeout = timeout
        self.sudo = sudo
        self.tty = tty

    def _key_opts(self):
        '''
        Return options for the ssh command base for Salt to call
        '''
        options = ['ControlMaster=auto',
                   'ControlPersist=60s',
                   'StrictHostKeyChecking=no',
                   'KbdInteractiveAuthentication=no',
                   'GSSAPIAuthentication=no',
                   'PasswordAuthentication=no',
                   ]
        options.append('ConnectTimeout={0}'.format(self.timeout))
        if self.port:
            options.append('Port={0}'.format(self.port))
        if self.priv:
            options.append('IdentityFile={0}'.format(self.priv))
        if self.user:
            options.append('User={0}'.format(self.user))

        return options

    def _passwd_opts(self):
        '''
        Return options to pass to sshpass
        '''
        options = ['ControlMaster=auto',
                   'ControlPersist=60s',
                   'StrictHostKeyChecking=no',
                   'GSSAPIAuthentication=no',
                   ]
        options.append('ConnectTimeout={0}'.format(self.timeout))
        if self.port:
            options.append('Port={0}'.format(self.port))
        if self.user:
            options.append('User={0}'.format(self.user))

        return options


    def _cmd_str(self, cmd, ssh='ssh'):
        '''
        Return the cmd string to execute
        '''
        if self.priv:
            opts = self._key_opts(
                    self.user,
                    self.port,
                    self.priv,
                    self.timeout)
            return '{0} {1} {2} -o {3} -c {4}'.format(
                    ssh,
                    self.host,
                    '-t -t' if self.tty else '',
                    ','.join(opts),
                    cmd)
        elif self.passwd:
            if not salt.utils.which('sshpass'):
                return None
            opts = self._key_opts(
                    self.user,
                    self.port,
                    self.priv,
                    self.timeout)
            return 'sshpass -p {0} {1} {2} {3} -o {4} -c {5}'.format(
                    self.passwd,
                    ssh,
                    self.host,
                    '-t -t' if self.tty else '',
                    ','.join(opts),
                    cmd)
        return None


    def _run_cmd(self, cmd):
        '''
        Cleanly execute the command string
        '''
        try:
            proc = salt.utils.nb_open.NonBlockingPopen(
                cmd,
                shell=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            while proc.poll() is None:
                time.sleep(0.25)

            data = proc.communicate()
            return data[0]
        except Exception:
            pass
        # Signal an error
        return ()


    def exec_cmd(self, cmd):
        '''
        Execute a remote command
        '''
        if self.sudo:
            cmd = 'sudo {0}'.format(cmd)
            tty = True
        else:
            tty = False
        cmd = self._cmd_str(cmd, tty=tty)
        return self._run_cmd(cmd)


    def send(self, local, remote):
        '''
        scp a file or files to a remote system
        '''
        cmd = '{0} {1}:{2}'.format(local, self.host, remote)
        if self.sudo:
            cmd = 'sudo {0}'.format(cmd)
            tty = True
        else:
            tty = False
        cmd = self._cmd_str(cmd, ssh='scp', tty=tty)
        return self._run_cmd(cmd)
