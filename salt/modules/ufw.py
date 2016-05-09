# -*- coding: utf-8 -*-
'''
Support for ufw.

.. versionadded:: #TODO ??
'''

# This module is an edit of Publysher Blog ufw module:
# (https://github.com/publysher/infra-example-nginx/tree/develop)

# The MIT License (MIT)
#
# Original work Copyright (c) 2013 publysher
# Modified work Copyright 2016 Alpha Ledger LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import logging
import re
import socket

import salt

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Check to see if ufw is installed.
    '''
    if salt.utils.which('ufw'):
        return True

    return (False, 'The ufw execution module cannot be loaded: the ufw binary is not in the path.')

def _build_cmd(action, protocol,
               to_port, to_addr,
               from_port, from_addr,
               direction, interface):
    '''
    Build an ufw rule creation/deletion command.
    '''
    actions_re = r'^\s*(--dry-run\s+)?(delete\s+)?(allow|deny|reject|limit)\s*$'
    if not re.match(actions_re, action):
        raise ValueError('invalid action: {0}'.format(action))
    if direction not in ['in', 'out']:
        raise ValueError('invalid direction: {0}'.format(direction))

    cmd_list = ['ufw', action, direction]
    if interface is not None:
        cmd_list.extend(['on', interface])

    cmd_list.extend(["from", _resolve(from_addr)])
    if from_port is not None:
        cmd_list.extend(["port", str(from_port)])

    cmd_list.extend(["to", _resolve(to_addr)])
    if to_port is not None:
        cmd_list.extend(["port", str(to_port)])

    if protocol is not None:
        cmd_list.extend(["proto", protocol])

    return ' '.join(cmd_list)

def _ufw_cmd(action, protocol,
             to_port, to_addr,
             from_port, from_addr,
             direction, interface):
    '''
    Run an ufw rule creation/deletion command.
    '''
    try:
        cmd = _build_cmd(action, protocol,
                         to_port, to_addr,
                         from_port, from_addr,
                         direction, interface)
    except ValueError as exc:
        log.error('Error creating command list: {0}'.format(exc.message))
        return exc.message

    log.info('Running ufw {0}'.format(cmd))
    out = __salt__['cmd.run'](cmd)
    if not out.startswith('ERROR'):
        __salt__['cmd.run']('ufw reload')
    return out

def _resolve(host):
    '''
    Get a host IP. If `host` is an IP address or 'any', it's returned unchanged
    '''
    if host == 'any':
        return host
    return socket.getaddrinfo(host, 0, 0, 0, socket.IPPROTO_TCP)[0][4][0]

def status():
    '''
    Print current ufw status.
    '''
    return __salt__['cmd.run']('ufw status numbered')

def is_enabled():
    '''
    Returns whether ufw is currently enabled.
    '''
    return status().startswith('Status: active')

def show_added():
    '''
    Returns a list of added rules.
    '''
    out = __salt__['cmd.run']('ufw show added')
    return out.split('\n')[1:]

def set_enabled(enabled):
    '''
    Enable or disable ufw.

    CLI Example:

    .. code-block:: bash

        salt '*' ufw.set_enabled True
    '''
    if enabled:
        log.info('Enabling ufw')
        return __salt__['cmd.run']('ufw --force enable')
    else:
        log.info('Disabling ufw')
        return __salt__['cmd.run']('ufw disable')

def add_rule(action, protocol=None,
             to_port=None, to_addr='any',
             from_port=None, from_addr='any',
             direction='in', interface=None,
             test=False):
    '''
    Add an allow, deny, reject or limit rule.

    CLI Example:

    .. code-block:: bash

        salt '*' ufw.add_rule allow tcp 22
    '''
    if test:
        action = '--dry-run {0}'.format(action)
    return _ufw_cmd(action, protocol, to_port, to_addr, from_port, from_addr, direction, interface)

def delete_rule(action, protocol=None,
                to_port=None, to_addr='any',
                from_port=None, from_addr='any',
                direction='in', interface=None):
    '''
    Delete an allow, deny, reject or limit rule.

    CLI Example:

    .. code-block:: bash

        salt '*' ufw.delete allow tcp 22
    '''
    delete_action = 'delete {0}'.format(action)
    # --dry-run doesn't seem to work with delete
    # if test:
    #     delete_action = '--dry-run {0}'.format(delete_action)
    return _ufw_cmd(delete_action, protocol, to_port, to_addr, from_port, from_addr, direction, interface)
