# -*- coding: utf-8 -*-
'''
The backed for the mercurial based file server system.

After enabling this backend, branches, bookmarks, and tags in a remote
mercurial repository are exposed to salt as different environments. This
feature is managed by the fileserver_backend option in the salt master config.

This fileserver has an additional option ``hgfs_branch_method`` that will set
the desired branch method. Possible values are: ``branches``, ``bookmarks``, or
``mixed``. If using ``branches`` or ``mixed``, the ``default`` branch will be
mapped to ``base``.

:depends:   - mercurial
'''

# Import python libs
import os
import glob
import time
import shutil
import hashlib
import logging

# Import third party libs
HAS_HG = False
try:
    import hglib
    HAS_HG = True
except ImportError:
    pass

# Import salt libs
import salt.utils
import salt.fileserver
from salt.utils.event import tagify

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'hg'


def __virtual__():
    '''
    Only load if mercurial is available
    '''
    if not isinstance(__opts__['hgfs_remotes'], list):
        log.error('Mercurial fileserver backend is enabled in configuration '
                  'but could not be loaded. Did you specify `hgfs_remotes` as a list? It is required.')
        return False
    if not isinstance(__opts__['hgfs_root'], str):
        log.error('Mercurial fileserver backend is enabled in configuration '
                  'but could not be loaded. Did you specify `hgfs_root` as a string? It is required.')
        return False
    if not isinstance(__opts__['hgfs_branch_method'], str):
        log.error('Mercurial fileserver backend is enabled in configuration'
                  'but could not be loaded. Did you specify `hgfs_branch_method` as a string? It is required')
        return False
    if not 'hg' in __opts__['fileserver_backend']:
        return False
    if not HAS_HG:
        log.error('Mercurial fileserver backend is enabled in configuration '
                  'but could not be loaded, is hglib installed?')
        return False
    return __virtualname__


def _get_ref(repo, name):
    '''
    Return ref tuple if ref is in the repo
    '''
    for ref in repo.branches():
        if name == ref[0]:
            return ref
    for ref in repo.tags():
        if name == ref[0]:
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


def init():
    '''
    Return the hg repo object for this session
    '''
    bp_ = os.path.join(__opts__['cachedir'], 'hgfs')
    repos = []
    for _, opt in enumerate(__opts__['hgfs_remotes']):
        repo_hash = hashlib.md5(opt).hexdigest()
        rp_ = os.path.join(bp_, repo_hash)
        if not os.path.isdir(rp_):
            os.makedirs(rp_)
            hglib.init(rp_)
        repo = hglib.open(rp_)
        refs = repo.config(names='paths')
        if not refs:
            hgconfpath = os.path.join(rp_, '.hg', 'hgrc')
            with salt.utils.fopen(hgconfpath, 'w+') as hgconfig:
                hgconfig.write('[paths]\n')
                hgconfig.write('default = {0}\n'.format(opt))
        repos.append(repo)
        repo.close()

    return repos


def purge_cache():
    bp_ = os.path.join(__opts__['cachedir'], 'hgfs')
    try:
        remove_dirs = os.listdir(bp_)
    except OSError:
        remove_dirs = []
    for _, opt in enumerate(__opts__['hgfs_remotes']):
        repo_hash = hashlib.md5(opt).hexdigest()
        try:
            remove_dirs.remove(repo_hash)
        except ValueError:
            pass
    remove_dirs = [os.path.join(bp_, r) for r in remove_dirs if r not in ('hash', 'refs')]
    if remove_dirs:
        for r in remove_dirs:
            shutil.rmtree(r)
        return True
    return False


def update():
    '''
    Execute a hg pull on all of the repos
    '''
    # data for the fileserver event
    data = {'changed': False,
            'backend': 'hgfs'}
    pid = os.getpid()
    data['changed'] = purge_cache()
    repos = init()
    for repo in repos:
        repo.open()
        lk_fn = os.path.join(repo.root(), 'update.lk')
        with salt.utils.fopen(lk_fn, 'w+') as fp_:
            fp_.write(str(pid))
        curtip = repo.tip()
        if repo.pull():
            newtip = repo.tip()
            if curtip[1] != newtip[1]:
                data['changed'] = True
        else:
            log.warning('Failed to pull changes to repo: '
                        '{0}'.format(repo.root()))
        repo.close()
        try:
            os.remove(lk_fn)
        except (OSError, IOError):
            pass

    # if there is a change, fire an event
    if __opts__.get('fileserver_events', False):
        event = salt.utils.event.MasterEvent(__opts__['sock_dir'])
        event.fire_event(data, tagify(['hgfs', 'update'], prefix='fileserver'))
    try:
        salt.fileserver.reap_fileserver_cache_dir(
            os.path.join(__opts__['cachedir'], 'hgfs/hash'),
            find_file
        )
    except (IOError, OSError):
        # Hash file won't exist if no files have yet been served up
        pass


def envs():
    '''
    Return a list of refs that can be used as environments
    '''
    ret = set()
    repos = init()
    for repo in repos:
        repo.open()
        if __opts__['hgfs_branch_method'] != 'bookmarks':
            branches = repo.branches()
            for branch in branches:
                branch_name = branch[0]
                if branch_name == 'default':
                    branch_name = 'base'
                ret.add(branch_name)
        if __opts__['hgfs_branch_method'] != 'branches':
            bookmarks = repo.bookmarks()
            for bookmark in bookmarks:
                bookmark_name = bookmark[0]
                ret.add(bookmark_name)
        tags = repo.tags()
        for tag in tags:
            tag_name = tag[0]
            # Avoid adding the special 'tip' tag as an env.
            if tag_name != 'tip':
                ret.add(tag_name)
        repo.close()
    return list(ret)


def find_file(path, short='base', **kwargs):
    '''
    Find the first file to match the path and ref, read the file out of hg
    and send the path to the newly cached file
    '''
    fnd = {'path': '',
           'rel': ''}
    if os.path.isabs(path):
        return fnd

    local_path = path
    path = os.path.join(__opts__['hgfs_root'], local_path)

    if __opts__['hgfs_branch_method'] != 'bookmarks' and short == 'base':
        short = 'default'
    dest = os.path.join(__opts__['cachedir'], 'hgfs/refs', short, path)
    hashes_glob = os.path.join(__opts__['cachedir'],
                               'hgfs/hash',
                               short,
                               '{0}.hash.*'.format(path))
    blobshadest = os.path.join(__opts__['cachedir'],
                               'hgfs/hash',
                               short,
                               '{0}.hash.blob_sha1'.format(path))
    lk_fn = os.path.join(__opts__['cachedir'],
                         'hgfs/hash',
                         short,
                         '{0}.lk'.format(path))
    destdir = os.path.dirname(dest)
    hashdir = os.path.dirname(blobshadest)
    if not os.path.isdir(destdir):
        os.makedirs(destdir)
    if not os.path.isdir(hashdir):
        os.makedirs(hashdir)
    repos = init()
    if 'index' in kwargs:
        try:
            repos = [repos[int(kwargs['index'])]]
        except IndexError:
            # Invalid index param
            return fnd
        except ValueError:
            # Invalid index option
            return fnd
    for repo in repos:
        repo.open()
        ref = _get_ref(repo, short)
        if not ref:
            # Branch or tag not found in repo, try the next
            repo.close()
            continue
        _wait_lock(lk_fn, dest)
        if os.path.isfile(blobshadest) and os.path.isfile(dest):
            with salt.utils.fopen(blobshadest, 'r') as fp_:
                sha = fp_.read()
                if sha == ref[2]:
                    fnd['rel'] = local_path
                    fnd['path'] = dest
                    repo.close()
                    return fnd
        try:
            repo.cat(['path:{0}'.format(path)], rev=ref[2], output=dest)
        except hglib.error.CommandError:
            repo.close()
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
        fnd['rel'] = local_path
        fnd['path'] = dest
        repo.close()
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
    if 'path' not in load or 'loc' not in load or 'saltenv' not in load:
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

    if 'path' not in load or 'saltenv' not in load:
        return ''
    ret = {'hash_type': __opts__['hash_type']}
    short = load['saltenv']
    if __opts__['hgfs_branch_method'] != 'bookmarks' and short == 'base':
        short = 'default'
    relpath = fnd['rel']
    path = fnd['path']
    hashdest = os.path.join(__opts__['cachedir'],
                            'hgfs/hash',
                            short,
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


def file_list(load):
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

    ret = []
    if 'saltenv' not in load:
        return ret
    if __opts__['hgfs_branch_method'] != 'bookmarks' and \
            load['saltenv'] == 'base':
        load['saltenv'] = 'default'
    repos = init()
    for repo in repos:
        repo.open()
        ref = _get_ref(repo, load['saltenv'])
        if ref:
            manifest = repo.manifest(rev=ref[1])
            for tup in manifest:
                ret.append(os.path.relpath(tup[4], __opts__['hgfs_root']))
        repo.close()
    return ret


def file_list_emptydirs(load):
    '''
    Return a list of all empty directories on the master
    '''
    # Cannot have empty dirs in hg
    return []


def dir_list(load):
    '''
    Return a list of all directories on the master
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    ret = set()
    if 'saltenv' not in load:
        return ret
    if __opts__['hgfs_branch_method'] != 'bookmarks' and \
            load['saltenv'] == 'base':
        load['saltenv'] = 'default'
    repos = init()
    for repo in repos:
        repo.open()
        ref = _get_ref(repo, load['saltenv'])
        if ref:
            manifest = repo.manifest(rev=ref[1])
            for tup in manifest:
                filepath = tup[4]
                split = filepath.rsplit('/', 1)
                while len(split) > 1:
                    ret.add(os.path.relpath(split[0], __opts__['hgfs_root']))
                    split = split[0].rsplit('/', 1)
        repo.close()
    return list(ret)
