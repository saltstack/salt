# -*- coding: utf-8 -*-
'''
Keyring Database Module
'''

# import python libs
import logging

try:
    import keyring
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

log = logging.getLogger(__name__)

__func_alias__ = {
    'set_': 'set'
}

__virtualname__ = 'keyring'


def __virtual__():
    '''
    Only load the module if keyring is installed
    '''
    if HAS_LIBS:
        return __virtualname__
    return False


def set_(key, value, service=None, profile=None):
    '''
    Set a key/value pair in a keyring service
    '''
    service = _get_service(service, profile)
    keyring.set_password(service, key, value)


def get(key, service=None, profile=None):
    '''
    Get a value from a keyring service
    '''
    service = _get_service(service, profile)
    return keyring.get_password(service, key)


def _get_service(service, profile):
    '''
    Get a service name
    '''
    if isinstance(profile, dict) and 'service' in profile:
        return profile['service']

    return service
