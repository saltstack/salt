# -*- coding: utf-8 -*-
'''
uWSGI stats server http://uwsgi-docs.readthedocs.org/en/latest/StatsServer.html

:maintainer: Peter Baumgartner <pete@lincolnloop.com>
:maturity:   new
:platform:   all
'''

# Import Python libs
import json

# Import Salt libs
import salt.utils

# Don't shadow built-in's.
__func_alias__ = {
    'help_': 'help'
}

def __virtual__():
    '''
    Only load the module if uwsgi is installed
    '''
    cmd = 'uwsgi'
    if salt.utils.which(cmd):
        return cmd
    return False


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

    cmd = 'uwsgi --connect-and-read {0}'.format(socket)
    out = __salt__['cmd.run'](cmd)
    return json.loads(out)


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' wsgi.help

        salt '*' wsgi.help stats
    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))

