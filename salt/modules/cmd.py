'''
A module for shelling out

Keep in mind that this module is insecure, in that it can give whomever has
access to the master root execution access to all salt minions
'''

import logging
import os
import subprocess
import tempfile
import salt.utils
from salt.exceptions import CommandExecutionError
try:
    import pwd
except:
    pass


# Set up logging
log = logging.getLogger(__name__)

# Set up the default outputters
__outputter__ = {
    'run': 'txt',
}
def _run(cmd,
        cwd=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        quiet=False,
        runas=None,
        with_env=True):
    '''
    Do the DRY thing and only call subprocess.Popen() once
    '''
    # Set the default working directory to the home directory
    # of the user salt-minion is running as.  Default:  /root
    if not cwd:
        cwd = os.path.expanduser('~{0}'.format('' if not runas else runas))

    # TODO: Figure out the proper way to do this in windows
    disable_runas = [
        'Windows',
    ]

    ret = {}

    if runas and __grains__['os'] in disable_runas:
        msg = 'Sorry, {0} does not support runas functionality'
        raise CommandExecutionError(msg.format(__grains__['os']))

    if runas:
        # Save the original command before munging it
        orig_cmd = cmd
        try:
            p = pwd.getpwnam(runas)
        except KeyError:
            msg = 'User \'{0}\' is not available'.format(runas)
            raise CommandExecutionError(msg)

        cmd_prefix = 'su'

        # Load the 'nix environment
        if with_env:
            cmd_prefix += ' - '

        cmd_prefix += runas + ' -c'
        cmd = '{0} "{1}"'.format(cmd_prefix, cmd)

    if not quiet:
        # Put the most common case first
        if not runas:
            log.info('Executing command {0} in directory {1}'.format(cmd, cwd))
        else:
            log.info('Executing command {0} as user {1} in directory {2}'.format(
                    orig_cmd, runas, cwd))

    # This is where the magic happens
    proc = subprocess.Popen(cmd,
        cwd=cwd,
        shell=True,
        stdout=stdout,
        stderr=stderr
    )

    out = proc.communicate()
    ret['stdout']  = out[0]
    ret['stderr']  = out[1]
    ret['pid']     = proc.pid
    ret['retcode'] = proc.returncode
    return ret


def _run_quiet(cmd, cwd=None, runas=None):
    '''
    Helper for running commands quietly for minion startup
    '''
    return _run(cmd, runas=runas, cwd=cwd, stderr=subprocess.STDOUT, quiet=True)['stdout']


def run(cmd, cwd=None, runas=None):
    '''
    Execute the passed command and return the output as a string

    CLI Example::

        salt '*' cmd.run "ls -l | awk '/foo/{print $2}'"
    '''
    out = _run(cmd, runas=runas, cwd=cwd, stderr=subprocess.STDOUT)['stdout']
    log.debug(out)
    return out


def run_stdout(cmd, cwd=None,  runas=None):
    '''
    Execute a command, and only return the standard out

    CLI Example::

        salt '*' cmd.run_stdout "ls -l | awk '/foo/{print $2}'"
    '''
    stdout = _run(cmd, runas=runas, cwd=cwd)["stdout"]
    log.debug(stdout)
    return stdout


def run_stderr(cmd, cwd=None, runas=None):
    '''
    Execute a command and only return the standard error

    CLI Example::

        salt '*' cmd.run_stderr "ls -l | awk '/foo/{print $2}'"
    '''
    stderr = _run(cmd, runas=runas, cwd=cwd)["stderr"]
    log.debug(stderr)
    return stderr


def run_all(cmd, cwd=None, runas=None):
    '''
    Execute the passed command and return a dict of return data

    CLI Example::

        salt '*' cmd.run_all "ls -l | awk '/foo/{print $2}'"
    '''
    ret = _run(cmd, runas=runas, cwd=cwd)
    if ret['retcode'] != 0:
        log.error('Command {0} failed'.format(cmd))
        log.error('retcode: {0}'.format(ret['retcode']))
        log.error('stdout: {0}'.format(ret['stdout']))
        log.error('stderr: {0}'.format(ret['stderr']))
    else:
        log.info('stdout: {0}'.format(ret['stdout']))
        log.info('stderr: {0}'.format(ret['stderr']))
    return ret


def retcode(cmd, cwd=None, runas=None):
    '''
    Execute a shell command and return the command's return code.

    CLI Example::

        salt '*' cmd.retcode "file /bin/bash"
    '''
    return _run(cmd, runas=runas, cwd=cwd)['retcode']


def has_exec(cmd):
    '''
    Returns true if the executable is available on the minion, false otherwise

    CLI Example::

        salt '*' cmd.has_exec cat
    '''
    return bool(salt.utils.which(cmd))

def which(cmd):
    '''
    Returns the path of an executable available on the minion, None otherwise

    CLI Example::

        salt '*' cmd.which cat
    '''
    return salt.utils.which(cmd)

def exec_code(lang, code, cwd=None):
    '''
    Pass in two strings, the first naming the executable language, aka -
    python2, python3, ruby, perl, lua, etc. the second string containing
    the code you wish to execute. The stdout and stderr will be returned

    CLI Example::

        salt '*' cmd.exec_code ruby 'puts "cheese"'
    '''
    fd, codefile = tempfile.mkstemp()
    open(codefile, 'w+').write(code)

    cmd = '{0} {1}'.format(lang, codefile)
    ret = run(cmd, cwd=cwd)
    os.remove(codefile)
    return ret
