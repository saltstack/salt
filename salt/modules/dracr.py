# -*- coding: utf-8 -*-
'''
Manage Dell DRAC
'''

# Import python libs
from __future__ import absolute_import
import logging
import re

# Import Salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import \
    range  # pylint: disable=import-error,no-name-in-module,redefined-builtin

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
            modswitch = '-a '+module[module.index('_')+1:len(module)].lower()
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
                                                         modswitch))

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
                                                         modswitch))

    if cmd['retcode'] != 0:
        log.warning('racadm return an exit code \'{0}\'.'
                    .format(cmd['retcode']))
    else:
        fmtlines = []
        for l in cmd['stdout'].splitlines():
            if l.startswith('Security Alert'):
                continue
            if l.startswith('Continuing execution'):
                continue
            if len(l.strip()) == 0:
                continue
            fmtlines.append(l)
        cmd['stdout'] = '\n'.join(fmtlines)

    return cmd


def system_info(host=None,
                admin_username=None, admin_password=None,
                module=None):
    '''
    Return System information

    CLI Example:

    .. code-block:: bash

        salt dell drac.system_info
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


def set_niccfg(ip, subnet, gateway, dhcp=False,
               host=None,
               admin_username=None,
               admin_password=None,
               module=None):

    cmdstr = 'setniccfg '

    if dhcp:
        cmdstr += '-d '
    else:
        cmdstr += '-s ' + ip + ' ' + subnet + ' ' + gateway

    ret = __execute_cmd(cmdstr, host=host,
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

        salt dell drac.network_info
    '''

    cmd = __execute_ret('getniccfg', host=host,
                        admin_username=admin_username,
                        admin_password=admin_password,
                        module=None)

    if cmd['retcode'] != 0:
        log.warning('racadm return an exit code \'{0}\'.'
                    .format(cmd['retcode']))

    return __parse_drac(cmd['stdout'])


def nameservers(ns, host=None,
                admin_username=None, admin_password=None,
                module=None):
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
        if not __execute_cmd('config -g cfgLanNetworking -o '
                             'cfgDNSServer{0} {1}'.format(i, ns[i - 1]),
                             host=host,
                             admin_username=admin_username,
                             admin_password=admin_password,
                             module=None):
            return False

    return True


def syslog(server, enable=True, host=None,
           admin_username=None, admin_password=None,
           module=None):
    '''
    Configure syslog remote logging, by default syslog will automatically be
    enabled if a server is specified. However, if you want to disable syslog
    you will need to specify a server followed by False

    CLI Example:

    .. code-block:: bash

        salt dell drac.syslog [SYSLOG IP] [ENABLE/DISABLE]
        salt dell drac.syslog 0.0.0.0 False
    '''
    if enable and __execute_cmd('config -g cfgRemoteHosts -o '
                                'cfgRhostsSyslogEnable 1'):
        return __execute_cmd('config -g cfgRemoteHosts -o '
                             'cfgRhostsSyslogServer1 {0}'.format(server))

    return __execute_cmd('config -g cfgRemoteHosts -o cfgRhostsSyslogEnable 0',
                         host=host,
                         admin_username=admin_username,
                         admin_password=admin_password)


def email_alerts(action, host=None,
                 admin_username=None,
                 admin_password=None,
                 module=None):
    '''
    Enable/Disable email alerts

    CLI Example:

    .. code-block:: bash

        salt dell drac.email_alerts True
        salt dell drac.email_alerts False
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

        salt dell drac.list_users
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


def delete_user(username, uid=None,
                host=None,
                admin_username=None,
                admin_password=None,
                module=None):
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

        salt dell drac.change_password [USERNAME] [PASSWORD] uid=[OPTIONAL]
            host=<remote DRAC> admin_username=<DRAC user>
            admin_password=<DRAC PW>
        salt dell drac.change_password diana secret

    Note that if only a username is specified then this module will look up
    details for all 16 possible DRAC users.  This is time consuming, but might
    be necessary if one is not sure which user slot contains the one you want.
    Many late-model Dell chassis have 'root' as UID 1, so if you can depend
    on that then setting the password is much quicker.
    '''
    if uid is None:
        user = list_users(host=host, admin_username=admin_username,
                          admin_password=admin_password)
        uid = user[username]['index']

    if uid:
        return __execute_cmd('config -g cfgUserAdmin -o '
                             'cfgUserAdminPassword -i {0} {1}'
                             .format(uid, password),
                             host=host, admin_username=admin_username,
                             admin_password=admin_password)
    else:
        log.warning('\'{0}\' does not exist'.format(username))
        return False


def deploy_password(username, password, host=None, admin_username=None,
                    admin_password=None, module=None):
    return __execute_cmd('deploy -u {0} -p {1}'.format(
        username, password), host=host, admin_username=admin_username,
        admin_password=admin_password, module=module
    )


def deploy_snmp(snmp, host=None, admin_username=None,
                admin_password=None, module=None):
    return __execute_cmd('deploy -v SNMPv2 {0} ro'.format(snmp),
        host=host, admin_username=admin_username,
        admin_password=admin_password, module=module
    )
def create_user(username, password, permissions,
                users=None, host=None,
                admin_username=None, admin_password=None,
                module=None):
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
                    admin_username=None, admin_password=None,
                    module=None):
    '''
    Configure users permissions

    CLI Example:

    .. code-block:: bash

        salt dell drac.set_permissions [USERNAME] [PRIVELEGES]
             [USER INDEX - optional]
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

    return __execute_cmd('config -g cfgUserAdmin -o '
                         'cfgUserAdminPrivilege -i {0} 0x{1:08X}'
                         .format(uid, permission),
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def set_snmp(community, host=None,
             admin_username=None, admin_password=None,
             module=None):
    '''
    Configure SNMP community string

    CLI Example:

    .. code-block:: bash

        salt dell drac.set_snmp [COMMUNITY]
        salt dell drac.set_snmp public
    '''
    return __execute_cmd('config -g cfgOobSnmp -o '
                         'cfgOobSnmpAgentCommunity {0}'.format(community),
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def set_network(ip, netmask, gateway, host=None,
                admin_username=None, admin_password=None,
                module=None):
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


def server_reboot(host=None,
                  admin_username=None, admin_password=None,
                  module=None):
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


def server_poweroff(host=None,
                    admin_username=None, admin_password=None,
                    module=None):
    '''
    Powers down the managed server.

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_poweroff
    '''
    return __execute_cmd('serveraction powerdown',
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def server_poweron(host=None,
                   admin_username=None, admin_password=None,
                   module=None):
    '''
    Powers up the managed server.

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_poweron
    '''
    return __execute_cmd('serveraction powerup',
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def server_hardreset(host=None,
                     admin_username=None, admin_password=None,
                     module=None):
    '''
    Performs a reset (reboot) operation on the managed server.

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_hardreset
    '''
    return __execute_cmd('serveraction hardreset',
                         host=host, admin_username=admin_username,
                         admin_password=admin_password)


def server_pxe(host=None,
               admin_username=None, admin_password=None,
               module=None):
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


def get_slotname(host=None,
                 admin_username=None, admin_password=None):
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


def set_slotname(slot, name, host=None,
                 admin_username=None, admin_password=None):
    return __execute_cmd('setslotname -i {0} {1}'.format(
        slot, name[0:14], admin_username=admin_username,
        admin_password=admin_password))


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

        salt '*' dracr.set_chassis_name my-chassis host=111.222.333.444 admin_username=root admin_password=secret

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

        salt '*' dracr.get_chassis_name host=111.222.333.444 admin_username=root admin_password=secret

    '''
    return system_info(host=host,
                       admin_username=admin_username,
                       admin_password=admin_password)['Chassis Information']['Chassis Name']


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

        salt '*' dracr.set_chassis_location location-name host=111.222.333.444 admin_username=root admin_password=secret

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

        salt '*' dracr.set_chassis_location host=111.222.333.444 admin_username=root admin_password=secret

    '''
    return system_info(host=host,
                       admin_username=admin_username,
                       admin_password=admin_password)['Chassis Information']['Chassis Location']


def set_general(cfgsec, cfgvar, val, host=None,
                admin_username=None, admin_password=None):
    return __execute_cmd('config -g {0} -o {1} {2}'
                         .format(cfgsec, cfgvar, val),
                         host=host,
                         admin_username=admin_username,
                         admin_password=admin_password)


def get_general(cfgsec, cfgvar, host=None,
                admin_username=None, admin_password=None,
                module=None):
    r = __execute_ret('getconfig -g {0} -o {1}'
                         .format(cfgsec, cfgvar),
                         host=host,
                         admin_username=admin_username,
                         admin_password=admin_password)

    if r['retcode'] == 0:
        return r['stdout']
    else:
        return r
