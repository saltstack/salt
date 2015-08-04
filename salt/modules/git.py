# -*- coding: utf-8 -*-
'''
Support for the Git SCM
'''
from __future__ import absolute_import

# Import python libs
import os
import subprocess

# Import salt libs
from salt import utils
from salt.exceptions import SaltInvocationError, CommandExecutionError
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module,import-error
from salt.ext.six.moves.urllib.parse import urlunparse as _urlunparse  # pylint: disable=no-name-in-module,import-error


def __virtual__():
    '''
    Only load if git exists on the system
    '''
    return True if utils.which('git') else False


def _git_run(cmd, cwd=None, runas=None, identity=None, **kwargs):
    '''
    simple, throw an exception with the error message on an error return code.

    this function may be moved to the command module, spliced with
    'cmd.run_all', and used as an alternative to 'cmd.run_all'. Some
    commands don't return proper retcodes, so this can't replace 'cmd.run_all'.
    '''
    env = {}

    if identity:
        stderrs = []

        # if the statefile provides multiple identities, they need to be tried
        # (but also allow a string instead of a list)
        if not isinstance(identity, list):
            # force it into a list
            identity = [identity]

        # try each of the identities, independently
        for id_file in identity:
            env = {
                'GIT_IDENTITY': id_file
            }

            # copy wrapper to area accessible by ``runas`` user
            # currently no suppport in windows for wrapping git ssh
            if not utils.is_windows():
                ssh_id_wrapper = os.path.join(utils.templates.TEMPLATE_DIRNAME,
                                              'git/ssh-id-wrapper')
                tmp_file = utils.mkstemp()
                utils.files.copyfile(ssh_id_wrapper, tmp_file)
                os.chmod(tmp_file, 0o500)
                os.chown(tmp_file, __salt__['file.user_to_uid'](runas), -1)
                env['GIT_SSH'] = tmp_file

            try:
                result = __salt__['cmd.run_all'](cmd,
                                                 cwd=cwd,
                                                 runas=runas,
                                                 env=env,
                                                 python_shell=False,
                                                 **kwargs)
            finally:
                if 'GIT_SSH' in env:
                    os.remove(env['GIT_SSH'])

            # if the command was successful, no need to try additional IDs
            if result['retcode'] == 0:
                return result['stdout']
            else:
                stderrs.append(result['stderr'])

        # we've tried all IDs and still haven't passed, so error out
        raise CommandExecutionError("\n\n".join(stderrs))

    else:
        result = __salt__['cmd.run_all'](cmd,
                                         cwd=cwd,
                                         runas=runas,
                                         env=env,
                                         python_shell=False,
                                         **kwargs)
        retcode = result['retcode']

        if retcode == 0:
            return result['stdout']
        else:
            raise CommandExecutionError(
                'Command {0!r} failed. Stderr: {1!r}'.format(cmd,
                                                             result['stderr']))


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
    '''
    Check if git is available
    '''
    utils.check_or_die('git')


def _add_http_basic_auth(repository, https_user=None, https_pass=None):
    if https_user is None and https_pass is None:
        return repository
    else:
        urltuple = _urlparse(repository)
        if urltuple.scheme == 'https':
            netloc = "{0}:{1}@{2}".format(https_user, https_pass,
                                          urltuple.netloc)
            urltuple = urltuple._replace(netloc=netloc)
            return _urlunparse(urltuple)
        else:
            raise ValueError('Basic Auth only supported for HTTPS scheme')


def current_branch(cwd, user=None):
    '''
    Returns the current branch name, if on a branch.

    CLI Example:

    .. code-block:: bash

        salt '*' git.current_branch /path/to/repo
    '''
    cmd = r'git rev-parse --abbrev-ref HEAD'

    return __salt__['cmd.run_stdout'](cmd, cwd=cwd, runas=user)


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

    CLI Example:

    .. code-block:: bash

        salt '*' git.revision /path/to/repo mybranch
    '''
    _check_git()

    cmd = 'git rev-parse {0}{1}'.format('--short ' if short else '', rev)
    return _git_run(cmd, cwd, runas=user)


def clone(cwd, repository, opts=None, user=None, identity=None,
          https_user=None, https_pass=None):
    '''
    Clone a new repository

    cwd
        The path to the Git repository

    repository
        The git URI of the repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    identity : None
        A path to a private key to use over SSH

    https_user : None
        HTTP Basic Auth username for HTTPS (only) clones

        .. versionadded:: 20515.5.0

    https_pass : None
        HTTP Basic Auth password for HTTPS (only) clones

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' git.clone /path/to/repo git://github.com/saltstack/salt.git

        salt '*' git.clone /path/to/repo.git\\
                git://github.com/saltstack/salt.git '--bare --origin github'

    '''
    _check_git()

    repository = _add_http_basic_auth(repository, https_user, https_pass)

    if not opts:
        opts = ''
    if utils.is_windows():
        cmd = 'git clone {0} {1} {2}'.format(repository, cwd, opts)
    else:
        cmd = 'git clone {0} {1!r} {2}'.format(repository, cwd, opts)

    return _git_run(cmd, runas=user, identity=identity)


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

    CLI Examples:

    .. code-block:: bash

        salt '*' git.describe /path/to/repo

        salt '*' git.describe /path/to/repo develop
    '''
    cmd = 'git describe {0}'.format(rev)
    return __salt__['cmd.run_stdout'](cmd,
                                      cwd=cwd,
                                      runas=user,
                                      python_shell=False)


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

    CLI Example:

    .. code-block:: bash

        salt '*' git.archive /path/to/repo /path/to/archive.tar.gz
    '''
    _check_git()

    basename = '{0}/'.format(os.path.basename(_git_getdir(cwd, user=user)))

    cmd = 'git archive{prefix}{fmt} -o {output} {rev}'.format(
            rev=rev,
            output=output,
            fmt=' --format={0}'.format(fmt) if fmt else '',
            prefix=' --prefix="{0}"'.format(prefix if prefix else basename)
    )

    return _git_run(cmd, cwd=cwd, runas=user)


def fetch(cwd, opts=None, user=None, identity=None):
    '''
    Perform a fetch on the given repository

    cwd
        The path to the Git repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    identity : None
        A path to a private key to use over SSH

    CLI Example:

    .. code-block:: bash

        salt '*' git.fetch /path/to/repo '--all'

        salt '*' git.fetch cwd=/path/to/repo opts='--all' user=johnny
    '''
    _check_git()

    if not opts:
        opts = ''
    cmd = 'git fetch {0}'.format(opts)

    return _git_run(cmd, cwd=cwd, runas=user, identity=identity)


def pull(cwd, opts=None, user=None, identity=None):
    '''
    Perform a pull on the given repository

    cwd
        The path to the Git repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    identity : None
        A path to a private key to use over SSH

    CLI Example:

    .. code-block:: bash

        salt '*' git.pull /path/to/repo opts='--rebase origin master'
    '''
    _check_git()

    if not opts:
        opts = ''
    return _git_run('git pull {0}'.format(opts),
                    cwd=cwd,
                    runas=user,
                    identity=identity)


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

    CLI Example:

    .. code-block:: bash

        salt '*' git.rebase /path/to/repo master
        salt '*' git.rebase /path/to/repo 'origin master'

    That is the same as:

    .. code-block:: bash

        git rebase master
        git rebase origin master
    '''
    _check_git()

    if not opts:
        opts = ''
    return _git_run('git rebase {0} {1}'.format(opts, rev),
                    cwd=cwd,
                    runas=user)


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

    CLI Examples:

    .. code-block:: bash

        salt '*' git.checkout /path/to/repo somebranch user=jeff

        salt '*' git.checkout /path/to/repo opts='testbranch -- conf/file1 file2'

        salt '*' git.checkout /path/to/repo rev=origin/mybranch opts=--track
    '''
    _check_git()

    if not opts:
        opts = ''
    cmd = 'git checkout {0} {1} {2}'.format(' -f' if force else '', rev, opts)
    return _git_run(cmd, cwd=cwd, runas=user)


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

    CLI Example:

    .. code-block:: bash

        salt '*' git.fetch /path/to/repo
        salt '*' git.merge /path/to/repo @{upstream}
    '''
    _check_git()

    if not opts:
        opts = ''
    cmd = 'git merge {0} {1}'.format(branch,
                                     opts)

    return _git_run(cmd, cwd, runas=user)


def init(cwd, opts=None, user=None):
    '''
    Initialize a new git repository

    cwd
        The path to the Git repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' git.init /path/to/repo.git opts='--bare'
    '''
    _check_git()
    if not opts:
        opts = ''
    cmd = 'git init {0} {1}'.format(cwd, opts)
    return _git_run(cmd, runas=user)


def submodule(cwd, init=True, opts=None, user=None, identity=None):
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

    identity : None
        A path to a private key to use over SSH

    CLI Example:

    .. code-block:: bash

        salt '*' git.submodule /path/to/repo.git/sub/repo
    '''
    _check_git()

    if not opts:
        opts = ''
    cmd = 'git submodule update {0} {1}'.format('--init' if init else '', opts)
    return _git_run(cmd, cwd=cwd, runas=user, identity=identity)


def status(cwd, user=None):
    '''
    Return the status of the repository. The returned format uses the status
    codes of git's 'porcelain' output mode

    cwd
        The path to the Git repository

    user : None
        Run git as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' git.status /path/to/git/repo
    '''
    cmd = 'git status -z --porcelain'
    stdout = _git_run(cmd, cwd=cwd, runas=user)
    state_by_file = []
    for line in stdout.split("\0"):
        state = line[:2]
        filename = line[3:]
        if filename != '' and state != '':
            state_by_file.append((state, filename))
    return state_by_file


def add(cwd, file_name, user=None, opts=None):
    '''
    add a file to git

    cwd
        The path to the Git repository

    file_name
        Path to the file in the cwd

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' git.add /path/to/git/repo /path/to/file

    '''

    if not opts:
        opts = ''
    cmd = 'git add {0} {1}'.format(file_name, opts)
    return _git_run(cmd, cwd=cwd, runas=user)


def rm(cwd, file_name, user=None, opts=None):
    '''
    Remove a file from git

    cwd
        The path to the Git repository

    file_name
        Path to the file in the cwd

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' git.rm /path/to/git/repo /path/to/file
    '''

    if not opts:
        opts = ''
    cmd = 'git rm {0} {1}'.format(file_name, opts)
    return _git_run(cmd, cwd=cwd, runas=user)


def commit(cwd, message, user=None, opts=None):
    '''
    create a commit

    cwd
        The path to the Git repository

    message
        The commit message

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' git.commit /path/to/git/repo 'The commit message'
    '''

    cmd = subprocess.list2cmdline(['git', 'commit', '-m', message])
    # add opts separately; they don't need to be quoted
    if opts:
        cmd = cmd + ' ' + opts
    return _git_run(cmd, cwd=cwd, runas=user)


def push(cwd, remote_name, branch='master', user=None, opts=None,
         identity=None):
    '''
    Push to remote

    cwd
        The path to the Git repository

    remote_name
        Name of the remote to push to

    branch : master
        Name of the branch to push

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    identity : None
        A path to a private key to use over SSH


    CLI Example:

    .. code-block:: bash

        salt '*' git.push /path/to/git/repo remote-name
    '''

    if not opts:
        opts = ''
    cmd = 'git push {0} {1} {2}'.format(remote_name, branch, opts)
    return _git_run(cmd, cwd=cwd, runas=user, identity=identity)


def remotes(cwd, user=None):
    '''
    Get remotes like git remote -v

    cwd
        The path to the Git repository

    user : None
        Run git as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' git.remotes /path/to/repo
    '''
    cmd = 'git remote'
    ret = _git_run(cmd, cwd=cwd, runas=user)
    res = dict()
    for remote_name in ret.splitlines():
        remote = remote_name.strip()
        res[remote] = remote_get(cwd, remote, user=user)
    return res


def remote_get(cwd, remote='origin', user=None):
    '''
    get the fetch and push URL for a specified remote name

    remote : origin
        the remote name used to define the fetch and push URL

    user : None
        Run git as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' git.remote_get /path/to/repo
        salt '*' git.remote_get /path/to/repo upstream
    '''
    try:
        cmd = 'git remote show -n {0}'.format(remote)
        ret = _git_run(cmd, cwd=cwd, runas=user)
        lines = ret.splitlines()
        remote_fetch_url = lines[1].replace('Fetch URL: ', '').strip()
        remote_push_url = lines[2].replace('Push  URL: ', '').strip()
        if remote_fetch_url != remote and remote_push_url != remote:
            res = (remote_fetch_url, remote_push_url)
            return res
        else:
            return None
    except CommandExecutionError:
        return None


def remote_set(cwd, name='origin', url=None, user=None, https_user=None,
               https_pass=None):
    '''
    sets a remote with name and URL like git remote add <remote_name> <remote_url>

    remote_name : origin
        defines the remote name

    remote_url : None
        defines the remote URL; should not be None!

    user : None
        Run git as a user other than what the minion runs as

    https_user : None
        HTTP Basic Auth username for HTTPS (only) clones

        .. versionadded:: 2015.5.0

    https_pass : None
        HTTP Basic Auth password for HTTPS (only) clones

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' git.remote_set /path/to/repo remote_url=git@github.com:saltstack/salt.git
        salt '*' git.remote_set /path/to/repo origin git@github.com:saltstack/salt.git
    '''
    if remote_get(cwd, name):
        cmd = 'git remote rm {0}'.format(name)
        _git_run(cmd, cwd=cwd, runas=user)
    url = _add_http_basic_auth(url, https_user, https_pass)
    cmd = 'git remote add {0} {1}'.format(name, url)
    _git_run(cmd, cwd=cwd, runas=user)
    return remote_get(cwd=cwd, remote=name, user=None)


def branch(cwd, rev, opts=None, user=None):
    '''
    Interacts with branches.

    cwd
        The path to the Git repository

    rev
        The branch/revision to be used in the command.

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' git.branch mybranch --set-upstream-to=origin/mybranch
    '''
    cmd = 'git branch {0} {1}'.format(rev, opts)
    _git_run(cmd, cwd=cwd, user=user)
    return current_branch(cwd, user=user)


def reset(cwd, opts=None, user=None):
    '''
    Reset the repository checkout

    cwd
        The path to the Git repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' git.reset /path/to/repo master
    '''
    _check_git()

    if not opts:
        opts = ''
    return _git_run('git reset {0}'.format(opts), cwd=cwd, runas=user)


def stash(cwd, opts=None, user=None):
    '''
    Stash changes in the repository checkout

    cwd
        The path to the Git repository

    opts : None
        Any additional options to add to the command line

    user : None
        Run git as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' git.stash /path/to/repo master
    '''
    _check_git()

    if not opts:
        opts = ''
    return _git_run('git stash {0}'.format(opts), cwd=cwd, runas=user)


def config_set(cwd=None, setting_name=None, setting_value=None, user=None, is_global=False):
    '''
    Set a key in the git configuration file (.git/config) of the repository or
    globally.

    cwd : None
        Options path to the Git repository

        .. versionchanged:: 2014.7.0
            Made ``cwd`` optional

    setting_name : None
        The name of the configuration key to set. Required.

    setting_value : None
        The (new) value to set. Required.

    user : None
        Run git as a user other than what the minion runs as

    is_global : False
        Set to True to use the '--global' flag with 'git config'

    CLI Example:

    .. code-block:: bash

        salt '*' git.config_set /path/to/repo user.email me@example.com
    '''
    if setting_name is None or setting_value is None:
        raise TypeError('Missing required parameter setting_name for git.config_set')
    if cwd is None and not is_global:
        raise SaltInvocationError('Either `is_global` must be set to True or '
                                  'you must provide `cwd`')

    if is_global:
        cmd = 'git config --global {0} "{1}"'.format(setting_name, setting_value)
    else:
        cmd = 'git config {0} "{1}"'.format(setting_name, setting_value)

    _check_git()

    return _git_run(cmd, cwd=cwd, runas=user)


def config_get(cwd=None, setting_name=None, user=None):
    '''
    Get a key or keys from the git configuration file (.git/config).

    cwd : None
        Optional path to a Git repository

        .. versionchanged:: 2014.7.0
            Made ``cwd`` optional

    setting_name : None
        The name of the configuration key to get. Required.

    user : None
        Run git as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' git.config_get setting_name=user.email
        salt '*' git.config_get /path/to/repo user.name arthur
    '''
    if setting_name is None:
        raise TypeError('Missing required parameter setting_name for git.config_get')
    _check_git()

    return _git_run('git config {0}'.format(setting_name), cwd=cwd, runas=user)


def ls_remote(cwd, repository="origin", branch="master", user=None,
              identity=None, https_user=None, https_pass=None):
    '''
    Returns the upstream hash for any given URL and branch.

    cwd
        The path to the Git repository

    repository: origin
        The name of the repository to get the revision from. Can be the name of
        a remote, an URL, etc.

    branch: master
        The name of the branch to get the revision from.

    user : none
        run git as a user other than what the minion runs as

    identity : none
        a path to a private key to use over ssh

    https_user : None
        HTTP Basic Auth username for HTTPS (only) clones

        .. versionadded:: 2015.5.0

    https_pass : None
        HTTP Basic Auth password for HTTPS (only) clones

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' git.ls_remote /pat/to/repo origin master

    '''
    _check_git()
    repository = _add_http_basic_auth(repository, https_user, https_pass)
    cmd = ' '.join(["git", "ls-remote", "-h", str(repository), str(branch), "| cut -f 1"])
    return _git_run(cmd, cwd=cwd, runas=user, identity=identity)
