# -*- coding: utf-8 -*-
'''
Clone a remote git repository and use the filesystem as a Pillar source

Currently GitPython is the only supported provider for git Pillars

This external Pillar source can be configured in the master config file like
so:

.. code-block:: yaml

    ext_pillar:
      - git: master git://gitserver/git-pillar.git root=subdirectory

The `root=` parameter is optional and used to set the subdirectory from where
to look for Pillar files (such as ``top.sls``).

.. versionchanged:: 2014.7.0
    The optional ``root`` parameter will be added.

.. versionchanged:: 2015.5.0
    The special branch name '__env__' will be replace by the
    environment ({{env}})

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

To remap a specific branch to a specific environment separate the branch name
and the environment name with a colon:

.. code-block:: yaml

    ext_pillar:
      - git: develop:dev git://gitserver/git-pillar.git
      - git: master:prod git://gitserver/git-pillar.git

In this case, the ``dev`` branch would need its own ``top.sls`` with a ``dev``
section in it, like this:

.. code-block:: yaml

    dev:
      '*':
        - bar

In a gitfs base setup with pillars from the same repository as the states,
the ``ext_pillar:`` configuration would be like:

.. code-block:: yaml

    ext_pillar:
      - git: __env__ git://gitserver/git-pillar.git root=pillar

The (optional) root=pillar defines the directory that contains the pillar data.
The corresponding ``top.sls`` would be like:

.. code-block:: yaml

    {{env}}:
      '*':
        - bar
'''
from __future__ import absolute_import

# Import python libs
from copy import deepcopy
import logging
import hashlib
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
        Try to initialize the Git repo object
        '''
        self.branch = self.map_branch(branch, opts)
        self.rp_location = repo_location
        self.opts = opts
        self._envs = set()
        self.working_dir = ''
        self.repo = None

        hash_type = getattr(hashlib, opts.get('hash_type', 'md5'))
        hash_str = '{0} {1}'.format(self.branch, self.rp_location)
        repo_hash = hash_type(hash_str).hexdigest()
        rp_ = os.path.join(self.opts['cachedir'], 'pillar_gitfs', repo_hash)

        if not os.path.isdir(rp_):
            os.makedirs(rp_)

        try:
            self.repo = git.Repo.init(rp_)
        except (git.exc.NoSuchPathError,
                git.exc.InvalidGitRepositoryError) as exc:
            log.error('GitPython exception caught while '
                      'initializing the repo: {0}. Maybe '
                      'git is not available.'.format(exc))

        # Git directory we are working on
        # Should be the same as self.repo.working_dir
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
            else:
                if self.repo.remotes.origin.url != self.rp_location:
                    self.repo.remotes.origin.config_writer.set('url', self.rp_location)

    def map_branch(self, branch, opts=None):
        opts = __opts__ if opts is None else opts
        if branch == '__env__':
            branch = opts.get('environment') or 'base'
            if branch == 'base':
                branch = opts.get('gitfs_base') or 'master'
        return branch

    def update(self):
        '''
        Ensure you are following the latest changes on the remote

        Return boolean whether it worked
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


def _extract_key_val(kv, delimiter='='):
    '''Extract key and value from key=val string.

    Example:
    >>> _extract_key_val('foo=bar')
    ('foo', 'bar')
    '''
    pieces = kv.split(delimiter)
    key = pieces[0]
    val = delimiter.join(pieces[1:])
    return key, val


def ext_pillar(minion_id,
               repo_string,
               pillar_dirs):
    '''
    Execute a command and read the output as YAML
    '''
    if pillar_dirs is None:
        return
    # split the branch, repo name and optional extra (key=val) parameters.
    options = repo_string.strip().split()
    branch_env = options[0]
    repo_location = options[1]
    root = ''

    for extraopt in options[2:]:
        # Support multiple key=val attributes as custom parameters.
        DELIM = '='
        if DELIM not in extraopt:
            log.error('Incorrectly formatted extra parameter. '
                      'Missing {0!r}: {1}'.format(DELIM, extraopt))
        key, val = _extract_key_val(extraopt, DELIM)
        if key == 'root':
            root = val
        else:
            log.warning('Unrecognized extra parameter: {0}'.format(key))

    # environment is "different" from the branch
    branch, _, environment = branch_env.partition(':')

    gitpil = GitPillar(branch, repo_location, __opts__)
    branch = gitpil.branch

    if environment == '':
        if branch == 'master':
            environment = 'base'
        else:
            environment = branch

    # normpath is needed to remove appended '/' if root is empty string.
    pillar_dir = os.path.normpath(os.path.join(gitpil.working_dir, root))

    pillar_dirs.setdefault(pillar_dir, {})

    if pillar_dirs[pillar_dir].get(branch, False):
        return {}  # we've already seen this combo

    pillar_dirs[pillar_dir].setdefault(branch, True)

    # Don't recurse forever-- the Pillar object will re-call the ext_pillar
    # function
    if __opts__['pillar_roots'].get(branch, []) == [pillar_dir]:
        return {}

    gitpil.update()

    opts = deepcopy(__opts__)

    opts['pillar_roots'][environment] = [pillar_dir]

    pil = Pillar(opts, __grains__, minion_id, branch)

    return pil.compile_pillar()
