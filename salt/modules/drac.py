"""
Manage Dell DRAC
"""

import logging

import salt.utils.path

log = logging.getLogger(__name__)


def __virtual__():
    if salt.utils.path.which("racadm"):
        return True

    return (
        False,
        "The drac execution module cannot be loaded: racadm binary not in path.",
    )


def __parse_drac(output):
    """
    Parse Dell DRAC output
    """
    drac = {}
    section = ""

    for i in output.splitlines():
        if i.rstrip() and "=" in i:
            if section in drac:
                drac[section].update(dict([[prop.strip() for prop in i.split("=")]]))
        else:
            section = i.strip()[:-1]
            if section not in drac and section:
                drac[section] = {}

    return drac


def __execute_cmd(command):
    """
    Execute rac commands
    """
    cmd = __salt__["cmd.run_all"](f"racadm {command}")

    if cmd["retcode"] != 0:
        log.warning("racadm return an exit code '%s'.", cmd["retcode"])
        return False

    return True


def system_info():
    """
    Return System information

    CLI Example:

    .. code-block:: bash

        salt dell drac.system_info
    """
    cmd = __salt__["cmd.run_all"]("racadm getsysinfo")

    if cmd["retcode"] != 0:
        log.warning("racadm return an exit code '%s'.", cmd["retcode"])

    return __parse_drac(cmd["stdout"])


def network_info():
    """
    Return Network Configuration

    CLI Example:

    .. code-block:: bash

        salt dell drac.network_info
    """

    cmd = __salt__["cmd.run_all"]("racadm getniccfg")

    if cmd["retcode"] != 0:
        log.warning("racadm return an exit code '%s'.", cmd["retcode"])

    return __parse_drac(cmd["stdout"])


def nameservers(*ns):
    """
    Configure the nameservers on the DRAC

    CLI Example:

    .. code-block:: bash

        salt dell drac.nameservers [NAMESERVERS]
        salt dell drac.nameservers ns1.example.com ns2.example.com
    """
    if len(ns) > 2:
        log.warning("racadm only supports two nameservers")
        return False

    for i in range(1, len(ns) + 1):
        if not __execute_cmd(
            f"config -g cfgLanNetworking -o cfgDNSServer{i} {ns[i - 1]}"
        ):
            return False

    return True


def syslog(server, enable=True):
    """
    Configure syslog remote logging, by default syslog will automatically be
    enabled if a server is specified. However, if you want to disable syslog
    you will need to specify a server followed by False

    CLI Example:

    .. code-block:: bash

        salt dell drac.syslog [SYSLOG IP] [ENABLE/DISABLE]
        salt dell drac.syslog 0.0.0.0 False
    """
    if enable and __execute_cmd("config -g cfgRemoteHosts -o cfgRhostsSyslogEnable 1"):
        return __execute_cmd(
            f"config -g cfgRemoteHosts -o cfgRhostsSyslogServer1 {server}"
        )

    return __execute_cmd("config -g cfgRemoteHosts -o cfgRhostsSyslogEnable 0")


def email_alerts(action):
    """
    Enable/Disable email alerts

    CLI Example:

    .. code-block:: bash

        salt dell drac.email_alerts True
        salt dell drac.email_alerts False
    """

    if action:
        return __execute_cmd("config -g cfgEmailAlert -o cfgEmailAlertEnable -i 1 1")
    else:
        return __execute_cmd("config -g cfgEmailAlert -o cfgEmailAlertEnable -i 1 0")


def list_users():
    """
    List all DRAC users

    CLI Example:

    .. code-block:: bash

        salt dell drac.list_users
    """
    users = {}
    _username = ""

    for idx in range(1, 17):
        cmd = __salt__["cmd.run_all"](f"racadm getconfig -g cfgUserAdmin -i {idx}")

        if cmd["retcode"] != 0:
            log.warning("racadm return an exit code '%s'.", cmd["retcode"])

        for user in cmd["stdout"].splitlines():
            if not user.startswith("cfg"):
                continue

            (key, val) = user.split("=")

            if key.startswith("cfgUserAdminUserName"):
                _username = val.strip()

                if val:
                    users[_username] = {"index": idx}
                else:
                    break
            else:
                users[_username].update({key: val})

    return users


def delete_user(username, uid=None):
    """
    Delete a user

    CLI Example:

    .. code-block:: bash

        salt dell drac.delete_user [USERNAME] [UID - optional]
        salt dell drac.delete_user diana 4
    """
    if uid is None:
        user = list_users()
        uid = user[username]["index"]

    if uid:
        return __execute_cmd(
            f'config -g cfgUserAdmin -o cfgUserAdminUserName -i {uid} ""'
        )

    else:
        log.warning("'%s' does not exist", username)
        return False

    return True


def change_password(username, password, uid=None):
    """
    Change users password

    CLI Example:

    .. code-block:: bash

        salt dell drac.change_password [USERNAME] [PASSWORD] [UID - optional]
        salt dell drac.change_password diana secret
    """
    if uid is None:
        user = list_users()
        uid = user[username]["index"]

    if uid:
        return __execute_cmd(
            "config -g cfgUserAdmin -o cfgUserAdminPassword -i {} {}".format(
                uid, password
            )
        )
    else:
        log.warning("'%s' does not exist", username)
        return False

    return True


def create_user(username, password, permissions, users=None):
    """
    Create user accounts

    CLI Example:

    .. code-block:: bash

        salt dell drac.create_user [USERNAME] [PASSWORD] [PRIVILEGES]
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
    """
    _uids = set()

    if users is None:
        users = list_users()

    if username in users:
        log.warning("'%s' already exists", username)
        return False

    for idx in users.keys():
        _uids.add(users[idx]["index"])

    uid = sorted(list(set(range(2, 12)) - _uids), reverse=True).pop()

    # Create user accountvfirst
    if not __execute_cmd(
        f"config -g cfgUserAdmin -o cfgUserAdminUserName -i {uid} {username}"
    ):
        delete_user(username, uid)
        return False

    # Configure users permissions
    if not set_permissions(username, permissions, uid):
        log.warning("unable to set user permissions")
        delete_user(username, uid)
        return False

    # Configure users password
    if not change_password(username, password, uid):
        log.warning("unable to set user password")
        delete_user(username, uid)
        return False

    # Enable users admin
    if not __execute_cmd(f"config -g cfgUserAdmin -o cfgUserAdminEnable -i {uid} 1"):
        delete_user(username, uid)
        return False

    return True


def set_permissions(username, permissions, uid=None):
    """
    Configure users permissions

    CLI Example:

    .. code-block:: bash

        salt dell drac.set_permissions [USERNAME] [PRIVILEGES] [USER INDEX - optional]
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
    """
    privileges = {
        "login": "0x0000001",
        "drac": "0x0000002",
        "user_management": "0x0000004",
        "clear_logs": "0x0000008",
        "server_control_commands": "0x0000010",
        "console_redirection": "0x0000020",
        "virtual_media": "0x0000040",
        "test_alerts": "0x0000080",
        "debug_commands": "0x0000100",
    }

    permission = 0

    # When users don't provide a user ID we need to search for this
    if uid is None:
        user = list_users()
        uid = user[username]["index"]

    # Generate privilege bit mask
    for i in permissions.split(","):
        perm = i.strip()

        if perm in privileges:
            permission += int(privileges[perm], 16)

    return __execute_cmd(
        "config -g cfgUserAdmin -o cfgUserAdminPrivilege -i {} 0x{:08X}".format(
            uid, permission
        )
    )


def set_snmp(community):
    """
    Configure SNMP community string

    CLI Example:

    .. code-block:: bash

        salt dell drac.set_snmp [COMMUNITY]
        salt dell drac.set_snmp public
    """
    return __execute_cmd(
        f"config -g cfgOobSnmp -o cfgOobSnmpAgentCommunity {community}"
    )


def set_network(ip, netmask, gateway):
    """
    Configure Network

    CLI Example:

    .. code-block:: bash

        salt dell drac.set_network [DRAC IP] [NETMASK] [GATEWAY]
        salt dell drac.set_network 192.168.0.2 255.255.255.0 192.168.0.1
    """
    return __execute_cmd(f"setniccfg -s {ip} {netmask} {gateway}")


def server_reboot():
    """
    Issues a power-cycle operation on the managed server. This action is
    similar to pressing the power button on the system's front panel to
    power down and then power up the system.

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_reboot
    """
    return __execute_cmd("serveraction powercycle")


def server_poweroff():
    """
    Powers down the managed server.

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_poweroff
    """
    return __execute_cmd("serveraction powerdown")


def server_poweron():
    """
    Powers up the managed server.

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_poweron
    """
    return __execute_cmd("serveraction powerup")


def server_hardreset():
    """
    Performs a reset (reboot) operation on the managed server.

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_hardreset
    """
    return __execute_cmd("serveraction hardreset")


def server_pxe():
    """
    Configure server to PXE perform a one off PXE boot

    CLI Example:

    .. code-block:: bash

        salt dell drac.server_pxe
    """
    if __execute_cmd("config -g cfgServerInfo -o cfgServerFirstBootDevice PXE"):
        if __execute_cmd("config -g cfgServerInfo -o cfgServerBootOnce 1"):
            return server_reboot
        else:
            log.warning("failed to set boot order")
            return False

    log.warning("failed to configure PXE boot")
    return False
