# -*- coding: utf-8 -*-
"""
Support for Open vSwitch
"""
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load the module if Open vSwitch is installed
    """
    cmd = _detect_os()
    if salt.utils.which(cmd):
        return 'openvswitch'
    return False


def _detect_os():
    """
    Open vSwitch command may differ depending on packaging.
    """
    return 'ovs-vsctl'


def _param_may_exist(may_exist):
    """
    Returns --may-exist parameter for Open vSwitch command.

    Args:
        may_exist: Boolean whether to use this parameter.

    Returns:
        String '--may-exist ' or empty string.
    """
    if may_exist:
        return '--may-exist '
    else:
        return ''


def _param_if_exists(if_exists):
    """
    Returns --if-exist parameter for Open vSwitch command.

    Args:
        if_exists: Boolean whether to use this parameter.

    Returns:
        String '--if-exist ' or empty string.
    """
    if if_exists:
        return '--if-exists '
    else:
        return ''


def _retcode_to_bool(retcode):
    """
    Evaulates Open vSwitch command`s retcode value.

    Args:
        retcode: Value of retcode field from response, should be 0, 1 or 2.

    Returns:
        True on 0, else False
    """
    if retcode == 0:
        return True
    else:
        return False


def _stdout_list_split(retcode, stdout='', splitstring='\n'):
    """
    Evaulates Open vSwitch command`s retcode value.

    Args:
        retcode: Value of retcode field from response, should be 0, 1 or 2.
        stdout: Value of stdout filed from response.
        splitstring: String used to split the stdout default new line.

    Returns:
        List or False.
    """
    if retcode == 0:
        ret = stdout.split(splitstring)
        return ret
    else:
        return False


def bridge_list():
    """
    Lists all existing real and fake bridges.

    Returns:
        List of bridges (or empty list), False on failure.

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.bridge_list
    """
    cmd = _detect_os() + ' list-br'
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    stdout = result['stdout']
    return _stdout_list_split(retcode, stdout)


def bridge_exists(br):
    """
    Tests whether bridge exists as a real or fake  bridge.

    Returns:
        True if Bridge exists, else False.

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.bridge_exists br0
    """
    cmd = _detect_os() + ' br-exists {0}'.format(br)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    return _retcode_to_bool(retcode)


def bridge_create(br, may_exist=True):
    """
    Creates a new bridge.

    Args:
        br: A string - bridge name
        may_exist: Bool, if False - attempting to create a bridge that exists returns False.

    Returns:
        True on success, else False.

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.bridge_create br0
    """
    param_may_exist = _param_may_exist(may_exist)
    cmd = _detect_os() + ' {1}add-br {0}'.format(br, param_may_exist)
    result = __salt__['cmd.run_all'](cmd)
    return _retcode_to_bool(result['retcode'])


def bridge_delete(br, if_exists=True):
    """
    Deletes bridge and all of  its  ports.

    Args:
        br: A string - bridge name
        if_exists: Bool, if False - attempting to delete a bridge that does not exist returns False.

    Returns:
        True on success, else False.

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.bridge_delete br0
    """
    param_if_exists = _param_if_exists(if_exists)
    cmd = _detect_os() + ' {1}del-br {0}'.format(br, param_if_exists)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    return _retcode_to_bool(retcode)


def port_add(br, port, may_exist=False):
    """
    Creates on bridge a new port named port.

    Returns:
        True on success, else False.

    Args:
        br: A string - bridge name
        port: A string - port name
        may_exist: Bool, if False - attempting to create a port that exists returns False.

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.port_add br0 8080
    """
    param_may_exist = _param_may_exist(may_exist)
    cmd = _detect_os() + ' {2}add-port {0} {1}'.format(br, port, param_may_exist)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    return _retcode_to_bool(retcode)


def port_remove(*args, **kwargs):
    """
     Deletes port.

    Args:
        br: A string - bridge name (Optional: If bridge is not set, port is removed from  whatever bridge contains it)
        port: A string - port name (Required argument)
        if_exists: Bool, if False - attempting to delete a por that  does  not exist returns False. (Default True)
t
    Returns:
        True on success, else False.

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.port_remove br0 8080
    """

    default_args = {
        0: None,    # br
        1: None,    # port
        2: None,    # if_exists
    }

    #kwargs
    try:
        if kwargs.get("br"):
            default_args[0] = str(kwargs.get("br"))
        if kwargs.get("port"):
            default_args[1] = str(kwargs.get("port"))
        default_args[2] = str(kwargs.get("if_exists", None))
    except IndexError:
        pass

    #args
    try:
        for index, item in enumerate(args):
            if not default_args[index]:
                default_args[index] = str(item)
    except KeyError:
        pass

    br = default_args[0]
    port = default_args[1]
    if_exists = default_args[2]

    if br and not port:
        try:
            if not kwargs.get("br"):
                # br argument was not called as kwarg br=name
                raise IndexError
        except IndexError:
            port = br
            br = ''

    if not br:
        br = ''

    if if_exists == 'False':
        if_exists = False
    else:
        if_exists = True

    # port is the only required argument for this function
    if not port:
        raise TypeError

    param_if_exists = _param_if_exists(if_exists)
    cmd = _detect_os() + ' {2}del-port {0} {1}'.format(br, port, param_if_exists)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    return _retcode_to_bool(retcode)


def port_list(br):
    """
    Lists all of the ports within bridge.

    Returns:
        List of bridges (or empty list), False on failure.

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.port_list br0
    """
    cmd = _detect_os() + ' list-ports {0}'.format(br)
    result = __salt__['cmd.run_all'](cmd)
    retcode = result['retcode']
    stdout = result['stdout']
    return _stdout_list_split(retcode, stdout)
