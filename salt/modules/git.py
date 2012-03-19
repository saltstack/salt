'''
Support for the Git SCM
'''

import os

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

def revision(cwd, rev='HEAD', short=False, user=None):
    '''
    Returns the long hash of a given identifier (hash, branch, tag, HEAD, etc)

    Usage::

        salt '*' git.revision /path/to/repo mybranch
    '''
    cmd = 'git rev-parse {0}{1}'.format('--short ' if short else '', rev)
    result = __salt__['cmd.run_all'](cmd, cwd, runas=user)

    if result['retcode'] == 0:
        return result['stdout']
    else:
        return ''

def clone(cwd, repository, opts=None, user=None):
    '''
    Clone a new repository

    Usage::

        salt '*' git.clone /path/to/repo git://github.com/saltstack/salt.git

        salt '*' git.clone /path/to/repo.git\\
                git://github.com/saltstack/salt.git '--bare --origin github'

    '''
    if not opts:
        opts = ''
    cmd = 'git clone {0} {1} {2}'.format(repository, cwd, opts)

    return __salt__['cmd.run'](cmd, runas=user)

def describe(cwd, rev='HEAD', user=None):
    '''
    Returns the git describe string (or the SHA hash if there are no tags) for
    the given revision
    '''
    cmd = 'git describe {0}'.format(rev)
    return __salt__['cmd.run_stdout'](cmd, cwd=cwd, runas=user)

def archive(cwd, output, rev='HEAD', fmt='', prefix='', user=None):
    '''
    Export a tarball from the repository

    If ``prefix`` is not specified it defaults to the basename of the repo
    directory.

    Usage::

        salt '*' git.archive /path/to/repo /path/to/archive.tar.gz
    '''
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

    Usage::

        salt '*' git.fetch /path/to/repo '--all'
    '''
    if not opts:
        opts = ''
    cmd = 'git fetch {0}'.format(opts)

    return __salt__['cmd.run'](cmd, cwd=cwd, runas=user)

def pull(cwd, opts=None, user=None):
    '''
    Perform a pull on the given repository

    Usage::

        salt '*' git.pull /path/to/repo '--rebase origin master'
    '''
    if not opts:
        opts = ''
    return __salt__['cmd.run']('git pull {0}'.format(opts), cwd=cwd, runas=user)

def checkout(cwd, rev, force=False, opts=None, user=None):
    '''
    Checkout a given revision

    Usage::

        salt '*' git.checkout /path/to/repo somebranch user=jeff

        salt '*' git.checkout /path/to/repo opts='testbranch -- conf/file1 file2'

        salt '*' git.checkout /path/to/repo 'origin/mybranch --track'
    '''
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
    opts : (none)
        Any additional options to add to the command line

    Usage::

        salt '*' git.fetch /path/to/repo
        salt '*' git.merge /path/to/repo @{upstream}
    '''
    if not opts:
        opts = ''
    cmd = 'git merge {0}{1} {2}'.format(
            branch,
            opts)

    return __salt__['cmd.run'](cmd, cwd, runas=user)

def init(cwd, opts=None, user=None):
    '''
    Init a new repository

    Usage::

        salt '*' git.init /path/to/repo.git '--bare'
    '''
    cmd = 'git init {0} {1}'.format(cwd, opts)
    return __salt__['cmd.run'](cmd, runas=user)
