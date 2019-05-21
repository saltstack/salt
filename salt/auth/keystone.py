# -*- coding: utf-8 -*-
'''
Provide authentication using OpenStack Keystone

:depends:   - keystoneclient Python module
'''

from __future__ import absolute_import, print_function, unicode_literals
try:
    from keystoneclient.v2_0 import client as clientv2
    from keystoneclient.v3 import client as clientv3
    from keystoneclient.exceptions import AuthorizationFailure, Unauthorized
except ImportError:
    pass


def get_auth_url():
    '''
    Try and get the URL from the config, else return localhost
    '''
    try:
        return __opts__['keystone.auth_url']
    except KeyError:
        return 'http://localhost:35357/v2.0'


def get_api_version():
    '''
    Try and get the API version from the config, else return v2
    Valid values v2, v3
    '''
    try:
        return __opts__['keystone.api_version']
    except KeyError:
        return 'v2'


def auth(username, password):
    '''
    Try and authenticate
    '''
    try:
        if get_api_version() == 'v2':
            keystone = clientv2.Client(username=username, password=password,
                                 auth_url=get_auth_url())
        elif get_api_version() == 'v3':
            keystone = clientv3.Client(username=username, password=password,
                                 auth_url=get_auth_url())
        else:
            return False
        return keystone.authenticate()
    except (AuthorizationFailure, Unauthorized):
        return False


if __name__ == '__main__':
    __opts__ = {}
    if auth('test', 'test'):
        print("Authenticated")
    else:
        print("Failed to authenticate")
