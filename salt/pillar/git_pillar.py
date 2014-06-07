# -*- coding: utf-8 -*-
'''
Clone a remote git repository and use the filesystem as a Pillar source

This external Pillar source can be configured in the master config file like
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


class GitPillar(object):
    '''
    Deal with the remote git repository for Pillar
    '''

    def __init__(self, branch, repo_location, opts):
        '''
        Try to initilize the Git repo object
        '''
        self.branch = branch
        self.rp_location = repo_location
        self.opts = opts
        self._envs = set()
        self.working_dir = ''
        self.repo = None

        for idx, opts_dict in enumerate(self.opts['ext_pillar']):

            # self.opts['ext_pillar'] always contains full ext_pillar list
            if 'git' not in opts_dict:
                continue

            parts = opts_dict.get('git', '').split()

            # parts = 2: 'master' 'git_repo_uri'
            # parts = 3: 'master' 'git_repo_uri' 'root=pillars_dir'
            if len(parts) == 2:
                self.branch = parts[0]
                self.rp_location = parts[1]
            elif len(parts) == 3:
                self.branch = parts[0]
                self.rp_location = parts[1]
                self.root = parts[2]
            else:
                log.error("Unable to initilize GitPillar with ext_pillar: %s",
                          opts_dict.get('git', None))
                break

            rp_ = os.path.join(self.opts['cachedir'],
                               'pillar_gitfs', str(idx))

            if not os.path.isdir(rp_):
                os.makedirs(rp_)

            try:
                self.repo = git.Repo.init(rp_)
            except (git.exc.NoSuchPathError,
                    git.exc.InvalidGitRepositoryError) as exc:
                log.error('GitPython exception caught while '
                          'initializing the repo: {0}. Maybe '
                          'git is not available.'.format(exc))

            self.working_dir = rp_
            if isinstance(self.repo, git.Repo):
                if not self.repo.remotes:
                    try:
                        self.repo.create_remote('origin', self.rp_location)
                        # ignore git ssl verification if requested
                        if self.opts.get('pillar_gitfs_ssl_verify', True):
                            self.repo.git.config('http.sslVerify', 'true')
                        else:
                            self.repo.git.config('http.sslVerify', 'false')
                    except os.error:
                        # This exception occurs when two processes are
                        # trying to write to the git config at once, go
                        # ahead and pass over it since this is the only
                        # write.
                        # This should place a lock down.
                        pass
            break

    def update(self):
        '''
        Ensure you are following the latest changes on the remote

        Return boolean wether it worked
        '''
        try:
            log.debug('Updating fileserver for git_pillar module')
            self.repo.git.fetch()
        except git.exc.GitCommandError as exc:
            log.error('Unable to fetch the latest changes from remote '
                      '{0}: {1}'.format(self.rp_location, exc))
            return False

        try:
            self.repo.git.checkout('origin/{0}'.format(self.branch))
        except git.exc.GitCommandError as exc:
            logging.error('Unable to checkout branch '
                          '{0}: {1}'.format(self.branch, exc))
            return False

        return True

    def envs(self):
        '''
        Return a list of refs that can be used as environments
        '''

        if isinstance(self.repo, git.Repo):
            remote = self.repo.remote()
            for ref in self.repo.refs:
                parted = ref.name.partition('/')
                short = parted[2] if parted[2] else parted[0]
                if isinstance(ref, git.Head):
                    if short == 'master':
                        short = 'base'
                    if ref not in remote.stale_refs:
                        self._envs.add(short)
                elif isinstance(ref, git.Tag):
                    self._envs.add(short)

        return list(self._envs)


def update(branch, repo_location):
    '''
    Ensure you are following the latest changes on the remote

    return boolean whether it worked
    '''
    gitpil = GitPillar(branch, repo_location, __opts__)

    return gitpil.update()


def envs(branch, repo_location):
    '''
    Return a list of refs that can be used as environments
    '''
    gitpil = GitPillar(branch, repo_location, __opts__)

    return gitpil.envs()


def _get_pillars_root_dir(parts, delim='='):
    '''
    Return the directory name from git repo to update pillars
    '''
    # NB: Only interested in pillar_roots, ignoring others.
    if not parts:
        return ''

    if len(parts) > 1:
        log.error("There are more K=V params than expected: %s", "".join(parts))
        return ''

    key, _dir = parts[0].split(delim)
    if key != 'root':
        log.warn("invalid extra key=val: %s=%s passed. Ignoring entry.",
                 key, _dir)
        return ''
    return _dir


def ext_pillar(minion_id, pillar, repo_string):
    '''
    Execute a command and read the output as YAML
    '''
    # split the branch and repo name
    parts = repo_string.strip().split()

    try:
        branch = parts[0]
        repo_location = parts[1]
    except IndexError:
        log.error("Unable to extract git branch and repo_location: %s",
                  "".join(parts))

    root = _get_pillars_root_dir(parts[2:])
    gitpil = GitPillar(branch, repo_location, __opts__)

    pillar_dir = os.path.normpath(os.path.join(gitpil.working_dir, root))

    # environment is "different" from the branch
    branch = (branch == 'master' and 'base' or branch)

    # Don't recurse forever-- the Pillar object will re-call
    # the ext_pillar function
    if __opts__['pillar_roots'].get(branch, []) == [pillar_dir]:
        return {}

    gitpil.update()

    opts = deepcopy(__opts__)

    opts['pillar_roots'][branch] = [pillar_dir]

    pil = Pillar(opts, __grains__, minion_id, branch)

    return pil.compile_pillar()
