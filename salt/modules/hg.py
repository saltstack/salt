# -*- coding: utf-8 -*-
'''
Support for the Mercurial SCM
'''
from __future__ import absolute_import

# Import salt libs
from salt import utils

if utils.is_windows():
    hg_binary = 'hg.exe'
else:
    hg_binary = 'hg'


def _check_hg():
    utils.check_or_die(hg_binary)


def _ssh_flag(identity_path):
    return '--ssh "ssh -i {0}"'.format(identity_path)


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
    _check_hg()

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
    _check_hg()

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
    _check_hg()

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
    _check_hg()

    cmd = ['hg', 'pull']
    if identity:
        cmd.append(_ssh_flag(identity))
    if opts:
        for opt in opts.split():
            cmd.append(opt)
    if repository is not None:
        cmd.append(repository)
    return __salt__['cmd.run'](cmd, cwd=cwd, runas=user, python_shell=False, use_vt=not utils.is_windows())


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
    _check_hg()

    cmd = ['hg', 'update', '{0}'.format(rev)]
    if force:
        cmd.append('-C')
    return __salt__['cmd.run'](cmd, cwd=cwd, runas=user, python_shell=False)


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
    _check_hg()
    cmd = ['hg', 'clone', '{0}'.format(repository), '{0}'.format(cwd)]
    if opts:
        for opt in opts.split():
            cmd.append('{0}'.format(opt))
    if identity:
        cmd.append(_ssh_flag(identity))
    return __salt__['cmd.run'](cmd, runas=user, python_shell=False, use_vt=not utils.is_windows())
