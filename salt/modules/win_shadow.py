'''
Manage the shadow file
'''

import os

def __virtual__():
    '''
    Only works on Windows systems
    '''
    if __grains__['os'] == 'Windows':
        return 'shadow'
    return False


def info(name):
    '''
    Return information for the specified user
    This is just returns dummy data so that it states can work.

    CLI Example::

        salt '*' shadow.info root
    '''
    ret = {
            'name': name,
            'pwd': '',
            'lstchg': '',
            'min': '',
            'max': '',
            'warn': '',
            'inact': '',
            'expire': ''}
    return ret


def set_password(name, password):
    '''
    Set the password for a named user. The password must be a properly defined
    hash, the password hash can be generated with this command:
    ``openssl passwd -1 <plaintext password>``

    CLI Example::

        salt '*' shadow.set_password root $1$UYCIxa628.9qXjpQCjM4a..
    '''
    cmd = 'net user {0} {1}'.format(name, password)
    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']
