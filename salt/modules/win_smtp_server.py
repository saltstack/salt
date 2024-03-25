"""
Module for managing IIS SMTP server configuration on Windows servers.
The Windows features 'SMTP-Server' and 'Web-WMI' must be installed.

:depends: wmi

"""

# IIS metabase configuration settings:
#   https://goo.gl/XCt1uO
# IIS logging options:
#   https://goo.gl/RL8ki9
#   https://goo.gl/iwnDow
# MicrosoftIISv2 namespace in Windows 2008r2 and later:
#   http://goo.gl/O4m48T
# Connection and relay IPs in PowerShell:
#   https://goo.gl/aBMZ9K
#   http://goo.gl/MrybFq


import logging
import re

import salt.utils.args
import salt.utils.platform
from salt.exceptions import SaltInvocationError

try:
    import wmi

    import salt.utils.winapi

    _HAS_MODULE_DEPENDENCIES = True
except ImportError:
    _HAS_MODULE_DEPENDENCIES = False

_DEFAULT_SERVER = "SmtpSvc/1"
_WMI_NAMESPACE = "MicrosoftIISv2"
_LOG = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "win_smtp_server"


def __virtual__():
    """
    Only works on Windows systems.
    """
    if salt.utils.platform.is_windows() and _HAS_MODULE_DEPENDENCIES:
        return __virtualname__
    return (
        False,
        "Module win_smtp_server: module only works on Windows systems with wmi.",
    )


def _get_wmi_setting(wmi_class_name, setting, server):
    """
    Get the value of the setting for the provided class.
    """
    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            wmi_class = getattr(connection, wmi_class_name)

            objs = wmi_class([setting], Name=server)[0]
            ret = getattr(objs, setting)
        except wmi.x_wmi as error:
            _LOG.error("Encountered WMI error: %s", error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error("Error getting %s: %s", wmi_class_name, error)
    return ret


def _set_wmi_setting(wmi_class_name, setting, value, server):
    """
    Set the value of the setting for the provided class.
    """
    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            wmi_class = getattr(connection, wmi_class_name)

            objs = wmi_class(Name=server)[0]
        except wmi.x_wmi as error:
            _LOG.error("Encountered WMI error: %s", error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error("Error getting %s: %s", wmi_class_name, error)

        try:
            setattr(objs, setting, value)
            return True
        except wmi.x_wmi as error:
            _LOG.error("Encountered WMI error: %s", error.com_error)
        except AttributeError as error:
            _LOG.error("Error setting %s: %s", setting, error)
    return False


def _normalize_server_settings(**settings):
    """
    Convert setting values that had been improperly converted to a dict back to a string.
    """
    ret = dict()
    settings = salt.utils.args.clean_kwargs(**settings)

    for setting in settings:
        if isinstance(settings[setting], dict):
            _LOG.debug("Fixing value: %s", settings[setting])
            value_from_key = next(iter(settings[setting].keys()))

            ret[setting] = f"{{{value_from_key}}}"
        else:
            ret[setting] = settings[setting]
    return ret


def get_log_format_types():
    """
    Get all available log format names and ids.

    :return: A dictionary of the log format names and ids.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_log_format_types
    """
    ret = dict()
    prefix = "logging/"

    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            objs = connection.IISLogModuleSetting()

            # Remove the prefix from the name.
            for obj in objs:
                name = str(obj.Name).replace(prefix, "", 1)
                ret[name] = str(obj.LogModuleId)
        except wmi.x_wmi as error:
            _LOG.error("Encountered WMI error: %s", error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error("Error getting IISLogModuleSetting: %s", error)

    if not ret:
        _LOG.error("Unable to get log format types.")
    return ret


def get_servers():
    """
    Get the SMTP virtual server names.

    :return: A list of the SMTP virtual servers.
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_servers
    """
    ret = list()

    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            objs = connection.IIsSmtpServerSetting()

            for obj in objs:
                ret.append(str(obj.Name))
        except wmi.x_wmi as error:
            _LOG.error("Encountered WMI error: %s", error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error("Error getting IIsSmtpServerSetting: %s", error)

    _LOG.debug("Found SMTP servers: %s", ret)
    return ret


def get_server_setting(settings, server=_DEFAULT_SERVER):
    """
    Get the value of the setting for the SMTP virtual server.

    :param str settings: A list of the setting names.
    :param str server: The SMTP server name.

    :return: A dictionary of the provided settings and their values.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_server_setting settings="['MaxRecipients']"
    """
    ret = dict()

    if not settings:
        _LOG.warning("No settings provided.")
        return ret

    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            objs = connection.IIsSmtpServerSetting(settings, Name=server)[0]

            for setting in settings:
                ret[setting] = str(getattr(objs, setting))
        except wmi.x_wmi as error:
            _LOG.error("Encountered WMI error: %s", error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error("Error getting IIsSmtpServerSetting: %s", error)
    return ret


def set_server_setting(settings, server=_DEFAULT_SERVER):
    """
    Set the value of the setting for the SMTP virtual server.

    .. note::

        The setting names are case-sensitive.

    :param str settings: A dictionary of the setting names and their values.
    :param str server: The SMTP server name.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.set_server_setting settings="{'MaxRecipients': '500'}"
    """
    if not settings:
        _LOG.warning("No settings provided")
        return False

    # Some fields are formatted like '{data}'. Salt tries to convert these to dicts
    # automatically on input, so convert them back to the proper format.
    settings = _normalize_server_settings(**settings)

    current_settings = get_server_setting(settings=settings.keys(), server=server)

    if settings == current_settings:
        _LOG.debug("Settings already contain the provided values.")
        return True

    # Note that we must fetch all properties of IIsSmtpServerSetting below, since
    # filtering for specific properties and then attempting to set them will cause
    # an error like: wmi.x_wmi Unexpected COM Error -2147352567
    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            objs = connection.IIsSmtpServerSetting(Name=server)[0]
        except wmi.x_wmi as error:
            _LOG.error("Encountered WMI error: %s", error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error("Error getting IIsSmtpServerSetting: %s", error)

        for setting in settings:
            if str(settings[setting]) != str(current_settings[setting]):
                try:
                    setattr(objs, setting, settings[setting])
                except wmi.x_wmi as error:
                    _LOG.error("Encountered WMI error: %s", error.com_error)
                except AttributeError as error:
                    _LOG.error("Error setting %s: %s", setting, error)

    # Get the settings post-change so that we can verify tht all properties
    # were modified successfully. Track the ones that weren't.
    new_settings = get_server_setting(settings=settings.keys(), server=server)
    failed_settings = dict()

    for setting in settings:
        if str(settings[setting]) != str(new_settings[setting]):
            failed_settings[setting] = settings[setting]
    if failed_settings:
        _LOG.error("Failed to change settings: %s", failed_settings)
        return False

    _LOG.debug("Settings configured successfully: %s", settings.keys())
    return True


def get_log_format(server=_DEFAULT_SERVER):
    """
    Get the active log format for the SMTP virtual server.

    :param str server: The SMTP server name.

    :return: A string of the log format name.
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_log_format
    """
    log_format_types = get_log_format_types()
    format_id = _get_wmi_setting("IIsSmtpServerSetting", "LogPluginClsid", server)

    # Since IIsSmtpServerSetting stores the log type as an id, we need
    # to get the mapping from IISLogModuleSetting and extract the name.
    for key in log_format_types:
        if str(format_id) == log_format_types[key]:
            return key
    _LOG.warning("Unable to determine log format.")
    return None


def set_log_format(log_format, server=_DEFAULT_SERVER):
    """
    Set the active log format for the SMTP virtual server.

    :param str log_format: The log format name.
    :param str server: The SMTP server name.

    :return: A boolean representing whether the change succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.set_log_format 'Microsoft IIS Log File Format'
    """
    setting = "LogPluginClsid"
    log_format_types = get_log_format_types()
    format_id = log_format_types.get(log_format, None)

    if not format_id:
        message = "Invalid log format '{}' specified. Valid formats: {}".format(
            log_format, log_format_types.keys()
        )
        raise SaltInvocationError(message)

    _LOG.debug("Id for '%s' found: %s", log_format, format_id)

    current_log_format = get_log_format(server)

    if log_format == current_log_format:
        _LOG.debug("%s already contains the provided format.", setting)
        return True

    _set_wmi_setting("IIsSmtpServerSetting", setting, format_id, server)

    new_log_format = get_log_format(server)
    ret = log_format == new_log_format

    if ret:
        _LOG.debug("Setting %s configured successfully: %s", setting, log_format)
    else:
        _LOG.error("Unable to configure %s with value: %s", setting, log_format)
    return ret


def get_connection_ip_list(as_wmi_format=False, server=_DEFAULT_SERVER):
    """
    Get the IPGrant list for the SMTP virtual server.

    :param bool as_wmi_format: Returns the connection IPs as a list in the format WMI expects.
    :param str server: The SMTP server name.

    :return: A dictionary of the IP and subnet pairs.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_connection_ip_list
    """
    ret = dict()
    setting = "IPGrant"
    reg_separator = r",\s*"

    if as_wmi_format:
        ret = list()

    addresses = _get_wmi_setting("IIsIPSecuritySetting", setting, server)

    # WMI returns the addresses as a tuple of unicode strings, each representing
    # an address/subnet pair. Remove extra spaces that may be present.
    for unnormalized_address in addresses:
        ip_address, subnet = re.split(reg_separator, unnormalized_address)
        if as_wmi_format:
            ret.append(f"{ip_address}, {subnet}")
        else:
            ret[ip_address] = subnet

    if not ret:
        _LOG.debug("%s is empty.", setting)
    return ret


def set_connection_ip_list(
    addresses=None, grant_by_default=False, server=_DEFAULT_SERVER
):
    """
    Set the IPGrant list for the SMTP virtual server.

    :param str addresses: A dictionary of IP + subnet pairs.
    :param bool grant_by_default: Whether the addresses should be a blacklist or whitelist.
    :param str server: The SMTP server name.

    :return: A boolean representing whether the change succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.set_connection_ip_list addresses="{'127.0.0.1': '255.255.255.255'}"
    """
    setting = "IPGrant"
    formatted_addresses = list()

    # It's okay to accept an empty list for set_connection_ip_list,
    # since an empty list may be desirable.
    if not addresses:
        addresses = dict()
        _LOG.debug("Empty %s specified.", setting)

    # Convert addresses to the 'ip_address, subnet' format used by
    # IIsIPSecuritySetting.
    for address in addresses:
        formatted_addresses.append(f"{address.strip()}, {addresses[address].strip()}")

    current_addresses = get_connection_ip_list(as_wmi_format=True, server=server)

    # Order is not important, so compare to the current addresses as unordered sets.
    if set(formatted_addresses) == set(current_addresses):
        _LOG.debug("%s already contains the provided addresses.", setting)
        return True

    # First we should check GrantByDefault, and change it if necessary.
    current_grant_by_default = _get_wmi_setting(
        "IIsIPSecuritySetting", "GrantByDefault", server
    )

    if grant_by_default != current_grant_by_default:
        _LOG.debug("Setting GrantByDefault to: %s", grant_by_default)
        _set_wmi_setting(
            "IIsIPSecuritySetting", "GrantByDefault", grant_by_default, server
        )

    _set_wmi_setting("IIsIPSecuritySetting", setting, formatted_addresses, server)

    new_addresses = get_connection_ip_list(as_wmi_format=True, server=server)
    ret = set(formatted_addresses) == set(new_addresses)

    if ret:
        _LOG.debug("%s configured successfully: %s", setting, formatted_addresses)
        return ret
    _LOG.error("Unable to configure %s with value: %s", setting, formatted_addresses)
    return ret


def get_relay_ip_list(server=_DEFAULT_SERVER):
    """
    Get the RelayIpList list for the SMTP virtual server.

    :param str server: The SMTP server name.

    :return: A list of the relay IPs.
    :rtype: list

    .. note::

        A return value of None corresponds to the restrictive 'Only the list below' GUI parameter
        with an empty access list, and setting an empty list/tuple corresponds to the more
        permissive 'All except the list below' GUI parameter.

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_relay_ip_list
    """
    ret = list()
    setting = "RelayIpList"

    lines = _get_wmi_setting("IIsSmtpServerSetting", setting, server)

    if not lines:
        _LOG.debug("%s is empty: %s", setting, lines)
        if lines is None:
            lines = [None]
        return list(lines)

    # WMI returns the addresses as a tuple of individual octets, so we
    # need to group them and reassemble them into IP addresses.
    i = 0
    while i < len(lines):
        octets = [str(x) for x in lines[i : i + 4]]
        address = ".".join(octets)
        ret.append(address)
        i += 4
    return ret


def set_relay_ip_list(addresses=None, server=_DEFAULT_SERVER):
    """
    Set the RelayIpList list for the SMTP virtual server.

    Due to the unusual way that Windows stores the relay IPs, it is advisable to retrieve
    the existing list you wish to set from a pre-configured server.

    For example, setting '127.0.0.1' as an allowed relay IP through the GUI would generate
    an actual relay IP list similar to the following:

    .. code-block:: cfg

        ['24.0.0.128', '32.0.0.128', '60.0.0.128', '68.0.0.128', '1.0.0.0', '76.0.0.0',
         '0.0.0.0', '0.0.0.0', '1.0.0.0', '1.0.0.0', '2.0.0.0', '2.0.0.0', '4.0.0.0',
         '0.0.0.0', '76.0.0.128', '0.0.0.0', '0.0.0.0', '0.0.0.0', '0.0.0.0',
         '255.255.255.255', '127.0.0.1']

    .. note::

        Setting the list to None corresponds to the restrictive 'Only the list below' GUI parameter
        with an empty access list configured, and setting an empty list/tuple corresponds to the
        more permissive 'All except the list below' GUI parameter.

    :param str addresses: A list of the relay IPs. The order of the list is important.
    :param str server: The SMTP server name.

    :return: A boolean representing whether the change succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.set_relay_ip_list addresses="['192.168.1.1', '172.16.1.1']"
    """
    setting = "RelayIpList"
    formatted_addresses = list()

    current_addresses = get_relay_ip_list(server)

    if list(addresses) == current_addresses:
        _LOG.debug("%s already contains the provided addresses.", setting)
        return True

    if addresses:
        # The WMI input data needs to be in the format used by RelayIpList. Order
        # is also important due to the way RelayIpList orders the address list.

        if addresses[0] is None:
            formatted_addresses = None
        else:
            for address in addresses:
                for octet in address.split("."):
                    formatted_addresses.append(octet)

    _LOG.debug("Formatted %s addresses: %s", setting, formatted_addresses)

    _set_wmi_setting("IIsSmtpServerSetting", setting, formatted_addresses, server)

    new_addresses = get_relay_ip_list(server)

    ret = list(addresses) == new_addresses

    if ret:
        _LOG.debug("%s configured successfully: %s", setting, addresses)
        return ret
    _LOG.error("Unable to configure %s with value: %s", setting, addresses)
    return ret
