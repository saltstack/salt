"""
A state module to manage Cisco UCS chassis devices.

:codeauthor: ``Spencer Ervin <spencer_ervin@hotmail.com>``
:maturity:   new
:depends:    none
:platform:   unix


About
=====
This state module was designed to handle connections to a Cisco Unified Computing System (UCS) chassis. This module
relies on the CIMC proxy module to interface with the device.

.. seealso::
    :py:mod:`CIMC Proxy Module <salt.proxy.cimc>`

"""


import logging

log = logging.getLogger(__name__)


def __virtual__():
    if "cimc.get_system_info" in __salt__:
        return True
    return (False, "cimc module could not be loaded")


def _default_ret(name):
    """
    Set the default response values.

    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    return ret


def hostname(name, hostname=None):
    """
    Ensures that the hostname is set to the specified value.

    .. versionadded:: 2019.2.0

    name: The name of the module function to execute.

    hostname(str): The hostname of the server.

    SLS Example:

    .. code-block:: yaml

        set_name:
          cimc.hostname:
            - hostname: foobar

    """

    ret = _default_ret(name)

    current_name = __salt__["cimc.get_hostname"]()

    req_change = False

    try:

        if current_name != hostname:
            req_change = True

        if req_change:

            update = __salt__["cimc.set_hostname"](hostname)

            if not update:
                ret["result"] = False
                ret["comment"] = "Error setting hostname."
                return ret

            ret["changes"]["before"] = current_name
            ret["changes"]["after"] = hostname
            ret["comment"] = "Hostname modified."
        else:
            ret["comment"] = "Hostname already configured. No changes required."

    except Exception as err:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = "Error occurred setting hostname."
        log.error(err)
        return ret

    ret["result"] = True

    return ret


def logging_levels(name, remote=None, local=None):
    """
    Ensures that the logging levels are set on the device. The logging levels
    must match the following options: emergency, alert, critical, error, warning,
    notice, informational, debug.

    .. versionadded:: 2019.2.0

    name: The name of the module function to execute.

    remote(str): The logging level for SYSLOG logs.

    local(str): The logging level for the local device.

    SLS Example:

    .. code-block:: yaml

        logging_levels:
          cimc.logging_levels:
            - remote: informational
            - local: notice

    """

    ret = _default_ret(name)

    syslog_conf = __salt__["cimc.get_syslog_settings"]()

    req_change = False

    try:
        syslog_dict = syslog_conf["outConfigs"]["commSyslog"][0]

        if remote and syslog_dict["remoteSeverity"] != remote:
            req_change = True
        elif local and syslog_dict["localSeverity"] != local:
            req_change = True

        if req_change:

            update = __salt__["cimc.set_logging_levels"](remote, local)

            if update["outConfig"]["commSyslog"][0]["status"] != "modified":
                ret["result"] = False
                ret["comment"] = "Error setting logging levels."
                return ret

            ret["changes"]["before"] = syslog_conf
            ret["changes"]["after"] = __salt__["cimc.get_syslog_settings"]()
            ret["comment"] = "Logging level settings modified."
        else:
            ret["comment"] = "Logging level already configured. No changes required."

    except Exception as err:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = "Error occurred setting logging level settings."
        log.error(err)
        return ret

    ret["result"] = True

    return ret


def ntp(name, servers):
    """
    Ensures that the NTP servers are configured. Servers are provided as an individual string or list format. Only four
    NTP servers will be reviewed. Any entries past four will be ignored.

    name: The name of the module function to execute.

    servers(str, list): The IP address or FQDN of the NTP servers.

    SLS Example:

    .. code-block:: yaml

        ntp_configuration_list:
          cimc.ntp:
            - servers:
              - foo.bar.com
              - 10.10.10.10

        ntp_configuration_str:
          cimc.ntp:
            - servers: foo.bar.com

    """
    ret = _default_ret(name)

    ntp_servers = ["", "", "", ""]

    # Parse our server arguments
    if isinstance(servers, list):
        i = 0
        for x in servers:
            ntp_servers[i] = x
            i += 1
    else:
        ntp_servers[0] = servers

    conf = __salt__["cimc.get_ntp"]()

    # Check if our NTP configuration is already set
    req_change = False
    try:
        if (
            conf["outConfigs"]["commNtpProvider"][0]["ntpEnable"] != "yes"
            or ntp_servers[0] != conf["outConfigs"]["commNtpProvider"][0]["ntpServer1"]
            or ntp_servers[1] != conf["outConfigs"]["commNtpProvider"][0]["ntpServer2"]
            or ntp_servers[2] != conf["outConfigs"]["commNtpProvider"][0]["ntpServer3"]
            or ntp_servers[3] != conf["outConfigs"]["commNtpProvider"][0]["ntpServer4"]
        ):
            req_change = True
    except KeyError as err:
        ret["result"] = False
        ret["comment"] = "Unable to confirm current NTP settings."
        log.error(err)
        return ret

    if req_change:

        try:
            update = __salt__["cimc.set_ntp_server"](
                ntp_servers[0], ntp_servers[1], ntp_servers[2], ntp_servers[3]
            )
            if update["outConfig"]["commNtpProvider"][0]["status"] != "modified":
                ret["result"] = False
                ret["comment"] = "Error setting NTP configuration."
                return ret
        except Exception as err:  # pylint: disable=broad-except
            ret["result"] = False
            ret["comment"] = "Error setting NTP configuration."
            log.error(err)
            return ret

        ret["changes"]["before"] = conf
        ret["changes"]["after"] = __salt__["cimc.get_ntp"]()
        ret["comment"] = "NTP settings modified."
    else:
        ret["comment"] = "NTP already configured. No changes required."

    ret["result"] = True

    return ret


def power_configuration(name, policy=None, delayType=None, delayValue=None):
    """
    Ensures that the power configuration is configured on the system. This is
    only available on some C-Series servers.

    .. versionadded:: 2019.2.0

    name: The name of the module function to execute.

    policy(str): The action to be taken when chassis power is restored after
    an unexpected power loss. This can be one of the following:

        reset: The server is allowed to boot up normally when power is
        restored. The server can restart immediately or, optionally, after a
        fixed or random delay.

        stay-off: The server remains off until it is manually restarted.

        last-state: The server restarts and the system attempts to restore
        any processes that were running before power was lost.

    delayType(str): If the selected policy is reset, the restart can be
    delayed with this option. This can be one of the following:

        fixed: The server restarts after a fixed delay.

        random: The server restarts after a random delay.

    delayValue(int): If a fixed delay is selected, once chassis power is
    restored and the Cisco IMC has finished rebooting, the system waits for
    the specified number of seconds before restarting the server. Enter an
    integer between 0 and 240.


    SLS Example:

    .. code-block:: yaml

        reset_power:
          cimc.power_configuration:
            - policy: reset
            - delayType: fixed
            - delayValue: 0

        power_off:
          cimc.power_configuration:
            - policy: stay-off


    """

    ret = _default_ret(name)

    power_conf = __salt__["cimc.get_power_configuration"]()

    req_change = False

    try:
        power_dict = power_conf["outConfigs"]["biosVfResumeOnACPowerLoss"][0]

        if policy and power_dict["vpResumeOnACPowerLoss"] != policy:
            req_change = True
        elif policy == "reset":
            if power_dict["delayType"] != delayType:
                req_change = True
            elif power_dict["delayType"] == "fixed":
                if str(power_dict["delay"]) != str(delayValue):
                    req_change = True
        else:
            ret["result"] = False
            ret["comment"] = "The power policy must be specified."
            return ret

        if req_change:

            update = __salt__["cimc.set_power_configuration"](
                policy, delayType, delayValue
            )

            if (
                update["outConfig"]["biosVfResumeOnACPowerLoss"][0]["status"]
                != "modified"
            ):
                ret["result"] = False
                ret["comment"] = "Error setting power configuration."
                return ret

            ret["changes"]["before"] = power_conf
            ret["changes"]["after"] = __salt__["cimc.get_power_configuration"]()
            ret["comment"] = "Power settings modified."
        else:
            ret["comment"] = "Power settings already configured. No changes required."

    except Exception as err:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = "Error occurred setting power settings."
        log.error(err)
        return ret

    ret["result"] = True

    return ret


def syslog(name, primary=None, secondary=None):
    """
    Ensures that the syslog servers are set to the specified values. A value of None will be ignored.

    name: The name of the module function to execute.

    primary(str): The IP address or FQDN of the primary syslog server.

    secondary(str): The IP address or FQDN of the secondary syslog server.

    SLS Example:

    .. code-block:: yaml

        syslog_configuration:
          cimc.syslog:
            - primary: 10.10.10.10
            - secondary: foo.bar.com

    """
    ret = _default_ret(name)

    conf = __salt__["cimc.get_syslog"]()

    req_change = False

    if primary:
        prim_change = True
        if "outConfigs" in conf and "commSyslogClient" in conf["outConfigs"]:
            for entry in conf["outConfigs"]["commSyslogClient"]:
                if entry["name"] != "primary":
                    continue
                if entry["adminState"] == "enabled" and entry["hostname"] == primary:
                    prim_change = False

        if prim_change:
            try:
                update = __salt__["cimc.set_syslog_server"](primary, "primary")
                if update["outConfig"]["commSyslogClient"][0]["status"] == "modified":
                    req_change = True
                else:
                    ret["result"] = False
                    ret["comment"] = "Error setting primary SYSLOG server."
                    return ret
            except Exception as err:  # pylint: disable=broad-except
                ret["result"] = False
                ret["comment"] = "Error setting primary SYSLOG server."
                log.error(err)
                return ret

    if secondary:
        sec_change = True
        if "outConfig" in conf and "commSyslogClient" in conf["outConfig"]:
            for entry in conf["outConfig"]["commSyslogClient"]:
                if entry["name"] != "secondary":
                    continue
                if entry["adminState"] == "enabled" and entry["hostname"] == secondary:
                    sec_change = False

        if sec_change:
            try:
                update = __salt__["cimc.set_syslog_server"](secondary, "secondary")
                if update["outConfig"]["commSyslogClient"][0]["status"] == "modified":
                    req_change = True
                else:
                    ret["result"] = False
                    ret["comment"] = "Error setting secondary SYSLOG server."
                    return ret
            except Exception as err:  # pylint: disable=broad-except
                ret["result"] = False
                ret["comment"] = "Error setting secondary SYSLOG server."
                log.error(err)
                return ret

    if req_change:
        ret["changes"]["before"] = conf
        ret["changes"]["after"] = __salt__["cimc.get_syslog"]()
        ret["comment"] = "SYSLOG settings modified."
    else:
        ret["comment"] = "SYSLOG already configured. No changes required."

    ret["result"] = True

    return ret


def user(name, id="", user="", priv="", password="", status="active"):
    """
    Ensures that a user is configured on the device. Due to being unable to
    verify the user password. This is a forced operation.

    .. versionadded:: 2019.2.0

    name: The name of the module function to execute.

    id(int): The user ID slot on the device.

    user(str): The username of the user.

    priv(str): The privilege level of the user.

    password(str): The password of the user.

    status(str): The status of the user. Can be either active or inactive.

    SLS Example:

    .. code-block:: yaml

        user_configuration:
          cimc.user:
            - id: 11
            - user: foo
            - priv: admin
            - password: mypassword
            - status: active

    """

    ret = _default_ret(name)

    user_conf = __salt__["cimc.get_users"]()

    try:
        for entry in user_conf["outConfigs"]["aaaUser"]:
            if entry["id"] == str(id):
                conf = entry

        if not conf:
            ret["result"] = False
            ret[
                "comment"
            ] = "Unable to find requested user id on device. Please verify id is valid."
            return ret

        updates = __salt__["cimc.set_user"](str(id), user, password, priv, status)

        if "outConfig" in updates:
            ret["changes"]["before"] = conf
            ret["changes"]["after"] = updates["outConfig"]["aaaUser"]
            ret["comment"] = "User settings modified."
        else:
            ret["result"] = False
            ret["comment"] = "Error setting user configuration."
            return ret

    except Exception as err:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = "Error setting user configuration."
        log.error(err)
        return ret

    ret["result"] = True

    return ret
