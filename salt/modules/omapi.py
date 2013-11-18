# -*- coding: utf-8 -*-
'''
This module interacts with an ISC DHCP Server via OMAPI.
server_ip and server_port params may be set in the minion
config or pillar:

.. code-block:: yaml

  omapi.server_ip: 127.0.0.1
  omapi.server_port: 7991

:depends: pypureomapi Python module
'''
# Import python libs
import logging
import struct


log = logging.getLogger(__name__)


try:
    import pypureomapi as omapi
    omapi_support = True
except ImportError as e:
    omapi_support = False


def __virtual__():
    '''
    Confirm pypureomapi is available.
    '''
    if omapi_support:
        return 'omapi'
    return False


def _conn():
    server_ip = __pillar__.get('omapi.server_ip',
            __opts__.get('omapi.server_ip', '127.0.0.1'))
    server_port = __pillar__.get('omapi.server_port',
            __opts__.get('omapi.server_port', 7991))
    key = __pillar__.get('omapi.key',
            __opts__.get('omapi.key', None))
    username = __pillar__.get('omapi.user',
            __opts__.get('omapi.user', None))
    return omapi.Omapi(server_ip, server_port, username=username, key=key)


def add_host(mac, name=None, ip=None, ddns=False, group=None,
        supersede_host=False):
    '''
    Add a host object for the given mac.

    CLI Example:

    .. code-block:: bash

        salt dhcp-server omapi.add_host ab:ab:ab:ab:ab:ab name=host1

    Add ddns-hostname and a fixed-ip statements:

    .. code-block:: bash

        salt dhcp-server omapi.add_host ab:ab:ab:ab:ab:ab name=host1 ip=10.1.1.1 ddns=true
    '''
    statements = ''
    o = _conn()
    msg = omapi.OmapiMessage.open(b'host')
    msg.message.append(('create', struct.pack('!I', 1)))
    msg.message.append(('exclusive', struct.pack('!I', 1)))
    msg.obj.append(('hardware-address', omapi.pack_mac(mac)))
    msg.obj.append(('hardware-type', struct.pack('!I', 1)))
    if ip:
        msg.obj.append(('ip-address', omapi.pack_ip(ip)))
    if name:
        msg.obj.append(('name', name))
    if group:
        msg.obj.append(('group', group))
    if supersede_host:
        statements += 'option host-name {0}; '.format(name)
    if ddns and name:
        statements += 'ddns-hostname {0}; '.format(name)
    if statements:
        msg.obj.append(('statements', statements))
    response = o.query_server(msg)
    if response.opcode != omapi.OMAPI_OP_UPDATE:
        return False
    return True


def delete_host(mac=None, name=None):
    '''
    Delete the host with the given mac or name.

    CLI Examples:

    .. code-block:: bash

        salt dhcp-server omapi.delete_host name=host1
        salt dhcp-server omapi.delete_host mac=ab:ab:ab:ab:ab:ab
    '''
    if not (mac or name):
        raise TypeError('At least one argument is required')
    o = _conn()
    msg = omapi.OmapiMessage.open(b'host')
    if mac:
        msg.obj.append(('hardware-address', omapi.pack_mac(mac)))
        msg.obj.append(('hardware-type', struct.pack('!I', 1)))
    if name:
        msg.obj.append(('name', name))
    response = o.query_server(msg)
    if response.opcode != omapi.OMAPI_OP_UPDATE:
        return None
    if response.handle == 0:
        return False
    response = o.query_server(omapi.OmapiMessage.delete(response.handle))
    if response.opcode != omapi.OMAPI_OP_STATUS:
        return False
    return True
