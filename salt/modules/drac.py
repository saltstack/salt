# -*- coding: utf-8 -*-
'''
Manage Dell DRAC
'''

import salt.utils

import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''

    '''
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


def getsysinfo():
    '''
    Return System information

    CLI Example:

    .. code-block:: bash

        salt dell drac.getsysinfo
    '''
    drac = {}
    section = ''

    cmd = __salt__['cmd.run_all']('racadm getsysinfo')

    if cmd['retcode'] != 0:
        log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

    return __parse_drac(cmd['stdout'])


def getniccfg():
    '''
    Return Network Configuration

    CLI Example:

    .. code-block:: bash

        salt dell drac.getniccfg
    '''

    cmd = __salt__['cmd.run_all']('racadm getniccfg')

    if cmd['retcode'] != 0:
        log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

    return __parse_drac(cmd['stdout'])


def nameservers(*ns):
    '''
    Configure the nameservers on the DRAC

    CLI Example:

    .. code-block:: bash

        salt dell drac.nameservers ns1.example.com
        salt dell drac.nameservers ns1.example.com ns2.example.com
    '''
    if len(ns) > 2:
        log.warn('racadm only supports two nameservers')
        return False

    for i in range(1, len(ns) + 1):
        cmd = __salt__['cmd.run_all']('racadm config -g cfgLanNetworking -o cfgDNSServer{0} {1}'.format(i, ns[i - 1]))

        if cmd['retcode'] != 0:
            log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))
            return False

    return True


def syslog(server, enable=True):
    '''
    Configure syslog remote logging, by default syslog will automatically be
    enabled if a server is specified. However, if you want to disable syslog
    you will need to specify a server followed by False

    CLI Example:

    .. code-block:: bash

        salt dell drac.syslog 10.0.0.1 True
        salt dell drac.syslog 0.0.0.0 False
    '''
    if enable:
        cmd = __salt__['cmd.run_all']('racadm config -g cfgRemoteHosts -o cfgRhostsSyslogEnable 1')

        if cmd['retcode'] != 0:
            log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))
        else:
            cmd = __salt__['cmd.run_all']('racadm config -g cfgRemoteHosts -o cfgRhostsSyslogServer1 {0}'.format(server))

            if cmd['retcode'] != 0:
                log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

            return True

    cmd = __salt__['cmd.run_all']('racadm config -g cfgRemoteHosts -o cfgRhostsSyslogEnable 0')

    if cmd['retcode'] != 0:
        log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

    return True


def email_alerts(action):
    '''
    Enable/Disable email alerts

    CLI Example:

    .. code-block:: bash

        salt dell drac.email_alerts True
        salt dell drac.email_alerts False
    '''

    if action:
        cmd = __salt__['cmd.run_all']('racadm config -g cfgEmailAlert -o cfgEmailAlertEnable -i 1 1')
    else:
        cmd = __salt__['cmd.run_all']('racadm config -g cfgEmailAlert -o cfgEmailAlertEnable -i 1 0')

    if cmd['retcode'] != 0:
        if cmd['retcode'] != 0:
            log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

        return False

    return True


def list_users():
    '''
    List all DRAC users

    CLI Example:

    .. code-block:: bash

        salt dell drac.list_users
    '''
    users = {}
    _username = ''

    for i in range(1, 12):
        cmd = __salt__['cmd.run_all']('racadm getconfig -g cfgUserAdmin -i {0}'.format(i))

        if cmd['retcode'] != 0:
            log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

        for user in cmd['stdout'].splitlines():
            if 'cfgUserAdminIndex' in user or user.startswith('#'):
                continue

            (k, v) = user.split('=')

            if k.startswith('cfgUserAdminUserName'):
                _username = v.strip()

                if v:
                    users[_username] = {'index': i}
                else:
                    break
            else:
                users[_username].update({k: v})

    return users


def delete_user(username, uid=None):
    '''
    Delete a user

    CLI Example:

    .. code-block:: bash

        salt dell drac.delete_user damian
        salt dell drac.delete_user diana 4
    '''
    if uid is None:
        user = list_users()
        uid = user[username]['index']

    if uid:
        cmd = __salt__['cmd.run_all']('racadm config -g cfgUserAdmin -o \
                                       cfgUserAdminUserName -i {0} ""'.format(
                                       uid))
    else:
        log.warn('\'{0}\' does not exist'.format(username))
        return False

    if cmd['retcode'] != 0:
        log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))
        return False

    return True


def change_password(username, password, uid=None):
    '''
    Change users password

    CLI Example:

    .. code-block:: bash

        salt dell drac.change_password damian secret
        salt dell drac.change_password diana secret
    '''
    if uid is None:
        user = list_users()
        uid = user[username]['index']

    if uid:
        cmd = __salt__['cmd.run_all']('racadm config -g cfgUserAdmin -o \
                                       cfgUserAdminPassword -i {0} {1}'.format(
                                       uid, password))

        if cmd['retcode'] != 0:
            log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))
            return False
    else:
        log.warn('\'{0}\' does not exist'.format(username))
        return False

    return True


def create_user(username, password, permissions):
    '''
    Create user accounts

    CLI Example:

    .. code-block:: bash

        salt dell drac.create_user damian secret login,drac,user_management
        salt dell drac.create_user diana secret login,test_alerts,clear_logs

    DRAC Priveleges
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

    user = list_users()

    if username in user:
        log.warn('\'{0}\' already exists'.format(username))
        return False

    for i in user.keys():
        _uids.add(user[i]['index'])

    uid = sorted(list(set(xrange(2, 12)) - _uids), reverse=True).pop()

    cmd = __salt__['cmd.run_all']('racadm config -g cfgUserAdmin -o \
                                   cfgUserAdminUserName -i {0} {1}'.format(uid, username))

    if cmd['retcode'] != 0:
        log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))
        delete_user(username, uid)
        return False

    cmd = __salt__['cmd.run_all']('racadm config -g cfgUserAdmin -o \
                                   cfgUserAdminEnable -i {0} 1'.format(uid))

    if cmd['retcode'] != 0:
        log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))
        delete_user(username, uid)
        return False

    if not set_permissions(username, permissions, uid):
        log.warn('unable to set user permissions')
        delete_user(username, uid)
        return False

    if not change_password(username, password, uid):
        log.warn('unable to set user password')
        delete_user(username, uid)
        return False

    return True


def set_permissions(username, permissions, uid=None):
    '''
    Configure users permissions

    CLI Example:

    .. code-block:: bash

        salt dell drac.set_permissions damian login,drac,user_management
        salt dell drac.set_permissions diana login,test_alerts,clear_logs 4

    DRAC Priveleges
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

    permission = "0x%0.8X" % permission

    cmd = __salt__['cmd.run_all']('racadm config -g cfgUserAdmin -o cfgUserAdminPrivilege -i {0} {1}'.format(uid, permission))

    if cmd['retcode'] != 0:
        log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))
        return False

    return True


def set_snmp(community):
    '''
    Configure SNMP community string

    CLI Example:

    .. code-block:: bash

        salt dell drac.create_user damian login,drac,user_management
        salt dell drac.create_user diana login,test_alerts,clear_logs 4
    '''
    cmd = __salt__['cmd.run_all']('racadm config -g cfgOobSnmp -o cfgOobSnmpAgentCommunity {0}'.format(community))

    if cmd['retcode'] != 0:
        log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))
        return False

    return True
