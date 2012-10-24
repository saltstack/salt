'''
Support for Bluetooth (using Bluez in Linux)
'''

import salt.utils
import salt.modules.service


def __virtual__():
    '''
    Only load the module if bluetooth is installed
    '''
    if salt.utils.which('bluetoothd'):
        return 'bluetooth'
    return False


def version():
    '''
    Return Bluez version from bluetoothd -v

    CLI Example::

        salt '*' bluetoothd.version
    '''
    cmd = 'bluetoothd -v'
    out = __salt__['cmd.run'](cmd).split('\n')
    return out[0]


def address():
    '''
    Get the many addresses of the Bluetooth adapter

    CLI Example::

        salt '*' bluetooth.address
    '''
    cmd = ('dbus-send --system --print-reply --dest=org.bluez / '
           'org.bluez.Manager.DefaultAdapter|awk \'/object path/ '
           '{print $3}\' | sed \'s/"//g\'')
    path = __salt__['cmd.run'](cmd).split('\n')
    devname = path[0].split('/')
    syspath = '/sys/class/bluetooth/{0}/address'.format(devname[-1])
    sysfile = open(syspath, 'r')
    address = sysfile.read().strip()
    sysfile.close()
    return {
                'path': path[0],
                'devname': devname[-1],
                'address': address,
           }


def scan():
    '''
    Scan for bluetooth devices in the area

    CLI Example::

        salt '*' bluetooth.scan
    '''
    cmd = 'hcitool scan'
    ret = {}
    out = __salt__['cmd.run'](cmd).split('\n')
    for line in out:
        if not line:
            continue
        if 'Scanning' in line:
            continue
        comps = line.strip().split()
        devname = ' '.join(comps[1:])
        ret[comps[0]] = devname
    return ret


def pair(address, key):
    '''
    Pair the bluetooth adapter with a device

    CLI Example::

        salt '*' bluetooth.pair DE:AD:BE:EF:CA:FE 1234

    Where DE:AD:BE:EF:CA:FE is the address of the device
    to pair with, and 1234 is the passphrase.
    '''
    address = address()
    cmd = 'echo "{0}" | bluez-simple-agent {1} {2}'.format(
        address['devname'], address, key
    )
    out = __salt__['cmd.run'](cmd).split('\n')
    return out


def unpair(address):
    '''
    Unpair the bluetooth adapter from a device

    CLI Example::

        salt '*' bluetooth.unpair DE:AD:BE:EF:CA:FE

    Where DE:AD:BE:EF:CA:FE is the address of the device
    to unpair.
    '''
    address = address()
    cmd = 'bluez-test-device remove {0}'.format(address)
    out = __salt__['cmd.run'](cmd).split('\n')
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
