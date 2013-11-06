# -*- coding: utf-8 -*-
'''
Manage transport commands via ssh
'''

# Import python libs
import os
import time
import subprocess

# Import salt libs
import salt.utils
import salt.utils.nb_popen


def gen_key(path):
    '''
    Generate a key for use with salt-ssh
    '''
    cmd = 'ssh-keygen -P "" -f {0} -t rsa -q'.format(path)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    subprocess.call(cmd, shell=True)


class Shell(object):
    '''
    Create a shell connection object to encapsulate ssh executions
    '''
    def __init__(
            self,
            opts,
            host,
            user=None,
            port=None,
            passwd=None,
            priv=None,
            timeout=None,
            sudo=False,
            tty=False):
        self.opts = opts
        self.host = host
        self.user = user
        self.port = port
        self.passwd = passwd
        self.priv = priv
        self.timeout = timeout
        self.sudo = sudo
        self.tty = tty

    def get_error(self, errstr):
        '''
        Parse out an error and return a targetted error string
        '''
        for line in errstr.split('\n'):
            if line.startswith('ssh:'):
                return line
            if line.startswith('Pseudo-terminal'):
                continue
            if 'to the list of known hosts.' in line:
                continue
            return line
        return errstr

    def _key_opts(self):
        '''
        Return options for the ssh command base for Salt to call
        '''
        options = [
                   'KbdInteractiveAuthentication=no',
                   'GSSAPIAuthentication=no',
                   'PasswordAuthentication=no',
                   ]
        options.append('ConnectTimeout={0}'.format(self.timeout))
        if self.opts.get('ignore_host_keys'):
            options.append('StrictHostKeyChecking=no')
        if self.port:
            options.append('Port={0}'.format(self.port))
        if self.priv:
            options.append('IdentityFile={0}'.format(self.priv))
        if self.user:
            options.append('User={0}'.format(self.user))

        ret = []
        for option in options:
            ret.append('-o {0} '.format(option))
        return ''.join(ret)

    def _passwd_opts(self):
        '''
        Return options to pass to sshpass
        '''
        # TODO ControlMaster does not work without ControlPath
        # user could take advange of it if they set ControlPath in thier
        # ssh config.  Also, ControlPersist not widely available.
        options = ['ControlMaster=auto',
                   'StrictHostKeyChecking=no',
                   'GSSAPIAuthentication=no',
                   ]
        options.append('ConnectTimeout={0}'.format(self.timeout))
        if self.opts.get('ignore_host_keys'):
            options.append('StrictHostKeyChecking=no')

        if self.passwd:
            options.extend(['PasswordAuthentication=yes',
                            'PubkeyAuthentication=no'])
        else:
            options.extend(['PasswordAuthentication=no',
                            'PubkeyAuthentication=yes',
                            'KbdInteractiveAuthentication=no',
                            'ChallengeResponseAuthentication=no',
                            'BatchMode=yes'])
        if self.port:
            options.append('Port={0}'.format(self.port))
        if self.user:
            options.append('User={0}'.format(self.user))

        ret = []
        for option in options:
            ret.append('-o {0} '.format(option))
        return ''.join(ret)

    def _copy_id_str_old(self):
        '''
        Return the string to execute ssh-copy-id
        '''
        if self.passwd and salt.utils.which('sshpass'):
            return "sshpass -p '{0}' {1} {2} '{3} -p {4} {5}@{6}'".format(
                    self.passwd,
                    'ssh-copy-id',
                    '-i {0}.pub'.format(self.priv),
                    self._passwd_opts(),
                    self.port,
                    self.user,
                    self.host)
        return None

    def _copy_id_str_new(self):
        '''
        Since newer ssh-copy-id commands ingest option differently we need to
        have two commands
        '''
        if self.passwd and salt.utils.which('sshpass'):
            return "sshpass -p '{0}' {1} {2} {3} -p {4} {5}@{6}".format(
                    self.passwd,
                    'ssh-copy-id',
                    '-i {0}.pub'.format(self.priv),
                    self._passwd_opts(),
                    self.port,
                    self.user,
                    self.host)
        return None

    def copy_id(self):
        '''
        Execute ssh-copy-id to plant the id file on the target
        '''
        stdout, stderr = self._run_cmd(self._copy_id_str_old())
        if stderr.startswith('Usage'):
            self._run_cmd(self._copy_id_str_new())

    def _cmd_str(self, cmd, ssh='ssh'):
        '''
        Return the cmd string to execute
        '''

        # TODO: if tty, then our SSH_SHIM cannot be supplied from STDIN Will
        # need to deliver the SHIM to the remote host and execute it there

        if self.passwd and salt.utils.which('sshpass'):
            opts = self._passwd_opts()
            return "sshpass -p '{0}' {1} {2} {3} {4} {5}".format(
                    self.passwd,
                    ssh,
                    '' if ssh == 'scp' else self.host,
                    '-t -t' if self.tty else '',
                    opts,
                    cmd)
        if self.priv:
            opts = self._key_opts()
            return "{0} {1} {2} {3} {4}".format(
                    ssh,
                    '' if ssh == 'scp' else self.host,
                    '-t -t' if self.tty else '',
                    opts,
                    cmd)
        return None

    def _run_cmd(self, cmd):
        '''
        Cleanly execute the command string
        '''
        try:
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )

            data = proc.communicate()
            return data
        except Exception:
            return ('local', 'Unknown Error')

    def _run_nb_cmd(self, cmd):
        '''
        cmd iterator
        '''
        try:
            proc = salt.utils.nb_popen.NonBlockingPopen(
                cmd,
                shell=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            while True:
                time.sleep(0.1)
                out = proc.recv()
                err = proc.recv_err()
                if out is None and err is None:
                    break
                if err:
                    err = self.get_error(err)
                yield out, err
        except Exception:
            yield ('', 'Unknown Error')

    def exec_nb_cmd(self, cmd):
        '''
        Yield None until cmd finished
        '''
        r_out = []
        r_err = []
        cmd = self._cmd_str(cmd)
        for out, err in self._run_nb_cmd(cmd):
            if out is not None:
                r_out.append(out)
            if err is not None:
                r_err.append(err)
            yield None, None
        yield ''.join(r_out), ''.join(r_err)

    def exec_cmd(self, cmd):
        '''
        Execute a remote command
        '''
        cmd = self._cmd_str(cmd)
        ret = self._run_cmd(cmd)
        return ret

    def send(self, local, remote):
        '''
        scp a file or files to a remote system
        '''
        cmd = '{0} {1}:{2}'.format(local, self.host, remote)
        cmd = self._cmd_str(cmd, ssh='scp')
        return self._run_cmd(cmd)
