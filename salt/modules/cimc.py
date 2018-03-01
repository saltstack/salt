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
from __future__ import absolute_import, print_function, unicode_literals
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

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig, False)

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

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig, False)

    return ret


def get_bios_defaults():
    '''
    Get the default values of BIOS tokens.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_bios_defaults

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('biosPlatformDefaults', True)

    return ret


def get_bios_settings():
    '''
    Get the C240 server BIOS token values.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_bios_settings

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('biosSettings', True)

    return ret


def get_boot_order():
    '''
    Retrieves the configured boot order table.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_boot_order

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('lsbootDef', True)

    return ret


def get_cpu_details():
    '''
    Get the CPU product ID details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_cpu_details

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('pidCatalogCpu', True)

    return ret


def get_disks():
    '''
    Get the HDD product ID details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_disks

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('pidCatalogHdd', True)

    return ret


def get_ethernet_interfaces():
    '''
    Get the adapter Ethernet interface details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_ethernet_interfaces

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('adaptorHostEthIf', True)

    return ret


def get_fibre_channel_interfaces():
    '''
    Get the adapter fibre channel interface details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_fibre_channel_interfaces

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('adaptorHostFcIf', True)

    return ret


def get_firmware():
    '''
    Retrieves the current running firmware versions of server components.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_firmware

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('firmwareRunning', False)

    return ret


def get_ldap():
    '''
    Retrieves LDAP server details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_ldap

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('aaaLdap', True)

    return ret


def get_management_interface():
    '''
    Retrieve the management interface details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_management_interface

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('mgmtIf', False)

    return ret


def get_memory_token():
    '''
    Get the memory RAS BIOS token.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_memory_token

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('biosVfSelectMemoryRASConfiguration', False)

    return ret


def get_memory_unit():
    '''
    Get the IMM/Memory unit product ID details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_memory_unit

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('pidCatalogDimm', True)

    return ret


def get_network_adapters():
    '''
    Get the list of network adapaters and configuration details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_network_adapters

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('networkAdapterEthIf', True)

    return ret


def get_ntp():
    '''
    Retrieves the current running NTP configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_ntp

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('commNtpProvider', False)

    return ret


def get_pci_adapters():
    '''
    Get the PCI adapter product ID details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_disks

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('pidCatalogPCIAdapter', True)

    return ret


def get_power_supplies():
    '''
    Retrieves the power supply unit details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_power_supplies

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('equipmentPsu', False)

    return ret


def get_snmp_config():
    '''
    Get the snmp configuration details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_snmp_config

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('commSnmp', False)

    return ret


def get_syslog():
    '''
    Get the Syslog client-server details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_syslog

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('commSyslogClient', False)

    return ret


def get_system_info():
    '''
    Get the system information.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_system_info

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('computeRackUnit', False)

    return ret


def get_users():
    '''
    Get the CIMC users.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_users

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('aaaUser', False)

    return ret


def get_vic_adapters():
    '''
    Get the VIC adapter general profile details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_vic_adapters

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('adaptorGenProfile', True)

    return ret


def get_vic_uplinks():
    '''
    Get the VIC adapter uplink port details.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.get_vic_uplinks

    '''
    ret = __proxy__['cimc.get_config_resolver_class']('adaptorExtEthIf', True)

    return ret


def mount_share(name=None,
                remote_share=None,
                remote_file=None,
                mount_type="nfs",
                username=None,
                password=None):
    '''
    Mounts a remote file through a remote share. Currently, this feature is supported in version 1.5 or greater.
    The remote share can be either NFS, CIFS, or WWW.

    Some of the advantages of CIMC Mounted vMedia include:
      Communication between mounted media and target stays local (inside datacenter)
      Media mounts can be scripted/automated
      No vKVM requirements for media connection
      Multiple share types supported
      Connections supported through all CIMC interfaces

      Note: CIMC Mounted vMedia is enabled through BIOS configuration.

    Args:
        name(str): The name of the volume on the CIMC device.

        remote_share(str): The file share link that will be used to mount the share. This can be NFS, CIFS, or WWW. This
        must be the directory path and not the full path to the remote file.

        remote_file(str): The name of the remote file to mount. It must reside within remote_share.

        mount_type(str): The type of share to mount. Valid options are nfs, cifs, and www.

        username(str): An optional requirement to pass credentials to the remote share. If not provided, an
        unauthenticated connection attempt will be made.

        password(str): An optional requirement to pass a password to the remote share. If not provided, an
        unauthenticated connection attempt will be made.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.mount_share name=WIN7 remote_share=10.xxx.27.xxx:/nfs remote_file=sl1huu.iso

        salt '*' cimc.mount_share name=WIN7 remote_share=10.xxx.27.xxx:/nfs remote_file=sl1huu.iso username=bob password=badpassword

    '''

    if not name:
        raise salt.exceptions.CommandExecutionError("The share name must be specified.")

    if not remote_share:
        raise salt.exceptions.CommandExecutionError("The remote share path must be specified.")

    if not remote_file:
        raise salt.exceptions.CommandExecutionError("The remote file name must be specified.")

    if username and password:
        mount_options = " mountOptions='username={0},password={1}'".format(username, password)
    else:
        mount_options = ""

    dn = 'sys/svc-ext/vmedia-svc/vmmap-{0}'.format(name)
    inconfig = """<commVMediaMap dn='sys/svc-ext/vmedia-svc/vmmap-{0}' map='{1}'{2}
    remoteFile='{3}' remoteShare='{4}' status='created'
    volumeName='Win12' />""".format(name, mount_type, mount_options, remote_file, remote_share)

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig, False)

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

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig, False)

    return ret


def set_ntp_server(server1='', server2='', server3='', server4=''):
    '''
    Sets the NTP servers configuration. This will also enable the client NTP service.

    Args:
        server1(str): The first IP address or FQDN of the NTP servers.

        server2(str): The second IP address or FQDN of the NTP servers.

        server3(str): The third IP address or FQDN of the NTP servers.

        server4(str): The fourth IP address or FQDN of the NTP servers.

    CLI Example:

    .. code-block:: bash

        salt '*' cimc.set_ntp_server 10.10.10.1

        salt '*' cimc.set_ntp_server 10.10.10.1 foo.bar.com

    '''

    dn = "sys/svc-ext/ntp-svc"
    inconfig = """<commNtpProvider dn="sys/svc-ext/ntp-svc" ntpEnable="yes" ntpServer1="{0}" ntpServer2="{1}"
    ntpServer3="{2}" ntpServer4="{3}"/>""".format(server1, server2, server3, server4)

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig, False)

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

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig, False)

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

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig, False)

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

    ret = __proxy__['cimc.set_config_modify'](dn, inconfig, False)

    return ret
