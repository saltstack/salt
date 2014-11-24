# -*- coding: utf-8 -*-
'''
Support for Bluetooth (using BlueZ in Linux).

The following packages are required packages for this module:

    bluez >= 5.7
    bluez-libs >= 5.7
    bluez-utils >= 5.7
    pybluez >= 0.18
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import 3rd-party libs
# pylint: disable=import-error
from salt.ext.six.moves import shlex_quote as _cmd_quote
# pylint: enable=import-error

# Import salt libs
import salt.utils.validate.net
from salt.exceptions import CommandExecutionError


log = logging.getLogger(__name__)
HAS_PYBLUEZ = False
try:
    import bluetooth  # pylint: disable=import-error
    HAS_PYBLUEZ = True
except ImportError:
    pass

__func_alias__ = {
    'address_': 'address'
}

# Define the module's virtual name
__virtualname__ = 'bluetooth'


def __virtual__():
    '''
    Only load the module if bluetooth is installed
    '''
    if HAS_PYBLUEZ:
        return __virtualname__
    return False


def version():
    '''
    Return Bluez version from bluetoothd -v

    CLI Example:

    .. code-block:: bash

        salt '*' bluetoothd.version
    '''
    cmd = 'bluetoothctl -v'
    out = __salt__['cmd.run'](cmd).splitlines()
    bluez_version = out[0]
    pybluez_version = '<= 0.18 (Unknown, but installed)'
    try:
        pybluez_version = bluetooth.__version__
    except Exception as exc:
        pass
    return {'Bluez': bluez_version, 'PyBluez': pybluez_version}


def address_():
    '''
    Get the many addresses of the Bluetooth adapter

    CLI Example:

    .. code-block:: bash

        salt '*' bluetooth.address
    '''
    ret = {}
    cmd = 'hciconfig'
    out = __salt__['cmd.run'](cmd).splitlines()
    dev = ''
    for line in out:
        if line.startswith('hci'):
            comps = line.split(':')
            dev = comps[0]
            ret[dev] = {
                'device': dev,
                'path': '/sys/class/bluetooth/{0}'.format(dev),
            }
        if 'BD Address' in line:
            comps = line.split()
            ret[dev]['address'] = comps[2]
        if 'DOWN' in line:
            ret[dev]['power'] = 'off'
        if 'UP RUNNING' in line:
            ret[dev]['power'] = 'on'
    return ret


def power(dev, mode):
    '''
    Power a bluetooth device on or off

    CLI Examples:

    .. code-block:: bash

        salt '*' bluetooth.power hci0 on
        salt '*' bluetooth.power hci0 off
    '''
    if dev not in address_():
        raise CommandExecutionError('Invalid dev passed to bluetooth.power')

    if mode == 'on' or mode is True:
        state = 'up'
        mode = 'on'
    else:
        state = 'down'
        mode = 'off'
    cmd = 'hciconfig {0} {1}'.format(dev, state)
    __salt__['cmd.run'](cmd).splitlines()
    info = address_()
    if info[dev]['power'] == mode:
        return True
    return False


def discoverable(dev):
    '''
    Enable this bluetooth device to be discoverable.

    CLI Example:

    .. code-block:: bash

        salt '*' bluetooth.discoverable hci0
    '''
    if dev not in address_():
        raise CommandExecutionError(
            'Invalid dev passed to bluetooth.discoverable'
        )

    cmd = 'hciconfig {0} iscan'.format(dev)
    __salt__['cmd.run'](cmd).splitlines()
    cmd = 'hciconfig {0}'.format(dev)
    out = __salt__['cmd.run'](cmd)
    if 'UP RUNNING ISCAN' in out:
        return True
    return False


def noscan(dev):
    '''
    Turn off scanning modes on this device.

    CLI Example:

    .. code-block:: bash

        salt '*' bluetooth.noscan hci0
    '''
    if dev not in address_():
        raise CommandExecutionError('Invalid dev passed to bluetooth.noscan')

    cmd = 'hciconfig {0} noscan'.format(dev)
    __salt__['cmd.run'](cmd).splitlines()
    cmd = 'hciconfig {0}'.format(dev)
    out = __salt__['cmd.run'](cmd)
    if 'SCAN' in out:
        return False
    return True


def scan():
    '''
    Scan for bluetooth devices in the area

    CLI Example:

    .. code-block:: bash

        salt '*' bluetooth.scan
    '''
    ret = []
    devices = bluetooth.discover_devices(lookup_names=True)
    for device in devices:
        ret.append({device[0]: device[1]})
    return ret


def block(bdaddr):
    '''
    Block a specific bluetooth device by BD Address

    CLI Example:

    .. code-block:: bash

        salt '*' bluetooth.block DE:AD:BE:EF:CA:FE
    '''
    if not salt.utils.validate.net.mac(bdaddr):
        raise CommandExecutionError(
            'Invalid BD address passed to bluetooth.block'
        )

    cmd = 'hciconfig {0} block'.format(bdaddr)
    __salt__['cmd.run'](cmd).splitlines()


def unblock(bdaddr):
    '''
    Unblock a specific bluetooth device by BD Address

    CLI Example:

    .. code-block:: bash

        salt '*' bluetooth.unblock DE:AD:BE:EF:CA:FE
    '''
    if not salt.utils.validate.net.mac(bdaddr):
        raise CommandExecutionError(
            'Invalid BD address passed to bluetooth.unblock'
        )

    cmd = 'hciconfig {0} unblock'.format(bdaddr)
    __salt__['cmd.run'](cmd).splitlines()


def pair(address, key):
    '''
    Pair the bluetooth adapter with a device

    CLI Example:

    .. code-block:: bash

        salt '*' bluetooth.pair DE:AD:BE:EF:CA:FE 1234

    Where DE:AD:BE:EF:CA:FE is the address of the device to pair with, and 1234
    is the passphrase.

    TODO: This function is currently broken, as the bluez-simple-agent program
    no longer ships with BlueZ >= 5.0. It needs to be refactored.
    '''
    if not salt.utils.validate.net.mac(address):
        raise CommandExecutionError(
            'Invalid BD address passed to bluetooth.pair'
        )

    try:
        int(key)
    except Exception:
        raise CommandExecutionError(
            'bluetooth.pair requires a numerical key to be used'
        )

    addy = address_()
    cmd = 'echo {0} | bluez-simple-agent {1} {2}'.format(
        _cmd_quote(addy['device']), _cmd_quote(address), _cmd_quote(key)
    )
    out = __salt__['cmd.run'](cmd, python_shell=True).splitlines()
    return out


def unpair(address):
    '''
    Unpair the bluetooth adapter from a device

    CLI Example:

    .. code-block:: bash

        salt '*' bluetooth.unpair DE:AD:BE:EF:CA:FE

    Where DE:AD:BE:EF:CA:FE is the address of the device to unpair.

    TODO: This function is currently broken, as the bluez-simple-agent program
    no longer ships with BlueZ >= 5.0. It needs to be refactored.
    '''
    if not salt.utils.validate.net.mac(address):
        raise CommandExecutionError(
            'Invalid BD address passed to bluetooth.unpair'
        )

    cmd = 'bluez-test-device remove {0}'.format(address)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def start():
    '''
    Start the bluetooth service.

    CLI Example:

    .. code-block:: bash

        salt '*' bluetooth.start
    '''
    out = __salt__['service.start']('bluetooth')
    return out


def stop():
    '''
    Stop the bluetooth service.

    CLI Example:

    .. code-block:: bash

        salt '*' bluetooth.stop
    '''
    out = __salt__['service.stop']('bluetooth')
    return out
