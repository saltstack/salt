# -*- coding: utf-8 -*-
'''
Apache Libcloud Storage Management
==================================

Connection module for Apache Libcloud Storage (object/blob) management for a full list
of supported clouds, see http://libcloud.readthedocs.io/en/latest/storage/supported_providers.html

Clouds include Amazon S3, Google Storage, Aliyun, Azure Blobs, Ceph, OpenStack swift

.. versionadded:: Oxygen

:configuration:
    This module uses a configuration profile for one or multiple Storage providers

    .. code-block:: yaml

        libcloud_storage:
            profile_test1:
              driver: google_storage
              key: GOOG0123456789ABCXYZ
              secret: mysecret
            profile_test2:
              driver: s3
              key: 12345
              secret: mysecret

:depends: apache-libcloud
'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

from __future__ import absolute_import

# Import Python libs
import logging

# Import salt libs
import salt.utils.compat
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)

# Import third party libs
REQUIRED_LIBCLOUD_VERSION = '1.5.0'
try:
    #pylint: disable=unused-import
    import libcloud
    from libcloud.storage.providers import get_driver
    #pylint: enable=unused-import
    if hasattr(libcloud, '__version__') and _LooseVersion(libcloud.__version__) < _LooseVersion(REQUIRED_LIBCLOUD_VERSION):
        raise ImportError()
    logging.getLogger('libcloud').setLevel(logging.CRITICAL)
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False


def __virtual__():
    '''
    Only load if libcloud libraries exist.
    '''
    if not HAS_LIBCLOUD:
        msg = ('A apache-libcloud library with version at least {0} was not '
               'found').format(REQUIRED_LIBCLOUD_VERSION)
        return (False, msg)
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)


def _get_driver(profile):
    config = __salt__['config.option']('libcloud_storage')[profile]
    cls = get_driver(config['driver'])
    args = config
    del args['driver']
    args['key'] = config.get('key')
    args['secret'] = config.get('secret', None)
    args['secure'] = config.get('secure', True)
    args['host'] = config.get('host', None)
    args['port'] = config.get('port', None)
    return cls(**args)


def list_containers(profile, **libcloud_kwargs):
    '''
    Return a list of containers.

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_containers method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.list_containers profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    containers = conn.list_containers(**libcloud_kwargs)
    ret = []
    for container in containers:
        ret.append({
            'name': container.name,
            'extra': container.extra
        })
    return ret


def list_container_objects(container_name, profile, **libcloud_kwargs):
    '''
    List container objects (e.g. files) for the given container_id on the given profile

    :param container_name: Container name
    :type  container_name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_container_objects method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.list_container_objects MyFolder profile1
    '''
    conn = _get_driver(profile=profile)
    container = conn.get_container(container_name)
    _sanitize_kwargs(libcloud_kwargs)
    objects = conn.list_container_objects(container, **libcloud_kwargs)
    ret = []
    for obj in objects:
        ret.append({
            'name': obj.name,
            'size': obj.size,
            'hash': obj.hash,
            'container': obj.container.name,
            'extra': obj.extra,
            'meta_data': obj.meta_data
        })
    return ret


def create_container(container_name, profile, **libcloud_kwargs):
    '''
    Create a container in the cloud

    :param container_name: Container name
    :type  container_name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's create_container method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.create_container MyFolder profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    container = conn.create_container(container_name, **libcloud_kwargs)
    return {
            'name': container.name,
            'extra': container.extra
            }


def get_container(container_name, profile, **libcloud_kwargs):
    '''
    List container details for the given container_name on the given profile

    :param container_name: Container name
    :type  container_name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's get_container method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.get_container MyFolder profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    container = conn.get_container(container_name, **libcloud_kwargs)
    return {
            'name': container.name,
            'extra': container.extra
            }


def get_container_object(container_name, object_name, profile, **libcloud_kwargs):
    '''
    Get the details for a container object (file or object in the cloud)

    :param container_name: Container name
    :type  container_name: ``str``

    :param object_name: Object name
    :type  object_name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's get_container_object method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.get_container_object MyFolder MyFile.xyz profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    obj = conn.get_container_object(container_name, object_name, **libcloud_kwargs)
    return {
        'name': obj.name,
        'size': obj.size,
        'hash': obj.hash,
        'container': obj.container.name,
        'extra': obj.extra,
        'meta_data': obj.meta_data}


def download_object(container_name, object_name, destination_path, profile,
                    overwrite_existing=False, delete_on_failure=True, **libcloud_kwargs):
    '''
    Download an object to the specified destination path.

    :param container_name: Container name
    :type  container_name: ``str``

    :param object_name: Object name
    :type  object_name: ``str``

    :param destination_path: Full path to a file or a directory where the
                                incoming file will be saved.
    :type destination_path: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param overwrite_existing: True to overwrite an existing file,
                                defaults to False.
    :type overwrite_existing: ``bool``

    :param delete_on_failure: True to delete a partially downloaded file if
                                the download was not successful (hash
                                mismatch / file size).
    :type delete_on_failure: ``bool``

    :param libcloud_kwargs: Extra arguments for the driver's download_object method
    :type  libcloud_kwargs: ``dict``

    :return: True if an object has been successfully downloaded, False
                otherwise.
    :rtype: ``bool``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.download_object MyFolder me.jpg /tmp/me.jpg profile1

    '''
    conn = _get_driver(profile=profile)
    obj = conn.get_object(container_name, object_name)
    _sanitize_kwargs(libcloud_kwargs)
    return conn.download_object(obj, destination_path, overwrite_existing, delete_on_failure, **libcloud_kwargs)


def upload_object(file_path, container_name, object_name, profile, extra=None,
                      verify_hash=True, headers=None, **libcloud_kwargs):
    '''
    Upload an object currently located on a disk.

    :param file_path: Path to the object on disk.
    :type file_path: ``str``

    :param container_name: Destination container.
    :type container_name: ``str``

    :param object_name: Object name.
    :type object_name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param verify_hash: Verify hash
    :type verify_hash: ``bool``

    :param extra: Extra attributes (driver specific). (optional)
    :type extra: ``dict``

    :param headers: (optional) Additional request headers,
        such as CORS headers. For example:
        headers = {'Access-Control-Allow-Origin': 'http://mozilla.com'}
    :type headers: ``dict``

    :param libcloud_kwargs: Extra arguments for the driver's upload_object method
    :type  libcloud_kwargs: ``dict``

    :return: The object name in the cloud
    :rtype: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.upload_object /file/to/me.jpg MyFolder me.jpg profile1

    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    container = conn.get_container(container_name)
    obj = conn.upload_object(file_path, container, object_name, extra, verify_hash, headers, **libcloud_kwargs)
    return obj.name


def delete_object(container_name, object_name, profile, **libcloud_kwargs):
    '''
    Delete an object in the cloud

    :param container_name: Container name
    :type  container_name: ``str``

    :param object_name: Object name
    :type  object_name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's delete_object method
    :type  libcloud_kwargs: ``dict``

    :return: True if an object has been successfully deleted, False
                otherwise.
    :rtype: ``bool``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.delete_object MyFolder me.jpg profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    obj = conn.get_object(container_name, object_name, **libcloud_kwargs)
    return conn.delete_object(obj)


def delete_container(container_name, profile, **libcloud_kwargs):
    '''
    Delete an object container in the cloud

    :param container_name: Container name
    :type  container_name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's delete_container method
    :type  libcloud_kwargs: ``dict``

    :return: True if an object container has been successfully deleted, False
                otherwise.
    :rtype: ``bool``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.delete_container MyFolder profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    container = conn.get_container(container_name)
    return conn.delete_container(container, **libcloud_kwargs)


def _sanitize_kwargs(kwargs):
    '''
    Remove internal arguments from the command line keyword listing

    :param kwargs: The keyword argument dictionary
    :type  kwargs: ``dict``
    '''
    clean = {}
    for key, val in kwargs.items():
        if key.startswith('__'):
            del kwargs[key]
    return kwargs
