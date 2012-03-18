'''
Support for the Mercurial SCM
'''

from salt import utils

__outputter__ = {
  'clone': 'txt',
  'revision': 'txt',
}

def _check_hg():
    utils.check_or_die('hg')

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

    CLI Example::

        salt '*' hg.revision /path/to/repo mybranch
    '''
    _check_hg()

    cmd = 'hg id -i{short} {rev}'.format(
        short = ' --debug' if not short else '',
        rev = ' -r {0}'.format(rev))

    result = __salt__['cmd.run_all'](cmd, cwd=cwd, runas=user)

    if result['retcode'] == 0:
        return result['stdout']
    else:
        return ''

def describe(cwd, rev='tip', user=None):
    '''
    Mimick git describe and return an identifier for the given revision

    cwd
        The path to the Mercurial repository

    rev: tip
        The path to the archive tarball

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example::

        salt '*' hg.describe /path/to/repo
    '''
    _check_hg()

    cmd = "hg log -r {0} --template"\
            " '{{latesttag}}-{{latesttagdistance}}-{{node|short}}'".format(rev)
    desc = __salt__['cmd.run_stdout'](cmd, cwd=cwd, runas=user)

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

    CLI Example::

        salt '*' hg.archive /path/to/repo output=/tmp/archive.tgz fmt=tgz
    '''
    _check_hg()

    cmd = 'hg archive {output}{rev}{fmt}'.format(
        rev = ' --rev {0}'.format(rev),
        output = output,
        fmt = ' --type {0}'.format(fmt) if fmt else '',
        prefix = ' --prefix "{0}"'.format(prefix if prefix else ''))

    return __salt__['cmd.run'](cmd, cwd=cwd, runas=user)

def pull(cwd, opts=None, user=None):
    '''
    Perform a pull on the given repository

    cwd
        The path to the Mercurial repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example::

        salt '*' hg.pull /path/to/repo '-u'
    '''
    _check_hg()

    if not opts:
        opts = ''
    return __salt__['cmd.run']('hg pull {0}'.format(opts), cwd=cwd, runas=user)

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

    CLI Example::

        salt devserver1 hg.update /path/to/repo somebranch
    '''
    _check_hg()

    cmd = 'hg update {0}{1}'.format(rev, ' -C' if force else '')
    return __salt__['cmd.run'](cmd, cwd=cwd, runas=user)

def clone(cwd, repository, opts=None, user=None):
    '''
    Clone a new repository

    cwd
        The path to the Mercurial repository

    repository
        The hg uri of the repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example::

        salt '*' hg.clone /path/to/repo https://bitbucket.org/birkenfeld/sphinx
    '''
    _check_hg()

    if not opts:
        opts = ''
    cmd = 'hg clone {0} {1} {2}'.format(repository, cwd, opts)
    return __salt__['cmd.run'](cmd, runas=user)
