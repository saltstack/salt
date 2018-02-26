# -*- coding: utf-8 -*-
'''
Manage Dell DRAC.

.. versionadded:: 2015.8.2
'''

# Import python libs
from __future__ import absolute_import
import logging
import os
import re

# Import Salt libs
from salt.exceptions import CommandExecutionError
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves import map

log = logging.getLogger(__name__)

__proxyenabled__ = ['fx2']

try:
    run_all = __salt__['cmd.run_all']
except (NameError, KeyError):
    import salt.modules.cmdmod
    __salt__ = {
        'cmd.run_all': salt.modules.cmdmod._run_all_quiet
    }


def __virtual__():
    if salt.utils.which('racadm'):
        return True

    return (False, 'The drac execution module cannot be loaded: racadm binary not in path.')


def __parse_drac(output):
    '''
    Parse Dell DRAC output
    '''
    drac = {}
    section = ''

    for i in output.splitlines():
        if i.strip().endswith(':') and '=' not in i:
            section = i[0:-1]
            drac[section] = {}
        if len(i.rstrip()) > 0 and '=' in i:
            if section in drac:
                drac[section].update(dict(
                    [[prop.strip() for prop in i.split('=')]]
                ))
            else:
                section = i.strip()
                if section not in drac and section:
                    drac[section] = {}

    return drac


def __execute_cmd(command, host=None,
                  admin_username=None, admin_password=None,
                  module=None):
    '''
    Execute rac commands
    '''
    if module:
        # -a takes 'server' or 'switch' to represent all servers
        # or all switches in a chassis.  Allow
        # user to say 'module=ALL_SERVER' or 'module=ALL_SWITCH'
        if module.startswith('ALL_'):
            modswitch = '-a '\
                        + module[module.index('_') + 1:len(module)].lower()
        else:
            modswitch = '-m {0}'.format(module)
    else:
        modswitch = ''
    if not host:
        # This is a local call
        cmd = __salt__['cmd.run_all']('racadm {0} {1}'.format(command,
                                                              modswitch))
    else:
        cmd = __salt__['cmd.run_all'](
            'racadm -r {0} -u {1} -p {2} {3} {4}'.format(host,
                                                         admin_username,
                                                         admin_password,
                                                         command,
                                                         modswitch),
        output_loglevel='quiet')

    if cmd['retcode'] != 0:
        log.warning('racadm return an exit code \'{0}\'.'
                    .format(cmd['retcode']))
        return False

    return True


def __execute_ret(command, host=None,
                  admin_username=None, admin_password=None,
                  module=None):
    '''
    Execute rac commands
    '''
    if module:
        if module == 'ALL':
            modswitch = '-a '
        else:
            modswitch = '-m {0}'.format(module)
    else:
        modswitch = ''
    if not host:
        # This is a local call
        cmd = __salt__['cmd.run_all']('racadm {0} {1}'.format(command,
                                                              modswitch))
    else:
        cmd = __salt__['cmd.run_all'](
            'racadm -r {0} -u {1} -p {2} {3} {4}'.format(host,
                                                         admin_username,
                                                         admin_password,
                                                         command,
                                                         modswitch),
        output_loglevel='quiet')

    if cmd['retcode'] != 0:
        log.warning('racadm return an exit code \'{0}\'.'
                    .format(cmd['retcode']))
    else:
        fmtlines = []
        for l in cmd['stdout'].splitlines():
            if l.startswith('Security Alert'):
                continue
            if l.startswith('RAC1168:'):
                break
            if l.startswith('RAC1169:'):
                break
            if l.startswith('Continuing execution'):
                continue

            if len(l.strip()) == 0:
                continue
            fmtlines.append(l)
            if '=' in l:
                continue
        cmd['stdout'] = '\n'.join(fmtlines)

    return cmd


def get_dns_dracname(host=None,
                     admin_username=None, admin_password=None):

    ret = __execute_ret('get iDRAC.NIC.DNSRacName', host=host,
                        admin_username=admin_username,
                        admin_password=admin_password)
    parsed = __parse_drac(ret['stdout'])
    return parsed


def set_dns_dracname(name,
                     host=None,
                     admin_username=None,
                     admin_password=None):

    ret = __execute_ret('set iDRAC.NIC.DNSRacName {0}'.format(name),
                        host=host,
                        admin_username=admin_username,
                        admin_password=admin_password)
    return ret


def system_info(host=None,
                admin_username=None, admin_password=None,
                module=None):
    '''
    Return System information

    CLI Example:

    .. code-block:: bash

        salt dell dracr.system_info
    '''
    cmd = __execute_ret('getsysinfo', host=host,
                        admin_username=admin_username,
                        admin_password=admin_password,
                        module=module)

    if cmd['retcode'] != 0:
        log.warning('racadm return an exit code \'{0}\'.'
                    .format(cmd['retcode']))
        return cmd

    return __parse_drac(cmd['stdout'])


def set_niccfg(ip=None, netmask=None, gateway=None, dhcp=False,
               host=None,
               admin_username=None,
               admin_password=None,
               module=None):

    cmdstr = 'setniccfg '

    if dhcp:
        cmdstr += '-d '
    else:
        cmdstr += '-s ' + ip + ' ' + netmask + ' ' + gateway

    return __execute_cmd(cmdstr, host=host,
                         admin_username=admin_username,
                         admin_password=admin_password,
                         module=module)


def set_nicvlan(vlan=None,
                host=None,
                admin_username=None,
                admin_password=None,
                module=None):

    cmdstr = 'setniccfg -v '

    if vlan:
        cmdstr += vlan

    ret = __execute_cmd(cmdstr, host=host,
                        admin_username=admin_username,
                        admin_password=admin_password,
                        module=module)

    return ret


def network_info(host=None,
                 admin_username=None,
                 admin_password=None,
                 module=None):
    '''
    Return Network Configuration

    CLI Example:

    .. code-block:: bash

        salt dell dracr.network_info
    '''

    inv = inventory(host=host, admin_username=admin_username,
                    admin_password=admin_password)
    if inv is None:
        cmd = {}
        cmd['retcode'] = -1
        cmd['stdout'] = 'Problem getting switch inventory'
        return cmd

    if module not in inv.get('switch') and module not in inv.get('server'):
        cmd = {}
        cmd['retcode'] = -1
        cmd['stdout'] = 'No module {0} found.'.format(module)
        return cmd

    cmd = __execute_ret('getniccfg', host=host,
                        admin_username=admin_username,
                        admin_password=admin_password,
                        module=module)

    if cmd['retcode'] != 0:
        log.warning('racadm return an exit code \'{0}\'.'
                    .format(cmd['retcode']))

    cmd['stdout'] = 'Network:\n' + 'Device = ' + module + '\n' + \
                    cmd['stdout']
    return __parse_drac(cmd['stdout'])


def nameservers(ns,
                host=None,
                admin_username=None,
                admin_password=None,
                module=None):
    '''
    Configure the nameservers on the DRAC

    CLI Example:

    .. code-block:: bash

        salt dell dracr.nameservers [NAMESERVERS]
        salt dell dracr.nameservers ns1.example.com ns2.example.com
            admin_username=root admin_password=calvin module=server-1
            host=192.168.1.1
    '''
    if len(ns) > 2:
        log.warning('racadm only supports two nameservers')
        return False

    for i in range(1, len(ns) + 1):
        if not __execute_cmd('config -g cfgLanNetworking -o '
                             'cfgDNSServer{0} {1}'.format(i, ns[i - 1]),
                             host=host,
                             admin_username=admin_username,
                             admin_password=admin_password,
                             module=module):
            return False

    return True


def syslog(server, enable=True, host=None,
           admin_username=None, admin_password=None, module=None):
    '''
    Configure syslog remote logging, by default syslog will automatically be
    enabled if a server is specified. However, if you want to disable syslog
    you will need to specify a server followed by False

    CLI Example:

    .. code-block:: bash

        salt dell dracr.syslog [SYSLOG IP] [ENABLE/DISABLE]
        salt dell dracr.syslog 0.0.0.0 False
    '''
    if enable and __execute_cmd('config -g cfgRemoteHosts -o '
                                'cfgRhostsSyslogEnable 1',
                                host=host,
                                admin_username=admin_username,
                                admin_password=admin_password,
                                module=None):
        return __execute_cmd('config -g cfgRemoteHosts -o '
                             'cfgRhostsSyslogServer1 {0}'.format(server),
                             host=host,
                             admin_username=admin_username,
                             admin_password=admin_password,
                             module=module)

    return __execute_cmd('config -g cfgRemoteHosts -o cfgRhostsSyslogEnable 0',
                         host=host,
                         admin_username=admin_username,
                         admin_password=admin_password,
                         module=module)


def email_alerts(action,
                 host=None,
                 admin_username=None,
                 admin_password=None):
    '''
    Enable/Disable email alerts

    CLI Example:

    .. code-block:: bash

        salt dell dracr.email_alerts True
        salt dell dracr.email_alerts False
    '''

    if action:
        return __execute_cmd('config -g cfgEmailAlert -o '
                             'cfgEmailAlertEnable -i 1 1', host=host,
                             admin_username=admin_username,
                             admin_password=admin_password)
    else:
        return __execute_cmd('config -g cfgEmailAlert -o '
                             'cfgEmailAlertEnable -i 1 0')


def list_users(host=None,
               admin_username=None,
               admin_password=None,
               module=None):
    '''
    List all DRAC users

    CLI Example:

    .. code-block:: bash

        salt dell dracr.list_users
    '''
    users = {}
    _username = ''

    for idx in range(1, 17):
        cmd = __execute_ret('getconfig -g '
                            'cfgUserAdmin -i {0}'.format(idx),
                            host=host, admin_username=admin_username,
                            admin_password=admin_password)

        if cmd['retcode'] != 0:
            log.warning('racadm return an exit code \'{0}\'.'
                        .format(cmd['retcode']))

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
                if len(_username) > 0:
                    users[_username].update({key: val})

    return users


def delete_user(username,
                uid=None,
                host=None,
                admin_username=None,
                admin_password=None):
    '''
    Delete a user

    CLI Example:

    .. code-block:: bash

        salt dell dracr.delete_user [USERNAME] [UID - optional]
        salt dell dracr.delete_user diana 4
    '''
    if uid is None:
        user = list_users()
        uid = user[username]['index']

    if uid:
        return __execute_cmd('config -g cfgUserAdmin -o '
                             'cfgUserAdminUserName -i {0} ""'.format(uid),
                             host=host, admin_username=admin_username,
                             admin_password=admin_password)

    else:
        log.warning('\'{0}\' does not exist'.format(username))
        return False


def change_password(username, password, uid=None, host=None,
                    admin_username=None, admin_password=None,
                    module=None):
    '''
    Change user's password

    CLI Example:

    .. code-block:: bash

        salt dell dracr.change_password [USERNAME] [PASSWORD] uid=[OPTIONAL]
            host=<remote DRAC> admin_username=<DRAC user>
            admin_password=<DRAC PW>
        salt dell dracr.change_password diana secret

    Note that if only a username is specified then this module will look up
    details for all 16 possible DRAC users.  This is time consuming, but might
    be necessary if one is not sure which user slot contains the one you want.
    Many late-model Dell chassis have 'root' as UID 1, so if you can depend
    on that then setting the password is much quicker.
    Raises an error if the supplied password is greater than 20 chars.
    '''
    if len(password) > 20:
        raise CommandExecutionError('Supplied password should be 20 characters or less')

    if uid is None:
        user = list_users(host=host, admin_username=admin_username,
                          admin_password=admin_password, module=module)
        uid = user[username]['index']

    if uid:
        return __execute_cmd('config -g cfgUserAdmin -o '
                             'cfgUserAdminPassword -i {0} {1}'
                             .format(uid, password),
                             host=host, admin_username=admin_username,
                             admin_password=admin_password, module=module)
    else:
        log.warning('\'{0}\' does not exist'.format(username))
        return False


def deploy_password(username, password, host=None, admin_username=None,
                    admin_password=None, module=None):
    '''
    Change the QuickDeploy password, used for switches as well

    CLI Example:

    .. code-block:: bash

        salt dell dracr.deploy_password [USERNAME] [PASSWORD]
            host=<remote DRAC> admin_username=<DRAC user>
            admin_password=<DRAC PW>
        salt dell dracr.change_password diana secret

    Note that if only a username is specified then this module will look up
    details for all 16 possible DRAC users.  This is time consuming, but might
    be necessary if one is not sure which user slot contains the one you want.
    Many late-model Dell chassis have 'root' as UID 1, so if you can depend
    on that then setting the password is much quicker.
    '''
    return __execute_cmd('deploy -u {0} -p {1}'.format(
        username, password), host=host, admin_username=admin_username,
        admin_password=admin_password, module=module
    )


def deploy_snmp(snmp, host=None, admin_username=None,
                admin_password=None, module=None):
    '''
    Change the QuickDeploy SNMP community string, used for switches as well

    CLI Example:

    .. code-block:: bash

        salt dell dracr.deploy_snmp SNMP_STRING
            host=<remote DRAC or CMC> admin_username=<DRAC user>
            admin_password=<DRAC PW>
        salt dell dracr.deploy_password diana secret

    '''
    return __execute_cmd('deploy -v SNMPv2 {0} ro'.format(snmp),
                         host=host,
                         admin_username=admin_username,
                         admin_password=admin_password,
                         module=module)


def create_user(username, password, permissions,
                users=None, host=None,
                admin_username=None, admin_password=None):
    '''
    Create user accounts

    CLI Example:

    .. code-block:: bash

        salt dell dracr.create_user [USERNAME] [PASSWORD] [PRIVILEGES]
        salt dell dracr.create_user diana secret login,test_alerts,clear_logs

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

    # Create user account first
    if not __execute_cmd('config -g cfgUserAdmin -o '
                         'cfgUserAdminUserName -i {0} {1}'
                                 .format(uid, username),
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
    if not __execute_cmd('config -g cfgUserAdmin -o '
                         'cfgUserAdminEnable -i {0} 1'.format(uid)):
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

        salt dell dracr.set_permissions [USERNAME] [PRIVILEGES]
             [USER INDEX - optional]
        salt dell dracr.set_permissions diana login,test_alerts,clear_logs 4

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

    return __execute_cmd('config -g cfgUserAdmin -o '
                         'cfgUserAdminPrivilege -i {0} 0x{1:08X}'
                         .format(uid, permission),
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def set_snmp(community, host=None,
             admin_username=None, admin_password=None):
    '''
    Configure CMC or individual iDRAC SNMP community string.
    Use ``deploy_snmp`` for configuring chassis switch SNMP.

    CLI Example:

    .. code-block:: bash

        salt dell dracr.set_snmp [COMMUNITY]
        salt dell dracr.set_snmp public
    '''
    return __execute_cmd('config -g cfgOobSnmp -o '
                         'cfgOobSnmpAgentCommunity {0}'.format(community),
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def set_network(ip, netmask, gateway, host=None,
                admin_username=None, admin_password=None):
    '''
    Configure Network on the CMC or individual iDRAC.
    Use ``set_niccfg`` for blade and switch addresses.

    CLI Example:

    .. code-block:: bash

        salt dell dracr.set_network [DRAC IP] [NETMASK] [GATEWAY]
        salt dell dracr.set_network 192.168.0.2 255.255.255.0 192.168.0.1
            admin_username=root admin_password=calvin host=192.168.1.1
    '''
    return __execute_cmd('setniccfg -s {0} {1} {2}'.format(
        ip, netmask, gateway, host=host, admin_username=admin_username,
        admin_password=admin_password
    ))


def server_power(status, host=None,
                  admin_username=None,
                  admin_password=None,
                  module=None):
    '''
    status
        One of 'powerup', 'powerdown', 'powercycle', 'hardreset',
        'graceshutdown'

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    module
        The element to reboot on the chassis such as a blade. If not provided,
        the chassis will be rebooted.

    CLI Example:

    .. code-block:: bash

        salt dell dracr.server_reboot
        salt dell dracr.server_reboot module=server-1

    '''
    return __execute_cmd('serveraction {0}'.format(status),
                         host=host, admin_username=admin_username,
                         admin_password=admin_password, module=module)


def server_reboot(host=None,
                  admin_username=None,
                  admin_password=None,
                  module=None):
    '''
    Issues a power-cycle operation on the managed server. This action is
    similar to pressing the power button on the system's front panel to
    power down and then power up the system.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    module
        The element to reboot on the chassis such as a blade. If not provided,
        the chassis will be rebooted.

    CLI Example:

    .. code-block:: bash

        salt dell dracr.server_reboot
        salt dell dracr.server_reboot module=server-1

    '''
    return __execute_cmd('serveraction powercycle',
                         host=host, admin_username=admin_username,
                         admin_password=admin_password, module=module)


def server_poweroff(host=None,
                    admin_username=None,
                    admin_password=None,
                    module=None):
    '''
    Powers down the managed server.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    module
        The element to power off on the chassis such as a blade.
        If not provided, the chassis will be powered off.

    CLI Example:

    .. code-block:: bash

        salt dell dracr.server_poweroff
        salt dell dracr.server_poweroff module=server-1
    '''
    return __execute_cmd('serveraction powerdown',
                         host=host, admin_username=admin_username,
                         admin_password=admin_password, module=module)


def server_poweron(host=None,
                   admin_username=None,
                   admin_password=None,
                   module=None):
    '''
    Powers up the managed server.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    module
        The element to power on located on the chassis such as a blade. If
        not provided, the chassis will be powered on.

    CLI Example:

    .. code-block:: bash

        salt dell dracr.server_poweron
        salt dell dracr.server_poweron module=server-1
    '''
    return __execute_cmd('serveraction powerup',
                         host=host, admin_username=admin_username,
                         admin_password=admin_password, module=module)


def server_hardreset(host=None,
                     admin_username=None,
                     admin_password=None,
                     module=None):
    '''
    Performs a reset (reboot) operation on the managed server.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    module
        The element to hard reset on the chassis such as a blade. If
        not provided, the chassis will be reset.

    CLI Example:

    .. code-block:: bash

        salt dell dracr.server_hardreset
        salt dell dracr.server_hardreset module=server-1
    '''
    return __execute_cmd('serveraction hardreset',
                         host=host,
                         admin_username=admin_username,
                         admin_password=admin_password,
                         module=module)


def server_powerstatus(host=None,
                       admin_username=None,
                       admin_password=None,
                       module=None):
    '''
    return the power status for the passed module

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_powerstatus
    '''
    ret = __execute_ret('serveraction powerstatus',
                        host=host, admin_username=admin_username,
                        admin_password=admin_password,
                        module=module)

    result = {'retcode': 0}
    if ret['stdout'] == 'ON':
        result['status'] = True
        result['comment'] = 'Power is on'
    if ret['stdout'] == 'OFF':
        result['status'] = False
        result['comment'] = 'Power is on'
    if ret['stdout'].startswith('ERROR'):
        result['status'] = False
        result['comment'] = ret['stdout']

    return result


def server_pxe(host=None,
               admin_username=None,
               admin_password=None):
    '''
    Configure server to PXE perform a one off PXE boot

    CLI Example:

    .. code-block:: bash

        salt dell dracr.server_pxe
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


def list_slotnames(host=None,
                   admin_username=None,
                   admin_password=None):
    '''
    List the names of all slots in the chassis.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    CLI Example:

    .. code-block:: bash

        salt-call --local dracr.list_slotnames host=111.222.333.444
            admin_username=root admin_password=secret

    '''
    slotraw = __execute_ret('getslotname',
                            host=host, admin_username=admin_username,
                            admin_password=admin_password)

    if slotraw['retcode'] != 0:
        return slotraw
    slots = {}
    stripheader = True
    for l in slotraw['stdout'].splitlines():
        if l.startswith('<'):
            stripheader = False
            continue
        if stripheader:
            continue
        fields = l.split()
        slots[fields[0]] = {}
        slots[fields[0]]['slot'] = fields[0]
        if len(fields) > 1:
            slots[fields[0]]['slotname'] = fields[1]
        else:
            slots[fields[0]]['slotname'] = ''
        if len(fields) > 2:
            slots[fields[0]]['hostname'] = fields[2]
        else:
            slots[fields[0]]['hostname'] = ''

    return slots


def get_slotname(slot, host=None, admin_username=None, admin_password=None):
    '''
    Get the name of a slot number in the chassis.

    slot
        The number of the slot for which to obtain the name.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    CLI Example:

    .. code-block:: bash

        salt-call --local dracr.get_slotname 0 host=111.222.333.444
           admin_username=root admin_password=secret

    '''
    slots = list_slotnames(host=host, admin_username=admin_username,
                           admin_password=admin_password)
    # The keys for this dictionary are strings, not integers, so convert the
    # argument to a string
    slot = str(slot)
    return slots[slot]['slotname']


def set_slotname(slot, name, host=None,
                 admin_username=None, admin_password=None):
    '''
    Set the name of a slot in a chassis.

    slot
        The slot number to change.

    name
        The name to set. Can only be 15 characters long.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    CLI Example:

    .. code-block:: bash

        salt '*' dracr.set_slotname 2 my-slotname host=111.222.333.444
            admin_username=root admin_password=secret

    '''
    return __execute_cmd('config -g cfgServerInfo -o cfgServerName -i {0} {1}'.format(slot, name),
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def set_chassis_name(name,
                     host=None,
                     admin_username=None,
                     admin_password=None):
    '''
    Set the name of the chassis.

    name
        The name to be set on the chassis.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    CLI Example:

    .. code-block:: bash

        salt '*' dracr.set_chassis_name my-chassis host=111.222.333.444
            admin_username=root admin_password=secret

    '''
    return __execute_cmd('setsysinfo -c chassisname {0}'.format(name),
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def get_chassis_name(host=None, admin_username=None, admin_password=None):
    '''
    Get the name of a chassis.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    CLI Example:

    .. code-block:: bash

        salt '*' dracr.get_chassis_name host=111.222.333.444
            admin_username=root admin_password=secret

    '''
    return bare_rac_cmd('getchassisname', host=host,
                        admin_username=admin_username,
                        admin_password=admin_password)


def inventory(host=None, admin_username=None, admin_password=None):
    def mapit(x, y):
        return {x: y}

    fields = {}
    fields['server'] = ['name', 'idrac_version', 'blade_type', 'gen',
                        'updateable']
    fields['switch'] = ['name', 'model_name', 'hw_version', 'fw_version']
    fields['cmc'] = ['name', 'cmc_version', 'updateable']
    fields['chassis'] = ['name', 'fw_version', 'fqdd']

    rawinv = __execute_ret('getversion', host=host,
                           admin_username=admin_username,
                           admin_password=admin_password)

    if rawinv['retcode'] != 0:
        return rawinv

    in_server = False
    in_switch = False
    in_cmc = False
    in_chassis = False
    ret = {}
    ret['server'] = {}
    ret['switch'] = {}
    ret['cmc'] = {}
    ret['chassis'] = {}
    for l in rawinv['stdout'].splitlines():
        if l.startswith('<Server>'):
            in_server = True
            in_switch = False
            in_cmc = False
            in_chassis = False
            continue

        if l.startswith('<Switch>'):
            in_server = False
            in_switch = True
            in_cmc = False
            in_chassis = False
            continue

        if l.startswith('<CMC>'):
            in_server = False
            in_switch = False
            in_cmc = True
            in_chassis = False
            continue

        if l.startswith('<Chassis Infrastructure>'):
            in_server = False
            in_switch = False
            in_cmc = False
            in_chassis = True
            continue

        if len(l) < 1:
            continue

        line = re.split('  +', l.strip())

        if in_server:
            ret['server'][line[0]] = dict(
                (k, v) for d in map(mapit, fields['server'], line) for (k, v)
                in d.items())
        if in_switch:
            ret['switch'][line[0]] = dict(
                (k, v) for d in map(mapit, fields['switch'], line) for (k, v)
                in d.items())
        if in_cmc:
            ret['cmc'][line[0]] = dict(
                (k, v) for d in map(mapit, fields['cmc'], line) for (k, v) in
                d.items())
        if in_chassis:
            ret['chassis'][line[0]] = dict(
                (k, v) for d in map(mapit, fields['chassis'], line) for k, v in
                d.items())

    return ret


def set_chassis_location(location,
                         host=None,
                         admin_username=None,
                         admin_password=None):
    '''
    Set the location of the chassis.

    location
        The name of the location to be set on the chassis.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    CLI Example:

    .. code-block:: bash

        salt '*' dracr.set_chassis_location location-name host=111.222.333.444
            admin_username=root admin_password=secret

    '''
    return __execute_cmd('setsysinfo -c chassislocation {0}'.format(location),
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def get_chassis_location(host=None,
                         admin_username=None,
                         admin_password=None):
    '''
    Get the location of the chassis.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    CLI Example:

    .. code-block:: bash

        salt '*' dracr.set_chassis_location host=111.222.333.444
           admin_username=root admin_password=secret

    '''
    return system_info(host=host,
                       admin_username=admin_username,
                       admin_password=admin_password)['Chassis Information']['Chassis Location']


def set_chassis_datacenter(location,
                         host=None,
                         admin_username=None,
                         admin_password=None):
    '''
    Set the location of the chassis.

    location
        The name of the datacenter to be set on the chassis.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    CLI Example:

    .. code-block:: bash

        salt '*' dracr.set_chassis_datacenter datacenter-name host=111.222.333.444
            admin_username=root admin_password=secret

    '''
    return set_general('cfgLocation', 'cfgLocationDatacenter', location,
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def get_chassis_datacenter(host=None,
                         admin_username=None,
                         admin_password=None):
    '''
    Get the datacenter of the chassis.

    host
        The chassis host.

    admin_username
        The username used to access the chassis.

    admin_password
        The password used to access the chassis.

    CLI Example:

    .. code-block:: bash

        salt '*' dracr.set_chassis_location host=111.222.333.444
           admin_username=root admin_password=secret

    '''
    return get_general('cfgLocation', 'cfgLocationDatacenter', host=host,
                       admin_username=admin_username, admin_password=admin_password)


def set_general(cfg_sec, cfg_var, val, host=None,
                admin_username=None, admin_password=None):
    return __execute_cmd('config -g {0} -o {1} {2}'.format(cfg_sec,
                                                           cfg_var, val),
                         host=host,
                         admin_username=admin_username,
                         admin_password=admin_password)


def get_general(cfg_sec, cfg_var, host=None,
                admin_username=None, admin_password=None):
    ret = __execute_ret('getconfig -g {0} -o {1}'.format(cfg_sec, cfg_var),
                        host=host,
                        admin_username=admin_username,
                        admin_password=admin_password)

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return ret


def idrac_general(blade_name, command, idrac_password=None,
                  host=None,
                  admin_username=None, admin_password=None):
    '''
    Run a generic racadm command against a particular
    blade in a chassis.  Blades are usually named things like
    'server-1', 'server-2', etc.  If the iDRAC has a different
    password than the CMC, then you can pass it with the
    idrac_password kwarg.

    :param blade_name: Name of the blade to run the command on
    :param command: Command like to pass to racadm
    :param idrac_password: Password for the iDRAC if different from the CMC
    :param host: Chassis hostname
    :param admin_username: CMC username
    :param admin_password: CMC password
    :return: stdout if the retcode is 0, otherwise a standard cmd.run_all dictionary

    CLI Example:

    .. code-block:: bash

        salt fx2 chassis.cmd idrac_general server-1 'get BIOS.SysProfileSettings'

    '''

    module_network = network_info(host, admin_username,
                                  admin_password, blade_name)

    if idrac_password is not None:
        password = idrac_password
    else:
        password = admin_password

    idrac_ip = module_network['Network']['IP Address']

    ret = __execute_ret(command, host=idrac_ip,
                        admin_username='root',
                        admin_password=password)

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return ret


def _update_firmware(cmd,
                     host=None,
                     admin_username=None,
                     admin_password=None):

    if not admin_username:
        admin_username = __pillar__['proxy']['admin_username']
    if not admin_username:
        admin_password = __pillar__['proxy']['admin_password']

    ret = __execute_ret(cmd,
                        host=host,
                        admin_username=admin_username,
                        admin_password=admin_password)

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return ret


def bare_rac_cmd(cmd, host=None,
                admin_username=None, admin_password=None):
    ret = __execute_ret('{0}'.format(cmd),
                        host=host,
                        admin_username=admin_username,
                        admin_password=admin_password)

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return ret


def update_firmware(filename,
                    host=None,
                    admin_username=None,
                    admin_password=None):
    '''
    Updates firmware using local firmware file

    .. code-block:: bash

         salt dell dracr.update_firmware firmware.exe

    This executes the following command on your FX2
    (using username and password stored in the pillar data)

    .. code-block:: bash

         racadm update –f firmware.exe -u user –p pass

    '''
    if os.path.exists(filename):
        return _update_firmware('update -f {0}'.format(filename),
                                host=None,
                                admin_username=None,
                                admin_password=None)
    else:
        raise CommandExecutionError('Unable to find firmware file {0}'
                                    .format(filename))


def update_firmware_nfs_or_cifs(filename, share,
                                host=None,
                                admin_username=None,
                                admin_password=None):
    '''
    Executes the following for CIFS
    (using username and password stored in the pillar data)

    .. code-block:: bash

         racadm update -f <updatefile> -u user –p pass -l //IP-Address/share

    Or for NFS
    (using username and password stored in the pillar data)

    .. code-block:: bash

          racadm update -f <updatefile> -u user –p pass -l IP-address:/share


    Salt command for CIFS:

    .. code-block:: bash

         salt dell dracr.update_firmware_nfs_or_cifs \
         firmware.exe //IP-Address/share


    Salt command for NFS:

    .. code-block:: bash

         salt dell dracr.update_firmware_nfs_or_cifs \
         firmware.exe IP-address:/share
    '''
    if os.path.exists(filename):
        return _update_firmware('update -f {0} -l {1}'.format(filename, share),
                                host=None,
                                admin_username=None,
                                admin_password=None)
    else:
        raise CommandExecutionError('Unable to find firmware file {0}'
                                    .format(filename))

# def get_idrac_nic()
