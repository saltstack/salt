# -*- coding: utf-8 -*-
'''
Classes which provide the shared base for GitFS, git_pillar, and winrepo
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import contextlib
import errno
import fnmatch
import glob
import hashlib
import logging
import os
import shlex
import shutil
import stat
import subprocess
import time
import tornado.ioloop
import weakref
from datetime import datetime

# Import salt libs
import salt.utils.configparser
import salt.utils.data
import salt.utils.files
import salt.utils.gzip_util
import salt.utils.hashutils
import salt.utils.itertools
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.url
import salt.utils.user
import salt.utils.versions
import salt.fileserver
from salt.config import DEFAULT_MASTER_OPTS as _DEFAULT_MASTER_OPTS
from salt.utils.odict import OrderedDict
from salt.utils.process import os_is_running as pid_exists
from salt.exceptions import (
    FileserverConfigError,
    GitLockError,
    get_error_message
)
from salt.utils.event import tagify
from salt.utils.versions import LooseVersion as _LooseVersion

# Import third party libs
from salt.ext import six

VALID_REF_TYPES = _DEFAULT_MASTER_OPTS['gitfs_ref_types']

# Optional per-remote params that can only be used on a per-remote basis, and
# thus do not have defaults in salt/config.py.
PER_REMOTE_ONLY = ('name',)
# Params which are global only and cannot be overridden for a single remote.
GLOBAL_ONLY = ()

SYMLINK_RECURSE_DEPTH = 100

# Auth support (auth params can be global or per-remote, too)
AUTH_PROVIDERS = ('pygit2',)
AUTH_PARAMS = ('user', 'password', 'pubkey', 'privkey', 'passphrase',
               'insecure_auth')

# GitFS only: params which can be overridden for a single saltenv. Aside from
# 'ref', this must be a subset of the per-remote params passed to the
# constructor for the GitProvider subclasses.
PER_SALTENV_PARAMS = ('mountpoint', 'root', 'ref')

_RECOMMEND_GITPYTHON = (
    'GitPython is installed, you may wish to set %s_provider to '
    '\'gitpython\' to use GitPython for %s support.'
)

_RECOMMEND_PYGIT2 = (
    'pygit2 is installed, you may wish to set %s_provider to '
    '\'pygit2\' to use pygit2 for for %s support.'
)

_INVALID_REPO = (
    'Cache path %s (corresponding remote: %s) exists but is not a valid '
    'git repository. You will need to manually delete this directory on the '
    'master to continue to use this %s remote.'
)

log = logging.getLogger(__name__)

# pylint: disable=import-error
try:
    import git
    import gitdb
    GITPYTHON_VERSION = _LooseVersion(git.__version__)
except Exception:
    GITPYTHON_VERSION = None

try:
    # Squelch warning on cent7 due to them upgrading cffi
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        import pygit2
    PYGIT2_VERSION = _LooseVersion(pygit2.__version__)
    LIBGIT2_VERSION = _LooseVersion(pygit2.LIBGIT2_VERSION)

    # Work around upstream bug where bytestrings were being decoded using the
    # default encoding (which is usually ascii on Python 2). This was fixed
    # on 2 Feb 2018, so releases prior to 0.26.3 will need a workaround.
    if PYGIT2_VERSION <= _LooseVersion('0.26.3'):
        try:
            import pygit2.ffi
            import pygit2.remote
        except ImportError:
            # If we couldn't import these, then we're using an old enough
            # version where ffi isn't in use and this workaround would be
            # useless.
            pass
        else:
            def __maybe_string(ptr):
                if not ptr:
                    return None
                return pygit2.ffi.string(ptr).decode('utf-8')

            pygit2.remote.maybe_string = __maybe_string

    # Older pygit2 releases did not raise a specific exception class, this
    # try/except makes Salt's exception catching work on any supported release.
    try:
        GitError = pygit2.errors.GitError
    except AttributeError:
        GitError = Exception
except Exception as exc:
    # Exceptions other than ImportError can be raised in cases where there is a
    # problem with cffi (such as when python-cffi is upgraded and pygit2 tries
    # to rebuild itself against the newer cffi). Therefore, we simply will
    # catch a generic exception, and log the exception if it is anything other
    # than an ImportError.
    PYGIT2_VERSION = None
    LIBGIT2_VERSION = None
    if not isinstance(exc, ImportError):
        log.exception('Failed to import pygit2')

# pylint: enable=import-error

# Minimum versions for backend providers
GITPYTHON_MINVER = _LooseVersion('0.3')
PYGIT2_MINVER = _LooseVersion('0.20.3')
LIBGIT2_MINVER = _LooseVersion('0.20.0')


def enforce_types(key, val):
    '''
    Force params to be strings unless they should remain a different type
    '''
    non_string_params = {
        'ssl_verify': bool,
        'insecure_auth': bool,
        'disable_saltenv_mapping': bool,
        'env_whitelist': 'stringlist',
        'env_blacklist': 'stringlist',
        'saltenv_whitelist': 'stringlist',
        'saltenv_blacklist': 'stringlist',
        'refspecs': 'stringlist',
        'ref_types': 'stringlist',
        'update_interval': int,
    }

    def _find_global(key):
        for item in non_string_params:
            try:
                if key.endswith('_' + item):
                    ret = item
                    break
            except TypeError:
                if key.endswith('_' + six.text_type(item)):
                    ret = item
                    break
        else:
            ret = None
        return ret

    if key not in non_string_params:
        key = _find_global(key)
        if key is None:
            return six.text_type(val)

    expected = non_string_params[key]
    if expected == 'stringlist':
        if not isinstance(val, (six.string_types, list)):
            val = six.text_type(val)
        if isinstance(val, six.string_types):
            return [x.strip() for x in val.split(',')]
        return [six.text_type(x) for x in val]
    else:
        try:
            return expected(val)
        except Exception as exc:
            log.error(
                'Failed to enforce type for key=%s with val=%s, falling back '
                'to a string', key, val
            )
            return six.text_type(val)


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
    invoking the parent class' __init__.
    '''
    def __init__(self, opts, remote, per_remote_defaults, per_remote_only,
                 override_params, cache_root, role='gitfs'):
        self.opts = opts
        self.role = role
        self.global_saltenv = salt.utils.data.repack_dictlist(
            self.opts.get('{0}_saltenv'.format(self.role), []),
            strict=True,
            recurse=True,
            key_cb=six.text_type,
            val_cb=lambda x, y: six.text_type(y))
        self.conf = copy.deepcopy(per_remote_defaults)

        # Remove the 'salt://' from the beginning of any globally-defined
        # per-saltenv mountpoints
        for saltenv, saltenv_conf in six.iteritems(self.global_saltenv):
            if 'mountpoint' in saltenv_conf:
                self.global_saltenv[saltenv]['mountpoint'] = \
                    salt.utils.url.strip_proto(
                        self.global_saltenv[saltenv]['mountpoint']
                    )

        per_remote_collisions = [x for x in override_params
                                 if x in per_remote_only]
        if per_remote_collisions:
            log.critical(
                'The following parameter names are restricted to per-remote '
                'use only: %s. This is a bug, please report it.',
                ', '.join(per_remote_collisions)
            )

        try:
            valid_per_remote_params = override_params + per_remote_only
        except TypeError:
            valid_per_remote_params = \
                list(override_params) + list(per_remote_only)

        if isinstance(remote, dict):
            self.id = next(iter(remote))
            self.get_url()

            per_remote_conf = salt.utils.data.repack_dictlist(
                remote[self.id],
                strict=True,
                recurse=True,
                key_cb=six.text_type,
                val_cb=enforce_types)

            if not per_remote_conf:
                log.critical(
                    'Invalid per-remote configuration for %s remote \'%s\'. '
                    'If no per-remote parameters are being specified, there '
                    'may be a trailing colon after the URL, which should be '
                    'removed. Check the master configuration file.',
                    self.role, self.id
                )
                failhard(self.role)

            per_remote_errors = False
            for param in (x for x in per_remote_conf
                          if x not in valid_per_remote_params):
                per_remote_errors = True
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
                        'remote \'{2}\'. Valid parameters are: {3}.'.format(
                            self.role,
                            param,
                            self.id,
                            ', '.join(valid_per_remote_params)
                        )
                    )
                    if self.role == 'gitfs':
                        msg += (
                            ' See the GitFS Walkthrough in the Salt '
                            'documentation for further information.'
                        )
                    log.critical(msg)

            if per_remote_errors:
                failhard(self.role)

            self.conf.update(per_remote_conf)
        else:
            self.id = remote
            self.get_url()

        # Winrepo doesn't support the 'root' option, but it still must be part
        # of the GitProvider object because other code depends on it. Add it as
        # an empty string.
        if 'root' not in self.conf:
            self.conf['root'] = ''

        if self.role == 'winrepo' and 'name' not in self.conf:
            # Ensure that winrepo has the 'name' parameter set if it wasn't
            # provided. Default to the last part of the URL, minus the .git if
            # it is present.
            self.conf['name'] = self.url.rsplit('/', 1)[-1]
            # Remove trailing .git from name
            if self.conf['name'].lower().endswith('.git'):
                self.conf['name'] = self.conf['name'][:-4]

        if 'mountpoint' in self.conf:
            # Remove the 'salt://' from the beginning of the mountpoint, as
            # well as any additional leading/trailing slashes
            self.conf['mountpoint'] = \
                salt.utils.url.strip_proto(self.conf['mountpoint']).strip('/')
        else:
            # For providers which do not use a mountpoint, assume the
            # filesystem is mounted at the root of the fileserver.
            self.conf['mountpoint'] = ''

        if 'saltenv' not in self.conf:
            self.conf['saltenv'] = {}
        else:
            for saltenv, saltenv_conf in six.iteritems(self.conf['saltenv']):
                if 'mountpoint' in saltenv_conf:
                    saltenv_ptr = self.conf['saltenv'][saltenv]
                    saltenv_ptr['mountpoint'] = \
                        salt.utils.url.strip_proto(saltenv_ptr['mountpoint'])

        for key, val in six.iteritems(self.conf):
            if key not in PER_SALTENV_PARAMS and not hasattr(self, key):
                setattr(self, key, val)

        for key in PER_SALTENV_PARAMS:
            if key != 'ref':
                setattr(self, '_' + key, self.conf[key])
            self.add_conf_overlay(key)

        if not hasattr(self, 'refspecs'):
            # This was not specified as a per-remote overrideable parameter
            # when instantiating an instance of a GitBase subclass. Make sure
            # that we set this attribute so we at least have a sane default and
            # are able to fetch.
            key = '{0}_refspecs'.format(self.role)
            try:
                default_refspecs = _DEFAULT_MASTER_OPTS[key]
            except KeyError:
                log.critical(
                    'The \'%s\' option has no default value in '
                    'salt/config/__init__.py.', key
                )
                failhard(self.role)

            setattr(self, 'refspecs', default_refspecs)
            log.debug(
                'The \'refspecs\' option was not explicitly defined as a '
                'configurable parameter. Falling back to %s for %s remote '
                '\'%s\'.', default_refspecs, self.role, self.id
            )

        for item in ('env_whitelist', 'env_blacklist'):
            val = getattr(self, item, None)
            if val:
                salt.utils.versions.warn_until(
                    'Neon',
                    'The gitfs_{0} config option (and {0} per-remote config '
                    'option) have been renamed to gitfs_salt{0} (and '
                    'salt{0}). Please update your configuration.'.format(item)
                )
                setattr(self, 'salt{0}'.format(item), val)

        # Discard the conf dictionary since we have set all of the config
        # params as attributes
        delattr(self, 'conf')

        # Normalize components of the ref_types configuration and check for
        # invalid configuration.
        if hasattr(self, 'ref_types'):
            self.ref_types = [x.lower() for x in self.ref_types]
            invalid_ref_types = [x for x in self.ref_types
                                 if x not in VALID_REF_TYPES]
            if invalid_ref_types:
                log.critical(
                    'The following ref_types for %s remote \'%s\' are '
                    'invalid: %s. The supported values are: %s',
                    self.role,
                    self.id,
                    ', '.join(invalid_ref_types),
                    ', '.join(VALID_REF_TYPES),
                )
                failhard(self.role)

        if not isinstance(self.url, six.string_types):
            log.critical(
                'Invalid %s remote \'%s\'. Remotes must be strings, you '
                'may need to enclose the URL in quotes', self.role, self.id
            )
            failhard(self.role)

        hash_type = getattr(hashlib, self.opts.get('hash_type', 'md5'))
        if six.PY3:
            # We loaded this data from yaml configuration files, so, its safe
            # to use UTF-8
            self.hash = hash_type(self.id.encode('utf-8')).hexdigest()
        else:
            self.hash = hash_type(self.id).hexdigest()
        self.cachedir_basename = getattr(self, 'name', self.hash)
        self.cachedir = salt.utils.path.join(cache_root, self.cachedir_basename)
        self.linkdir = salt.utils.path.join(cache_root,
                                            'links',
                                            self.cachedir_basename)

        if not os.path.isdir(self.cachedir):
            os.makedirs(self.cachedir)

        try:
            self.new = self.init_remote()
        except Exception as exc:
            msg = ('Exception caught while initializing {0} remote \'{1}\': '
                   '{2}'.format(self.role, self.id, exc))
            if isinstance(self, GitPython):
                msg += ' Perhaps git is not available.'
            log.critical(msg, exc_info=True)
            failhard(self.role)

    def _get_envs_from_ref_paths(self, refs):
        '''
        Return the names of remote refs (stripped of the remote name) and tags
        which are map to the branches and tags.
        '''
        def _check_ref(env_set, rname):
            '''
            Add the appropriate saltenv(s) to the set
            '''
            if rname in self.saltenv_revmap:
                env_set.update(self.saltenv_revmap[rname])
            else:
                if rname == self.base:
                    env_set.add('base')
                elif not self.disable_saltenv_mapping:
                    env_set.add(rname)

        use_branches = 'branch' in self.ref_types
        use_tags = 'tag' in self.ref_types

        ret = set()
        if salt.utils.stringutils.is_hex(self.base):
            # gitfs_base or per-saltenv 'base' may point to a commit ID, which
            # would not show up in the refs. Make sure we include it.
            ret.add('base')
        for ref in salt.utils.data.decode(refs):
            if ref.startswith('refs/'):
                ref = ref[5:]
            rtype, rname = ref.split('/', 1)
            if rtype == 'remotes' and use_branches:
                parted = rname.partition('/')
                rname = parted[2] if parted[2] else parted[0]
                _check_ref(ret, rname)
            elif rtype == 'tags' and use_tags:
                _check_ref(ret, rname)

        return ret

    def _get_lock_file(self, lock_type='update'):
        return salt.utils.path.join(self.gitdir, lock_type + '.lk')

    @classmethod
    def add_conf_overlay(cls, name):
        '''
        Programmatically determine config value based on the desired saltenv
        '''
        def _getconf(self, tgt_env='base'):
            strip_sep = lambda x: x.rstrip(os.sep) \
                if name in ('root', 'mountpoint') \
                else x
            if self.role != 'gitfs':
                return strip_sep(getattr(self, '_' + name))
            # Get saltenv-specific configuration
            saltenv_conf = self.saltenv.get(tgt_env, {})
            if name == 'ref':
                def _get_per_saltenv(tgt_env):
                    if name in saltenv_conf:
                        return saltenv_conf[name]
                    elif tgt_env in self.global_saltenv \
                            and name in self.global_saltenv[tgt_env]:
                        return self.global_saltenv[tgt_env][name]
                    else:
                        return None

                # Return the all_saltenvs branch/tag if it is configured
                per_saltenv_ref = _get_per_saltenv(tgt_env)
                try:
                    all_saltenvs_ref = self.all_saltenvs
                    if per_saltenv_ref and all_saltenvs_ref != per_saltenv_ref:
                        log.debug(
                            'The per-saltenv configuration has mapped the '
                            '\'%s\' branch/tag to saltenv \'%s\' for %s '
                            'remote \'%s\', but this remote has '
                            'all_saltenvs set to \'%s\'. The per-saltenv '
                            'mapping will be ignored in favor of \'%s\'.',
                            per_saltenv_ref, tgt_env, self.role, self.id,
                            all_saltenvs_ref, all_saltenvs_ref
                        )
                    return all_saltenvs_ref
                except AttributeError:
                    # all_saltenvs not configured for this remote
                    pass

                if tgt_env == 'base':
                    return self.base
                elif self.disable_saltenv_mapping:
                    if per_saltenv_ref is None:
                        log.debug(
                            'saltenv mapping is diabled for %s remote \'%s\' '
                            'and saltenv \'%s\' is not explicitly mapped',
                            self.role, self.id, tgt_env
                        )
                    return per_saltenv_ref
                else:
                    return per_saltenv_ref or tgt_env

            if name in saltenv_conf:
                return strip_sep(saltenv_conf[name])
            elif tgt_env in self.global_saltenv \
                    and name in self.global_saltenv[tgt_env]:
                return strip_sep(self.global_saltenv[tgt_env][name])
            else:
                return strip_sep(getattr(self, '_' + name))
        setattr(cls, name, _getconf)

    def check_root(self):
        '''
        Check if the relative root path exists in the checked-out copy of the
        remote. Return the full path to that relative root if it does exist,
        otherwise return None.
        '''
        # No need to pass an environment to self.root() here since per-saltenv
        # configuration is a gitfs-only feature and check_root() is not used
        # for gitfs.
        root_dir = salt.utils.path.join(self.cachedir, self.root()).rstrip(os.sep)
        if os.path.isdir(root_dir):
            return root_dir
        log.error(
            'Root path \'%s\' not present in %s remote \'%s\', '
            'skipping.', self.root(), self.role, self.id
        )
        return None

    def clean_stale_refs(self):
        '''
        Remove stale refs so that they are no longer seen as fileserver envs
        '''
        cleaned = []
        cmd_str = 'git remote prune origin'

        # Attempt to force all output to plain ascii english, which is what some parsing code
        # may expect.
        # According to stackoverflow (http://goo.gl/l74GC8), we are setting LANGUAGE as well
        # just to be sure.
        env = os.environ.copy()
        env[b"LANGUAGE"] = b"C"
        env[b"LC_ALL"] = b"C"

        cmd = subprocess.Popen(
            shlex.split(cmd_str),
            close_fds=not salt.utils.platform.is_windows(),
            cwd=os.path.dirname(self.gitdir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        output = cmd.communicate()[0]
        if six.PY3:
            output = output.decode(__salt_system_encoding__)
        if cmd.returncode != 0:
            log.warning(
                'Failed to prune stale branches for %s remote \'%s\'. '
                'Output from \'%s\' follows:\n%s',
                self.role, self.id, cmd_str, output
            )
        else:
            marker = ' * [pruned] '
            for line in salt.utils.itertools.split(output, '\n'):
                if line.startswith(marker):
                    cleaned.append(line[len(marker):].strip())
            if cleaned:
                log.debug(
                    '%s pruned the following stale refs: %s',
                    self.role, ', '.join(cleaned)
                )
        return cleaned

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

    def enforce_git_config(self):
        '''
        For the config options which need to be maintained in the git config,
        ensure that the git config file is configured as desired.
        '''
        git_config = os.path.join(self.gitdir, 'config')
        conf = salt.utils.configparser.GitConfigParser()
        if not conf.read(git_config):
            log.error('Failed to read from git config file %s', git_config)
        else:
            # We are currently enforcing the following git config items:
            # 1. Fetch URL
            # 2. refspecs used in fetch
            # 3. http.sslVerify
            conf_changed = False
            remote_section = 'remote "origin"'

            # 1. URL
            try:
                url = conf.get(remote_section, 'url')
            except salt.utils.configparser.NoSectionError:
                # First time we've init'ed this repo, we need to add the
                # section for the remote to the git config
                conf.add_section(remote_section)
                conf_changed = True
                url = None
            log.debug(
                'Current fetch URL for %s remote \'%s\': %s (desired: %s)',
                self.role, self.id, url, self.url
            )
            if url != self.url:
                conf.set(remote_section, 'url', self.url)
                log.debug(
                    'Fetch URL for %s remote \'%s\' set to %s',
                    self.role, self.id, self.url
                )
                conf_changed = True

            # 2. refspecs
            try:
                refspecs = sorted(
                    conf.get(remote_section, 'fetch', as_list=True))
            except salt.utils.configparser.NoOptionError:
                # No 'fetch' option present in the remote section. Should never
                # happen, but if it does for some reason, don't let it cause a
                # traceback.
                refspecs = []
            desired_refspecs = sorted(self.refspecs)
            log.debug(
                'Current refspecs for %s remote \'%s\': %s (desired: %s)',
                self.role, self.id, refspecs, desired_refspecs
            )
            if refspecs != desired_refspecs:
                conf.set_multivar(remote_section, 'fetch', self.refspecs)
                log.debug(
                    'Refspecs for %s remote \'%s\' set to %s',
                    self.role, self.id, desired_refspecs
                )
                conf_changed = True

            # 3. http.sslVerify
            try:
                ssl_verify = conf.get('http', 'sslVerify')
            except salt.utils.configparser.NoSectionError:
                conf.add_section('http')
                ssl_verify = None
            except salt.utils.configparser.NoOptionError:
                ssl_verify = None
            desired_ssl_verify = six.text_type(self.ssl_verify).lower()
            log.debug(
                'Current http.sslVerify for %s remote \'%s\': %s (desired: %s)',
                self.role, self.id, ssl_verify, desired_ssl_verify
            )
            if ssl_verify != desired_ssl_verify:
                conf.set('http', 'sslVerify', desired_ssl_verify)
                log.debug(
                    'http.sslVerify for %s remote \'%s\' set to %s',
                    self.role, self.id, desired_ssl_verify
                )
                conf_changed = True

            # Write changes, if necessary
            if conf_changed:
                with salt.utils.files.fopen(git_config, 'w') as fp_:
                    conf.write(fp_)
                    log.debug(
                        'Config updates for %s remote \'%s\' written to %s',
                        self.role, self.id, git_config
                    )

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
            with os.fdopen(fh_, 'wb'):
                # Write the lock file and close the filehandle
                os.write(fh_, salt.utils.stringutils.to_bytes(six.text_type(os.getpid())))
        except (OSError, IOError) as exc:
            if exc.errno == errno.EEXIST:
                with salt.utils.files.fopen(self._get_lock_file(lock_type), 'r') as fd_:
                    try:
                        pid = int(salt.utils.stringutils.to_unicode(fd_.readline()).rstrip())
                    except ValueError:
                        # Lock file is empty, set pid to 0 so it evaluates as
                        # False.
                        pid = 0
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
                        raise exc
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
                log.error(msg, exc_info=True)
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
    def gen_lock(self, lock_type='update', timeout=0, poll_interval=0.5):
        '''
        Set and automatically clear a lock
        '''
        if not isinstance(lock_type, six.string_types):
            raise GitLockError(
                errno.EINVAL,
                'Invalid lock_type \'{0}\''.format(lock_type)
            )

        # Make sure that we have a positive integer timeout, otherwise just set
        # it to zero.
        try:
            timeout = int(timeout)
        except ValueError:
            timeout = 0
        else:
            if timeout < 0:
                timeout = 0

        if not isinstance(poll_interval, (six.integer_types, float)) \
                or poll_interval < 0:
            poll_interval = 0.5

        if poll_interval > timeout:
            poll_interval = timeout

        lock_set = False
        try:
            time_start = time.time()
            while True:
                try:
                    self._lock(lock_type=lock_type, failhard=True)
                    lock_set = True
                    yield
                    # Break out of his loop once we've yielded the lock, to
                    # avoid continued attempts to iterate and establish lock
                    break
                except (OSError, IOError, GitLockError) as exc:
                    if not timeout or time.time() - time_start > timeout:
                        raise GitLockError(exc.errno, exc.strerror)
                    else:
                        log.debug(
                            'A %s lock is already present for %s remote '
                            '\'%s\', sleeping %f second(s)',
                            lock_type, self.role, self.id, poll_interval
                        )
                        time.sleep(poll_interval)
                        continue
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
        return salt.utils.stringutils.check_whitelist_blacklist(
            tgt_env,
            whitelist=self.saltenv_whitelist,
            blacklist=self.saltenv_blacklist,
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

    def get_checkout_target(self):
        '''
        Resolve dynamically-set branch
        '''
        if self.role == 'git_pillar' and self.branch == '__env__':
            try:
                return self.all_saltenvs
            except AttributeError:
                # all_saltenvs not configured for this remote
                pass
            target = self.opts.get('pillarenv') \
                or self.opts.get('saltenv') \
                or 'base'
            return self.base \
                if target == 'base' \
                else six.text_type(target)
        return self.branch

    def get_tree(self, tgt_env):
        '''
        Return a tree object for the specified environment
        '''
        if not self.env_is_exposed(tgt_env):
            return None

        tgt_ref = self.ref(tgt_env)
        if tgt_ref is None:
            return None

        for ref_type in self.ref_types:
            try:
                func_name = 'get_tree_from_{0}'.format(ref_type)
                func = getattr(self, func_name)
            except AttributeError:
                log.error(
                    '%s class is missing function \'%s\'',
                    self.__class__.__name__, func_name
                )
            else:
                candidate = func(tgt_ref)
                if candidate is not None:
                    return candidate

        # No matches found
        return None

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
                self.branch = self.conf['branch']
                self.url = self.id
        else:
            self.url = self.id

    @property
    def linkdir_walk(self):
        '''
        Return the expected result of an os.walk on the linkdir, based on the
        mountpoint value.
        '''
        try:
            # Use cached linkdir_walk if we've already run this
            return self._linkdir_walk
        except AttributeError:
            self._linkdir_walk = []
            try:
                parts = self._mountpoint.split('/')
            except AttributeError:
                log.error(
                    '%s class is missing a \'_mountpoint\' attribute',
                    self.__class__.__name__
                )
            else:
                for idx, item in enumerate(parts[:-1]):
                    try:
                        dirs = [parts[idx + 1]]
                    except IndexError:
                        dirs = []
                    self._linkdir_walk.append((
                        salt.utils.path.join(self.linkdir, *parts[:idx + 1]),
                        dirs,
                        []
                    ))
                try:
                    # The linkdir itself goes at the beginning
                    self._linkdir_walk.insert(0, (self.linkdir, [parts[0]], []))
                except IndexError:
                    pass
            return self._linkdir_walk

    def setup_callbacks(self):
        '''
        Only needed in pygit2, included in the base class for simplicty of use
        '''
        pass

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
    def __init__(self, opts, remote, per_remote_defaults, per_remote_only,
                 override_params, cache_root, role='gitfs'):
        self.provider = 'gitpython'
        super(GitPython, self).__init__(
            opts, remote, per_remote_defaults, per_remote_only,
            override_params, cache_root, role
        )

    def checkout(self):
        '''
        Checkout the configured branch/tag. We catch an "Exception" class here
        instead of a specific exception class because the exceptions raised by
        GitPython when running these functions vary in different versions of
        GitPython.
        '''
        tgt_ref = self.get_checkout_target()
        try:
            head_sha = self.repo.rev_parse('HEAD').hexsha
        except Exception:
            # Should only happen the first time we are checking out, since
            # we fetch first before ever checking anything out.
            head_sha = None

        # 'origin/' + tgt_ref ==> matches a branch head
        # 'tags/' + tgt_ref + '@{commit}' ==> matches tag's commit
        for rev_parse_target, checkout_ref in (
                ('origin/' + tgt_ref, 'origin/' + tgt_ref),
                ('tags/' + tgt_ref, 'tags/' + tgt_ref)):
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
            'not exist', tgt_ref, self.role, self.id
        )
        return None

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
                log.error(_INVALID_REPO, self.cachedir, self.url, self.role)
                return new

        self.gitdir = salt.utils.path.join(self.repo.working_dir, '.git')
        self.enforce_git_config()

        return new

    def dir_list(self, tgt_env):
        '''
        Get list of directories for the target environment using GitPython
        '''
        ret = set()
        tree = self.get_tree(tgt_env)
        if not tree:
            return ret
        if self.root(tgt_env):
            try:
                tree = tree / self.root(tgt_env)
            except KeyError:
                return ret
            relpath = lambda path: os.path.relpath(path, self.root(tgt_env))
        else:
            relpath = lambda path: path
        add_mountpoint = lambda path: salt.utils.path.join(
            self.mountpoint(tgt_env), path, use_posixpath=True)
        for blob in tree.traverse():
            if isinstance(blob, git.Tree):
                ret.add(add_mountpoint(relpath(blob.path)))
        if self.mountpoint(tgt_env):
            ret.add(self.mountpoint(tgt_env))
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
                    '%s has updated \'%s\' for remote \'%s\' '
                    'from %s to %s',
                    self.role,
                    fetchinfo.name,
                    self.id,
                    fetchinfo.old_commit.hexsha[:7],
                    fetchinfo.commit.hexsha[:7]
                )
                new_objs = True
            elif fetchinfo.flags in (fetchinfo.NEW_TAG,
                                     fetchinfo.NEW_HEAD):
                log.debug(
                    '%s has fetched new %s \'%s\' for remote \'%s\'',
                    self.role,
                    'tag' if fetchinfo.flags == fetchinfo.NEW_TAG else 'head',
                    fetchinfo.name,
                    self.id
                )
                new_objs = True

        cleaned = self.clean_stale_refs()
        return True if (new_objs or cleaned) else None

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
        if self.root(tgt_env):
            try:
                tree = tree / self.root(tgt_env)
            except KeyError:
                return files, symlinks
            relpath = lambda path: os.path.relpath(path, self.root(tgt_env))
        else:
            relpath = lambda path: path
        add_mountpoint = lambda path: salt.utils.path.join(
            self.mountpoint(tgt_env), path, use_posixpath=True)
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
            # Branch/tag/SHA not found in repo
            return None, None, None
        blob = None
        depth = 0
        while True:
            depth += 1
            if depth > SYMLINK_RECURSE_DEPTH:
                blob = None
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
                    path = salt.utils.path.join(
                        os.path.dirname(path), link_tgt, use_posixpath=True)
                else:
                    blob = file_blob
                    if isinstance(blob, git.Tree):
                        # Path is a directory, not a file.
                        blob = None
                    break
            except KeyError:
                # File not found or repo_path points to a directory
                blob = None
                break
        if isinstance(blob, git.Blob):
            return blob, blob.hexsha, blob.mode
        return None, None, None

    def get_tree_from_branch(self, ref):
        '''
        Return a git.Tree object matching a head ref fetched into
        refs/remotes/origin/
        '''
        try:
            return git.RemoteReference(
                self.repo,
                'refs/remotes/origin/{0}'.format(ref)).commit.tree
        except ValueError:
            return None

    def get_tree_from_tag(self, ref):
        '''
        Return a git.Tree object matching a tag ref fetched into refs/tags/
        '''
        try:
            return git.TagReference(
                self.repo,
                'refs/tags/{0}'.format(ref)).commit.tree
        except ValueError:
            return None

    def get_tree_from_sha(self, ref):
        '''
        Return a git.Tree object matching a SHA
        '''
        try:
            return self.repo.rev_parse(ref).tree
        except (gitdb.exc.ODBError, AttributeError):
            return None

    def write_file(self, blob, dest):
        '''
        Using the blob object, write the file to the destination path
        '''
        with salt.utils.files.fopen(dest, 'wb+') as fp_:
            blob.stream_data(fp_)


class Pygit2(GitProvider):
    '''
    Interface to Pygit2
    '''
    def __init__(self, opts, remote, per_remote_defaults, per_remote_only,
                 override_params, cache_root, role='gitfs'):
        self.provider = 'pygit2'
        super(Pygit2, self).__init__(
            opts, remote, per_remote_defaults, per_remote_only,
            override_params, cache_root, role
        )

    def peel(self, obj):
        '''
        Compatibility function for pygit2.Reference objects. Older versions of
        pygit2 use .get_object() to return the object to which the reference
        points, while newer versions use .peel(). In pygit2 0.27.4,
        .get_object() was removed. This function will try .peel() first and
        fall back to .get_object().
        '''
        try:
            return obj.peel()
        except AttributeError:
            return obj.get_object()

    def checkout(self):
        '''
        Checkout the configured branch/tag
        '''
        tgt_ref = self.get_checkout_target()
        local_ref = 'refs/heads/' + tgt_ref
        remote_ref = 'refs/remotes/origin/' + tgt_ref
        tag_ref = 'refs/tags/' + tgt_ref

        try:
            local_head = self.repo.lookup_reference('HEAD')
        except KeyError:
            log.warning(
                'HEAD not present in %s remote \'%s\'', self.role, self.id
            )
            return None

        try:
            head_sha = self.peel(local_head).hex
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
                oid = self.peel(self.repo.lookup_reference(remote_ref)).id
                if local_ref not in refs:
                    # No local branch for this remote, so create one and point
                    # it at the commit id of the remote ref
                    self.repo.create_reference(local_ref, oid)

                try:
                    target_sha = \
                        self.peel(self.repo.lookup_reference(remote_ref)).hex
                except KeyError:
                    log.error(
                        'pygit2 was unable to get SHA for %s in %s remote '
                        '\'%s\'', local_ref, self.role, self.id,
                        exc_info=True
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
                                'HEAD ref \'%s\' in %s remote \'%s\'',
                                head_ref, self.role, self.id
                            )
                            return None
                        remote_head = 'refs/remotes/origin/' + branch_name
                        if remote_head not in refs:
                            # No remote ref for HEAD exists. This can happen in
                            # the first-time git_pillar checkout when when the
                            # remote repo does not have a master branch. Since
                            # we need a HEAD reference to keep pygit2 from
                            # throwing an error, and none exists in
                            # refs/remotes/origin, we'll just point HEAD at the
                            # remote_ref.
                            remote_head = remote_ref
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
                if not isinstance(tag_obj, pygit2.Commit):
                    log.error(
                        '%s does not correspond to pygit2.Commit object',
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
                                tag_ref, self.role, self.id,
                                exc_info=True
                            )
                            return None
                    log.debug('SHA of tag %s: %s', tgt_ref, tag_sha)

                    if head_sha != tag_sha:
                        if not _perform_checkout(tag_ref, branch=False):
                            return None

                    # Return the relative root, if present
                    return self.check_root()
        except GitLockError:
            raise
        except Exception as exc:
            log.error(
                'Failed to checkout %s from %s remote \'%s\': %s',
                tgt_ref, self.role, self.id, exc,
                exc_info=True
            )
            return None
        log.error(
            'Failed to checkout %s from %s remote \'%s\': remote ref '
            'does not exist', tgt_ref, self.role, self.id
        )
        return None

    def clean_stale_refs(self, local_refs=None):  # pylint: disable=arguments-differ
        '''
        Clean stale local refs so they don't appear as fileserver environments
        '''
        try:
            if pygit2.GIT_FETCH_PRUNE:
                # Don't need to clean anything, pygit2 can do it by itself
                return []
        except AttributeError:
            # However, only in 0.26.2 and newer
            pass
        if self.credentials is not None:
            log.debug(
                'The installed version of pygit2 (%s) does not support '
                'detecting stale refs for authenticated remotes, saltenvs '
                'will not reflect branches/tags removed from remote \'%s\'',
                PYGIT2_VERSION, self.id
            )
            return []
        return super(Pygit2, self).clean_stale_refs()

    def init_remote(self):
        '''
        Initialize/attach to a remote using pygit2. Return a boolean which
        will let the calling function know whether or not a new repo was
        initialized by this function.
        '''
        # https://github.com/libgit2/pygit2/issues/339
        # https://github.com/libgit2/libgit2/issues/2122
        home = os.path.expanduser('~')
        pygit2.settings.search_path[pygit2.GIT_CONFIG_LEVEL_GLOBAL] = home
        new = False
        if not os.listdir(self.cachedir):
            # Repo cachedir is empty, initialize a new repo there
            self.repo = pygit2.init_repository(self.cachedir)
            new = True
        else:
            # Repo cachedir exists, try to attach
            try:
                self.repo = pygit2.Repository(self.cachedir)
            except KeyError:
                log.error(_INVALID_REPO, self.cachedir, self.url, self.role)
                return new

        self.gitdir = salt.utils.path.join(self.repo.workdir, '.git')
        self.enforce_git_config()
        git_config = os.path.join(self.gitdir, 'config')
        if os.path.exists(git_config) and PYGIT2_VERSION >= _LooseVersion('0.28.0'):
            self.repo.config.add_file(git_config)

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
                blobs.append(
                    salt.utils.path.join(prefix, entry.name, use_posixpath=True)
                )
                if len(blob):
                    _traverse(
                        blob, blobs, salt.utils.path.join(
                            prefix, entry.name, use_posixpath=True)
                    )

        ret = set()
        tree = self.get_tree(tgt_env)
        if not tree:
            return ret
        if self.root(tgt_env):
            try:
                oid = tree[self.root(tgt_env)].oid
                tree = self.repo[oid]
            except KeyError:
                return ret
            if not isinstance(tree, pygit2.Tree):
                return ret
            relpath = lambda path: os.path.relpath(path, self.root(tgt_env))
        else:
            relpath = lambda path: path
        blobs = []
        if len(tree):
            _traverse(tree, blobs, self.root(tgt_env))
        add_mountpoint = lambda path: salt.utils.path.join(
            self.mountpoint(tgt_env), path, use_posixpath=True)
        for blob in blobs:
            ret.add(add_mountpoint(relpath(blob)))
        if self.mountpoint(tgt_env):
            ret.add(self.mountpoint(tgt_env))
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
        # pygit2 radically changed fetchiing in 0.23.2
        if self.remotecallbacks is not None:
            fetch_kwargs['callbacks'] = self.remotecallbacks
        else:
            if self.credentials is not None:
                origin.credentials = self.credentials
        try:
            fetch_kwargs['prune'] = pygit2.GIT_FETCH_PRUNE
        except AttributeError:
            # pruning only available in pygit2 >= 0.26.2
            pass
        try:
            fetch_results = origin.fetch(**fetch_kwargs)
        except GitError as exc:
            exc_str = get_error_message(exc).lower()
            if 'unsupported url protocol' in exc_str \
                    and isinstance(self.credentials, pygit2.Keypair):
                log.error(
                    'Unable to fetch SSH-based %s remote \'%s\'. '
                    'You may need to add ssh:// to the repo string or '
                    'libgit2 must be compiled with libssh2 to support '
                    'SSH authentication.', self.role, self.id,
                    exc_info=True
                )
            elif 'authentication required but no callback set' in exc_str:
                log.error(
                    '%s remote \'%s\' requires authentication, but no '
                    'authentication configured', self.role, self.id,
                    exc_info=True
                )
            else:
                log.error(
                    'Error occurred fetching %s remote \'%s\': %s',
                    self.role, self.id, exc,
                    exc_info=True
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
                '%s received %s objects for remote \'%s\'',
                self.role, received_objects, self.id
            )
        else:
            log.debug('%s remote \'%s\' is up-to-date', self.role, self.id)
        refs_post = self.repo.listall_references()
        cleaned = self.clean_stale_refs(local_refs=refs_post)
        return True \
            if (received_objects or refs_pre != refs_post or cleaned) \
            else None

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
                    repo_path = salt.utils.path.join(
                        prefix, entry.name, use_posixpath=True)
                    blobs.setdefault('files', []).append(repo_path)
                    if stat.S_ISLNK(tree[entry.name].filemode):
                        link_tgt = self.repo[tree[entry.name].oid].data
                        blobs.setdefault('symlinks', {})[repo_path] = link_tgt
                elif isinstance(obj, pygit2.Tree):
                    _traverse(
                        obj, blobs, salt.utils.path.join(
                            prefix, entry.name, use_posixpath=True)
                    )

        files = set()
        symlinks = {}
        tree = self.get_tree(tgt_env)
        if not tree:
            # Not found, return empty objects
            return files, symlinks
        if self.root(tgt_env):
            try:
                # This might need to be changed to account for a root that
                # spans more than one directory
                oid = tree[self.root(tgt_env)].oid
                tree = self.repo[oid]
            except KeyError:
                return files, symlinks
            if not isinstance(tree, pygit2.Tree):
                return files, symlinks
            relpath = lambda path: os.path.relpath(path, self.root(tgt_env))
        else:
            relpath = lambda path: path
        blobs = {}
        if len(tree):
            _traverse(tree, blobs, self.root(tgt_env))
        add_mountpoint = lambda path: salt.utils.path.join(
            self.mountpoint(tgt_env), path, use_posixpath=True)
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
            return None, None, None
        blob = None
        mode = None
        depth = 0
        while True:
            depth += 1
            if depth > SYMLINK_RECURSE_DEPTH:
                blob = None
                break
            try:
                entry = tree[path]
                mode = entry.filemode
                if stat.S_ISLNK(mode):
                    # Path is a symlink. The blob data corresponding to this
                    # path's object ID will be the target of the symlink. Follow
                    # the symlink and set path to the location indicated
                    # in the blob data.
                    link_tgt = self.repo[entry.oid].data
                    path = salt.utils.path.join(
                        os.path.dirname(path), link_tgt, use_posixpath=True)
                else:
                    blob = self.repo[entry.oid]
                    if isinstance(blob, pygit2.Tree):
                        # Path is a directory, not a file.
                        blob = None
                    break
            except KeyError:
                blob = None
                break
        if isinstance(blob, pygit2.Blob):
            return blob, blob.hex, mode
        return None, None, None

    def get_tree_from_branch(self, ref):
        '''
        Return a pygit2.Tree object matching a head ref fetched into
        refs/remotes/origin/
        '''
        try:
            return self.peel(self.repo.lookup_reference(
                'refs/remotes/origin/{0}'.format(ref))).tree
        except KeyError:
            return None

    def get_tree_from_tag(self, ref):
        '''
        Return a pygit2.Tree object matching a tag ref fetched into refs/tags/
        '''
        try:
            return self.peel(self.repo.lookup_reference(
                'refs/tags/{0}'.format(ref))).tree
        except KeyError:
            return None

    def get_tree_from_sha(self, ref):
        '''
        Return a pygit2.Tree object matching a SHA
        '''
        try:
            return self.repo.revparse_single(ref).tree
        except (KeyError, TypeError, ValueError, AttributeError):
            return None

    def setup_callbacks(self):
        '''
        Assign attributes for pygit2 callbacks
        '''
        if PYGIT2_VERSION >= _LooseVersion('0.23.2'):
            self.remotecallbacks = pygit2.RemoteCallbacks(
                credentials=self.credentials)
            if not self.ssl_verify:
                # Override the certificate_check function with a lambda that
                # just returns True, thus skipping the cert check.
                self.remotecallbacks.certificate_check = \
                    lambda *args, **kwargs: True
        else:
            self.remotecallbacks = None
            if not self.ssl_verify:
                warnings.warn(
                    'pygit2 does not support disabling the SSL certificate '
                    'check in versions prior to 0.23.2 (installed: {0}). '
                    'Fetches for self-signed certificates will fail.'.format(
                        PYGIT2_VERSION
                    )
                )

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
                'Incomplete authentication information for %s remote '
                '\'%s\'. Missing parameters: %s',
                self.role, self.id, ', '.join(missing)
            )
            failhard(self.role)

        def _key_does_not_exist(key_type, path):
            '''
            Helper function to log errors about missing key file
            '''
            log.critical(
                'SSH %s (%s) for %s remote \'%s\' could not be found, path '
                'may be incorrect. Note that it may be necessary to clear '
                'git_pillar locks to proceed once this is resolved and the '
                'master has been started back up. A warning will be logged '
                'if this is the case, with instructions.',
                key_type, path, self.role, self.id
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
                    'Keypair specified for %s remote \'%s\', but remote URL '
                    'is missing a username', self.role, self.id
                )
                failhard(self.role)

            self.user = user
            if all(bool(getattr(self, x, None)) for x in required_params):
                keypair_params = [getattr(self, x, None) for x in
                                  ('user', 'pubkey', 'privkey', 'passphrase')]
                # Check pubkey and privkey to make sure file exists
                for idx, key_type in ((1, 'pubkey'), (2, 'privkey')):
                    key_path = keypair_params[idx]
                    if key_path is not None:
                        try:
                            if not os.path.isfile(key_path):
                                _key_does_not_exist(key_type, key_path)
                        except TypeError:
                            _key_does_not_exist(key_type, key_path)
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
                        'Invalid configuration for %s remote \'%s\'. '
                        'Authentication is disabled by default on http '
                        'remotes. Either set %s_insecure_auth to True in the '
                        'master configuration file, set a per-remote config '
                        'option named \'insecure_auth\' to True, or use https '
                        'or ssh-based authentication.',
                        self.role, self.id, self.role
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
                'Invalid configuration for %s remote \'%s\'. Unsupported '
                'transport \'%s\'.', self.role, self.id, transport
            )
            failhard(self.role)

    def write_file(self, blob, dest):
        '''
        Using the blob object, write the file to the destination path
        '''
        with salt.utils.files.fopen(dest, 'wb+') as fp_:
            fp_.write(blob.data)


GIT_PROVIDERS = {
    'pygit2': Pygit2,
    'gitpython': GitPython,
}


class GitBase(object):
    '''
    Base class for gitfs/git_pillar
    '''
    def __init__(self, opts, remotes=None, per_remote_overrides=(),
                 per_remote_only=PER_REMOTE_ONLY, global_only=GLOBAL_ONLY,
                 git_providers=None, cache_root=None, init_remotes=True):
        '''
        IMPORTANT: If specifying a cache_root, understand that this is also
        where the remotes will be cloned. A non-default cache_root is only
        really designed right now for winrepo, as its repos need to be checked
        out into the winrepo locations and not within the cachedir.

        As of the 2018.3 release cycle, the classes used to interface with
        Pygit2 and GitPython can be overridden by passing the git_providers
        argument when spawning a class instance. This allows for one to write
        classes which inherit from salt.utils.gitfs.Pygit2 or
        salt.utils.gitfs.GitPython, and then direct one of the GitBase
        subclasses (GitFS, GitPillar, WinRepo) to use the custom class. For
        example:

        .. code-block:: Python

            import salt.utils.gitfs
            from salt.fileserver.gitfs import PER_REMOTE_OVERRIDES, PER_REMOTE_ONLY

            class CustomPygit2(salt.utils.gitfs.Pygit2):
                def fetch_remotes(self):
                    ...
                    Alternate fetch behavior here
                    ...

            git_providers = {
                'pygit2': CustomPygit2,
                'gitpython': salt.utils.gitfs.GitPython,
            }

            gitfs = salt.utils.gitfs.GitFS(
                __opts__,
                __opts__['gitfs_remotes'],
                per_remote_overrides=PER_REMOTE_OVERRIDES,
                per_remote_only=PER_REMOTE_ONLY,
                git_providers=git_providers)

            gitfs.fetch_remotes()
        '''
        self.opts = opts
        self.git_providers = git_providers if git_providers is not None \
            else GIT_PROVIDERS
        self.verify_provider()
        if cache_root is not None:
            self.cache_root = self.remote_root = cache_root
        else:
            self.cache_root = salt.utils.path.join(self.opts['cachedir'],
                                                   self.role)
            self.remote_root = salt.utils.path.join(self.cache_root, 'remotes')
        self.env_cache = salt.utils.path.join(self.cache_root, 'envs.p')
        self.hash_cachedir = salt.utils.path.join(self.cache_root, 'hash')
        self.file_list_cachedir = salt.utils.path.join(
            self.opts['cachedir'], 'file_lists', self.role)
        if init_remotes:
            self.init_remotes(
                remotes if remotes is not None else [],
                per_remote_overrides,
                per_remote_only,
                global_only)

    def init_remotes(self, remotes, per_remote_overrides=(),
                     per_remote_only=PER_REMOTE_ONLY,
                     global_only=GLOBAL_ONLY):
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
        global_values = set(override_params)
        global_values.update(set(global_only))
        for param in global_values:
            key = '{0}_{1}'.format(self.role, param)
            if key not in self.opts:
                log.critical(
                    'Key \'%s\' not present in global configuration. This is '
                    'a bug, please report it.', key
                )
                failhard(self.role)
            per_remote_defaults[param] = enforce_types(key, self.opts[key])

        self.remotes = []
        for remote in remotes:
            repo_obj = self.git_providers[self.provider](
                self.opts,
                remote,
                per_remote_defaults,
                per_remote_only,
                override_params,
                self.cache_root,
                self.role
            )
            if hasattr(repo_obj, 'repo'):
                # Sanity check and assign the credential parameter
                repo_obj.verify_auth()
                repo_obj.setup_callbacks()
                if self.opts['__role'] == 'minion' and repo_obj.new:
                    # Perform initial fetch on masterless minion
                    repo_obj.fetch()

                # Reverse map to be used when running envs() to detect the
                # available envs.
                repo_obj.saltenv_revmap = {}

                for saltenv, saltenv_conf in six.iteritems(repo_obj.saltenv):
                    if 'ref' in saltenv_conf:
                        ref = saltenv_conf['ref']
                        repo_obj.saltenv_revmap.setdefault(
                            ref, []).append(saltenv)

                        if saltenv == 'base':
                            # Remove redundant 'ref' config for base saltenv
                            repo_obj.saltenv[saltenv].pop('ref')
                            if ref != repo_obj.base:
                                log.warning(
                                    'The \'base\' environment has been '
                                    'defined in the \'saltenv\' param for %s '
                                    'remote %s and will override the '
                                    'branch/tag specified by %s_base (or a '
                                    'per-remote \'base\' parameter).',
                                    self.role, repo_obj.id, self.role
                                )
                                # Rewrite 'base' config param
                                repo_obj.base = ref

                # Build list of all envs defined by ref mappings in the
                # per-remote 'saltenv' param. We won't add any matching envs
                # from the global saltenv map to the revmap.
                all_envs = []
                for env_names in six.itervalues(repo_obj.saltenv_revmap):
                    all_envs.extend(env_names)

                # Add the global saltenv map to the reverse map, skipping envs
                # explicitly mapped in the per-remote 'saltenv' param.
                for key, conf in six.iteritems(repo_obj.global_saltenv):
                    if key not in all_envs and 'ref' in conf:
                        repo_obj.saltenv_revmap.setdefault(
                            conf['ref'], []).append(key)

                self.remotes.append(repo_obj)

        # Don't allow collisions in cachedir naming
        cachedir_map = {}
        for repo in self.remotes:
            cachedir_map.setdefault(repo.cachedir, []).append(repo.id)

        collisions = [x for x in cachedir_map if len(cachedir_map[x]) > 1]
        if collisions:
            for dirname in collisions:
                log.critical(
                    'The following %s remotes have conflicting cachedirs: '
                    '%s. Resolve this using a per-remote parameter called '
                    '\'name\'.', self.role, ', '.join(cachedir_map[dirname])
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
            path = salt.utils.path.join(self.cache_root, item)
            if os.path.isdir(path):
                to_remove.append(path)
        failed = []
        if to_remove:
            for rdir in to_remove:
                try:
                    shutil.rmtree(rdir)
                except OSError as exc:
                    log.error(
                        'Unable to remove old %s remote cachedir %s: %s',
                        self.role, rdir, exc
                    )
                    failed.append(rdir)
                else:
                    log.debug('%s removed old cachedir %s', self.role, rdir)
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

    def fetch_remotes(self, remotes=None):
        '''
        Fetch all remotes and return a boolean to let the calling function know
        whether or not any remotes were updated in the process of fetching
        '''
        if remotes is None:
            remotes = []
        elif not isinstance(remotes, list):
            log.error(
                'Invalid \'remotes\' argument (%s) for fetch_remotes. '
                'Must be a list of strings', remotes
            )
            remotes = []

        changed = False
        for repo in self.remotes:
            name = getattr(repo, 'name', None)
            if not remotes or (repo.id, name) in remotes:
                try:
                    if repo.fetch():
                        # We can't just use the return value from repo.fetch()
                        # because the data could still have changed if old
                        # remotes were cleared above. Additionally, we're
                        # running this in a loop and later remotes without
                        # changes would override this value and make it
                        # incorrect.
                        changed = True
                except Exception as exc:
                    log.error(
                        'Exception caught while fetching %s remote \'%s\': %s',
                        self.role, repo.id, exc,
                        exc_info=True
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

    def update(self, remotes=None):
        '''
        .. versionchanged:: 2018.3.0
            The remotes argument was added. This being a list of remote URLs,
            it will only update matching remotes. This actually matches on
            repo.id

        Execute a git fetch on all of the repos and perform maintenance on the
        fileserver cache.
        '''
        # data for the fileserver event
        data = {'changed': False,
                'backend': 'gitfs'}

        data['changed'] = self.clear_old_remotes()
        if self.fetch_remotes(remotes=remotes):
            data['changed'] = True

        # A masterless minion will need a new env cache file even if no changes
        # were fetched.
        refresh_env_cache = self.opts['__role'] == 'minion'

        if data['changed'] is True or not os.path.isfile(self.env_cache):
            env_cachedir = os.path.dirname(self.env_cache)
            if not os.path.exists(env_cachedir):
                os.makedirs(env_cachedir)
            refresh_env_cache = True

        if refresh_env_cache:
            new_envs = self.envs(ignore_cache=True)
            serial = salt.payload.Serial(self.opts)
            with salt.utils.files.fopen(self.env_cache, 'wb+') as fp_:
                fp_.write(serial.dumps(new_envs))
                log.trace('Wrote env cache data to %s', self.env_cache)

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

    def update_intervals(self):
        '''
        Returns a dictionary mapping remote IDs to their intervals, designed to
        be used for variable update intervals in salt.master.FileserverUpdate.

        A remote's ID is defined here as a tuple of the GitPython/Pygit2
        object's "id" and "name" attributes, with None being assumed as the
        "name" value if the attribute is not present.
        '''
        return {(repo.id, getattr(repo, 'name', None)): repo.update_interval
                for repo in self.remotes}

    def verify_provider(self):
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
            else:
                # Ensure non-lowercase providers work
                try:
                    desired_provider = desired_provider.lower()
                except AttributeError:
                    # Should only happen if someone does something silly like
                    # set the provider to a numeric value.
                    desired_provider = six.text_type(desired_provider).lower()
                if desired_provider not in self.git_providers:
                    log.critical(
                        'Invalid %s_provider \'%s\'. Valid choices are: %s',
                        self.role,
                        desired_provider,
                        ', '.join(self.git_providers)
                    )
                    failhard(self.role)
                elif desired_provider == 'pygit2' and self.verify_pygit2():
                    self.provider = 'pygit2'
                elif desired_provider == 'gitpython' and self.verify_gitpython():
                    self.provider = 'gitpython'
        if not hasattr(self, 'provider'):
            log.critical(
                'No suitable %s provider module is installed.', self.role
            )
            failhard(self.role)

    def verify_gitpython(self, quiet=False):
        '''
        Check if GitPython is available and at a compatible version (>= 0.3.0)
        '''
        def _recommend():
            if PYGIT2_VERSION and 'pygit2' in self.git_providers:
                log.error(_RECOMMEND_PYGIT2, self.role, self.role)

        if not GITPYTHON_VERSION:
            if not quiet:
                log.error(
                    '%s is configured but could not be loaded, is GitPython '
                    'installed?', self.role
                )
                _recommend()
            return False
        elif 'gitpython' not in self.git_providers:
            return False

        errors = []
        if GITPYTHON_VERSION < GITPYTHON_MINVER:
            errors.append(
                '{0} is configured, but the GitPython version is earlier than '
                '{1}. Version {2} detected.'.format(
                    self.role,
                    GITPYTHON_MINVER,
                    GITPYTHON_VERSION
                )
            )
        if not salt.utils.path.which('git'):
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
        log.debug('gitpython %s_provider enabled', self.role)
        return True

    def verify_pygit2(self, quiet=False):
        '''
        Check if pygit2/libgit2 are available and at a compatible version.
        Pygit2 must be at least 0.20.3 and libgit2 must be at least 0.20.0.
        '''
        def _recommend():
            if GITPYTHON_VERSION and 'gitpython' in self.git_providers:
                log.error(_RECOMMEND_GITPYTHON, self.role, self.role)

        if not PYGIT2_VERSION:
            if not quiet:
                log.error(
                    '%s is configured but could not be loaded, are pygit2 '
                    'and libgit2 installed?', self.role
                )
                _recommend()
            return False
        elif 'pygit2' not in self.git_providers:
            return False

        errors = []
        if PYGIT2_VERSION < PYGIT2_MINVER:
            errors.append(
                '{0} is configured, but the pygit2 version is earlier than '
                '{1}. Version {2} detected.'.format(
                    self.role,
                    PYGIT2_MINVER,
                    PYGIT2_VERSION
                )
            )
        if LIBGIT2_VERSION < LIBGIT2_MINVER:
            errors.append(
                '{0} is configured, but the libgit2 version is earlier than '
                '{1}. Version {2} detected.'.format(
                    self.role,
                    LIBGIT2_MINVER,
                    LIBGIT2_VERSION
                )
            )
        if not getattr(pygit2, 'GIT_FETCH_PRUNE', False) \
                and not salt.utils.path.which('git'):
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
        log.debug('pygit2 %s_provider enabled', self.role)
        return True

    def write_remote_map(self):
        '''
        Write the remote_map.txt
        '''
        remote_map = salt.utils.path.join(self.cache_root, 'remote_map.txt')
        try:
            with salt.utils.files.fopen(remote_map, 'w+') as fp_:
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
                        salt.utils.stringutils.to_str(
                            '{0} = {1}\n'.format(
                                repo.cachedir_basename,
                                repo.id
                            )
                        )
                    )
        except OSError:
            pass
        else:
            log.info('Wrote new %s remote map to %s', self.role, remote_map)

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
                        exc,
                        exc_info=True
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
    role = 'gitfs'
    instance_map = weakref.WeakKeyDictionary()

    def __new__(cls, opts, remotes=None, per_remote_overrides=(),
                per_remote_only=PER_REMOTE_ONLY, git_providers=None,
                cache_root=None, init_remotes=True):
        '''
        If we are not initializing remotes (such as in cases where we just want
        to load the config so that we can run clear_cache), then just return a
        new __init__'ed object. Otherwise, check the instance map and re-use an
        instance if one exists for the current process. Weak references are
        used to ensure that we garbage collect instances for threads which have
        exited.
        '''
        # No need to get the ioloop reference if we're not initializing remotes
        io_loop = tornado.ioloop.IOLoop.current() if init_remotes else None
        if not init_remotes or io_loop not in cls.instance_map:
            # We only evaluate the second condition in this if statement if
            # we're initializing remotes, so we won't get here unless io_loop
            # is something other than None.
            obj = object.__new__(cls)
            super(GitFS, obj).__init__(
                opts,
                remotes if remotes is not None else [],
                per_remote_overrides=per_remote_overrides,
                per_remote_only=per_remote_only,
                git_providers=git_providers if git_providers is not None
                    else GIT_PROVIDERS,
                cache_root=cache_root,
                init_remotes=init_remotes)
            if not init_remotes:
                log.debug('Created gitfs object with uninitialized remotes')
            else:
                log.debug('Created gitfs object for process %s', os.getpid())
                # Add to the instance map so we can re-use later
                cls.instance_map[io_loop] = obj
            return obj
        log.debug('Re-using gitfs object for process %s', os.getpid())
        return cls.instance_map[io_loop]

    def __init__(self, opts, remotes, per_remote_overrides=(),  # pylint: disable=super-init-not-called
                 per_remote_only=PER_REMOTE_ONLY, git_providers=None,
                 cache_root=None, init_remotes=True):
        # Initialization happens above in __new__(), so don't do anything here
        pass

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
            repo_envs = repo.envs()
            for env_list in six.itervalues(repo.saltenv_revmap):
                repo_envs.update(env_list)
            ret.update([x for x in repo_envs if repo.env_is_exposed(x)])
        return sorted(ret)

    def find_file(self, path, tgt_env='base', **kwargs):  # pylint: disable=W0613
        '''
        Find the first file to match the path and ref, read the file out of git
        and send the path to the newly cached file
        '''
        fnd = {'path': '',
               'rel': ''}
        if os.path.isabs(path) or \
                (not salt.utils.stringutils.is_hex(tgt_env) and tgt_env not in self.envs()):
            return fnd

        dest = salt.utils.path.join(self.cache_root, 'refs', tgt_env, path)
        hashes_glob = salt.utils.path.join(self.hash_cachedir,
                                           tgt_env,
                                           '{0}.hash.*'.format(path))
        blobshadest = salt.utils.path.join(self.hash_cachedir,
                                           tgt_env,
                                           '{0}.hash.blob_sha1'.format(path))
        lk_fn = salt.utils.path.join(self.hash_cachedir,
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
            if repo.mountpoint(tgt_env) \
                    and not path.startswith(repo.mountpoint(tgt_env) + os.sep):
                continue
            repo_path = path[len(repo.mountpoint(tgt_env)):].lstrip(os.sep)
            if repo.root(tgt_env):
                repo_path = salt.utils.path.join(repo.root(tgt_env), repo_path)

            blob, blob_hexsha, blob_mode = repo.find_file(repo_path, tgt_env)
            if blob is None:
                continue

            def _add_file_stat(fnd, mode):
                '''
                Add a the mode to the return dict. In other fileserver backends
                we stat the file to get its mode, and add the stat result
                (passed through list() for better serialization) to the 'stat'
                key in the return dict. However, since we aren't using the
                stat result for anything but the mode at this time, we can
                avoid unnecessary work by just manually creating the list and
                not running an os.stat() on all files in the repo.
                '''
                if mode is not None:
                    fnd['stat'] = [mode]
                return fnd

            salt.fileserver.wait_lock(lk_fn, dest)
            try:
                with salt.utils.files.fopen(blobshadest, 'r') as fp_:
                    sha = salt.utils.stringutils.to_unicode(fp_.read())
                    if sha == blob_hexsha:
                        fnd['rel'] = path
                        fnd['path'] = dest
                        return _add_file_stat(fnd, blob_mode)
            except IOError as exc:
                if exc.errno != errno.ENOENT:
                    raise exc

            with salt.utils.files.fopen(lk_fn, 'w'):
                pass

            for filename in glob.glob(hashes_glob):
                try:
                    os.remove(filename)
                except Exception:
                    pass
            # Write contents of file to their destination in the FS cache
            repo.write_file(blob, dest)
            with salt.utils.files.fopen(blobshadest, 'w+') as fp_:
                fp_.write(blob_hexsha)
            try:
                os.remove(lk_fn)
            except OSError:
                pass
            fnd['rel'] = path
            fnd['path'] = dest
            return _add_file_stat(fnd, blob_mode)

        # No matching file was found in tgt_env. Return a dict with empty paths
        # so the calling function knows the file could not be found.
        return fnd

    def serve_file(self, load, fnd):
        '''
        Return a chunk from a file based on the data received
        '''
        if 'env' in load:
            # "env" is not supported; Use "saltenv".
            load.pop('env')

        ret = {'data': '',
               'dest': ''}
        required_load_keys = set(['path', 'loc', 'saltenv'])
        if not all(x in load for x in required_load_keys):
            log.debug(
                'Not all of the required keys present in payload. Missing: %s',
                ', '.join(required_load_keys.difference(load))
            )
            return ret
        if not fnd['path']:
            return ret
        ret['dest'] = fnd['rel']
        gzip = load.get('gzip', None)
        fpath = os.path.normpath(fnd['path'])
        with salt.utils.files.fopen(fpath, 'rb') as fp_:
            fp_.seek(load['loc'])
            data = fp_.read(self.opts['file_buffer_size'])
            if data and six.PY3 and not salt.utils.files.is_binary(fpath):
                data = data.decode(__salt_system_encoding__)
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
            # "env" is not supported; Use "saltenv".
            load.pop('env')

        if not all(x in load for x in ('path', 'saltenv')):
            return '', None
        ret = {'hash_type': self.opts['hash_type']}
        relpath = fnd['rel']
        path = fnd['path']
        hashdest = salt.utils.path.join(self.hash_cachedir,
                                        load['saltenv'],
                                        '{0}.hash.{1}'.format(relpath,
                                                              self.opts['hash_type']))
        try:
            with salt.utils.files.fopen(hashdest, 'rb') as fp_:
                ret['hsum'] = fp_.read()
            return ret
        except IOError as exc:
            if exc.errno != errno.ENOENT:
                raise exc

        try:
            os.makedirs(os.path.dirname(hashdest))
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise exc

        ret['hsum'] = salt.utils.hashutils.get_hash(path, self.opts['hash_type'])
        with salt.utils.files.fopen(hashdest, 'w+') as fp_:
            fp_.write(ret['hsum'])
        return ret

    def _file_lists(self, load, form):
        '''
        Return a dict containing the file lists for files and dirs
        '''
        if 'env' in load:
            # "env" is not supported; Use "saltenv".
            load.pop('env')

        if not os.path.isdir(self.file_list_cachedir):
            try:
                os.makedirs(self.file_list_cachedir)
            except os.error:
                log.error('Unable to make cachedir %s', self.file_list_cachedir)
                return []
        list_cache = salt.utils.path.join(
            self.file_list_cachedir,
            '{0}.p'.format(load['saltenv'].replace(os.path.sep, '_|-'))
        )
        w_lock = salt.utils.path.join(
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
            if salt.utils.stringutils.is_hex(load['saltenv']) \
                    or load['saltenv'] in self.envs():
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
            # "env" is not supported; Use "saltenv".
            load.pop('env')

        if not salt.utils.stringutils.is_hex(load['saltenv']) \
                and load['saltenv'] not in self.envs():
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
    role = 'git_pillar'

    def checkout(self):
        '''
        Checkout the targeted branches/tags from the git_pillar remotes
        '''
        self.pillar_dirs = OrderedDict()
        self.pillar_linked_dirs = []
        for repo in self.remotes:
            cachedir = self.do_checkout(repo)
            if cachedir is not None:
                # Figure out which environment this remote should be assigned
                if repo.branch == '__env__' and hasattr(repo, 'all_saltenvs'):
                    env = self.opts.get('pillarenv') \
                        or self.opts.get('saltenv') \
                        or 'base'
                elif repo.env:
                    env = repo.env
                else:
                    if repo.branch == repo.base:
                        env = 'base'
                    else:
                        tgt = repo.get_checkout_target()
                        env = 'base' if tgt == repo.base else tgt
                if repo._mountpoint:
                    if self.link_mountpoint(repo):
                        self.pillar_dirs[repo.linkdir] = env
                        self.pillar_linked_dirs.append(repo.linkdir)
                else:
                    self.pillar_dirs[cachedir] = env

    def link_mountpoint(self, repo):
        '''
        Ensure that the mountpoint is present in the correct location and
        points at the correct path
        '''
        lcachelink = salt.utils.path.join(repo.linkdir, repo._mountpoint)
        lcachedest = salt.utils.path.join(repo.cachedir, repo.root()).rstrip(os.sep)
        wipe_linkdir = False
        create_link = False
        try:
            with repo.gen_lock(lock_type='mountpoint', timeout=10):
                walk_results = list(os.walk(repo.linkdir, followlinks=False))
                if walk_results != repo.linkdir_walk:
                    log.debug(
                        'Results of walking %s differ from expected results',
                        repo.linkdir
                    )
                    log.debug('Walk results: %s', walk_results)
                    log.debug('Expected results: %s', repo.linkdir_walk)
                    wipe_linkdir = True
                else:
                    if not all(not salt.utils.path.islink(x[0])
                               and os.path.isdir(x[0])
                               for x in walk_results[:-1]):
                        log.debug(
                            'Linkdir parents of %s are not all directories',
                            lcachelink
                        )
                        wipe_linkdir = True
                    elif not salt.utils.path.islink(lcachelink):
                        wipe_linkdir = True
                    else:
                        try:
                            ldest = salt.utils.path.readlink(lcachelink)
                        except Exception:
                            log.debug(
                                'Failed to read destination of %s', lcachelink
                            )
                            wipe_linkdir = True
                        else:
                            if ldest != lcachedest:
                                log.debug(
                                    'Destination of %s (%s) does not match '
                                    'the expected value (%s)',
                                    lcachelink, ldest, lcachedest
                                )
                                # Since we know that the parent dirs of the
                                # link are set up properly, all we need to do
                                # is remove the symlink and let it be created
                                # below.
                                try:
                                    if salt.utils.platform.is_windows() \
                                            and not ldest.startswith('\\\\') \
                                            and os.path.isdir(ldest):
                                        # On Windows, symlinks to directories
                                        # must be removed as if they were
                                        # themselves directories.
                                        shutil.rmtree(lcachelink)
                                    else:
                                        os.remove(lcachelink)
                                except Exception as exc:
                                    log.exception(
                                        'Failed to remove existing git_pillar '
                                        'mountpoint link %s: %s',
                                        lcachelink, exc.__str__()
                                    )
                                wipe_linkdir = False
                                create_link = True

                if wipe_linkdir:
                    # Wiping implies that we need to create the link
                    create_link = True
                    try:
                        shutil.rmtree(repo.linkdir)
                    except OSError:
                        pass
                    try:
                        ldirname = os.path.dirname(lcachelink)
                        os.makedirs(ldirname)
                        log.debug('Successfully made linkdir parent %s', ldirname)
                    except OSError as exc:
                        log.error(
                            'Failed to os.makedirs() linkdir parent %s: %s',
                            ldirname, exc.__str__()
                        )
                        return False

                if create_link:
                    try:
                        os.symlink(lcachedest, lcachelink)
                        log.debug(
                            'Successfully linked %s to cachedir %s',
                            lcachelink, lcachedest
                        )
                        return True
                    except OSError as exc:
                        log.error(
                            'Failed to create symlink to %s at path %s: %s',
                            lcachedest, lcachelink, exc.__str__()
                        )
                        return False
        except GitLockError:
            log.error(
                'Timed out setting mountpoint lock for %s remote \'%s\'. If '
                'this error persists, it may be because an earlier %s '
                'checkout was interrupted. The lock can be cleared by running '
                '\'salt-run cache.clear_git_lock %s type=mountpoint\', or by '
                'manually removing %s.',
                self.role, repo.id, self.role, self.role,
                repo._get_lock_file(lock_type='mountpoint')
            )
            return False
        return True


class WinRepo(GitBase):
    '''
    Functionality specific to the winrepo runner
    '''
    role = 'winrepo'
    # Need to define this in case we try to reference it before checking
    # out the repos.
    winrepo_dirs = {}

    def checkout(self):
        '''
        Checkout the targeted branches/tags from the winrepo remotes
        '''
        self.winrepo_dirs = {}
        for repo in self.remotes:
            cachedir = self.do_checkout(repo)
            if cachedir is not None:
                self.winrepo_dirs[repo.id] = cachedir
