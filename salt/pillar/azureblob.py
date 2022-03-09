"""
Use Azure Blob as a Pillar source.

.. versionadded:: 3001

:maintainer: <devops@eitr.tech>
:maturity: new
:depends:
    * `azure-storage-blob <https://pypi.org/project/azure-storage-blob/>`_ >= 12.0.0

The Azure Blob ext_pillar can be configured with the following parameters:

.. code-block:: yaml

    ext_pillar:
      - azureblob:
          container: 'test_container'
          connection_string: 'connection_string'
          multiple_env: False
          environment: 'base'
          blob_cache_expire: 30
          blob_sync_on_update: True

:param container: The name of the target Azure Blob Container.

:param connection_string: The connection string to use to access the specified Azure Blob Container.

:param multiple_env: Specifies whether the pillar should interpret top level folders as pillar environments.
    Defaults to false.

:param environment: Specifies which environment the container represents when in single environment mode. Defaults
    to 'base' and is ignored if multiple_env is set as True.

:param blob_cache_expire: Specifies expiration time of the Azure Blob metadata cache file. Defaults to 30s.

:param blob_sync_on_update: Specifies if the cache is synced on update. Defaults to True.

"""

import logging
import os
import pickle
import time
from copy import deepcopy

import salt.utils.files
import salt.utils.hashutils
from salt.pillar import Pillar

HAS_LIBS = False
try:
    # pylint: disable=no-name-in-module
    from azure.storage.blob import BlobServiceClient

    # pylint: enable=no-name-in-module
    HAS_LIBS = True
except ImportError:
    pass


__virtualname__ = "azureblob"

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_LIBS:
        return (
            False,
            "The following dependency is required to use the Azure Blob ext_pillar: "
            "Microsoft Azure Storage Blob >= 12.0.0 ",
        )

    return __virtualname__


def ext_pillar(
    minion_id,
    pillar,  # pylint: disable=W0613
    container,
    connection_string,
    multiple_env=False,
    environment="base",
    blob_cache_expire=30,
    blob_sync_on_update=True,
):
    """
    Execute a command and read the output as YAML.

    :param container: The name of the target Azure Blob Container.

    :param connection_string: The connection string to use to access the specified Azure Blob Container.

    :param multiple_env: Specifies whether the pillar should interpret top level folders as pillar environments.
        Defaults to false.

    :param environment: Specifies which environment the container represents when in single environment mode. Defaults
        to 'base' and is ignored if multiple_env is set as True.

    :param blob_cache_expire: Specifies expiration time of the Azure Blob metadata cache file. Defaults to 30s.

    :param blob_sync_on_update: Specifies if the cache is synced on update. Defaults to True.

    """
    # normpath is needed to remove appended '/' if root is empty string.
    pillar_dir = os.path.normpath(
        os.path.join(_get_cache_dir(), environment, container)
    )

    if __opts__["pillar_roots"].get(environment, []) == [pillar_dir]:
        return {}

    metadata = _init(
        connection_string, container, multiple_env, environment, blob_cache_expire
    )

    log.debug("Blob metadata: %s", metadata)

    if blob_sync_on_update:
        # sync the containers to the local cache
        log.info("Syncing local pillar cache from Azure Blob...")
        for saltenv, env_meta in metadata.items():
            for container, files in _find_files(env_meta).items():
                for file_path in files:
                    cached_file_path = _get_cached_file_name(
                        container, saltenv, file_path
                    )
                    log.info("%s - %s : %s", container, saltenv, file_path)
                    # load the file from Azure Blob if not in the cache or too old
                    _get_file_from_blob(
                        connection_string,
                        metadata,
                        saltenv,
                        container,
                        file_path,
                        cached_file_path,
                    )

        log.info("Sync local pillar cache from Azure Blob completed.")

    opts = deepcopy(__opts__)
    opts["pillar_roots"][environment] = (
        [os.path.join(pillar_dir, environment)] if multiple_env else [pillar_dir]
    )

    # Avoid recursively re-adding this same pillar
    opts["ext_pillar"] = [x for x in opts["ext_pillar"] if "azureblob" not in x]

    pil = Pillar(opts, __grains__, minion_id, environment)

    compiled_pillar = pil.compile_pillar(ext=False)

    return compiled_pillar


def _init(connection_string, container, multiple_env, environment, blob_cache_expire):
    """
    .. versionadded:: 3001

    Connect to Blob Storage and download the metadata for each file in all containers specified and
        cache the data to disk.

    :param connection_string: The connection string to use to access the specified Azure Blob Container.

    :param container: The name of the target Azure Blob Container.

    :param multiple_env: Specifies whether the pillar should interpret top level folders as pillar environments.
        Defaults to false.

    :param environment: Specifies which environment the container represents when in single environment mode. Defaults
        to 'base' and is ignored if multiple_env is set as True.

    :param blob_cache_expire: Specifies expiration time of the Azure Blob metadata cache file. Defaults to 30s.

    """
    cache_file = _get_containers_cache_filename(container)
    exp = time.time() - blob_cache_expire

    # Check if cache_file exists and its mtime
    if os.path.isfile(cache_file):
        cache_file_mtime = os.path.getmtime(cache_file)
    else:
        # If the file does not exist then set mtime to 0 (aka epoch)
        cache_file_mtime = 0

    expired = cache_file_mtime <= exp

    log.debug(
        "Blob storage container cache file %s is %sexpired, mtime_diff=%ss,"
        " expiration=%ss",
        cache_file,
        "" if expired else "not ",
        cache_file_mtime - exp,
        blob_cache_expire,
    )

    if expired:
        pillars = _refresh_containers_cache_file(
            connection_string, container, cache_file, multiple_env, environment
        )
    else:
        pillars = _read_containers_cache_file(cache_file)

    log.debug("Blob container retrieved pillars %s", pillars)

    return pillars


def _get_cache_dir():
    """
    .. versionadded:: 3001

    Get pillar cache directory. Initialize it if it does not exist.

    """
    cache_dir = os.path.join(__opts__["cachedir"], "pillar_azureblob")

    if not os.path.isdir(cache_dir):
        log.debug("Initializing Azure Blob Pillar Cache")
        os.makedirs(cache_dir)

    return cache_dir


def _get_cached_file_name(container, saltenv, path):
    """
    .. versionadded:: 3001

    Return the cached file name for a container path file.

    :param container: The name of the target Azure Blob Container.

    :param saltenv: Specifies which environment the container represents.

    :param path: The path of the file in the container.

    """
    file_path = os.path.join(_get_cache_dir(), saltenv, container, path)

    # make sure container and saltenv directories exist
    if not os.path.exists(os.path.dirname(file_path)):
        os.makedirs(os.path.dirname(file_path))

    return file_path


def _get_containers_cache_filename(container):
    """
    .. versionadded:: 3001

    Return the filename of the cache for container contents. Create the path if it does not exist.

    :param container: The name of the target Azure Blob Container.

    """
    cache_dir = _get_cache_dir()
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    return os.path.join(cache_dir, "{}-files.cache".format(container))


def _refresh_containers_cache_file(
    connection_string, container, cache_file, multiple_env=False, environment="base"
):
    """
    .. versionadded:: 3001

    Downloads the entire contents of an Azure storage container to the local filesystem.

    :param connection_string: The connection string to use to access the specified Azure Blob Container.

    :param container: The name of the target Azure Blob Container.

    :param cache_file: The path of where the file will be cached.

    :param multiple_env: Specifies whether the pillar should interpret top level folders as pillar environments.

    :param environment: Specifies which environment the container represents when in single environment mode. This is
        ignored if multiple_env is set as True.

    """
    try:
        # Create the BlobServiceClient object which will be used to create a container client
        blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )

        # Create the ContainerClient object
        container_client = blob_service_client.get_container_client(container)
    except Exception as exc:  # pylint: disable=broad-except
        log.error("Exception: %s", exc)
        return False

    metadata = {}

    def _walk_blobs(saltenv="base", prefix=None):
        # Walk the blobs in the container with a generator
        blob_list = container_client.walk_blobs(name_starts_with=prefix)

        # Iterate over the generator
        while True:
            try:
                blob = next(blob_list)
            except StopIteration:
                break

            log.debug("Raw blob attributes: %s", blob)

            # Directories end with "/".
            if blob.name.endswith("/"):
                # Recurse into the directory
                _walk_blobs(prefix=blob.name)
                continue

            if multiple_env:
                saltenv = "base" if (not prefix or prefix == ".") else prefix[:-1]

            if saltenv not in metadata:
                metadata[saltenv] = {}

            if container not in metadata[saltenv]:
                metadata[saltenv][container] = []

            metadata[saltenv][container].append(blob)

    _walk_blobs(saltenv=environment)

    # write the metadata to disk
    if os.path.isfile(cache_file):
        os.remove(cache_file)

    log.debug("Writing Azure blobs pillar cache file")

    with salt.utils.files.fopen(cache_file, "wb") as fp_:
        pickle.dump(metadata, fp_)

    return metadata


def _read_containers_cache_file(cache_file):
    """
    .. versionadded:: 3001

    Return the contents of the containers cache file.

    :param cache_file: The path for where the file will be cached.

    """
    log.debug("Reading containers cache file")

    with salt.utils.files.fopen(cache_file, "rb") as fp_:
        data = pickle.load(fp_)

    return data


def _find_files(metadata):
    """
    .. versionadded:: 3001

    Looks for all the files in the Azure Blob container cache metadata.

    :param metadata: The metadata for the container files.

    """
    ret = {}

    for container, data in metadata.items():
        if container not in ret:
            ret[container] = []

        # grab the paths from the metadata
        file_paths = [k["name"] for k in data]
        # filter out the dirs
        ret[container] += [k for k in file_paths if not k.endswith("/")]

    return ret


def _find_file_meta(metadata, container, saltenv, path):
    """
    .. versionadded:: 3001

    Looks for a file's metadata in the Azure Blob Container cache file.

    :param metadata: The metadata for the container files.

    :param container: The name of the target Azure Blob Container.

    :param saltenv: Specifies which environment the container represents.

    :param path: The path of the file in the container.

    """
    env_meta = metadata[saltenv] if saltenv in metadata else {}
    container_meta = env_meta[container] if container in env_meta else {}

    for item_meta in container_meta:
        item_meta = dict(item_meta)
        if "name" in item_meta and item_meta["name"] == path:
            return item_meta


def _get_file_from_blob(
    connection_string, metadata, saltenv, container, path, cached_file_path
):
    """
    .. versionadded:: 3001

    Downloads the entire contents of an Azure storage container to the local filesystem.

    :param connection_string: The connection string to use to access the specified Azure Blob Container.

    :param metadata: The metadata for the container files.

    :param saltenv: Specifies which environment the container represents when in single environment mode. This is
        ignored if multiple_env is set as True.

    :param container: The name of the target Azure Blob Container.

    :param path: The path of the file in the container.

    :param cached_file_path: The path of where the file will be cached.

    """
    # check the local cache...
    if os.path.isfile(cached_file_path):
        file_meta = _find_file_meta(metadata, container, saltenv, path)
        file_md5 = (
            "".join(list(filter(str.isalnum, file_meta["etag"]))) if file_meta else None
        )

        cached_md5 = salt.utils.hashutils.get_hash(cached_file_path, "md5")

        # hashes match we have a cache hit
        log.debug(
            "Cached file: path=%s, md5=%s, etag=%s",
            cached_file_path,
            cached_md5,
            file_md5,
        )
        if cached_md5 == file_md5:
            return

    try:
        # Create the BlobServiceClient object which will be used to create a container client
        blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )

        # Create the ContainerClient object
        container_client = blob_service_client.get_container_client(container)

        # Create the BlobClient object
        blob_client = container_client.get_blob_client(path)
    except Exception as exc:  # pylint: disable=broad-except
        log.error("Exception: %s", exc)
        return False

    with salt.utils.files.fopen(cached_file_path, "wb") as outfile:
        outfile.write(blob_client.download_blob().readall())

    return
