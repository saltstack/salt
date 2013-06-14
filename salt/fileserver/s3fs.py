'''
The backend for a fileserver based on Amazon S3 - see
http://docs.saltstack.com/ref/file_server/index.html

This backend exposes directories in S3 buckets as salt environments.  This
feature is managed by the fileserver_backend option in the salt master
config.

:configuration: S3 credentials can be either set in the master file using:

    S3 credentials can be set in the master config file with:

        s3.keyid: GKTADJGHEIQSXMKKRBJ08H
        s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    Alternatively, if on EC2 these credentials can be automatically loaded from
    instance metadata.

    This fileserver supports two modes of operation for the buckets:

    - A single bucket per environment:
    eg.
        s3.buckets:
            production:
                - bucket1
                - bucket2
            staging:
                - bucket3
                - bucket4

    - Or multiple environments per bucket
    eg.
        s3.buckets:
            - bucket1
            - bucket2
            - bucket3
            - bucket4

    A multiple environment bucket must adhere to the following root directory structure:
        s3://<bucket name>/<environment>/<files>
'''

# Import python libs
import os
import hashlib
import time
import pickle
import urllib
import logging

# Import salt libs
import salt.fileserver as fs
import salt.modules
import salt.utils
import salt.utils.s3 as s3

log = logging.getLogger(__name__)

_s3_cache_expire = 30 # cache for 30 seconds
_s3_sync_on_update = True  # sync cache on update rather than jit

def envs():
    '''
    Return a list of directories within the bucket that can be
    used as environments.
    '''

    # update and grab the envs from the metadata keys
    metadata = _init()
    return metadata.keys()

def update():
    '''
    Update the cache file for the bucket.
    '''

    metadata = _init()

    if _s3_sync_on_update:
        key, keyid = _get_s3_key()

        # sync the buckets to the local cache
        log.info('Syncing local cache from S3...')
        for env, env_meta in metadata.iteritems():
            for bucket, files in _find_files(env_meta).iteritems():
                for file_path in files:
                    cached_file_path = _get_cached_file_name(bucket, env, file_path)
                    log.info('{0} - {1} : {2}'.format(bucket, env, file_path))

                    # load the file from S3 if it's not in the cache or it's old
                    _get_file_from_s3(metadata, env, bucket, file_path, cached_file_path)

        log.info('Sync local cache from S3 completed.')

def find_file(path, env='base', **kwargs):
    '''
    Look through the buckets cache file for a match.
    If the field is found, it is retrieved from S3 only if its cached version
    is missing, or if the MD5 does not match.
    '''

    fnd = {'bucket': None,
            'path' : None}

    metadata = _init()
    if not metadata or env not in metadata:
        return fnd

    env_files = _find_files(metadata[env])

    if not _is_env_per_bucket():
        path = os.path.join(env, path)

    # look for the files and check if they're ignored globally
    for bucket_name, files in env_files.iteritems():
        if path in files and not fs.is_file_ignored(__opts__, path):
            fnd['bucket'] = bucket_name
            fnd['path'] = path

    if not fnd['path'] or not fnd['bucket']:
        return fnd

    cached_file_path = _get_cached_file_name(fnd['bucket'], env, path)

    # jit load the file from S3 if it's not in the cache or it's old
    _get_file_from_s3(metadata, env, fnd['bucket'], path, cached_file_path)

    return fnd

def file_hash(load, fnd):
    '''
    Return an MD5 file hash
    '''

    ret = {}

    if 'env' not in load:
        return ret

    if 'path' not in fnd or 'bucket' not in fnd or not fnd['path']:
        return ret

    cached_file_path = _get_cached_file_name(
            fnd['bucket'],
            load['env'],
            fnd['path'])

    if os.path.isfile(cached_file_path):
        ret['hsum'] = salt.utils.get_hash(cached_file_path)
        ret['hash_type'] = 'md5'

    return ret

def serve_file(load, fnd):
    '''
    Return a chunk from a file based on the data received
    '''

    ret = {'data': '',
           'dest': ''}

    if 'path' not in load or 'loc' not in load or 'env' not in load:
        return ret

    if 'path' not in fnd or 'bucket' not in fnd:
        return ret

    gzip = load.get('gzip', None)

    # get the env/path file from the cache
    cached_file_path = _get_cached_file_name(
            fnd['bucket'],
            load['env'],
            fnd['path'])

    ret['dest'] = fnd['path']

    with salt.utils.fopen(cached_file_path, 'rb') as fp_:
        fp_.seek(load['loc'])
        data = fp_.read(__opts__['file_buffer_size'])
        if gzip and data:
            data = salt.utils.gzip_util.compress(data, gzip)
            ret['gzip'] = gzip
        ret['data'] = data
    return ret

def file_list(load):
    '''
    Return a list of all files on the file server in a specified environment
    '''

    ret = []

    if 'env' not in load:
        return ret

    env = load['env']
    metadata = _init()

    if not metadata or env not in metadata:
        return ret

    for buckets in _find_files(metadata[env]).values():
        files = filter(lambda f: not fs.is_file_ignored(__opts__, f), buckets)
        ret += _trim_env_off_path(files, env)

    return ret

def file_list_emptydirs(load):
    '''
    Return a list of all empty directories on the master
    '''
    # TODO - implement this
    _init()

    return []

def dir_list(load):
    '''
    Return a list of all directories on the master
    '''

    ret = []

    if 'env' not in load:
        return ret

    env = load['env']
    metadata = _init()

    if not metadata or env not in metadata:
        return ret

    # grab all the dirs from the buckets cache file
    for dirs in _find_files(metadata[env], dirs_only=True).values():
        # trim env and trailing slash
        dirs = _trim_env_off_path(dirs, env, trim_slash=True)
        # remove empty string left by the base env dir in single bucket mode
        ret += filter(None, dirs)

    return ret

def _get_s3_key():
    '''
    Get AWS keys from pillar or config
    '''

    key = __opts__['s3.key'] if 's3.key' in __opts__ else None
    keyid = __opts__['s3.keyid'] if 's3.keyid' in __opts__ else None

    return key, keyid

def _init():
    '''
    Connect to S3 and download the metadata for each file in all buckets
    specified and cache the data to disk.
    '''

    cache_file = _get_buckets_cache_filename()
    exp = time.time() - _s3_cache_expire

    # check mtime of the buckets files cache
    if os.path.isfile(cache_file) and os.path.getmtime(cache_file) > exp:
        return _read_buckets_cache_file(cache_file)
    else:
        # bucket files cache expired
        return _refresh_buckets_cache_file(cache_file)

def _get_cache_dir():
    '''
    Return the path to the s3cache dir
    '''

    # Or is that making too many assumptions?
    return os.path.join(__opts__['cachedir'], 's3cache')

def _get_cached_file_name(bucket_name, env, path):
    '''
    Return the cached file name for a bucket path file
    '''

    file_path = os.path.join(_get_cache_dir(), env, bucket_name, path)

    # make sure bucket and env directories exist
    if not os.path.exists(os.path.dirname(file_path)):
        os.makedirs(os.path.dirname(file_path))

    return file_path

def _get_buckets_cache_filename():
    '''
    Return the filename of the cache for bucket contents.
    Create the path if it does not exist.
    '''

    cache_dir = _get_cache_dir()
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    return os.path.join(cache_dir, 'buckets_files.cache')

def _refresh_buckets_cache_file(cache_file):
    '''
    Retrieve the content of all buckets and cache the metadata to the buckets
    cache file
    '''

    log.debug('Refreshing buckets cache file')

    key, keyid = _get_s3_key()
    metadata = {}

    # helper s3 query fuction
    def __get_s3_meta(bucket, key=key, keyid=keyid):
        return s3.query(
                key=key,
                keyid=keyid,
                bucket=bucket,
                return_bin=False)

    if _is_env_per_bucket():
        # Single environment per bucket
        for env, buckets in _get_buckets().items():
            bucket_files = {}
            for bucket_name in buckets:
                s3_meta = __get_s3_meta(bucket_name)

                # s3 query returned nothing
                if not s3_meta:
                    continue

                # grab only the files/dirs
                bucket_files[bucket_name] = filter(lambda k: 'Key' in k, s3_meta)

            metadata[env] = bucket_files

    else:
        # Multiple environments per buckets
        for bucket_name in _get_buckets():
            s3_meta = __get_s3_meta(bucket_name)

            # s3 query returned nothing
            if not s3_meta:
                continue

            # pull out the environment dirs (eg. the root dirs)
            files = filter(lambda k: 'Key' in k, s3_meta)
            envs = map(lambda k: (os.path.dirname(k['Key']).split('/', 1))[0], files)
            envs = set(envs)

            # pull out the files for the environment
            for env in envs:
                # grab only files/dirs that match this env
                env_files = filter(lambda k: k['Key'].startswith(env), files)

                if env not in metadata:
                    metadata[env] = {}

                if bucket_name not in metadata[env]:
                    metadata[env][bucket_name] = []

                metadata[env][bucket_name] += env_files

    # write the metadata to disk
    if os.path.isfile(cache_file):
        os.remove(cache_file)

    log.debug('Writing buckets cache file')

    with salt.utils.fopen(cache_file, 'w') as fp_:
        pickle.dump(metadata, fp_)

    return metadata

def _read_buckets_cache_file(cache_file):
    '''
    Return the contents of the buckets cache file
    '''

    log.debug('Reading buckets cache file')

    with salt.utils.fopen(cache_file, 'rb') as fp_:
        data = pickle.load(fp_)

    return data

def _find_files(metadata, dirs_only=False):
    '''
    Looks for all the files in the S3 bucket cache metadata
    '''

    ret = {}

    for bucket_name, data in metadata.iteritems():
        if bucket_name not in ret:
            ret[bucket_name] = []

        # grab the paths from the metadata
        filePaths = map(lambda k: k['Key'], data)
        # filter out the files or the dirs depending on flag
        ret[bucket_name] += filter(lambda k: k.endswith('/') == dirs_only, filePaths)

    return ret

def _find_file_meta(metadata, bucket_name, env, path):
    '''
    Looks for a file's metadata in the S3 bucket cache file
    '''

    env_meta = metadata[env] if env in metadata else {}
    bucket_meta = env_meta[bucket_name] if bucket_name in env_meta else {}
    files_meta = filter((lambda k: 'Key' in k), bucket_meta)

    for item_meta in files_meta:
        if 'Key' in item_meta and item_meta['Key'] == path:
            return item_meta

def _get_buckets():
    '''
    Return the configuration buckets
    '''

    return __opts__['s3.buckets'] if 's3.buckets' in __opts__ else {}

def _get_file_from_s3(metadata, env, bucket_name, path, cached_file_path):
    '''
    Checks the local cache for the file, if it's old or missing go grab the
    file from S3 and update the cache
    '''

    # check the local cache...
    if os.path.isfile(cached_file_path):
        file_meta = _find_file_meta(metadata, bucket_name, env, path)
        file_md5 = filter(str.isalnum, file_meta['ETag']) if file_meta else None

        cached_file_hash = hashlib.md5()
        with salt.utils.fopen(cached_file_path, 'rb') as fp_:
            cached_file_hash.update(fp_.read())

        # hashes match we have a cache hit
        if cached_file_hash.hexdigest() == file_md5:
            return

    # ... or get the file from S3
    key, keyid = _get_s3_key()
    s3.query(
            key=key,
            keyid=keyid,
            bucket=bucket_name,
            path=urllib.quote(path),
            local_file=cached_file_path)

def _trim_env_off_path(paths, env, trim_slash=False):
    '''
    Return a list of file paths with the env directory removed
    '''
    env_len = None if _is_env_per_bucket() else len(env) + 1
    slash_len = -1 if trim_slash else None

    return map(lambda d: d[env_len:slash_len], paths)

def _is_env_per_bucket():
    '''
    Return the configuration mode, either buckets per environment or a list of
    buckets that have environment dirs in their root
    '''

    buckets = _get_buckets()
    if isinstance(buckets, dict):
        return True
    elif isinstance(buckets, list):
        return False
    else:
        raise ValueError('Incorrect s3.buckets type given in config')
