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

# Set up logging
log = logging.getLogger(__name__)

# Set the default working directory to the home directory
# of the user salt-minion is running as.  Default:  /root
DEFAULT_CWD = os.path.expanduser('~')

# Set up the default outputters
__outputter__ = {
    'run': 'txt',
}


def _is_exec(path):
    '''
    Return true if the passed path exists and is executable
    '''
    return os.path.exists(path) and os.access(path, os.X_OK)


def run(cmd, cwd=DEFAULT_CWD):
    '''
    Execute the passed command and return the output as a string

    CLI Example::

        salt '*' cmd.run "ls -l | awk '/foo/{print $2}'"
    '''
    log.info('Executing command {0} in directory {1}'.format(cmd, cwd))
    out = subprocess.Popen(cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT).communicate()[0]
    log.debug(out)
    return out


def run_stdout(cmd, cwd=DEFAULT_CWD):
    '''
    Execute a command, and only return the standard out

    CLI Example::

        salt '*' cmd.run_stdout "ls -l | awk '/foo/{print $2}'"
    '''
    log.info('Executing command {0} in directory {1}'.format(cmd, cwd))
    stdout = subprocess.Popen(cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE).communicate()[0]
    log.debug(stdout)
    return stdout


def run_stderr(cmd, cwd=DEFAULT_CWD):
    '''
    Execute a command and only return the standard error

    CLI Example::

        salt '*' cmd.run_stderr "ls -l | awk '/foo/{print $2}'"
    '''
    log.info('Executing command {0} in directory {1}'.format(cmd, cwd))
    stderr = subprocess.Popen(cmd,
            shell=True,
            cwd=cwd,
            stderr=subprocess.PIPE).communicate()[0]
    log.debug(stderr)
    return stderr


def run_all(cmd, cwd=DEFAULT_CWD):
    '''
    Execute the passed command and return a dict of return data

    CLI Example::

        salt '*' cmd.run_all "ls -l | awk '/foo/{print $2}'"
    '''
    log.info('Executing command {0} in directory {1}'.format(cmd, cwd))
    ret = {}
    proc = subprocess.Popen(cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    out = proc.communicate()
    ret['stdout'] = out[0]
    ret['stderr'] = out[1]
    ret['retcode'] = proc.returncode
    ret['pid'] = proc.pid
    if not ret['retcode']:
        log.error('Command {0} failed'.format(cmd))
        log.error('stdout: {0}'.format(ret['stdout']))
        log.error('stderr: {0}'.format(ret['stderr']))
    else:
        log.info('stdout: {0}'.format(ret['stdout']))
        log.info('stderr: {0}'.format(ret['stderr']))
    return ret


def retcode(cmd, cwd=DEFAULT_CWD):
    '''
    Execute a shell command and return the command's return code.

    CLI Example::

        salt '*' cmd.retcode "file /bin/bash"
    '''
    log.info('Executing command {0} in directory {1}'.format(cmd, cwd))
    return subprocess.call(cmd, shell=True, cwd=cwd)


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

def exec_code(lang, code, cwd=DEFAULT_CWD):
    '''
    Pass in two strings, the first naming the executable language, aka -
    python2, python3, ruby, perl, lua, etc. the second string containing
    the code you wish to execute. The stdout and stderr will be returned

    CLI Example::

        salt '*' cmd.exec_code ruby 'puts "cheese"'
    '''
    fd, cfn = tempfile.mkstemp()
    open(cfn, 'w+').write(code)
    return subprocess.Popen(lang + ' ' + cfn,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT).communicate()[0]
