# -*- coding: utf-8 -*-
'''
Copy pillar data from a bucket in Amazon S3

The S3 pillar can be configured in the master config file with the following
options

.. code-block:: yaml

    ext_pillar:
      - s3:
          bucket: my.fancy.pillar.bucket
          keyid: KASKFJWAKJASJKDAJKSD
          key: ksladfDLKDALSFKSD93q032sdDasdfasdflsadkf
          multiple_env: False
          environment: base
          verify_ssl: True
          service_url: s3.amazonaws.com

The ``bucket`` parameter specifies the target S3 bucket. It is required.

The ``keyid`` parameter specifies the key id to use when access the S3 bucket.
It is required.

The ``key`` parameter specifies the key to use when access the S3 bucket. It
is required.

The ``multiple_env`` defaults to False. It specifies whether the pillar should
interpret top level folders as pillar environments (see mode section below).

The ``environment`` defaults to 'base'. It specifies which environment the
bucket represents when in single environments mode (see mode section below). It
is ignored if multiple_env is True.

The ``verify_ssl`` parameter defaults to True. It specifies whether to check for
valid S3 SSL certificates. *NOTE* If you use bucket names with periods, this
must be set to False else an invalid certificate error will be thrown (issue
#12200).

The ``service_url`` parameter defaults to 's3.amazonaws.com'. It specifies the
base url to use for accessing S3.


This pillar can operate in two modes, single environment per bucket or multiple
environments per bucket.

Single environment mode must have this bucket structure:

.. code-block:: text

    s3://<bucket name>/<files>

Multiple environment mode must have this bucket structure:

.. code-block:: text

    s3://<bucket name>/<environment>/<files>
'''

# Import python libs
import logging
import os
import time
import hashlib
import pickle
import urllib
from copy import deepcopy

# Import salt libs
from salt.pillar import Pillar
import salt.utils
import salt.utils.s3 as s3

# Set up logging
log = logging.getLogger(__name__)

_s3_cache_expire = 30  # cache for 30 seconds
_s3_sync_on_update = True  # sync cache on update rather than jit


class S3Credentials(object):
    def __init__(self, key, keyid, bucket, service_url, verify_ssl=True):
        self.key = key
        self.keyid = keyid
        self.bucket = bucket
        self.service_url = service_url
        self.verify_ssl = verify_ssl


def ext_pillar(minion_id, pillar, bucket, key, keyid, verify_ssl,
               multiple_env=False, environment='base', service_url=None):
    '''
    Execute a command and read the output as YAML
    '''

    s3_creds = S3Credentials(key, keyid, bucket, service_url, verify_ssl)

    # normpath is needed to remove appended '/' if root is empty string.
    pillar_dir = os.path.normpath(os.path.join(_get_cache_dir(), environment,
                                               bucket))

    if __opts__['pillar_roots'].get(environment, []) == [pillar_dir]:
        return {}

    metadata = _init(s3_creds, multiple_env, environment)

    if _s3_sync_on_update:
        # sync the buckets to the local cache
        log.info('Syncing local pillar cache from S3...')
        for saltenv, env_meta in metadata.iteritems():
            for bucket, files in _find_files(env_meta).iteritems():
                for file_path in files:
                    cached_file_path = _get_cached_file_name(bucket, saltenv,
                                                             file_path)
                    log.info('{0} - {1} : {2}'.format(bucket, saltenv,
                                                      file_path))
                    # load the file from S3 if not in the cache or too old
                    _get_file_from_s3(s3_creds, metadata, saltenv, bucket,
                                      file_path, cached_file_path)

        log.info('Sync local pillar cache from S3 completed.')

    opts = deepcopy(__opts__)
    opts['pillar_roots'][environment] = [pillar_dir]

    pil = Pillar(opts, __grains__, minion_id, environment)

    compiled_pillar = pil.compile_pillar()

    return compiled_pillar


def _init(creds, multiple_env, environment):
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
        return _refresh_buckets_cache_file(creds, cache_file, multiple_env,
                                           environment)


def _get_cache_dir():
    '''
    Get pillar cache directory. Initialize it if it does not exist.
    '''

    cache_dir = os.path.join(__opts__['cachedir'], 'pillar_s3fs')

    if not os.path.isdir(cache_dir):
        log.debug('Initializing S3 Pillar Cache')
        os.makedirs(cache_dir)

    return cache_dir


def _get_cached_file_name(bucket, saltenv, path):
    '''
    Return the cached file name for a bucket path file
    '''

    file_path = os.path.join(_get_cache_dir(), saltenv, bucket, path)

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


def _refresh_buckets_cache_file(creds, cache_file, multiple_env, environment):
    '''
    Retrieve the content of all buckets and cache the metadata to the buckets
    cache file
    '''

    # helper s3 query function
    def __get_s3_meta():
        return s3.query(
            key=creds.key,
            keyid=creds.keyid,
            bucket=creds.bucket,
            service_url=creds.service_url,
            verify_ssl=creds.verify_ssl,
            return_bin=False)

    # grab only the files/dirs in the bucket
    def __get_pillar_files_from_s3_meta(s3_meta):
        return filter(lambda k: 'Key' in k, s3_meta)

    # pull out the environment dirs (e.g. the root dirs)
    def __get_pillar_environments(files):
        environments = map(
            lambda k: (os.path.dirname(k['Key']).split('/', 1))[0], files
        )
        return set(environments)

    log.debug('Refreshing S3 buckets pillar cache file')

    metadata = {}
    bucket = creds.bucket

    if not multiple_env:
        # Single environment per bucket
        log.debug('Single environment per bucket mode')

        bucket_files = {}
        s3_meta = __get_s3_meta()

        # s3 query returned something
        if s3_meta:
            bucket_files[bucket] = __get_pillar_files_from_s3_meta(s3_meta)

            metadata[environment] = bucket_files

    else:
        # Multiple environments per buckets
        log.debug('Multiple environment per bucket mode')
        s3_meta = __get_s3_meta()

        # s3 query returned data
        if s3_meta:
            files = __get_pillar_files_from_s3_meta(s3_meta)
            environments = __get_pillar_environments(files)

            # pull out the files for the environment
            for saltenv in environments:
                # grab only files/dirs that match this saltenv.
                env_files = [k for k in files if k['Key'].startswith(saltenv)]

                if saltenv not in metadata:
                    metadata[saltenv] = {}

                if bucket not in metadata[saltenv]:
                    metadata[saltenv][bucket] = []

                metadata[saltenv][bucket] += env_files

    # write the metadata to disk
    if os.path.isfile(cache_file):
        os.remove(cache_file)

    log.debug('Writing S3 buckets pillar cache file')

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

    for bucket, data in metadata.iteritems():
        if bucket not in ret:
            ret[bucket] = []

        # grab the paths from the metadata
        filePaths = map(lambda k: k['Key'], data)
        # filter out the files or the dirs depending on flag
        ret[bucket] += filter(lambda k: k.endswith('/') == dirs_only,
                              filePaths)

    return ret


def _find_file_meta(metadata, bucket, saltenv, path):
    '''
    Looks for a file's metadata in the S3 bucket cache file
    '''

    env_meta = metadata[saltenv] if saltenv in metadata else {}
    bucket_meta = env_meta[bucket] if bucket in env_meta else {}
    files_meta = filter((lambda k: 'Key' in k), bucket_meta)

    for item_meta in files_meta:
        if 'Key' in item_meta and item_meta['Key'] == path:
            return item_meta


def _get_file_from_s3(creds, metadata, saltenv, bucket, path,
                      cached_file_path):
    '''
    Checks the local cache for the file, if it's old or missing go grab the
    file from S3 and update the cache
    '''

    # check the local cache...
    if os.path.isfile(cached_file_path):
        file_meta = _find_file_meta(metadata, bucket, saltenv, path)
        file_md5 = filter(str.isalnum, file_meta['ETag']) \
            if file_meta else None

        cached_file_hash = hashlib.md5()
        with salt.utils.fopen(cached_file_path, 'rb') as fp_:
            cached_file_hash.update(fp_.read())

        # hashes match we have a cache hit
        if cached_file_hash.hexdigest() == file_md5:
            return

    # ... or get the file from S3
    s3.query(
        key=creds.key,
        keyid=creds.keyid,
        bucket=bucket,
        service_url=creds.service_url,
        path=urllib.quote(path),
        local_file=cached_file_path,
        verify_ssl=creds.verify_ssl
    )
