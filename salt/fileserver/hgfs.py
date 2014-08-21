# -*- coding: utf-8 -*-
'''
Mercurial Fileserver Backend

To enable, add ``hg`` to the :conf_master:`fileserver_backend` option in the
master config file.

After enabling this backend, branches, bookmarks, and tags in a remote
mercurial repository are exposed to salt as different environments. This
feature is managed by the :conf_master:`fileserver_backend` option in the salt
master config file.

This fileserver has an additional option :conf_master:`hgfs_branch_method` that
will set the desired branch method. Possible values are: ``branches``,
``bookmarks``, or ``mixed``. If using ``branches`` or ``mixed``, the
``default`` branch will be mapped to ``base``.


.. versionchanged:: 2014.1.0
    The :conf_master:`hgfs_base` master config parameter was added, allowing
    for a branch other than ``default`` to be used for the ``base``
    environment, and allowing for a ``base`` environment to be specified when
    using an :conf_master:`hgfs_branch_method` of ``bookmarks``.


:depends:   - mercurial
            - python bindings for mercurial (``python-hglib``)
'''

# Import python libs
import copy
import glob
import hashlib
import logging
import os
import shutil
from datetime import datetime

VALID_BRANCH_METHODS = ('branches', 'bookmarks', 'mixed')
PER_REMOTE_PARAMS = ('base', 'branch_method', 'mountpoint', 'root')

# Import third party libs
try:
    import hglib
    HAS_HG = True
except ImportError:
    HAS_HG = False

# Import salt libs
import salt.utils
import salt.fileserver
from salt._compat import string_types
from salt.utils.event import tagify

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'hg'


def __virtual__():
    '''
    Only load if mercurial is available
    '''
    if __virtualname__ not in __opts__['fileserver_backend']:
        return False
    if not HAS_HG:
        log.error('Mercurial fileserver backend is enabled in configuration '
                  'but could not be loaded, is hglib installed?')
        return False
    if __opts__['hgfs_branch_method'] not in VALID_BRANCH_METHODS:
        log.error(
            'Invalid hgfs_branch_method {0!r}. Valid methods are: {1}'
            .format(__opts__['hgfs_branch_method'], VALID_BRANCH_METHODS)
        )
        return False
    return __virtualname__


def _all_branches(repo):
    '''
    Returns all branches for the specified repo
    '''
    # repo.branches() returns a list of 3-tuples consisting of
    # (branch name, rev #, nodeid)
    # Example: [('default', 4, '7c96229269fa')]
    return repo.branches()


def _get_branch(repo, name):
    '''
    Find the requested branch in the specified repo
    '''
    try:
        return [x for x in _all_branches(repo) if x[0] == name][0]
    except IndexError:
        return False


def _all_bookmarks(repo):
    '''
    Returns all bookmarks for the specified repo
    '''
    # repo.bookmarks() returns a tuple containing the following:
    #   1. A list of 3-tuples consisting of (bookmark name, rev #, nodeid)
    #   2. The index of the current bookmark (-1 if no current one)
    # Example: ([('mymark', 4, '7c96229269fa')], -1)
    return repo.bookmarks()[0]


def _get_bookmark(repo, name):
    '''
    Find the requested bookmark in the specified repo
    '''
    try:
        return [x for x in _all_bookmarks(repo) if x[0] == name][0]
    except IndexError:
        return False


def _all_tags(repo):
    '''
    Returns all tags for the specified repo
    '''
    # repo.tags() returns a list of 4-tuples consisting of
    # (tag name, rev #, nodeid, islocal)
    # Example: [('1.0', 3, '3be15e71b31a', False),
    #           ('tip', 4, '7c96229269fa', False)]
    # Avoid returning the special 'tip' tag.
    return [x for x in repo.tags() if x[0] != 'tip']


def _get_tag(repo, name):
    '''
    Find the requested tag in the specified repo
    '''
    try:
        return [x for x in _all_tags(repo) if x[0] == name][0]
    except IndexError:
        return False


def _get_ref(repo, name):
    '''
    Return ref tuple if ref is in the repo.
    '''
    if name == 'base':
        name = repo['base']
    if name == repo['base'] or name in envs():
        if repo['branch_method'] == 'branches':
            return _get_branch(repo['repo'], name) \
                or _get_tag(repo['repo'], name)
        elif repo['branch_method'] == 'bookmarks':
            return _get_bookmark(repo['repo'], name) \
                or _get_tag(repo['repo'], name)
        elif repo['branch_method'] == 'mixed':
            return _get_branch(repo['repo'], name) \
                or _get_bookmark(repo['repo'], name) \
                or _get_tag(repo['repo'], name)
    return False


def init():
    '''
    Return a list of hglib objects for the various hgfs remotes
    '''
    bp_ = os.path.join(__opts__['cachedir'], 'hgfs')
    new_remote = False
    repos = []

    per_remote_defaults = {}
    for param in PER_REMOTE_PARAMS:
        per_remote_defaults[param] = __opts__['hgfs_{0}'.format(param)]

    for remote in __opts__['hgfs_remotes']:
        repo_conf = copy.deepcopy(per_remote_defaults)
        if isinstance(remote, dict):
            repo_uri = next(iter(remote))
            per_remote_conf = salt.utils.repack_dictlist(remote[repo_uri])
            if not per_remote_conf:
                log.error(
                    'Invalid per-remote configuration for remote {0}. If no '
                    'per-remote parameters are being specified, there may be '
                    'a trailing colon after the URI, which should be removed. '
                    'Check the master configuration file.'.format(repo_uri)
                )

            branch_method = \
                per_remote_conf.get('branch_method',
                                    per_remote_defaults['branch_method'])
            if branch_method not in VALID_BRANCH_METHODS:
                log.error(
                    'Invalid branch_method {0!r} for remote {1}. Valid '
                    'branch methods are: {2}. This remote will be ignored.'
                    .format(branch_method, repo_uri,
                            ', '.join(VALID_BRANCH_METHODS))
                )
                continue

            for param in (x for x in per_remote_conf
                          if x not in PER_REMOTE_PARAMS):
                log.error(
                    'Invalid configuration parameter {0!r} for remote {1}. '
                    'Valid parameters are: {2}. See the documentation for '
                    'further information.'.format(
                        param, repo_uri, ', '.join(PER_REMOTE_PARAMS)
                    )
                )
                per_remote_conf.pop(param)
            repo_conf.update(per_remote_conf)
        else:
            repo_uri = remote

        if not isinstance(repo_uri, string_types):
            log.error(
                'Invalid gitfs remote {0}. Remotes must be strings, you may '
                'need to enclose the URI in quotes'.format(repo_uri)
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
        repo_hash = hash_type(repo_uri).hexdigest()
        rp_ = os.path.join(bp_, repo_hash)
        if not os.path.isdir(rp_):
            os.makedirs(rp_)

        if not os.listdir(rp_):
            # Only init if the directory is empty.
            hglib.init(rp_)
            new_remote = True
        try:
            repo = hglib.open(rp_)
        except hglib.error.ServerError:
            log.error(
                'Cache path {0} (corresponding remote: {1}) exists but is not '
                'a valid mercurial repository. You will need to manually '
                'delete this directory on the master to continue to use this '
                'hgfs remote.'.format(rp_, repo_uri)
            )
            continue

        refs = repo.config(names='paths')
        if not refs:
            # Write an hgrc defining the remote URI
            hgconfpath = os.path.join(rp_, '.hg', 'hgrc')
            with salt.utils.fopen(hgconfpath, 'w+') as hgconfig:
                hgconfig.write('[paths]\n')
                hgconfig.write('default = {0}\n'.format(repo_uri))

        repo_conf.update({
            'repo': repo,
            'uri': repo_uri,
            'hash': repo_hash,
            'cachedir': rp_
        })
        repos.append(repo_conf)
        repo.close()

    if new_remote:
        remote_map = os.path.join(__opts__['cachedir'], 'hgfs/remote_map.txt')
        try:
            with salt.utils.fopen(remote_map, 'w+') as fp_:
                timestamp = datetime.now().strftime('%d %b %Y %H:%M:%S.%f')
                fp_.write('# hgfs_remote map as of {0}\n'.format(timestamp))
                for repo in repos:
                    fp_.write('{0} = {1}\n'.format(repo['hash'], repo['uri']))
        except OSError:
            pass
        else:
            log.info('Wrote new hgfs_remote map to {0}'.format(remote_map))

    return repos


def purge_cache():
    '''
    Purge the fileserver cache
    '''
    bp_ = os.path.join(__opts__['cachedir'], 'hgfs')
    try:
        remove_dirs = os.listdir(bp_)
    except OSError:
        remove_dirs = []
    for repo in init():
        try:
            remove_dirs.remove(repo['hash'])
        except ValueError:
            pass
    remove_dirs = [os.path.join(bp_, rdir) for rdir in remove_dirs
                   if rdir not in ('hash', 'refs', 'envs.p', 'remote_map.txt')]
    if remove_dirs:
        for rdir in remove_dirs:
            shutil.rmtree(rdir)
        return True
    return False


def update():
    '''
    Execute an hg pull on all of the repos
    '''
    # data for the fileserver event
    data = {'changed': False,
            'backend': 'hgfs'}
    pid = os.getpid()
    data['changed'] = purge_cache()
    for repo in init():
        repo['repo'].open()
        lk_fn = os.path.join(repo['repo'].root(), 'update.lk')
        with salt.utils.fopen(lk_fn, 'w+') as fp_:
            fp_.write(str(pid))
        curtip = repo['repo'].tip()
        try:
            repo['repo'].pull()
        except Exception as exc:
            log.error(
                'Exception {0} caught while updating hgfs remote {1}'
                .format(exc, repo['uri']),
                exc_info_on_loglevel=logging.DEBUG
            )
        else:
            newtip = repo['repo'].tip()
            if curtip[1] != newtip[1]:
                data['changed'] = True
        repo['repo'].close()
        try:
            os.remove(lk_fn)
        except (IOError, OSError):
            pass

    env_cache = os.path.join(__opts__['cachedir'], 'hgfs/envs.p')
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
                listen=False)
        event.fire_event(data, tagify(['hgfs', 'update'], prefix='fileserver'))
    try:
        salt.fileserver.reap_fileserver_cache_dir(
            os.path.join(__opts__['cachedir'], 'hgfs/hash'),
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
        whitelist=__opts__['hgfs_env_whitelist'],
        blacklist=__opts__['hgfs_env_blacklist']
    )


def envs(ignore_cache=False):
    '''
    Return a list of refs that can be used as environments
    '''
    if not ignore_cache:
        env_cache = os.path.join(__opts__['cachedir'], 'hgfs/envs.p')
        cache_match = salt.fileserver.check_env_cache(__opts__, env_cache)
        if cache_match is not None:
            return cache_match
    ret = set()
    for repo in init():
        repo['repo'].open()
        if repo['branch_method'] in ('branches', 'mixed'):
            for branch in _all_branches(repo['repo']):
                branch_name = branch[0]
                if branch_name == repo['base']:
                    branch_name = 'base'
                ret.add(branch_name)
        if repo['branch_method'] in ('bookmarks', 'mixed'):
            for bookmark in _all_bookmarks(repo['repo']):
                bookmark_name = bookmark[0]
                if bookmark_name == repo['base']:
                    bookmark_name = 'base'
                ret.add(bookmark_name)
        ret.update([x[0] for x in _all_tags(repo['repo'])])
        repo['repo'].close()
    return [x for x in sorted(ret) if _env_is_exposed(x)]


def find_file(path, tgt_env='base', **kwargs):  # pylint: disable=W0613
    '''
    Find the first file to match the path and ref, read the file out of hg
    and send the path to the newly cached file
    '''
    fnd = {'path': '',
           'rel': ''}
    if os.path.isabs(path) or tgt_env not in envs():
        return fnd

    dest = os.path.join(__opts__['cachedir'], 'hgfs/refs', tgt_env, path)
    hashes_glob = os.path.join(__opts__['cachedir'],
                               'hgfs/hash',
                               tgt_env,
                               '{0}.hash.*'.format(path))
    blobshadest = os.path.join(__opts__['cachedir'],
                               'hgfs/hash',
                               tgt_env,
                               '{0}.hash.blob_sha1'.format(path))
    lk_fn = os.path.join(__opts__['cachedir'],
                         'hgfs/hash',
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

        repo['repo'].open()
        ref = _get_ref(repo, tgt_env)
        if not ref:
            # Branch or tag not found in repo, try the next
            repo['repo'].close()
            continue
        salt.fileserver.wait_lock(lk_fn, dest)
        if os.path.isfile(blobshadest) and os.path.isfile(dest):
            with salt.utils.fopen(blobshadest, 'r') as fp_:
                sha = fp_.read()
                if sha == ref[2]:
                    fnd['rel'] = path
                    fnd['path'] = dest
                    repo['repo'].close()
                    return fnd
        try:
            repo['repo'].cat(
                ['path:{0}'.format(repo_path)], rev=ref[2], output=dest
            )
        except hglib.error.CommandError:
            repo['repo'].close()
            continue
        with salt.utils.fopen(lk_fn, 'w+') as fp_:
            fp_.write('')
        for filename in glob.glob(hashes_glob):
            try:
                os.remove(filename)
            except Exception:
                pass
        with salt.utils.fopen(blobshadest, 'w+') as fp_:
            fp_.write(ref[2])
        try:
            os.remove(lk_fn)
        except (OSError, IOError):
            pass
        fnd['rel'] = path
        fnd['path'] = dest
        repo['repo'].close()
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
                            'hgfs/hash',
                            load['saltenv'],
                            '{0}.hash.{1}'.format(relpath,
                                                  __opts__['hash_type']))
    if not os.path.isfile(hashdest):
        with salt.utils.fopen(path, 'rb') as fp_:
            ret['hsum'] = getattr(hashlib, __opts__['hash_type'])(
                fp_.read()).hexdigest()
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

    list_cachedir = os.path.join(__opts__['cachedir'], 'file_lists/hgfs')
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
        ret = {}
        ret['files'] = _get_file_list(load)
        ret['dirs'] = _get_dir_list(load)
        if save_cache:
            salt.fileserver.write_file_list_cache(
                __opts__, ret, list_cache, w_lock
            )
        return ret.get(form, [])
    # Shouldn't get here, but if we do, this prevents a TypeError
    return []


def file_list(load):
    '''
    Return a list of all files on the file server in a specified environment
    '''
    return _file_lists(load, 'files')


def _get_file_list(load):
    '''
    Get a list of all files on the file server in a specified environment
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    if 'saltenv' not in load or load['saltenv'] not in envs():
        return []
    ret = set()
    for repo in init():
        repo['repo'].open()
        ref = _get_ref(repo, load['saltenv'])
        if ref:
            manifest = repo['repo'].manifest(rev=ref[1])
            for tup in manifest:
                relpath = os.path.relpath(tup[4], repo['root'])
                # Don't add files outside the hgfs_root
                if not relpath.startswith('../'):
                    ret.add(os.path.join(repo['mountpoint'], relpath))
        repo['repo'].close()
    return sorted(ret)


def file_list_emptydirs(load):  # pylint: disable=W0613
    '''
    Return a list of all empty directories on the master
    '''
    # Cannot have empty dirs in hg
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

    if 'saltenv' not in load or load['saltenv'] not in envs():
        return []
    ret = set()
    for repo in init():
        repo['repo'].open()
        ref = _get_ref(repo, load['saltenv'])
        if ref:
            manifest = repo['repo'].manifest(rev=ref[1])
            for tup in manifest:
                filepath = tup[4]
                split = filepath.rsplit('/', 1)
                while len(split) > 1:
                    relpath = os.path.relpath(split[0], repo['root'])
                    # Don't add '.'
                    if relpath != '.':
                        # Don't add files outside the hgfs_root
                        if not relpath.startswith('../'):
                            ret.add(os.path.join(repo['mountpoint'], relpath))
                    split = split[0].rsplit('/', 1)
        repo['repo'].close()
    return sorted(ret)
