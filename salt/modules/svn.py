'''
Subversion SCM
'''

# Import python libs
import re
import shlex
import subprocess

# Import salt libs
from salt import utils, exceptions

_INI_RE = re.compile(r"^([^:]+):\s+(\S.*)$", re.M)


def __virtual__():
    '''
    Only load if svn is installed
    '''
    if utils.which('svn'):
        return 'svn'
    return False


def _check_svn():
    '''Check for svn on this node.'''
    utils.check_or_die('svn')


def _run_svn(cmd, cwd, user, username, opts, **kwargs):
    '''
    Execute svn
    return the output of the command

    cmd
        The command to run.

    cwd
        The path to the Subversion repository

    user
        Run svn as a user other than what the minion runs as

    username
        Connect to the Subversion server as another user

    opts
        Any additional options to add to the command line

    kwargs
        Additional options to pass to the run-cmd
    '''
    cmd = 'svn --non-interactive {0} '.format(cmd)
    if username:
        opts += ('--username', username)
    if opts:
        cmd += subprocess.list2cmdline(opts)

    result = __salt__['cmd.run_all'](cmd, cwd=cwd, runas=user, **kwargs)

    retcode = result['retcode']

    if retcode == 0:
        return result['stdout']
    else:
        raise exceptions.CommandExecutionError(result['stderr'] + '\n\n' + cmd)


def info(cwd, targets=None, user=None, username=None, fmt='str'):
    '''
    Display the Subversion information from the checkout.

    cwd
        The path to the Subversion repository

    targets : None
        files, directories, and URLs to pass to the command as arguments
        svn uses '.' by default

    user : None
        Run svn as a user other than what the minion runs as

    username : None
        Connect to the Subversion server as another user

    fmt : str
        How to fmt the output from info.
        (str, xml, list, dict)
    '''
    opts = list()
    if fmt == 'xml':
        opts.append('--xml')
    if targets:
        opts += shlex.split(targets)
    infos = _run_svn('info', cwd, user, username, opts)

    if fmt in ('str', 'xml'):
        return infos

    info_list = []
    for infosplit in infos.split('\n\n'):
        info_list.append(_INI_RE.findall(infosplit))

    if fmt == 'list':
        return info_list
    if fmt == 'dict':
        return [dict(tmp) for tmp in info_list]


def checkout(cwd, remote, target=None, user=None, username=None, *opts):
    '''
    Download a working copy of the remote Subversion repository
    directory or file

    cwd
        The path to the Subversion repository

    remote : None
        URL to checkout

    target : None
        The name to give the file or directory working copy
        Default: svn uses the remote basename

    user : None
        Run svn as a user other than what the minion runs as

    username : None
        Connect to the Subversion server as another user
    '''
    opts += (remote,)
    if target:
        opts += (target,)
    return _run_svn('checkout', cwd, user, username, opts)


def update(cwd, targets=None, user=None, *opts):
    '''
    Update the current directory, files, or directories from
    the remote Subversion repository

    cwd
        The path to the Subversion repository

    targets : None
        files and directories to pass to the command as arguments
        Default: svn uses '.'

    user : None
        Run svn as a user other than what the minion runs as

    username : None
        Connect to the Subversion server as another user
    '''
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn('update', cwd, user, None, opts)


def commit(cwd, targets=None, msg=None, user=None, username=None, *opts):
    '''
    Commit the current directory, files, or directories to
    the remote Subversion repository

    cwd
        The path to the Subversion repository

    targets : None
        files and directories to pass to the command as arguments
        Default: svn uses '.'

    msg : None
        Message to attach to the commit log

    user : None
        Run svn as a user other than what the minion runs as

    username : None
        Connect to the Subversion server as another user
    '''
    if msg:
        opts += ('-m', msg)
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn('commit', cwd, user, username, opts)


def add(cwd, targets, user=None, *opts):
    '''
    Add files to be tracked by the Subversion working-copy checkout

    cwd
        The path to the Subversion repository

    targets : None
        files and directories to pass to the command as arguments

    user : None
        Run svn as a user other than what the minion runs as
    '''
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn('add', cwd, user, None, opts)


def remove(cwd, targets, msg=None, user=None, username=None, *opts):
    '''
    Remove files and directories from the Subversion repository

    cwd
        The path to the Subversion repository

    targets : None
        files, directories, and URLs to pass to the command as arguments

    msg : None
        Message to attach to the commit log

    user : None
        Run svn as a user other than what the minion runs as

    username : None
        Connect to the Subversion server as another user
    '''
    if msg:
        opts += ('-m', msg)
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn('remove', cwd, user, username, opts)


def status(cwd, targets=None, user=None, username=None, *opts):
    '''
    Display the status of the current directory, files, or
    directories in the Subversion repository

    cwd
        The path to the Subversion repository

    targets : None
        files, directories, and URLs to pass to the command as arguments
        Default: svn uses '.'

    user : None
        Run svn as a user other than what the minion runs as

    username : None
        Connect to the Subversion server as another user
    '''
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn('status', cwd, user, username, opts)
