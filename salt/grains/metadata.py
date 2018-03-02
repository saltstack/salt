# -*- coding: utf-8 -*-
'''
Grains from cloud metadata servers at 169.254.169.254

.. versionadded:: 2017.7.0

:depends: requests

To enable these grains that pull from the http://169.254.169.254/latest
metadata server set `metadata_server_grains: True`.

.. code-block:: yaml

    metadata_server_grains: True

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import os
import socket

# Import salt libs
import salt.utils.http as http
import salt.utils.json


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
    linedata = http.query(os.path.join(HOST, prefix))
    if 'body' not in linedata:
        return ret
    for line in linedata['body'].split('\n'):
        if line.endswith('/'):
            ret[line[:-1]] = _search(prefix=os.path.join(prefix, line))
        elif prefix == 'latest/':
            # (gtmanfred) The first level should have a forward slash since
            # they have stuff underneath. This will not be doubled up though,
            # because lines ending with a slash are checked first.
            ret[line] = _search(prefix=os.path.join(prefix, line + '/'))
        elif line.endswith(('dynamic', 'meta-data')):
            ret[line] = _search(prefix=os.path.join(prefix, line))
        elif '=' in line:
            key, value = line.split('=')
            ret[value] = _search(prefix=os.path.join(prefix, key))
        else:
            retdata = http.query(os.path.join(HOST, prefix, line)).get('body', None)
            # (gtmanfred) This try except block is slightly faster than
            # checking if the string starts with a curly brace
            try:
                ret[line] = salt.utils.json.loads(retdata)
            except ValueError:
                ret[line] = retdata
    return ret


def metadata():
    return _search()
