'''
The backend for the s3 based file server system.

:configuration: S3 credentials can be either set in the master file using:

        s3.keyid: GKTADJGHEIQSXMKKRBJ08H
        s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    If on EC2 these credentials can be automatically loaded from the
    instance metadata

    Example configuration options in master file:

    s3.buckets:
      env:
        - bucket1
        - bucket2
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

_s3_cache_expire = 300 # cache for 5 minutes

def envs():
    '''
    Return the file server environments listed for the buckets
    '''
    _init()
    return _get_buckets().keys()

def update():
    '''
    Update the buckets cache file
    '''
    _init()

def find_file(path, env='base', **kwargs):
    '''
    Looks through the buckets cache file for a match. If it's found the file
    will be retrieved from S3 only if it's cached version is missing or the md5
    hash doesn't match
    '''
    fnd = {'bucket': None,
            'path' : None}

    env_path = _get_env_path(env, path)

    resultset = _init()
    if not resultset or env not in resultset:
        return fnd

    ret = _find_files(resultset[env])

    for bucket_name, files in ret.iteritems():
        if env_path in files:
            fnd['bucket'] = bucket_name
            fnd['path'] = env_path

    if not fnd['path'] or not fnd['bucket']:
            return fnd

    if _is_cached_file_current(resultset, env, fnd['bucket'], fnd['path']):
        return fnd

    key, keyid = _get_s3_key()
    s3.query(
            key = key,
            keyid = keyid,
            bucket = fnd['bucket'],
            path = urllib.quote(fnd['path']),
            local_file = _get_cached_file_name(fnd['bucket'], fnd['path']))
    return fnd

def file_hash(load, fnd):
    '''
    Return a file hash, the hash type is always md5
    '''
    if 'path' not in load or 'env' not in load:
        return ''

    if 'path' not in fnd or 'bucket' not in fnd:
        return ''

    ret = {}
    cache_file = _get_cached_file_name(fnd['bucket'], fnd['path'])

    if os.path.isfile(cache_file):
        ret['hsum'] = salt.utils.get_hash(cache_file)
        ret['hash_type'] = 'md5' # always md5 due to ETags in S3
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

    env_len = len(load['env']) + 1 # strip off the env from the path
    ret['dest'] = fnd['path'][env_len:]

    gzip = load.get('gzip', None)

    cache_file = _get_cached_file_name(fnd['bucket'], fnd['path'])

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

    for files in _find_files(resultset[env]).values():
        ret += files

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
    specified and cache the data to disk
    '''
    cache_file = _get_buckets_cache_filename()

    # check mtime of the buckets files cache 
    if os.path.isfile(cache_file) and os.path.getmtime(cache_file) > time.time() - _s3_cache_expire:
        return _read_buckets_cache_file()
    else:
        # bucket files cache expired
        return _refresh_buckets_cache_file()

def _get_cache_dir():
    '''
    Return the path to the s3cache dir
    '''
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
    # TODO - should use file.makedirs maybe?
    if not os.path.exists(os.path.dirname(file_path)):
        os.makedirs(os.path.dirname(file_path))

    return file_path

def _get_buckets_cache_filename():
    '''
    Return the filename and path of the buckets cache file
    '''
    cache_dir = _get_cache_dir()

    # make sure the cache dirs exists
    # TODO - should use file.makedirs maybe?
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    return os.path.join(cache_dir, 'buckets_files.cache')

def _refresh_buckets_cache_file():
    '''
    Retrieve the content of all buckets and cache the metadata to the buckets
    cache file
    '''
    key, keyid = _get_s3_key()
    cache_file = _get_buckets_cache_filename()

    resultset = {}

    # == envs ==
    for env, buckets in _get_buckets().items():
        bucket_files = {}
        # == buckets ==
        for bucket_name in buckets:
            # == metadata ==
            bucket_files[bucket_name] = s3.query(
                    key = key,
                    keyid = keyid,
                    bucket = bucket_name,
                    return_bin = False)

        resultset[env] = bucket_files

    # write the metadata to disk
    if os.path.isfile(cache_file):
        os.remove(cache_file)

    with salt.utils.fopen(cache_file, 'w') as fp_:
        pickle.dump(resultset, fp_)

    return resultset

def _read_buckets_cache_file():
    '''
    Return the contents of the buckets cache file
    '''
    with salt.utils.fopen(_get_buckets_cache_filename(), 'rb') as fp_:
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

def _find_files(resultset):
    '''
    Looks for all the files in the S3 bucket cache metadata
    '''
    ret = {}

    for bucket in resultset.keys():
        ret[bucket] = []

    for bucket, data in resultset.iteritems():
        fileData = filter(lambda key: key.has_key('Key'), data)
        filePaths = map(lambda key: key['Key'], fileData)
        ret[bucket] += filter(lambda key: key.endswith('/') == False, filePaths)

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


