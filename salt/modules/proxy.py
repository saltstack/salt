"""
This module allows you to manage proxy settings

.. code-block:: bash

    salt '*' network.get_http_proxy
"""


import logging
import re

import salt.utils.platform

log = logging.getLogger(__name__)
__virtualname__ = "proxy"


def __virtual__():
    """
    Only work on Mac OS and Windows
    """
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_windows():
        return True
    return False, "Module proxy: module only works on Windows or MacOS systems"


def _get_proxy_osx(cmd_function, network_service):
    ret = {}

    out = __salt__["cmd.run"](
        "networksetup -{} {}".format(cmd_function, network_service)
    )
    match = re.match("Enabled: (.*)\nServer: (.*)\nPort: (.*)\n", out)
    if match is not None:
        g = match.groups()
        enabled = True if g[0] == "Yes" else False
        ret = {"enabled": enabled, "server": g[1], "port": g[2]}

    return ret


def _set_proxy_osx(cmd_function, server, port, user, password, network_service):
    cmd = "networksetup -{} {} {} {}".format(
        cmd_function, network_service, server, port
    )

    if user is not None and password is not None:
        cmd = cmd + " On {} {}".format(user, password)

    out = __salt__["cmd.run"](cmd)

    return "error" not in out


def _get_proxy_windows(types=None):
    proxies = {}

    if types is None:
        types = ["http", "https", "ftp"]

    servers = __utils__["reg.read_value"](
        hive="HKEY_CURRENT_USER",
        key=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings",
        vname="ProxyServer",
    )["vdata"]

    if servers and "=" in servers:
        split = servers.split(";")
        for s in split:
            if len(s) == 0:
                continue

            if ":" in s:
                server_type, port = s.split(":")
            else:
                server_type = s
                port = None

            proxy_type, server = server_type.split("=")
            proxies[proxy_type] = {"server": server, "port": port}

    ret = {}
    if proxies:
        if len(types) == 1:
            return proxies[types[0]]
        else:
            # Filter out types
            for proxy in proxies:
                if proxy in types:
                    ret[proxy] = proxies[proxy]

    # Return enabled info
    ret["enabled"] = (
        __utils__["reg.read_value"](
            hive="HKEY_CURRENT_USER",
            key=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings",
            vname="ProxyEnable",
        )["vdata"]
        == 1
    )

    return ret


def _set_proxy_windows(
    server, port, types=None, bypass_hosts=None, import_winhttp=True
):
    if types is None:
        types = ["http", "https", "ftp"]

    server_str = ""
    for t in types:
        server_str += "{}={}:{};".format(t, server, port)

    __utils__["reg.set_value"](
        hive="HKEY_CURRENT_USER",
        key=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings",
        vname="ProxyServer",
        vdata=server_str,
    )

    __utils__["reg.set_value"](
        hive="HKEY_CURRENT_USER",
        key=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings",
        vname="ProxyEnable",
        vdata=1,
        vtype="REG_DWORD",
    )

    if bypass_hosts is not None:
        bypass_hosts_str = "<local>;{}".format(";".join(bypass_hosts))

        __utils__["reg.set_value"](
            hive="HKEY_CURRENT_USER",
            key=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings",
            vname="ProxyOverride",
            vdata=bypass_hosts_str,
        )

    if import_winhttp:
        cmd = "netsh winhttp import proxy source=ie"
        __salt__["cmd.run"](cmd)

    return True


def get_http_proxy(network_service="Ethernet"):
    """
    Returns the current http proxy settings

    network_service
        The network service to apply the changes to, this only necessary on
        macOS

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.get_http_proxy Ethernet
    """
    if __grains__["os"] == "Windows":
        return _get_proxy_windows(types=["http"])

    return _get_proxy_osx(cmd_function="getwebproxy", network_service=network_service)


def set_http_proxy(
    server,
    port,
    user=None,
    password=None,
    network_service="Ethernet",
    bypass_hosts=None,
):
    """
    Sets the http proxy settings. Note: On Windows this will override any other
    proxy settings you have, the preferred method of updating proxies on windows
    is using set_proxy.

    server
        The proxy server to use

    port
        The port used by the proxy server

    user
        The username to use for the proxy server if required

    password
        The password to use if required by the server

    network_service
        The network service to apply the changes to, this only necessary on
        macOS

    bypass_hosts
        The hosts that are allowed to by pass the proxy. Only used on Windows
        for other OS's use set_proxy_bypass to edit the bypass hosts.

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.set_http_proxy example.com 1080 user=proxy_user password=proxy_pass network_service=Ethernet
    """
    if __grains__["os"] == "Windows":
        return _set_proxy_windows(
            server=server, port=port, types=["http"], bypass_hosts=bypass_hosts
        )

    return _set_proxy_osx(
        cmd_function="setwebproxy",
        server=server,
        port=port,
        user=user,
        password=password,
        network_service=network_service,
    )


def get_https_proxy(network_service="Ethernet"):
    """
    Returns the current https proxy settings

    network_service
        The network service to apply the changes to, this only necessary on
        macOS

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.get_https_proxy Ethernet
    """
    if __grains__["os"] == "Windows":
        return _get_proxy_windows(types=["https"])

    return _get_proxy_osx(
        cmd_function="getsecurewebproxy", network_service=network_service
    )


def set_https_proxy(
    server,
    port,
    user=None,
    password=None,
    network_service="Ethernet",
    bypass_hosts=None,
):
    """
    Sets the https proxy settings. Note: On Windows this will override any other
    proxy settings you have, the preferred method of updating proxies on windows
    is using set_proxy.

    server
        The proxy server to use

    port
        The port used by the proxy server

    user
        The username to use for the proxy server if required

    password
        The password to use if required by the server

    network_service
        The network service to apply the changes to, this only necessary on
        macOS

    bypass_hosts
        The hosts that are allowed to by pass the proxy. Only used on Windows
        for other OS's use set_proxy_bypass to edit the bypass hosts.

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.set_https_proxy example.com 1080 user=proxy_user password=proxy_pass network_service=Ethernet
    """
    if __grains__["os"] == "Windows":
        return _set_proxy_windows(
            server=server, port=port, types=["https"], bypass_hosts=bypass_hosts
        )

    return _set_proxy_osx(
        cmd_function="setsecurewebproxy",
        server=server,
        port=port,
        user=user,
        password=password,
        network_service=network_service,
    )


def get_ftp_proxy(network_service="Ethernet"):
    """
    Returns the current ftp proxy settings

    network_service
        The network service to apply the changes to, this only necessary on
        macOS

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.get_ftp_proxy Ethernet
    """
    if __grains__["os"] == "Windows":
        return _get_proxy_windows(types=["ftp"])

    return _get_proxy_osx(cmd_function="getftpproxy", network_service=network_service)


def set_ftp_proxy(
    server,
    port,
    user=None,
    password=None,
    network_service="Ethernet",
    bypass_hosts=None,
):
    """
    Sets the ftp proxy settings

    server
        The proxy server to use

    port
        The port used by the proxy server

    user
        The username to use for the proxy server if required

    password
        The password to use if required by the server

    network_service
        The network service to apply the changes to, this only necessary on
        macOS

    bypass_hosts
        The hosts that are allowed to by pass the proxy. Only used on Windows
        for other OS's use set_proxy_bypass to edit the bypass hosts.

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.set_ftp_proxy example.com 1080 user=proxy_user password=proxy_pass network_service=Ethernet
    """
    if __grains__["os"] == "Windows":
        return _set_proxy_windows(
            server=server, port=port, types=["ftp"], bypass_hosts=bypass_hosts
        )

    return _set_proxy_osx(
        cmd_function="setftpproxy",
        server=server,
        port=port,
        user=user,
        password=password,
        network_service=network_service,
    )


def get_proxy_bypass(network_service="Ethernet"):
    """
    Returns the current domains that can bypass the proxy

    network_service
        The network service to get the bypass domains from, this is only
        necessary on macOS

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.get_proxy_bypass

    """
    if __grains__["os"] == "Windows":
        reg_val = __utils__["reg.read_value"](
            hive="HKEY_CURRENT_USER",
            key=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings",
            vname="ProxyOverride",
        )["vdata"]

        # `reg.read_value` returns None if the key doesn't exist
        if reg_val is None:
            return []

        return reg_val.replace("<local>", "").split(";")

    out = __salt__["cmd.run"](
        "networksetup -getproxybypassdomains {}".format(network_service)
    )

    return out.split("\n")


def set_proxy_bypass(domains, network_service="Ethernet"):
    """
    Sets the domains that can bypass the proxy

    domains
        An array of domains allowed to bypass the proxy

    network_service
        The network service to apply the changes to, this only necessary on
        macOS

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.set_proxy_bypass "['127.0.0.1', 'localhost']"

    """
    servers_str = " ".join(domains)
    cmd = "networksetup -setproxybypassdomains {} {}".format(
        network_service,
        servers_str,
    )
    out = __salt__["cmd.run"](cmd)

    return "error" not in out


def set_proxy_win(server, port, types=None, bypass_hosts=None):
    """
    Sets the http proxy settings, only works with Windows.

    server
        The proxy server to use

    password
        The password to use if required by the server

    types
        The types of proxy connections should be setup with this server. Valid
        types are:

            - ``http``
            - ``https``
            - ``ftp``

    bypass_hosts
        The hosts that are allowed to by pass the proxy.

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.set_http_proxy example.com 1080 types="['http', 'https']"
    """
    if __grains__["os"] == "Windows":
        return _set_proxy_windows(
            server=server, port=port, types=types, bypass_hosts=bypass_hosts
        )


def get_proxy_win():
    """
    Gets all of the proxy settings in one call, only available on Windows

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.get_proxy_win
    """
    if __grains__["os"] == "Windows":
        return _get_proxy_windows()
