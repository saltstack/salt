'''
Module for managing user's passwords.
'''
# Import Python Libs
import os

# Import Salt libs
import salt.utils
from salt.exceptions import CommandExecutionError
from salt.grains.extra import shell as shell_grain


# Load in default options for the module
__opts__ = {
    'password.expire': 'foo'
}
# Load the outputters for the module
__outputter__ = {
    'expire': 'txt',
}


def expire(name):
    '''
    Expire the specified user's password

    CLI Example::

        salt '*' password.expire "thomas"
    '''
    uname = name
    cmd = 'passwd' + ' -e ' + uname
    out = __salt__['cmd.run'](cmd).split('\n')
    ret = out[0].split(': ')
    return ret[1]


