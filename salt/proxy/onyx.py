# -*- coding: utf-8 -*-
'''
Proxy Minion for Onyx OS Switches

.. versionadded: 2018.3.2 (Oxygen)

The Onyx OS Proxy Minion uses the built in SSHConnection module in :mod:`salt.utils.vt_helper <salt.utils.vt_helper>`

To configure the proxy minion:

.. code-block:: yaml

    proxy:
      proxytype: onyx
      host: 192.168.187.100
      username: admin
      password: admin
      prompt_name: switch
      ssh_args: '-o PubkeyAuthentication=no'
      key_accept: True

proxytype
    (REQUIRED) Use this proxy minion `onyx`

host
    (REQUIRED) ip address or hostname to connect to

username
    (REQUIRED) username to login with

password
    (REQUIRED) password to use to login with

prompt_name
    (REQUIRED) The name in the prompt on the switch.  By default, use your
    devices hostname.

ssh_args
    Any extra args to use to connect to the switch.

key_accept
    Whether or not to accept a the host key of the switch on initial login.
    Defaults to False.


The functions from the proxy minion can be run from the salt commandline using
the :mod:`salt.modules.onyx<salt.modules.onyx>` execution module.

.. note:
    If `multiprocessing: True` is set for the proxy minion config, each forked
    worker will open up a new connection to the Onyx OS Switch.  If you
    only want one consistent connection used for everything, use
    `multiprocessing: False`
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import multiprocessing
import re

# Import Salt libs
from salt.utils.pycrypto import gen_hash, secure_password
from salt.utils.vt_helper import SSHConnection
from salt.utils.vt import TerminalException
from pdb import set_trace as bp
log = logging.getLogger(__file__)

__proxyenabled__ = ['onyx']
__virtualname__ = 'onyx'
DETAILS = {'grains_cache': {}}


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    log.info('onyx proxy __virtual__() called...')

    return __virtualname__


def _worker_name():
    return multiprocessing.current_process().name


def init(opts=None):
    '''
    Required.
    Can be used to initialize the server connection.
    '''
    if opts is None:
        opts = __opts__
    try:
        DETAILS[_worker_name()] = SSHConnection(
            host=opts['proxy']['host'],
            username=opts['proxy']['username'],
            password=opts['proxy']['password'],
            key_accept=opts['proxy'].get('key_accept', False),
            ssh_args=opts['proxy'].get('ssh_args', ''),
            prompt='{0}.*(#|>) '.format(opts['proxy']['prompt_name']))
        out, err = DETAILS[_worker_name()].sendline('no cli session paging enable')

    except TerminalException as e:
        log.error(e)
        return False
    DETAILS['initialized'] = True


def initialized():
    return DETAILS.get('initialized', False)


def ping():
    '''
    Ping the device on the other end of the connection

    .. code-block: bash

        salt '*' onyx.cmd ping
    '''
    if _worker_name() not in DETAILS:
        init()
    try:
        return DETAILS[_worker_name()].conn.isalive()
    except TerminalException as e:
        log.error(e)
        return False


def shutdown(opts):
    '''
    Disconnect
    '''
    DETAILS[_worker_name()].close_connection()


def sendline(command):
    '''
    Run command through switch's cli

    .. code-block: bash

        salt '*' onyx.cmd sendline 'show run | include "username admin password 7"'
    '''
    if ping() is False:
        init()
    out, err = DETAILS[_worker_name()].sendline(command)
    return out


def grains():
    '''
    Get grains for proxy minion

    .. code-block: bash

        salt '*' nxos.cmd grains
    '''
    if not DETAILS['grains_cache']:
        ret = system_info()
        log.debug(ret)
        DETAILS['grains_cache'].update(ret)
    return {'nxos': DETAILS['grains_cache']}


def grains_refresh():
    '''
    Refresh the grains from the proxy device.

    .. code-block: bash

        salt '*' nxos.cmd grains_refresh
    '''
    DETAILS['grains_cache'] = {}
    return grains()


def enable():
    '''
    Shortcut to run `enable` on switch

    .. code-block:: bash

        salt '*' onyx.cmd enable
    '''
    try:
        ret = sendline('enable')
    except TerminalException as e:
        log.error(e)
        return 'Failed to run "enable" command on switch'
    return ret


def configure_terminal():
    '''
    Shortcut to run `configure terminal` on switch

    .. code-block:: bash

        salt '*' onyx.cmd configure_terminal
    '''
    try:
        ret = sendline('configure terminal ')
    except TerminalException as e:
        log.error(e)
        return 'Failed to enable configuration mode on switch'
    return ret


def configure_terminal_exit():
    '''
        Shortcut to run `exit` from configuration mode on switch

        .. code-block:: bash

            salt '*' onyx.cmd configure_terminal_exit
        '''
    try:
        ret = sendline('exit')
    except TerminalException as e:
        log.error(e)
        return 'Failed to exit form configure terminal mode on switch'
    return ret


def disable():
    '''
        Shortcut to run `disable` on switch

        .. code-block:: bash

            salt '*' onyx.cmd disable
        '''
    try:
        ret = sendline('disable')
    except TerminalException as e:
        log.error(e)
        return 'Failed to run "disable" command on switch'
    return ret


def get_user(username):
    '''
    Get username line from switch

    .. code-block: bash

        salt '*' onyx.cmd get_user username=admin
    '''
    try:
        enable()
        configure_terminal()
        cmd_out = sendline('show running-config | include "username {0} password 7"'.format(username))
        cmd_out.split('\n')
        user=cmd_out[1:-1]
        configure_terminal_exit()
        disable()
        return user
    except TerminalException as e:
        log.error(e)
        return 'Failed to get user'


def check_password(username, password, encrypted=False):
    '''
    Check if passed password is the one assigned to user

    .. code-block: bash

        salt '*' onyx.cmd check_password username=admin password=admin
        salt '*' onyx.cmd check_password username=admin \\
            password='$5$2fWwO2vK$s7.Hr3YltMNHuhywQQ3nfOd.gAPHgs3SOBYYdGT3E.A' \\
            encrypted=True
    '''
    hash_algorithms = {'1': 'md5',
                       '2a': 'blowfish',
                       '5': 'sha256',
                       '6': 'sha512', }
    user = get_user(username)
    password_line = user.split('\n')
    password_line = password_line[1]
    log.error("password_line: %s" % password_line)
    if not password_line:
        return None
    if '!!' in password_line:
        return False
    cur_hash = re.search(r'(\$[0-6](?:\$[^$ ]+)+)', str(password_line)).group(0)
    if encrypted is False:
        hash_type, cur_salt, hashed_pass = re.search(r'^\$([0-6])\$([^$]+)\$(.*)$', str(cur_hash)).groups()
        log.error("hash_type: %s" % hash_type)
        log.error("cur_salt: %s" % cur_salt)
        log.error("hashed_pass: %s" % hashed_pass)
        new_hash = gen_hash(crypt_salt=cur_salt, password=password, algorithm=hash_algorithms[hash_type])
        log.error("new_hash: %s" % new_hash)
    else:
        new_hash = password
    if new_hash == cur_hash:
        return True
    return False


def set_password(username, password, encrypted=False, role=None, crypt_salt=None, algorithm='sha256'):
    '''
    Set users password on switch

    .. code-block:: bash

        salt '*' onyx.cmd set_password admin TestPass
        salt '*' onyx.cmd set_password admin \\
            password='$5$2fWwO2vK$s7.Hr3YltMNHuhywQQ3nfOd.gAPHgs3SOBYYdGT3E.A' \\
            encrypted=True
    '''
    password_line = get_user(username)
    if encrypted is False:
        if crypt_salt is None:
            # onyx does not like non alphanumeric characters.  Using the random module from pycrypto
            # can lead to having non alphanumeric characters in the salt for the hashed password.
            crypt_salt = secure_password(8, use_random=False)
        hashed_pass = gen_hash(crypt_salt=crypt_salt, password=password, algorithm=algorithm)
    else:
        hashed_pass = password
    password_line = 'username {0} password 5 {1}'.format(username, hashed_pass)
    if role is not None:
        password_line += ' role {0}'.format(role)
    try:
        sendline('config terminal')
        ret = sendline(password_line)
        sendline('end')
        sendline('copy running-config startup-config')
        return '\n'.join([password_line, ret])
    except TerminalException as e:
        log.error(e)
        return 'Failed to set password'


def show_run():
    '''
    Shortcut to run `show run` on switch

    .. code-block:: bash

        salt '*' onyx.cmd show_run
    '''
    try:
        enable()
        configure_terminal()
        ret = sendline('show running-config')
        log.error("Ret Code For Run show run CMD: " + str(ret))
        configure_terminal_exit()
        disable()
    except TerminalException as e:
        log.error(e)
        return 'Failed to show running-config on switch'
    return ret


def show_ver():
    '''
    Shortcut to run `show ver` on switch

    .. code-block:: bash

        salt '*' onyx.cmd show_ver
    '''
    try:
        ret = sendline('show ver')
    except TerminalException as e:
        log.error(e)
        return 'Failed to "show ver"'
    return ret


def add_config(lines):
    '''
    Add one or more config lines to the switch running config

    .. code-block:: bash

        salt '*' onyx.cmd add_config 'snmp-server community TESTSTRINGHERE rw'

    .. note::
        For more than one config added per command, lines should be a list.
    '''
    if not isinstance(lines, list):
        lines = [lines]
    try:
        enable()
        configure_terminal()
        for line in lines:
            sendline(line)

        configure_terminal_exit()
        disable()
    except TerminalException as e:
        log.error(e)
        return False
    return True


def _parser(block):
    return re.compile('^{block}\n(?:^[ \n].*$\n?)+'.format(block=block), re.MULTILINE)


def _parse_software(data):
    ret = {'software': {}}
    software = _parser('Software').search(data).group(0)
    matcher = re.compile('^  ([^:]+): *([^\n]+)', re.MULTILINE)
    for line in matcher.finditer(software):
        key, val = line.groups()
        ret['software'][key] = val
    return ret['software']


def _parse_hardware(data):
    ret = {'hardware': {}}
    hardware = _parser('Hardware').search(data).group(0)
    matcher = re.compile('^  ([^:\n]+): *([^\n]+)', re.MULTILINE)
    for line in matcher.finditer(hardware):
        key, val = line.groups()
        ret['hardware'][key] = val
    return ret['hardware']



def system_info():
    '''
    Return system information for grains of the Onyx OS proxy minion

    .. code-block:: bash

        salt '*' onyx.system_info
    '''
    data = show_ver()
    info = {
        'software': 'Test',
        'hardware': '',#_parse_hardware(data),
    }
    return info
