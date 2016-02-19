# -*- coding: utf-8 -*-
'''
Subversion Fileserver Backend

After enabling this backend, branches, and tags in a remote subversion
repository are exposed to salt as different environments. To enable this
backend, add ``svn`` to the :conf_master:`fileserver_backend` option in the
Master config file.

.. code-block:: yaml

    fileserver_backend:
      - svn

This backend assumes a standard svn layout with directories for ``branches``,
``tags``, and ``trunk``, at the repository root.

:depends:   - subversion
            - pysvn

.. versionchanged:: 2014.7.0
    The paths to the trunk, branches, and tags have been made configurable, via
    the config options :conf_master:`svnfs_trunk`,
    :conf_master:`svnfs_branches`, and :conf_master:`svnfs_tags`.
    :conf_master:`svnfs_mountpoint` was also added. Finally, support for
    per-remote configuration parameters was added. See the
    :conf_master:`documentation <svnfs_remotes>` for more information.
'''

# Import python libs
from __future__ import absolute_import
import copy
import errno
import fnmatch
import hashlib
import logging
import os
import shutil
from datetime import datetime
from salt.exceptions import FileserverConfigError

PER_REMOTE_OVERRIDES = ('mountpoint', 'root', 'trunk', 'branches', 'tags')

# Import third party libs
import salt.ext.six as six
# pylint: disable=import-error
HAS_SVN = False
try:
    import pysvn
    HAS_SVN = True
    CLIENT = pysvn.Client()
except ImportError:
    pass
# pylint: enable=import-error

# Import salt libs
import salt.utils
import salt.utils.url
import salt.fileserver
from salt.utils.event import tagify

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'svn'


def __virtual__():
    '''
    Only load if subversion is available
    '''
    if __virtualname__ not in __opts__['fileserver_backend']:
        return False
    if not HAS_SVN:
        log.error('Subversion fileserver backend is enabled in configuration '
                  'but could not be loaded, is pysvn installed?')
        return False
    errors = []
    for param in ('svnfs_trunk', 'svnfs_branches', 'svnfs_tags'):
        if os.path.isabs(__opts__[param]):
            errors.append(
                'Master configuration parameter \'{0}\' (value: {1}) cannot '
                'be an absolute path'.format(param, __opts__[param])
            )
    if errors:
        for error in errors:
            log.error(error)
        log.error('Subversion fileserver backed will be disabled')
        return False
    return __virtualname__


def _rev(repo):
    '''
    Returns revision ID of repo
    '''
    try:
        repo_info = dict(six.iteritems(CLIENT.info(repo['repo'])))
    except (pysvn._pysvn.ClientError, TypeError,
            KeyError, AttributeError) as exc:
        log.error(
            'Error retrieving revision ID for svnfs remote {0} '
            '(cachedir: {1}): {2}'
            .format(repo['url'], repo['repo'], exc)
        )
    else:
        return repo_info['revision'].number
    return None


def _failhard():
    '''
    Fatal fileserver configuration issue, raise an exception
    '''
    raise FileserverConfigError(
        'Failed to load svn fileserver backend'
    )


def init():
    '''
    Return the list of svn remotes and their configuration information
    '''
    bp_ = os.path.join(__opts__['cachedir'], 'svnfs')
    new_remote = False
    repos = []

    per_remote_defaults = {}
    for param in PER_REMOTE_OVERRIDES:
        per_remote_defaults[param] = \
            six.text_type(__opts__['svnfs_{0}'.format(param)])

    for remote in __opts__['svnfs_remotes']:
        repo_conf = copy.deepcopy(per_remote_defaults)
        if isinstance(remote, dict):
            repo_url = next(iter(remote))
            per_remote_conf = dict(
                [(key, six.text_type(val)) for key, val in
                 six.iteritems(salt.utils.repack_dictlist(remote[repo_url]))]
            )
            if not per_remote_conf:
                log.error(
                    'Invalid per-remote configuration for remote {0}. If no '
                    'per-remote parameters are being specified, there may be '
                    'a trailing colon after the URL, which should be removed. '
                    'Check the master configuration file.'.format(repo_url)
                )
                _failhard()

            per_remote_errors = False
            for param in (x for x in per_remote_conf
                          if x not in PER_REMOTE_OVERRIDES):
                log.error(
                    'Invalid configuration parameter \'{0}\' for remote {1}. '
                    'Valid parameters are: {2}. See the documentation for '
                    'further information.'.format(
                        param, repo_url, ', '.join(PER_REMOTE_OVERRIDES)
                    )
                )
                per_remote_errors = True
            if per_remote_errors:
                _failhard()

            repo_conf.update(per_remote_conf)
        else:
            repo_url = remote

        if not isinstance(repo_url, six.string_types):
            log.error(
                'Invalid svnfs remote {0}. Remotes must be strings, you may '
                'need to enclose the URL in quotes'.format(repo_url)
            )
            _failhard()

        try:
            repo_conf['mountpoint'] = salt.utils.url.strip_proto(
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

        if not os.listdir(rp_):
            # Only attempt a new checkout if the directory is empty.
            try:
                CLIENT.checkout(repo_url, rp_)
                repos.append(rp_)
                new_remote = True
            except pysvn._pysvn.ClientError as exc:
                log.error(
                    'Failed to initialize svnfs remote \'{0}\': {1}'
                    .format(repo_url, exc)
                )
                _failhard()
        else:
            # Confirm that there is an svn checkout at the necessary path by
            # running pysvn.Client().status()
            try:
                CLIENT.status(rp_)
            except pysvn._pysvn.ClientError as exc:
                log.error(
                    'Cache path {0} (corresponding remote: {1}) exists but is '
                    'not a valid subversion checkout. You will need to '
                    'manually delete this directory on the master to continue '
                    'to use this svnfs remote.'.format(rp_, repo_url)
                )
                _failhard()

        repo_conf.update({
            'repo': rp_,
            'url': repo_url,
            'hash': repo_hash,
            'cachedir': rp_,
            'lockfile': os.path.join(rp_, 'update.lk')
        })
        repos.append(repo_conf)

    if new_remote:
        remote_map = os.path.join(__opts__['cachedir'], 'svnfs/remote_map.txt')
        try:
            with salt.utils.fopen(remote_map, 'w+') as fp_:
                timestamp = datetime.now().strftime('%d %b %Y %H:%M:%S.%f')
                fp_.write('# svnfs_remote map as of {0}\n'.format(timestamp))
                for repo_conf in repos:
                    fp_.write(
                        '{0} = {1}\n'.format(
                            repo_conf['hash'], repo_conf['url']
                        )
                    )
        except OSError:
            pass
        else:
            log.info('Wrote new svnfs_remote map to {0}'.format(remote_map))

    return repos


def _clear_old_remotes():
    '''
    Remove cache directories for remotes no longer configured
    '''
    bp_ = os.path.join(__opts__['cachedir'], 'svnfs')
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
                    'Unable to remove old svnfs remote cachedir {0}: {1}'
                    .format(rdir, exc)
                )
                failed.append(rdir)
            else:
                log.debug('svnfs removed old cachedir {0}'.format(rdir))
    for fdir in failed:
        to_remove.remove(fdir)
    return bool(to_remove), repos


def clear_cache():
    '''
    Completely clear svnfs cache
    '''
    fsb_cachedir = os.path.join(__opts__['cachedir'], 'svnfs')
    list_cachedir = os.path.join(__opts__['cachedir'], 'file_lists/svnfs')
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
                if remote not in repo['url']:
                    continue
            except TypeError:
                # remote was non-string, try again
                if six.text_type(remote) not in repo['url']:
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
                if not fnmatch.fnmatch(repo['url'], six.text_type(remote)):
                    continue
        success, failed = _do_lock(repo)
        locked.extend(success)
        errors.extend(failed)

    return locked, errors


def update():
    '''
    Execute an svn update on all of the repos
    '''
    # data for the fileserver event
    data = {'changed': False,
            'backend': 'svnfs'}
    # _clear_old_remotes runs init(), so use the value from there to avoid a
    # second init()
    data['changed'], repos = _clear_old_remotes()
    for repo in repos:
        if os.path.exists(repo['lockfile']):
            log.warning(
                'Update lockfile is present for svnfs remote {0}, skipping. '
                'If this warning persists, it is possible that the update '
                'process was interrupted. Removing {1} or running '
                '\'salt-run fileserver.clear_lock svnfs\' will allow updates '
                'to continue for this remote.'
                .format(repo['url'], repo['lockfile'])
            )
            continue
        _, errors = lock(repo)
        if errors:
            log.error('Unable to set update lock for svnfs remote {0}, '
                      'skipping.'.format(repo['url']))
            continue
        log.debug('svnfs is fetching from {0}'.format(repo['url']))
        old_rev = _rev(repo)
        try:
            CLIENT.update(repo['repo'])
        except pysvn._pysvn.ClientError as exc:
            log.error(
                'Error updating svnfs remote {0} (cachedir: {1}): {2}'
                .format(repo['url'], repo['cachedir'], exc)
            )

        new_rev = _rev(repo)
        if any((x is None for x in (old_rev, new_rev))):
            # There were problems getting the revision ID
            continue
        if new_rev != old_rev:
            data['changed'] = True

        clear_lock(repo)

    env_cache = os.path.join(__opts__['cachedir'], 'svnfs/envs.p')
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
        event.fire_event(data, tagify(['svnfs', 'update'], prefix='fileserver'))
    try:
        salt.fileserver.reap_fileserver_cache_dir(
            os.path.join(__opts__['cachedir'], 'svnfs/hash'),
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
        whitelist=__opts__['svnfs_env_whitelist'],
        blacklist=__opts__['svnfs_env_blacklist']
    )


def envs(ignore_cache=False):
    '''
    Return a list of refs that can be used as environments
    '''
    if not ignore_cache:
        env_cache = os.path.join(__opts__['cachedir'], 'svnfs/envs.p')
        cache_match = salt.fileserver.check_env_cache(__opts__, env_cache)
        if cache_match is not None:
            return cache_match
    ret = set()
    for repo in init():
        trunk = os.path.join(repo['repo'], repo['trunk'])
        if os.path.isdir(trunk):
            # Add base as the env for trunk
            ret.add('base')
        else:
            log.error(
                'svnfs trunk path \'{0}\' does not exist in repo {1}, no base '
                'environment will be provided by this remote'
                .format(repo['trunk'], repo['url'])
            )

        branches = os.path.join(repo['repo'], repo['branches'])
        if os.path.isdir(branches):
            ret.update(os.listdir(branches))
        else:
            log.error(
                'svnfs branches path \'{0}\' does not exist in repo {1}'
                .format(repo['branches'], repo['url'])
            )

        tags = os.path.join(repo['repo'], repo['tags'])
        if os.path.isdir(tags):
            ret.update(os.listdir(tags))
        else:
            log.error(
                'svnfs tags path \'{0}\' does not exist in repo {1}'
                .format(repo['tags'], repo['url'])
            )
    return [x for x in sorted(ret) if _env_is_exposed(x)]


def _env_root(repo, saltenv):
    '''
    Return the root of the directory corresponding to the desired environment,
    or None if the environment was not found.
    '''
    # If 'base' is desired, look for the trunk
    if saltenv == 'base':
        trunk = os.path.join(repo['repo'], repo['trunk'])
        if os.path.isdir(trunk):
            return trunk
        else:
            return None

    # Check branches
    branches = os.path.join(repo['repo'], repo['branches'])
    if os.path.isdir(branches) and saltenv in os.listdir(branches):
        return os.path.join(branches, saltenv)

    # Check tags
    tags = os.path.join(repo['repo'], repo['tags'])
    if os.path.isdir(tags) and saltenv in os.listdir(tags):
        return os.path.join(tags, saltenv)

    return None


def find_file(path, tgt_env='base', **kwargs):  # pylint: disable=W0613
    '''
    Find the first file to match the path and ref. This operates similarly to
    the roots file sever but with assumptions of the directory structure
    based on svn standard practices.
    '''
    fnd = {'path': '',
           'rel': ''}
    if os.path.isabs(path) or tgt_env not in envs():
        return fnd

    for repo in init():
        env_root = _env_root(repo, tgt_env)
        if env_root is None:
            # Environment not found, try the next repo
            continue
        if repo['mountpoint'] \
                and not path.startswith(repo['mountpoint'] + os.path.sep):
            continue
        repo_path = path[len(repo['mountpoint']):].lstrip(os.path.sep)
        if repo['root']:
            repo_path = os.path.join(repo['root'], repo_path)

        full = os.path.join(env_root, repo_path)
        if os.path.isfile(full):
            fnd['rel'] = path
            fnd['path'] = full
            return fnd
    return fnd


def serve_file(load, fnd):
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
    if not all(x in load for x in ('path', 'loc', 'saltenv')):
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
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
            )
        load.pop('env')

    if not all(x in load for x in ('path', 'saltenv')):
        return ''
    saltenv = load['saltenv']
    if saltenv == 'base':
        saltenv = 'trunk'
    ret = {}
    relpath = fnd['rel']
    path = fnd['path']

    # If the file doesn't exist, we can't get a hash
    if not path or not os.path.isfile(path):
        return ret

    # Set the hash_type as it is determined by config
    ret['hash_type'] = __opts__['hash_type']

    # Check if the hash is cached
    # Cache file's contents should be "hash:mtime"
    cache_path = os.path.join(__opts__['cachedir'],
                              'svnfs/hash',
                              saltenv,
                              '{0}.hash.{1}'.format(relpath,
                                                    __opts__['hash_type']))
    # If we have a cache, serve that if the mtime hasn't changed
    if os.path.exists(cache_path):
        with salt.utils.fopen(cache_path, 'rb') as fp_:
            hsum, mtime = fp_.read().split(':')
            if os.path.getmtime(path) == mtime:
                # check if mtime changed
                ret['hsum'] = hsum
                return ret

    # if we don't have a cache entry-- lets make one
    ret['hsum'] = salt.utils.get_hash(path, __opts__['hash_type'])
    cache_dir = os.path.dirname(cache_path)
    # make cache directory if it doesn't exist
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    # save the cache object "hash:mtime"
    with salt.utils.fopen(cache_path, 'w') as fp_:
        fp_.write('{0}:{1}'.format(ret['hsum'], os.path.getmtime(path)))

    return ret


def _file_lists(load, form):
    '''
    Return a dict containing the file lists for files, dirs, emtydirs and symlinks
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
            )
        load.pop('env')

    if 'saltenv' not in load or load['saltenv'] not in envs():
        return []

    list_cachedir = os.path.join(__opts__['cachedir'], 'file_lists/svnfs')
    if not os.path.isdir(list_cachedir):
        try:
            os.makedirs(list_cachedir)
        except os.error:
            log.critical('Unable to make cachedir {0}'.format(list_cachedir))
            return []
    list_cache = os.path.join(list_cachedir, '{0}.p'.format(load['saltenv']))
    w_lock = os.path.join(list_cachedir, '.{0}.w'.format(load['saltenv']))
    cache_match, refresh_cache, save_cache = \
        salt.fileserver.check_file_list_cache(
            __opts__, form, list_cache, w_lock
        )
    if cache_match is not None:
        return cache_match
    if refresh_cache:
        ret = {
            'files': set(),
            'dirs': set(),
            'empty_dirs': set()
        }
        for repo in init():
            env_root = _env_root(repo, load['saltenv'])
            if env_root is None:
                # Environment not found, try the next repo
                continue
            if repo['root']:
                env_root = \
                    os.path.join(env_root, repo['root']).rstrip(os.path.sep)
                if not os.path.isdir(env_root):
                    # svnfs root (global or per-remote) does not exist in env
                    continue

            for root, dirs, files in os.walk(env_root):
                relpath = os.path.relpath(root, env_root)
                dir_rel_fn = os.path.join(repo['mountpoint'], relpath)
                if relpath != '.':
                    ret['dirs'].add(dir_rel_fn)
                    if len(dirs) == 0 and len(files) == 0:
                        ret['empty_dirs'].add(dir_rel_fn)
                for fname in files:
                    rel_fn = os.path.relpath(
                                os.path.join(root, fname),
                                env_root
                            )
                    ret['files'].add(os.path.join(repo['mountpoint'], rel_fn))
        if repo['mountpoint']:
            ret['dirs'].add(repo['mountpoint'])
        # Convert all compiled sets to lists
        for key in ret:
            ret[key] = sorted(ret[key])
        if save_cache:
            salt.fileserver.write_file_list_cache(
                __opts__, ret, list_cache, w_lock
            )
        return ret.get(form, [])
    # Shouldn't get here, but if we do, this prevents a TypeError
    return []


def file_list(load):
    '''
    Return a list of all files on the file server in a specified
    environment
    '''
    return _file_lists(load, 'files')


def file_list_emptydirs(load):
    '''
    Return a list of all empty directories on the master
    '''
    return _file_lists(load, 'empty_dirs')


def dir_list(load):
    '''
    Return a list of all directories on the master
    '''
    return _file_lists(load, 'dirs')
