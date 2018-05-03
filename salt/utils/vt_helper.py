# -*- coding: utf-8 -*-
'''
    salt.utils.vt_helper
    ~~~~~~~~~~~~~~~~~~~~

    VT Helper

    This module provides the SSHConnection to expose an SSH connection object
    allowing users to programmatically execute commands on a remote server using
    Salt VT.
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import os
import re

# Import salt's Libs
from .vt import Terminal, TerminalException

SSH_PASSWORD_PROMPT_RE = re.compile(r'(?:.*)[Pp]assword(?: for .*)?:', re.M)
KEY_VALID_RE = re.compile(r'.*\(yes\/no\).*')

log = logging.getLogger(__name__)


class SSHConnection(object):
    '''
    SSH Connection to a remote server.
    '''
    def __init__(self,
                 username='salt',
                 password='password',
                 host='localhost',
                 key_accept=False,
                 prompt=r'(Cmd)',
                 passwd_retries=3,
                 linesep=os.linesep,
                 ssh_args=''):
        '''
        Establishes a connection to the remote server.

        The format for parameters is:

        username (string): The username to use for this
            ssh connection. Defaults to root.
        password (string): The password to use for this
            ssh connection. Defaults to password.
        host (string): The host to connect to.
            Defaults to localhost.
        key_accept (boolean): Should we accept this host's key
            and add it to the known_hosts file? Defaults to False.
        prompt (string): The shell prompt (regex) on the server.
            Prompt is compiled into a regular expression.
            Defaults to (Cmd)
        passwd_retries (int): How many times should I try to send the password?
            Defaults to 3.
        linesep (string): The line separator to use when sending
            commands to the server. Defaults to os.linesep.
        ssh_args (string): Extra ssh args to use with ssh.
             Example: '-o PubkeyAuthentication=no'
        '''
        self.conn = Terminal(
            'ssh {0} -l {1} {2}'.format(ssh_args, username, host),
            shell=True,
            log_stdout=True,
            log_stdout_level='trace',
            log_stderr=True,
            log_stderr_level='trace',
            stream_stdout=False,
            stream_stderr=False)
        sent_passwd = 0

        self.prompt_re = re.compile(prompt)
        self.linesep = linesep

        while self.conn.has_unread_data:
            stdout, stderr = self.conn.recv()

            if stdout and SSH_PASSWORD_PROMPT_RE.search(stdout):
                if not password:
                    log.error('Failure while authentication.')
                    raise TerminalException(
                        'Permission denied, no authentication information')
                if sent_passwd < passwd_retries:
                    self.conn.sendline(password, self.linesep)
                    sent_passwd += 1
                    continue
                else:
                    # asking for a password, and we can't seem to send it
                    raise TerminalException('Password authentication failed')
            elif stdout and KEY_VALID_RE.search(stdout):
                # Connecting to this server for the first time
                # and need to accept key
                if key_accept:
                    log.info('Adding %s to known_hosts', host)
                    self.conn.sendline('yes')
                    continue
                else:
                    self.conn.sendline('no')
            elif stdout and self.prompt_re.search(stdout):
                # Auth success!
                # We now have a prompt
                break

    def sendline(self, cmd):
        '''
        Send this command to the server and
        return a tuple of the output and the stderr.

        The format for parameters is:

        cmd (string): The command to send to the sever.
        '''
        self.conn.sendline(cmd, self.linesep)

        # saw_prompt = False
        ret_stdout = []
        ret_stderr = []
        while self.conn.has_unread_data:
            stdout, stderr = self.conn.recv()

            if stdout:
                ret_stdout.append(stdout)
            if stderr:
                log.debug('Error while executing command.')
                ret_stderr.append(stderr)

            if stdout and self.prompt_re.search(stdout):
                break

        return ''.join(ret_stdout), ''.join(ret_stderr)

    def close_connection(self):
        '''
        Close the server connection
        '''
        self.conn.close(terminate=True, kill=True)
