# -*- coding: utf-8 -*-
'''
Service support for the REST example
'''

# Import python libs
import logging

log = logging.getLogger(__name__)

__proxyenabled__ = ['rest_sample']
# Define the module's virtual name
__virtualname__ = 'service'

# Don't shadow built-ins.
__func_alias__ = {
    'help_': 'help',
    'list_': 'list'
}


def __virtual__():
    '''
    Only work on RestExampleOS
    '''
    # Enable on these platforms only.
    enable = set((
        'RestExampleOS',
    ))
    if __grains__['os'] in enable:
        return __virtualname__
    return False


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' rest_service.start <service name>
    '''
    return __opts__['proxyobject'].service_start(name)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' rest_service.stop <service name>
    '''
    return __opts__['proxyobject'].service_stop(name)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' rest_service.restart <service name>
    '''

    return __opts__['proxyobject'].service_restart(name)


def status(name):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example:

    .. code-block:: bash

        salt '*' rest_service.status <service name>
    '''
    return __opts__['proxyobject'].service_status(name)


def list_():
    '''
    List services.

    CLI Example:

    .. code-block:: bash

        salt '*' rest_service.list <service name>
    '''
    return __opts__['proxyobject'].service_list()


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' rest_service.help

        salt '*' rest_service.help list
    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))
