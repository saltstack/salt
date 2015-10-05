# -*- coding: utf-8 -*-
'''
Manage Dell DRAC
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,no-name-in-module,redefined-builtin

log = logging.getLogger(__name__)


def __virtual__():
    if salt.utils.which('racadm'):
        return True

    return False


def __parse_drac(output):
    '''
    Parse Dell DRAC output
    '''
    drac = {}
    section = ''

    for i in output.splitlines():
        if len(i.rstrip()) > 0 and '=' in i:
            if section in drac:
                drac[section].update(dict(
                    [[prop.strip() for prop in i.split('=')]]
                ))
        else:
            section = i.strip()[:-1]
            if section not in drac and section:
                drac[section] = {}

    return drac


def __execute_cmd(command, host=None, admin_username=None, admin_password=None):
    '''
    Execute rac commands
    '''
    if not host:
        # This is a local call
        cmd = __salt__['cmd.run_all']('racadm {0}'.format(command))
    else:
        cmd = __salt__['cmd.run_all'](
                  'racadm -r {0} -u {1} -p {2} {3}'.format(host, 
                                                           admin_username,
                                                           admin_password,
                                                           command))

    if cmd['retcode'] != 0:
        log.warning('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))
        return False

    return True

def __execute_ret(command, host=None, admin_username=None, admin_password=None):
    '''
    Execute rac commands
    '''
    if not host:
        # This is a local call
        cmd = __salt__['cmd.run_all']('racadm {0}'.format(command))
    else:
        cmd = __salt__['cmd.run_all'](
            'racadm -r {0} -u {1} -p {2} {3}'.format(host, 
                                                     admin_username, 
                                                     admin_password,
                                                     command))


    if cmd['retcode'] != 0:
        log.warning('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

    return cmd


def system_info(host=None, admin_username=None, admin_password=None):
    '''
    Return System information

    CLI Example:

    .. code-block:: bash

        salt dell drac.system_info
    '''
    cmd = __execute_ret('getsysinfo', host=host, 
                        admin_username=admin_username, admin_password=admin_password)

    if cmd['retcode'] != 0:
        log.warning('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

    return __parse_drac(cmd['stdout'])


def network_info(host=None, admin_username=None, admin_password=None):
    '''
    Return Network Configuration

    CLI Example:

    .. code-block:: bash

        salt dell drac.network_info
    '''

    cmd = __execute_ret('getniccfg', host=host, admin_username=admin_username,
                        admin_password=admin_password)

    if cmd['retcode'] != 0:
        log.warning('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

    return __parse_drac(cmd['stdout'])


def nameservers(ns, host=None, admin_username=None, admin_password=None):
    '''
    Configure the nameservers on the DRAC

    CLI Example:

    .. code-block:: bash

        salt dell drac.nameservers [NAMESERVERS]
        salt dell drac.nameservers ns1.example.com ns2.example.com
    '''
    if len(ns) > 2:
        log.warning('racadm only supports two nameservers')
        return False

    for i in range(1, len(ns) + 1):
        if not __execute_cmd('config -g cfgLanNetworking -o \
                cfgDNSServer{0} {1}'.format(i, ns[i - 1])):
            return False

    return True


def syslog(server, enable=True, host=None, admin_username=None, admin_password=None):
    '''
    Configure syslog remote logging, by default syslog will automatically be
    enabled if a server is specified. However, if you want to disable syslog
    you will need to specify a server followed by False

    CLI Example:

    .. code-block:: bash

        salt dell drac.syslog [SYSLOG IP] [ENABLE/DISABLE]
        salt dell drac.syslog 0.0.0.0 False
    '''
    if enable and __execute_cmd('config -g cfgRemoteHosts -o \
                cfgRhostsSyslogEnable 1'):
        return __execute_cmd('config -g cfgRemoteHosts -o \
                cfgRhostsSyslogServer1 {0}'.format(server))

    return __execute_cmd('config -g cfgRemoteHosts -o cfgRhostsSyslogEnable 0',
                         host=host,
                         admin_username=admin_username,
                         admin_password=admin_password)


def email_alerts(action, host=None, admin_username=None, admin_password=None):
    '''
    Enable/Disable email alerts

    CLI Example:

    .. code-block:: bash

        salt dell drac.email_alerts True
        salt dell drac.email_alerts False
    '''

    if action:
        return __execute_cmd('config -g cfgEmailAlert -o \
                cfgEmailAlertEnable -i 1 1', host=host,
                            admin_username=admin_username,
                            admin_password=admin_password)
    else:
        return __execute_cmd('config -g cfgEmailAlert -o \
                cfgEmailAlertEnable -i 1 0')


def list_users(host=None, admin_username=None, admin_password=None):
    '''
    List all DRAC users

    CLI Example:

    .. code-block:: bash

        salt dell drac.list_users
    '''
    users = {}
    _username = ''

    for idx in range(1, 17):
        cmd = __execute_ret('getconfig -g \
                cfgUserAdmin -i {0}'.format(idx),
                           host=host, admin_username=admin_username,
                           admin_password=admin_password)

        if cmd['retcode'] != 0:
            log.warning('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

        for user in cmd['stdout'].splitlines():
            if not user.startswith('cfg'):
                continue

            (key, val) = user.split('=')

            if key.startswith('cfgUserAdminUserName'):
                _username = val.strip()

                if val:
                    users[_username] = {'index': idx}
                else:
                    break
            else:
                users[_username].update({key: val})

    return users


def delete_user(username, uid=None, 
                host=None, admin_username=None, admin_password=None):
    '''
    Delete a user

    CLI Example:

    .. code-block:: bash

        salt dell drac.delete_user [USERNAME] [UID - optional]
        salt dell drac.delete_user diana 4
    '''
    if uid is None:
        user = list_users()
        uid = user[username]['index']

    if uid:
        return __execute_cmd('config -g cfgUserAdmin -o \
                              cfgUserAdminUserName -i {0} ""'.format(uid),
                            host=host, admin_username=admin_username,
                            admin_password=admin_password)

    else:
        log.warning('\'{0}\' does not exist'.format(username))
        return False

    return True


def change_password(username, password, uid=None, host=None, 
                    admin_username=None, admin_password=None):
    '''
    Change users password

    CLI Example:

    .. code-block:: bash

        salt dell drac.change_password [USERNAME] [PASSWORD] [UID - optional]
        salt dell drac.change_password diana secret
    '''
    if uid is None:
        user = list_users()
        uid = user[username]['index']

    if uid:
        return __execute_cmd('config -g cfgUserAdmin -o \
                cfgUserAdminPassword -i {0} {1}'.format(uid, password),
                            host=host, admin_username=admin_username,
                            admin_password=admin_password)
    else:
        log.warning('\'{0}\' does not exist'.format(username))
        return False

    return True


def create_user(username, password, permissions, 
                users=None, host=None, admin_username=None, admin_password=None):
    '''
    Create user accounts

    CLI Example:

    .. code-block:: bash

        salt dell drac.create_user [USERNAME] [PASSWORD] [PRIVELEGES]
        salt dell drac.create_user diana secret login,test_alerts,clear_logs

    DRAC Privileges
      * login                   : Login to iDRAC
      * drac                    : Configure iDRAC
      * user_management         : Configure Users
      * clear_logs              : Clear Logs
      * server_control_commands : Execute Server Control Commands
      * console_redirection     : Access Console Redirection
      * virtual_media           : Access Virtual Media
      * test_alerts             : Test Alerts
      * debug_commands          : Execute Debug Commands
    '''
    _uids = set()

    if users is None:
        users = list_users()

    if username in users:
        log.warning('\'{0}\' already exists'.format(username))
        return False

    for idx in six.iterkeys(users):
        _uids.add(users[idx]['index'])

    uid = sorted(list(set(range(2, 12)) - _uids), reverse=True).pop()

    # Create user accountvfirst
    if not __execute_cmd('config -g cfgUserAdmin -o \
                 cfgUserAdminUserName -i {0} {1}'.format(uid, username),
                            host=host, admin_username=admin_username,
                            admin_password=admin_password):
        delete_user(username, uid)
        return False

    # Configure users permissions
    if not set_permissions(username, permissions, uid):
        log.warning('unable to set user permissions')
        delete_user(username, uid)
        return False

    # Configure users password
    if not change_password(username, password, uid):
        log.warning('unable to set user password')
        delete_user(username, uid)
        return False

    # Enable users admin
    if not __execute_cmd('config -g cfgUserAdmin -o \
                          cfgUserAdminEnable -i {0} 1'.format(uid)):
        delete_user(username, uid)
        return False

    return True


def set_permissions(username, permissions, 
                    uid=None, host=None, 
                    admin_username=None, admin_password=None):
    '''
    Configure users permissions

    CLI Example:

    .. code-block:: bash

        salt dell drac.set_permissions [USERNAME] [PRIVELEGES] [USER INDEX - optional]
        salt dell drac.set_permissions diana login,test_alerts,clear_logs 4

    DRAC Privileges
      * login                   : Login to iDRAC
      * drac                    : Configure iDRAC
      * user_management         : Configure Users
      * clear_logs              : Clear Logs
      * server_control_commands : Execute Server Control Commands
      * console_redirection     : Access Console Redirection
      * virtual_media           : Access Virtual Media
      * test_alerts             : Test Alerts
      * debug_commands          : Execute Debug Commands
    '''
    privileges = {'login': '0x0000001',
                  'drac': '0x0000002',
                  'user_management': '0x0000004',
                  'clear_logs': '0x0000008',
                  'server_control_commands': '0x0000010',
                  'console_redirection': '0x0000020',
                  'virtual_media': '0x0000040',
                  'test_alerts': '0x0000080',
                  'debug_commands': '0x0000100'}

    permission = 0

    # When users don't provide a user ID we need to search for this
    if uid is None:
        user = list_users()
        uid = user[username]['index']

    # Generate privilege bit mask
    for i in permissions.split(','):
        perm = i.strip()

        if perm in privileges:
            permission += int(privileges[perm], 16)

    return __execute_cmd('config -g cfgUserAdmin -o \
            cfgUserAdminPrivilege -i {0} 0x{1:08X}'.format(uid, permission),
                            host=host, admin_username=admin_username,
                            admin_password=admin_password)


def set_snmp(community, host=None, admin_username=None, admin_password=None):
    '''
    Configure SNMP community string

    CLI Example:

    .. code-block:: bash

        salt dell drac.set_snmp [COMMUNITY]
        salt dell drac.set_snmp public
    '''
    return __execute_cmd('config -g cfgOobSnmp -o \
            cfgOobSnmpAgentCommunity {0}'.format(community),
                            host=host, admin_username=admin_username,
                            admin_password=admin_password)


def set_network(ip, netmask, gateway, host=None, 
                admin_username=None, admin_password=None):
    '''
    Configure Network

    CLI Example:

    .. code-block:: bash

        salt dell drac.set_network [DRAC IP] [NETMASK] [GATEWAY]
        salt dell drac.set_network 192.168.0.2 255.255.255.0 192.168.0.1
    '''
    return __execute_cmd('setniccfg -s {0} {1} {2}'.format(
        ip, netmask, gateway, host=host, admin_username=admin_username,
        admin_password=admin_password
    ))


def server_reboot(host=None, admin_username=None, admin_password=None):
    '''
    Issues a power-cycle operation on the managed server. This action is
    similar to pressing the power button on the system's front panel to
    power down and then power up the system.

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_reboot
    '''
    return __execute_cmd('serveraction powercycle',
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def server_poweroff(host=None, admin_username=None, admin_password=None):
    '''
    Powers down the managed server.

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_poweroff
    '''
    return __execute_cmd('serveraction powerdown',
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def server_poweron(host=None, admin_username=None, admin_password=None):
    '''
    Powers up the managed server.

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_poweron
    '''
    return __execute_cmd('serveraction powerup',
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def server_hardreset(host=None, admin_username=None, admin_password=None):
    '''
    Performs a reset (reboot) operation on the managed server.

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_hardreset
    '''
    return __execute_cmd('serveraction hardreset',
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def server_pxe(host=None, admin_username=None, admin_password=None):
    '''
    Configure server to PXE perform a one off PXE boot

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_pxe
    '''
    if __execute_cmd('config -g cfgServerInfo -o cfgServerFirstBootDevice PXE',
                     host=host, admin_username=admin_username,
                     admin_password=admin_password):
        if __execute_cmd('config -g cfgServerInfo -o cfgServerBootOnce 1',
                         host=host, admin_username=admin_username,
                         admin_password=admin_password):
            return server_reboot
        else:
            log.warning('failed to set boot order')
            return False

    log.warning('failed to to configure PXE boot')
    return False
