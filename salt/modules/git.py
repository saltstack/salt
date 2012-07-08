'''
Support for the Git SCM
'''

import os
from salt import utils

def _git_getdir(cwd, user=None):
    '''
    Returns the absolute path to the top-level of a given repo because some Git
    commands are sensitive to where they're run from (archive for one)
    '''
    cmd_bare = 'git rev-parse --is-bare-repository'
    is_bare = __salt__['cmd.run_stdout'](cmd_bare, cwd, runas=user) == 'true'

    if is_bare:
        return cwd

    cmd_toplvl = 'git rev-parse --show-toplevel'
    return __salt__['cmd.run'](cmd_toplvl, cwd)

def _check_git():
    utils.check_or_die('git')

def revision(cwd, rev='HEAD', short=False, user=None):
    '''
    Returns the long hash of a given identifier (hash, branch, tag, HEAD, etc)

    cwd
        The path to the Git repository

    rev: HEAD
        The revision

    short: False
        Return an abbreviated SHA1 git hash

    user : None
        Run git as a user other than what the minion runs as

    CLI Example::

        salt '*' git.revision /path/to/repo mybranch
    '''
    _check_git()

    cmd = 'git rev-parse {0}{1}'.format('--short ' if short else '', rev)
    result = __salt__['cmd.run_all'](cmd, cwd, runas=user)

    if result['retcode'] == 0:
        return result['stdout']
    else:
        return ''

def clone(cwd, repository, opts=None, user=None):
    '''
    Clone a new repository

    cwd
        The path to the Git repository

    repository
        The git uri of the repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example::

        salt '*' git.clone /path/to/repo git://github.com/saltstack/salt.git

        salt '*' git.clone /path/to/repo.git\\
                git://github.com/saltstack/salt.git '--bare --origin github'

    '''
    _check_git()

    if not opts:
        opts = ''
    cmd = 'git clone {0} {1} {2}'.format(repository, cwd, opts)

    return __salt__['cmd.run'](cmd, runas=user)

def describe(cwd, rev='HEAD', user=None):
    '''
    Returns the git describe string (or the SHA hash if there are no tags) for
    the given revision

    cwd
        The path to the Git repository

    rev: HEAD
        The revision to describe

    user : None
        Run git as a user other than what the minion runs as

    CLI Examples::

        salt '*' git.describe /path/to/repo

        salt '*' git.describe /path/to/repo develop
    '''
    cmd = 'git describe {0}'.format(rev)
    return __salt__['cmd.run_stdout'](cmd, cwd=cwd, runas=user)

def archive(cwd, output, rev='HEAD', fmt=None, prefix=None, user=None):
    '''
    Export a tarball from the repository

    cwd
        The path to the Git repository

    output
        The path to the archive tarball

    rev: HEAD
        The revision to create an archive from

    fmt: None
        Format of the resulting archive, zip and tar are commonly used

    prefix : None
        Prepend <prefix>/ to every filename in the archive

    user : None
        Run git as a user other than what the minion runs as

    If ``prefix`` is not specified it defaults to the basename of the repo
    directory.

    CLI Example::

        salt '*' git.archive /path/to/repo /path/to/archive.tar.gz
    '''
    _check_git()

    basename = '{0}/'.format(os.path.basename(_git_getdir(cwd, user=user)))

    cmd = 'git archive{prefix}{fmt} -o {output} {rev}'.format(
        rev = rev,
        output = output,
        fmt = ' --format={0}'.format(fmt) if fmt else '',
        prefix = ' --prefix="{0}"'.format(prefix if prefix else basename))

    return __salt__['cmd.run'](cmd, cwd=cwd, runas=user)

def fetch(cwd, opts=None, user=None):
    '''
    Perform a fetch on the given repository

    cwd
        The path to the Git repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example::

        salt '*' git.fetch /path/to/repo '--all'

        salt '*' git.fetch cwd=/path/to/repo opts='--all' user=johnny
    '''
    _check_git()

    if not opts:
        opts = ''
    cmd = 'git fetch {0}'.format(opts)

    return __salt__['cmd.run'](cmd, cwd=cwd, runas=user)

def pull(cwd, opts=None, user=None):
    '''
    Perform a pull on the given repository

    cwd
        The path to the Git repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example::

        salt '*' git.pull /path/to/repo opts='--rebase origin master'
    '''
    _check_git()

    if not opts:
        opts = ''
    return __salt__['cmd.run']('git pull {0}'.format(opts), cwd=cwd, runas=user)

def rebase(cwd, rev='master', opts=None, user=None):
    '''
    Rebase the current branch

    cwd
        The path to the Git repository

    rev : master
        The revision to rebase onto the current branch

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example::

        salt '*' git.rebase /path/to/repo master

    That is the same as: git rebase master
    '''
    _check_git()

    if not opts:
        opts = ''
    return __salt__['cmd.run']('git rebase {0}'.format(opts), cwd=cwd, runas=user)

def checkout(cwd, rev, force=False, opts=None, user=None):
    '''
    Checkout a given revision

    cwd
        The path to the Git repository

    rev
        The remote branch or revision to checkout

    force : False
        Force a checkout even if there might be overwritten changes

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Examples::

        salt '*' git.checkout /path/to/repo somebranch user=jeff

        salt '*' git.checkout /path/to/repo opts='testbranch -- conf/file1 file2'

        salt '*' git.checkout /path/to/repo rev=origin/mybranch opts=--track
    '''
    _check_git()

    if not opts:
        opts = ''
    cmd = 'git checkout {0} {1} {2}'.format(' -f' if force else '', rev, opts)
    return __salt__['cmd.run'](cmd, cwd=cwd, runas=user)

def merge(cwd, branch='@{upstream}', opts=None, user=None):
    '''
    Merge a given branch

    cwd
        The path to the Git repository

    branch : @{upstream}
        The remote branch or revision to merge into the current branch

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example::

        salt '*' git.fetch /path/to/repo
        salt '*' git.merge /path/to/repo @{upstream}
    '''
    _check_git()

    if not opts:
        opts = ''
    cmd = 'git merge {0}{1} {2}'.format(
            branch,
            opts)

    return __salt__['cmd.run'](cmd, cwd, runas=user)

def init(cwd, opts=None, user=None):
    '''
    Initialize a new git repository

    cwd
        The path to the Git repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example::

        salt '*' git.init /path/to/repo.git opts='--bare'
    '''
    _check_git()

    cmd = 'git init {0} {1}'.format(cwd, opts)
    return __salt__['cmd.run'](cmd, runas=user)

def submodule(cwd, init=True, opts=None, user=None):
    '''
    Initialize git submodules

    cwd
        The path to the Git repository

    init : True
        Ensure that new submodules are initialized

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as
    '''
    _check_git()

    if not opts:
        opts = ''
    cmd = 'git submodule update {0} {1}'.format('--init' if init else '', opts)
    return __salt__['cmd.run'](cmd, cwd=cwd, runas=user)
