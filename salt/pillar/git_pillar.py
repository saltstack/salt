# -*- coding: utf-8 -*-
'''
Clone a remote git repository and use the filesystem as a pillar directory.

This external pillar source can be configured in the master config file like
so:

.. code-block:: yaml

    ext_pillar:
      - git: master git://gitserver/git-pillar.git

Note that this is not the same thing as configuring pillar data using the
:conf_master:`pillar_roots` parameter. The branch referenced in the
:conf_master:`ext_pillar` entry above (``master``), would evaluate to the
``base`` environment, so this branch needs to contain a ``top.sls`` with a
``base`` section in it, like this:

.. code-block:: yaml

    base:
      '*':
        - foo

To use other environments from the same git repo as git_pillar sources, just
add additional lines, like so:

.. code-block:: yaml

    ext_pillar:
      - git: master git://gitserver/git-pillar.git
      - git: dev git://gitserver/git-pillar.git

In this case, the ``dev`` branch would need its own ``top.sls`` with a ``dev``
section in it, like this:

.. code-block:: yaml

    dev:
      '*':
        - bar
'''

# Import python libs
from copy import deepcopy
import logging
import os

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

# Define the module's virtual name
__virtualname__ = 'git'


def __virtual__():
    '''
    Only load if gitpython is available
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
    return __virtualname__


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
    Ensure you are on the right branch, and execute a git pull

    return boolean whether it worked
    '''
    pid = os.getpid()
    repo = init(branch, repo_location)
    try:
        repo.git.checkout("origin/" + branch)
    except git.exc.GitCommandError as e:
        logging.error('Unable to checkout branch {0}: {1}'.format(branch, e))
        return False
    return True


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


def ext_pillar(minion_id, pillar, repo_string):
    '''
    Execute a command and read the output as YAML
    '''
    # split the branch and repo name
    branch, repo_location = repo_string.strip().split()

    # environment is "different" from the branch
    branch_env = branch
    if branch_env == 'master':
        branch_env = 'base'

    # Update first
    if not update(branch, repo_location):
        return {}

    # get the repo
    repo = init(branch, repo_location)

    # Don't recurse forever-- the Pillar object will re-call the ext_pillar
    # function
    if __opts__['pillar_roots'].get(branch_env, []) == [repo.working_dir]:
        return {}

    opts = deepcopy(__opts__)

    opts['pillar_roots'][branch_env] = [repo.working_dir]

    pil = Pillar(opts, __grains__, minion_id, 'base')

    return pil.compile_pillar()
