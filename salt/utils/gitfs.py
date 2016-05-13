# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import copy
import contextlib
import distutils.version  # pylint: disable=import-error,no-name-in-module
import errno
import fnmatch
import glob
import hashlib
import logging
import os
import re
import shlex
import shutil
import stat
import subprocess
import time
from datetime import datetime

# Import salt libs
import salt.utils
import salt.utils.itertools
import salt.utils.url
import salt.fileserver
from salt.utils.process import os_is_running as pid_exists
from salt.exceptions import FileserverConfigError, GitLockError, get_error_message
from salt.utils.event import tagify

# Import third party libs
import salt.ext.six as six

VALID_PROVIDERS = ('gitpython', 'pygit2', 'dulwich')
# Optional per-remote params that can only be used on a per-remote basis, and
# thus do not have defaults in salt/config.py.
PER_REMOTE_ONLY = ('name',)
SYMLINK_RECURSE_DEPTH = 100

# Auth support (auth params can be global or per-remote, too)
AUTH_PROVIDERS = ('pygit2',)
AUTH_PARAMS = ('user', 'password', 'pubkey', 'privkey', 'passphrase',
               'insecure_auth')

_RECOMMEND_GITPYTHON = (
    'GitPython is installed, you may wish to set {0}_provider to '
    '\'gitpython\' to use GitPython for {0} support.'
)

_RECOMMEND_PYGIT2 = (
    'pygit2 is installed, you may wish to set {0}_provider to '
    '\'pygit2\' to use pygit2 for for {0} support.'
)

_RECOMMEND_DULWICH = (
    'Dulwich is installed, you may wish to set {0}_provider to '
    '\'dulwich\' to use Dulwich for {0} support.'
)

_INVALID_REPO = (
    'Cache path {0} (corresponding remote: {1}) exists but is not a valid '
    'git repository. You will need to manually delete this directory on the '
    'master to continue to use this {2} remote.'
)

log = logging.getLogger(__name__)

# pylint: disable=import-error
try:
    import git
    import gitdb
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False

try:
    import pygit2
    HAS_PYGIT2 = True
    try:
        GitError = pygit2.errors.GitError
    except AttributeError:
        GitError = Exception
except Exception as err:  # cffi VerificationError also may happen
    HAS_PYGIT2 = False    # and pygit2 requrests re-compilation
                          # on a production system (!),
                          # but cffi might be absent as well!
                          # Therefore just a generic Exception class.
    if not isinstance(err, ImportError):
        log.error('Import pygit2 failed: {0}'.format(err))

try:
    import dulwich.errors
    import dulwich.repo
    import dulwich.client
    import dulwich.config
    import dulwich.objects
    HAS_DULWICH = True
except ImportError:
    HAS_DULWICH = False
# pylint: enable=import-error

# Minimum versions for backend providers
GITPYTHON_MINVER = '0.3'
PYGIT2_MINVER = '0.20.3'
LIBGIT2_MINVER = '0.20.0'
# dulwich.__version__ is a versioninfotuple so we can compare tuples
# instead of using distutils.version.LooseVersion
DULWICH_MINVER = (0, 9, 4)


def failhard(role):
    '''
    Fatal configuration issue, raise an exception
    '''
    raise FileserverConfigError('Failed to load {0}'.format(role))


class GitProvider(object):
    '''
    Base class for gitfs/git_pillar provider classes. Should never be used
    directly.

    self.provider should be set in the sub-class' __init__ function before
    invoking GitProvider.__init__().
    '''
    def __init__(self, opts, remote, per_remote_defaults,
                 override_params, cache_root, role='gitfs'):
        self.opts = opts
        self.role = role
        self.env_blacklist = self.opts.get(
            '{0}_env_blacklist'.format(self.role), [])
        self.env_whitelist = self.opts.get(
            '{0}_env_whitelist'.format(self.role), [])
        repo_conf = copy.deepcopy(per_remote_defaults)

        per_remote_collisions = [x for x in override_params
                                 if x in PER_REMOTE_ONLY]
        if per_remote_collisions:
            log.critical(
                'The following parameter names are restricted to per-remote '
                'use only: {0}. This is a bug, please report it.'.format(
                    ', '.join(per_remote_collisions)
                )
            )

        try:
            valid_per_remote_params = override_params + PER_REMOTE_ONLY
        except TypeError:
            valid_per_remote_params = \
                list(override_params) + list(PER_REMOTE_ONLY)

        if isinstance(remote, dict):
            self.id = next(iter(remote))
            self.get_url()
            per_remote_conf = dict(
                [(key, six.text_type(val)) for key, val in
                 six.iteritems(salt.utils.repack_dictlist(remote[self.id]))]
            )
            if not per_remote_conf:
                log.critical(
                    'Invalid per-remote configuration for {0} remote \'{1}\'. '
                    'If no per-remote parameters are being specified, there '
                    'may be a trailing colon after the URL, which should be '
                    'removed. Check the master configuration file.'
                    .format(self.role, self.id)
                )
                failhard(self.role)

            # Separate the per-remote-only (non-global) parameters
            per_remote_only = {}
            for param in PER_REMOTE_ONLY:
                if param in per_remote_conf:
                    per_remote_only[param] = per_remote_conf.pop(param)

            per_remote_errors = False
            for param in (x for x in per_remote_conf
                          if x not in valid_per_remote_params):
                if param in AUTH_PARAMS \
                        and self.provider not in AUTH_PROVIDERS:
                    msg = (
                        '{0} authentication parameter \'{1}\' (from remote '
                        '\'{2}\') is only supported by the following '
                        'provider(s): {3}. Current {0}_provider is \'{4}\'.'
                        .format(
                            self.role,
                            param,
                            self.id,
                            ', '.join(AUTH_PROVIDERS),
                            self.provider
                        )
                    )
                    if self.role == 'gitfs':
                        msg += (
                            'See the GitFS Walkthrough in the Salt '
                            'documentation for further information.'
                        )
                    log.critical(msg)
                else:
                    msg = (
                        'Invalid {0} configuration parameter \'{1}\' in '
                        'remote {2}. Valid parameters are: {3}.'.format(
                            self.role,
                            param,
                            self.url,
                            ', '.join(valid_per_remote_params)
                        )
                    )
                    if self.role == 'gitfs':
                        msg += (
                            ' See the GitFS Walkthrough in the Salt '
                            'documentation for further information.'
                        )
                    log.critical(msg)

                per_remote_errors = True
            if per_remote_errors:
                failhard(self.role)

            repo_conf.update(per_remote_conf)
            repo_conf.update(per_remote_only)
        else:
            self.id = remote
            self.get_url()

        # Winrepo doesn't support the 'root' option, but it still must be part
        # of the GitProvider object because other code depends on it. Add it as
        # an empty string.
        if 'root' not in repo_conf:
            repo_conf['root'] = ''

        if self.role == 'winrepo' and 'name' not in repo_conf:
            # Ensure that winrepo has the 'name' parameter set if it wasn't
            # provided. Default to the last part of the URL, minus the .git if
            # it is present.
            repo_conf['name'] = self.url.rsplit('/', 1)[-1]
            # Remove trailing .git from name
            if repo_conf['name'].lower().endswith('.git'):
                repo_conf['name'] = repo_conf['name'][:-4]

        # Set all repo config params as attributes
        for key, val in six.iteritems(repo_conf):
            setattr(self, key, val)

        if hasattr(self, 'mountpoint'):
            self.mountpoint = salt.utils.url.strip_proto(self.mountpoint)
        else:
            # For providers which do not use a mountpoint, assume the
            # filesystem is mounted at the root of the fileserver.
            self.mountpoint = ''

        if not isinstance(self.url, six.string_types):
            log.critical(
                'Invalid {0} remote \'{1}\'. Remotes must be strings, you '
                'may need to enclose the URL in quotes'.format(
                    self.role,
                    self.id
                )
            )
            failhard(self.role)

        hash_type = getattr(hashlib, self.opts.get('hash_type', 'md5'))
        self.hash = hash_type(self.id).hexdigest()
        self.cachedir_basename = getattr(self, 'name', self.hash)
        self.cachedir = os.path.join(cache_root, self.cachedir_basename)
        if not os.path.isdir(self.cachedir):
            os.makedirs(self.cachedir)

        try:
            self.new = self.init_remote()
        except Exception as exc:
            msg = ('Exception caught while initializing {0} remote \'{1}\': '
                   '{2}'.format(self.role, self.id, exc))
            if isinstance(self, GitPython):
                msg += ' Perhaps git is not available.'
            log.critical(msg, exc_info_on_loglevel=logging.DEBUG)
            failhard(self.role)

    def _get_envs_from_ref_paths(self, refs):
        '''
        Return the names of remote refs (stripped of the remote name) and tags
        which are exposed as environments. If a branch or tag matches
        '''
        def _check_ref(env_set, base_ref, rname):
            '''
            Check the ref and resolve it as the base_ref if it matches. If the
            resulting env is exposed via whitelist/blacklist, add it to the
            env_set.
            '''
            if base_ref is not None and base_ref == rname:
                rname = 'base'
            if self.env_is_exposed(rname):
                env_set.add(rname)

        ret = set()
        base_ref = getattr(self, 'base', None)
        for ref in refs:
            ref = re.sub('^refs/', '', ref)
            rtype, rname = ref.split('/', 1)
            if rtype == 'remotes':
                parted = rname.partition('/')
                rname = parted[2] if parted[2] else parted[0]
                _check_ref(ret, base_ref, rname)
            elif rtype == 'tags':
                _check_ref(ret, base_ref, rname)
        return ret

    def _get_lock_file(self, lock_type='update'):
        return os.path.join(self.gitdir, lock_type + '.lk')

    def check_root(self):
        '''
        Check if the relative root path exists in the checked-out copy of the
        remote. Return the full path to that relative root if it does exist,
        otherwise return None.
        '''
        root_dir = os.path.join(self.cachedir, self.root).rstrip(os.sep)
        if os.path.isdir(root_dir):
            return root_dir
        log.error(
            'Root path \'{0}\' not present in {1} remote \'{2}\', '
            'skipping.'.format(self.root, self.role, self.id)
        )
        return None

    def clean_stale_refs(self):
        '''
        Not all providers need stale refs to be cleaned manually. Override this
        function in a sub-class if this is needed.
        '''
        return []

    def clear_lock(self, lock_type='update'):
        '''
        Clear update.lk
        '''
        lock_file = self._get_lock_file(lock_type=lock_type)

        def _add_error(errlist, exc):
            msg = ('Unable to remove update lock for {0} ({1}): {2} '
                   .format(self.url, lock_file, exc))
            log.debug(msg)
            errlist.append(msg)

        success = []
        failed = []

        try:
            os.remove(lock_file)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                # No lock file present
                pass
            elif exc.errno == errno.EISDIR:
                # Somehow this path is a directory. Should never happen
                # unless some wiseguy manually creates a directory at this
                # path, but just in case, handle it.
                try:
                    shutil.rmtree(lock_file)
                except OSError as exc:
                    _add_error(failed, exc)
            else:
                _add_error(failed, exc)
        else:
            msg = 'Removed {0} lock for {1} remote \'{2}\''.format(
                lock_type,
                self.role,
                self.id
            )
            log.debug(msg)
            success.append(msg)
        return success, failed

    def fetch(self):
        '''
        Fetch the repo. If the local copy was updated, return True. If the
        local copy was already up-to-date, return False.

        This function requires that a _fetch() function be implemented in a
        sub-class.
        '''
        try:
            with self.gen_lock(lock_type='update'):
                log.debug('Fetching %s remote \'%s\'', self.role, self.id)
                # Run provider-specific fetch code
                return self._fetch()
        except GitLockError as exc:
            if exc.errno == errno.EEXIST:
                log.warning(
                    'Update lock file is present for %s remote \'%s\', '
                    'skipping. If this warning persists, it is possible that '
                    'the update process was interrupted, but the lock could '
                    'also have been manually set. Removing %s or running '
                    '\'salt-run cache.clear_git_lock %s type=update\' will '
                    'allow updates to continue for this remote.',
                    self.role,
                    self.id,
                    self._get_lock_file(lock_type='update'),
                    self.role,
                )
            return False

    def _lock(self, lock_type='update', failhard=False):
        '''
        Place a lock file if (and only if) it does not already exist.
        '''
        try:
            fh_ = os.open(self._get_lock_file(lock_type),
                          os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fh_, 'w'):
                # Write the lock file and close the filehandle
                os.write(fh_, str(os.getpid()))
        except (OSError, IOError) as exc:
            if exc.errno == errno.EEXIST:
                with salt.utils.fopen(self._get_lock_file(lock_type), 'r') as fd_:
                    try:
                        pid = int(fd_.readline().rstrip())
                    except ValueError:
                        # Lock file is empty, set pid to 0 so it evaluates as
                        # False.
                        pid = 0
                #if self.opts.get("gitfs_global_lock") or pid and pid_exists(int(pid)):
                global_lock_key = self.role + '_global_lock'
                lock_file = self._get_lock_file(lock_type=lock_type)
                if self.opts[global_lock_key]:
                    msg = (
                        '{0} is enabled and {1} lockfile {2} is present for '
                        '{3} remote \'{4}\'.'.format(
                            global_lock_key,
                            lock_type,
                            lock_file,
                            self.role,
                            self.id,
                        )
                    )
                    if pid:
                        msg += ' Process {0} obtained the lock'.format(pid)
                        if not pid_exists(pid):
                            msg += (' but this process is not running. The '
                                    'update may have been interrupted. If '
                                    'using multi-master with shared gitfs '
                                    'cache, the lock may have been obtained '
                                    'by another master.')
                    log.warning(msg)
                    if failhard:
                        raise
                    return
                elif pid and pid_exists(pid):
                    log.warning('Process %d has a %s %s lock (%s)',
                                pid, self.role, lock_type, lock_file)
                    if failhard:
                        raise
                    return
                else:
                    if pid:
                        log.warning(
                            'Process %d has a %s %s lock (%s), but this '
                            'process is not running. Cleaning up lock file.',
                            pid, self.role, lock_type, lock_file
                        )
                    success, fail = self.clear_lock()
                    if success:
                        return self._lock(lock_type='update',
                                          failhard=failhard)
                    elif failhard:
                        raise
                    return
            else:
                msg = 'Unable to set {0} lock for {1} ({2}): {3} '.format(
                    lock_type,
                    self.id,
                    self._get_lock_file(lock_type),
                    exc
                )
                log.error(msg)
                raise GitLockError(exc.errno, msg)
        msg = 'Set {0} lock for {1} remote \'{2}\''.format(
            lock_type,
            self.role,
            self.id
        )
        log.debug(msg)
        return msg

    def lock(self):
        '''
        Place an lock file and report on the success/failure. This is an
        interface to be used by the fileserver runner, so it is hard-coded to
        perform an update lock. We aren't using the gen_lock()
        contextmanager here because the lock is meant to stay and not be
        automatically removed.
        '''
        success = []
        failed = []
        try:
            result = self._lock(lock_type='update')
        except GitLockError as exc:
            failed.append(exc.strerror)
        else:
            if result is not None:
                success.append(result)
        return success, failed

    @contextlib.contextmanager
    def gen_lock(self, lock_type='update'):
        '''
        Set and automatically clear a lock
        '''
        lock_set = False
        try:
            self._lock(lock_type=lock_type, failhard=True)
            lock_set = True
            yield
        except (OSError, IOError, GitLockError) as exc:
            raise GitLockError(exc.errno, exc.strerror)
        finally:
            if lock_set:
                self.clear_lock(lock_type=lock_type)

    def init_remote(self):
        '''
        This function must be overridden in a sub-class
        '''
        raise NotImplementedError()

    def checkout(self):
        '''
        This function must be overridden in a sub-class
        '''
        raise NotImplementedError()

    def dir_list(self, tgt_env):
        '''
        This function must be overridden in a sub-class
        '''
        raise NotImplementedError()

    def env_is_exposed(self, tgt_env):
        '''
        Check if an environment is exposed by comparing it against a whitelist
        and blacklist.
        '''
        return salt.utils.check_whitelist_blacklist(
            tgt_env,
            whitelist=self.env_whitelist,
            blacklist=self.env_blacklist
        )

    def _fetch(self):
        '''
        Provider-specific code for fetching, must be implemented in a
        sub-class.
        '''
        raise NotImplementedError()

    def envs(self):
        '''
        This function must be overridden in a sub-class
        '''
        raise NotImplementedError()

    def file_list(self, tgt_env):
        '''
        This function must be overridden in a sub-class
        '''
        raise NotImplementedError()

    def find_file(self, path, tgt_env):
        '''
        This function must be overridden in a sub-class
        '''
        raise NotImplementedError()

    def get_tree(self, tgt_env):
        '''
        This function must be overridden in a sub-class
        '''
        raise NotImplementedError()

    def get_url(self):
        '''
        Examine self.id and assign self.url (and self.branch, for git_pillar)
        '''
        if self.role in ('git_pillar', 'winrepo'):
            # With winrepo and git_pillar, the remote is specified in the
            # format '<branch> <url>', so that we can get a unique identifier
            # to hash for each remote.
            try:
                self.branch, self.url = self.id.split(None, 1)
            except ValueError:
                self.branch = self.opts['{0}_branch'.format(self.role)]
                self.url = self.id
        else:
            self.url = self.id

    def verify_auth(self):
        '''
        Override this function in a sub-class to implement auth checking.
        '''
        self.credentials = None
        return True

    def write_file(self, blob, dest):
        '''
        This function must be overridden in a sub-class
        '''
        raise NotImplementedError()


class GitPython(GitProvider):
    '''
    Interface to GitPython
    '''
    def __init__(self, opts, remote, per_remote_defaults,
                 override_params, cache_root, role='gitfs'):
        self.provider = 'gitpython'
        GitProvider.__init__(self, opts, remote, per_remote_defaults,
                             override_params, cache_root, role)

    def checkout(self):
        '''
        Checkout the configured branch/tag. We catch an "Exception" class here
        instead of a specific exception class because the exceptions raised by
        GitPython when running these functions vary in different versions of
        GitPython.
        '''
        try:
            head_sha = self.repo.rev_parse('HEAD').hexsha
        except Exception:
            # Should only happen the first time we are checking out, since
            # we fetch first before ever checking anything out.
            head_sha = None

        # 'origin/' + self.branch ==> matches a branch head
        # 'tags/' + self.branch + '@{commit}' ==> matches tag's commit
        for rev_parse_target, checkout_ref in (
                ('origin/' + self.branch, 'origin/' + self.branch),
                ('tags/' + self.branch + '@{commit}', 'tags/' + self.branch)):
            try:
                target_sha = self.repo.rev_parse(rev_parse_target).hexsha
            except Exception:
                # ref does not exist
                continue
            else:
                if head_sha == target_sha:
                    # No need to checkout, we're already up-to-date
                    return self.check_root()

            try:
                with self.gen_lock(lock_type='checkout'):
                    self.repo.git.checkout(checkout_ref)
                    log.debug(
                        '%s remote \'%s\' has been checked out to %s',
                        self.role,
                        self.id,
                        checkout_ref
                    )
            except GitLockError as exc:
                if exc.errno == errno.EEXIST:
                    # Re-raise with a different strerror containing a
                    # more meaningful error message for the calling
                    # function.
                    raise GitLockError(
                        exc.errno,
                        'Checkout lock exists for {0} remote \'{1}\''
                        .format(self.role, self.id)
                    )
                else:
                    log.error(
                        'Error %d encountered obtaining checkout lock '
                        'for %s remote \'%s\'',
                        exc.errno,
                        self.role,
                        self.id
                    )
                    return None
            except Exception:
                continue
            return self.check_root()
        log.error(
            'Failed to checkout %s from %s remote \'%s\': remote ref does '
            'not exist', self.branch, self.role, self.id
        )
        return None

    def clean_stale_refs(self):
        '''
        Clean stale local refs so they don't appear as fileserver environments
        '''
        cleaned = []
        for ref in self.repo.remotes[0].stale_refs:
            if ref.name.startswith('refs/tags/'):
                # Work around GitPython bug affecting removal of tags
                # https://github.com/gitpython-developers/GitPython/issues/260
                self.repo.git.tag('-d', ref.name[10:])
            else:
                ref.delete(self.repo, ref)
            cleaned.append(ref)
        if cleaned:
            log.debug('{0} cleaned the following stale refs: {1}'
                      .format(self.role, cleaned))
        return cleaned

    def init_remote(self):
        '''
        Initialize/attach to a remote using GitPython. Return a boolean
        which will let the calling function know whether or not a new repo was
        initialized by this function.
        '''
        new = False
        if not os.listdir(self.cachedir):
            # Repo cachedir is empty, initialize a new repo there
            self.repo = git.Repo.init(self.cachedir)
            new = True
        else:
            # Repo cachedir exists, try to attach
            try:
                self.repo = git.Repo(self.cachedir)
            except git.exc.InvalidGitRepositoryError:
                log.error(_INVALID_REPO.format(self.cachedir, self.url, self.role))
                return new

        self.gitdir = os.path.join(self.repo.working_dir, '.git')

        if not self.repo.remotes:
            try:
                self.repo.create_remote('origin', self.url)
                # Ensure tags are also fetched
                self.repo.git.config('--add',
                                     'remote.origin.fetch',
                                     '+refs/tags/*:refs/tags/*')
                self.repo.git.config('http.sslVerify', self.ssl_verify)
            except os.error:
                # This exception occurs when two processes are trying to write
                # to the git config at once, go ahead and pass over it since
                # this is the only write. This should place a lock down.
                pass
            else:
                new = True
        return new

    def dir_list(self, tgt_env):
        '''
        Get list of directories for the target environment using GitPython
        '''
        ret = set()
        tree = self.get_tree(tgt_env)
        if not tree:
            return ret
        if self.root:
            try:
                tree = tree / self.root
            except KeyError:
                return ret
            relpath = lambda path: os.path.relpath(path, self.root)
        else:
            relpath = lambda path: path
        add_mountpoint = lambda path: os.path.join(self.mountpoint, path)
        for blob in tree.traverse():
            if isinstance(blob, git.Tree):
                ret.add(add_mountpoint(relpath(blob.path)))
        if self.mountpoint:
            ret.add(self.mountpoint)
        return ret

    def envs(self):
        '''
        Check the refs and return a list of the ones which can be used as salt
        environments.
        '''
        ref_paths = [x.path for x in self.repo.refs]
        return self._get_envs_from_ref_paths(ref_paths)

    def _fetch(self):
        '''
        Fetch the repo. If the local copy was updated, return True. If the
        local copy was already up-to-date, return False.
        '''
        origin = self.repo.remotes[0]
        try:
            fetch_results = origin.fetch()
        except AssertionError:
            fetch_results = origin.fetch()

        new_objs = False
        for fetchinfo in fetch_results:
            if fetchinfo.old_commit is not None:
                log.debug(
                    '{0} has updated \'{1}\' for remote \'{2}\' '
                    'from {3} to {4}'.format(
                        self.role,
                        fetchinfo.name,
                        self.id,
                        fetchinfo.old_commit.hexsha[:7],
                        fetchinfo.commit.hexsha[:7]
                    )
                )
                new_objs = True
            elif fetchinfo.flags in (fetchinfo.NEW_TAG,
                                     fetchinfo.NEW_HEAD):
                log.debug(
                    '{0} has fetched new {1} \'{2}\' for remote \'{3}\' '
                    .format(
                        self.role,
                        'tag' if fetchinfo.flags == fetchinfo.NEW_TAG
                            else 'head',
                        fetchinfo.name,
                        self.id
                    )
                )
                new_objs = True

        cleaned = self.clean_stale_refs()
        return bool(new_objs or cleaned)

    def file_list(self, tgt_env):
        '''
        Get file list for the target environment using GitPython
        '''
        files = set()
        symlinks = {}
        tree = self.get_tree(tgt_env)
        if not tree:
            # Not found, return empty objects
            return files, symlinks
        if self.root:
            try:
                tree = tree / self.root
            except KeyError:
                return files, symlinks
            relpath = lambda path: os.path.relpath(path, self.root)
        else:
            relpath = lambda path: path
        add_mountpoint = lambda path: os.path.join(self.mountpoint, path)
        for file_blob in tree.traverse():
            if not isinstance(file_blob, git.Blob):
                continue
            file_path = add_mountpoint(relpath(file_blob.path))
            files.add(file_path)
            if stat.S_ISLNK(file_blob.mode):
                stream = six.StringIO()
                file_blob.stream_data(stream)
                stream.seek(0)
                link_tgt = stream.read()
                stream.close()
                symlinks[file_path] = link_tgt
        return files, symlinks

    def find_file(self, path, tgt_env):
        '''
        Find the specified file in the specified environment
        '''
        tree = self.get_tree(tgt_env)
        if not tree:
            # Branch/tag/SHA not found
            return None, None
        blob = None
        depth = 0
        while True:
            depth += 1
            if depth > SYMLINK_RECURSE_DEPTH:
                break
            try:
                file_blob = tree / path
                if stat.S_ISLNK(file_blob.mode):
                    # Path is a symlink. The blob data corresponding to
                    # this path's object ID will be the target of the
                    # symlink. Follow the symlink and set path to the
                    # location indicated in the blob data.
                    stream = six.StringIO()
                    file_blob.stream_data(stream)
                    stream.seek(0)
                    link_tgt = stream.read()
                    stream.close()
                    path = os.path.normpath(
                        os.path.join(os.path.dirname(path), link_tgt)
                    )
                else:
                    blob = file_blob
                    break
            except KeyError:
                # File not found or repo_path points to a directory
                break
        return blob, blob.hexsha if blob is not None else blob

    def get_tree(self, tgt_env):
        '''
        Return a git.Tree object if the branch/tag/SHA is found, otherwise None
        '''
        if tgt_env == 'base':
            tgt_ref = self.base
        else:
            tgt_ref = tgt_env
        for ref in self.repo.refs:
            if isinstance(ref, (git.RemoteReference, git.TagReference)):
                parted = ref.name.partition('/')
                rspec = parted[2] if parted[2] else parted[0]
                if rspec == tgt_ref:
                    return ref.commit.tree

        # Branch or tag not matched, check if 'tgt_env' is a commit
        if not self.env_is_exposed(tgt_env):
            return None

        try:
            commit = self.repo.rev_parse(tgt_ref)
            return commit.tree
        except gitdb.exc.ODBError:
            return None

    def write_file(self, blob, dest):
        '''
        Using the blob object, write the file to the destination path
        '''
        with salt.utils.fopen(dest, 'w+') as fp_:
            blob.stream_data(fp_)


class Pygit2(GitProvider):
    '''
    Interface to Pygit2
    '''
    def __init__(self, opts, remote, per_remote_defaults,
                 override_params, cache_root, role='gitfs'):
        self.provider = 'pygit2'
        self.use_callback = \
            distutils.version.LooseVersion(pygit2.__version__) >= \
            distutils.version.LooseVersion('0.23.2')
        GitProvider.__init__(self, opts, remote, per_remote_defaults,
                             override_params, cache_root, role)

    def checkout(self):
        '''
        Checkout the configured branch/tag
        '''
        local_ref = 'refs/heads/' + self.branch
        remote_ref = 'refs/remotes/origin/' + self.branch
        tag_ref = 'refs/tags/' + self.branch

        try:
            local_head = self.repo.lookup_reference('HEAD')
        except KeyError:
            log.warning(
                'HEAD not present in %s remote \'%s\'', self.role, self.id
            )
            return None

        try:
            head_sha = local_head.get_object().hex
        except AttributeError:
            # Shouldn't happen, but just in case a future pygit2 API change
            # breaks things, avoid a traceback and log an error.
            log.error(
                'Unable to get SHA of HEAD for %s remote \'%s\'',
                self.role, self.id
            )
            return None
        except KeyError:
            head_sha = None

        refs = self.repo.listall_references()

        def _perform_checkout(checkout_ref, branch=True):
            '''
            DRY function for checking out either a branch or a tag
            '''
            try:
                with self.gen_lock(lock_type='checkout'):
                    # Checkout the local branch corresponding to the
                    # remote ref.
                    self.repo.checkout(checkout_ref)
                    if branch:
                        self.repo.reset(oid, pygit2.GIT_RESET_HARD)
                return True
            except GitLockError as exc:
                if exc.errno == errno.EEXIST:
                    # Re-raise with a different strerror containing a
                    # more meaningful error message for the calling
                    # function.
                    raise GitLockError(
                        exc.errno,
                        'Checkout lock exists for {0} remote \'{1}\''
                        .format(self.role, self.id)
                    )
                else:
                    log.error(
                        'Error %d encountered obtaining checkout lock '
                        'for %s remote \'%s\'',
                        exc.errno,
                        self.role,
                        self.id
                    )
            return False

        try:
            if remote_ref in refs:
                # Get commit id for the remote ref
                oid = self.repo.lookup_reference(remote_ref).get_object().id
                if local_ref not in refs:
                    # No local branch for this remote, so create one and point
                    # it at the commit id of the remote ref
                    self.repo.create_reference(local_ref, oid)

                try:
                    target_sha = \
                        self.repo.lookup_reference(remote_ref).get_object().hex
                except KeyError:
                    log.error(
                        'pygit2 was unable to get SHA for %s in %s remote '
                        '\'%s\'', local_ref, self.role, self.id
                    )
                    return None

                # Only perform a checkout if HEAD and target are not pointing
                # at the same SHA1.
                if head_sha != target_sha:
                    # Check existence of the ref in refs/heads/ which
                    # corresponds to the local HEAD. Checking out local_ref
                    # below when no local ref for HEAD is missing will raise an
                    # exception in pygit2 >= 0.21. If this ref is not present,
                    # create it. The "head_ref != local_ref" check ensures we
                    # don't try to add this ref if it is not necessary, as it
                    # would have been added above already. head_ref would be
                    # the same as local_ref if the branch name was changed but
                    # the cachedir was not (for example if a "name" parameter
                    # was used in a git_pillar remote, or if we are using
                    # winrepo which takes the basename of the repo as the
                    # cachedir).
                    head_ref = local_head.target
                    # If head_ref is not a string, it will point to a
                    # pygit2.Oid object and we are in detached HEAD mode.
                    # Therefore, there is no need to add a local reference. If
                    # head_ref == local_ref, then the local reference for HEAD
                    # in refs/heads/ already exists and again, no need to add.
                    if isinstance(head_ref, six.string_types) \
                            and head_ref not in refs and head_ref != local_ref:
                        branch_name = head_ref.partition('refs/heads/')[-1]
                        if not branch_name:
                            # Shouldn't happen, but log an error if it does
                            log.error(
                                'pygit2 was unable to resolve branch name from '
                                'HEAD ref \'{0}\' in {1} remote \'{2}\''.format(
                                    head_ref, self.role, self.id
                                )
                            )
                            return None
                        remote_head = 'refs/remotes/origin/' + branch_name
                        if remote_head not in refs:
                            log.error(
                                'Unable to find remote ref \'{0}\' in {1} remote '
                                '\'{2}\''.format(head_ref, self.role, self.id)
                            )
                            return None
                        self.repo.create_reference(
                            head_ref,
                            self.repo.lookup_reference(remote_head).target
                        )

                    if not _perform_checkout(local_ref, branch=True):
                        return None

                # Return the relative root, if present
                return self.check_root()

            elif tag_ref in refs:
                tag_obj = self.repo.revparse_single(tag_ref)
                if not isinstance(tag_obj, pygit2.Tag):
                    log.error(
                        '%s does not correspond to pygit2.Tag object',
                        tag_ref
                    )
                else:
                    try:
                        # If no AttributeError raised, this is an annotated tag
                        tag_sha = tag_obj.target.hex
                    except AttributeError:
                        try:
                            tag_sha = tag_obj.hex
                        except AttributeError:
                            # Shouldn't happen, but could if a future pygit2
                            # API change breaks things.
                            log.error(
                                'Unable to resolve %s from %s remote \'%s\' '
                                'to either an annotated or non-annotated tag',
                                tag_ref, self.role, self.id
                            )
                            return None

                    if head_sha != target_sha:
                        if not _perform_checkout(local_ref, branch=False):
                            return None

                    # Return the relative root, if present
                    return self.check_root()
        except GitLockError:
            raise
        except Exception as exc:
            log.error(
                'Failed to checkout {0} from {1} remote \'{2}\': {3}'.format(
                    self.branch,
                    self.role,
                    self.id,
                    exc
                ),
                exc_info_on_loglevel=logging.DEBUG
            )
            return None
        log.error(
            'Failed to checkout {0} from {1} remote \'{2}\': remote ref '
            'does not exist'.format(self.branch, self.role, self.id)
        )
        return None

    def clean_stale_refs(self, local_refs=None):  # pylint: disable=arguments-differ
        '''
        Clean stale local refs so they don't appear as fileserver environments
        '''
        if self.credentials is not None:
            log.debug(
                'pygit2 does not support detecting stale refs for '
                'authenticated remotes, saltenvs will not reflect '
                'branches/tags removed from remote \'{0}\''
                .format(self.id)
            )
            return []
        if local_refs is None:
            local_refs = self.repo.listall_references()
        remote_refs = []
        cmd_str = 'git ls-remote origin'
        cmd = subprocess.Popen(
            shlex.split(cmd_str),
            close_fds=not salt.utils.is_windows(),
            cwd=self.repo.workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        output = cmd.communicate()[0]
        if cmd.returncode != 0:
            log.warning(
                'Failed to list remote references for {0} remote \'{1}\'. '
                'Output from \'{2}\' follows:\n{3}'.format(
                    self.role,
                    self.id,
                    cmd_str,
                    output
                )
            )
            return []
        for line in salt.utils.itertools.split(output, '\n'):
            try:
                # Rename heads to match the remote ref names from
                # pygit2.Repository.listall_references()
                remote_refs.append(
                    line.split()[-1].replace(b'refs/heads/',
                                             b'refs/remotes/origin/')
                )
            except IndexError:
                continue
        cleaned = []
        if remote_refs:
            for ref in local_refs:
                if ref.startswith('refs/heads/'):
                    # Local head, ignore it
                    continue
                elif ref not in remote_refs:
                    self.repo.lookup_reference(ref).delete()
                    cleaned.append(ref)
        if cleaned:
            log.debug('{0} cleaned the following stale refs: {1}'
                      .format(self.role, cleaned))
        return cleaned

    def init_remote(self):
        '''
        Initialize/attach to a remote using pygit2. Return a boolean which
        will let the calling function know whether or not a new repo was
        initialized by this function.
        '''
        new = False
        if not os.listdir(self.cachedir):
            # Repo cachedir is empty, initialize a new repo there
            self.repo = pygit2.init_repository(self.cachedir)
            new = True
        else:
            # Repo cachedir exists, try to attach
            try:
                try:
                    self.repo = pygit2.Repository(self.cachedir)
                except pygit2.GitError as exc:
                    import pwd
                    # https://github.com/libgit2/pygit2/issues/339
                    # https://github.com/libgit2/libgit2/issues/2122
                    if "Error stat'ing config file" not in str(exc):
                        raise
                    home = pwd.getpwnam(salt.utils.get_user()).pw_dir
                    pygit2.settings.search_path[pygit2.GIT_CONFIG_LEVEL_GLOBAL] = home
                    self.repo = pygit2.Repository(self.cachedir)
            except KeyError:
                log.error(_INVALID_REPO.format(self.cachedir, self.url, self.role))
                return new

        self.gitdir = os.path.join(self.repo.workdir, '.git')

        if not self.repo.remotes:
            try:
                self.repo.create_remote('origin', self.url)
                # Ensure tags are also fetched
                self.repo.config.set_multivar(
                    'remote.origin.fetch',
                    'FOO',
                    '+refs/tags/*:refs/tags/*'
                )
                self.repo.config.set_multivar(
                    'http.sslVerify',
                    '',
                    self.ssl_verify
                )
            except os.error:
                # This exception occurs when two processes are trying to write
                # to the git config at once, go ahead and pass over it since
                # this is the only write. This should place a lock down.
                pass
            else:
                new = True
        return new

    def dir_list(self, tgt_env):
        '''
        Get a list of directories for the target environment using pygit2
        '''
        def _traverse(tree, blobs, prefix):
            '''
            Traverse through a pygit2 Tree object recursively, accumulating all
            the empty directories within it in the "blobs" list
            '''
            for entry in iter(tree):
                if entry.oid not in self.repo:
                    # Entry is a submodule, skip it
                    continue
                blob = self.repo[entry.oid]
                if not isinstance(blob, pygit2.Tree):
                    continue
                blobs.append(os.path.join(prefix, entry.name))
                if len(blob):
                    _traverse(blob, blobs, os.path.join(prefix, entry.name))

        ret = set()
        tree = self.get_tree(tgt_env)
        if not tree:
            return ret
        if self.root:
            try:
                oid = tree[self.root].oid
                tree = self.repo[oid]
            except KeyError:
                return ret
            if not isinstance(tree, pygit2.Tree):
                return ret
            relpath = lambda path: os.path.relpath(path, self.root)
        else:
            relpath = lambda path: path
        blobs = []
        if len(tree):
            _traverse(tree, blobs, self.root)
        add_mountpoint = lambda path: os.path.join(self.mountpoint, path)
        for blob in blobs:
            ret.add(add_mountpoint(relpath(blob)))
        if self.mountpoint:
            ret.add(self.mountpoint)
        return ret

    def envs(self):
        '''
        Check the refs and return a list of the ones which can be used as salt
        environments.
        '''
        ref_paths = self.repo.listall_references()
        return self._get_envs_from_ref_paths(ref_paths)

    def _fetch(self):
        '''
        Fetch the repo. If the local copy was updated, return True. If the
        local copy was already up-to-date, return False.
        '''
        origin = self.repo.remotes[0]
        refs_pre = self.repo.listall_references()
        fetch_kwargs = {}
        if self.credentials is not None:
            if self.use_callback:
                fetch_kwargs['callbacks'] = \
                    pygit2.RemoteCallbacks(credentials=self.credentials)
            else:
                origin.credentials = self.credentials
        try:
            fetch_results = origin.fetch(**fetch_kwargs)
        except GitError as exc:
            exc_str = get_error_message(exc).lower()
            if 'unsupported url protocol' in exc_str \
                    and isinstance(self.credentials, pygit2.Keypair):
                log.error(
                    'Unable to fetch SSH-based {0} remote \'{1}\'. '
                    'You may need to add ssh:// to the repo string or '
                    'libgit2 must be compiled with libssh2 to support '
                    'SSH authentication.'.format(self.role, self.id)
                )
            elif 'authentication required but no callback set' in exc_str:
                log.error(
                    '{0} remote \'{1}\' requires authentication, but no '
                    'authentication configured'.format(self.role, self.id)
                )
            else:
                log.error(
                    'Error occured fetching {0} remote \'{1}\': {2}'.format(
                        self.role, self.id, exc
                    )
                )
            return False
        try:
            # pygit2.Remote.fetch() returns a dict in pygit2 < 0.21.0
            received_objects = fetch_results['received_objects']
        except (AttributeError, TypeError):
            # pygit2.Remote.fetch() returns a class instance in
            # pygit2 >= 0.21.0
            received_objects = fetch_results.received_objects
        if received_objects != 0:
            log.debug(
                '{0} received {1} objects for remote \'{2}\''
                .format(self.role, received_objects, self.id)
            )
        else:
            log.debug(
                '{0} remote \'{1}\' is up-to-date'.format(self.role, self.id)
            )
        refs_post = self.repo.listall_references()
        cleaned = self.clean_stale_refs(local_refs=refs_post)
        return bool(received_objects or refs_pre != refs_post or cleaned)

    def file_list(self, tgt_env):
        '''
        Get file list for the target environment using pygit2
        '''
        def _traverse(tree, blobs, prefix):
            '''
            Traverse through a pygit2 Tree object recursively, accumulating all
            the file paths and symlink info in the "blobs" dict
            '''
            for entry in iter(tree):
                if entry.oid not in self.repo:
                    # Entry is a submodule, skip it
                    continue
                obj = self.repo[entry.oid]
                if isinstance(obj, pygit2.Blob):
                    repo_path = os.path.join(prefix, entry.name)
                    blobs.setdefault('files', []).append(repo_path)
                    if stat.S_ISLNK(tree[entry.name].filemode):
                        link_tgt = self.repo[tree[entry.name].oid].data
                        blobs.setdefault('symlinks', {})[repo_path] = link_tgt
                elif isinstance(obj, pygit2.Tree):
                    _traverse(obj, blobs, os.path.join(prefix, entry.name))

        files = set()
        symlinks = {}
        tree = self.get_tree(tgt_env)
        if not tree:
            # Not found, return empty objects
            return files, symlinks
        if self.root:
            try:
                # This might need to be changed to account for a root that
                # spans more than one directory
                oid = tree[self.root].oid
                tree = self.repo[oid]
            except KeyError:
                return files, symlinks
            if not isinstance(tree, pygit2.Tree):
                return files, symlinks
            relpath = lambda path: os.path.relpath(path, self.root)
        else:
            relpath = lambda path: path
        blobs = {}
        if len(tree):
            _traverse(tree, blobs, self.root)
        add_mountpoint = lambda path: os.path.join(self.mountpoint, path)
        for repo_path in blobs.get('files', []):
            files.add(add_mountpoint(relpath(repo_path)))
        for repo_path, link_tgt in six.iteritems(blobs.get('symlinks', {})):
            symlinks[add_mountpoint(relpath(repo_path))] = link_tgt
        return files, symlinks

    def find_file(self, path, tgt_env):
        '''
        Find the specified file in the specified environment
        '''
        tree = self.get_tree(tgt_env)
        if not tree:
            # Branch/tag/SHA not found in repo
            return None, None
        blob = None
        depth = 0
        while True:
            depth += 1
            if depth > SYMLINK_RECURSE_DEPTH:
                break
            try:
                if stat.S_ISLNK(tree[path].filemode):
                    # Path is a symlink. The blob data corresponding to this
                    # path's object ID will be the target of the symlink. Follow
                    # the symlink and set path to the location indicated
                    # in the blob data.
                    link_tgt = self.repo[tree[path].oid].data
                    path = os.path.normpath(
                        os.path.join(os.path.dirname(path), link_tgt)
                    )
                else:
                    oid = tree[path].oid
                    blob = self.repo[oid]
            except KeyError:
                break
        return blob, blob.hex if blob is not None else blob

    def get_tree(self, tgt_env):
        '''
        Return a pygit2.Tree object if the branch/tag/SHA is found, otherwise
        None
        '''
        if tgt_env == 'base':
            tgt_ref = self.base
        else:
            tgt_ref = tgt_env
        for ref in self.repo.listall_references():
            _, rtype, rspec = ref.split('/', 2)
            if rtype in ('remotes', 'tags'):
                parted = rspec.partition('/')
                rspec = parted[2] if parted[2] else parted[0]
                if rspec == tgt_ref and self.env_is_exposed(tgt_env):
                    return self.repo.lookup_reference(ref).get_object().tree

        # Branch or tag not matched, check if 'tgt_env' is a commit
        if not self.env_is_exposed(tgt_env):
            return None
        try:
            commit = self.repo.revparse_single(tgt_ref)
        except (KeyError, TypeError):
            # Not a valid commit, likely not a commit SHA
            pass
        else:
            return commit.tree
        return None

    def verify_auth(self):
        '''
        Check the username and password/keypair info for validity. If valid,
        set a 'credentials' attribute consisting of the appropriate Pygit2
        credentials object. Return False if a required auth param is not
        present. Return True if the required auth parameters are present (or
        auth is not configured), otherwise failhard if there is a problem with
        authenticaion.
        '''
        self.credentials = None

        if os.path.isabs(self.url):
            # If the URL is an absolute file path, there is no authentication.
            return True
        elif not any(getattr(self, x, None) for x in AUTH_PARAMS):
            # Auth information not configured for this remote
            return True

        def _incomplete_auth(missing):
            '''
            Helper function to log errors about missing auth parameters
            '''
            log.critical(
                'Incomplete authentication information for {0} remote '
                '\'{1}\'. Missing parameters: {2}'.format(
                    self.role,
                    self.id,
                    ', '.join(missing)
                )
            )
            failhard(self.role)

        transport, _, address = self.url.partition('://')
        if not address:
            # Assume scp-like SSH syntax (user@domain.tld:relative/path.git)
            transport = 'ssh'
            address = self.url

        transport = transport.lower()

        if transport in ('git', 'file'):
            # These transports do not use auth
            return True

        elif 'ssh' in transport:
            required_params = ('pubkey', 'privkey')
            user = address.split('@')[0]
            if user == address:
                # No '@' sign == no user. This is a problem.
                log.critical(
                    'Keypair specified for {0} remote \'{1}\', but remote URL '
                    'is missing a username'.format(self.role, self.id)
                )
                failhard(self.role)

            self.user = user
            if all(bool(getattr(self, x, None)) for x in required_params):
                keypair_params = [getattr(self, x, None) for x in
                                  ('user', 'pubkey', 'privkey', 'passphrase')]
                self.credentials = pygit2.Keypair(*keypair_params)
                return True
            else:
                missing_auth = [x for x in required_params
                                if not bool(getattr(self, x, None))]
                _incomplete_auth(missing_auth)

        elif 'http' in transport:
            required_params = ('user', 'password')
            password_ok = all(
                bool(getattr(self, x, None)) for x in required_params
            )
            no_password_auth = not any(
                bool(getattr(self, x, None)) for x in required_params
            )
            if no_password_auth:
                # No auth params were passed, assuming this is unauthenticated
                # http(s).
                return True
            if password_ok:
                if transport == 'http' and not self.insecure_auth:
                    log.critical(
                        'Invalid configuration for {0} remote \'{1}\'. '
                        'Authentication is disabled by default on http '
                        'remotes. Either set {0}_insecure_auth to True in the '
                        'master configuration file, set a per-remote config '
                        'option named \'insecure_auth\' to True, or use https '
                        'or ssh-based authentication.'.format(
                            self.role,
                            self.id
                        )
                    )
                    failhard(self.role)
                self.credentials = pygit2.UserPass(self.user, self.password)
                return True
            else:
                missing_auth = [x for x in required_params
                                if not bool(getattr(self, x, None))]
                _incomplete_auth(missing_auth)
        else:
            log.critical(
                'Invalid configuration for {0} remote \'{1}\'. Unsupported '
                'transport \'{2}\'.'.format(self.role, self.id, transport)
            )
            failhard(self.role)

    def write_file(self, blob, dest):
        '''
        Using the blob object, write the file to the destination path
        '''
        with salt.utils.fopen(dest, 'w+') as fp_:
            fp_.write(blob.data)


class Dulwich(GitProvider):  # pylint: disable=abstract-method
    '''
    Interface to dulwich
    '''
    def __init__(self, opts, remote, per_remote_defaults,
                 override_params, cache_root, role='gitfs'):
        self.get_env_refs = lambda refs: [
            x for x in refs if re.match('refs/(remotes|tags)', x)
            and not x.endswith('^{}')
        ]
        self.provider = 'dulwich'
        GitProvider.__init__(self, opts, remote, per_remote_defaults,
                             override_params, cache_root, role)

    def dir_list(self, tgt_env):
        '''
        Get a list of directories for the target environment using dulwich
        '''
        def _traverse(tree, blobs, prefix):
            '''
            Traverse through a dulwich Tree object recursively, accumulating
            all the empty directories within it in the "blobs" list
            '''
            for item in six.iteritems(tree):
                try:
                    obj = self.repo.get_object(item.sha)
                except KeyError:
                    # Entry is a submodule, skip it
                    continue
                if not isinstance(obj, dulwich.objects.Tree):
                    continue
                blobs.append(os.path.join(prefix, item.path))
                if len(self.repo.get_object(item.sha)):
                    _traverse(obj, blobs, os.path.join(prefix, item.path))

        ret = set()
        tree = self.get_tree(tgt_env)
        tree = self.walk_tree(tree, self.root)
        if not isinstance(tree, dulwich.objects.Tree):
            return ret
        blobs = []
        if len(tree):
            _traverse(tree, blobs, self.root)
        if self.root:
            relpath = lambda path: os.path.relpath(path, self.root)
        else:
            relpath = lambda path: path
        add_mountpoint = lambda path: os.path.join(self.mountpoint, path)
        for blob in blobs:
            ret.add(add_mountpoint(relpath(blob)))
        if self.mountpoint:
            ret.add(self.mountpoint)
        return ret

    def envs(self):
        '''
        Check the refs and return a list of the ones which can be used as salt
        environments.
        '''
        ref_paths = self.get_env_refs(self.repo.get_refs())
        return self._get_envs_from_ref_paths(ref_paths)

    def _fetch(self):
        '''
        Fetch the repo. If the local copy was updated, return True. If the
        local copy was already up-to-date, return False.
        '''
        # origin is just a url here, there is no origin object
        origin = self.url
        client, path = \
            dulwich.client.get_transport_and_path_from_url(
                origin, thin_packs=True
            )
        refs_pre = self.repo.get_refs()
        try:
            refs_post = client.fetch(path, self.repo)
        except dulwich.errors.NotGitRepository:
            log.error(
                'Dulwich does not recognize {0} as a valid remote '
                'remote URL. Perhaps it is missing \'.git\' at the '
                'end.'.format(self.id)
            )
            return False
        except KeyError:
            log.error(
                'Local repository cachedir \'{0}\' (corresponding '
                'remote: \'{1}\') has been corrupted. Salt will now '
                'attempt to remove the local checkout to allow it to '
                'be re-initialized in the next fileserver cache '
                'update.'
                .format(self.cachedir, self.id)
            )
            try:
                salt.utils.rm_rf(self.cachedir)
            except OSError as exc:
                log.error(
                    'Unable to remove {0}: {1}'.format(self.cachedir, exc)
                )
            return False
        else:
            # Dulwich does not write fetched references to the gitdir, that is
            # done manually below (see the "Update local refs" comment). Since
            # A) gitfs doesn't check out any local branches, B) both Pygit2 and
            # GitPython set remote refs when fetching instead of head refs, and
            # C) Dulwich is not supported for git_pillar or winrepo, there is
            # no harm in simply renaming the head refs from the fetch results
            # to remote refs. This allows the same logic (see the
            # "_get_envs_from_ref_paths()" function) to be used for all three
            # GitProvider subclasses to derive available envs.
            for ref in [x for x in refs_post if x.startswith('refs/heads/')]:
                val = refs_post.pop(ref)
                key = ref.replace('refs/heads/', 'refs/remotes/origin/', 1)
                refs_post[key] = val

        if refs_post is None:
            # Empty repository
            log.warning(
                '{0} remote \'{1}\' is an empty repository and will '
                'be skipped.'.format(self.role, self.id)
            )
            return False
        if refs_pre != refs_post:
            # Update local refs
            for ref in self.get_env_refs(refs_post):
                self.repo[ref] = refs_post[ref]
            # Prune stale refs
            for ref in refs_pre:
                if ref not in refs_post:
                    del self.repo[ref]
            return True
        return False

    def file_list(self, tgt_env):
        '''
        Get file list for the target environment using dulwich
        '''
        def _traverse(tree, blobs, prefix):
            '''
            Traverse through a dulwich Tree object recursively, accumulating
            all the file paths and symlinks info in the "blobs" dict
            '''
            for item in six.iteritems(tree):
                try:
                    obj = self.repo.get_object(item.sha)
                except KeyError:
                    # Entry is a submodule, skip it
                    continue
                if isinstance(obj, dulwich.objects.Blob):
                    repo_path = os.path.join(prefix, item.path)
                    blobs.setdefault('files', []).append(repo_path)
                    mode, oid = tree[item.path]
                    if stat.S_ISLNK(mode):
                        link_tgt = self.repo.get_object(oid).as_raw_string()
                        blobs.setdefault('symlinks', {})[repo_path] = link_tgt
                elif isinstance(obj, dulwich.objects.Tree):
                    _traverse(obj, blobs, os.path.join(prefix, item.path))

        files = set()
        symlinks = {}
        tree = self.get_tree(tgt_env)
        tree = self.walk_tree(tree, self.root)
        if not isinstance(tree, dulwich.objects.Tree):
            return files, symlinks
        blobs = {}
        if len(tree):
            _traverse(tree, blobs, self.root)
        if self.root:
            relpath = lambda path: os.path.relpath(path, self.root)
        else:
            relpath = lambda path: path
        add_mountpoint = lambda path: os.path.join(self.mountpoint, path)
        for repo_path in blobs.get('files', []):
            files.add(add_mountpoint(relpath(repo_path)))
        for repo_path, link_tgt in six.iteritems(blobs.get('symlinks', {})):
            symlinks[add_mountpoint(relpath(repo_path))] = link_tgt
        return files, symlinks

    def find_file(self, path, tgt_env):
        '''
        Find the specified file in the specified environment
        '''
        tree = self.get_tree(tgt_env)
        if not tree:
            # Branch/tag/SHA not found
            return None, None
        blob = None
        depth = 0
        while True:
            depth += 1
            if depth > SYMLINK_RECURSE_DEPTH:
                break
            prefix_dirs, _, filename = path.rpartition(os.path.sep)
            tree = self.walk_tree(tree, prefix_dirs)
            if not isinstance(tree, dulwich.objects.Tree):
                # Branch/tag/SHA not found in repo
                break
            try:
                mode, oid = tree[filename]
                if stat.S_ISLNK(mode):
                    # Path is a symlink. The blob data corresponding to
                    # this path's object ID will be the target of the
                    # symlink. Follow the symlink and set path to the
                    # location indicated in the blob data.
                    link_tgt = self.repo.get_object(oid).as_raw_string()
                    path = os.path.normpath(
                        os.path.join(os.path.dirname(path), link_tgt)
                    )
                else:
                    blob = self.repo.get_object(oid)
                    break
            except KeyError:
                break
        return blob, blob.sha().hexdigest() if blob is not None else blob

    def get_conf(self):
        '''
        Returns a dulwich.config.ConfigFile object for the specified repo
        '''
        return dulwich.config.ConfigFile().from_path(
            os.path.join(self.repo.controldir(), 'config')
        )

    def get_remote_url(self, repo):
        '''
        Returns the remote url for the specified repo
        '''
        return self.get_conf().get(('remote', 'origin'), 'url')

    def get_tree(self, tgt_env):
        '''
        Return a dulwich.objects.Tree object if the branch/tag/SHA is found,
        otherwise None
        '''
        if tgt_env == 'base':
            tgt_ref = self.base
        else:
            tgt_ref = tgt_env
        refs = self.repo.get_refs()
        # Sorting ensures we check heads (branches) before tags
        for ref in sorted(self.get_env_refs(refs)):
            # ref will be something like 'refs/remotes/origin/master'
            try:
                rtype, rspec = re.split('^refs/(remotes/origin|tags)/',
                                        ref,
                                        1)[-2:]
            except ValueError:
                # No match was fount for the split regex, we don't care about
                # this ref. We shouldn't see any of these as the refs are being
                # filtered through self.get_env_refs(), but just in case, this
                # will avoid a traceback.
                continue
            if rspec == tgt_ref and self.env_is_exposed(tgt_env):
                if rtype == 'remotes/origin':
                    commit = self.repo.get_object(refs[ref])
                elif rtype == 'tags':
                    tag = self.repo.get_object(refs[ref])
                    if isinstance(tag, dulwich.objects.Tag):
                        # Tag.get_object() returns a 2-tuple, the 2nd element
                        # of which is the commit SHA to which the tag refers
                        commit = self.repo.get_object(tag.object[1])
                    elif isinstance(tag, dulwich.objects.Commit):
                        commit = tag
                    else:
                        log.error(
                            'Unhandled object type \'{0}\' in '
                            'Dulwich get_tree. This is a bug, please '
                            'report it.'.format(tag.type_name)
                        )
                return self.repo.get_object(commit.tree)

        # Branch or tag not matched, check if 'tgt_env' is a commit. This is more
        # difficult with Dulwich because of its inability to deal with shortened
        # SHA-1 hashes.
        if not self.env_is_exposed(tgt_env):
            return None
        try:
            int(tgt_ref, 16)
        except ValueError:
            # Not hexidecimal, likely just a non-matching environment
            return None

        try:
            if len(tgt_ref) == 40:
                sha_obj = self.repo.get_object(tgt_ref)
                if isinstance(sha_obj, dulwich.objects.Commit):
                    sha_commit = sha_obj
            else:
                matches = set([
                    x for x in (
                        self.repo.get_object(y)
                        for y in self.repo.object_store
                        if y.startswith(tgt_ref)
                    )
                    if isinstance(x, dulwich.objects.Commit)
                ])
                if len(matches) > 1:
                    log.warning('Ambiguous commit ID \'{0}\''.format(tgt_ref))
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
            return self.repo.get_object(sha_commit.tree)
        except NameError:
            # No matching sha_commit object was created. Unable to find SHA.
            pass
        return None

    def init_remote(self):
        '''
        Initialize/attach to a remote using dulwich. Return a boolean which
        will let the calling function know whether or not a new repo was
        initialized by this function.
        '''
        if self.url.startswith('ssh://'):
            # Dulwich will throw an error if 'ssh://' is used, so make the URL
            # use git+ssh:// as dulwich expects
            self.url = 'git+' + self.url
        new = False
        if not os.listdir(self.cachedir):
            # Repo cachedir is empty, initialize a new repo there
            self.repo = dulwich.repo.Repo.init(self.cachedir)
            new = True
        else:
            # Repo cachedir exists, try to attach
            try:
                self.repo = dulwich.repo.Repo(self.cachedir)
            except dulwich.repo.NotGitRepository:
                log.error(_INVALID_REPO.format(self.cachedir, self.url, self.role))
                return new

        self.gitdir = os.path.join(self.repo.path, '.git')

        # Read in config file and look for the remote
        try:
            conf = self.get_conf()
            conf.get(('remote', 'origin'), 'url')
        except KeyError:
            try:
                conf.set('http', 'sslVerify', self.ssl_verify)
                # Add remote manually, there is no function/object to do this
                conf.set(
                    'remote "origin"',
                    'fetch',
                    '+refs/heads/*:refs/remotes/origin/*'
                )
                conf.set('remote "origin"', 'url', self.url)
                conf.set('remote "origin"', 'pushurl', self.url)
                conf.write_to_path()
            except os.error:
                pass
            else:
                new = True
        except os.error:
            pass
        return new

    def walk_tree(self, tree, path):
        '''
        Dulwich does not provide a means of directly accessing subdirectories.
        This function will walk down to the directory specified by 'path', and
        return a Tree object at that path. If path is an empty string, the
        original tree will be returned, and if there are any issues encountered
        walking the tree, None will be returned.
        '''
        if not path:
            return tree
        # Walk down the tree to get to the file
        for parent in path.split(os.path.sep):
            try:
                tree = self.repo.get_object(tree[parent][1])
            except (KeyError, TypeError):
                # Directory not found, or tree passed into function is not a Tree
                # object. Either way, desired path does not exist.
                return None
        return tree

    def write_file(self, blob, dest):
        '''
        Using the blob object, write the file to the destination path
        '''
        with salt.utils.fopen(dest, 'w+') as fp_:
            fp_.write(blob.as_raw_string())


class GitBase(object):
    '''
    Base class for gitfs/git_pillar
    '''
    def __init__(self, opts, valid_providers=VALID_PROVIDERS, cache_root=None):
        self.opts = opts
        self.valid_providers = valid_providers
        self.get_provider()
        if cache_root is not None:
            self.cache_root = cache_root
        else:
            self.cache_root = os.path.join(self.opts['cachedir'], self.role)
        self.env_cache = os.path.join(self.cache_root, 'envs.p')
        self.hash_cachedir = os.path.join(
            self.cache_root, 'hash')
        self.file_list_cachedir = os.path.join(
            self.opts['cachedir'], 'file_lists', self.role)

    def init_remotes(self, remotes, per_remote_overrides):
        '''
        Initialize remotes
        '''
        # The global versions of the auth params (gitfs_user,
        # gitfs_password, etc.) default to empty strings. If any of them
        # are defined and the provider is not one that supports auth, then
        # error out and do not proceed.
        override_params = copy.deepcopy(per_remote_overrides)
        global_auth_params = [
            '{0}_{1}'.format(self.role, x) for x in AUTH_PARAMS
            if self.opts['{0}_{1}'.format(self.role, x)]
        ]
        if self.provider in AUTH_PROVIDERS:
            override_params += AUTH_PARAMS
        elif global_auth_params:
            msg = (
                '{0} authentication was configured, but the \'{1}\' '
                '{0}_provider does not support authentication. The '
                'providers for which authentication is supported in {0} '
                'are: {2}.'.format(
                    self.role, self.provider, ', '.join(AUTH_PROVIDERS)
                )
            )
            if self.role == 'gitfs':
                msg += (
                    ' See the GitFS Walkthrough in the Salt documentation '
                    'for further information.'
                )
            log.critical(msg)
            failhard(self.role)

        per_remote_defaults = {}
        for param in override_params:
            key = '{0}_{1}'.format(self.role, param)
            if key not in self.opts:
                log.critical(
                    'Key \'{0}\' not present in global configuration. This is '
                    'a bug, please report it.'.format(key)
                )
                failhard(self.role)
            per_remote_defaults[param] = six.text_type(self.opts[key])

        self.remotes = []
        for remote in remotes:
            repo_obj = self.provider_class(
                self.opts,
                remote,
                per_remote_defaults,
                override_params,
                self.cache_root,
                self.role
            )
            if hasattr(repo_obj, 'repo'):
                # Strip trailing slashes from the gitfs root as these cause
                # path searches to fail.
                repo_obj.root = repo_obj.root.rstrip(os.path.sep)
                # Sanity check and assign the credential parameter
                repo_obj.verify_auth()
                if self.opts['__role'] == 'minion' and repo_obj.new:
                    # Perform initial fetch
                    repo_obj.fetch()
                self.remotes.append(repo_obj)

        # Don't allow collisions in cachedir naming
        cachedir_map = {}
        for repo in self.remotes:
            cachedir_map.setdefault(repo.cachedir, []).append(repo.id)
        collisions = [x for x in cachedir_map if len(cachedir_map[x]) > 1]
        if collisions:
            for dirname in collisions:
                log.critical(
                    'The following {0} remotes have conflicting cachedirs: '
                    '{1}. Resolve this using a per-remote parameter called '
                    '\'name\'.'.format(
                        self.role,
                        ', '.join(cachedir_map[dirname])
                    )
                )
                failhard(self.role)

        if any(x.new for x in self.remotes):
            self.write_remote_map()

    def clear_old_remotes(self):
        '''
        Remove cache directories for remotes no longer configured
        '''
        try:
            cachedir_ls = os.listdir(self.cache_root)
        except OSError:
            cachedir_ls = []
        # Remove actively-used remotes from list
        for repo in self.remotes:
            try:
                cachedir_ls.remove(repo.cachedir_basename)
            except ValueError:
                pass
        to_remove = []
        for item in cachedir_ls:
            if item in ('hash', 'refs'):
                continue
            path = os.path.join(self.cache_root, item)
            if os.path.isdir(path):
                to_remove.append(path)
        failed = []
        if to_remove:
            for rdir in to_remove:
                try:
                    shutil.rmtree(rdir)
                except OSError as exc:
                    log.error(
                        'Unable to remove old {0} remote cachedir {1}: {2}'
                        .format(self.role, rdir, exc)
                    )
                    failed.append(rdir)
                else:
                    log.debug(
                        '{0} removed old cachedir {1}'.format(self.role, rdir)
                    )
        for fdir in failed:
            to_remove.remove(fdir)
        ret = bool(to_remove)
        if ret:
            self.write_remote_map()
        return ret

    def clear_cache(self):
        '''
        Completely clear cache
        '''
        errors = []
        for rdir in (self.cache_root, self.file_list_cachedir):
            if os.path.exists(rdir):
                try:
                    shutil.rmtree(rdir)
                except OSError as exc:
                    errors.append(
                        'Unable to delete {0}: {1}'.format(rdir, exc)
                    )
        return errors

    def clear_lock(self, remote=None, lock_type='update'):
        '''
        Clear update.lk for all remotes
        '''
        cleared = []
        errors = []
        for repo in self.remotes:
            if remote:
                # Specific remote URL/pattern was passed, ensure that the URL
                # matches or else skip this one
                try:
                    if not fnmatch.fnmatch(repo.url, remote):
                        continue
                except TypeError:
                    # remote was non-string, try again
                    if not fnmatch.fnmatch(repo.url, six.text_type(remote)):
                        continue
            success, failed = repo.clear_lock(lock_type=lock_type)
            cleared.extend(success)
            errors.extend(failed)
        return cleared, errors

    def fetch_remotes(self):
        '''
        Fetch all remotes and return a boolean to let the calling function know
        whether or not any remotes were updated in the process of fetching
        '''
        changed = False
        for repo in self.remotes:
            try:
                if repo.fetch():
                    # We can't just use the return value from repo.fetch()
                    # because the data could still have changed if old remotes
                    # were cleared above. Additionally, we're running this in a
                    # loop and later remotes without changes would override
                    # this value and make it incorrect.
                    changed = True
            except Exception as exc:
                log.error(
                    'Exception \'{0}\' caught while fetching {1} remote '
                    '\'{2}\''.format(exc, self.role, repo.id),
                    exc_info_on_loglevel=logging.DEBUG
                )
        return changed

    def lock(self, remote=None):
        '''
        Place an update.lk
        '''
        locked = []
        errors = []
        for repo in self.remotes:
            if remote:
                # Specific remote URL/pattern was passed, ensure that the URL
                # matches or else skip this one
                try:
                    if not fnmatch.fnmatch(repo.url, remote):
                        continue
                except TypeError:
                    # remote was non-string, try again
                    if not fnmatch.fnmatch(repo.url, six.text_type(remote)):
                        continue
            success, failed = repo.lock()
            locked.extend(success)
            errors.extend(failed)
        return locked, errors

    def update(self):
        '''
        Execute a git fetch on all of the repos and perform maintenance on the
        fileserver cache.
        '''
        # data for the fileserver event
        data = {'changed': False,
                'backend': 'gitfs'}

        data['changed'] = self.clear_old_remotes()
        if self.fetch_remotes():
            data['changed'] = True

        if data['changed'] is True or not os.path.isfile(self.env_cache):
            env_cachedir = os.path.dirname(self.env_cache)
            if not os.path.exists(env_cachedir):
                os.makedirs(env_cachedir)
            new_envs = self.envs(ignore_cache=True)
            serial = salt.payload.Serial(self.opts)
            with salt.utils.fopen(self.env_cache, 'w+') as fp_:
                fp_.write(serial.dumps(new_envs))
                log.trace('Wrote env cache data to {0}'.format(self.env_cache))

        # if there is a change, fire an event
        if self.opts.get('fileserver_events', False):
            event = salt.utils.event.get_event(
                    'master',
                    self.opts['sock_dir'],
                    self.opts['transport'],
                    opts=self.opts,
                    listen=False)
            event.fire_event(
                data,
                tagify(['gitfs', 'update'], prefix='fileserver')
            )
        try:
            salt.fileserver.reap_fileserver_cache_dir(
                self.hash_cachedir,
                self.find_file
            )
        except (OSError, IOError):
            # Hash file won't exist if no files have yet been served up
            pass

    def get_provider(self):
        '''
        Determine which provider to use
        '''
        if 'verified_{0}_provider'.format(self.role) in self.opts:
            self.provider = self.opts['verified_{0}_provider'.format(self.role)]
        else:
            desired_provider = self.opts.get('{0}_provider'.format(self.role))
            if not desired_provider:
                if self.verify_pygit2(quiet=True):
                    self.provider = 'pygit2'
                elif self.verify_gitpython(quiet=True):
                    self.provider = 'gitpython'
                elif self.verify_dulwich(quiet=True):
                    self.provider = 'dulwich'
            else:
                # Ensure non-lowercase providers work
                try:
                    desired_provider = desired_provider.lower()
                except AttributeError:
                    # Should only happen if someone does something silly like
                    # set the provider to a numeric value.
                    desired_provider = str(desired_provider).lower()
                if desired_provider not in self.valid_providers:
                    log.critical(
                        'Invalid {0}_provider \'{1}\'. Valid choices are: {2}'
                        .format(self.role,
                                desired_provider,
                                ', '.join(self.valid_providers))
                    )
                    failhard(self.role)
                elif desired_provider == 'pygit2' and self.verify_pygit2():
                    self.provider = 'pygit2'
                elif desired_provider == 'gitpython' and self.verify_gitpython():
                    self.provider = 'gitpython'
                elif desired_provider == 'dulwich' and self.verify_dulwich():
                    self.provider = 'dulwich'
        if not hasattr(self, 'provider'):
            log.critical(
                'No suitable {0} provider module is installed.'
                .format(self.role)
            )
            failhard(self.role)
        if self.provider == 'pygit2':
            self.provider_class = Pygit2
        elif self.provider == 'gitpython':
            self.provider_class = GitPython
        elif self.provider == 'dulwich':
            self.provider_class = Dulwich

    def verify_gitpython(self, quiet=False):
        '''
        Check if GitPython is available and at a compatible version (>= 0.3.0)
        '''
        def _recommend():
            if HAS_PYGIT2 and 'pygit2' in self.valid_providers:
                log.error(_RECOMMEND_PYGIT2.format(self.role))
            if HAS_DULWICH and 'dulwich' in self.valid_providers:
                log.error(_RECOMMEND_DULWICH.format(self.role))

        if not HAS_GITPYTHON:
            if not quiet:
                log.error(
                    '%s is configured but could not be loaded, is GitPython '
                    'installed?', self.role
                )
                _recommend()
            return False
        elif 'gitpython' not in self.valid_providers:
            return False

        # pylint: disable=no-member
        gitver = distutils.version.LooseVersion(git.__version__)
        minver = distutils.version.LooseVersion(GITPYTHON_MINVER)
        # pylint: enable=no-member
        errors = []
        if gitver < minver:
            errors.append(
                '{0} is configured, but the GitPython version is earlier than '
                '{1}. Version {2} detected.'.format(
                    self.role,
                    GITPYTHON_MINVER,
                    git.__version__
                )
            )
        if not salt.utils.which('git'):
            errors.append(
                'The git command line utility is required when using the '
                '\'gitpython\' {0}_provider.'.format(self.role)
            )

        if errors:
            for error in errors:
                log.error(error)
            if not quiet:
                _recommend()
            return False

        self.opts['verified_{0}_provider'.format(self.role)] = 'gitpython'
        log.debug('gitpython {0}_provider enabled'.format(self.role))
        return True

    def verify_pygit2(self, quiet=False):
        '''
        Check if pygit2/libgit2 are available and at a compatible version.
        Pygit2 must be at least 0.20.3 and libgit2 must be at least 0.20.0.
        '''
        def _recommend():
            if HAS_GITPYTHON and 'gitpython' in self.valid_providers:
                log.error(_RECOMMEND_GITPYTHON.format(self.role))
            if HAS_DULWICH and 'dulwich' in self.valid_providers:
                log.error(_RECOMMEND_DULWICH.format(self.role))

        if not HAS_PYGIT2:
            if not quiet:
                log.error(
                    '%s is configured but could not be loaded, are pygit2 '
                    'and libgit2 installed?', self.role
                )
                _recommend()
            return False
        elif 'pygit2' not in self.valid_providers:
            return False

        # pylint: disable=no-member
        pygit2ver = distutils.version.LooseVersion(pygit2.__version__)
        pygit2_minver = distutils.version.LooseVersion(PYGIT2_MINVER)

        libgit2ver = distutils.version.LooseVersion(pygit2.LIBGIT2_VERSION)
        libgit2_minver = distutils.version.LooseVersion(LIBGIT2_MINVER)
        # pylint: enable=no-member

        errors = []
        if pygit2ver < pygit2_minver:
            errors.append(
                '{0} is configured, but the pygit2 version is earlier than '
                '{1}. Version {2} detected.'.format(
                    self.role,
                    PYGIT2_MINVER,
                    pygit2.__version__
                )
            )
        if libgit2ver < libgit2_minver:
            errors.append(
                '{0} is configured, but the libgit2 version is earlier than '
                '{1}. Version {2} detected.'.format(
                    self.role,
                    LIBGIT2_MINVER,
                    pygit2.LIBGIT2_VERSION
                )
            )
        if not salt.utils.which('git'):
            errors.append(
                'The git command line utility is required when using the '
                '\'pygit2\' {0}_provider.'.format(self.role)
            )

        if errors:
            for error in errors:
                log.error(error)
            if not quiet:
                _recommend()
            return False

        self.opts['verified_{0}_provider'.format(self.role)] = 'pygit2'
        log.debug('pygit2 {0}_provider enabled'.format(self.role))
        return True

    def verify_dulwich(self, quiet=False):
        '''
        Check if dulwich is available.
        '''
        def _recommend():
            if HAS_GITPYTHON and 'gitpython' in self.valid_providers:
                log.error(_RECOMMEND_GITPYTHON.format(self.role))
            if HAS_PYGIT2 and 'pygit2' in self.valid_providers:
                log.error(_RECOMMEND_PYGIT2.format(self.role))

        if not HAS_DULWICH:
            if not quiet:
                log.error(
                    '%s is configured but could not be loaded. Is Dulwich '
                    'installed?', self.role
                )
                _recommend()
            return False
        elif 'dulwich' not in self.valid_providers:
            return False

        errors = []

        if dulwich.__version__ < DULWICH_MINVER:
            errors.append(
                '{0} is configured, but the installed version of Dulwich is '
                'earlier than {1}. Version {2} detected.'.format(
                    self.role,
                    DULWICH_MINVER,
                    dulwich.__version__
                )
            )

        if errors:
            for error in errors:
                log.error(error)
            if not quiet:
                _recommend()
            return False

        self.opts['verified_{0}_provider'.format(self.role)] = 'dulwich'
        log.debug('dulwich {0}_provider enabled'.format(self.role))
        return True

    def write_remote_map(self):
        '''
        Write the remote_map.txt
        '''
        remote_map = os.path.join(self.cache_root, 'remote_map.txt')
        try:
            with salt.utils.fopen(remote_map, 'w+') as fp_:
                timestamp = \
                    datetime.now().strftime('%d %b %Y %H:%M:%S.%f')
                fp_.write(
                    '# {0}_remote map as of {1}\n'.format(
                        self.role,
                        timestamp
                    )
                )
                for repo in self.remotes:
                    fp_.write(
                        '{0} = {1}\n'.format(
                            repo.cachedir_basename,
                            repo.id
                        )
                    )
        except OSError:
            pass
        else:
            log.info(
                'Wrote new {0} remote map to {1}'.format(
                    self.role,
                    remote_map
                )
            )

    def do_checkout(self, repo):
        '''
        Common code for git_pillar/winrepo to handle locking and checking out
        of a repo.
        '''
        time_start = time.time()
        while time.time() - time_start <= 5:
            try:
                return repo.checkout()
            except GitLockError as exc:
                if exc.errno == errno.EEXIST:
                    time.sleep(0.1)
                    continue
                else:
                    log.error(
                        'Error %d encountered while obtaining checkout '
                        'lock for %s remote \'%s\': %s',
                        exc.errno,
                        repo.role,
                        repo.id,
                        exc
                    )
                    break
        else:
            log.error(
                'Timed out waiting for checkout lock to be released for '
                '%s remote \'%s\'. If this error persists, run \'salt-run '
                'cache.clear_git_lock %s type=checkout\' to clear it.',
                self.role, repo.id, self.role
            )
        return None


class GitFS(GitBase):
    '''
    Functionality specific to the git fileserver backend
    '''
    def __init__(self, opts):
        self.role = 'gitfs'
        GitBase.__init__(self, opts)

    def dir_list(self, load):
        '''
        Return a list of all directories on the master
        '''
        return self._file_lists(load, 'dirs')

    def envs(self, ignore_cache=False):
        '''
        Return a list of refs that can be used as environments
        '''
        if not ignore_cache:
            cache_match = salt.fileserver.check_env_cache(
                self.opts,
                self.env_cache
            )
            if cache_match is not None:
                return cache_match
        ret = set()
        for repo in self.remotes:
            ret.update(repo.envs())
        return sorted(ret)

    def find_file(self, path, tgt_env='base', **kwargs):  # pylint: disable=W0613
        '''
        Find the first file to match the path and ref, read the file out of git
        and send the path to the newly cached file
        '''
        fnd = {'path': '',
               'rel': ''}
        if os.path.isabs(path) or tgt_env not in self.envs():
            return fnd

        dest = os.path.join(self.cache_root, 'refs', tgt_env, path)
        hashes_glob = os.path.join(self.hash_cachedir,
                                   tgt_env,
                                   '{0}.hash.*'.format(path))
        blobshadest = os.path.join(self.hash_cachedir,
                                   tgt_env,
                                   '{0}.hash.blob_sha1'.format(path))
        lk_fn = os.path.join(self.hash_cachedir,
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

        for repo in self.remotes:
            if repo.mountpoint \
                    and not path.startswith(repo.mountpoint + os.path.sep):
                continue
            repo_path = path[len(repo.mountpoint):].lstrip(os.path.sep)
            if repo.root:
                repo_path = os.path.join(repo.root, repo_path)

            blob, blob_hexsha = repo.find_file(repo_path, tgt_env)
            if blob is None:
                continue

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
            # Write contents of file to their destination in the FS cache
            repo.write_file(blob, dest)
            with salt.utils.fopen(blobshadest, 'w+') as fp_:
                fp_.write(blob_hexsha)
            try:
                os.remove(lk_fn)
            except OSError:
                pass
            fnd['rel'] = path
            fnd['path'] = dest
            return fnd

        # No matching file was found in tgt_env. Return a dict with empty paths
        # so the calling function knows the file could not be found.
        return fnd

    def serve_file(self, load, fnd):
        '''
        Return a chunk from a file based on the data received
        '''
        if 'env' in load:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
                )
            load.pop('env')

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
            data = fp_.read(self.opts['file_buffer_size'])
            if gzip and data:
                data = salt.utils.gzip_util.compress(data, gzip)
                ret['gzip'] = gzip
            ret['data'] = data
        return ret

    def file_hash(self, load, fnd):
        '''
        Return a file hash, the hash type is set in the master config file
        '''
        if 'env' in load:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
                )
            load.pop('env')

        if not all(x in load for x in ('path', 'saltenv')):
            return ''
        ret = {'hash_type': self.opts['hash_type']}
        relpath = fnd['rel']
        path = fnd['path']
        hashdest = os.path.join(self.hash_cachedir,
                                load['saltenv'],
                                '{0}.hash.{1}'.format(relpath,
                                                      self.opts['hash_type']))
        if not os.path.isfile(hashdest):
            if not os.path.exists(os.path.dirname(hashdest)):
                os.makedirs(os.path.dirname(hashdest))
            ret['hsum'] = salt.utils.get_hash(path, self.opts['hash_type'])
            with salt.utils.fopen(hashdest, 'w+') as fp_:
                fp_.write(ret['hsum'])
            return ret
        else:
            with salt.utils.fopen(hashdest, 'rb') as fp_:
                ret['hsum'] = fp_.read()
            return ret

    def _file_lists(self, load, form):
        '''
        Return a dict containing the file lists for files and dirs
        '''
        if 'env' in load:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
                )
            load.pop('env')

        if not os.path.isdir(self.file_list_cachedir):
            try:
                os.makedirs(self.file_list_cachedir)
            except os.error:
                log.error(
                    'Unable to make cachedir {0}'.format(
                        self.file_list_cachedir
                    )
                )
                return []
        list_cache = os.path.join(
            self.file_list_cachedir,
            '{0}.p'.format(load['saltenv'].replace(os.path.sep, '_|-'))
        )
        w_lock = os.path.join(
            self.file_list_cachedir,
            '.{0}.w'.format(load['saltenv'].replace(os.path.sep, '_|-'))
        )
        cache_match, refresh_cache, save_cache = \
            salt.fileserver.check_file_list_cache(
                self.opts, form, list_cache, w_lock
            )
        if cache_match is not None:
            return cache_match
        if refresh_cache:
            ret = {'files': set(), 'symlinks': {}, 'dirs': set()}
            if load['saltenv'] in self.envs():
                for repo in self.remotes:
                    repo_files, repo_symlinks = repo.file_list(load['saltenv'])
                    ret['files'].update(repo_files)
                    ret['symlinks'].update(repo_symlinks)
                    ret['dirs'].update(repo.dir_list(load['saltenv']))
            ret['files'] = sorted(ret['files'])
            ret['dirs'] = sorted(ret['dirs'])

            if save_cache:
                salt.fileserver.write_file_list_cache(
                    self.opts, ret, list_cache, w_lock
                )
            # NOTE: symlinks are organized in a dict instead of a list, however
            # the 'symlinks' key will be defined above so it will never get to
            # the default value in the call to ret.get() below.
            return ret.get(form, [])
        # Shouldn't get here, but if we do, this prevents a TypeError
        return {} if form == 'symlinks' else []

    def file_list(self, load):
        '''
        Return a list of all files on the file server in a specified
        environment
        '''
        return self._file_lists(load, 'files')

    def file_list_emptydirs(self, load):  # pylint: disable=W0613
        '''
        Return a list of all empty directories on the master
        '''
        # Cannot have empty dirs in git
        return []

    def symlink_list(self, load):
        '''
        Return a dict of all symlinks based on a given path in the repo
        '''
        if 'env' in load:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
                )
            load.pop('env')

        if load['saltenv'] not in self.envs():
            return {}
        if 'prefix' in load:
            prefix = load['prefix'].strip('/')
        else:
            prefix = ''
        symlinks = self._file_lists(load, 'symlinks')
        return dict([(key, val)
                     for key, val in six.iteritems(symlinks)
                     if key.startswith(prefix)])


class GitPillar(GitBase):
    '''
    Functionality specific to the git external pillar
    '''
    def __init__(self, opts):
        self.role = 'git_pillar'
        # Dulwich has no function to check out a branch/tag, so this will be
        # limited to GitPython and Pygit2 for the forseeable future.
        GitBase.__init__(self,
                         opts,
                         valid_providers=('gitpython', 'pygit2'))

    def checkout(self):
        '''
        Checkout the targeted branches/tags from the git_pillar remotes
        '''
        self.pillar_dirs = {}
        for repo in self.remotes:
            cachedir = self.do_checkout(repo)
            if cachedir is not None:
                # Figure out which environment this remote should be assigned
                if repo.env:
                    env = repo.env
                else:
                    base_branch = self.opts['{0}_base'.format(self.role)]
                    env = 'base' if repo.branch == base_branch else repo.branch
                self.pillar_dirs[cachedir] = env

    def update(self):
        '''
        Execute a git fetch on all of the repos. In this case, simply execute
        self.fetch_remotes() from the parent class.

        This function only exists to make the git_pillar update code in
        master.py (salt.master.Maintenance.handle_git_pillar) less complicated,
        once the legacy git_pillar code is purged we can remove this function
        and just run pillar.fetch_remotes() there.
        '''
        return self.fetch_remotes()


class WinRepo(GitBase):
    '''
    Functionality specific to the winrepo runner
    '''
    def __init__(self, opts, winrepo_dir):
        self.role = 'winrepo'
        # Dulwich has no function to check out a branch/tag, so this will be
        # limited to GitPython and Pygit2 for the forseeable future.
        GitBase.__init__(self,
                         opts,
                         valid_providers=('gitpython', 'pygit2'),
                         cache_root=winrepo_dir)

    def checkout(self):
        '''
        Checkout the targeted branches/tags from the winrepo remotes
        '''
        self.winrepo_dirs = {}
        for repo in self.remotes:
            cachedir = self.do_checkout(repo)
            if cachedir is not None:
                self.winrepo_dirs[repo.id] = cachedir
