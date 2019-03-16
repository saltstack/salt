# -*- coding: utf-8 -*-
'''
Support for the Mercurial SCM
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import salt libs
from salt.exceptions import CommandExecutionError
import salt.utils.data
import salt.utils.path

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if hg is installed
    '''
    if salt.utils.path.which('hg') is None:
        return (False,
                'The hg execution module cannot be loaded: hg unavailable.')
    else:
        return True


def _ssh_flag(identity_path):
    return ['--ssh', 'ssh -i {0}'.format(identity_path)]


def revision(cwd, rev='tip', short=False, user=None):
    '''
    Returns the long hash of a given identifier (hash, branch, tag, HEAD, etc)

    cwd
        The path to the Mercurial repository

    rev: tip
        The revision

    short: False
        Return an abbreviated commit hash

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' hg.revision /path/to/repo mybranch
    '''
    cmd = [
            'hg',
            'id',
            '-i',
            '--debug' if not short else '',
            '-r',
            '{0}'.format(rev)]

    result = __salt__['cmd.run_all'](
            cmd,
            cwd=cwd,
            runas=user,
            python_shell=False)

    if result['retcode'] == 0:
        return result['stdout']
    else:
        return ''


def describe(cwd, rev='tip', user=None):
    '''
    Mimic git describe and return an identifier for the given revision

    cwd
        The path to the Mercurial repository

    rev: tip
        The path to the archive tarball

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' hg.describe /path/to/repo
    '''
    cmd = [
            'hg',
            'log',
            '-r',
            '{0}'.format(rev),
            '--template',
            "'{{latesttag}}-{{latesttagdistance}}-{{node|short}}'"
            ]
    desc = __salt__['cmd.run_stdout'](
            cmd,
            cwd=cwd,
            runas=user,
            python_shell=False)

    return desc or revision(cwd, rev, short=True)


def archive(cwd, output, rev='tip', fmt=None, prefix=None, user=None):
    '''
    Export a tarball from the repository

    cwd
        The path to the Mercurial repository

    output
        The path to the archive tarball

    rev: tip
        The revision to create an archive from

    fmt: None
        Format of the resulting archive. Mercurial supports: tar,
        tbz2, tgz, zip, uzip, and files formats.

    prefix : None
        Prepend <prefix>/ to every filename in the archive

    user : None
        Run hg as a user other than what the minion runs as

    If ``prefix`` is not specified it defaults to the basename of the repo
    directory.

    CLI Example:

    .. code-block:: bash

        salt '*' hg.archive /path/to/repo output=/tmp/archive.tgz fmt=tgz
    '''
    cmd = [
            'hg',
            'archive',
            '{0}'.format(output),
            '--rev',
            '{0}'.format(rev),
            ]
    if fmt:
        cmd.append('--type')
        cmd.append('{0}'.format(fmt))
    if prefix:
        cmd.append('--prefix')
        cmd.append('"{0}"'.format(prefix))
    return __salt__['cmd.run'](cmd, cwd=cwd, runas=user, python_shell=False)


def pull(cwd, opts=None, user=None, identity=None, repository=None):
    '''
    Perform a pull on the given repository

    cwd
        The path to the Mercurial repository

    repository : None
        Perform pull from the repository different from .hg/hgrc:[paths]:default

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as

    identity : None
        Private SSH key on the minion server for authentication (ssh://)

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' hg.pull /path/to/repo opts=-u
    '''
    cmd = ['hg', 'pull']
    if identity:
        cmd.extend(_ssh_flag(identity))
    if opts:
        for opt in opts.split():
            cmd.append(opt)
    if repository is not None:
        cmd.append(repository)

    ret = __salt__['cmd.run_all'](cmd, cwd=cwd, runas=user, python_shell=False)
    if ret['retcode'] != 0:
        raise CommandExecutionError(
            'Hg command failed: {0}'.format(ret.get('stderr', ret['stdout']))
        )

    return ret['stdout']


def update(cwd, rev, force=False, user=None):
    '''
    Update to a given revision

    cwd
        The path to the Mercurial repository

    rev
        The revision to update to

    force : False
        Force an update

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt devserver1 hg.update /path/to/repo somebranch
    '''
    cmd = ['hg', 'update', '{0}'.format(rev)]
    if force:
        cmd.append('-C')

    ret = __salt__['cmd.run_all'](cmd, cwd=cwd, runas=user, python_shell=False)
    if ret['retcode'] != 0:
        raise CommandExecutionError(
            'Hg command failed: {0}'.format(ret.get('stderr', ret['stdout']))
        )

    return ret['stdout']


def clone(cwd, repository, opts=None, user=None, identity=None):
    '''
    Clone a new repository

    cwd
        The path to the Mercurial repository

    repository
        The hg URI of the repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as

    identity : None
        Private SSH key on the minion server for authentication (ssh://)

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' hg.clone /path/to/repo https://bitbucket.org/birkenfeld/sphinx
    '''
    cmd = ['hg', 'clone', '{0}'.format(repository), '{0}'.format(cwd)]
    if opts:
        for opt in opts.split():
            cmd.append('{0}'.format(opt))
    if identity:
        cmd.extend(_ssh_flag(identity))

    ret = __salt__['cmd.run_all'](cmd, runas=user, python_shell=False)
    if ret['retcode'] != 0:
        raise CommandExecutionError(
            'Hg command failed: {0}'.format(ret.get('stderr', ret['stdout']))
        )

    return ret['stdout']


def status(cwd, opts=None, user=None):
    '''
    Show changed files of the given repository

    cwd
        The path to the Mercurial repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' hg.status /path/to/repo
    '''
    def _status(cwd):
        cmd = ['hg', 'status']
        if opts:
            for opt in opts.split():
                cmd.append('{0}'.format(opt))
        out = __salt__['cmd.run_stdout'](
            cmd, cwd=cwd, runas=user, python_shell=False)
        types = {
            'M': 'modified',
            'A': 'added',
            'R': 'removed',
            'C': 'clean',
            '!': 'missing',
            '?': 'not tracked',
            'I': 'ignored',
            ' ': 'origin of the previous file',
        }
        ret = {}
        for line in out.splitlines():
            t, f = types[line[0]], line[2:]
            if t not in ret:
                ret[t] = []
            ret[t].append(f)
        return ret

    if salt.utils.data.is_iter(cwd):
        return dict((cwd, _status(cwd)) for cwd in cwd)
    else:
        return _status(cwd)
