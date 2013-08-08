'''
Support for Bluetooth (using BlueZ in Linux).

The following packages are required packages for this module:

    bluez >= 5.7
    bluez-libs >= 5.7
    bluez-utils >= 5.7
    pybluez >= 0.18
'''

# Import python libs
import logging

# Import salt libs
import salt.utils
import salt.modules.service

log = logging.getLogger(__name__)
HAS_PYBLUEZ = False
try:
    import bluetooth
    HAS_PYBLUEZ = True
except Exception as exc:
    HAS_PYBLUEZ = False

__func_alias__ = {
    'address_': 'address'
}


def __virtual__():
    '''
    Only load the module if bluetooth is installed
    '''
    if HAS_PYBLUEZ:
        return 'bluetooth'
    return False


def version():
    '''
    Return Bluez version from bluetoothd -v

    CLI Example::

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

    CLI Example::

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

    CLI Examples::

        salt '*' bluetooth.power hci0 on
        salt '*' bluetooth.power hci0 off
    '''
    log.debug('mode is {0}'.format(mode))
    if mode == 'on' or mode is True:
        state = 'up'
        mode = 'on'
    else:
        state = 'down'
        mode = 'off'
    log.debug('state is {0}'.format(state))
    cmd = 'hciconfig {0} {1}'.format(dev, state)
    out = __salt__['cmd.run'](cmd).splitlines()
    info = address_()
    log.debug(info)
    if info[dev]['power'] == mode:
        return True
    return False


def scan():
    '''
    Scan for bluetooth devices in the area

    CLI Example::

        salt '*' bluetooth.scan
    '''
    ret = []
    devices = bluetooth.discover_devices(lookup_names=True)
    for device in devices:
        ret.append({device[0]: device[1]})
    return ret


def pair(address, key):
    '''
    Pair the bluetooth adapter with a device

    CLI Example::

        salt '*' bluetooth.pair DE:AD:BE:EF:CA:FE 1234

    Where DE:AD:BE:EF:CA:FE is the address of the device to pair with, and 1234
    is the passphrase.

    TODO: This function is currently broken, as the bluez-simple-agent program
    no longer ships with BlueZ >= 5.0. It needs to be refactored.
    '''
    address = address()
    cmd = 'echo "{0}" | bluez-simple-agent {1} {2}'.format(
        address['devname'], address, key
    )
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def unpair(address):
    '''
    Unpair the bluetooth adapter from a device

    CLI Example::

        salt '*' bluetooth.unpair DE:AD:BE:EF:CA:FE

    Where DE:AD:BE:EF:CA:FE is the address of the device to unpair.

    TODO: This function is currently broken, as the bluez-simple-agent program
    no longer ships with BlueZ >= 5.0. It needs to be refactored.
    '''
    address = address()
    cmd = 'bluez-test-device remove {0}'.format(address)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def start():
    '''
    Start the bluetooth service.

    CLI Example::

        salt '*' bluetooth.start
    '''
    out = __salt__['service.start']('bluetooth')
    return out


def stop():
    '''
    Stop the bluetooth service.

    CLI Example::

        salt '*' bluetooth.stop
    '''
    out = __salt__['service.stop']('bluetooth')
    return out
