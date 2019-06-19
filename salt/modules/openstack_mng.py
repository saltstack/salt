# -*- coding: utf-8 -*-
'''
Module for OpenStack Management

:codeauthor:    Konrad Mosoń <mosonkonrad@gmail.com>
:maturity:      new
:depends:       openstack-utils
:platform:      linux
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os.path

# Import salt libs
import salt.utils.files
import salt.utils.stringutils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'openstack_mng'


def __virtual__():
    '''
    Only load this module if openstack-service is installed
    '''
    if os.path.isfile('/usr/bin/openstack-service'):
        return __virtualname__
    else:
        return (False, 'The openstack-service binary could not be found.')


def start_service(service_name):
    '''
    Start OpenStack service immediately

    CLI Example:

    .. code-block:: bash

        salt '*' openstack_mng.start_service neutron
    '''

    os_cmd = ['/usr/bin/openstack-service', 'start', service_name]
    return __salt__['cmd.retcode'](os_cmd) == 0


def stop_service(service_name):
    '''
    Stop OpenStack service immediately

    CLI Example:

    .. code-block:: bash

        salt '*' openstack_mng.stop_service neutron
    '''

    os_cmd = ['/usr/bin/openstack-service', 'stop', service_name]
    return __salt__['cmd.retcode'](os_cmd) == 0


def restart_service(service_name, minimum_running_time=None):
    '''
    Restart OpenStack service immediately, or only if it's running longer than
    specified value

    CLI Example:

    .. code-block:: bash

        salt '*' openstack_mng.restart_service neutron
        salt '*' openstack_mng.restart_service neutron minimum_running_time=600
    '''

    if minimum_running_time:
        ret_code = False
        # get system services list for interesting openstack service
        services = __salt__['cmd.run'](['/usr/bin/openstack-service', 'list', service_name]).split('\n')
        for service in services:
            service_info = __salt__['service.show'](service)
            with salt.utils.files.fopen('/proc/uptime') as rfh:
                boot_time = float(
                    salt.utils.stringutils.to_unicode(
                        rfh.read()
                    ).split(' ')[0]
                )

            expr_time = int(service_info.get('ExecMainStartTimestampMonotonic', 0)) / 1000000 < boot_time - minimum_running_time
            expr_active = service_info.get('ActiveState') == "active"

            if expr_time or not expr_active:
                # restart specific system service
                ret = __salt__['service.restart'](service)
                if ret:
                    ret_code = True

        return ret_code
    else:
        # just restart
        os_cmd = ['/usr/bin/openstack-service', 'restart', service_name]
        return __salt__['cmd.retcode'](os_cmd) == 0
