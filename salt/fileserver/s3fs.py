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

    s3.buckets in the salt master config should look like this:

        s3.buckets:
          - bucket1
          - bucket2

    The buckets must contain the directory structure. For example:

        /bucket1/<env>/<files and dirs>

        eg. /bucket1/prod/<files and dirs>
'''

# Import python libs
import os
import hashlib
import time
import pickle
import urllib
import logging

# Import salt libs
import salt.fileserver
import salt.utils
import salt.utils.s3 as s3
import salt.modules

log = logging.getLogger(__name__)

_s3_cache_expire = 30 # cache for 30 seconds
_s3_sync_on_update = True  # sync cache on update rather than jit

def envs():
    '''
    Return a list of directories within the bucket that can be 
    used as environments.
    '''

    resultset = _init()
    return resultset.keys()

def update():
    '''
    Update the cache file for the bucket.
    '''

    _init()

    if _s3_sync_on_update:
        # sync the buckets to the local cache
        # TODO - implement full S3 sync versus JIT file serving
        pass

def find_file(path, env='base', **kwargs):
    '''
    Look through the buckets cache file for a match.
    If the field is found, it is retrieved from S3 only if its cached version
    is missing, or if the MD5 does not match.
    '''

    fnd = {'bucket': None,
            'path' : None}

    resultset = _init()
    if not resultset or env not in resultset:
        return fnd

    ret = _find_files(resultset[env])

    # look for the path including the env, but only return the path if found
    env_path = _get_env_path(env, path)
    for bucket_name, files in ret.iteritems():
        if env_path in files and not salt.fileserver.is_file_ignored(__opts__, env_path):
            fnd['bucket'] = bucket_name
            fnd['path'] = path

    if not fnd['path'] or not fnd['bucket']:
        return fnd

    # check the cache using the env/path
    if _is_cached_file_current(resultset, env, fnd['bucket'], env_path):
        return fnd

    # grab from S3 using the env/path, url encode to cover weird chars
    key, keyid = _get_s3_key()
    s3.query(
            key = key,
            keyid = keyid,
            bucket = fnd['bucket'],
            path = urllib.quote(env_path),
            local_file = _get_cached_file_name(fnd['bucket'], env_path))
    return fnd

def file_hash(load, fnd):
    '''
    Return an MD5 file hash
    '''

    if 'path' not in load or 'env' not in load:
        return ''

    if 'path' not in fnd or 'bucket' not in fnd:
        return ''

    if not fnd['path']:
        return {}

    # get the env/path file from the cache
    env_path = _get_env_path(load['env'], fnd['path'])
    cache_file = _get_cached_file_name(fnd['bucket'], env_path)

    if os.path.isfile(cache_file):
        return {
            'hsum': salt.utils.get_hash(cache_file),
            'hash_type': 'md5',
        }
    else:
        return {}

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

    ret['dest'] = fnd['path']

    gzip = load.get('gzip', None)

    # get the env/path file from the cache
    env_path = _get_env_path(load['env'], fnd['path'])
    cache_file = _get_cached_file_name(fnd['bucket'], env_path)

    with salt.utils.fopen(cache_file, 'rb') as fp_:
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
    env = load['env']

    resultset = _init()

    if not resultset or env not in resultset:
        return ret

    # used to trim the env of the dirs in the map
    env_len = len(load['env']) + 1

    # map and filter the files without the env
    for buckets in _find_files(resultset[env]).values():
        for env_path in buckets:
            if not salt.fileserver.is_file_ignored(__opts__, env_path):
                if env_path[env_len:]:
                    ret.append(env_path[env_len:])

    return ret

def file_list_emptydirs(load):
    '''
    Return a list of all empty directories on the master
    '''
    # TODO - implement this

    ret = []

    _init()

    return ret

def dir_list(load):
    '''
    Return a list of all directories on the master
    '''

    ret = []
    env = load['env']

    resultset = _init()

    if not resultset or env not in resultset:
        return ret

    # used to trim the env of the dirs in the map
    env_len = len(load['env']) + 1

    # map and filter the dirs without the env
    for dirs in _find_files(resultset[env], dirs_only = True).values():
        filtered_dirs = map(lambda dir: dir[env_len:-1], dirs)
        # TODO - filter out the empties
        ret += filter(lambda dir: dir, filtered_dirs)

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

    # check mtime of the buckets files cache 
    if os.path.isfile(cache_file) and os.path.getmtime(cache_file) > time.time() - _s3_cache_expire:
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

def _get_env_path(env, path):
    '''
    Return the path of the file including the environment
    '''

    return os.path.join(env, path)

def _get_cached_file_name(bucket_name, path):
    '''
    Return the cached file name for a bucket path file
    '''

    file_path = os.path.join(_get_cache_dir(), bucket_name, path)

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
    resultset = {}

    if _is_env_per_bucket():
        # Single environment per bucket
        for env, buckets in _get_buckets().items():
            bucket_files = {}
            for bucket_name in buckets:

                bucket_files[bucket_name] = s3.query(
                        key = key,
                        keyid = keyid,
                        bucket = bucket_name,
                        return_bin = False)

            resultset[env] = bucket_files

    else:
        # Multiple environments per buckets
        for bucket_name in _get_buckets():

            s3_meta = s3.query(
                    key = key,
                    keyid = keyid,
                    bucket = bucket_name,
                    return_bin = False)

            # pull out the environment dirs (eg. the root dirs)
            files = filter(lambda key: 'Key' in key, s3_meta)
            envs = set(
                    map(lambda fp: (os.path.dirname(fp['Key']).split('/', 1))[0],
                        files)
                    )

            # pull out the files for the environment
            for env in envs:
                env_files = filter(lambda ef: ef['Key'].startswith(env), files)

                if env not in resultset:
                    resultset[env] = {}

                if bucket_name not in resultset[env]:
                    resultset[env][bucket_name] = []

                resultset[env][bucket_name] += env_files

    # write the resultset to disk
    if os.path.isfile(cache_file):
        os.remove(cache_file)

    log.debug('Writing buckets cache file')

    with salt.utils.fopen(cache_file, 'w') as fp_:
        pickle.dump(resultset, fp_)

    return resultset

def _read_buckets_cache_file(cache_file):
    '''
    Return the contents of the buckets cache file
    '''

    with salt.utils.fopen(cache_file, 'rb') as fp_:
        data = pickle.load(fp_)

    return data

def _is_cached_file_current(resultset, env, bucket_name, path):
    '''
    Check the cache for the named bucket file and check it's md5 hash against
    the file S3 metadata ETag
    '''

    filename = _get_cached_file_name(bucket_name, path)

    if not os.path.isfile(filename):
        return None

    # get the S3 ETag/MD5 for the given file to compare
    res = _find_file_meta(resultset, env, bucket_name, path)
    file_md5 = filter(str.isalnum, res['ETag']) if res else None

    # read cache file and generate its md5 hash
    m = hashlib.md5()
    with salt.utils.fopen(filename, 'rb') as fp_:
        m.update(fp_.read())

    return m.hexdigest() == file_md5

def _find_files(resultset, dirs_only = False):
    '''
    Looks for all the files in the S3 bucket cache metadata
    '''

    ret = {}

    for bucket in resultset.keys():
        ret[bucket] = []

    for bucket, data in resultset.iteritems():
        fileData = filter(lambda key: key.has_key('Key'), data)
        filePaths = map(lambda key: key['Key'], fileData)
        ret[bucket] += filter(lambda key: key.endswith('/') == dirs_only, filePaths)

    return ret

def _find_file_meta(resultset, env, bucket_name, path):
    '''
    Looks for a file's metadata in the S3 bucket cache file
    '''

    env_meta = resultset[env] if env in resultset else {}
    bucket_meta = env_meta[bucket_name] if bucket_name in env_meta else {}
    files_meta = filter(lambda key: key.has_key('Key'), bucket_meta)

    for item_meta in files_meta:
        if 'Key' in item_meta and item_meta['Key'] == path:
            return item_meta

def _get_buckets():
    '''
    Return the configuration buckets
    '''

    return __opts__['s3.buckets'] if 's3.buckets' in __opts__ else {}

def _is_env_per_bucket():
    '''
    Return the configuration mode, either buckets per environment
    eg.
        s3.buckets:
            production:
                - bucket1
                - bucket2
            staging:
                - bucket3
                - bucket4

    or a list of buckets that have environment dirs in their root
    eg.
        s3.buckets:
            - bucket1
            - bucket2
            - bucket3
            - bucket4

    s3://bucket1/production/<files>
    s3://bucket1/staging/<files>
    etc
    '''

    buckets = _get_buckets()
    if isinstance(buckets, dict):
        return True
    elif isinstance(buckets, list):
        return False
    else:
        raise ValueError('Incorrect s3.buckets type given in config')
