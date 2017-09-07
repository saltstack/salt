# -*- coding: utf-8 -*-
'''
Module to provide Cisco UCS compatibility to Salt.

:codeauthor: :email:`Spencer Ervin <spencer_ervin@hotmail.com>`
:maturity:   new
:depends:    none
:platform:   unix


Configuration
=============
This module accepts connection configuration details either as
parameters, or as configuration settings in pillar as a Salt proxy.
Options passed into opts will be ignored if options are passed into pillar.

.. seealso::
    :prox:`Cisco UCS Proxy Module <salt.proxy.cimc>`

About
=====
This execution module was designed to handle connections to a Cisco UCS server. This module adds support to send
connections directly to the device through the rest API.

'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils.platform
import salt.proxy.cimc

log = logging.getLogger(__name__)

__virtualname__ = 'cimc'


def __virtual__():
    '''
    Will load for the cimc proxy minions.
    '''
    try:
        if salt.utils.platform.is_proxy() and \
           __opts__['proxy']['proxytype'] == 'cimc':
            return __virtualname__
    except KeyError:
        pass

    return False, 'The cimc execution module can only be loaded for cimc proxy minions.'


def activate_backup_image(reset=False):
    '''
    Activates the firmware backup image.

    CLI Example:

    Args:
        reset(bool): Reset the CIMC device on activate.

    .. code-block:: bash

        salt '*' cimc.activate_backup_image
        salt '*' cimc.activate_backup_image reset=True

    '''

    dn = "sys/rack-unit-1/mgmt/fw-boot-def/bootunit-combined"

    r = "no"

    if reset is True:
        r = "yes"

    inconfig = """<firmwareBootUnit dn='sys/rack-unit-1/mgmt/fw-boot-def/bootunit-combined'
    adminState='trigger' image='backup' resetOnActivate='{0}' />""".format(r)

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig)

    return ret


def create_user(uid=None, username=None, password=None, priv=None):
    '''
    Create a CIMC user with username and password.

    Args:
        uid(int): The user ID slot to create the user account in.

        username(str): The name of the user.

        password(str): The clear text password of the user.

        priv(str): The privilege level of the user.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.create_user 11 username=admin password=foobar priv=admin

    '''

    if not uid:
        raise salt.exceptions.CommandExecutionError("The user ID must be specified.")

    if not username:
        raise salt.exceptions.CommandExecutionError("The username must be specified.")

    if not password:
        raise salt.exceptions.CommandExecutionError("The password must be specified.")

    if not priv:
        raise salt.exceptions.CommandExecutionError("The privilege level must be specified.")

    dn = "sys/user-ext/user-{0}".format(uid)

    inconfig = """<aaaUser id="{0}" accountStatus="active" name="{1}" priv="{2}"
    pwd="{3}"  dn="sys/user-ext/user-{0}"/>""".format(uid,
                                                      username,
                                                      priv,
                                                      password)

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig)

    return ret


def get_bios_defaults():
    '''
    Get the default values of BIOS tokens.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_bios_defaults

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('biosPlatformDefaults')

    return ret


def get_bios_settings():
    '''
    Get the C240 server BIOS token values.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_bios_settings

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('biosSettings')

    return ret


def get_boot_order():
    '''
    Retrieves the configured boot order table.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_boot_order

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('lsbootDef')

    return ret


def get_cpu_details():
    '''
    Get the CPU product ID details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_cpu_details

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('pidCatalogCpu')

    return ret


def get_disks():
    '''
    Get the HDD product ID details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_disks

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('pidCatalogHdd')

    return ret


def get_ethernet_interfaces():
    '''
    Get the adapter Ethernet interface details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_ethernet_interfaces

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('adaptorHostEthIf')

    return ret


def get_fibre_channel_interfaces():
    '''
    Get the adapter fibre channel interface details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_fibre_channel_interfaces

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('adaptorHostFcIf')

    return ret


def get_firmware():
    '''
    Retrieves the current running firmware versions of server components.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_firmware

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('firmwareRunning')

    return ret


def get_ldap():
    '''
    Retrieves LDAP server details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_ldap

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('aaaLdap')

    return ret


def get_memory_token():
    '''
    Get the memory RAS BIOS token.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_memory_token

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('biosVfSelectMemoryRASConfiguration')

    return ret


def get_memory_unit():
    '''
    Get the IMM/Memory unit product ID details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_memory_unit

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('pidCatalogDimm')

    return ret


def get_pci_adapters():
    '''
    Get the PCI adapter product ID details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_disks

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('pidCatalogPCIAdapter')

    return ret


def get_power_supplies():
    '''
    Retrieves the power supply unit details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_power_supplies

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('equipmentPsu')

    return ret


def get_snmp_config():
    '''
    Get the snmp configuration details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_snmp_config

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('commSnmp')

    return ret


def get_syslog_details():
    '''
    Get the Syslog client-server details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_syslog_details

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('commSyslogClient')

    return ret


def get_system_info():
    '''
    Get the system information.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_system_info

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('computeRackUnit')

    return ret


def get_users():
    '''
    Get the CIMC users.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_users

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('aaaUser')

    return ret


def get_vic_adapters():
    '''
    Get the VIC adapter general profile details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_vic_adapters

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('adaptorGenProfile')

    return ret


def get_vic_uplinks():
    '''
    Get the VIC adapter uplink port details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_vic_uplinks

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('adaptorExtEthIf')

    return ret


def reboot():
    '''
    Power cycling the server.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.reboot

    '''

    dn = "sys/rack-unit-1"

    inconfig = """<computeRackUnit adminPower="cycle-immediate" dn="sys/rack-unit-1"></computeRackUnit>"""

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig)

    return ret


def set_syslog_server(server=None, type="primary"):
    '''
    Set the SYSLOG server on the host.

    Args:
        server(str): The hostname or IP address of the SYSLOG server.

        type(str): Specifies the type of SYSLOG server. This can either be primary (default) or secondary.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.set_syslog_server foo.bar.com

        salt '*' cimc.set_syslog_server foo.bar.com primary

        salt '*' cimc.set_syslog_server foo.bar.com secondary

    '''

    if not server:
        raise salt.exceptions.CommandExecutionError("The SYSLOG server must be specified.")

    if type == "primary":
        dn = "sys/svc-ext/syslog/client-primary"
        inconfig = """<commSyslogClient name='primary' adminState='enabled'  hostname='{0}'
        dn='sys/svc-ext/syslog/client-primary'> </commSyslogClient>""".format(server)
    elif type == "secondary":
        dn = "sys/svc-ext/syslog/client-secondary"
        inconfig = """<commSyslogClient name='secondary' adminState='enabled'  hostname='{0}'
        dn='sys/svc-ext/syslog/client-secondary'> </commSyslogClient>""".format(server)
    else:
        raise salt.exceptions.CommandExecutionError("The SYSLOG type must be either primary or secondary.")

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig)

    return ret


def tftp_update_bios(server=None, path=None):
    '''
    Update the BIOS firmware through TFTP.

    Args:
        server(str): The IP address or hostname of the TFTP server.

        path(str): The TFTP path and filename for the BIOS image.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.tftp_update_bios foo.bar.com HP-SL2.cap

    '''

    if not server:
        raise salt.exceptions.CommandExecutionError("The server name must be specified.")

    if not path:
        raise salt.exceptions.CommandExecutionError("The TFTP path must be specified.")

    dn = "sys/rack-unit-1/bios/fw-updatable"

    inconfig = """<firmwareUpdatable adminState='trigger' dn='sys/rack-unit-1/bios/fw-updatable'
    protocol='tftp' remoteServer='{0}' remotePath='{1}'
    type='blade-bios' />""".format(server, path)

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig)

    return ret


def tftp_update_cimc(server=None, path=None):
    '''
    Update the CIMC firmware through TFTP.

    Args:
        server(str): The IP address or hostname of the TFTP server.

        path(str): The TFTP path and filename for the CIMC image.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.tftp_update_cimc foo.bar.com HP-SL2.bin

    '''

    if not server:
        raise salt.exceptions.CommandExecutionError("The server name must be specified.")

    if not path:
        raise salt.exceptions.CommandExecutionError("The TFTP path must be specified.")

    dn = "sys/rack-unit-1/mgmt/fw-updatable"

    inconfig = """<firmwareUpdatable adminState='trigger' dn='sys/rack-unit-1/mgmt/fw-updatable'
    protocol='tftp' remoteServer='{0}' remotePath='{1}'
    type='blade-controller' />""".format(server, path)

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig)

    return ret
