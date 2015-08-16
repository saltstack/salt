# -*- coding: utf-8 -*-
'''
Manage Dell DRAC from the Master

The login credentials need to be configured in the Salt master
configuration file.

  .. code-block: yaml

      drac:
        username: admin
        password: secret
'''

# Import python libs
from __future__ import absolute_import, print_function
import logging

# Import 3rd-party libs
try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

log = logging.getLogger(__name__)


def __virtual__():
    if HAS_PARAMIKO:
        return True

    return False


def __connect(hostname, timeout=20):
    '''
    Connect to the DRAC
    '''
    username = __opts__['drac'].get('username', None)
    password = __opts__['drac'].get('password', None)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(hostname, username=username, password=password, timeout=timeout)
    except Exception as e:
        log.error('Unable to connect to {0}: {1}'.format(hostname, e))
        return False

    return client


def __version(client):
    '''
    Grab DRAC version
    '''
    versions = {9: 'CMC',
                8: 'iDRAC6',
                10: 'iDRAC6',
                11: 'iDRAC6',
                16: 'iDRAC7',
                17: 'iDRAC7'}

    if isinstance(client, paramiko.SSHClient):
        (stdin, stdout, stderr) = client.exec_command('racadm getconfig -g idRacInfo')

        for i in stdout.readlines():
            if i[2:].startswith('idRacType'):
                return versions.get(int(i[2:].split('=')[1]), None)

    return None


def pxe(hostname, timeout=20):
    '''
    Connect to the Dell DRAC and have the boot order set to PXE
    and power cycle the system to PXE boot

    CLI Example:

    .. code-block:: bash

        salt-run drac.pxe example.com
    '''
    _cmds = [
        'racadm config -g cfgServerInfo -o cfgServerFirstBootDevice pxe',
        'racadm config -g cfgServerInfo -o cfgServerBootOnce 1',
        'racadm serveraction powercycle',
    ]

    client = __connect(hostname, timeout)

    if isinstance(client, paramiko.SSHClient):
        for i, cmd in enumerate(_cmds, 1):
            log.info('Executing command {0}'.format(i))

            (stdin, stdout, stderr) = client.exec_command(cmd)

        if 'successful' in stdout.readline():
            log.info('Executing command: {0}'.format(cmd))
        else:
            log.error('Unable to execute: {0}'.format(cmd))
            return False

    return True


def reboot(hostname, timeout=20):
    '''
    Reboot a server using the Dell DRAC

    CLI Example:

    .. code-block:: bash

        salt-run drac.reboot example.com
    '''
    client = __connect(hostname, timeout)

    if isinstance(client, paramiko.SSHClient):
        (stdin, stdout, stderr) = client.exec_command('racadm serveraction powercycle')

        if 'successful' in stdout.readline():
            log.info('powercycle successful')
        else:
            log.error('powercycle racadm command failed')
            return False
    else:
        log.error('client was not of type paramiko.SSHClient')
        return False

    return True


def poweroff(hostname, timeout=20):
    '''
    Power server off

    CLI Example:

    .. code-block:: bash

        salt-run drac.poweroff example.com
    '''
    client = __connect(hostname, timeout)

    if isinstance(client, paramiko.SSHClient):
        (stdin, stdout, stderr) = client.exec_command('racadm serveraction powerdown')

        if 'successful' in stdout.readline():
            log.info('powerdown successful')
        else:
            log.error('powerdown racadm command failed')
            return False
    else:
        log.error('client was not of type paramiko.SSHClient')
        return False

    return True


def poweron(hostname, timeout=20):
    '''
    Power server on

    CLI Example:

    .. code-block:: bash

        salt-run drac.poweron example.com
    '''
    client = __connect(hostname, timeout)

    if isinstance(client, paramiko.SSHClient):
        (stdin, stdout, stderr) = client.exec_command('racadm serveraction powerup')

        if 'successful' in stdout.readline():
            log.info('powerup successful')
        else:
            log.error('powerup racadm command failed')
            return False
    else:
        log.error('client was not of type paramiko.SSHClient')
        return False

    return True


def version(hostname, timeout=20):
    '''
    Display the version of DRAC

    CLI Example:

    .. code-block:: bash

        salt-run drac.version example.com
    '''
    return __version(__connect(hostname, timeout))
