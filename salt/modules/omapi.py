'''
The OMAPI module interacts with an ISC DHCP Server via OMAPI.
Requires pypureomapi module. server_ip and server_port params may
be set in the minion config or pillar,  or passed as arguments:

.. code-block:: yaml

  omapi.server_ip: 127.0.0.1
  omapi.port: 7991

Key authentication is not supported, but may
be added in a later version.
'''
# Import python libs
import logging
import struct

# Import salt libs
import salt.utils


log = logging.getLogger(__name__)


try:
    from pypureomapi import *
    from pypureomapi import pack_ip, pack_mac
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


def _conn(kwargs):
    server_ip = kwargs.get('omapi.server_ip', __pillar__.get(
        'omapi.server_ip', __opts__.get('server_ip', '127.0.0.1')))
    server_port = kwargs.get('omapi.server_port', __pillar__.get(
        'omapi.server_port', __opts__.get('serve_port', 7991)))
    return Omapi(server_ip, server_port, debug=True)


def add_host(ip, mac, name, **kwargs):
    '''
    Add a host with a fixed-address and name.

    CLI Example::
        
        salt dhcp-server omapi.add_host 10.0.0.1 ab:ab:ab:ab:ab:ab host1
    '''
    o = _conn(kwargs)
    msg = OmapiMessage.open(b"host")
    msg.message.append(("create", struct.pack("!I", 1)))
    msg.message.append(("exclusive", struct.pack("!I", 1)))
    msg.obj.append(("hardware-address", pack_mac(mac)))
    msg.obj.append(("hardware-type", struct.pack("!I", 1)))
    msg.obj.append(("ip-address", pack_ip(ip)))
    msg.obj.append(("name", name))
    response = o.query_server(msg)
    if response.opcode != OMAPI_OP_UPDATE:
        return False
    return True


def delete_host(name, **kwargs):
    '''
    Delete the named host from a dhcp server.

    CLI Example::
        
        salt dhcp-server omapi.delete_host host1
    '''
    o = _conn(kwargs)
    msg = OmapiMessage.open(b"host")
    msg.obj.append(("name", name))
    response = o.query_server(msg)
    if response.opcode != OMAPI_OP_UPDATE:
        return None
    if response.handle == 0:
        return False
    response = o.query_server(OmapiMessage.delete(response.handle))
    if response.opcode != OMAPI_OP_STATUS:
        return False
    return True
