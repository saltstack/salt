# -*- coding: utf-8 -*-
'''
Swift utility class
===================
Author: Anthony Stanton <anthony.stanton@gmail.com>
'''

# Import third party libs
HAS_SWIFT = False
try:
    from swiftclient import client
    HAS_SWIFT = True
except ImportError:
    pass

# Import python libs
import time
import logging
from sys import stdout
from os import makedirs
from os.path import dirname, isdir

# Import salt libs
import salt.utils

# Get logging started
log = logging.getLogger(__name__)


def check_swift():
    return HAS_SWIFT

def mkdirs(path):
    try:
        makedirs(path)
    except OSError as err:
        if err.errno != EEXIST:
            raise

def _sanitize(kwargs):
    variables = (
        'user', 'key', 'authurl', 
        'retries', 'preauthurl', 'preauthtoken', 'snet',
        'starting_backoff', 'max_backoff', 'tenant_name',
        'os_options', 'auth_version', 'cacert',
        'insecure', 'ssl_compression'
    )
    ret = {}
    for var in kwargs.keys():
        if var in variables:
            ret[var] = kwargs[var]

    return ret

# Function alias to not shadow built-ins
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
        if not HAS_SWIFT:
            return None

        self.kwargs = kwargs.copy()
        self.kwargs['user'] = user
        self.kwargs['password'] = password
        self.kwargs['tenant_name'] = tenant_name
        self.kwargs['authurl'] = auth_url
        self.kwargs['auth_version'] = auth_version
        if not 'key' in self.kwargs.keys():
            self.kwargs['key'] = password

        self.kwargs = _sanitize(self.kwargs)

        self.conn = client.Connection(**self.kwargs)

    def get_account(self):
        '''
        List Swift containers
        '''
        try:
            listing = self.conn.get_account()
            return listing
        except Exception as exc:
            log.error('There was an error::')
            if hasattr(exc, 'code') and hasattr(exc, 'msg'):
                log.error('    Code: {0}: {1}'.format(exc.code, exc.msg))
            log.error('    Content: \n{0}'.format(getattr(exc, 'read', lambda: str(exc))()))
            return False

    def get_container(self, cont):
        '''
        List files in a new Swift container
        '''
        try:
            listing = self.conn.get_container(cont)
            return listing
        except Exception as exc:
            log.error('There was an error::')
            if hasattr(exc, 'code') and hasattr(exc, 'msg'):
                log.error('    Code: {0}: {1}'.format(exc.code, exc.msg))
            log.error('    Content: \n{0}'.format(getattr(exc, 'read', lambda: str(exc))()))
            return False

    def put_container(self, cont, metadata=None):
        '''
        Create a new Swift container
        '''
        try:
            self.conn.put_container(cont)
            return True
        except Exception as exc:      
            log.error('There was an error::')
            if hasattr(exc, 'code') and hasattr(exc, 'msg'):
                log.error('    Code: {0}: {1}'.format(exc.code, exc.msg))
            log.error('    Content: \n{0}'.format(getattr(exc, 'read', lambda: str(exc))()))
            return False

    def delete_container(self, cont):
        '''
        Delete a Swift container
        '''
        try:
            self.conn.delete_container(cont)
            return True
        except Exception as exc:
            log.error('There was an error::')
            if hasattr(exc, 'code') and hasattr(exc, 'msg'):
                log.error('    Code: {0}: {1}'.format(exc.code, exc.msg))
            log.error('    Content: \n{0}'.format(getattr(exc, 'read', lambda: str(exc))()))
            return False

    def post_container(self, cont, metadata=None):
        pass

    def head_container(self, cont):
        pass

    def get_object(self, cont, obj, local_file=None, return_bin=False):
        '''
        Retrieve a file from Swift
        '''
        try:
            if local_file == None and return_bin == False:
                return False

            headers, body = self.conn.get_object(cont, obj, resp_chunk_size=65536)

            if return_bin == True:
                fp = stdout
            else:
                dirpath = dirname(local_file)
                if dirpath and not isdir(dirpath):
                    mkdirs(dirpath)
                fp = open(local_file, 'wb')

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

    def put_object(self, cont, obj, local_file, content_type=None, metadata=None):
        '''
        Upload a file to Swift
        '''
        try:
            fp = open(local_file, 'rb')
            self.conn.put_object(cont, obj, fp)
            fp.close()
            return True
        except Exception as exc:      
            log.error('There was an error::')
            if hasattr(exc, 'code') and hasattr(exc, 'msg'):
                log.error('    Code: {0}: {1}'.format(exc.code, exc.msg))
            log.error('    Content: \n{0}'.format(getattr(exc, 'read', lambda: str(exc))()))
            return False


    def delete_object(self, cont, obj):
        '''
        Upload a file to Swift
        '''
        try:
            self.conn.delete_object(cont, obj)
            return True
        except Exception as exc:      
            log.error('There was an error::')
            if hasattr(exc, 'code') and hasattr(exc, 'msg'):
                log.error('    Code: {0}: {1}'.format(exc.code, exc.msg))
            log.error('    Content: \n{0}'.format(getattr(exc, 'read', lambda: str(exc))()))
            return False

    def head_object(self, cont, obj):
        pass

    def post_object(self, cont, obj, metadata):
        pass



#The following is a list of functions that need to be incorporated in the
#swift module. This list should be updated as functions are added.
#
#    delete               Delete a container or objects within a container.
#    download             Download objects from containers.
#    list                 Lists the containers for the account or the objects
#                         for a container.
#    post                 Updates meta information for the account, container,
#                         or object; creates containers if not present.
#    stat                 Displays information for the account, container,
#                         or object.
#    upload               Uploads files or directories to the given container
#    capabilities         List cluster capabilities.
