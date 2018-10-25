# -*- coding: utf-8 -*-
'''
Proxy Minion for Onyx OS Switches

.. versionadded: Neon

The Onyx OS Proxy Minion uses the built in SSHConnection module
in :mod:`salt.utils.vt_helper <salt.utils.vt_helper>`

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
    worker will open up a new connection to the Cisco NX OS Switch.  If you
    only want one consistent connection used for everything, use
    `multiprocessing: False`

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import multiprocessing
import re

# Import Salt libs
from salt.utils.vt_helper import SSHConnection
from salt.utils.vt import TerminalException
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
        DETAILS[_worker_name()].sendline('no cli session paging enable')

    except TerminalException as e:
        log.error(e)
        return False
    DETAILS['initialized'] = True


def initialized():
    '''
        module initialization
    '''
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


def shutdown():
    '''
    Disconnect
    '''
    DETAILS[_worker_name()].close_connection()


def sendline(command):
    '''
    Run command through switch's cli

    .. code-block: bash

        salt '*' onyx.cmd sendline 'show run | include
        "username admin password 7"'
    '''
    if ping() is False:
        init()
    out, _ = DETAILS[_worker_name()].sendline(command)
    return out


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
        return 'Failed to enable switch'
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
        return 'Failed to enable ' \
               'configuration mode on switch'
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
        return 'Failed to exit form configuration mode on switch'
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
        return 'Failed to "configure terminal"'
    return ret


def grains():
    '''
    Get grains for proxy minion

    .. code-block: bash

        salt '*' onyx.cmd grains
    '''
    if not DETAILS['grains_cache']:
        ret = system_info()
        log.debug(ret)
        DETAILS['grains_cache'].update(ret)
    return {'onyx': DETAILS['grains_cache']}


def grains_refresh():
    '''
    Refresh the grains from the proxy device.

    .. code-block: bash

        salt '*' onyx.cmd grains_refresh
    '''
    DETAILS['grains_cache'] = {}
    return grains()


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
        user = cmd_out[1:-1]
        configure_terminal_exit()
        disable()
        return user
    except TerminalException as e:
        log.error(e)
        return 'Failed to get user'


def get_roles(username):
    '''
    Get roles that the username is assigned from switch

    .. code-block: bash

        salt '*' onyx.cmd get_roles username=admin
    '''
    info = sendline('show user-account {0}'.format(username))
    roles = re.search(r'^\s*roles:(.*)$', info, re.MULTILINE)
    if roles:
        roles = roles.group(1).strip().split(' ')
    else:
        roles = []
    return roles


def check_role(username, role):
    '''
    Check if user is assigned a specific role on switch

    .. code-block:: bash

        salt '*' onyx.cmd check_role username=admin role=network-admin
    '''
    return role in get_roles(username)


def remove_user(username):
    '''
    Remove user from switch

    .. code-block:: bash

        salt '*' onyx.cmd remove_user username=daniel
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

        salt '*' onyx.cmd set_role username=daniel role=vdc-admin
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

        salt '*' onyx.cmd unset_role username=daniel role=vdc-admin
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

        salt '*' onyx.cmd show_run
    '''
    try:
        enable()
        configure_terminal()
        ret = sendline('show running-config')
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


def delete_config(lines):
    '''
    Delete one or more config lines to the switch running config

    .. code-block:: bash

        salt '*' onyx.cmd delete_config 'snmp-server community TESTSTRINGHERE group network-operator'

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

        salt '*' onyx.cmd find '^snmp-server.*$'

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

        salt '*' onyx.cmd replace 'TESTSTRINGHERE' 'NEWTESTSTRINGHERE'
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

        salt '*' onyx.system_info
    '''
    # data = show_ver()
    info = {
        'software': 'Test',
        'hardware': '',
        'plugins': ''
    }
    return info
