'''
Clone a remote git repository and use the filesystem as a pillar directory.

This looks like:

ext_pillar:
    - git: master git://gitserver/git-pillar.git

'''

# Import python libs
from copy import deepcopy
import logging
import os
import time

# Import third party libs
HAS_GIT = False
try:
    import git
    HAS_GIT = True
except ImportError:
    pass

# Import salt libs
from salt.pillar import Pillar


# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if git-python is available
    '''
    ext_pillar_sources = [x for x in __opts__.get('ext_pillar', [])]
    if not any(['git' in x for x in ext_pillar_sources]):
        return False
    if not HAS_GIT:
        log.error('Git-based ext_pillar is enabled in configuration but '
                  'could not be loaded, is GitPython installed?')
        return False
    if not git.__version__ > '0.3.0':
        return False
    return 'git'

def _get_ref(repo, short):
    '''
    Return bool if the short ref is in the repo
    '''
    for ref in repo.refs:
        if isinstance(ref, git.RemoteReference):
            parted = ref.name.partition('/')
            refname = parted[2] if parted[2] else parted[0]
            if short == refname:
                return ref
    return False


def _wait_lock(lk_fn, dest):
    '''
    If the write lock is there, check to see if the file is actually being
    written. If there is no change in the file size after a short sleep,
    remove the lock and move forward.
    '''
    if not os.path.isfile(lk_fn):
        return False
    if not os.path.isfile(dest):
        # The dest is not here, sleep for a bit, if the dest is not here yet
        # kill the lockfile and start the write
        time.sleep(1)
        if not os.path.isfile(dest):
            try:
                os.remove(lk_fn)
            except (OSError, IOError):
                pass
            return False
    # There is a lock file, the dest is there, stat the dest, sleep and check
    # that the dest is being written, if it is not being written kill the lock
    # file and continue. Also check if the lock file is gone.
    s_count = 0
    s_size = os.stat(dest).st_size
    while True:
        time.sleep(1)
        if not os.path.isfile(lk_fn):
            return False
        size = os.stat(dest).st_size
        if size == s_size:
            s_count += 1
            if s_count >= 3:
                # The file is not being written to, kill the lock and proceed
                try:
                    os.remove(lk_fn)
                except (OSError, IOError):
                    pass
                return False
        else:
            s_size = size
    return False

def init(branch, repo_location):
    '''
    Return the git repo object for this session
    '''
    # get index
    ind = None
    for index, opts_dict in enumerate(__opts__['ext_pillar']):
        if opts_dict.get('git', '') == '{0} {1}'.format(branch, repo_location):
            ind = index
            break

    if ind is None:
        return None

    rp_ = os.path.join(__opts__['cachedir'], 'pillar_gitfs', str(ind))

    if not os.path.isdir(rp_):
        os.makedirs(rp_)
    repo = git.Repo.init(rp_)
    if not repo.remotes:
        try:
            repo.create_remote('origin', repo_location)
        except Exception:
            pass
    repo.git.fetch()
    return repo

def update(branch, repo_location):
    '''
    Execute a git pull on all of the repos
    '''
    pid = os.getpid()
    repo = init(branch, repo_location)
    origin = repo.remotes[0]
    lk_fn = os.path.join(repo.working_dir, 'update.lk')
    with open(lk_fn, 'w+') as fp_:
        fp_.write(str(pid))
    origin.fetch()
    try:
        os.remove(lk_fn)
    except (OSError, IOError):
        pass


def envs(branch, repo_location):
    '''
    Return a list of refs that can be used as environments
    '''
    ret = set()
    repo = init(branch, repo_location)

    remote = repo.remote()
    for ref in repo.refs:
        parted = ref.name.partition('/')
        short = parted[2] if parted[2] else parted[0]
        if isinstance(ref, git.Head):
            if short == 'master':
                short = 'base'
            if ref not in remote.stale_refs:
                ret.add(short)
        elif isinstance(ref, git.Tag):
            ret.add(short)
    return list(ret)


def ext_pillar(pillar, repo_string):
    '''
    Execute a command and read the output as YAML
    '''
    # split the branch and repo name
    branch, repo_location = repo_string.strip().split()

    # environment is "different" from the branch
    branch_env = branch
    if branch_env == 'master':
        branch_env = 'base'

    # make sure you have the branch
    if branch_env not in envs(branch, repo_location):
        # don't have that branch
        logging.warning('Unable to get branch {0} of git repo {1}, branch does not exit'.format(branch, repo_location))
        return {}

    # get the repo
    repo = init(branch, repo_location)

    # Don't recurse forever-- the Pillar object will re-call the ext_pillar function
    if __opts__['pillar_roots'][branch_env] == [repo.working_dir]:
        return {}

    update(branch, repo_location)
    git_ = repo.git

    git_.checkout(branch)

    opts = deepcopy(__opts__)

    opts['pillar_roots'][branch_env] = [repo.working_dir]

    pil = Pillar(opts, __grains__, __grains__['id'], 'base')

    return pil.compile_pillar()

