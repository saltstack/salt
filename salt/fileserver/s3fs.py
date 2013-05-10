'''
The backend for the s3 based file server system.

S3 credentials can be either set in the master file using:

s3_key_id: XXXXXXXXXXXXXXX
s3_server_access_key: XXXXXXXXXXXXXXX


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
import logging
import time
import json

# Import salt libs
import salt.fileserver
import salt.utils
import salt.utils.s3 as s3
import salt.modules

log = logging.getLogger(__name__)

_s3_cache_expire = 300 # cache for 5 minutes

def envs():
    '''
    Return the file server environments
    '''
    _init()
    return _get_buckets().keys()

def update():
    '''
    Check if the cache_file is up to date
    '''
    _init()

def find_file(path, env='base', **kwargs):
    '''
    Looks through the buckets to find the first matching file and formats it
    '''
    log.error('******************************** find_file');
    log.error('path: {0}'.format(path))
    log.error('env: {0}'.format(env))

    env_path = _get_env_path(env, path)
    log.error('env_path: {0}'.format(env_path))

    fnd = {'bucket': None,
            'path' : None}

    # grab the buckets files from S3 or the cache
    resultset = _init()
    if not resultset or env not in resultset:
        return fnd

    # grab the files for this env
    ret = _find_files(resultset[env])

    # look for the env_filename in the buckets files
    for bucket_name, files in ret.iteritems():
        if env_path in files:
            fnd['bucket'] = bucket_name
            fnd['path'] = env_path

    # grab the file from S3 if it doesn't exist in the cache
    if fnd['path'] and fnd['bucket']:
        if _is_cached_file_current(resultset, env, fnd['bucket'], fnd['path']):
            log.error('******************************** find_file CACHED')
            return fnd
    
        log.error('******************************** find_file RELOAD')

        # not in cache or is old/mismatched, reload!
        key, keyid = _get_s3_key()

        s3.query(
                key = key,
                keyid = keyid,
                bucket = fnd['bucket'],
                path = fnd['path'],
                local_file = _get_cached_file_name(fnd['bucket'], fnd['path']))

    log.error(json.dumps(fnd))
    return fnd

def serve_file(load, fnd):
    '''
    Serve the file chunks out to the minion
    '''
    log.error('******************************** serve_file');
    log.error('load: {0}'.format(json.dumps(load)))
    log.error('fnd: {0}'.format(json.dumps(fnd)))

    ret = {}
    #s3_key_id =  __opts__['s3_key_id'] if __opts__['s3_key_id'] else None
    #s3_server_access_key = __opts__['s3_server_access_key'] if __opts__['s3_server_access_key'] else None

    env = load["env"] # FIXME - IMPLEMENT ENV
    bucket = fnd["bucket"]
    path = fnd["path"]

    abspath = os.path.join(_get_cache_dir(), bucket, fnd['path'])
    absdirectory = os.path.dirname(abspath)

    log.error(json.dumps(fnd))
    log.error(env)
    log.error(abspath)
    log.error(absdirectory)

    return ret

    #if not os.path.exists(absdirectory):
        #os.makedirs(absdirectory)

    #if os.path.isfile(abspath):
        #with salt.utils.fopen(abspath, 'rb') as fp_:
            #diskmd5 = hashlib.md5(fp_.read()).hexdigest()

            #if diskmd5 == fnd["md5"]:
                #ret['dest'] = bucket+"//"+path
                #ret['data'] = fp_.read()
    #else:
        #with salt.utils.fopen(abspath, 'w') as fp_:
            #fetchedFile = s3.query(s3_server_access_key,s3_key_id,bucket=bucket,path=path,return_bin=True)
            #fp_.write(fetchedFile)


    #gzip = load.get('gzip', None)
    #with salt.utils.fopen(abspath, 'rb') as fp_:
        #fp_.seek(load['loc'])
        #data = fp_.read(__opts__['file_buffer_size'])
        #if gzip and data:
            #data = salt.utils.gzip_util.compress(data, gzip)
            #ret['gzip'] = gzip
        #ret['data'] = data
        #ret['dest'] = bucket+"//"+path
        #return ret

def file_hash(load, fnd):
    '''
    Provides Salt with
    '''
    log.error('******************************** find_hash')
    log.error('load: {0}'.format(json.dumps(load)))
    log.error('fnd: {0}'.format(json.dumps(fnd)))

    #ret = {}
    #resultset = get_result_set()
    #env = load["env"]
    #bucket = fnd["bucket"]
    #path = fnd["path"]

    #fileData = filter(lambda key: key.has_key("Key"),  resultset[env][bucket])
    #item =  filter(lambda key: key["Key"] == path , fileData)[0]
    #ret['hsum'] = item["ETag"]
    #ret['hash_type'] = "md5"
    #return ret

def file_list(load):
    '''
    Return a list of all files on the file server in a specified
    environment
    '''
    log.error('******************************** file_list')
    ret = []
    env = load['env']

    resultset = _init()

    if not resultset or env not in resultset:
        return ret

    for files in _find_files(resultset[env]).values():
        ret += files

    log.error(json.dumps(ret))
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
    Connects to S3 and downloads metadata about each file in all
    buckets specified within and environment and saves them to disk
    '''
    cache_file = _get_buckets_cache_name()

    # check for cache file
    if os.path.isfile(cache_file) and os.path.getmtime(cache_file) > time.time() - _s3_cache_expire:
        # cache hit
        return _read_buckets_cache_file()
    else:
        # cache miss
        return _refresh_buckets_cache_file()

def _get_cache_dir():
    '''
    Return the path to the cache dir
    '''
    return os.path.join(__opts__['cachedir'], 's3cache')

def _get_env_path(env, path):
    '''
    Returns the path of the file including the
    environment dirname
    '''
    return os.path.join(env, path)

def _get_cached_file_name(bucket_name, path):
    '''
    Returns the cached files named
    '''
    file_path = os.path.join(_get_cache_dir(), bucket_name, path)

    # make sure bucket and env directories exist
    # TODO - should use file.makedirs maybe?
    if not os.path.exists(os.path.dirname(file_path)):
        os.makedirs(os.path.dirname(file_path))

    return file_path

def _get_buckets_cache_name():
    '''
    Return the filename and path of the cache file
    '''
    cache_dir = _get_cache_dir()

    # make sure the cache dirs exists
    # TODO - should use file.makedirs maybe?
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    return os.path.join(cache_dir, 'buckets_files.cache')

def _refresh_buckets_cache_file():
    '''
    Retrieves the contents of the buckets and caches them to a file
    '''
    key, keyid = _get_s3_key()
    cache_file = _get_buckets_cache_name()

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
        fp_.write(str(resultset))

    return resultset

def _read_buckets_cache_file():
    '''
    Returns the contents of the buckets contained in the cache file
    '''
    with salt.utils.fopen(_get_buckets_cache_name(), 'rb') as fp_:
        data = fp_.read()
        return eval(data)

def _is_cached_file_current(resultset, env, bucket_name, path):
    '''
    Check the cache for the named filename
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
    Looks for the files in the S3 bucket cache
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
    Looks for a files metadata in the S3 bucket cache
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


