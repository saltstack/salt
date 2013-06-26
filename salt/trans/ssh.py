'''
Manage transport commands via ssh
'''

# Import python libs
import time
import subprocess

# Import salt libs
import salt.utils
import salt.utils.nb_popen

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
        timeout=None,
        tty=False):
    '''
    Return the cmd string to execute
    '''
    if priv:
        opts = _key_opts(
                user,
                port,
                priv,
                timeout)
        return '{0} {1} -o {2} -c {3}'.format(
                ssh,
                '-t -t' if tty else '',
                ','.join(opts),
                cmd)
    elif passwd:
        if not salt.utils.which('sshpass'):
            return None
        opts = _key_opts(
                user,
                port,
                priv,
                timeout)
        return 'sshpass -p {0} {1} {2} -o {3} -c {4}'.format(
                passwd,
                ssh,
                '-t -t' if tty else '',
                ','.join(opts),
                cmd)
    return None


def exec_cmd(
        cmd,
        user=None,
        port=None,
        passwd=None,
        priv=None,
        timeout=None,
        sudo=False):
    '''
    Execute a remote command
    '''
    if sudo:
        cmd = 'sudo {0}'.format(cmd)
        tty = True
    else:
        tty = False
    cmd = _cmd_str(
            cmd,
            user=user,
            port=port,
            passwd=passwd,
            priv=priv,
            timeout=timeout,
            tty=tty)
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
