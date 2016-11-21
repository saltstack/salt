# -*- coding: utf-8 -*-
'''
uWSGI stats server https://uwsgi-docs.readthedocs.io/en/latest/StatsServer.html

:maintainer: Peter Baumgartner <pete@lincolnloop.com>
:maturity:   new
:platform:   all
'''
from __future__ import absolute_import

# Import Python libs
import json

# Import Salt libs
import salt.utils


def __virtual__():
    '''
    Only load the module if uwsgi is installed
    '''
    cmd = 'uwsgi'
    if salt.utils.which(cmd):
        return cmd
    return (False, 'The uwsgi execution module failed to load: the uwsgi binary is not in the path.')


def stats(socket):
    '''
    Return the data from `uwsgi --connect-and-read` as a dictionary.

    socket
        The socket the uWSGI stats server is listening on

    CLI Example:

    .. code-block:: bash

        salt '*' uwsgi.stats /var/run/mystatsserver.sock

        salt '*' uwsgi.stats 127.0.0.1:5050
    '''

    cmd = ['uwsgi', '--connect-and-read', '{0}'.format(socket)]
    out = __salt__['cmd.run'](cmd, python_shell=False)
    return json.loads(out)
