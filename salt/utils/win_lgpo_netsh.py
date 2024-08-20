r"""
A salt util for modifying firewall settings.

.. versionadded:: 2018.3.4
.. versionadded:: 2019.2.0

This util allows you to modify firewall settings in the local group policy in
addition to the normal firewall settings. Parameters are taken from the
netsh advfirewall prompt. This utility has been adapted to use powershell
instead of the ``netsh`` command to make it compatible with non-English systems.
It maintains the ``netsh`` commands and parameters, but it is using powershell
under the hood.

.. versionchanged:: 3008.0

.. note::
    More information can be found in the advfirewall context in netsh. This can
    be accessed by opening a netsh prompt. At a command prompt type the
    following:

    .. code-block:: powershell

        c:\>netsh
        netsh>advfirewall
        netsh advfirewall>set help
        netsh advfirewall>set domain help

Usage:

.. code-block:: python

    import salt.utils.win_lgpo_netsh

    # Get the inbound/outbound firewall settings for connections on the
    # local domain profile
    salt.utils.win_lgpo_netsh.get_settings(profile='domain',
                                           section='firewallpolicy')

    # Get the inbound/outbound firewall settings for connections on the
    # domain profile as defined by local group policy
    salt.utils.win_lgpo_netsh.get_settings(profile='domain',
                                           section='firewallpolicy',
                                           store='lgpo')

    # Get all firewall settings for connections on the domain profile
    salt.utils.win_lgpo_netsh.get_all_settings(profile='domain')

    # Get all firewall settings for connections on the domain profile as
    # defined by local group policy
    salt.utils.win_lgpo_netsh.get_all_settings(profile='domain', store='lgpo')

    # Get all firewall settings for all profiles
    salt.utils.win_lgpo_netsh.get_all_settings()

    # Get all firewall settings for all profiles as defined by local group
    # policy
    salt.utils.win_lgpo_netsh.get_all_settings(store='lgpo')

    # Set the inbound setting for the domain profile to block inbound
    # connections
    salt.utils.win_lgpo_netsh.set_firewall_settings(profile='domain',
                                                    inbound='blockinbound')

    # Set the outbound setting for the domain profile to allow outbound
    # connections
    salt.utils.win_lgpo_netsh.set_firewall_settings(profile='domain',
                                                    outbound='allowoutbound')

    # Set inbound/outbound settings for the domain profile in the group
    # policy to block inbound and allow outbound
    salt.utils.win_lgpo_netsh.set_firewall_settings(profile='domain',
                                                    inbound='blockinbound',
                                                    outbound='allowoutbound',
                                                    store='lgpo')
"""

import salt.utils.platform
import salt.utils.win_pwsh
from salt.exceptions import CommandExecutionError

ON_OFF = {
    0: "OFF",
    1: "ON",
    2: "NotConfigured",
    "off": "False",
    "on": "True",
    "notconfigured": "NotConfigured",
}

ENABLE_DISABLE = {
    0: "Disable",
    1: "Enable",
    2: "NotConfigured",
    "disable": 0,
    "enable": 1,
    "notconfigured": 2,
}
OUTBOUND = {
    0: "NotConfigured",
    2: "AllowOutbound",
    4: "BlockOutbound",
    "notconfigured": "NotConfigured",
    "allowoutbound": "Allow",
    "blockoutbound": "Block",
}


def _get_inbound_text(rule, action):
    """
    The "Inbound connections" setting is a combination of 2 parameters:

    - AllowInboundRules
    - DefaultInboundAction

    The settings are as follows:

    Rules Action
    2     2       AllowInbound
    2     4       BlockInbound
    0     4       BlockInboundAlways
    2     0       NotConfigured
    """
    settings = {
        0: {
            4: "BlockInboundAlways",
        },
        2: {
            0: "NotConfigured",
            2: "AllowInbound",
            4: "BlockInbound",
        },
    }
    return settings[rule][action]


def _get_inbound_settings(text):
    settings = {
        "allowinbound": (2, 2),
        "blockinbound": (2, 4),
        "blockinboundalways": (0, 4),
        "notconfigured": (2, 0),
    }
    return settings[text.lower()]


def get_settings(profile, section, store="local"):
    """
    Get the firewall property from the specified profile in the specified store
    as returned by ``netsh advfirewall``.

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
    """
    # validate input
    if profile.lower() not in ("domain", "public", "private"):
        raise ValueError(f"Incorrect profile: {profile}")
    if section.lower() not in ("state", "firewallpolicy", "settings", "logging"):
        raise ValueError(f"Incorrect section: {section}")
    if store.lower() not in ("local", "lgpo"):
        raise ValueError(f"Incorrect store: {store}")

    # Build the powershell command
    cmd = ["Get-NetFirewallProfile"]
    if profile:
        cmd.append(profile)
    if store and store.lower() == "lgpo":
        cmd.extend(["-PolicyStore", "localhost"])

    # Run the command
    settings = salt.utils.win_pwsh.run_dict(cmd)

    # A successful run should return a dictionary
    if not settings:
        raise CommandExecutionError("LGPO NETSH: An unknown error occurred")

    # Remove the junk
    for setting in list(settings.keys()):
        if setting.startswith("Cim"):
            settings.pop(setting)

    # Make it look like netsh output
    ret_settings = {
        "firewallpolicy": {
            "Inbound": _get_inbound_text(
                settings["AllowInboundRules"], settings["DefaultInboundAction"]
            ),
            "Outbound": OUTBOUND[settings["DefaultOutboundAction"]],
        },
        "state": {
            "State": ON_OFF[settings["Enabled"]],
        },
        "logging": {
            "FileName": settings["LogFileName"],
            "LogAllowedConnections": ENABLE_DISABLE[settings["LogAllowed"]],
            "LogDroppedConnections": ENABLE_DISABLE[settings["LogBlocked"]],
            "MaxFileSize": settings["LogMaxSizeKilobytes"],
        },
        "settings": {
            "InboundUserNotification": ENABLE_DISABLE[settings["NotifyOnListen"]],
            "LocalConSecRules": ENABLE_DISABLE[settings["AllowLocalIPsecRules"]],
            "LocalFirewallRules": ENABLE_DISABLE[settings["AllowLocalFirewallRules"]],
            "UnicastResponseToMulticast": ENABLE_DISABLE[
                settings["AllowUnicastResponseToMulticast"]
            ],
        },
    }

    return ret_settings[section.lower()]


def get_all_profiles(store="local"):
    """
    Gets all properties for all profiles in the specified store

    Args:

        store (str):
            The store to use. This is either the local firewall policy or the
            policy defined by local group policy. Valid options are:

            - lgpo
            - local

            Default is ``local``

    Returns:
        dict: A dictionary containing the specified settings for each profile
    """
    return {
        "Domain Profile": get_all_settings(profile="domain", store=store),
        "Private Profile": get_all_settings(profile="private", store=store),
        "Public Profile": get_all_settings(profile="public", store=store),
    }


def get_all_settings(profile, store="local"):
    """
    Gets all the properties for the specified profile in the specified store

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

    Raises:
        CommandExecutionError: If an error occurs
        ValueError: If the parameters are incorrect
    """
    # validate input
    if profile.lower() not in ("domain", "public", "private"):
        raise ValueError(f"Incorrect profile: {profile}")
    if store.lower() not in ("local", "lgpo"):
        raise ValueError(f"Incorrect store: {store}")

    # Build the powershell command
    cmd = ["Get-NetFirewallProfile"]
    if profile:
        cmd.append(profile)
    if store and store.lower() == "lgpo":
        cmd.extend(["-PolicyStore", "localhost"])

    # Run the command
    settings = salt.utils.win_pwsh.run_dict(cmd)

    # A successful run should return a dictionary
    if not settings:
        raise CommandExecutionError("LGPO NETSH: An unknown error occurred")

    # Remove the junk
    for setting in list(settings.keys()):
        if setting.startswith("Cim"):
            settings.pop(setting)

    # Make it look like netsh output
    ret_settings = {
        "FileName": settings["LogFileName"],
        "Inbound": _get_inbound_text(
            settings["AllowInboundRules"], settings["DefaultInboundAction"]
        ),
        "InboundUserNotification": ENABLE_DISABLE[settings["NotifyOnListen"]],
        "LocalConSecRules": ENABLE_DISABLE[settings["AllowLocalIPsecRules"]],
        "LocalFirewallRules": ENABLE_DISABLE[settings["AllowLocalFirewallRules"]],
        "LogAllowedConnections": ENABLE_DISABLE[settings["LogAllowed"]],
        "LogDroppedConnections": ENABLE_DISABLE[settings["LogBlocked"]],
        "MaxFileSize": settings["LogMaxSizeKilobytes"],
        "Outbound": OUTBOUND[settings["DefaultOutboundAction"]],
        "State": ON_OFF[settings["Enabled"]],
        "UnicastResponseToMulticast": ON_OFF[
            settings["AllowUnicastResponseToMulticast"]
        ],
    }

    return ret_settings


def set_firewall_settings(profile, inbound=None, outbound=None, store="local"):
    """
    Set the firewall inbound/outbound settings for the specified profile and
    store

    Args:

        profile (str):
            The firewall profile to configure. Valid options are:

            - domain
            - public
            - private

        inbound (str):
            The inbound setting. If ``None`` is passed, the setting will remain
            unchanged. Valid values are:

            - blockinbound
            - blockinboundalways
            - allowinbound
            - notconfigured  <=== lgpo only

            Default is ``None``

        outbound (str):
            The outbound setting. If ``None`` is passed, the setting will remain
            unchanged. Valid values are:

            - allowoutbound
            - blockoutbound
            - notconfigured  <=== lgpo only

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
    """
    # Input validation
    if profile.lower() not in ("domain", "public", "private"):
        raise ValueError(f"Incorrect profile: {profile}")
    if inbound and inbound.lower() not in (
        "blockinbound",
        "blockinboundalways",
        "allowinbound",
        "notconfigured",
    ):
        raise ValueError(f"Incorrect inbound value: {inbound}")
    if outbound and outbound.lower() not in (
        "allowoutbound",
        "blockoutbound",
        "notconfigured",
    ):
        raise ValueError(f"Incorrect outbound value: {outbound}")
    if not inbound and not outbound:
        raise ValueError("Must set inbound or outbound")
    if store == "local":
        if inbound and inbound.lower() == "notconfigured":
            msg = "Cannot set local inbound policies as NotConfigured"
            raise CommandExecutionError(msg)
        if outbound and outbound.lower() == "notconfigured":
            msg = "Cannot set local outbound policies as NotConfigured"
            raise CommandExecutionError(msg)

    # Build the powershell command
    cmd = ["Set-NetFirewallProfile"]
    if profile:
        cmd.append(profile)
    if store and store.lower() == "lgpo":
        cmd.extend(["-PolicyStore", "localhost"])

    # Get inbound settings
    if inbound:
        in_rule, in_action = _get_inbound_settings(inbound.lower())
        cmd.extend(["-AllowInboundRules", in_rule, "-DefaultInboundAction", in_action])

    if outbound:
        out_rule = OUTBOUND[outbound.lower()]
        cmd.extend(["-DefaultOutboundAction", out_rule])

    # Run the command
    results = salt.utils.win_pwsh.run_dict(cmd)

    # A successful run should return an empty list
    if results:
        raise CommandExecutionError(f"An error occurred: {results}")

    return True


def set_logging_settings(profile, setting, value, store="local"):
    """
    Configure logging settings for the Windows firewall.

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

                - 1 - 32767 (Kb)
                - notconfigured

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
    """
    # Input validation
    if profile.lower() not in ("domain", "public", "private"):
        raise ValueError(f"Incorrect profile: {profile}")
    if store == "local":
        if str(value).lower() == "notconfigured":
            msg = "Cannot set local policies as NotConfigured"
            raise CommandExecutionError(msg)
    if setting.lower() not in (
        "allowedconnections",
        "droppedconnections",
        "filename",
        "maxfilesize",
    ):
        raise ValueError(f"Incorrect setting: {setting}")
    settings = {"filename": ["-LogFileName", value]}
    if setting.lower() in ("allowedconnections", "droppedconnections"):
        if value.lower() not in ("enable", "disable", "notconfigured"):
            raise ValueError(f"Incorrect value: {value}")
        settings.update(
            {
                "allowedconnections": ["-LogAllowed", ENABLE_DISABLE[value.lower()]],
                "droppedconnections": ["-LogBlocked", ENABLE_DISABLE[value.lower()]],
            }
        )

    # TODO: Consider adding something like the following to validate filename
    # https://stackoverflow.com/questions/9532499/check-whether-a-path-is-valid-in-python-without-creating-a-file-at-the-paths-ta
    if setting.lower() == "maxfilesize":
        if str(value).lower() != "notconfigured":
            # Must be a number between 1 and 32767
            try:
                int(value)
            except ValueError:
                raise ValueError(f"Incorrect value: {value}")
            if not 1 <= int(value) <= 32767:
                raise ValueError(f"Incorrect value: {value}")
        settings.update({"maxfilesize": ["-LogMaxSizeKilobytes", value]})

    # Build the powershell command
    cmd = ["Set-NetFirewallProfile"]
    if profile:
        cmd.append(profile)
    if store and store.lower() == "lgpo":
        cmd.extend(["-PolicyStore", "localhost"])

    cmd.extend(settings[setting.lower()])

    results = salt.utils.win_pwsh.run_dict(cmd)

    # A successful run should return an empty list
    if results:
        raise CommandExecutionError(f"An error occurred: {results}")

    return True


def set_settings(profile, setting, value, store="local"):
    """
    Configure firewall settings.

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
            - unicastresponsetomulticast

        value (str):
            The value to apply to the setting. Valid options are

            - enable
            - disable
            - notconfigured

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
    """
    # Input validation
    if profile.lower() not in ("domain", "public", "private"):
        raise ValueError(f"Incorrect profile: {profile}")
    if setting.lower() not in (
        "localfirewallrules",
        "localconsecrules",
        "inboundusernotification",
        "unicastresponsetomulticast",
    ):
        raise ValueError(f"Incorrect setting: {setting}")
    if value.lower() not in ("enable", "disable", "notconfigured"):
        raise ValueError(f"Incorrect value: {value}")
    if setting.lower() in ["localfirewallrules", "localconsecrules"]:
        if store.lower() != "lgpo":
            msg = f"{setting} can only be set using Group Policy"
            raise CommandExecutionError(msg)
    if setting.lower() == "inboundusernotification" and store.lower() != "lgpo":
        if value.lower() == "notconfigured":
            msg = "NotConfigured is only valid when setting group policy"
            raise CommandExecutionError(msg)

    # Build the powershell command
    cmd = ["Set-NetFirewallProfile"]
    if profile:
        cmd.append(profile)
    if store and store.lower() == "lgpo":
        cmd.extend(["-PolicyStore", "localhost"])

    settings = {
        "localfirewallrules": [
            "-AllowLocalFirewallRules",
            ENABLE_DISABLE[value.lower()],
        ],
        "localconsecrules": ["-AllowLocalIPsecRules", ENABLE_DISABLE[value.lower()]],
        "inboundusernotification": ["-NotifyOnListen", ENABLE_DISABLE[value.lower()]],
        "unicastresponsetomulticast": [
            "-AllowUnicastResponseToMulticast",
            ENABLE_DISABLE[value.lower()],
        ],
    }
    cmd.extend(settings[setting.lower()])

    results = salt.utils.win_pwsh.run_dict(cmd)

    # A successful run should return an empty list
    if results:
        raise CommandExecutionError(f"An error occurred: {results}")

    return True


def set_state(profile, state, store="local"):
    """
    Enable or disable the firewall profile.

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
    """
    # Input validation
    if profile.lower() not in ("domain", "public", "private"):
        raise ValueError(f"Incorrect profile: {profile}")
    if not isinstance(state, bool):
        if state.lower() not in ("on", "off", "notconfigured"):
            raise ValueError(f"Incorrect state: {state}")
    else:
        state = "On" if state else "Off"

    # Build the powershell command
    cmd = ["Set-NetFirewallProfile"]
    if profile:
        cmd.append(profile)
    if store and store.lower() == "lgpo":
        cmd.extend(["-PolicyStore", "localhost"])

    cmd.extend(["-Enabled", ON_OFF[state.lower()]])

    results = salt.utils.win_pwsh.run_dict(cmd)

    # A successful run should return an empty list
    if results:
        raise CommandExecutionError(f"An error occurred: {results}")

    return True
