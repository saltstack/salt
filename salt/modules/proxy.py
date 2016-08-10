# -*- coding: utf-8 -*-
'''
This module allows you to manage proxy settings

.. code-block:: bash

    salt '*' network.get_http_proxy
'''

# Import Python Libs
from __future__ import absolute_import
import logging
import re

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)
__virtualname__ = 'proxy'


def __virtual__():
    '''
    Only work on Mac OS and Windows
    '''
    if salt.utils.is_darwin() or salt.utils.is_windows():
        return True
    return False


def _get_proxy_osx(function, network_service):
    ret = {}

    out = __salt__['cmd.run']('networksetup -{0} {1}'.format(function, network_service))
    match = re.match('Enabled: (.*)\nServer: (.*)\nPort: (.*)\n', out)
    if match is not None:
        g = match.groups()
        enabled = True if g[0] == "Yes" else False
        ret = {"enabled": enabled, "server": g[1], "port": g[2]}

    return ret


def _set_proxy_osx(function, server, port, user, password, network_service):
    cmd = 'networksetup -{0} {1} {2} {3}'.format(function, network_service, server, port)

    if user is not None and password is not None:
        cmd = cmd + ' On {0} {1}'.format(user, password)

    out = __salt__['cmd.run'](cmd)

    return 'error' not in out


def _get_proxy_windows(types=None):
    ret = {}

    if types is None:
        types = ['http', 'https', 'ftp']

    reg_val = __salt__['reg.read_value']('HKEY_CURRENT_USER',
                                         r'SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings',
                                         'ProxyServer')
    servers = reg_val['vdata']

    if "=" in servers:
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
            ret[proxy_type] = {"server": server, "port": port}

    # Filter out types
    if len(types) == 1:
        return ret[types[0]]
    else:
        for key in ret.keys():
            if key not in types:
                del ret[key]

    # Return enabled info
    reg_val = __salt__['reg.read_value']('HKEY_CURRENT_USER',
                                         r'SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings',
                                         'ProxyEnable')
    enabled = reg_val.get('vdata', 0)
    ret['enabled'] = True if enabled == 1 else False

    return ret


def _set_proxy_windows(server, port, types=None, bypass_hosts=None, import_winhttp=True):
    if types is None:
        types = ['http', 'https', 'ftp']

    server_str = ''
    for t in types:
        server_str += '{0}={1}:{2};'.format(t, server, port)

    __salt__['reg.set_value']('HKEY_CURRENT_USER', r'SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings',
                              'ProxyServer', server_str)

    __salt__['reg.set_value']('HKEY_CURRENT_USER', r'SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings',
                              'ProxyEnable', 1, vtype='REG_DWORD')

    if bypass_hosts is not None:
        bypass_hosts_str = '<local>;{0}'.format(';'.join(bypass_hosts))

        __salt__['reg.set_value']('HKEY_CURRENT_USER', r'SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings',
                                  'ProxyOverride', bypass_hosts_str)

    if import_winhttp:
        cmd = 'netsh winhttp import proxy source=ie'
        __salt__['cmd.run'](cmd)

    return True


def get_http_proxy(network_service="Ethernet"):
    '''
    Returns the current http proxy settings

    network_service
        The network service to apply the changes to, this only necessary on OSX

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.get_http_proxy Ethernet
    '''
    if __grains__['os'] == 'Windows':
        return _get_proxy_windows(['http'])

    return _get_proxy_osx("getwebproxy", network_service)


def set_http_proxy(server, port, user=None, password=None, network_service="Ethernet", bypass_hosts=None):
    '''
    Sets the http proxy settings. Note: On Windows this will override any other proxy settings you have,
    the preferred method of updating proxies on windows is using set_proxy.

    server
        The proxy server to use

    port
        The port used by the proxy server

    user
        The username to use for the proxy server if required

    password
        The password to use if required by the server

    network_service
        The network service to apply the changes to, this only necessary on OSX

    bypass_hosts
        The hosts that are allowed to by pass the proxy. Only used on Windows for other OS's use
        set_proxy_bypass to edit the bypass hosts.

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.set_http_proxy example.com 1080 user=proxy_user password=proxy_pass network_service=Ethernet
    '''
    if __grains__['os'] == 'Windows':
        return _set_proxy_windows(server, port, ['http'], bypass_hosts)

    return _set_proxy_osx("setwebproxy", server, port, user, password, network_service)


def get_https_proxy(network_service="Ethernet"):
    '''
    Returns the current https proxy settings

    network_service
        The network service to apply the changes to, this only necessary on OSX

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.get_https_proxy Ethernet
    '''
    if __grains__['os'] == 'Windows':
        return _get_proxy_windows(['https'])

    return _get_proxy_osx("getsecurewebproxy", network_service)


def set_https_proxy(server, port, user=None, password=None, network_service="Ethernet", bypass_hosts=None):
    '''
    Sets the https proxy settings. Note: On Windows this will override any other proxy settings you have,
    the preferred method of updating proxies on windows is using set_proxy.

    server
        The proxy server to use

    port
        The port used by the proxy server

    user
        The username to use for the proxy server if required

    password
        The password to use if required by the server

    network_service
        The network service to apply the changes to, this only necessary on OSX

    bypass_hosts
        The hosts that are allowed to by pass the proxy. Only used on Windows for other OS's use
        set_proxy_bypass to edit the bypass hosts.

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.set_https_proxy example.com 1080 user=proxy_user password=proxy_pass network_service=Ethernet
    '''
    if __grains__['os'] == 'Windows':
        return _set_proxy_windows(server, port, ['https'], bypass_hosts)

    return _set_proxy_osx("setsecurewebproxy", server, port, user, password, network_service)


def get_ftp_proxy(network_service="Ethernet"):
    '''
    Returns the current ftp proxy settings

    network_service
        The network service to apply the changes to, this only necessary on OSX

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.get_ftp_proxy Ethernet
    '''
    if __grains__['os'] == 'Windows':
        return _get_proxy_windows(['ftp'])

    return _get_proxy_osx("getftpproxy", network_service)


def set_ftp_proxy(server, port, user=None, password=None, network_service="Ethernet", bypass_hosts=None):
    '''
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
        The network service to apply the changes to, this only necessary on OSX

    bypass_hosts
        The hosts that are allowed to by pass the proxy. Only used on Windows for other OS's use
        set_proxy_bypass to edit the bypass hosts.

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.set_ftp_proxy example.com 1080 user=proxy_user password=proxy_pass network_service=Ethernet
    '''
    if __grains__['os'] == 'Windows':
        return _set_proxy_windows(server, port, ['ftp'], bypass_hosts)

    return _set_proxy_osx("setftpproxy", server, port, user, password, network_service)


def get_proxy_bypass(network_service="Ethernet"):
    '''
    Returns the current domains that can bypass the proxy

    network_service
        The network service to get the bypass domains from, this is only necessary on OSX

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.get_proxy_bypass

    '''
    if __grains__['os'] == 'Windows':
        reg_val = __salt__['reg.read_value']('HKEY_CURRENT_USER',
                                         r'SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings',
                                         'ProxyOverride')
        bypass_servers = reg_val['vdata'].replace("<local>", "").split(";")

        return bypass_servers

    out = __salt__['cmd.run']('networksetup -getproxybypassdomains {0}'.format(network_service))

    return out.split("\n")


def set_proxy_bypass(domains, network_service="Ethernet"):
    '''
    Sets the domains that can bypass the proxy

    domains
        An array of domains allowed to bypass the proxy

    network_service
        The network service to apply the changes to, this only necessary on OSX

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.set_proxy_bypass "['127.0.0.1', 'localhost']"

    '''
    servers_str = ' '.join(domains)
    cmd = 'networksetup -setproxybypassdomains {0} {1}'.format(network_service, servers_str,)
    out = __salt__['cmd.run'](cmd)

    return 'error' not in out


def set_proxy_win(server, port, types=None, bypass_hosts=None):
    '''
    Sets the http proxy settings, only works with Windows.

    server
        The proxy server to use

    password
        The password to use if required by the server

    types
        The types of proxy connections should be setup with this server. Valid types are http and https.

    bypass_hosts
        The hosts that are allowed to by pass the proxy.

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.set_http_proxy example.com 1080 types="['http', 'https']"
    '''
    if __grains__['os'] == 'Windows':
        return _set_proxy_windows(server, port, types, bypass_hosts)


def get_proxy_win():
    '''
    Gets all of the proxy settings in one call, only available on Windows

    CLI Example:

    .. code-block:: bash

        salt '*' proxy.get_proxy_win
    '''
    if __grains__['os'] == 'Windows':
        return _get_proxy_windows()
