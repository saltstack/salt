'''
Define some generic socket functions for network modules
'''

# Import python libs
import socket
from string import ascii_letters, digits


# pylint: disable-msg=C0103

def sanitize_host(host):
    '''
    Sanitize host string.
    '''
    return ''.join([
        c for c in host[0:255] if c in (ascii_letters + digits + '.-')
    ])


def isportopen(host, port):
    '''
    Return status of a port

    CLI Example::

        salt '*' network.isportopen 127.0.0.1 22
    '''

    if not (1 <= int(port) <= 65535):
        return False

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    out = sock.connect_ex((sanitize_host(host), int(port)))

    return out


def host_to_ip(host):
    '''
    Returns the IP address of a given hostname

    CLI Example::

        salt '*' network.host_to_ip example.com
    '''
    try:
        ip = socket.gethostbyname(host)
    except Exception:
        ip = None
    return ip


def ip_to_host(ip):
    '''
    Returns the hostname of a given IP

    CLI Example::

        salt '*' network.ip_to_host 8.8.8.8
    '''
    try:
        hostname, aliaslist, ipaddrlist = socket.gethostbyaddr(ip)
    except Exception:
        hostname = None
    return hostname

# pylint: enable-msg=C0103
