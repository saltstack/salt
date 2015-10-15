# -*- coding: utf-8 -*-
'''
Subversion SCM
'''
from __future__ import absolute_import

# Import python libs
import re
import shlex

# Import salt libs
from salt import utils, exceptions

_INI_RE = re.compile(r"^([^:]+):\s+(\S.*)$", re.M)


def __virtual__():
    '''
    Only load if svn is installed
    '''
    if utils.which('svn'):
        return True
    return False


def _check_svn():
    '''
    Check for svn on this node.
    '''
    utils.check_or_die('svn')


def _run_svn(cmd, cwd, user, username, password, opts, **kwargs):
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

    password
        Connect to the Subversion server with this password

        .. versionadded:: 0.17.0

    opts
        Any additional options to add to the command line

    kwargs
        Additional options to pass to the run-cmd
    '''
    cmd = ['svn', '--non-interactive', cmd]

    options = list(opts)
    if username:
        options.extend(['--username', username])
    if password:
        options.extend(['--password', password])
    cmd.extend(options)

    result = __salt__['cmd.run_all'](cmd, python_shell=False, cwd=cwd, runas=user, **kwargs)

    retcode = result['retcode']

    if retcode == 0:
        return result['stdout']
    raise exceptions.CommandExecutionError(result['stderr'] + '\n\n' + ' '.join(cmd))


def info(cwd,
         targets=None,
         user=None,
         username=None,
         password=None,
         fmt='str'):
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

    password : None
        Connect to the Subversion server with this password

        .. versionadded:: 0.17.0

    fmt : str
        How to fmt the output from info.
        (str, xml, list, dict)

    CLI Example:

    .. code-block:: bash

        salt '*' svn.info /path/to/svn/repo
    '''
    opts = list()
    if fmt == 'xml':
        opts.append('--xml')
    if targets:
        opts += shlex.split(targets)
    infos = _run_svn('info', cwd, user, username, password, opts)

    if fmt in ('str', 'xml'):
        return infos

    info_list = []
    for infosplit in infos.split('\n\n'):
        info_list.append(_INI_RE.findall(infosplit))

    if fmt == 'list':
        return info_list
    if fmt == 'dict':
        return [dict(tmp) for tmp in info_list]


def checkout(cwd,
             remote,
             target=None,
             user=None,
             username=None,
             password=None,
             *opts):
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

    password : None
        Connect to the Subversion server with this password

        .. versionadded:: 0.17.0

    CLI Example:

    .. code-block:: bash

        salt '*' svn.checkout /path/to/repo svn://remote/repo
    '''
    opts += (remote,)
    if target:
        opts += (target,)
    return _run_svn('checkout', cwd, user, username, password, opts)


def switch(cwd, remote, target=None, user=None, username=None,
           password=None, *opts):
    '''
    .. versionadded:: 2014.1.0

    Switch a working copy of a remote Subversion repository
    directory

    cwd
        The path to the Subversion repository

    remote : None
        URL to switch

    target : None
        The name to give the file or directory working copy
        Default: svn uses the remote basename

    user : None
        Run svn as a user other than what the minion runs as

    username : None
        Connect to the Subversion server as another user

    password : None
        Connect to the Subversion server with this password

    CLI Example:

    .. code-block:: bash

        salt '*' svn.switch /path/to/repo svn://remote/repo
    '''
    opts += (remote,)
    if target:
        opts += (target,)
    return _run_svn('switch', cwd, user, username, password, opts)


def update(cwd, targets=None, user=None, username=None, password=None, *opts):
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

    password : None
        Connect to the Subversion server with this password

        .. versionadded:: 0.17.0

    username : None
        Connect to the Subversion server as another user

    CLI Example:

    .. code-block:: bash

        salt '*' svn.update /path/to/repo
    '''
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn('update', cwd, user, username, password, opts)


def diff(cwd, targets=None, user=None, username=None, password=None, *opts):
    '''
    Return the diff of the current directory, files, or directories from
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

    password : None
        Connect to the Subversion server with this password

        .. versionadded:: 0.17.0

    CLI Example:

    .. code-block:: bash

        salt '*' svn.diff /path/to/repo
    '''
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn('diff', cwd, user, username, password, opts)


def commit(cwd,
           targets=None,
           msg=None,
           user=None,
           username=None,
           password=None,
           *opts):
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

    password : None
        Connect to the Subversion server with this password

        .. versionadded:: 0.17.0

    CLI Example:

    .. code-block:: bash

        salt '*' svn.commit /path/to/repo
    '''
    if msg:
        opts += ('-m', msg)
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn('commit', cwd, user, username, password, opts)


def add(cwd, targets, user=None, username=None, password=None, *opts):
    '''
    Add files to be tracked by the Subversion working-copy checkout

    cwd
        The path to the Subversion repository

    targets : None
        files and directories to pass to the command as arguments

    user : None
        Run svn as a user other than what the minion runs as

    username : None
        Connect to the Subversion server as another user

    password : None
        Connect to the Subversion server with this password

        .. versionadded:: 0.17.0

    CLI Example:

    .. code-block:: bash

        salt '*' svn.add /path/to/repo /path/to/new/file
    '''
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn('add', cwd, user, username, password, opts)


def remove(cwd,
           targets,
           msg=None,
           user=None,
           username=None,
           password=None,
           *opts):
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

    password : None
        Connect to the Subversion server with this password

        .. versionadded:: 0.17.0

    CLI Example:

    .. code-block:: bash

        salt '*' svn.remove /path/to/repo /path/to/repo/remove
    '''
    if msg:
        opts += ('-m', msg)
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn('remove', cwd, user, username, password, opts)


def status(cwd, targets=None, user=None, username=None, password=None, *opts):
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

    password : None
        Connect to the Subversion server with this password

        .. versionadded:: 0.17.0

    CLI Example:

    .. code-block:: bash

        salt '*' svn.status /path/to/repo
    '''
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn('status', cwd, user, username, password, opts)


def export(cwd,
             remote,
             target=None,
             user=None,
             username=None,
             password=None,
             revision='HEAD',
             *opts):
    '''
    Create an unversioned copy of a tree.

    cwd
        The path to the Subversion repository

    remote : None
        URL and path to file or directory checkout

    target : None
        The name to give the file or directory working copy
        Default: svn uses the remote basename

    user : None
        Run svn as a user other than what the minion runs as

    username : None
        Connect to the Subversion server as another user

    password : None
        Connect to the Subversion server with this password

        .. versionadded:: 0.17.0

    CLI Example:

    .. code-block:: bash

        salt '*' svn.export /path/to/repo svn://remote/repo
    '''
    opts += (remote,)
    if target:
        opts += (target,)
    revision_args = '-r'
    opts += (revision_args, str(revision),)
    return _run_svn('export', cwd, user, username, password, opts)
