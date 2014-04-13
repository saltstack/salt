# -*- coding: utf-8 -*-
'''
The backend for a fileserver based on Amazon S3

.. seealso:: :doc:`/ref/file_server/index`

This backend exposes directories in S3 buckets as Salt environments.  This
feature is managed by the :conf_master:`fileserver_backend` option in the Salt
Master config.


S3 credentials can be set in the master config file like so:

.. code-block:: yaml

    s3.keyid: GKTADJGHEIQSXMKKRBJ08H
    s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

Alternatively, if on EC2 these credentials can be automatically loaded from
instance metadata.

Additionally, ``s3fs`` must be included in the
:conf_master:`fileserver_backend` config parameter in the master config file:

.. code-block:: yaml

    fileserver_backend:
      - s3fs

This fileserver supports two modes of operation for the buckets:

1. :strong:`A single bucket per environment`

   .. code-block:: yaml

    s3.buckets:
      production:
        - bucket1
        - bucket2
      staging:
        - bucket3
        - bucket4

2. :strong:`Multiple environments per bucket`

   .. code-block:: yaml

    s3.buckets:
      - bucket1
      - bucket2
      - bucket3
      - bucket4

Note that bucket names must be all lowercase both in the AWS console and in
Salt, otherwise you may encounter ``SignatureDoesNotMatch`` errors.

A multiple-environment bucket must adhere to the following root directory
structure::

    s3://<bucket name>/<environment>/<files>

.. note:: This fileserver back-end requires the use of the MD5 hashing algorightm.
    MD5 may not be compliant with all security policies.
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

_s3_cache_expire = 30  # cache for 30 seconds
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
        key, keyid, service_url = _get_s3_key()

        # sync the buckets to the local cache
        log.info('Syncing local cache from S3...')
        for saltenv, env_meta in metadata.iteritems():
            for bucket, files in _find_files(env_meta).iteritems():
                for file_path in files:
                    cached_file_path = _get_cached_file_name(bucket, saltenv, file_path)
                    log.info('{0} - {1} : {2}'.format(bucket, saltenv, file_path))

                    # load the file from S3 if it's not in the cache or it's old
                    _get_file_from_s3(metadata, saltenv, bucket, file_path, cached_file_path)

        log.info('Sync local cache from S3 completed.')


def find_file(path, saltenv='base', env=None, **kwargs):
    '''
    Look through the buckets cache file for a match.
    If the field is found, it is retrieved from S3 only if its cached version
    is missing, or if the MD5 does not match.
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    fnd = {'bucket': None,
           'path': None}

    metadata = _init()
    if not metadata or saltenv not in metadata:
        return fnd

    env_files = _find_files(metadata[saltenv])

    if not _is_env_per_bucket():
        path = os.path.join(saltenv, path)

    # look for the files and check if they're ignored globally
    for bucket_name, files in env_files.iteritems():
        if path in files and not fs.is_file_ignored(__opts__, path):
            fnd['bucket'] = bucket_name
            fnd['path'] = path

    if not fnd['path'] or not fnd['bucket']:
        return fnd

    cached_file_path = _get_cached_file_name(fnd['bucket'], saltenv, path)

    # jit load the file from S3 if it's not in the cache or it's old
    _get_file_from_s3(metadata, saltenv, fnd['bucket'], path, cached_file_path)

    return fnd


def file_hash(load, fnd):
    '''
    Return an MD5 file hash
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    ret = {}

    if 'saltenv' not in load:
        return ret

    if 'path' not in fnd or 'bucket' not in fnd or not fnd['path']:
        return ret

    cached_file_path = _get_cached_file_name(
            fnd['bucket'],
            load['saltenv'],
            fnd['path'])

    if os.path.isfile(cached_file_path):
        ret['hsum'] = salt.utils.get_hash(cached_file_path)
        ret['hash_type'] = 'md5'

    return ret


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

    if 'path' not in fnd or 'bucket' not in fnd:
        return ret

    gzip = load.get('gzip', None)

    # get the saltenv/path file from the cache
    cached_file_path = _get_cached_file_name(
            fnd['bucket'],
            load['saltenv'],
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

    saltenv = load['saltenv']
    metadata = _init()

    if not metadata or saltenv not in metadata:
        return ret

    for buckets in _find_files(metadata[saltenv]).values():
        files = filter(lambda f: not fs.is_file_ignored(__opts__, f), buckets)
        ret += _trim_env_off_path(files, saltenv)

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

    saltenv = load['saltenv']
    metadata = _init()

    if not metadata or saltenv not in metadata:
        return ret

    # grab all the dirs from the buckets cache file
    for dirs in _find_files(metadata[saltenv], dirs_only=True).values():
        # trim env and trailing slash
        dirs = _trim_env_off_path(dirs, saltenv, trim_slash=True)
        # remove empty string left by the base env dir in single bucket mode
        ret += filter(None, dirs)

    return ret


def _get_s3_key():
    '''
    Get AWS keys from pillar or config
    '''

    key = __opts__['s3.key'] if 's3.key' in __opts__ else None
    keyid = __opts__['s3.keyid'] if 's3.keyid' in __opts__ else None
    service_url = __opts__['s3.service_url'] \
        if 's3.service_url' in __opts__ \
        else None

    return key, keyid, service_url


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


def _get_cached_file_name(bucket_name, saltenv, path):
    '''
    Return the cached file name for a bucket path file
    '''

    file_path = os.path.join(_get_cache_dir(), saltenv, bucket_name, path)

    # make sure bucket and saltenv directories exist
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

    key, keyid, service_url = _get_s3_key()
    metadata = {}

    # helper s3 query function
    def __get_s3_meta(bucket, key=key, keyid=keyid):
        return s3.query(
                key=key,
                keyid=keyid,
                bucket=bucket,
                service_url=service_url,
                return_bin=False)

    if _is_env_per_bucket():
        # Single environment per bucket
        for saltenv, buckets in _get_buckets().items():
            bucket_files = {}
            for bucket_name in buckets:
                s3_meta = __get_s3_meta(bucket_name)

                # s3 query returned nothing
                if not s3_meta:
                    continue

                # grab only the files/dirs
                bucket_files[bucket_name] = filter(lambda k: 'Key' in k, s3_meta)

            metadata[saltenv] = bucket_files

    else:
        # Multiple environments per buckets
        for bucket_name in _get_buckets():
            s3_meta = __get_s3_meta(bucket_name)

            # s3 query returned nothing
            if not s3_meta:
                continue

            # pull out the environment dirs (eg. the root dirs)
            files = filter(lambda k: 'Key' in k, s3_meta)
            environments = map(lambda k: (os.path.dirname(k['Key']).split('/', 1))[0], files)
            environments = set(environments)

            # pull out the files for the environment
            for saltenv in environments:
                # grab only files/dirs that match this saltenv
                env_files = filter(lambda k: k['Key'].startswith(saltenv), files)

                if saltenv not in metadata:
                    metadata[saltenv] = {}

                if bucket_name not in metadata[saltenv]:
                    metadata[saltenv][bucket_name] = []

                metadata[saltenv][bucket_name] += env_files

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


def _find_file_meta(metadata, bucket_name, saltenv, path):
    '''
    Looks for a file's metadata in the S3 bucket cache file
    '''

    env_meta = metadata[saltenv] if saltenv in metadata else {}
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


def _get_file_from_s3(metadata, saltenv, bucket_name, path, cached_file_path):
    '''
    Checks the local cache for the file, if it's old or missing go grab the
    file from S3 and update the cache
    '''

    # check the local cache...
    if os.path.isfile(cached_file_path):
        file_meta = _find_file_meta(metadata, bucket_name, saltenv, path)
        file_md5 = filter(str.isalnum, file_meta['ETag']) if file_meta else None

        cached_file_hash = hashlib.md5()
        with salt.utils.fopen(cached_file_path, 'rb') as fp_:
            cached_file_hash.update(fp_.read())

        # hashes match we have a cache hit
        if cached_file_hash.hexdigest() == file_md5:
            return

    # ... or get the file from S3
    key, keyid, service_url = _get_s3_key()
    s3.query(
        key=key,
        keyid=keyid,
        bucket=bucket_name,
        service_url=service_url,
        path=urllib.quote(path),
        local_file=cached_file_path
    )


def _trim_env_off_path(paths, saltenv, trim_slash=False):
    '''
    Return a list of file paths with the saltenv directory removed
    '''
    env_len = None if _is_env_per_bucket() else len(saltenv) + 1
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
