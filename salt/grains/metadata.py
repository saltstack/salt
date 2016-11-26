# -*- coding: utf-8 -*-
'''
Grains from cloud metadata servers at 169.254.169.254

.. versionadded:: Nitrogen

:depends: requests

To enable these grains that pull from the http://169.254.169.254/latest
metadata server set `metadata_server_grains: True`.

.. code-block:: yaml

    metadata_server_grains: True

'''
from __future__ import absolute_import

# Import python libs
import os
import socket

# Import salt libs
import salt.utils.http as http


# metadata server information
IP = '169.254.169.254'
HOST = 'http://{0}/'.format(IP)


def __virtual__():
    if __opts__.get('metadata_server_grains', False) is False:
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(.1)
    result = sock.connect_ex((IP, 80))
    if result != 0:
        return False
    if http.query(os.path.join(HOST, 'latest/'), status=True).get('status') != 200:
        return False
    return True


def _search(prefix="latest/"):
    '''
    Recursively look up all grains in the metadata server
    '''
    ret = {}
    for line in http.query(os.path.join(HOST, prefix))['body'].split('\n'):
        if line.endswith('/'):
            ret[line[:-1]] = _search(prefix=os.path.join(prefix, line))
        elif '=' in line:
            key, value = line.split('=')
            ret[value] = _search(prefix=os.path.join(prefix, key))
        else:
            ret[line] = http.query(os.path.join(HOST, prefix, line))['body']
    return ret


def metadata():
    return _search()
