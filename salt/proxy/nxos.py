from __future__ import absolute_import
import re

from salt.utils.pycrypto import gen_hash
from salt.utils.vt_helper import SSHConnection
from salt.utils.vt import TerminalException

import logging
log = logging.getLogger(__file__)

__proxyenabled__ = ['nxos']
__virtualname__ = 'nxos'
DETAILS = {}
GRAINS_CACHE = {}


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    log.info('nxos proxy __virtual__() called...')

    return __virtualname__


def init(opts):
    '''
    Required.
    Can be used to initialize the server connection.
    '''
    try:
        DETAILS['server'] = SSHConnection(
            host=opts['proxy']['host'],
            username=opts['proxy']['username'],
            password=opts['proxy']['password'],
            ssh_args=opts['proxy']['ssh_args'],
            prompt='{0}.*#'.format(opts['proxy']['hostname']))
        out, err = DETAILS['server'].sendline('terminal length 0')

    except TerminalException as e:
        log.error(e)
        return False


def ping():
    '''
    Required.
    Ping the device on the other end of the connection
    '''
    try:
        out, err = DETAILS['server'].sendline('show ver')
        return True
    except TerminalException as e:
        log.error(e)
        return False


def shutdown(opts):
    '''
    Disconnect
    '''
    DETAILS['server'].close_connection()


def sendline(command):
    out, err = DETAILS['server'].sendline(command)
    _, out = out.split('\n', 1)
    out, _, _ = out.rpartition('\n')
    return out


def grains():
    if not GRAINS_CACHE:
        return _grains()
    return GRAINS_CACHE


def grains_refresh():
    '''
    Refresh the grains from the proxy device.
    '''
    GRAINS_CACHE = {}
    return grains()


def _grains():
    ret = __salt__['nxos.system_info']()
    GRAINS_CACHE.update(ret)
    return GRAINS_CACHE


def get_user(username):
    return sendline('show run | include "^username {0} password 5 "'.format(username))


def check_password(username, password, encrypted=False):
    hash_algorithms = {'1': 'md5',
                       '2a': 'blowfish',
                       '5': 'sha256',
                       '6': 'sha512',}
    password_line = get_user(username)
    if not password_line:
        return None
    cur_hash = re.search('(\$[0-6](?:\$[^$ ]+)+)', password_line).group(0)
    if encrypted is False:
        hash_type, cur_salt, hashed_pass = re.search('^\$([0-6])\$([^$]+)\$(.*)$', cur_hash).groups()
        new_hash = gen_hash(crypt_salt=cur_salt, password=password, algorithm=hash_algorithms[hash_type])
    else:
        new_hash = password
    if new_hash == cur_hash:
        return True
    return False


def set_password(username, password, encrypted=False, crypt_salt=None, algorithm='sha256', role=None):
    if encrypted is False:
        hashed_pass = gen_hash(crypt_salt=crypt_salt, password=password, algorithm=algorithm)
    else:
        hashed_pass = password
    password_line = get_user(username)
    if not password_line:
        remove_first = False
        password_line = 'username {0} password 5 {1}'.format(username, hashed_pass)
        if role is not None:
            password_line += ' role {0}'.format(role)
    else:
        remove_first = True
        password_line, _ = re.subn('\$[0-6](?:\$[^$ ]+)+', hashed_pass, password_line)
    try:
        sendline('config terminal')
        if remove_first is True:
            sendline('no username {0}'.format(name))
        ret = sendline(password_line)
        sendline('end')
        return '\n'.join([password_line, ret])
    except TerminalException as e:
        log.error(e)
        return False
