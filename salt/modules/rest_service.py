# -*- coding: utf-8 -*-
'''
Service support for the REST example
'''
from __future__ import absolute_import

# Import python libs
import logging

log = logging.getLogger(__name__)

__proxyenabled__ = ['rest_sample']
# Define the module's virtual name
__virtualname__ = 'service'

# Don't shadow built-ins.
__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    '''
    Only work on RestExampleOS
    '''
    # Enable on these platforms only.
    enable = set((
        'RestExampleOS',
        'proxy',
    ))
    if __grains__['os'] in enable:
        return __virtualname__
    return False


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    return __opts__['proxymodule']['rest_sample.service_start'](name)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    return __opts__['proxymodule']['rest_sample.service_stop'](name)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''

    return __opts__['proxymodule']['rest_sample.service_restart'](name)


def status(name):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    '''
    return __opts__['proxymodule']['rest_sample.service_status'](name)


def list_():
    '''
    List services.

    CLI Example:

    .. code-block:: bash

        salt '*' service.list <service name>
    '''
    return __opts__['proxymodule']['rest_sample.service_list']()
