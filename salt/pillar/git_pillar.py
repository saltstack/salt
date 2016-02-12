# -*- coding: utf-8 -*-
'''
Use a git repository as a Pillar source
---------------------------------------

.. note::
    This external pillar has been rewritten for the :doc:`2015.8.0
    </topics/releases/2015.8.0>` release. The old method of configuring this
    external pillar will be maintained for a couple releases, allowing time for
    configurations to be updated to reflect the new usage.

This external pillar allows for a Pillar top file and Pillar SLS files to be
sourced from a git repository.

However, since git_pillar does not have an equivalent to the
:conf_master:`pillar_roots` parameter, configuration is slightly different. A
Pillar top file is required to be in the git repository and must still contain
the relevant environment, like so:

.. code-block:: yaml

    base:
      '*':
        - foo

The branch/tag which maps to that environment must then be specified along with
the repo's URL. Configuration details can be found below.


.. _git-pillar-pre-2015-8-0:

Configuring git_pillar for Salt releases before 2015.8.0
========================================================

For Salt releases earlier than :doc:`2015.8.0 </topics/releases/2015.8.0>`,
GitPython is the only supported provider for git_pillar. Individual
repositories can be configured under the :conf_master:`ext_pillar`
configuration parameter like so:

.. code-block:: yaml

    ext_pillar:
      - git: master https://gitserver/git-pillar.git root=subdirectory

The repository is specified in the format ``<branch> <repo_url>``, with an
optional ``root`` parameter (added in the :doc:`2014.7.0
</topics/releases/2014.7.0>` release) which allows the pillar SLS files to be
served up from a subdirectory (similar to :conf_master:`gitfs_root` in gitfs).

To use more than one branch from the same repo, multiple lines must be
specified under :conf_master:`ext_pillar`:

.. code-block:: yaml

    ext_pillar:
      - git: master https://gitserver/git-pillar.git
      - git: dev https://gitserver/git-pillar.git

To remap a specific branch to a specific Pillar environment, use the format
``<branch>:<env>``:

.. code-block:: yaml

    ext_pillar:
      - git: develop:dev https://gitserver/git-pillar.git
      - git: master:prod https://gitserver/git-pillar.git

In this case, the ``develop`` branch would need its own ``top.sls`` with a
``dev`` section in it, like this:

.. code-block:: yaml

    dev:
      '*':
        - bar

The ``master`` branch would need its own ``top.sls`` with a ``prod`` section in
it:

.. code-block:: yaml

    prod:
      '*':
        - bar

If ``__env__`` is specified as the branch name, then git_pillar will use the
branch specified by :conf_master:`gitfs_base`:

.. code-block:: yaml

    ext_pillar:
      - git: __env__ https://gitserver/git-pillar.git root=pillar

The corresponding Pillar top file would look like this:

.. code-block:: yaml

    {{env}}:
      '*':
        - bar

.. _git-pillar-2015-8-0-and-later:

Configuring git_pillar for Salt releases 2015.8.0 and later
===========================================================

.. note::
    In version 2015.8.0, the method of configuring git external pillars has
    changed, and now more closely resembles that of the :ref:`Git Fileserver
    Backend <tutorial-gitfs>`. If Salt detects the old configuration schema, it
    will use the pre-2015.8.0 code to compile the external pillar. A warning
    will also be logged.

Beginning with Salt version 2015.8.0, pygit2_ is now supported in addition to
GitPython_ (Dulwich_ will not be supported for the forseeable future). The
requirements for GitPython_ and pygit2_ are the same as for gitfs, as described
:ref:`here <gitfs-dependencies>`.

.. important::
    git_pillar has its own set of global configuration parameters. While it may
    seem intuitive to use the global gitfs configuration parameters
    (:conf_master:`gitfs_base`, etc.) to manage git_pillar, this will not work.
    The main difference for this is the fact that the different components
    which use Salt's git backend code do not all function identically. For
    instance, in git_pillar it is necessary to specify which branch/tag to be
    used for git_pillar remotes. This is the reverse behavior from gitfs, where
    branches/tags make up your environments.

    See :ref:`here <git_pillar-config-opts>` for documentation on the
    git_pillar configuration options and their usage.

Here is an example git_pillar configuration:

.. code-block:: yaml

    ext_pillar:
      - git:
        # Use 'prod' instead of the branch name 'production' as the environment
        - production https://gitserver/git-pillar.git:
          - env: prod
        # Use 'dev' instead of the branch name 'develop' as the environment
        - develop https://gitserver/git-pillar.git:
          - env: dev
        # No per-remote config parameters (and no trailing colon), 'qa' will
        # be used as the environment
        - qa https://gitserver/git-pillar.git
        # SSH key authentication
        - master git@other-git-server:pillardata-ssh.git:
          # Pillar SLS files will be read from the 'pillar' subdirectory in
          # this repository
          - root: pillar
          - privkey: /path/to/key
          - pubkey: /path/to/key.pub
          - passphrase: CorrectHorseBatteryStaple
        # HTTPS authentication
        - master https://other-git-server/pillardata-https.git:
          - user: git
          - password: CorrectHorseBatteryStaple

The main difference between this and the old way of configuring git_pillar is
that multiple remotes can be configured under one ``git`` section under
:conf_master:`ext_pillar`. More than one ``git`` section can be used, but it is
not necessary. Remotes will be evaluated sequentially.

Per-remote configuration parameters are supported (similar to :ref:`gitfs
<gitfs-per-remote-config>`), and global versions of the git_pillar
configuration parameters can also be set.

With the addition of pygit2_ support, git_pillar can now interact with
authenticated remotes. Authentication works just like in gitfs (as outlined in
the :ref:`Git Fileserver Backend Walkthrough <gitfs-authentication>`), only
with the global authenication parameter names prefixed with ``git_pillar``
instead of ``gitfs`` (e.g. :conf_master:`git_pillar_pubkey`,
:conf_master:`git_pillar_privkey`, :conf_master:`git_pillar_passphrase`, etc.).

.. _GitPython: https://github.com/gitpython-developers/GitPython
.. _pygit2: https://github.com/libgit2/pygit2
.. _Dulwich: https://www.samba.org/~jelmer/dulwich/
'''
from __future__ import absolute_import

# Import python libs
import copy
import logging
import hashlib
import os

# Import salt libs
import salt.utils.gitfs
import salt.utils.dictupdate
from salt.exceptions import FileserverConfigError
from salt.pillar import Pillar

# Import third party libs
import salt.ext.six as six
# pylint: disable=import-error
try:
    import git
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False
# pylint: enable=import-error

PER_REMOTE_OVERRIDES = ('env', 'root', 'ssl_verify')

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'git'


def __virtual__():
    '''
    Only load if gitpython is available
    '''
    git_ext_pillars = [x for x in __opts__['ext_pillar'] if 'git' in x]
    if not git_ext_pillars:
        # No git external pillars were configured
        return False

    for ext_pillar in git_ext_pillars:
        if isinstance(ext_pillar['git'], six.string_types):
            # Verification of legacy git pillar configuration
            if not HAS_GITPYTHON:
                log.error(
                    'Git-based ext_pillar is enabled in configuration but '
                    'could not be loaded, is GitPython installed?'
                )
                return False
            if not git.__version__ > '0.3.0':
                return False
            return __virtualname__
        else:
            # Verification of new git pillar configuration
            try:
                salt.utils.gitfs.GitPillar(__opts__)
                # Initialization of the GitPillar object did not fail, so we
                # know we have valid configuration syntax and that a valid
                # provider was detected.
                return __virtualname__
            except FileserverConfigError:
                pass
    return False


def ext_pillar(minion_id, repo, pillar_dirs):
    '''
    Checkout the ext_pillar sources and compile the resulting pillar SLS
    '''
    if isinstance(repo, six.string_types):
        return _legacy_git_pillar(minion_id, repo, pillar_dirs)
    else:
        opts = copy.deepcopy(__opts__)
        opts['pillar_roots'] = {}
        pillar = salt.utils.gitfs.GitPillar(opts)
        pillar.init_remotes(repo, PER_REMOTE_OVERRIDES)
        pillar.checkout()
        ret = {}
        merge_strategy = __opts__.get(
            'pillar_source_merging_strategy',
            'smart'
        )
        merge_lists = __opts__.get(
            'pillar_merge_lists',
            False
        )
        for pillar_dir, env in six.iteritems(pillar.pillar_dirs):
            log.debug(
                'git_pillar is processing pillar SLS from {0} for pillar '
                'env \'{1}\''.format(pillar_dir, env)
            )
            all_dirs = [d for (d, e) in six.iteritems(pillar.pillar_dirs)
                        if env == e]

            # Ensure that the current pillar_dir is first in the list, so that
            # the pillar top.sls is sourced from the correct location.
            pillar_roots = [pillar_dir]
            pillar_roots.extend([x for x in all_dirs if x != pillar_dir])
            opts['pillar_roots'] = {env: pillar_roots}

            local_pillar = Pillar(opts, __grains__, minion_id, env)
            ret = salt.utils.dictupdate.merge(
                ret,
                local_pillar.compile_pillar(ext=False),
                strategy=merge_strategy,
                merge_lists=merge_lists
            )
        return ret


# Legacy git_pillar code
class _LegacyGitPillar(object):
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
                    self.repo.remotes.origin.config_writer.set(
                        'url', self.rp_location)

    def map_branch(self, branch, opts=None):
        opts = __opts__ if opts is None else opts
        if branch == '__env__':
            branch = opts.get('environment') or 'base'
            if branch == 'base':
                branch = opts.get('gitfs_base') or 'master'
        elif ':' in branch:
            branch = branch.split(':', 1)[0]
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
            log.error('Unable to checkout branch '
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


def _legacy_git_pillar(minion_id, repo_string, pillar_dirs):
    '''
    Support pre-Beryllium config schema
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
                      'Missing \'{0}\': {1}'.format(DELIM, extraopt))
        key, val = _extract_key_val(extraopt, DELIM)
        if key == 'root':
            root = val
        else:
            log.warning('Unrecognized extra parameter: {0}'.format(key))

    # environment is "different" from the branch
    cfg_branch, _, environment = branch_env.partition(':')

    gitpil = _LegacyGitPillar(cfg_branch, repo_location, __opts__)
    branch = gitpil.branch

    if environment == '':
        if branch == 'master':
            environment = 'base'
        else:
            environment = branch

    # normpath is needed to remove appended '/' if root is empty string.
    pillar_dir = os.path.normpath(os.path.join(gitpil.working_dir, root))

    pillar_dirs.setdefault(pillar_dir, {})

    if cfg_branch == '__env__' and branch not in ['master', 'base']:
        gitpil.update()
    elif pillar_dirs[pillar_dir].get(branch, False):
        return {}  # we've already seen this combo

    pillar_dirs[pillar_dir].setdefault(branch, True)

    # Don't recurse forever-- the Pillar object will re-call the ext_pillar
    # function
    if __opts__['pillar_roots'].get(branch, []) == [pillar_dir]:
        return {}

    opts = copy.deepcopy(__opts__)

    opts['pillar_roots'][environment] = [pillar_dir]

    pil = Pillar(opts, __grains__, minion_id, branch)

    return pil.compile_pillar(ext=False)


def _update(branch, repo_location):
    '''
    Ensure you are following the latest changes on the remote

    return boolean whether it worked
    '''
    gitpil = _LegacyGitPillar(branch, repo_location, __opts__)

    return gitpil.update()


def _envs(branch, repo_location):
    '''
    Return a list of refs that can be used as environments
    '''
    gitpil = _LegacyGitPillar(branch, repo_location, __opts__)

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
