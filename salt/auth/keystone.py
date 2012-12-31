'''Salt Keystone Authentication
Module to provide authentication using keystone as the backend.

Required python modules: keystoneclient
'''
try:
    from keystoneclient.v2_0 import client
    from keystoneclient.exceptions import AuthorizationFailure, Unauthorized
except ImportError:
    pass


def get_auth_url():
    '''
    Try and get the url from the config, else return localhost
    '''
    try:
        return __opts__['keystone.auth_url']
    except KeyError:
        return 'http://localhost:35357/v2.0'


def auth(username, password):
    '''
    Try and authenticate
    '''
    try:
        keystone = client.Client(username=username, password=password,
                                 auth_url=get_auth_url())
    except (AuthorizationFailure, Unauthorized):
        return False
    else:
        return keystone.authenticate()

if __name__ == '__main__':
    __opts__ = {}
    if auth('test', 'test'):
        print "Authenticated"
    else:
        print "Failed to authenticate"
