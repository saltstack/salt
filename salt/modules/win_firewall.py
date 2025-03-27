"""
Module for configuring Windows Firewall using ``netsh``
"""

import re

import salt.utils.platform
import salt.utils.win_lgpo_netsh
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = "firewall"


def __virtual__():
    """
    Only works on Windows systems
    """
    if not salt.utils.platform.is_windows():
        return False, "Module win_firewall: module only available on Windows"

    return __virtualname__


def get_config():
    """
    Get the status of all the firewall profiles

    Returns:
        dict: A dictionary of all profiles on the system

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.get_config
    """
    profiles = {}
    curr = None

    cmd = ["netsh", "advfirewall", "show", "allprofiles"]
    ret = __salt__["cmd.run_all"](cmd, python_shell=False, ignore_retcode=True)
    if ret["retcode"] != 0:
        raise CommandExecutionError(ret["stdout"])

    # There may be some problems with this depending on how `netsh` is localized
    # It's looking for lines that contain `Profile Settings` or start with
    # `State` which may be different in different localizations
    for line in ret["stdout"].splitlines():
        if not curr:
            tmp = re.search("(.*) Profile Settings:", line)
            if tmp:
                curr = tmp.group(1)
        elif line.startswith("State"):
            profiles[curr] = line.split()[1] == "ON"
            curr = None

    return profiles


def disable(profile="allprofiles"):
    """
    Disable firewall profile

    Args:
        profile (Optional[str]): The name of the profile to disable. Default is
            ``allprofiles``. Valid options are:

            - allprofiles
            - domainprofile
            - privateprofile
            - publicprofile

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.disable
    """
    cmd = ["netsh", "advfirewall", "set", profile, "state", "off"]
    ret = __salt__["cmd.run_all"](cmd, python_shell=False, ignore_retcode=True)
    if ret["retcode"] != 0:
        raise CommandExecutionError(ret["stdout"])

    return True


def enable(profile="allprofiles"):
    """
    .. versionadded:: 2015.5.0

    Enable firewall profile

    Args:
        profile (Optional[str]): The name of the profile to enable. Default is
            ``allprofiles``. Valid options are:

            - allprofiles
            - domainprofile
            - privateprofile
            - publicprofile

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.enable
    """
    cmd = ["netsh", "advfirewall", "set", profile, "state", "on"]
    ret = __salt__["cmd.run_all"](cmd, python_shell=False, ignore_retcode=True)
    if ret["retcode"] != 0:
        raise CommandExecutionError(ret["stdout"])

    return True


def get_rule(name="all"):
    """
    .. versionadded:: 2015.5.0

    Display all matching rules as specified by name

    Args:
        name (Optional[str]): The full name of the rule. ``all`` will return all
            rules. Default is ``all``

    Returns:
        dict: A dictionary of all rules or rules that match the name exactly

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.get_rule 'MyAppPort'
    """
    cmd = ["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"]
    ret = __salt__["cmd.run_all"](cmd, python_shell=False, ignore_retcode=True)
    if ret["retcode"] != 0:
        raise CommandExecutionError(ret["stdout"])

    return {name: ret["stdout"]}


def add_rule(name, localport, protocol="tcp", action="allow", dir="in", remoteip="any"):
    """
    .. versionadded:: 2015.5.0

    Add a new inbound or outbound rule to the firewall policy

    Args:

        name (str): The name of the rule. Must be unique and cannot be "all".
            Required.

        localport (int): The port the rule applies to. Must be a number between
            0 and 65535. Can be a range. Can specify multiple ports separated by
            commas. Required.

        protocol (Optional[str]): The protocol. Can be any of the following:

            - A number between 0 and 255
            - icmpv4
            - icmpv6
            - tcp
            - udp
            - any

        action (Optional[str]): The action the rule performs. Can be any of the
            following:

            - allow
            - block
            - bypass

        dir (Optional[str]): The direction. Can be ``in`` or ``out``.

        remoteip (Optional [str]): The remote IP. Can be any of the following:

            - any
            - localsubnet
            - dns
            - dhcp
            - wins
            - defaultgateway
            - Any valid IPv4 address (192.168.0.12)
            - Any valid IPv6 address (2002:9b3b:1a31:4:208:74ff:fe39:6c43)
            - Any valid subnet (192.168.1.0/24)
            - Any valid range of IP addresses (192.168.0.1-192.168.0.12)
            - A list of valid IP addresses

            Can be combinations of the above separated by commas.

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.add_rule 'test' '8080' 'tcp'
        salt '*' firewall.add_rule 'test' '1' 'icmpv4'
        salt '*' firewall.add_rule 'test_remote_ip' '8000' 'tcp' 'allow' 'in' '192.168.0.1'
    """
    cmd = [
        "netsh",
        "advfirewall",
        "firewall",
        "add",
        "rule",
        f"name={name}",
        f"protocol={protocol}",
        f"dir={dir}",
        f"action={action}",
        f"remoteip={remoteip}",
    ]

    if protocol is None or ("icmpv4" not in protocol and "icmpv6" not in protocol):
        cmd.append(f"localport={localport}")

    ret = __salt__["cmd.run_all"](cmd, python_shell=False, ignore_retcode=True)
    if ret["retcode"] != 0:
        raise CommandExecutionError(ret["stdout"])

    return True


def delete_rule(name=None, localport=None, protocol=None, dir=None, remoteip=None):
    """
    .. versionadded:: 2015.8.0

    Delete an existing firewall rule identified by name and optionally by ports,
    protocols, direction, and remote IP.

    Args:

        name (str): The name of the rule to delete. If the name ``all`` is used
            you must specify additional parameters.

        localport (Optional[str]): The port of the rule. If protocol is not
            specified, protocol will be set to ``tcp``

        protocol (Optional[str]): The protocol of the rule. Default is ``tcp``
            when ``localport`` is specified

        dir (Optional[str]): The direction of the rule.

        remoteip (Optional[str]): The remote IP of the rule.

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        # Delete incoming tcp port 8080 in the rule named 'test'
        salt '*' firewall.delete_rule 'test' '8080' 'tcp' 'in'

        # Delete the incoming tcp port 8000 from 192.168.0.1 in the rule named
        # 'test_remote_ip'
        salt '*' firewall.delete_rule 'test_remote_ip' '8000' 'tcp' 'in' '192.168.0.1'

        # Delete all rules for local port 80:
        salt '*' firewall.delete_rule all 80 tcp

        # Delete a rule called 'allow80':
        salt '*' firewall.delete_rule allow80
    """
    cmd = ["netsh", "advfirewall", "firewall", "delete", "rule"]
    if name:
        cmd.append(f"name={name}")
    if protocol:
        cmd.append(f"protocol={protocol}")
    if dir:
        cmd.append(f"dir={dir}")
    if remoteip:
        cmd.append(f"remoteip={remoteip}")

    if protocol is None or ("icmpv4" not in protocol and "icmpv6" not in protocol):
        if localport:
            if not protocol:
                cmd.append("protocol=tcp")
            cmd.append(f"localport={localport}")

    ret = __salt__["cmd.run_all"](cmd, python_shell=False, ignore_retcode=True)
    if ret["retcode"] != 0:
        raise CommandExecutionError(ret["stdout"])

    return True


def rule_exists(name):
    """
    .. versionadded:: 2016.11.6

    Checks if a firewall rule exists in the firewall policy

    Args:
        name (str): The name of the rule

    Returns:
        bool: True if exists, otherwise False

    CLI Example:

    .. code-block:: bash

        # Is there a rule named RemoteDesktop
        salt '*' firewall.rule_exists RemoteDesktop
    """
    try:
        get_rule(name)
        return True
    except CommandExecutionError:
        return False


def get_settings(profile, section, store="local"):
    """
    Get the firewall property from the specified profile in the specified store
    as returned by ``netsh advfirewall``.

    .. versionadded:: 2018.3.4
    .. versionadded:: 2019.2.0

    Args:

        profile (str):
            The firewall profile to query. Valid options are:

            - domain
            - public
            - private

        section (str):
            The property to query within the selected profile. Valid options
            are:

            - firewallpolicy : inbound/outbound behavior
            - logging : firewall logging settings
            - settings : firewall properties
            - state : firewalls state (on | off)

        store (str):
            The store to use. This is either the local firewall policy or the
            policy defined by local group policy. Valid options are:

            - lgpo
            - local

            Default is ``local``

    Returns:
        dict: A dictionary containing the properties for the specified profile

    Raises:
        CommandExecutionError: If an error occurs
        ValueError: If the parameters are incorrect

    CLI Example:

    .. code-block:: bash

        # Get the inbound/outbound firewall settings for connections on the
        # local domain profile
        salt * win_firewall.get_settings domain firewallpolicy

        # Get the inbound/outbound firewall settings for connections on the
        # domain profile as defined by local group policy
        salt * win_firewall.get_settings domain firewallpolicy lgpo
    """
    return salt.utils.win_lgpo_netsh.get_settings(
        profile=profile, section=section, store=store
    )


def get_all_settings(domain, store="local"):
    """
    Gets all the properties for the specified profile in the specified store

    .. versionadded:: 2018.3.4
    .. versionadded:: 2019.2.0

    Args:

        profile (str):
            The firewall profile to query. Valid options are:

            - domain
            - public
            - private

        store (str):
            The store to use. This is either the local firewall policy or the
            policy defined by local group policy. Valid options are:

            - lgpo
            - local

            Default is ``local``

    Returns:
        dict: A dictionary containing the specified settings

    CLI Example:

    .. code-block:: bash

        # Get all firewall settings for connections on the domain profile
        salt * win_firewall.get_all_settings domain

        # Get all firewall settings for connections on the domain profile as
        # defined by local group policy
        salt * win_firewall.get_all_settings domain lgpo
    """
    return salt.utils.win_lgpo_netsh.get_all_settings(profile=domain, store=store)


def get_all_profiles(store="local"):
    """
    Gets all properties for all profiles in the specified store

    .. versionadded:: 2018.3.4
    .. versionadded:: 2019.2.0

    Args:

        store (str):
            The store to use. This is either the local firewall policy or the
            policy defined by local group policy. Valid options are:

            - lgpo
            - local

            Default is ``local``

    Returns:
        dict: A dictionary containing the specified settings for each profile

    CLI Example:

    .. code-block:: bash

        # Get all firewall settings for all profiles
        salt * firewall.get_all_settings

        # Get all firewall settings for all profiles as defined by local group
        # policy

        salt * firewall.get_all_settings lgpo
    """
    return salt.utils.win_lgpo_netsh.get_all_profiles(store=store)


def set_firewall_settings(profile, inbound=None, outbound=None, store="local"):
    """
    Set the firewall inbound/outbound settings for the specified profile and
    store

    .. versionadded:: 2018.3.4
    .. versionadded:: 2019.2.0

    Args:

        profile (str):
            The firewall profile to query. Valid options are:

            - domain
            - public
            - private

        inbound (str):
            The inbound setting. If ``None`` is passed, the setting will remain
            unchanged. Valid values are:

            - blockinbound
            - blockinboundalways
            - allowinbound
            - notconfigured

            Default is ``None``

        outbound (str):
            The outbound setting. If ``None`` is passed, the setting will remain
            unchanged. Valid values are:

            - allowoutbound
            - blockoutbound
            - notconfigured

            Default is ``None``

        store (str):
            The store to use. This is either the local firewall policy or the
            policy defined by local group policy. Valid options are:

            - lgpo
            - local

            Default is ``local``

    Returns:
        bool: ``True`` if successful

    Raises:
        CommandExecutionError: If an error occurs
        ValueError: If the parameters are incorrect

    CLI Example:

    .. code-block:: bash

        # Set the inbound setting for the domain profile to block inbound
        # connections
        salt * firewall.set_firewall_settings domain='domain' inbound='blockinbound'

        # Set the outbound setting for the domain profile to allow outbound
        # connections
        salt * firewall.set_firewall_settings domain='domain' outbound='allowoutbound'

        # Set inbound/outbound settings for the domain profile in the group
        # policy to block inbound and allow outbound
        salt * firewall.set_firewall_settings domain='domain' inbound='blockinbound' outbound='allowoutbound' store='lgpo'
    """
    return salt.utils.win_lgpo_netsh.set_firewall_settings(
        profile=profile, inbound=inbound, outbound=outbound, store=store
    )


def set_logging_settings(profile, setting, value, store="local"):
    r"""
    Configure logging settings for the Windows firewall.

    .. versionadded:: 2018.3.4
    .. versionadded:: 2019.2.0

    Args:

        profile (str):
            The firewall profile to configure. Valid options are:

            - domain
            - public
            - private

        setting (str):
            The logging setting to configure. Valid options are:

            - allowedconnections
            - droppedconnections
            - filename
            - maxfilesize

        value (str):
            The value to apply to the setting. Valid values are dependent upon
            the setting being configured. Valid options are:

            allowedconnections:

                - enable
                - disable
                - notconfigured

            droppedconnections:

                - enable
                - disable
                - notconfigured

            filename:

                - Full path and name of the firewall log file
                - notconfigured

            maxfilesize:

                - 1 - 32767
                - notconfigured

            .. note::
                ``notconfigured`` can only be used when using the lgpo store

        store (str):
            The store to use. This is either the local firewall policy or the
            policy defined by local group policy. Valid options are:

            - lgpo
            - local

            Default is ``local``

    Returns:
        bool: ``True`` if successful

    Raises:
        CommandExecutionError: If an error occurs
        ValueError: If the parameters are incorrect

    CLI Example:

    .. code-block:: bash

        # Log allowed connections and set that in local group policy
        salt * firewall.set_logging_settings domain allowedconnections enable lgpo

        # Don't log dropped connections
        salt * firewall.set_logging_settings profile=private setting=droppedconnections value=disable

        # Set the location of the log file
        salt * firewall.set_logging_settings domain filename C:\windows\logs\firewall.log

        # You can also use environment variables
        salt * firewall.set_logging_settings domain filename %systemroot%\system32\LogFiles\Firewall\pfirewall.log

        # Set the max file size of the log to 2048 Kb
        salt * firewall.set_logging_settings domain maxfilesize 2048
    """
    return salt.utils.win_lgpo_netsh.set_logging_settings(
        profile=profile, setting=setting, value=value, store=store
    )


def set_settings(profile, setting, value, store="local"):
    """
    Configure firewall settings.

    .. versionadded:: 2018.3.4
    .. versionadded:: 2019.2.0

    Args:

        profile (str):
            The firewall profile to configure. Valid options are:

            - domain
            - public
            - private

        setting (str):
            The firewall setting to configure. Valid options are:

            - localfirewallrules
            - localconsecrules
            - inboundusernotification
            - remotemanagement
            - unicastresponsetomulticast

        value (str):
            The value to apply to the setting. Valid options are

            - enable
            - disable
            - notconfigured

            .. note::
                ``notconfigured`` can only be used when using the lgpo store

        store (str):
            The store to use. This is either the local firewall policy or the
            policy defined by local group policy. Valid options are:

            - lgpo
            - local

            Default is ``local``

    Returns:
        bool: ``True`` if successful

    Raises:
        CommandExecutionError: If an error occurs
        ValueError: If the parameters are incorrect

    CLI Example:

    .. code-block:: bash

        # Merge local rules with those distributed through group policy
        salt * firewall.set_settings domain localfirewallrules enable

        # Allow remote management of Windows Firewall
        salt * firewall.set_settings domain remotemanagement enable
    """
    return salt.utils.win_lgpo_netsh.set_settings(
        profile=profile, setting=setting, value=value, store=store
    )


def set_state(profile, state, store="local"):
    """
    Configure the firewall state.

    .. versionadded:: 2018.3.4
    .. versionadded:: 2019.2.0

    Args:

        profile (str):
            The firewall profile to configure. Valid options are:

            - domain
            - public
            - private

        state (str):
            The firewall state. Valid options are:

            - on
            - off
            - notconfigured

            .. note::
                ``notconfigured`` can only be used when using the lgpo store

        store (str):
            The store to use. This is either the local firewall policy or the
            policy defined by local group policy. Valid options are:

            - lgpo
            - local

            Default is ``local``

    Returns:
        bool: ``True`` if successful

    Raises:
        CommandExecutionError: If an error occurs
        ValueError: If the parameters are incorrect

    CLI Example:

    .. code-block:: bash

        # Turn the firewall off when the domain profile is active
        salt * firewall.set_state domain off

        # Turn the firewall on when the public profile is active and set that in
        # the local group policy
        salt * firewall.set_state public on lgpo
    """
    return salt.utils.win_lgpo_netsh.set_state(
        profile=profile, state=state, store=store
    )
