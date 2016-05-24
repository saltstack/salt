# -*- coding: utf-8 -*-
'''
Swift utility class
===================
Author: Anthony Stanton <anthony.stanton@gmail.com>
'''
from __future__ import absolute_import

# Import python libs
import logging
from sys import stdout
from os import makedirs
from os.path import dirname, isdir
from errno import EEXIST

# Import Salt libs
import salt.utils

# Get logging started
log = logging.getLogger(__name__)

# Import Swift client libs
HAS_SHADE = False
try:
    import shade

    HAS_SHADE = True
except ImportError:
    pass


def check_swift():
    return HAS_SHADE


def mkdirs(path):
    try:
        makedirs(path)
    except OSError as err:
        if err.errno != EEXIST:
            raise


# we've been playing fast and loose with kwargs, but the swiftclient isn't
# going to accept any old thing
def _sanitize(kwargs):
    variables = (
        'user', 'key', 'authurl',
        'retries', 'preauthurl', 'preauthtoken', 'snet',
        'starting_backoff', 'max_backoff', 'tenant_name',
        'os_options', 'auth_version', 'cacert',
        'insecure', 'ssl_compression'
    )
    ret = {}
    for var in kwargs:
        if var in variables:
            ret[var] = kwargs[var]

    return ret


class SaltSwift(object):
    '''
    Class for all swiftclient functions
    '''

    def __init__(
            self,
            user,
            tenant_name,
            auth_url,
            password=None,
            auth_version=2,
            **kwargs
    ):
        '''
        Set up openstack credentials
        '''
        if not HAS_SHADE:
            log.error('Error:: unable to find swiftclient. Try installing it from the appropriate repository.')
            return None

        self.kwargs = kwargs.copy()
        self.kwargs['user'] = user
        self.kwargs['password'] = password
        self.kwargs['tenant_name'] = tenant_name
        self.kwargs['authurl'] = auth_url
        self.kwargs['auth_version'] = auth_version
        if 'key' not in self.kwargs:
            self.kwargs['key'] = password

        self.kwargs = _sanitize(self.kwargs)

        self.conn = shade.openstack_cloud(**self.kwargs)

    def get_account(self, full_listing=True):
        '''
        List Swift containers
        '''
        return self.conn.list_containers(full_listing=full_listing)

    def get_container(self, cont):
        '''
        List files in a Swift container
        '''
        return self.conn.get_container(name=cont)

    def put_container(self, cont, public=False):
        '''
        Create a new Swift container
        '''
        return self.conn.create_container(cont, public=public)

    def delete_container(self, cont):
        '''
        Delete a Swift container
        '''
        return self.conn.delete_container(cont)

    def post_container(self, cont, headers=None):
        '''
        Update container metadata
        '''
        return self.conn.update_container(cont, headers=headers or {})

    def head_container(self, cont):
        '''
        Get container metadata
        '''
        return self.conn.get_container(cont)

    def get_object(self, cont, obj, local_file=None, return_bin=False):
        '''
        Retrieve a file from Swift
        '''
        try:
            if local_file is None and return_bin is False:
                return False

            _, body = self.conn.get_object(cont, obj, resp_chunk_size=65536)

            if return_bin is True:
                fp = stdout
            else:
                dirpath = dirname(local_file)
                if dirpath and not isdir(dirpath):
                    mkdirs(dirpath)
                fp = salt.utils.fopen(local_file, 'wb')

            read_length = 0
            for chunk in body:
                read_length += len(chunk)
                fp.write(chunk)
            fp.close()
            return True

        # ClientException
        # file/dir exceptions
        except Exception as exc:
            log.error('There was an error::')
            if hasattr(exc, 'code') and hasattr(exc, 'msg'):
                log.error('    Code: {0}: {1}'.format(exc.code, exc.msg))
            log.error('    Content: \n{0}'.format(getattr(exc, 'read', lambda: str(exc))()))
            return False

    def put_object(self, cont, obj, local_file):
        '''
        Upload a file to Swift
        '''
        return self.conn.create_object(container=cont, name=obj, filename=local_file)

    def delete_object(self, cont, obj):
        '''
        Delete a file from Swift
        '''
        return self.conn.delete_object(cont, obj)

    def head_object(self, cont, obj):
        '''
        Get object metadata
        '''
        return self.conn.get_object_metadata(cont, obj)

    def post_object(self, cont, obj, metadata):
        '''
        Update object metadata
        '''
        pass
