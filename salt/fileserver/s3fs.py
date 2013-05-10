'''
The backend for the s3 based file server system.

S3 credentials can be either set in the master file using:

s3_key_id: XXXXXXXXXXXXXXX
s3_server_access_key: XXXXXXXXXXXXXXX


If on EC2 these credentials can be automatically loaded from the
instance metadata

Example configuration options in master file:

s3_buckets:
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
_s3_cache_dir = 's3cache'
_s3_cache_file = os.path.join(_s3_cache_dir, 'buckets_files.cache')

#__opts__ = []

def init():
    '''
    Connects to S3 and downloads metadata about each file in all
    buckets specified within and environment and saves them to disk
    '''
    cache_file = os.path.join(__opts__['cachedir'], _s3_cache_file)

    # check for cache file
    if os.path.isfile(cache_file) and os.path.getmtime(cache_file) > time.time() - _s3_cache_expire:
        log.error('CACHE HIT!')
        with salt.utils.fopen(cache_file, 'rb') as fp_:
            data = fp_.read()
            return eval(data)

    else:
        log.error('CACHE MISS!')
        return refresh_cache()

def refresh_cache():
    '''
    Retrieves the contents of the buckets and caches them to a file
    '''
    s3_key_id =  __opts__['s3_key_id'] if __opts__['s3_key_id'] else None
    s3_server_access_key = __opts__['s3_server_access_key'] if __opts__['s3_server_access_key'] else None

    cache_file = os.path.join(__opts__['cachedir'], _s3_cache_file)

    resultset = {}
    for env, buckets in __opts__['s3_buckets'].items():
        bucket_files = {}
        for bucket_name in buckets:
            try:
                bucket_files[bucket_name] = s3.query(
                        key = s3_server_access_key,
                        keyid = s3_key_id,
                        bucket = bucket_name,
                        return_bin = False)

            except TypeError:
                log.error('There was an error accessing the {0} bucket'.format(bucket_name))

        resultset[env] = bucket_files

    if not os.path.exists(_s3_cache_dir):
        os.makedirs(_s3_cache_dir)

    if os.path.isfile(cache_file):
        os.remove(cache_file)

    with salt.utils.fopen(cache_file, 'w') as fp_:
        fp_.write(str(resultset))

    # return the resultset
    return resultset

def update():
    '''
    Check if the cache_file is up to date
    '''
    init()

def envs():
    '''
    Return the file server environments
    '''
    return __opts__['s3_buckets'].keys()

def find_file(path, env='base', **kwargs):
    '''
    Looks through the buckets to find the first matching file and formats it
    '''
    log.error('******************************** find_file');
    log.error('path: {0}'.format(json.dumps(path)))
    log.error('env: {0}'.format(json.dumps(env)))
    log.error('args: {0}'.format(json.dumps(kwargs)))

    fnd = {'bucket': None,
            'path' : None}

    filepath = '/'.join([env, path])

    resultset = init()
    if env not in resultset:
        return fnd

    ret = _find_file(resultset[env])

    for bucket, files in ret.iteritems():
        if filepath in files:
            fnd['bucket'] = bucket
            fnd['path'] = filepath

    # grab the file from S3 if it doesn't exist in the cache
    #if fnd['path'] and fnd['bucket']:
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

    abspath = os.path.join( __opts__['cachedir'], _s3_cache_dir, bucket, fnd['path'])
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
    log.error('load: {0}'.format(json.dumps(load)))

    ret = []
    env = load['env']

    resultset = init()

    if env not in resultset:
        return ret

    for files in _find_file(resultset[env]).values():
        ret += files

    log.error(json.dumps(ret))
    return ret

def _find_file(resultset):
    '''
    Looks for the file in the S3 bucket cache 
    '''
    ret = {}

    for bucket in resultset.keys():
        ret[bucket] = []

    for bucket, data in resultset.iteritems():
        fileData = filter(lambda key: key.has_key('Key'), data)
        filePaths = map(lambda key: key['Key'], fileData)
        ret[bucket] += filter(lambda key: key.endswith('/') == False, filePaths)

    return ret

