# -*- coding: utf-8 -*-
'''
.. versionadded:: 2015.8.0

Utilities for accessing storage container blobs on Azure
'''

# Import python libs
from __future__ import absolute_import
import logging
import inspect

# Import azure libs
HAS_LIBS = False
try:
    import azure
    HAS_LIBS = True
except ImportError:
    pass

# Import salt libs
import salt.ext.six as six
from salt.exceptions import SaltSystemExit

log = logging.getLogger(__name__)


def get_storage_conn(storage_account=None, storage_key=None, opts=None):
    '''
    .. versionadded:: 2015.8.0

    Return a storage_conn object for the storage account
    '''
    if opts is None:
        opts = {}

    if not storage_account:
        storage_account = opts.get('storage_account', None)
    if not storage_key:
        storage_key = opts.get('storage_key', None)

    return azure.storage.BlobService(storage_account, storage_key)


def list_blobs(storage_conn=None, **kwargs):
    '''
    .. versionadded:: 2015.8.0

    List blobs associated with the container
    '''
    if not storage_conn:
        storage_conn = get_storage_conn(opts=kwargs)

    if 'container' not in kwargs:
        raise SaltSystemExit(
            code=42,
            msg='An storage container name must be specified as "container"'
        )

    data = storage_conn.list_blobs(
        container_name=kwargs['container'],
        prefix=kwargs.get('prefix', None),
        marker=kwargs.get('marker', None),
        maxresults=kwargs.get('maxresults', None),
        include=kwargs.get('include', None),
        delimiter=kwargs.get('delimiter', None),
    )

    ret = {}
    for item in data.blobs:
        ret[item.name] = object_to_dict(item)
    return ret


def put_blob(storage_conn=None, **kwargs):
    '''
    .. versionadded:: 2015.8.0

    Upload a blob
    '''
    if not storage_conn:
        storage_conn = get_storage_conn(opts=kwargs)

    if 'container' not in kwargs:
        raise SaltSystemExit(code=42, msg='The blob container name must be specified as "container"')

    if 'name' not in kwargs:
        raise SaltSystemExit(code=42, msg='The blob name must be specified as "name"')

    if 'blob_path' not in kwargs and 'blob_content' not in kwargs:
        raise SaltSystemExit(
            code=42,
            msg='Either a path to a file needs to be passed in as "blob_path" '
            'or the contents of a blob as "blob_content."'
        )

    blob_kwargs = {
        'container_name': kwargs['container'],
        'blob_name': kwargs['name'],
        'cache_control': kwargs.get('cache_control', None),
        'content_language': kwargs.get('content_language', None),
        'content_md5': kwargs.get('content_md5', None),
        'x_ms_blob_content_type': kwargs.get('blob_content_type', None),
        'x_ms_blob_content_encoding': kwargs.get('blob_content_encoding', None),
        'x_ms_blob_content_language': kwargs.get('blob_content_language', None),
        'x_ms_blob_content_md5': kwargs.get('blob_content_md5', None),
        'x_ms_blob_cache_control': kwargs.get('blob_cache_control', None),
        'x_ms_meta_name_values': kwargs.get('meta_name_values', None),
        'x_ms_lease_id': kwargs.get('lease_id', None),
    }
    if 'blob_path' in kwargs:
        data = storage_conn.put_block_blob_from_path(
            file_path=kwargs['blob_path'],
            **blob_kwargs
        )
    elif 'blob_content' in kwargs:
        data = storage_conn.put_block_blob_from_bytes(
            blob=kwargs['blob_content'],
            **blob_kwargs
        )

    return data


def get_blob(storage_conn=None, **kwargs):
    '''
    .. versionadded:: 2015.8.0

    Download a blob
    '''
    if not storage_conn:
        storage_conn = get_storage_conn(opts=kwargs)

    if 'container' not in kwargs:
        raise SaltSystemExit(code=42, msg='The blob container name must be specified as "container"')

    if 'name' not in kwargs:
        raise SaltSystemExit(code=42, msg='The blob name must be specified as "name"')

    if 'local_path' not in kwargs and 'return_content' not in kwargs:
        raise SaltSystemExit(
            code=42,
            msg='Either a local path needs to be passed in as "local_path", '
            'or "return_content" to return the blob contents directly'
        )

    blob_kwargs = {
        'container_name': kwargs['container'],
        'blob_name': kwargs['name'],
        'snapshot': kwargs.get('snapshot', None),
        'x_ms_lease_id': kwargs.get('lease_id', None),
        'progress_callback': kwargs.get('progress_callback', None),
        'max_connections': kwargs.get('max_connections', 1),
        'max_retries': kwargs.get('max_retries', 5),
        'retry_wait': kwargs.get('retry_wait', 1),
    }

    if 'local_path' in kwargs:
        data = storage_conn.get_blob_to_path(
            file_path=kwargs['local_path'],
            open_mode=kwargs.get('open_mode', 'wb'),
            **blob_kwargs
        )
    elif 'return_content' in kwargs:
        data = storage_conn.get_blob_to_bytes(
            **blob_kwargs
        )

    return data


def object_to_dict(obj):
    '''
    .. versionadded:: 2015.8.0

    Convert an object to a dictionary
    '''
    if isinstance(obj, list) or isinstance(obj, tuple):
        ret = []
        for item in obj:
            #ret.append(obj.__dict__[item])
            ret.append(object_to_dict(obj))
    elif isinstance(obj, six.text_type):
        ret = obj.encode('ascii', 'replace'),
    elif isinstance(obj, six.string_types):
        ret = obj
    else:
        ret = {}
        for item in dir(obj):
            if item.startswith('_'):
                continue
            # This is ugly, but inspect.isclass() doesn't seem to work
            if inspect.isclass(obj) or 'class' in str(type(obj.__dict__.get(item))):
                ret[item] = object_to_dict(obj.__dict__[item])
            elif isinstance(obj.__dict__[item], six.text_type):
                ret[item] = obj.__dict__[item].encode('ascii', 'replace')
            else:
                ret[item] = obj.__dict__[item]
    return ret
