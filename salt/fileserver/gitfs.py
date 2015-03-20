# -*- coding: utf-8 -*-
'''
Git Fileserver Backend

With this backend, branches and tags in a remote git repository are exposed to
salt as different environments.

To enable, add ``git`` to the :conf_master:`fileserver_backend` option in the
Master config file.

.. code-block:: yaml

    fileserver_backend:
      - git

As of Salt 2014.7.0, the Git fileserver backend supports GitPython_, pygit2_,
and dulwich_ to provide the Python interface to git. If more than one of these
are present, the order of preference for which one will be chosen is the same
as the order in which they were listed: pygit2, GitPython, dulwich (keep in
mind, this order is subject to change).

An optional master config parameter (:conf_master:`gitfs_provider`) can be used
to specify which provider should be used.

More detailed information on how to use gitfs can be found in the :ref:`Gitfs
Walkthrough <tutorial-gitfs>`.

.. note:: Minimum requirements

    To use GitPython_ for gitfs requires a minimum GitPython version of 0.3.0,
    as well as the git CLI utility. Instructions for installing GitPython can
    be found :ref:`here <gitfs-dependencies>`.

    To use pygit2_ for gitfs requires a minimum pygit2_ version of 0.20.3.
    pygit2_ 0.20.3 requires libgit2_ 0.20.0. pygit2_ and libgit2_ are developed
    alongside one another, so it is recommended to keep them both at the same
    major release to avoid unexpected behavior. For example, pygit2_ 0.21.x
    requires libgit2_ 0.21.x, pygit2_ 0.22.x will require libgit2_ 0.22.x, etc.

    To find stale refs, pygit2 additionally requires the git CLI utility to be
    installed.

.. _GitPython: https://github.com/gitpython-developers/GitPython
.. _pygit2: https://github.com/libgit2/pygit2
.. _libgit2: https://libgit2.github.com/
.. _dulwich: https://www.samba.org/~jelmer/dulwich/
'''

# Import python libs
import copy
import distutils.version  # pylint: disable=E0611
import errno
import fnmatch
import glob
import hashlib
import logging
import os
import re
import shutil
import stat
import subprocess
from datetime import datetime
from salt._compat import text_type as _text_type
from salt._compat import StringIO

VALID_PROVIDERS = ('gitpython', 'pygit2', 'dulwich')
PER_REMOTE_PARAMS = ('base', 'mountpoint', 'root')
SYMLINK_RECURSE_DEPTH = 100

# Auth support (auth params can be global or per-remote, too)
AUTH_PROVIDERS = ('pygit2',)
AUTH_PARAMS = ('user', 'password', 'pubkey', 'privkey', 'passphrase',
               'insecure_auth')

_RECOMMEND_GITPYTHON = (
    'GitPython is installed, you may wish to set gitfs_provider to '
    '\'gitpython\' in the master config file to use GitPython for gitfs '
    'support.'
)

_RECOMMEND_PYGIT2 = (
    'pygit2 is installed, you may wish to set gitfs_provider to '
    '\'pygit2\' in the master config file to use pygit2 for for gitfs '
    'support.'
)

_RECOMMEND_DULWICH = (
    'Dulwich is installed, you may wish to set gitfs_provider to '
    '\'dulwich\' in the master config file to use Dulwich for gitfs '
    'support.'
)

_INVALID_REPO = (
    'Cache path {0} (corresponding remote: {1}) exists but is not a valid '
    'git repository. You will need to manually delete this directory on the '
    'master to continue to use this gitfs remote.'
)

# Import salt libs
import salt.utils
import salt.fileserver
from salt._compat import string_types
from salt.exceptions import FileserverConfigError
from salt.utils.event import tagify

# Import third party libs
try:
    import git
    import gitdb
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False

try:
    import pygit2
    HAS_PYGIT2 = True
except ImportError:
    HAS_PYGIT2 = False

try:
    import dulwich.errors
    import dulwich.repo
    import dulwich.client
    import dulwich.config
    import dulwich.objects
    HAS_DULWICH = True
except ImportError:
    HAS_DULWICH = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'git'


def _verify_gitpython(quiet=False):
    '''
    Check if GitPython is available and at a compatible version (>= 0.3.0)
    '''
    def _recommend():
        if HAS_PYGIT2:
            log.error(_RECOMMEND_PYGIT2)
        if HAS_DULWICH:
            log.error(_RECOMMEND_DULWICH)

    if not HAS_GITPYTHON:
        if not quiet:
            log.error(
                'Git fileserver backend is enabled in master config file, but '
                'could not be loaded, is GitPython installed?'
            )
            _recommend()
        return False

    gitver = distutils.version.LooseVersion(git.__version__)
    minver_str = '0.3.0'
    minver = distutils.version.LooseVersion(minver_str)
    errors = []
    if gitver < minver:
        errors.append(
            'Git fileserver backend is enabled in master config file, but '
            'the GitPython version is earlier than {0}. Version {1} '
            'detected.'.format(minver_str, git.__version__)
        )
    if not salt.utils.which('git'):
        errors.append(
            'The git command line utility is required by the Git fileserver '
            'backend when using the \'gitpython\' provider.'
        )

    if errors:
        for error in errors:
            log.error(error)
        if not quiet:
            _recommend()
        return False

    log.debug('gitpython gitfs_provider enabled')
    __opts__['verified_gitfs_provider'] = 'gitpython'
    return True


def _verify_pygit2(quiet=False):
    '''
    Check if pygit2/libgit2 are available and at a compatible version. Pygit2
    must be at least 0.20.3 and libgit2 must be at least 0.20.0.
    '''
    def _recommend():
        if HAS_GITPYTHON:
            log.error(_RECOMMEND_GITPYTHON)
        if HAS_DULWICH:
            log.error(_RECOMMEND_DULWICH)

    if not HAS_PYGIT2:
        if not quiet:
            log.error(
                'Git fileserver backend is enabled in master config file, but '
                'could not be loaded, are pygit2 and libgit2 installed?'
            )
            _recommend()
        return False

    pygit2ver = distutils.version.LooseVersion(pygit2.__version__)
    pygit2_minver_str = '0.20.3'
    pygit2_minver = distutils.version.LooseVersion(pygit2_minver_str)

    libgit2ver = distutils.version.LooseVersion(pygit2.LIBGIT2_VERSION)
    libgit2_minver_str = '0.20.0'
    libgit2_minver = distutils.version.LooseVersion(libgit2_minver_str)

    errors = []
    if pygit2ver < pygit2_minver:
        errors.append(
            'Git fileserver backend is enabled in master config file, but '
            'pygit2 version is earlier than {0}. Version {1} detected.'
            .format(pygit2_minver_str, pygit2.__version__)
        )
    if libgit2ver < libgit2_minver:
        errors.append(
            'Git fileserver backend is enabled in master config file, but '
            'libgit2 version is earlier than {0}. Version {1} detected.'
            .format(libgit2_minver_str, pygit2.LIBGIT2_VERSION)
        )
    if not salt.utils.which('git'):
        errors.append(
            'The git command line utility is required by the Git fileserver '
            'backend when using the \'pygit2\' provider.'
        )

    if errors:
        for error in errors:
            log.error(error)
        if not quiet:
            _recommend()
        return False

    log.debug('pygit2 gitfs_provider enabled')
    __opts__['verified_gitfs_provider'] = 'pygit2'
    return True


def _verify_dulwich(quiet=False):
    '''
    Check if dulwich is available.
    '''
    def _recommend():
        if HAS_GITPYTHON:
            log.error(_RECOMMEND_GITPYTHON)
        if HAS_PYGIT2:
            log.error(_RECOMMEND_PYGIT2)

    if not HAS_DULWICH:
        if not quiet:
            log.error(
                'Git fileserver backend is enabled in the master config file, but '
                'could not be loaded. Is Dulwich installed?'
            )
            _recommend()
        return False

    dulwich_version = dulwich.__version__
    dulwich_min_version = (0, 9, 4)

    errors = []

    if dulwich_version < dulwich_min_version:
        errors.append(
            'Git fileserver backend is enabled in the master config file, but '
            'the installed version of Dulwich is earlier than {0}. Version {1} '
            'detected.'.format(dulwich_min_version, dulwich_version)
        )

    if errors:
        for error in errors:
            log.error(error)
        if not quiet:
            _recommend()
        return False

    log.debug('dulwich gitfs_provider enabled')
    __opts__['verified_gitfs_provider'] = 'dulwich'
    return True


def _get_provider():
    '''
    Determine which gitfs_provider to use
    '''
    # Don't re-perform all the verification if we already have a verified
    # provider
    if 'verified_gitfs_provider' in __opts__:
        return __opts__['verified_gitfs_provider']
    provider = __opts__.get('gitfs_provider', '').lower()
    if not provider:
        if _verify_pygit2(quiet=True):
            return 'pygit2'
        elif _verify_gitpython(quiet=True):
            return 'gitpython'
        elif _verify_dulwich(quiet=True):
            return 'dulwich'
        else:
            log.error(
                'No suitable version of pygit2/libgit2, GitPython, or Dulwich '
                'is installed.'
            )
    else:
        if provider not in VALID_PROVIDERS:
            log.critical(
                'Invalid gitfs_provider {0!r}. Valid choices are: {1}'
                .format(provider, ', '.join(VALID_PROVIDERS))
            )
            return None
        elif provider == 'pygit2' and _verify_pygit2():
            return 'pygit2'
        elif provider == 'gitpython' and _verify_gitpython():
            return 'gitpython'
        elif provider == 'dulwich' and _verify_dulwich():
            return 'dulwich'
    return ''


def __virtual__():
    '''
    Only load if the desired provider module is present and gitfs is enabled
    properly in the master config file.
    '''
    if __virtualname__ not in __opts__['fileserver_backend']:
        return False
    return __virtualname__ if _get_provider() else False


def _dulwich_conf(repo):
    '''
    Returns a dulwich.config.ConfigFile object for the specified repo
    '''
    return dulwich.config.ConfigFile().from_path(
        os.path.join(repo.controldir(), 'config')
    )


def _dulwich_remote(repo):
    '''
    Returns the remote url for the specified repo
    '''
    return _dulwich_conf(repo).get(('remote', 'origin'), 'url')


def _dulwich_walk_tree(repo, tree, path):
    '''
    Dulwich does not provide a means of directly accessing subdirectories. This
    function will walk down to the directory specified by 'path', and return a
    Tree object at that path. If path is an empty string, the original tree
    will be returned, and if there are any issues encountered walking the tree,
    None will be returned.
    '''
    if not path:
        return tree
    # Walk down the tree to get to the file
    for parent in path.split(os.path.sep):
        try:
            tree = repo.get_object(tree[parent][1])
        except (KeyError, TypeError):
            # Directory not found, or tree passed into function is not a Tree
            # object. Either way, desired path does not exist.
            return None
    return tree


_dulwich_env_refs = lambda refs: [x for x in refs
                                  if re.match('refs/(heads|tags)', x)
                                  and not x.endswith('^{}')]


def _get_tree_gitpython(repo, tgt_env):
    '''
    Return a git.Tree object if the branch/tag/SHA is found, otherwise None
    '''
    if tgt_env == 'base':
        tgt_env = repo['base']
    if tgt_env == repo['base'] or tgt_env in envs():
        for ref in repo['repo'].refs:
            if isinstance(ref, (git.RemoteReference, git.TagReference)):
                parted = ref.name.partition('/')
                rspec = parted[2] if parted[2] else parted[0]
                if rspec == tgt_env:
                    return ref.commit.tree

    # Branch or tag not matched, check if 'tgt_env' is a commit
    if not _env_is_exposed(tgt_env):
        return None
    try:
        commit = repo['repo'].rev_parse(tgt_env)
    except gitdb.exc.BadObject:
        pass
    else:
        return commit.tree
    return None


def _get_tree_pygit2(repo, tgt_env):
    '''
    Return a pygit2.Tree object if the branch/tag/SHA is found, otherwise None
    '''
    if tgt_env == 'base':
        tgt_env = repo['base']
    if tgt_env == repo['base'] or tgt_env in envs():
        for ref in repo['repo'].listall_references():
            _, rtype, rspec = ref.split('/', 2)
            if rtype in ('remotes', 'tags'):
                parted = rspec.partition('/')
                rspec = parted[2] if parted[2] else parted[0]
                if rspec == tgt_env and _env_is_exposed(rspec):
                    return repo['repo'].lookup_reference(ref).get_object().tree

    # Branch or tag not matched, check if 'tgt_env' is a commit
    if not _env_is_exposed(tgt_env):
        return None
    try:
        commit = repo['repo'].revparse_single(tgt_env)
    except (KeyError, TypeError):
        # Not a valid commit, likely not a commit SHA
        pass
    else:
        return commit.tree
    return None


def _get_tree_dulwich(repo, tgt_env):
    '''
    Return a dulwich.objects.Tree object if the branch/tag/SHA is found,
    otherwise None
    '''
    if tgt_env == 'base':
        tgt_env = repo['base']
    if tgt_env == repo['base'] or tgt_env in envs():
        refs = repo['repo'].get_refs()
        # Sorting ensures we check heads (branches) before tags
        for ref in sorted(_dulwich_env_refs(refs)):
            # ref will be something like 'refs/heads/master'
            rtype, rspec = ref[5:].split('/', 1)
            if rspec == tgt_env and _env_is_exposed(rspec):
                if rtype == 'heads':
                    commit = repo['repo'].get_object(refs[ref])
                elif rtype == 'tags':
                    tag = repo['repo'].get_object(refs[ref])
                    if isinstance(tag, dulwich.objects.Tag):
                        # Tag.get_object() returns a 2-tuple, the 2nd element
                        # of which is the commit SHA to which the tag refers
                        commit = repo['repo'].get_object(tag.object[1])
                    elif isinstance(tag, dulwich.objects.Commit):
                        commit = tag
                    else:
                        log.error(
                            'Unhandled object type {0!r} in '
                            '_get_tree_dulwich. This is a bug, please report '
                            'it.'.format(tag.type_name)
                        )
                return repo['repo'].get_object(commit.tree)

    # Branch or tag not matched, check if 'tgt_env' is a commit. This is more
    # difficult with Dulwich because of its inability to deal with shortened
    # SHA-1 hashes.
    if not _env_is_exposed(tgt_env):
        return None
    try:
        int(tgt_env, 16)
    except ValueError:
        # Not hexidecimal, likely just a non-matching environment
        return None

    try:
        if len(tgt_env) == 40:
            sha_obj = repo['repo'].get_object(tgt_env)
            if isinstance(sha_obj, dulwich.objects.Commit):
                sha_commit = sha_obj
        else:
            matches = set([
                x for x in (
                    repo['repo'].get_object(x)
                    for x in repo['repo'].object_store
                    if x.startswith(tgt_env)
                )
                if isinstance(x, dulwich.objects.Commit)
            ])
            if len(matches) > 1:
                log.warning('Ambiguous commit ID {0!r}'.format(tgt_env))
                return None
            try:
                sha_commit = matches.pop()
            except IndexError:
                pass
    except TypeError as exc:
        log.warning('Invalid environment {0}: {1}'.format(tgt_env, exc))
    except KeyError:
        # No matching SHA
        return None

    try:
        return repo['repo'].get_object(sha_commit.tree)
    except NameError:
        # No matching sha_commit object was created. Unable to find SHA.
        pass
    return None


def _clean_stale(repo_obj, local_refs=None):
    '''
    Clean stale local refs so they don't appear as fileserver environments
    '''
    provider = _get_provider()
    cleaned = []
    if provider == 'gitpython':
        for ref in repo_obj.remotes[0].stale_refs:
            if ref.name.startswith('refs/tags/'):
                # Work around GitPython bug affecting removal of tags
                # https://github.com/gitpython-developers/GitPython/issues/260
                repo_obj.git.tag('-d', ref.name[10:])
            else:
                ref.delete(repo_obj, ref)
            cleaned.append(ref)
    elif provider == 'pygit2':
        if local_refs is None:
            local_refs = repo_obj.listall_references()
        remote_refs = []
        for line in subprocess.Popen(
                'git ls-remote origin',
                shell=True,
                close_fds=True,
                cwd=repo_obj.workdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT).communicate()[0].splitlines():
            try:
                # Rename heads to match the ref names from
                # pygit2.Repository.listall_references()
                remote_refs.append(
                    line.split()[-1].replace('refs/heads/',
                                             'refs/remotes/origin/')
                )
            except IndexError:
                continue
        for ref in [x for x in local_refs if x not in remote_refs]:
            repo_obj.lookup_reference(ref).delete()
            cleaned.append(ref)
    if cleaned:
        log.debug('gitfs cleaned the following stale refs: {0}'
                  .format(cleaned))
    return cleaned


def _verify_auth(repo):
    '''
    Check the username and password/keypair info for validity. If valid, assign
    a 'credentials' key (consisting of a relevant credentials object) to the
    repo config dict passed to this function. Return False if a required auth
    param is not present. Return True if the required auth parameters are
    present, or if the desired transport either does not support
    authentication.

    At this time, pygit2 is the only gitfs_provider which supports auth.
    '''
    if os.path.isabs(repo['url']) or _get_provider() not in AUTH_PROVIDERS:
        # If the URL is an absolute file path, there is no authentication.
        # Similarly, if the gitfs_provider is not one that supports auth, there
        # is no reason to proceed any further. Since there is no auth issue, we
        # return True
        return True
    if not any(repo.get(x) for x in AUTH_PARAMS):
        # Auth information not configured for this remote
        return True

    def _incomplete_auth(remote_url, missing):
        '''
        Helper function to log errors about missing auth parameters
        '''
        log.error(
            'Incomplete authentication information for remote {0}. Missing '
            'parameters: {1}'.format(remote_url, ', '.join(missing))
        )
        _failhard()

    transport, _, address = repo['url'].partition('://')
    if not address:
        # Assume scp-like SSH syntax (user@domain.tld:relative/path.git)
        transport = 'ssh'
        address = repo['url']

    transport = transport.lower()

    if transport in ('git', 'file'):
        # These transports do not use auth
        return True

    elif transport == 'ssh':
        required_params = ('pubkey', 'privkey')
        user = address.split('@')[0]
        if user == address:
            # No '@' sign == no user. This is a problem.
            log.error(
                'Password / keypair specified for remote {0}, but remote '
                'URL is missing a username'.format(repo['url'])
            )
            _failhard()

        repo['user'] = user
        if all(bool(repo[x]) for x in required_params):
            keypair_params = [repo[x] for x in
                              ('user', 'pubkey', 'privkey', 'passphrase')]
            repo['credentials'] = pygit2.Keypair(*keypair_params)
            return True
        else:
            missing_auth = [x for x in required_params if not bool(repo[x])]
            _incomplete_auth(repo['url'], missing_auth)

    elif transport in ('https', 'http'):
        required_params = ('user', 'password')
        password_ok = all(bool(repo[x]) for x in required_params)
        no_password_auth = not any(bool(repo[x]) for x in required_params)
        if no_password_auth:
            # Auth is not required, return True
            return True
        if password_ok:
            if transport == 'http' and not repo['insecure_auth']:
                log.error(
                    'Invalid configuration for gitfs remote {0}. '
                    'Authentication is disabled by default on http remotes. '
                    'Either set gitfs_insecure_auth to True in the master '
                    'configuration file, set a per-remote config option named '
                    '\'insecure_auth\' to True, or use https or ssh-based '
                    'authentication.'.format(repo['url'])
                )
                _failhard()
            repo['credentials'] = pygit2.UserPass(repo['user'],
                                                  repo['password'])
            return True
        else:
            missing_auth = [x for x in required_params if not bool(repo[x])]
            _incomplete_auth(repo['url'], missing_auth)
    else:
        log.error(
            'Invalid configuration for remote {0}. Unsupported transport '
            '{1!r}.'.format(repo['url'], transport)
        )
        _failhard()


def _failhard():
    '''
    Fatal fileserver configuration issue, raise an exception
    '''
    raise FileserverConfigError(
        'Failed to load git fileserver backend'
    )


def init():
    '''
    Return the git repo object for this session
    '''
    bp_ = os.path.join(__opts__['cachedir'], 'gitfs')
    provider = _get_provider()

    # The global versions of the auth params (gitfs_user, gitfs_password, etc.)
    # default to empty strings. If any of them are defined and the gitfs
    # provider is not one that supports auth, then error out and do not
    # proceed.
    override_params = copy.deepcopy(PER_REMOTE_PARAMS)
    global_auth_params = [
        'gitfs_{0}'.format(x) for x in AUTH_PARAMS
        if __opts__['gitfs_{0}'.format(x)]
    ]
    if provider in AUTH_PROVIDERS:
        override_params += AUTH_PARAMS
    elif global_auth_params:
        log.critical(
            'gitfs authentication was configured, but the {0!r} '
            'gitfs_provider does not support authentication. The providers '
            'for which authentication is supported in gitfs are: {1}. See the '
            'GitFS Walkthrough in the Salt documentation for further '
            'information.'.format(provider, ', '.join(AUTH_PROVIDERS))
        )
        _failhard()

    # ignore git ssl verification if requested
    ssl_verify = 'true' if __opts__.get('gitfs_ssl_verify', True) else 'false'
    new_remote = False
    repos = []

    per_remote_defaults = {}
    for param in override_params:
        per_remote_defaults[param] = \
            _text_type(__opts__['gitfs_{0}'.format(param)])

    for remote in __opts__['gitfs_remotes']:
        repo_conf = copy.deepcopy(per_remote_defaults)
        bad_per_remote_conf = False
        if isinstance(remote, dict):
            repo_url = next(iter(remote))
            per_remote_conf = dict(
                [(key, _text_type(val)) for key, val in
                 salt.utils.repack_dictlist(remote[repo_url]).items()]
            )
            if not per_remote_conf:
                log.error(
                    'Invalid per-remote configuration for gitfs remote {0}. '
                    'If no per-remote parameters are being specified, there '
                    'may be a trailing colon after the URL, which should be '
                    'removed. Check the master configuration file.'
                    .format(repo_url)
                )
                _failhard()

            per_remote_errors = False
            for param in (x for x in per_remote_conf
                          if x not in override_params):
                if param in AUTH_PARAMS and provider not in AUTH_PROVIDERS:
                    log.critical(
                        'gitfs authentication parameter {0!r} (from remote '
                        '{1}) is only supported by the following provider(s): '
                        '{2}. Current gitfs_provider is {3!r}. See the '
                        'GitFS Walkthrough in the Salt documentation for '
                        'further information.'.format(
                            param,
                            repo_url,
                            ', '.join(AUTH_PROVIDERS),
                            provider
                        )
                    )
                else:
                    log.critical(
                        'Invalid configuration parameter {0!r} in remote {1}. '
                        'Valid parameters are: {2}. See the GitFS Walkthrough '
                        'in the Salt documentation for further '
                        'information.'.format(
                            param,
                            repo_url,
                            ', '.join(override_params)
                        )
                    )
                per_remote_errors = True
            if per_remote_errors:
                _failhard()

            repo_conf.update(per_remote_conf)
        else:
            repo_url = remote

        if not isinstance(repo_url, string_types):
            log.error(
                'Invalid gitfs remote {0}. Remotes must be strings, you may '
                'need to enclose the URL in quotes'.format(repo_url)
            )
            continue

        try:
            repo_conf['mountpoint'] = salt.utils.strip_proto(
                repo_conf['mountpoint']
            )
        except TypeError:
            # mountpoint not specified
            pass

        hash_type = getattr(hashlib, __opts__.get('hash_type', 'md5'))
        repo_hash = hash_type(repo_url).hexdigest()
        rp_ = os.path.join(bp_, repo_hash)
        if not os.path.isdir(rp_):
            os.makedirs(rp_)

        try:
            if provider == 'gitpython':
                repo, new = _init_gitpython(rp_, repo_url, ssl_verify)
                if new:
                    new_remote = True
                lockfile = os.path.join(repo.working_dir, 'update.lk')
            elif provider == 'pygit2':
                repo, new = _init_pygit2(rp_, repo_url, ssl_verify)
                if new:
                    new_remote = True
                lockfile = os.path.join(repo.workdir, 'update.lk')
            elif provider == 'dulwich':
                repo, new = _init_dulwich(rp_, repo_url, ssl_verify)
                if new:
                    new_remote = True
                lockfile = os.path.join(repo.path, 'update.lk')
            else:
                # Should never get here because the provider has been verified
                # in __virtual__(). Log an error and return an empty list.
                log.error(
                    'Unexpected gitfs_provider {0!r}. This is probably a bug.'
                    .format(provider)
                )
                return []

            if repo is not None:
                repo_conf.update({
                    'repo': repo,
                    'url': repo_url,
                    'hash': repo_hash,
                    'cachedir': rp_,
                    'lockfile': lockfile
                })
                # Strip trailing slashes from the gitfs root as these cause
                # path searches to fail.
                repo_conf['root'] = repo_conf['root'].rstrip(os.path.sep)
                # Sanity check and assign the credential parameter to repo_conf
                if not _verify_auth(repo_conf):
                    continue
                repos.append(repo_conf)

        except Exception as exc:
            msg = ('Exception caught while initializing gitfs remote {0}: '
                   '{0}'.format(exc))
            if provider == 'gitpython':
                msg += ' Perhaps git is not available.'
            log.error(msg, exc_info_on_loglevel=logging.DEBUG)
            _failhard()

    if new_remote:
        remote_map = os.path.join(__opts__['cachedir'], 'gitfs/remote_map.txt')
        try:
            with salt.utils.fopen(remote_map, 'w+') as fp_:
                timestamp = datetime.now().strftime('%d %b %Y %H:%M:%S.%f')
                fp_.write('# gitfs_remote map as of {0}\n'.format(timestamp))
                for repo in repos:
                    fp_.write('{0} = {1}\n'.format(repo['hash'], repo['url']))
        except OSError:
            pass
        else:
            log.info('Wrote new gitfs_remote map to {0}'.format(remote_map))

    return repos


def _init_gitpython(rp_, repo_url, ssl_verify):
    '''
    Initialize/attach to a repository using GitPython. Return the repo object
    if successful, otherwise return None. Also return a boolean that will tell
    init() whether a new repo was initialized.
    '''
    new = False
    if not os.listdir(rp_):
        # Repo cachedir is empty, initialize a new repo there
        repo = git.Repo.init(rp_)
        new = True
    else:
        # Repo cachedir exists, try to attach
        try:
            repo = git.Repo(rp_)
        except git.exc.InvalidGitRepositoryError:
            log.error(_INVALID_REPO.format(rp_, repo_url))
            return None, new
    if not repo.remotes:
        try:
            repo.create_remote('origin', repo_url)
            # Ensure tags are also fetched
            repo.git.config('--add',
                            'remote.origin.fetch',
                            '+refs/tags/*:refs/tags/*')
            repo.git.config('http.sslVerify', ssl_verify)
        except os.error:
            # This exception occurs when two processes are trying to write to
            # the git config at once, go ahead and pass over it since this is
            # the only write. This should place a lock down.
            pass
    if repo.remotes:
        return repo, new
    return None, new


def _init_pygit2(rp_, repo_url, ssl_verify):
    '''
    Initialize/attach to a repository using pygit2. Return the repo object if
    successful, otherwise return None. Also return a boolean that will tell
    init() whether a new repo was initialized.
    '''
    new = False
    if not os.listdir(rp_):
        # Repo cachedir is empty, initialize a new repo there
        repo = pygit2.init_repository(rp_)
        new = True
    else:
        # Repo cachedir exists, try to attach
        try:
            repo = pygit2.Repository(rp_)
        except KeyError:
            log.error(_INVALID_REPO.format(rp_, repo_url))
            return None, new
    if not repo.remotes:
        try:
            repo.create_remote('origin', repo_url)
            # Ensure tags are also fetched
            repo.config.set_multivar('remote.origin.fetch', 'FOO',
                                     '+refs/tags/*:refs/tags/*')

            repo.config.set_multivar('http.sslVerify', '', ssl_verify)
        except os.error:
            # This exception occurs when two processes are trying to write to
            # the git config at once, go ahead and pass over it since this is
            # the only write. This should place a lock down.
            pass
    if repo.remotes:
        return repo, new
    return None, new


def _init_dulwich(rp_, repo_url, ssl_verify):
    '''
    Initialize/attach to a repository using Dulwich. Return the repo object if
    successful, otherwise return None. Also return a boolean that will tell
    init() whether a new repo was initialized.
    '''
    if repo_url.startswith('ssh://'):
        # Dulwich will throw an error if 'ssh' is used.
        repo_url = 'git+' + repo_url
    new = False
    if not os.listdir(rp_):
        # Repo cachedir is empty, initialize a new repo there
        try:
            repo = dulwich.repo.Repo.init(rp_)
            new = True
            conf = _dulwich_conf(repo)
            conf.set('http', 'sslVerify', ssl_verify)
            # Add the remote manually, there is no function/object to do this
            conf.set(
                'remote "origin"',
                'fetch',
                '+refs/heads/*:refs/remotes/origin/*'
            )
            conf.set('remote "origin"', 'url', repo_url)
            conf.set('remote "origin"', 'pushurl', repo_url)
            conf.write_to_path()
        except os.error:
            pass
    else:
        # Repo cachedir exists, try to attach
        try:
            repo = dulwich.repo.Repo(rp_)
        except dulwich.repo.NotGitRepository:
            log.error(_INVALID_REPO.format(rp_, repo_url))
            return None, new
    # No way to interact with remotes, so just assume success
    return repo, new


def _clear_old_remotes():
    '''
    Remove cache directories for remotes no longer configured
    '''
    bp_ = os.path.join(__opts__['cachedir'], 'gitfs')
    try:
        cachedir_ls = os.listdir(bp_)
    except OSError:
        cachedir_ls = []
    repos = init()
    # Remove actively-used remotes from list
    for repo in repos:
        try:
            cachedir_ls.remove(repo['hash'])
        except ValueError:
            pass
    to_remove = []
    for item in cachedir_ls:
        if item in ('hash', 'refs'):
            continue
        path = os.path.join(bp_, item)
        if os.path.isdir(path):
            to_remove.append(path)
    failed = []
    if to_remove:
        for rdir in to_remove:
            try:
                shutil.rmtree(rdir)
            except OSError as exc:
                log.error(
                    'Unable to remove old gitfs remote cachedir {0}: {1}'
                    .format(rdir, exc)
                )
                failed.append(rdir)
            else:
                log.debug('gitfs removed old cachedir {0}'.format(rdir))
    for fdir in failed:
        to_remove.remove(fdir)
    return bool(to_remove), repos


def clear_cache():
    '''
    Completely clear gitfs cache
    '''
    fsb_cachedir = os.path.join(__opts__['cachedir'], 'gitfs')
    list_cachedir = os.path.join(__opts__['cachedir'], 'file_lists/gitfs')
    errors = []
    for rdir in (fsb_cachedir, list_cachedir):
        if os.path.exists(rdir):
            try:
                shutil.rmtree(rdir)
            except OSError as exc:
                errors.append('Unable to delete {0}: {1}'.format(rdir, exc))
    return errors


def clear_lock(remote=None):
    '''
    Clear update.lk

    ``remote`` can either be a dictionary containing repo configuration
    information, or a pattern. If the latter, then remotes for which the URL
    matches the pattern will be locked.
    '''
    def _do_clear_lock(repo):
        def _add_error(errlist, repo, exc):
            msg = ('Unable to remove update lock for {0} ({1}): {2} '
                   .format(repo['url'], repo['lockfile'], exc))
            log.debug(msg)
            errlist.append(msg)
        success = []
        failed = []
        if os.path.exists(repo['lockfile']):
            try:
                os.remove(repo['lockfile'])
            except OSError as exc:
                if exc.errno == errno.EISDIR:
                    # Somehow this path is a directory. Should never happen
                    # unless some wiseguy manually creates a directory at this
                    # path, but just in case, handle it.
                    try:
                        shutil.rmtree(repo['lockfile'])
                    except OSError as exc:
                        _add_error(failed, repo, exc)
                else:
                    _add_error(failed, repo, exc)
            else:
                msg = 'Removed lock for {0}'.format(repo['url'])
                log.debug(msg)
                success.append(msg)
        return success, failed

    if isinstance(remote, dict):
        return _do_clear_lock(remote)

    cleared = []
    errors = []
    for repo in init():
        if remote:
            try:
                if not fnmatch.fnmatch(repo['url'], remote):
                    continue
            except TypeError:
                # remote was non-string, try again
                if not fnmatch.fnmatch(repo['url'], _text_type(remote)):
                    continue
        success, failed = _do_clear_lock(repo)
        cleared.extend(success)
        errors.extend(failed)
    return cleared, errors


def lock(remote=None):
    '''
    Place an update.lk

    ``remote`` can either be a dictionary containing repo configuration
    information, or a pattern. If the latter, then remotes for which the URL
    matches the pattern will be locked.
    '''
    def _do_lock(repo):
        success = []
        failed = []
        if not os.path.exists(repo['lockfile']):
            try:
                with salt.utils.fopen(repo['lockfile'], 'w+') as fp_:
                    fp_.write('')
            except (IOError, OSError) as exc:
                msg = ('Unable to set update lock for {0} ({1}): {2} '
                       .format(repo['url'], repo['lockfile'], exc))
                log.debug(msg)
                failed.append(msg)
            else:
                msg = 'Set lock for {0}'.format(repo['url'])
                log.debug(msg)
                success.append(msg)
        return success, failed

    if isinstance(remote, dict):
        return _do_lock(remote)

    locked = []
    errors = []
    for repo in init():
        if remote:
            try:
                if not fnmatch.fnmatch(repo['url'], remote):
                    continue
            except TypeError:
                # remote was non-string, try again
                if not fnmatch.fnmatch(repo['url'], _text_type(remote)):
                    continue
        success, failed = _do_lock(repo)
        locked.extend(success)
        errors.extend(failed)

    return locked, errors


def update():
    '''
    Execute a git fetch on all of the repos
    '''
    # data for the fileserver event
    data = {'changed': False,
            'backend': 'gitfs'}
    provider = _get_provider()
    # _clear_old_remotes runs init(), so use the value from there to avoid a
    # second init()
    data['changed'], repos = _clear_old_remotes()
    for repo in repos:
        if os.path.exists(repo['lockfile']):
            log.warning(
                'Update lockfile is present for gitfs remote {0}, skipping. '
                'If this warning persists, it is possible that the update '
                'process was interrupted. Removing {1} or running '
                '\'salt-run fileserver.clear_lock gitfs\' will allow updates '
                'to continue for this remote.'
                .format(repo['url'], repo['lockfile'])
            )
            continue
        _, errors = lock(repo)
        if errors:
            log.error('Unable to set update lock for gitfs remote {0}, '
                      'skipping.'.format(repo['url']))
            continue
        log.debug('gitfs is fetching from {0}'.format(repo['url']))
        try:
            if provider == 'gitpython':
                origin = repo['repo'].remotes[0]
                try:
                    fetch_results = origin.fetch()
                except AssertionError:
                    fetch_results = origin.fetch()
                cleaned = _clean_stale(repo['repo'])
                if fetch_results or cleaned:
                    data['changed'] = True
            elif provider == 'pygit2':
                origin = repo['repo'].remotes[0]
                refs_pre = repo['repo'].listall_references()
                try:
                    origin.credentials = repo['credentials']
                except KeyError:
                    # No credentials configured for this repo
                    pass
                fetch = origin.fetch()
                try:
                    # pygit2.Remote.fetch() returns a dict in pygit2 < 0.21.0
                    received_objects = fetch['received_objects']
                except (AttributeError, TypeError):
                    # pygit2.Remote.fetch() returns a class instance in
                    # pygit2 >= 0.21.0
                    received_objects = fetch.received_objects
                log.debug(
                    'gitfs received {0} objects for remote {1}'
                    .format(received_objects, repo['url'])
                )
                # Clean up any stale refs
                refs_post = repo['repo'].listall_references()
                cleaned = _clean_stale(repo['repo'], refs_post)
                if received_objects or refs_pre != refs_post or cleaned:
                    data['changed'] = True
            elif provider == 'dulwich':
                # origin is just a url here, there is no origin object
                origin = repo['url']
                client, path = \
                    dulwich.client.get_transport_and_path_from_url(
                        origin, thin_packs=True
                    )
                refs_pre = repo['repo'].get_refs()
                try:
                    refs_post = client.fetch(path, repo['repo'])
                except dulwich.errors.NotGitRepository:
                    log.critical(
                        'Dulwich does not recognize remote {0} as a valid '
                        'remote URL. Perhaps it is missing \'.git\' at the '
                        'end.'.format(repo['url'])
                    )
                    continue
                except KeyError:
                    log.critical(
                        'Local repository cachedir {0!r} (corresponding '
                        'remote: {1}) has been corrupted. Salt will now '
                        'attempt to remove the local checkout to allow it to '
                        'be re-initialized in the next fileserver cache '
                        'update.'
                        .format(repo['cachedir'], repo['url'])
                    )
                    try:
                        salt.utils.rm_rf(repo['cachedir'])
                    except OSError as exc:
                        log.critical(
                            'Unable to remove {0!r}: {1}'
                            .format(repo['cachedir'], exc)
                        )
                    continue
                if refs_post is None:
                    # Empty repository
                    log.warning(
                        'gitfs remote {0!r} is an empty repository and will '
                        'be skipped.'.format(origin)
                    )
                    continue
                if refs_pre != refs_post:
                    data['changed'] = True
                    # Update local refs
                    for ref in _dulwich_env_refs(refs_post):
                        repo['repo'][ref] = refs_post[ref]
                    # Prune stale refs
                    for ref in repo['repo'].get_refs():
                        if ref not in refs_post:
                            del repo['repo'][ref]
        except Exception as exc:
            # Do not use {0!r} in the error message, as exc is not a string
            log.error(
                'Exception \'{0}\' caught while fetching gitfs remote {1}'
                .format(exc, repo['url']),
                exc_info_on_loglevel=logging.DEBUG
            )
        finally:
            clear_lock(repo)

    env_cache = os.path.join(__opts__['cachedir'], 'gitfs/envs.p')
    if data.get('changed', False) is True or not os.path.isfile(env_cache):
        env_cachedir = os.path.dirname(env_cache)
        if not os.path.exists(env_cachedir):
            os.makedirs(env_cachedir)
        new_envs = envs(ignore_cache=True)
        serial = salt.payload.Serial(__opts__)
        with salt.utils.fopen(env_cache, 'w+') as fp_:
            fp_.write(serial.dumps(new_envs))
            log.trace('Wrote env cache data to {0}'.format(env_cache))

    # if there is a change, fire an event
    if __opts__.get('fileserver_events', False):
        event = salt.utils.event.get_event(
                'master',
                __opts__['sock_dir'],
                __opts__['transport'],
                opts=__opts__,
                listen=False)
        event.fire_event(data, tagify(['gitfs', 'update'], prefix='fileserver'))
    try:
        salt.fileserver.reap_fileserver_cache_dir(
            os.path.join(__opts__['cachedir'], 'gitfs/hash'),
            find_file
        )
    except (IOError, OSError):
        # Hash file won't exist if no files have yet been served up
        pass


def _env_is_exposed(env):
    '''
    Check if an environment is exposed by comparing it against a whitelist and
    blacklist.
    '''
    return salt.utils.check_whitelist_blacklist(
        env,
        whitelist=__opts__['gitfs_env_whitelist'],
        blacklist=__opts__['gitfs_env_blacklist']
    )


def envs(ignore_cache=False, skip_clean=False):
    '''
    Return a list of refs that can be used as environments
    '''
    if not ignore_cache:
        env_cache = os.path.join(__opts__['cachedir'], 'gitfs/envs.p')
        cache_match = salt.fileserver.check_env_cache(__opts__, env_cache)
        if cache_match is not None:
            return cache_match
    provider = _get_provider()
    ret = set()
    for repo in init():
        if provider == 'gitpython':
            ret.update(_envs_gitpython(repo))
        elif provider == 'pygit2':
            ret.update(_envs_pygit2(repo))
        elif provider == 'dulwich':
            ret.update(_envs_dulwich(repo))
        else:
            # Should never get here because the provider has been verified
            # in __virtual__(). Log an error and return an empty list.
            log.error(
                'Unexpected gitfs_provider {0!r}. This is probably a bug.'
                .format(provider)
            )
            return []
    return sorted(ret)


def _envs_gitpython(repo):
    '''
    Check the refs and return a list of the ones which can be used as salt
    environments.
    '''
    ret = set()
    for ref in repo['repo'].refs:
        parted = ref.name.partition('/')
        rspec = parted[2] if parted[2] else parted[0]
        if isinstance(ref, git.Head):
            if rspec == repo['base']:
                rspec = 'base'
            if _env_is_exposed(rspec):
                ret.add(rspec)
        elif isinstance(ref, git.Tag) and _env_is_exposed(rspec):
            ret.add(rspec)
    return ret


def _envs_pygit2(repo):
    '''
    Check the refs and return a list of the ones which can be used as salt
    environments.
    '''
    ret = set()
    for ref in repo['repo'].listall_references():
        ref = re.sub('^refs/', '', ref)
        rtype, rspec = ref.split('/', 1)
        if rtype == 'remotes':
            parted = rspec.partition('/')
            rspec = parted[2] if parted[2] else parted[0]
            if rspec == repo['base']:
                rspec = 'base'
            if _env_is_exposed(rspec):
                ret.add(rspec)
        elif rtype == 'tags' and _env_is_exposed(rspec):
            ret.add(rspec)
    return ret


def _envs_dulwich(repo):
    '''
    Check the refs and return a list of the ones which can be used as salt
    environments.
    '''
    ret = set()
    for ref in _dulwich_env_refs(repo['repo'].get_refs()):
        # ref will be something like 'refs/heads/master'
        rtype, rspec = ref[5:].split('/', 1)
        if rtype == 'heads':
            if rspec == repo['base']:
                rspec = 'base'
            if _env_is_exposed(rspec):
                ret.add(rspec)
        elif rtype == 'tags' and _env_is_exposed(rspec):
            ret.add(rspec)
    return ret


def find_file(path, tgt_env='base', **kwargs):  # pylint: disable=W0613
    '''
    Find the first file to match the path and ref, read the file out of git
    and send the path to the newly cached file
    '''
    fnd = {'path': '',
           'rel': ''}
    if os.path.isabs(path) or tgt_env not in envs():
        return fnd

    provider = _get_provider()
    dest = os.path.join(__opts__['cachedir'], 'gitfs/refs', tgt_env, path)
    hashes_glob = os.path.join(__opts__['cachedir'],
                               'gitfs/hash',
                               tgt_env,
                               '{0}.hash.*'.format(path))
    blobshadest = os.path.join(__opts__['cachedir'],
                               'gitfs/hash',
                               tgt_env,
                               '{0}.hash.blob_sha1'.format(path))
    lk_fn = os.path.join(__opts__['cachedir'],
                         'gitfs/hash',
                         tgt_env,
                         '{0}.lk'.format(path))
    destdir = os.path.dirname(dest)
    hashdir = os.path.dirname(blobshadest)
    if not os.path.isdir(destdir):
        try:
            os.makedirs(destdir)
        except OSError:
            # Path exists and is a file, remove it and retry
            os.remove(destdir)
            os.makedirs(destdir)
    if not os.path.isdir(hashdir):
        try:
            os.makedirs(hashdir)
        except OSError:
            # Path exists and is a file, remove it and retry
            os.remove(hashdir)
            os.makedirs(hashdir)

    for repo in init():
        if repo['mountpoint'] \
                and not path.startswith(repo['mountpoint'] + os.path.sep):
            continue
        repo_path = path[len(repo['mountpoint']):].lstrip(os.path.sep)
        if repo['root']:
            repo_path = os.path.join(repo['root'], repo_path)

        blob = None
        depth = 0
        if provider == 'gitpython':
            tree = _get_tree_gitpython(repo, tgt_env)
            if not tree:
                # Branch/tag/SHA not found in repo, try the next
                continue
            while True:
                depth += 1
                if depth > SYMLINK_RECURSE_DEPTH:
                    break
                try:
                    file_blob = tree / repo_path
                    if stat.S_ISLNK(file_blob.mode):
                        # Path is a symlink. The blob data corresponding to
                        # this path's object ID will be the target of the
                        # symlink. Follow the symlink and set repo_path to the
                        # location indicated in the blob data.
                        stream = StringIO()
                        file_blob.stream_data(stream)
                        stream.seek(0)
                        link_tgt = stream.read()
                        stream.close()
                        repo_path = os.path.normpath(
                            os.path.join(os.path.dirname(repo_path), link_tgt)
                        )
                    else:
                        blob = file_blob
                        break
                except KeyError:
                    # File not found or repo_path points to a directory
                    break
            if blob is None:
                continue
            blob_hexsha = blob.hexsha

        elif provider == 'pygit2':
            tree = _get_tree_pygit2(repo, tgt_env)
            if not tree:
                # Branch/tag/SHA not found in repo, try the next
                continue
            while True:
                depth += 1
                if depth > SYMLINK_RECURSE_DEPTH:
                    break
                try:
                    if stat.S_ISLNK(tree[repo_path].filemode):
                        # Path is a symlink. The blob data corresponding to this
                        # path's object ID will be the target of the symlink. Follow
                        # the symlink and set repo_path to the location indicated
                        # in the blob data.
                        link_tgt = repo['repo'][tree[repo_path].oid].data
                        repo_path = os.path.normpath(
                            os.path.join(os.path.dirname(repo_path), link_tgt)
                        )
                    else:
                        oid = tree[repo_path].oid
                        blob = repo['repo'][oid]
                except KeyError:
                    break
            if blob is None:
                continue
            blob_hexsha = blob.hex

        elif provider == 'dulwich':
            while True:
                depth += 1
                if depth > SYMLINK_RECURSE_DEPTH:
                    break
                prefix_dirs, _, filename = repo_path.rpartition(os.path.sep)
                tree = _get_tree_dulwich(repo, tgt_env)
                tree = _dulwich_walk_tree(repo['repo'], tree, prefix_dirs)
                if not isinstance(tree, dulwich.objects.Tree):
                    # Branch/tag/SHA not found in repo
                    break
                try:
                    mode, oid = tree[filename]
                    if stat.S_ISLNK(mode):
                        # Path is a symlink. The blob data corresponding to
                        # this path's object ID will be the target of the
                        # symlink. Follow the symlink and set repo_path to the
                        # location indicated in the blob data.
                        link_tgt = repo['repo'].get_object(oid).as_raw_string()
                        repo_path = os.path.normpath(
                            os.path.join(os.path.dirname(repo_path), link_tgt)
                        )
                    else:
                        blob = repo['repo'].get_object(oid)
                        break
                except KeyError:
                    break
            if blob is None:
                continue
            blob_hexsha = blob.sha().hexdigest()

        salt.fileserver.wait_lock(lk_fn, dest)
        if os.path.isfile(blobshadest) and os.path.isfile(dest):
            with salt.utils.fopen(blobshadest, 'r') as fp_:
                sha = fp_.read()
                if sha == blob_hexsha:
                    fnd['rel'] = path
                    fnd['path'] = dest
                    return fnd
        with salt.utils.fopen(lk_fn, 'w+') as fp_:
            fp_.write('')
        for filename in glob.glob(hashes_glob):
            try:
                os.remove(filename)
            except Exception:
                pass
        with salt.utils.fopen(dest, 'w+') as fp_:
            if provider == 'gitpython':
                blob.stream_data(fp_)
            elif provider == 'pygit2':
                fp_.write(blob.data)
            elif provider == 'dulwich':
                fp_.write(blob.as_raw_string())
        with salt.utils.fopen(blobshadest, 'w+') as fp_:
            fp_.write(blob_hexsha)
        try:
            os.remove(lk_fn)
        except OSError:
            pass
        fnd['rel'] = path
        fnd['path'] = dest
        return fnd
    return fnd


def serve_file(load, fnd):
    '''
    Return a chunk from a file based on the data received
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    ret = {'data': '',
           'dest': ''}
    required_load_keys = set(['path', 'loc', 'saltenv'])
    if not all(x in load for x in required_load_keys):
        log.debug(
            'Not all of the required keys present in payload. '
            'Missing: {0}'.format(
                ', '.join(required_load_keys.difference(load))
            )
        )
        return ret
    if not fnd['path']:
        return ret
    ret['dest'] = fnd['rel']
    gzip = load.get('gzip', None)
    with salt.utils.fopen(fnd['path'], 'rb') as fp_:
        fp_.seek(load['loc'])
        data = fp_.read(__opts__['file_buffer_size'])
        if gzip and data:
            data = salt.utils.gzip_util.compress(data, gzip)
            ret['gzip'] = gzip
        ret['data'] = data
    return ret


def file_hash(load, fnd):
    '''
    Return a file hash, the hash type is set in the master config file
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    if not all(x in load for x in ('path', 'saltenv')):
        return ''
    ret = {'hash_type': __opts__['hash_type']}
    relpath = fnd['rel']
    path = fnd['path']
    hashdest = os.path.join(__opts__['cachedir'],
                            'gitfs/hash',
                            load['saltenv'],
                            '{0}.hash.{1}'.format(relpath,
                                                  __opts__['hash_type']))
    if not os.path.isfile(hashdest):
        if not os.path.exists(os.path.dirname(hashdest)):
            os.makedirs(os.path.dirname(hashdest))
        ret['hsum'] = salt.utils.get_hash(path, __opts__['hash_type'])
        with salt.utils.fopen(hashdest, 'w+') as fp_:
            fp_.write(ret['hsum'])
        return ret
    else:
        with salt.utils.fopen(hashdest, 'rb') as fp_:
            ret['hsum'] = fp_.read()
        return ret


def _file_lists(load, form):
    '''
    Return a dict containing the file lists for files and dirs
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    list_cachedir = os.path.join(__opts__['cachedir'], 'file_lists/gitfs')
    if not os.path.isdir(list_cachedir):
        try:
            os.makedirs(list_cachedir)
        except os.error:
            log.critical('Unable to make cachedir {0}'.format(list_cachedir))
            return []
    list_cache = os.path.join(
        list_cachedir,
        '{0}.p'.format(load['saltenv'].replace(os.path.sep, '_|-'))
    )
    w_lock = os.path.join(
        list_cachedir,
        '.{0}.w'.format(load['saltenv'].replace(os.path.sep, '_|-'))
    )
    cache_match, refresh_cache, save_cache = \
        salt.fileserver.check_file_list_cache(
            __opts__, form, list_cache, w_lock
        )
    if cache_match is not None:
        return cache_match
    if refresh_cache:
        ret = {}
        ret['files'], ret['symlinks'] = _get_file_list(load)
        ret['dirs'] = _get_dir_list(load)
        if save_cache:
            salt.fileserver.write_file_list_cache(
                __opts__, ret, list_cache, w_lock
            )
        # NOTE: symlinks are organized in a dict instead of a list, however the
        # 'symlinks' key will be defined above so it will never get to the
        # default value in the call to ret.get() below.
        return ret.get(form, [])
    # Shouldn't get here, but if we do, this prevents a TypeError
    return []


def file_list(load):
    '''
    Return a list of all files on the file server in a specified
    environment
    '''
    return _file_lists(load, 'files')


def _get_file_list(load):
    '''
    Return a list of all files on the file server in a specified
    environment
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    provider = _get_provider()
    if 'saltenv' not in load or load['saltenv'] not in envs():
        return [], {}
    files = set()
    symlinks = {}
    for repo in init():
        fl_func = None
        if provider == 'gitpython':
            fl_func = _file_list_gitpython
        elif provider == 'pygit2':
            fl_func = _file_list_pygit2
        elif provider == 'dulwich':
            fl_func = _file_list_dulwich
        try:
            repo_files, repo_symlinks = fl_func(repo, load['saltenv'])
        except TypeError:
            # We should never get here unless the gitfs_provider is not
            # accounted for in tbe above if/elif block.
            continue
        else:
            files.update(repo_files)
            symlinks.update(repo_symlinks)
    return sorted(files), symlinks


def _file_list_gitpython(repo, tgt_env):
    '''
    Get file list using GitPython
    '''
    files = set()
    symlinks = {}
    if tgt_env == 'base':
        tgt_env = repo['base']
    tree = _get_tree_gitpython(repo, tgt_env)
    if not tree:
        return files, symlinks
    if repo['root']:
        try:
            tree = tree / repo['root']
        except KeyError:
            return files, symlinks
    relpath = lambda path: os.path.relpath(path, repo['root'])
    add_mountpoint = lambda path: os.path.join(repo['mountpoint'], path)
    for file_blob in tree.traverse():
        if not isinstance(file_blob, git.Blob):
            continue
        file_path = add_mountpoint(relpath(file_blob.path))
        files.add(file_path)
        if stat.S_ISLNK(file_blob.mode):
            stream = StringIO()
            file_blob.stream_data(stream)
            stream.seek(0)
            link_tgt = stream.read()
            stream.close()
            symlinks[file_path] = link_tgt
    return files, symlinks


def _file_list_pygit2(repo, tgt_env):
    '''
    Get file list using pygit2
    '''
    def _traverse(tree, repo_obj, blobs, prefix):
        '''
        Traverse through a pygit2 Tree object recursively, accumulating all the
        file paths and symlink info in the "blobs" dict
        '''
        for entry in iter(tree):
            obj = repo_obj[entry.oid]
            if isinstance(obj, pygit2.Blob):
                repo_path = os.path.join(prefix, entry.name)
                blobs.setdefault('files', []).append(repo_path)
                if stat.S_ISLNK(tree[entry.name].filemode):
                    link_tgt = repo_obj[tree[entry.name].oid].data
                    blobs.setdefault('symlinks', {})[repo_path] = link_tgt
            elif isinstance(obj, pygit2.Tree):
                _traverse(obj,
                          repo_obj,
                          blobs,
                          os.path.join(prefix, entry.name))
    files = set()
    symlinks = {}
    if tgt_env == 'base':
        tgt_env = repo['base']
    tree = _get_tree_pygit2(repo, tgt_env)
    if not tree:
        return files, symlinks
    if repo['root']:
        try:
            # This might need to be changed to account for a root that
            # spans more than one directory
            oid = tree[repo['root']].oid
            tree = repo['repo'][oid]
        except KeyError:
            return files, symlinks
        if not isinstance(tree, pygit2.Tree):
            return files, symlinks
    blobs = {}
    if len(tree):
        _traverse(tree, repo['repo'], blobs, repo['root'])
    relpath = lambda path: os.path.relpath(path, repo['root'])
    add_mountpoint = lambda path: os.path.join(repo['mountpoint'], path)
    for repo_path in blobs.get('files', []):
        files.add(add_mountpoint(relpath(repo_path)))
    for repo_path, link_tgt in blobs.get('symlinks', {}).iteritems():
        symlinks[add_mountpoint(relpath(repo_path))] = link_tgt
    return files, symlinks


def _file_list_dulwich(repo, tgt_env):
    '''
    Get file list using dulwich
    '''
    def _traverse(tree, repo_obj, blobs, prefix):
        '''
        Traverse through a dulwich Tree object recursively, accumulating all the
        file paths and symlink info in the "blobs" dict
        '''
        for item in tree.items():
            obj = repo_obj.get_object(item.sha)
            if isinstance(obj, dulwich.objects.Blob):
                repo_path = os.path.join(prefix, item.path)
                blobs.setdefault('files', []).append(repo_path)
                mode, oid = tree[item.path]
                if stat.S_ISLNK(mode):
                    link_tgt = repo_obj.get_object(oid).as_raw_string()
                    blobs.setdefault('symlinks', {})[repo_path] = link_tgt
            elif isinstance(obj, dulwich.objects.Tree):
                _traverse(obj,
                          repo_obj,
                          blobs,
                          os.path.join(prefix, item.path))
    files = set()
    symlinks = {}
    if tgt_env == 'base':
        tgt_env = repo['base']
    tree = _get_tree_dulwich(repo, tgt_env)
    tree = _dulwich_walk_tree(repo['repo'], tree, repo['root'])
    if not isinstance(tree, dulwich.objects.Tree):
        return files, symlinks
    blobs = {}
    if len(tree):
        _traverse(tree, repo['repo'], blobs, repo['root'])
    relpath = lambda path: os.path.relpath(path, repo['root'])
    add_mountpoint = lambda path: os.path.join(repo['mountpoint'], path)
    for repo_path in blobs.get('files', []):
        files.add(add_mountpoint(relpath(repo_path)))
    for repo_path, link_tgt in blobs.get('symlinks', {}).iteritems():
        symlinks[add_mountpoint(relpath(repo_path))] = link_tgt
    return files, symlinks


def file_list_emptydirs(load):  # pylint: disable=W0613
    '''
    Return a list of all empty directories on the master
    '''
    # Cannot have empty dirs in git
    return []


def dir_list(load):
    '''
    Return a list of all directories on the master
    '''
    return _file_lists(load, 'dirs')


def _get_dir_list(load):
    '''
    Get a list of all directories on the master
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    provider = _get_provider()
    if 'saltenv' not in load or load['saltenv'] not in envs():
        return []
    ret = set()
    for repo in init():
        if provider == 'gitpython':
            ret.update(
                _dir_list_gitpython(repo, load['saltenv'])
            )
        elif provider == 'pygit2':
            ret.update(
                _dir_list_pygit2(repo, load['saltenv'])
            )
        elif provider == 'dulwich':
            ret.update(
                _dir_list_dulwich(repo, load['saltenv'])
            )
    return sorted(ret)


def _dir_list_gitpython(repo, tgt_env):
    '''
    Get list of directories using GitPython
    '''
    ret = set()
    if tgt_env == 'base':
        tgt_env = repo['base']
    tree = _get_tree_gitpython(repo, tgt_env)
    if not tree:
        return ret
    if repo['root']:
        try:
            tree = tree / repo['root']
        except KeyError:
            return ret
    relpath = lambda path: os.path.relpath(path, repo['root'])
    add_mountpoint = lambda path: os.path.join(repo['mountpoint'], path)
    for blob in tree.traverse():
        if isinstance(blob, git.Tree):
            ret.add(add_mountpoint(relpath(blob.path)))
    if repo['mountpoint']:
        ret.add(repo['mountpoint'])
    return ret


def _dir_list_pygit2(repo, tgt_env):
    '''
    Get a list of directories using pygit2
    '''
    def _traverse(tree, repo_obj, blobs, prefix):
        '''
        Traverse through a pygit2 Tree object recursively, accumulating all the
        empty directories within it in the "blobs" list
        '''
        for entry in iter(tree):
            blob = repo_obj[entry.oid]
            if not isinstance(blob, pygit2.Tree):
                continue
            blobs.append(os.path.join(prefix, entry.name))
            if len(blob):
                _traverse(blob,
                          repo_obj,
                          blobs,
                          os.path.join(prefix, entry.name))
    ret = set()
    if tgt_env == 'base':
        tgt_env = repo['base']
    tree = _get_tree_pygit2(repo, tgt_env)
    if not tree:
        return ret
    if repo['root']:
        try:
            oid = tree[repo['root']].oid
            tree = repo['repo'][oid]
        except KeyError:
            return ret
        if not isinstance(tree, pygit2.Tree):
            return ret
    blobs = []
    if len(tree):
        _traverse(tree, repo['repo'], blobs, repo['root'])
    relpath = lambda path: os.path.relpath(path, repo['root'])
    add_mountpoint = lambda path: os.path.join(repo['mountpoint'], path)
    for blob in blobs:
        ret.add(add_mountpoint(relpath(blob)))
    if repo['mountpoint']:
        ret.add(repo['mountpoint'])
    return ret


def _dir_list_dulwich(repo, tgt_env):
    '''
    Get a list of directories using pygit2
    '''
    def _traverse(tree, repo_obj, blobs, prefix):
        '''
        Traverse through a dulwich Tree object recursively, accumulating all
        the empty directories within it in the "blobs" list
        '''
        for item in tree.items():
            obj = repo_obj.get_object(item.sha)
            if not isinstance(obj, dulwich.objects.Tree):
                continue
            blobs.append(os.path.join(prefix, item.path))
            if len(repo_obj.get_object(item.sha)):
                _traverse(obj,
                          repo_obj,
                          blobs,
                          os.path.join(prefix, item.path))
    ret = set()
    if tgt_env == 'base':
        tgt_env = repo['base']
    tree = _get_tree_dulwich(repo, tgt_env)
    tree = _dulwich_walk_tree(repo['repo'], tree, repo['root'])
    if not isinstance(tree, dulwich.objects.Tree):
        return ret
    blobs = []
    if len(tree):
        _traverse(tree, repo['repo'], blobs, repo['root'])
    relpath = lambda path: os.path.relpath(path, repo['root'])
    add_mountpoint = lambda path: os.path.join(repo['mountpoint'], path)
    for blob in blobs:
        ret.add(add_mountpoint(relpath(blob)))
    if repo['mountpoint']:
        ret.add(repo['mountpoint'])
    return ret


def symlink_list(load):
    '''
    Return a dict of all symlinks based on a given path in the repo
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    if load['saltenv'] not in envs():
        return {}
    try:
        prefix = load['prefix'].strip('/')
    except KeyError:
        prefix = ''
    symlinks = _file_lists(load, 'symlinks')
    return dict([(key, val)
                 for key, val in symlinks.iteritems()
                 if key.startswith(prefix)])
