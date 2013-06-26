'''
Manage transport commands via ssh
'''

# Import python libs
import os
import subprocess

# Import salt libs
import salt.utils


def _key_opts(user=None, port=None, priv=None, timeout=None):
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
    options.append('ConnectTimeout={0}'.format(timeout if timeout else 5))
    if port:
        options.append('Port={0}'.format(port))
    if priv:
        options.append('IdentityFile={0}'.format(priv))
    if user:
        options.append('User={0}'.format(user))

    return options


def _passwd_opts(user=None, port=None, passwd=None, timeout=None):
    '''
    Return options to pass to sshpass
    '''
    options = ['ControlMaster=auto',
               'ControlPersist=60s',
               'StrictHostKeyChecking=no',
               'GSSAPIAuthentication=no',
               ]
    options.append('ConnectTimeout={0}'.format(timeout if timeout else 5))
    if port:
        options.append('Port={0}'.format(port))
    if user:
        options.append('User={0}'.format(user))

    return options


def _cmd_str(
        cmd,
        ssh='ssh',
        user=None,
        port=None,
        passwd=None,
        priv=None,
        timeout=None):
    '''
    Return the cmd string to execute
    '''
    if priv:
        opts = _key_opts(
                user,
                port,
                priv,
                timeout)
        return 'ssh -o {0} -c {1}'.format(','.join(opts), cmd)
    elif passwd:
        opts = _key_opts(
                user,
                port,
                priv,
                timeout)
        return 'sshpass -p {0} ssh -o {1} -c {2}'.format(
                passwd,
                ','.join(opts),
                cmd)


def exec_cmd(
        cmd,
        user=None,
        port=None,
        passwd=None,
        priv=None,
        timeout=None):
    '''
    Execute a remote command
    '''

    cmd = _cmd_str(
            cmd,
            user=user,
            port=port,
            passwd=passwd,
            priv=priv,
            timeout=timeout)
