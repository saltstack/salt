# -*- coding: utf-8 -*-
'''
Manage transport commands via ssh
'''
from __future__ import absolute_import

# Import python libs
import re
import os
import sys
import json
import time
import logging
import subprocess

# Import salt libs
import salt.defaults.exitcodes
import salt.utils.nb_popen
import salt.utils.vt

log = logging.getLogger(__name__)

SSH_PASSWORD_PROMPT_RE = re.compile(r'(?:.*)[Pp]assword(?: for .*)?:', re.M)  # future lint: disable=non-unicode-string
KEY_VALID_RE = re.compile(r'.*\(yes\/no\).*')  # future lint: disable=non-unicode-string

# Keep these in sync with ./__init__.py
RSTR = u'_edbc7885e4f9aac9b83b35999b68d015148caf467b78fa39c05f669c0ff89878'
RSTR_RE = re.compile(r'(?:^|\r?\n)' + RSTR + r'(?:\r?\n|$)')  # future lint: disable=non-unicode-string


class NoPasswdError(Exception):
    pass


class KeyAcceptError(Exception):
    pass


def gen_key(path):
    '''
    Generate a key for use with salt-ssh
    '''
    cmd = u'ssh-keygen -P "" -f {0} -t rsa -q'.format(path)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    subprocess.call(cmd, shell=True)


def gen_shell(opts, **kwargs):
    '''
    Return the correct shell interface for the target system
    '''
    if kwargs[u'winrm']:
        try:
            import saltwinshell
            shell = saltwinshell.Shell(opts, **kwargs)
        except ImportError:
            log.error(u'The saltwinshell library is not available')
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
    else:
        shell = Shell(opts, **kwargs)
    return shell


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
            tty=False,
            mods=None,
            identities_only=False,
            sudo_user=None,
            remote_port_forwards=None,
            winrm=False,
            ssh_options=None):
        self.opts = opts
        # ssh <ipv6>, but scp [<ipv6]:/path
        self.host = host.strip(u'[]')
        self.user = user
        self.port = port
        self.passwd = str(passwd) if passwd else passwd
        self.priv = priv
        self.timeout = timeout
        self.sudo = sudo
        self.tty = tty
        self.mods = mods
        self.identities_only = identities_only
        self.remote_port_forwards = remote_port_forwards
        self.ssh_options = u'' if ssh_options is None else ssh_options

    def get_error(self, errstr):
        '''
        Parse out an error and return a targeted error string
        '''
        for line in errstr.split(u'\n'):
            if line.startswith(u'ssh:'):
                return line
            if line.startswith(u'Pseudo-terminal'):
                continue
            if u'to the list of known hosts.' in line:
                continue
            return line
        return errstr

    def _key_opts(self):
        '''
        Return options for the ssh command base for Salt to call
        '''
        options = [
                   u'KbdInteractiveAuthentication=no',
                   ]
        if self.passwd:
            options.append(u'PasswordAuthentication=yes')
        else:
            options.append(u'PasswordAuthentication=no')
        if self.opts.get(u'_ssh_version', (0,)) > (4, 9):
            options.append(u'GSSAPIAuthentication=no')
        options.append(u'ConnectTimeout={0}'.format(self.timeout))
        if self.opts.get(u'ignore_host_keys'):
            options.append(u'StrictHostKeyChecking=no')
        if self.opts.get(u'no_host_keys'):
            options.extend([u'StrictHostKeyChecking=no',
                            u'UserKnownHostsFile=/dev/null'])
        known_hosts = self.opts.get(u'known_hosts_file')
        if known_hosts and os.path.isfile(known_hosts):
            options.append(u'UserKnownHostsFile={0}'.format(known_hosts))
        if self.port:
            options.append(u'Port={0}'.format(self.port))
        if self.priv:
            options.append(u'IdentityFile={0}'.format(self.priv))
        if self.user:
            options.append(u'User={0}'.format(self.user))
        if self.identities_only:
            options.append(u'IdentitiesOnly=yes')

        ret = []
        for option in options:
            ret.append(u'-o {0} '.format(option))
        return u''.join(ret)

    def _passwd_opts(self):
        '''
        Return options to pass to ssh
        '''
        # TODO ControlMaster does not work without ControlPath
        # user could take advantage of it if they set ControlPath in their
        # ssh config.  Also, ControlPersist not widely available.
        options = [u'ControlMaster=auto',
                   u'StrictHostKeyChecking=no',
                   ]
        if self.opts[u'_ssh_version'] > (4, 9):
            options.append(u'GSSAPIAuthentication=no')
        options.append(u'ConnectTimeout={0}'.format(self.timeout))
        if self.opts.get(u'ignore_host_keys'):
            options.append(u'StrictHostKeyChecking=no')
        if self.opts.get(u'no_host_keys'):
            options.extend([u'StrictHostKeyChecking=no',
                            u'UserKnownHostsFile=/dev/null'])

        if self.passwd:
            options.extend([u'PasswordAuthentication=yes',
                            u'PubkeyAuthentication=yes'])
        else:
            options.extend([u'PasswordAuthentication=no',
                            u'PubkeyAuthentication=yes',
                            u'KbdInteractiveAuthentication=no',
                            u'ChallengeResponseAuthentication=no',
                            u'BatchMode=yes'])
        if self.port:
            options.append(u'Port={0}'.format(self.port))
        if self.user:
            options.append(u'User={0}'.format(self.user))
        if self.identities_only:
            options.append(u'IdentitiesOnly=yes')

        ret = []
        for option in options:
            ret.append(u'-o {0} '.format(option))
        return u''.join(ret)

    def _ssh_opts(self):
        return u' '.join([u'-o {0}'.format(opt)
                          for opt in self.ssh_options])

    def _copy_id_str_old(self):
        '''
        Return the string to execute ssh-copy-id
        '''
        if self.passwd:
            # Using single quotes prevents shell expansion and
            # passwords containing '$'
            return u"{0} {1} '{2} -p {3} {4} {5}@{6}'".format(
                    u'ssh-copy-id',
                    u'-i {0}.pub'.format(self.priv),
                    self._passwd_opts(),
                    self.port,
                    self._ssh_opts(),
                    self.user,
                    self.host)
        return None

    def _copy_id_str_new(self):
        '''
        Since newer ssh-copy-id commands ingest option differently we need to
        have two commands
        '''
        if self.passwd:
            # Using single quotes prevents shell expansion and
            # passwords containing '$'
            return u"{0} {1} {2} -p {3} {4} {5}@{6}".format(
                    u'ssh-copy-id',
                    u'-i {0}.pub'.format(self.priv),
                    self._passwd_opts(),
                    self.port,
                    self._ssh_opts(),
                    self.user,
                    self.host)
        return None

    def copy_id(self):
        '''
        Execute ssh-copy-id to plant the id file on the target
        '''
        stdout, stderr, retcode = self._run_cmd(self._copy_id_str_old())
        if salt.defaults.exitcodes.EX_OK != retcode and u'Usage' in stderr:
            stdout, stderr, retcode = self._run_cmd(self._copy_id_str_new())
        return stdout, stderr, retcode

    def _cmd_str(self, cmd, ssh=u'ssh'):
        '''
        Return the cmd string to execute
        '''

        # TODO: if tty, then our SSH_SHIM cannot be supplied from STDIN Will
        # need to deliver the SHIM to the remote host and execute it there

        command = [ssh]
        if ssh != u'scp':
            command.append(self.host)
        if self.tty and ssh == u'ssh':
            command.append(u'-t -t')
        if self.passwd or self.priv:
            command.append(self.priv and self._key_opts() or self._passwd_opts())
        if ssh != u'scp' and self.remote_port_forwards:
            command.append(u' '.join([u'-R {0}'.format(item)
                                      for item in self.remote_port_forwards.split(u',')]))
        if self.ssh_options:
            command.append(self._ssh_opts())

        command.append(cmd)

        return u' '.join(command)

    def _old_run_cmd(self, cmd):
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
            return data[0], data[1], proc.returncode
        except Exception:
            return (u'local', u'Unknown Error', None)

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
                rcode = proc.returncode
                if out is None and err is None:
                    break
                if err:
                    err = self.get_error(err)
                yield out, err, rcode
        except Exception:
            yield (u'', u'Unknown Error', None)

    def exec_nb_cmd(self, cmd):
        '''
        Yield None until cmd finished
        '''
        r_out = []
        r_err = []
        rcode = None
        cmd = self._cmd_str(cmd)

        logmsg = u'Executing non-blocking command: {0}'.format(cmd)
        if self.passwd:
            logmsg = logmsg.replace(self.passwd, (u'*' * 6))
        log.debug(logmsg)

        for out, err, rcode in self._run_nb_cmd(cmd):
            if out is not None:
                r_out.append(out)
            if err is not None:
                r_err.append(err)
            yield None, None, None
        yield u''.join(r_out), u''.join(r_err), rcode

    def exec_cmd(self, cmd):
        '''
        Execute a remote command
        '''
        cmd = self._cmd_str(cmd)

        logmsg = u'Executing command: {0}'.format(cmd)
        if self.passwd:
            logmsg = logmsg.replace(self.passwd, (u'*' * 6))
        if u'decode("base64")' in logmsg or u'base64.b64decode(' in logmsg:
            log.debug(u'Executed SHIM command. Command logged to TRACE')
            log.trace(logmsg)
        else:
            log.debug(logmsg)

        ret = self._run_cmd(cmd)
        return ret

    def send(self, local, remote, makedirs=False):
        '''
        scp a file or files to a remote system
        '''
        if makedirs:
            self.exec_cmd(u'mkdir -p {0}'.format(os.path.dirname(remote)))

        # scp needs [<ipv6}
        host = self.host
        if u':' in host:
            host = u'[{0}]'.format(host)

        cmd = u'{0} {1}:{2}'.format(local, host, remote)
        cmd = self._cmd_str(cmd, ssh=u'scp')

        logmsg = u'Executing command: {0}'.format(cmd)
        if self.passwd:
            logmsg = logmsg.replace(self.passwd, (u'*' * 6))
        log.debug(logmsg)

        return self._run_cmd(cmd)

    def _run_cmd(self, cmd, key_accept=False, passwd_retries=3):
        '''
        Execute a shell command via VT. This is blocking and assumes that ssh
        is being run
        '''
        term = salt.utils.vt.Terminal(
                cmd,
                shell=True,
                log_stdout=True,
                log_stdout_level=u'trace',
                log_stderr=True,
                log_stderr_level=u'trace',
                stream_stdout=False,
                stream_stderr=False)
        sent_passwd = 0
        send_password = True
        ret_stdout = u''
        ret_stderr = u''
        old_stdout = u''

        try:
            while term.has_unread_data:
                stdout, stderr = term.recv()
                if stdout:
                    ret_stdout += stdout
                    buff = old_stdout + stdout
                else:
                    buff = stdout
                if stderr:
                    ret_stderr += stderr
                if buff and RSTR_RE.search(buff):
                    # We're getting results back, don't try to send passwords
                    send_password = False
                if buff and SSH_PASSWORD_PROMPT_RE.search(buff) and send_password:
                    if not self.passwd:
                        return u'', u'Permission denied, no authentication information', 254
                    if sent_passwd < passwd_retries:
                        term.sendline(self.passwd)
                        sent_passwd += 1
                        continue
                    else:
                        # asking for a password, and we can't seem to send it
                        return u'', u'Password authentication failed', 254
                elif buff and KEY_VALID_RE.search(buff):
                    if key_accept:
                        term.sendline(u'yes')
                        continue
                    else:
                        term.sendline(u'no')
                        ret_stdout = (u'The host key needs to be accepted, to '
                                      u'auto accept run salt-ssh with the -i '
                                      u'flag:\n{0}').format(stdout)
                        return ret_stdout, u'', 254
                elif buff and buff.endswith(u'_||ext_mods||_'):
                    mods_raw = json.dumps(self.mods, separators=(u',', u':')) + u'|_E|0|'
                    term.sendline(mods_raw)
                if stdout:
                    old_stdout = stdout
                time.sleep(0.01)
            return ret_stdout, ret_stderr, term.exitstatus
        finally:
            term.close(terminate=True, kill=True)
