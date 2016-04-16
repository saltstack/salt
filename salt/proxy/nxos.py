# -*- coding: utf-8 -*-
'''
Proxy Minion for Cisco NX OS Switches

.. versionadded: Carbon

The Cisco NX OS Proxy Minion uses the built in SSHConnection module in `salt.utils.vt_helper`

To configure the proxy minion, include the following in

.. code-block:: yaml
    proxy:
      proxytype: nxos
      host: 192.168.187.100
      username: admin
      password: admin
      prompt_name: switch
      ssh_args: '-o PubkeyAuthentication=no'
      key_accept: True

proxytype
    (REQUIRED) Use this proxy minion `nxos`

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
the :doc:`salt.modules.nxos</ref/modules/all/salt.modules.nxos>` execution module.

.. note::
    The option `proxy_merge_grains_in_module: True` is required to have the NXOS
    grains be availble from the proxy minion, for the Carbon release.  For
    Nitrogen, the setting will be True by default.

.. note:
    If `multiprocessing: True` is set for the proxy minion config, each forked
    worker will open up a new connection to the Cisco NX OS Switch.  If you
    only want one consistent connection used for everything, use
    `multiprocessing: False`

'''
from __future__ import absolute_import
import multiprocessing
import re

import salt.utils
from salt.utils.pycrypto import gen_hash, secure_password
from salt.utils.vt_helper import SSHConnection
from salt.utils.vt import TerminalException

import logging
log = logging.getLogger(__file__)

__proxyenabled__ = ['nxos']
__virtualname__ = 'nxos'
DETAILS = {'grains_cache': {}}


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    log.info('nxos proxy __virtual__() called...')

    if __opts__.get('proxy_merge_grains_in_module', False) is False:
        salt.utils.warn_until(
            'Nitrogen',
            'To use grains with the NXOS proxy minion, '
            '`proxy_merge_grains_in_module: True` must be set in the '
            'proxy minion config.'
        )

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
            prompt='{0}.*#'.format(opts['proxy']['prompt_name']))
        out, err = DETAILS[_worker_name()].sendline('terminal length 0')

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

        salt '*' nxos.cmd ping
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

        salt '*' nxos.cmd sendline 'show run | include "^username admin password"'
    '''
    if ping() is False:
        init()
    out, err = DETAILS[_worker_name()].sendline(command)
    _, out = out.split('\n', 1)
    out, _, _ = out.rpartition('\n')
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


def get_user(username):
    '''
    Get username line from switch

    .. code-block: bash

        salt '*' nxos.cmd get_user username=admin
    '''
    return sendline('show run | include "^username {0} password 5 "'.format(username))


def get_roles(username):
    '''
    Get roles that the username is assigned from switch

    .. code-block: bash

        salt '*' nxos.cmd get_roles username=admin
    '''
    info = sendline('show user-account {0}'.format(username))
    roles = re.search(r'^\s*roles:(.*)$', info, re.MULTILINE)
    if roles:
        roles = roles.group(1).strip().split(' ')
    else:
        roles = []
    return roles


def check_password(username, password, encrypted=False):
    '''
    Check if passed password is the one assigned to user

    .. code-block: bash

        salt '*' nxos.cmd check_password username=admin password=admin
        salt '*' nxos.cmd check_password username=admin \
            password='$5$2fWwO2vK$s7.Hr3YltMNHuhywQQ3nfOd.gAPHgs3SOBYYdGT3E.A' \
            encrypted=True
    '''
    hash_algorithms = {'1': 'md5',
                       '2a': 'blowfish',
                       '5': 'sha256',
                       '6': 'sha512', }
    password_line = get_user(username)
    if not password_line:
        return None
    if '!!' in password_line:
        return False
    cur_hash = re.search(r'(\$[0-6](?:\$[^$ ]+)+)', password_line).group(0)
    if encrypted is False:
        hash_type, cur_salt, hashed_pass = re.search(r'^\$([0-6])\$([^$]+)\$(.*)$', cur_hash).groups()
        new_hash = gen_hash(crypt_salt=cur_salt, password=password, algorithm=hash_algorithms[hash_type])
    else:
        new_hash = password
    if new_hash == cur_hash:
        return True
    return False


def check_role(username, role):
    '''
    Check if user is assigned a specific role on switch

    .. code-block:: bash

        salt '*' nxos.cmd check_role username=admin role=network-admin
    '''
    return role in get_roles(username)


def set_password(username, password, encrypted=False, role=None, crypt_salt=None, algorithm='sha256'):
    '''
    Set users password on switch

    .. code-block:: bash

        salt '*' nxos.cmd set_password admin TestPass
        salt '*' nxos.cmd set_password admin \
            password='$5$2fWwO2vK$s7.Hr3YltMNHuhywQQ3nfOd.gAPHgs3SOBYYdGT3E.A' \
            encrypted=True
    '''
    password_line = get_user(username)
    if encrypted is False:
        if crypt_salt is None:
            # NXOS does not like non alphanumeric characters.  Using the random module from pycrypto
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


def remove_user(username):
    '''
    Remove user from switch

    .. code-block:: bash

        salt '*' nxos.cmd remove_user username=daniel
    '''
    try:
        sendline('config terminal')
        user_line = 'no username {0}'.format(username)
        ret = sendline(user_line)
        sendline('end')
        sendline('copy running-config startup-config')
        return '\n'.join([user_line, ret])
    except TerminalException as e:
        log.error(e)
        return 'Failed to set password'


def set_role(username, role):
    '''
    Assign role to username

    .. code-block:: bash

        salt '*' nxos.cmd set_role username=daniel role=vdc-admin
    '''
    try:
        sendline('config terminal')
        role_line = 'username {0} role {1}'.format(username, role)
        ret = sendline(role_line)
        sendline('end')
        sendline('copy running-config startup-config')
        return '\n'.join([role_line, ret])
    except TerminalException as e:
        log.error(e)
        return 'Failed to set password'


def unset_role(username, role):
    '''
    Remove role from username

    .. code-block:: bash

        salt '*' nxos.cmd unset_role username=daniel role=vdc-admin
    '''
    try:
        sendline('config terminal')
        role_line = 'no username {0} role {1}'.format(username, role)
        ret = sendline(role_line)
        sendline('end')
        sendline('copy running-config startup-config')
        return '\n'.join([role_line, ret])
    except TerminalException as e:
        log.error(e)
        return 'Failed to set password'


def show_run():
    '''
    Shortcut to run `show run` on switch

    .. code-block:: bash

        salt '*' nxos.cmd show_run
    '''
    try:
        ret = sendline('show run')
    except TerminalException as e:
        log.error(e)
        return 'Failed to "show run"'
    return ret


def show_ver():
    '''
    Shortcut to run `show ver` on switch

    .. code-block:: bash

        salt '*' nxos.cmd show_ver
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

        salt '*' nxos.cmd add_config 'snmp-server community TESTSTRINGHERE group network-operator'

    .. note::
        For more than one config added per command, lines should be a list.
    '''
    if not isinstance(lines, list):
        lines = [lines]
    try:
        sendline('config terminal')
        for line in lines:
            sendline(line)

        sendline('end')
        sendline('copy running-config startup-config')
    except TerminalException as e:
        log.error(e)
        return False
    return True


def delete_config(lines):
    '''
    Delete one or more config lines to the switch running config

    .. code-block:: bash

        salt '*' nxos.cmd delete_config 'snmp-server community TESTSTRINGHERE group network-operator'

    .. note::
        For more than one config deleted per command, lines should be a list.
    '''
    if not isinstance(lines, list):
        lines = [lines]
    try:
        sendline('config terminal')
        for line in lines:
            sendline(' '.join(['no', line]))

        sendline('end')
        sendline('copy running-config startup-config')
    except TerminalException as e:
        log.error(e)
        return False
    return True


def find(pattern):
    '''
    Find all instances where the pattern is in the running command

    .. code-block:: bash

        salt '*' nxos.cmd find '^snmp-server.*$'

    .. note::
        This uses the `re.MULTILINE` regex format for python, and runs the
        regex against the whole show_run output.
    '''
    matcher = re.compile(pattern, re.MULTILINE)
    return matcher.findall(show_run())


def replace(old_value, new_value, full_match=False):
    '''
    Replace string or full line matches in switch's running config

    If full_match is set to True, then the whole line will need to be matched
    as part of the old value.

    .. code-block:: bash

        salt '*' nxos.cmd replace 'TESTSTRINGHERE' 'NEWTESTSTRINGHERE'
    '''
    if full_match is False:
        matcher = re.compile('^.*{0}.*$'.format(re.escape(old_value)), re.MULTILINE)
        repl = re.compile(re.escape(old_value))
    else:
        matcher = re.compile(old_value, re.MULTILINE)
        repl = re.compile(old_value)

    lines = {'old': [], 'new': []}
    for line in matcher.finditer(show_run()):
        lines['old'].append(line.group(0))
        lines['new'].append(repl.sub(new_value, line.group(0)))

    delete_config(lines['old'])
    add_config(lines['new'])

    return lines


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


def _parse_plugins(data):
    ret = {'plugins': []}
    plugins = _parser('plugin').search(data).group(0)
    matcher = re.compile('^  (?:([^,]+), )+([^\n]+)', re.MULTILINE)
    for line in matcher.finditer(plugins):
        ret['plugins'].extend(line.groups())
    return ret['plugins']


def system_info():
    '''
    Return system information for grains of the NX OS proxy minion

    .. code-block:: bash

        salt '*' nxos.system_info
    '''
    data = show_ver()
    info = {
        'software': _parse_software(data),
        'hardware': _parse_hardware(data),
        'plugins': _parse_plugins(data),
    }
    return info
