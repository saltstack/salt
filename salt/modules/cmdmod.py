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
from salt.grains.extra import shell as shell_grain

# Only available on posix systems, nonfatal on windows
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

DEFAULT_SHELL = shell_grain()['shell']

def __virtual__():
    '''
    Overwriting the cmd python module makes debugging modules
    with pdb a bit harder so lets do it this way instead.
    '''
    return 'cmd'


def _run(cmd,
         cwd=None,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,
         quiet=False,
         runas=None,
         with_env=True,
         shell=DEFAULT_SHELL,
         env=(),
         rstrip=True):
    '''
    Do the DRY thing and only call subprocess.Popen() once
    '''
    # Set the default working directory to the home directory
    # of the user salt-minion is running as.  Default:  /root
    if not cwd:
        cwd = os.path.expanduser('~{0}'.format('' if not runas else runas))
    
    if os.environ['os'].startswith('Windows'):
        pass
    else:
        if not os.path.isfile(shell) or not os.access(shell, os.X_OK):
            msg = 'The shell {0} is not available'.format(shell)
            raise CommandExecutionError(msg)

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
            cmd = 'cd ' + cwd + ' && ' + cmd

        cmd_prefix += runas + ' -c'
        cmd = '{0} "{1}"'.format(cmd_prefix, cmd)

    if not quiet:
        # Put the most common case first
        if not runas:
            log.info('Executing command {0} in directory {1}'.format(cmd, cwd))
        else:
            log.info('Executing command {0} as user {1} in directory {2}'.format(
                    orig_cmd, runas, cwd))

    run_env = os.environ
    run_env.update(env)
    kwargs = {'cwd': cwd,
              'shell': True,
              'env': run_env,
              'stdout': stdout,
              'stderr':stderr}
    if not os.environ.get('os', '').startswith('Windows'):
        kwargs['executable'] = shell
    # This is where the magic happens
    proc = subprocess.Popen(cmd, **kwargs)

    out = proc.communicate()

    if rstrip:
        # Cast out to a list as proc.communicate() returns a tuple
        out = list(out)
        if out[0]:
            out[0] = out[0].rstrip()
        # None lacks a rstrip() method
        if out[1]:
            out[1] = out[1].rstrip()

    ret['stdout']  = out[0]
    ret['stderr']  = out[1]
    ret['pid']     = proc.pid
    ret['retcode'] = proc.returncode
    return ret


def _run_quiet(cmd, cwd=None, runas=None, shell=DEFAULT_SHELL, env=()):
    '''
    Helper for running commands quietly for minion startup
    '''
    return _run(cmd, runas=runas, cwd=cwd, stderr=subprocess.STDOUT,
                quiet=True, shell=shell, env=env)['stdout']


def run(cmd, cwd=None, runas=None, shell=DEFAULT_SHELL, env=()):
    '''
    Execute the passed command and return the output as a string

    CLI Example::

        salt '*' cmd.run "ls -l | awk '/foo/{print $2}'"
    '''
    out = _run(cmd, runas=runas, shell=shell,
               cwd=cwd, stderr=subprocess.STDOUT, env=env)['stdout']
    log.debug('output: {0}'.format(out))
    return out


def run_stdout(cmd, cwd=None,  runas=None, shell=DEFAULT_SHELL, env=()):
    '''
    Execute a command, and only return the standard out

    CLI Example::

        salt '*' cmd.run_stdout "ls -l | awk '/foo/{print $2}'"
    '''
    stdout = _run(cmd, runas=runas, cwd=cwd, shell=shell, env=())["stdout"]
    log.debug('stdout: {0}'.format(stdout))
    return stdout


def run_stderr(cmd, cwd=None, runas=None, shell=DEFAULT_SHELL, env=()):
    '''
    Execute a command and only return the standard error

    CLI Example::

        salt '*' cmd.run_stderr "ls -l | awk '/foo/{print $2}'"
    '''
    stderr = _run(cmd, runas=runas, cwd=cwd, shell=shell, env=env)["stderr"]
    log.debug('stderr: {0}'.format(stderr))
    return stderr


def run_all(cmd, cwd=None, runas=None, shell=DEFAULT_SHELL, env=()):
    '''
    Execute the passed command and return a dict of return data

    CLI Example::

        salt '*' cmd.run_all "ls -l | awk '/foo/{print $2}'"
    '''
    ret = _run(cmd, runas=runas, cwd=cwd, shell=shell, env=env)
    if ret['retcode'] != 0:
        rcode = ret['retcode']
        msg = 'Command \'{0}\' failed with return code: {1}'
        log.error(msg.format(cmd, rcode))
        # Don't log a blank line if there is no stderr or stdout
        if ret['stdout']:
            log.error('stdout: {0}'.format(ret['stdout']))
        if ret['stderr']:
            log.error('stderr: {0}'.format(ret['stderr']))
    else:
        # No need to always log output on success to the logs
        if ret['stdout']:
            log.debug('stdout: {0}'.format(ret['stdout']))
        if ret['stderr']:
            log.debug('stderr: {0}'.format(ret['stderr']))
    return ret


def retcode(cmd, cwd=None, runas=None, shell=DEFAULT_SHELL, env=()):
    '''
    Execute a shell command and return the command's return code.

    CLI Example::

        salt '*' cmd.retcode "file /bin/bash"
    '''
    return _run(cmd, runas=runas, cwd=cwd, shell=shell, env=env)['retcode']


def which(cmd):
    '''
    Returns the path of an executable available on the minion, None otherwise

    CLI Example::

        salt '*' cmd.which cat
    '''
    return salt.utils.which(cmd)


def which_bin(cmds):
    '''
    Returns the first command found in a list of commands

    CLI Example::

        salt '*' cmd.which_bin '[pip2, pip, pip-python]'
    '''
    return salt.utils.which_bin(cmds)


def has_exec(cmd):
    '''
    Returns true if the executable is available on the minion, false otherwise

    CLI Example::

        salt '*' cmd.has_exec cat
    '''
    return bool(which(cmd))


def exec_code(lang, code, cwd=None):
    '''
    Pass in two strings, the first naming the executable language, aka -
    python2, python3, ruby, perl, lua, etc. the second string containing
    the code you wish to execute. The stdout and stderr will be returned

    CLI Example::

        salt '*' cmd.exec_code ruby 'puts "cheese"'
    '''
    fd_, codefile = tempfile.mkstemp()
    os.close(fd_)
    with open(codefile, 'w+') as fp_:
        fp_.write(code)

    cmd = '{0} {1}'.format(lang, codefile)
    ret = run(cmd, cwd=cwd)
    os.remove(codefile)
    return ret
