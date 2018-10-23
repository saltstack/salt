# -*- coding: utf-8 -*-
'''
Support for Open vSwitch - module with basic Open vSwitch commands.

Suitable for setting up Openstack Neutron.

:codeauthor: Jiri Kotlin <jiri.kotlin@ultimum.io>
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
from salt.ext import six
import salt.utils.path

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load the module if Open vSwitch is installed
    '''
    if salt.utils.path.which('ovs-vsctl'):
        return 'openvswitch'
    return False


def _param_may_exist(may_exist):
    '''
    Returns --may-exist parameter for Open vSwitch command.

    Args:
        may_exist: Boolean whether to use this parameter.

    Returns:
        String '--may-exist ' or empty string.
    '''
    if may_exist:
        return '--may-exist '
    else:
        return ''


def _param_if_exists(if_exists):
    '''
    Returns --if-exist parameter for Open vSwitch command.

    Args:
        if_exists: Boolean whether to use this parameter.

    Returns:
        String '--if-exist ' or empty string.
    '''
    if if_exists:
        return '--if-exists '
    else:
        return ''


def _retcode_to_bool(retcode):
    '''
    Evaulates Open vSwitch command`s retcode value.

    Args:
        retcode: Value of retcode field from response, should be 0, 1 or 2.

    Returns:
        True on 0, else False
    '''
    if retcode == 0:
        return True
    else:
        return False


def _stdout_list_split(retcode, stdout='', splitstring='\n'):
    '''
    Evaulates Open vSwitch command`s retcode value.

    Args:
        retcode: Value of retcode field from response, should be 0, 1 or 2.
        stdout: Value of stdout filed from response.
        splitstring: String used to split the stdout default new line.

    Returns:
        List or False.
    '''
    if retcode == 0:
        ret = stdout.split(splitstring)
        return ret
    else:
        return False


def bridge_list():
    '''
    Lists all existing real and fake bridges.

    Returns:
        List of bridges (or empty list), False on failure.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

        salt '*' openvswitch.bridge_list
    '''
    cmd = 'ovs-vsctl list-br'
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    stdout = result['stdout']
    return _stdout_list_split(retcode, stdout)


def bridge_exists(br):
    '''
    Tests whether bridge exists as a real or fake  bridge.

    Returns:
        True if Bridge exists, else False.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

        salt '*' openvswitch.bridge_exists br0
    '''
    cmd = 'ovs-vsctl br-exists {0}'.format(br)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    return _retcode_to_bool(retcode)


def bridge_create(br, may_exist=True):
    '''
    Creates a new bridge.

    Args:
        br: A string - bridge name
        may_exist: Bool, if False - attempting to create a bridge that exists returns False.

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

        salt '*' openvswitch.bridge_create br0
    '''
    param_may_exist = _param_may_exist(may_exist)
    cmd = 'ovs-vsctl {1}add-br {0}'.format(br, param_may_exist)
    result = __salt__['cmd.run_all'](cmd)
    return _retcode_to_bool(result['retcode'])


def bridge_delete(br, if_exists=True):
    '''
    Deletes bridge and all of  its  ports.

    Args:
        br: A string - bridge name
        if_exists: Bool, if False - attempting to delete a bridge that does not exist returns False.

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

        salt '*' openvswitch.bridge_delete br0
    '''
    param_if_exists = _param_if_exists(if_exists)
    cmd = 'ovs-vsctl {1}del-br {0}'.format(br, param_if_exists)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    return _retcode_to_bool(retcode)


def port_add(br, port, may_exist=False):
    '''
    Creates on bridge a new port named port.

    Returns:
        True on success, else False.

    Args:
        br: A string - bridge name
        port: A string - port name
        may_exist: Bool, if False - attempting to create a port that exists returns False.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

        salt '*' openvswitch.port_add br0 8080
    '''
    param_may_exist = _param_may_exist(may_exist)
    cmd = 'ovs-vsctl {2}add-port {0} {1}'.format(br, port, param_may_exist)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    return _retcode_to_bool(retcode)


def port_remove(br, port, if_exists=True):
    '''
     Deletes port.

    Args:
        br: A string - bridge name (If bridge is None, port is removed from  whatever bridge contains it)
        port: A string - port name.
        if_exists: Bool, if False - attempting to delete a por that  does  not exist returns False. (Default True)

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

        salt '*' openvswitch.port_remove br0 8080
    '''
    param_if_exists = _param_if_exists(if_exists)

    if port and not br:
        cmd = 'ovs-vsctl {1}del-port {0}'.format(port, param_if_exists)
    else:
        cmd = 'ovs-vsctl {2}del-port {0} {1}'.format(br, port, param_if_exists)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    return _retcode_to_bool(retcode)


def port_list(br):
    '''
    Lists all of the ports within bridge.

    Args:
        br: A string - bridge name.

    Returns:
        List of bridges (or empty list), False on failure.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

        salt '*' openvswitch.port_list br0
    '''
    cmd = 'ovs-vsctl list-ports {0}'.format(br)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    stdout = result['stdout']
    return _stdout_list_split(retcode, stdout)


def port_get_tag(port):
    '''
    Lists tags of the port.

    Args:
        port: A string - port name.

    Returns:
        List of tags (or empty list), False on failure.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

        salt '*' openvswitch.port_get_tag tap0
    '''
    cmd = 'ovs-vsctl get port {0} tag'.format(port)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    stdout = result['stdout']
    return _stdout_list_split(retcode, stdout)


def interface_get_options(port):
    '''
    Port's interface's optional parameters.

    Args:
        port: A string - port name.

    Returns:
        String containing optional parameters of port's interface, False on failure.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

        salt '*' openvswitch.interface_get_options tap0
    '''
    cmd = 'ovs-vsctl get interface {0} options'.format(port)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    stdout = result['stdout']
    return _stdout_list_split(retcode, stdout)


def interface_get_type(port):
    '''
    Type of port's interface.

    Args:
        port: A string - port name.

    Returns:
        String - type of interface or empty string, False on failure.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

        salt '*' openvswitch.interface_get_type tap0
    '''
    cmd = 'ovs-vsctl get interface {0} type'.format(port)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    stdout = result['stdout']
    return _stdout_list_split(retcode, stdout)


def port_create_vlan(br, port, id, internal=False):
    '''
    Isolate VM traffic using VLANs.

    Args:
        br: A string - bridge name.
        port: A string - port name.
        id: An integer in the valid range 0 to 4095 (inclusive), name of VLAN.
        internal: A boolean to create an internal interface if one does not exist.

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

       salt '*' openvswitch.port_create_vlan br0 tap0 100
    '''
    interfaces = __salt__['network.interfaces']()
    if not 0 <= id <= 4095:
        return False
    elif not bridge_exists(br):
        return False
    elif not internal and port not in interfaces:
        return False
    elif port in port_list(br):
        cmd = 'ovs-vsctl set port {0} tag={1}'.format(port, id)
        if internal:
            cmd += ' -- set interface {0} type=internal'.format(port)
        result = __salt__['cmd.run_all'](cmd)
        return _retcode_to_bool(result['retcode'])
    else:
        cmd = 'ovs-vsctl add-port {0} {1} tag={2}'.format(br, port, id)
        if internal:
            cmd += ' -- set interface {0} type=internal'.format(port)
        result = __salt__['cmd.run_all'](cmd)
        return _retcode_to_bool(result['retcode'])


def port_create_gre(br, port, id, remote):
    '''
    Generic Routing Encapsulation - creates GRE tunnel between endpoints.

    Args:
        br: A string - bridge name.
        port: A string - port name.
        id: An integer - unsigned 32-bit number, tunnel's key.
        remote: A string - remote endpoint's IP address.

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

       salt '*' openvswitch.port_create_gre br0 gre1 5001 192.168.1.10
    '''
    if not 0 <= id < 2**32:
        return False
    elif not __salt__['dig.check_ip'](remote):
        return False
    elif not bridge_exists(br):
        return False
    elif port in port_list(br):
        cmd = 'ovs-vsctl set interface {0} type=gre options:remote_ip={1} options:key={2}'.format(port, remote, id)
        result = __salt__['cmd.run_all'](cmd)
        return _retcode_to_bool(result['retcode'])
    else:
        cmd = 'ovs-vsctl add-port {0} {1} -- set interface {1} type=gre options:remote_ip={2} ' \
              'options:key={3}'.format(br, port, remote, id)
        result = __salt__['cmd.run_all'](cmd)
        return _retcode_to_bool(result['retcode'])


def port_create_vxlan(br, port, id, remote, dst_port=None):
    '''
    Virtual eXtensible Local Area Network - creates VXLAN tunnel between endpoints.

    Args:
        br: A string - bridge name.
        port: A string - port name.
        id: An integer - unsigned 64-bit number, tunnel's key.
        remote: A string - remote endpoint's IP address.
        dst_port: An integer - port to use when creating tunnelport in the switch.

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

       salt '*' openvswitch.port_create_vxlan br0 vx1 5001 192.168.1.10 8472
    '''
    dst_port = ' options:dst_port=' + six.text_type(dst_port) if 0 < dst_port <= 65535 else ''
    if not 0 <= id < 2**64:
        return False
    elif not __salt__['dig.check_ip'](remote):
        return False
    elif not bridge_exists(br):
        return False
    elif port in port_list(br):
        cmd = 'ovs-vsctl set interface {0} type=vxlan options:remote_ip={1} ' \
              'options:key={2}{3}'.format(port, remote, id, dst_port)
        result = __salt__['cmd.run_all'](cmd)
        return _retcode_to_bool(result['retcode'])
    else:
        cmd = 'ovs-vsctl add-port {0} {1} -- set interface {1} type=vxlan options:remote_ip={2} ' \
              'options:key={3}{4}'.format(br, port, remote, id, dst_port)
        result = __salt__['cmd.run_all'](cmd)
        return _retcode_to_bool(result['retcode'])
