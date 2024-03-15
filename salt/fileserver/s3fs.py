"""
Amazon S3 Fileserver Backend

.. versionadded:: 0.16.0

This backend exposes directories in S3 buckets as Salt environments. To enable
this backend, add ``s3fs`` to the :conf_master:`fileserver_backend` option in the
Master config file.

.. code-block:: yaml

    fileserver_backend:
      - s3fs

S3 credentials must also be set in the master config file:

.. code-block:: yaml

    s3.keyid: GKTADJGHEIQSXMKKRBJ08H
    s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

Alternatively, if on EC2 these credentials can be automatically loaded from
instance metadata.

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

.. note:: This fileserver back-end requires the use of the MD5 hashing algorithm.
    MD5 may not be compliant with all security policies.

.. note:: This fileserver back-end is only compatible with MD5 ETag hashes in
    the S3 metadata. This means that you must use SSE-S3 or plaintext for
    bucket encryption, and that you must not use multipart upload when
    uploading to your bucket. More information here:
    https://docs.aws.amazon.com/AmazonS3/latest/API/RESTCommonResponseHeaders.html

    Objects without an MD5 ETag will be fetched on every fileserver update.

    If you deal with objects greater than 8MB, then you should use the
    following AWS CLI config to avoid mutipart upload:

    .. code-block:: text

        s3 =
          multipart_threshold = 1024MB

    More info here:
    https://docs.aws.amazon.com/cli/latest/topic/s3-config.html

.. note:: This fileserver back-end will by default sync all buckets on every
    fileserver update.

    If you want files to be only populated in the cache when requested, you can
    disable this in the master config:

    .. code-block:: yaml

        s3.s3_sync_on_update: False
"""

import datetime
import logging
import os
import pickle
import time
import urllib.parse

import salt.fileserver as fs
import salt.modules
import salt.utils.files
import salt.utils.gzip_util
import salt.utils.hashutils
import salt.utils.versions

log = logging.getLogger(__name__)

S3_HASH_TYPE = "md5"


def envs():
    """
    Return a list of directories within the bucket that can be
    used as environments.
    """

    # update and grab the envs from the metadata keys
    metadata = _init()
    return list(metadata.keys())


def update():
    """
    Update the cache file for the bucket.
    """

    metadata = _init()

    # sync cache on update rather than jit
    if __opts__.get("s3.s3_sync_on_update", True):
        # sync the buckets to the local cache
        log.info("Syncing local cache from S3...")
        for saltenv, env_meta in metadata.items():
            for bucket_files in _find_files(env_meta):
                for bucket, files in bucket_files.items():
                    for file_path in files:
                        cached_file_path = _get_cached_file_name(
                            bucket, saltenv, file_path
                        )
                        log.debug("%s - %s : %s", bucket, saltenv, file_path)

                        # load the file from S3 if it's not in the cache or it's old
                        _get_file_from_s3(
                            metadata, saltenv, bucket, file_path, cached_file_path
                        )

        log.info("Sync local cache from S3 completed.")


def find_file(path, saltenv="base", **kwargs):
    """
    Look through the buckets cache file for a match.
    If the field is found, it is retrieved from S3 only if its cached version
    is missing, or if the MD5 does not match.
    """
    if "env" in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop("env")

    fnd = {"bucket": None, "path": None}

    metadata = _init()
    if not metadata or saltenv not in metadata:
        return fnd

    env_files = _find_files(metadata[saltenv])

    if not _is_env_per_bucket():
        path = os.path.join(saltenv, path)

    # look for the files and check if they're ignored globally
    for bucket in env_files:
        for bucket_name, files in bucket.items():
            if path in files and not fs.is_file_ignored(__opts__, path):
                fnd["bucket"] = bucket_name
                fnd["path"] = path
                break
        else:
            continue  # only executes if we didn't break
        break

    if not fnd["path"] or not fnd["bucket"]:
        return fnd

    cached_file_path = _get_cached_file_name(fnd["bucket"], saltenv, path)

    # jit load the file from S3 if it's not in the cache or it's old
    _get_file_from_s3(metadata, saltenv, fnd["bucket"], path, cached_file_path)

    return fnd


def file_hash(load, fnd):
    """
    Return the hash of an object's cached copy
    """
    if "env" in load:
        # "env" is not supported; Use "saltenv".
        load.pop("env")

    ret = {}

    if "saltenv" not in load:
        return ret

    if "path" not in fnd or "bucket" not in fnd or not fnd["path"]:
        return ret

    cached_file_path = _get_cached_file_name(
        fnd["bucket"], load["saltenv"], fnd["path"]
    )

    if os.path.isfile(cached_file_path):
        ret["hash_type"] = S3_HASH_TYPE
        ret["hsum"] = salt.utils.hashutils.get_hash(cached_file_path, S3_HASH_TYPE)

    return ret


def serve_file(load, fnd):
    """
    Return a chunk from a file based on the data received
    """
    if "env" in load:
        # "env" is not supported; Use "saltenv".
        load.pop("env")

    ret = {"data": "", "dest": ""}

    if "path" not in load or "loc" not in load or "saltenv" not in load:
        return ret

    if "path" not in fnd or "bucket" not in fnd:
        return ret

    gzip = load.get("gzip", None)

    # get the saltenv/path file from the cache
    cached_file_path = _get_cached_file_name(
        fnd["bucket"], load["saltenv"], fnd["path"]
    )

    ret["dest"] = _trim_env_off_path([fnd["path"]], load["saltenv"])[0]

    with salt.utils.files.fopen(cached_file_path, "rb") as fp_:
        fp_.seek(load["loc"])
        data = fp_.read(__opts__["file_buffer_size"])
        if data and not salt.utils.files.is_binary(cached_file_path):
            data = data.decode(__salt_system_encoding__)
        if gzip and data:
            data = salt.utils.gzip_util.compress(data, gzip)
            ret["gzip"] = gzip
        ret["data"] = data
    return ret


def file_list(load):
    """
    Return a list of all files on the file server in a specified environment
    """
    if "env" in load:
        # "env" is not supported; Use "saltenv".
        load.pop("env")

    ret = []

    if "saltenv" not in load:
        return ret

    saltenv = load["saltenv"]
    metadata = _init()

    if not metadata or saltenv not in metadata:
        return ret
    for bucket in _find_files(metadata[saltenv]):
        for buckets in bucket.values():
            files = [f for f in buckets if not fs.is_file_ignored(__opts__, f)]
            ret += _trim_env_off_path(files, saltenv)

    return ret


def file_list_emptydirs(load):
    """
    Return a list of all empty directories on the master
    """
    # TODO - implement this
    _init()

    return []


def dir_list(load):
    """
    Return a list of all directories on the master
    """
    if "env" in load:
        # "env" is not supported; Use "saltenv".
        load.pop("env")

    ret = []

    if "saltenv" not in load:
        return ret

    saltenv = load["saltenv"]
    metadata = _init()

    if not metadata or saltenv not in metadata:
        return ret

    # grab all the dirs from the buckets cache file
    for bucket in _find_dirs(metadata[saltenv]):
        for dirs in bucket.values():
            # trim env and trailing slash
            dirs = _trim_env_off_path(dirs, saltenv, trim_slash=True)
            # remove empty string left by the base env dir in single bucket mode
            ret += [_f for _f in dirs if _f]

    return ret


def _get_s3_key():
    """
    Get AWS keys from pillar or config
    """

    key = __opts__["s3.key"] if "s3.key" in __opts__ else None
    keyid = __opts__["s3.keyid"] if "s3.keyid" in __opts__ else None
    service_url = __opts__["s3.service_url"] if "s3.service_url" in __opts__ else None
    verify_ssl = __opts__["s3.verify_ssl"] if "s3.verify_ssl" in __opts__ else None
    kms_keyid = __opts__["aws.kmw.keyid"] if "aws.kms.keyid" in __opts__ else None
    location = __opts__["s3.location"] if "s3.location" in __opts__ else None
    path_style = __opts__["s3.path_style"] if "s3.path_style" in __opts__ else None
    https_enable = (
        __opts__["s3.https_enable"] if "s3.https_enable" in __opts__ else None
    )

    return (
        key,
        keyid,
        service_url,
        verify_ssl,
        kms_keyid,
        location,
        path_style,
        https_enable,
    )


def _init():
    """
    Connect to S3 and download the metadata for each file in all buckets
    specified and cache the data to disk.
    """
    cache_file = _get_buckets_cache_filename()
    exp = time.time() - __opts__.get("s3.s3_cache_expire", 30)

    # check mtime of the buckets files cache
    metadata = None
    try:
        if os.path.getmtime(cache_file) > exp:
            metadata = _read_buckets_cache_file(cache_file)
    except OSError:
        pass

    if metadata is None:
        # bucket files cache expired or does not exist
        metadata = _refresh_buckets_cache_file(cache_file)

    return metadata


def _get_cache_dir():
    """
    Return the path to the s3cache dir
    """

    # Or is that making too many assumptions?
    return os.path.join(__opts__["cachedir"], "s3cache")


def _get_cached_file_name(bucket_name, saltenv, path):
    """
    Return the cached file name for a bucket path file
    """

    file_path = os.path.join(_get_cache_dir(), saltenv, bucket_name, path)

    # make sure bucket and saltenv directories exist
    if not os.path.exists(os.path.dirname(file_path)):
        os.makedirs(os.path.dirname(file_path))

    return file_path


def _get_buckets_cache_filename():
    """
    Return the filename of the cache for bucket contents.
    Create the path if it does not exist.
    """

    cache_dir = _get_cache_dir()
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    return os.path.join(cache_dir, "buckets_files.cache")


def _refresh_buckets_cache_file(cache_file):
    """
    Retrieve the content of all buckets and cache the metadata to the buckets
    cache file
    """

    log.debug("Refreshing buckets cache file")

    (
        key,
        keyid,
        service_url,
        verify_ssl,
        kms_keyid,
        location,
        path_style,
        https_enable,
    ) = _get_s3_key()
    metadata = {}

    # helper s3 query function
    def __get_s3_meta(bucket, key=key, keyid=keyid):
        ret, marker = [], ""
        while True:
            tmp = __utils__["s3.query"](
                key=key,
                keyid=keyid,
                kms_keyid=keyid,
                bucket=bucket,
                service_url=service_url,
                verify_ssl=verify_ssl,
                location=location,
                return_bin=False,
                path_style=path_style,
                https_enable=https_enable,
                params={"marker": marker},
            )
            headers = []
            for header in tmp:
                if "Key" in header:
                    break
                headers.append(header)
            ret.extend(tmp)
            if all(
                [header.get("IsTruncated", "false") == "false" for header in headers]
            ):
                break
            marker = tmp[-1]["Key"]
        return ret

    if _is_env_per_bucket():
        # Single environment per bucket
        for saltenv, buckets in _get_buckets().items():
            bucket_files_list = []
            for bucket_name in buckets:
                bucket_files = {}
                s3_meta = __get_s3_meta(bucket_name)

                # s3 query returned nothing
                if not s3_meta:
                    continue

                # grab only the files/dirs
                bucket_files[bucket_name] = [k for k in s3_meta if "Key" in k]
                bucket_files_list.append(bucket_files)

                # check to see if we added any keys, otherwise investigate possible error conditions
                if not bucket_files[bucket_name]:
                    meta_response = {}
                    for k in s3_meta:
                        if "Code" in k or "Message" in k:
                            # assumes no duplicate keys, consisdent with current erro response.
                            meta_response.update(k)
                    # attempt use of human readable output first.
                    try:
                        log.warning(
                            "'%s' response for bucket '%s'",
                            meta_response["Message"],
                            bucket_name,
                        )
                        continue
                    except KeyError:
                        # no human readable error message provided
                        if "Code" in meta_response:
                            log.warning(
                                "'%s' response for bucket '%s'",
                                meta_response["Code"],
                                bucket_name,
                            )
                            continue
                        else:
                            log.warning(
                                "S3 Error! Do you have any files in your S3 bucket?"
                            )
                            return {}

            metadata[saltenv] = bucket_files_list

    else:
        # Multiple environments per buckets
        for bucket_name in _get_buckets():
            s3_meta = __get_s3_meta(bucket_name)

            # s3 query returned nothing
            if not s3_meta:
                continue

            # pull out the environment dirs (e.g. the root dirs)
            files = [k for k in s3_meta if "Key" in k]

            # check to see if we added any keys, otherwise investigate possible error conditions
            if not files:
                meta_response = {}
                for k in s3_meta:
                    if "Code" in k or "Message" in k:
                        # assumes no duplicate keys, consisdent with current erro response.
                        meta_response.update(k)
                # attempt use of human readable output first.
                try:
                    log.warning(
                        "'%s' response for bucket '%s'",
                        meta_response["Message"],
                        bucket_name,
                    )
                    continue
                except KeyError:
                    # no human readable error message provided
                    if "Code" in meta_response:
                        log.warning(
                            "'%s' response for bucket '%s'",
                            meta_response["Code"],
                            bucket_name,
                        )
                        continue
                    else:
                        log.warning(
                            "S3 Error! Do you have any files in your S3 bucket?"
                        )
                        return {}

            environments = [(os.path.dirname(k["Key"]).split("/", 1))[0] for k in files]
            environments = set(environments)

            # pull out the files for the environment
            for saltenv in environments:
                # grab only files/dirs that match this saltenv
                env_files = [k for k in files if k["Key"].startswith(saltenv)]

                if saltenv not in metadata:
                    metadata[saltenv] = []

                found = False
                for bucket_files in metadata[saltenv]:
                    if bucket_name in bucket_files:
                        bucket_files[bucket_name] += env_files
                        found = True
                        break
                if not found:
                    metadata[saltenv].append({bucket_name: env_files})

    # write the metadata to disk
    _write_buckets_cache_file(metadata, cache_file)

    return metadata


def _write_buckets_cache_file(metadata, cache_file):
    """
    Write the contents of the buckets cache file
    """
    if os.path.isfile(cache_file):
        os.remove(cache_file)

    log.debug("Writing buckets cache file")

    with salt.utils.files.fopen(cache_file, "wb") as fp_:
        pickle.dump(metadata, fp_)


def _read_buckets_cache_file(cache_file):
    """
    Return the contents of the buckets cache file
    """

    log.debug("Reading buckets cache file")

    with salt.utils.files.fopen(cache_file, "rb") as fp_:
        try:
            data = pickle.load(fp_)
        except (
            pickle.UnpicklingError,
            AttributeError,
            EOFError,
            ImportError,
            IndexError,
            KeyError,
            ValueError,
        ) as exc:
            log.debug("Exception reading buckets cache file: '%s'", exc)
            data = None

    return data


def _find_files(metadata):
    """
    Looks for all the files in the S3 bucket cache metadata
    """

    ret = []
    found = {}

    for bucket_dict in metadata:
        for bucket_name, data in bucket_dict.items():
            filepaths = [k["Key"] for k in data]
            filepaths = [k for k in filepaths if not k.endswith("/")]
            if bucket_name not in found:
                found[bucket_name] = True
                ret.append({bucket_name: filepaths})
            else:
                for bucket in ret:
                    if bucket_name in bucket:
                        bucket[bucket_name] += filepaths
                        break
    return ret


def _find_dirs(metadata):
    """
    Looks for all the directories in the S3 bucket cache metadata.

    Supports trailing '/' keys (as created by S3 console) as well as
    directories discovered in the path of file keys.
    """

    ret = []
    found = {}

    for bucket_dict in metadata:
        for bucket_name, data in bucket_dict.items():
            dirpaths = set()
            for path in [k["Key"] for k in data]:
                prefix = ""
                for part in path.split("/")[:-1]:
                    directory = prefix + part + "/"
                    dirpaths.add(directory)
                    prefix = directory
            if bucket_name not in found:
                found[bucket_name] = True
                ret.append({bucket_name: list(dirpaths)})
            else:
                for bucket in ret:
                    if bucket_name in bucket:
                        bucket[bucket_name] += list(dirpaths)
                        bucket[bucket_name] = list(set(bucket[bucket_name]))
                        break
    return ret


def _find_file_meta(metadata, bucket_name, saltenv, path):
    """
    Looks for a file's metadata in the S3 bucket cache file
    """
    env_meta = metadata[saltenv] if saltenv in metadata else {}
    bucket_meta = {}
    for bucket in env_meta:
        if bucket_name in bucket:
            bucket_meta = bucket[bucket_name]
    files_meta = list(list(filter((lambda k: "Key" in k), bucket_meta)))

    for item_meta in files_meta:
        if "Key" in item_meta and item_meta["Key"] == path:
            try:
                # Get rid of quotes surrounding md5
                item_meta["ETag"] = item_meta["ETag"].strip('"')
            except KeyError:
                pass
            return item_meta


def _get_buckets():
    """
    Return the configuration buckets
    """

    return __opts__["s3.buckets"] if "s3.buckets" in __opts__ else {}


def _get_file_from_s3(metadata, saltenv, bucket_name, path, cached_file_path):
    """
    Checks the local cache for the file, if it's old or missing go grab the
    file from S3 and update the cache
    """
    (
        key,
        keyid,
        service_url,
        verify_ssl,
        kms_keyid,
        location,
        path_style,
        https_enable,
    ) = _get_s3_key()

    # check the local cache...
    if os.path.isfile(cached_file_path):
        file_meta = _find_file_meta(metadata, bucket_name, saltenv, path)
        if file_meta:
            file_etag = file_meta["ETag"]

            if file_etag.find("-") == -1:
                file_md5 = file_etag
                cached_md5 = salt.utils.hashutils.get_hash(
                    cached_file_path, S3_HASH_TYPE
                )

                # hashes match we have a cache hit
                if cached_md5 == file_md5:
                    return
                else:
                    log.info("found different hash for file %s, updating...", path)
            else:
                cached_file_stat = os.stat(cached_file_path)
                cached_file_size = cached_file_stat.st_size
                cached_file_mtime = datetime.datetime.fromtimestamp(
                    cached_file_stat.st_mtime
                )

                cached_file_lastmod = datetime.datetime.strptime(
                    file_meta["LastModified"], "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                if (
                    cached_file_size == int(file_meta["Size"])
                    and cached_file_mtime > cached_file_lastmod
                ):
                    log.debug(
                        "cached file size equal to metadata size and "
                        "cached file mtime later than metadata last "
                        "modification time."
                    )
                    ret = __utils__["s3.query"](
                        key=key,
                        keyid=keyid,
                        kms_keyid=keyid,
                        method="HEAD",
                        bucket=bucket_name,
                        service_url=service_url,
                        verify_ssl=verify_ssl,
                        location=location,
                        path=urllib.parse.quote(path),
                        local_file=cached_file_path,
                        full_headers=True,
                        path_style=path_style,
                        https_enable=https_enable,
                    )
                    if ret is not None:
                        s3_file_mtime = s3_file_size = None
                        for header_name, header_value in ret["headers"].items():
                            name = header_name.strip()
                            value = header_value.strip()
                            if str(name).lower() == "last-modified":
                                s3_file_mtime = datetime.datetime.strptime(
                                    value, "%a, %d %b %Y %H:%M:%S %Z"
                                )
                            elif str(name).lower() == "content-length":
                                s3_file_size = int(value)
                        if (s3_file_size and cached_file_size == s3_file_size) and (
                            s3_file_mtime and cached_file_mtime > s3_file_mtime
                        ):
                            log.info(
                                "%s - %s : %s skipped download since cached file size "
                                "equal to and mtime after s3 values",
                                bucket_name,
                                saltenv,
                                path,
                            )
                            return

    # ... or get the file from S3
    __utils__["s3.query"](
        key=key,
        keyid=keyid,
        kms_keyid=keyid,
        bucket=bucket_name,
        service_url=service_url,
        verify_ssl=verify_ssl,
        location=location,
        path=urllib.parse.quote(path),
        local_file=cached_file_path,
        path_style=path_style,
        https_enable=https_enable,
    )


def _trim_env_off_path(paths, saltenv, trim_slash=False):
    """
    Return a list of file paths with the saltenv directory removed
    """
    env_len = None if _is_env_per_bucket() else len(saltenv) + 1
    slash_len = -1 if trim_slash else None

    return [d[env_len:slash_len] for d in paths]


def _is_env_per_bucket():
    """
    Return the configuration mode, either buckets per environment or a list of
    buckets that have environment dirs in their root
    """

    buckets = _get_buckets()
    if isinstance(buckets, dict):
        return True
    elif isinstance(buckets, list):
        return False
    else:
        raise ValueError("Incorrect s3.buckets type given in config")
