# -*- coding: utf-8 -*-
'''
Module for OpenStack Management

:codeauthor:    Konrad Mosoń <mosonkonrad@gmail.com>
:maturity:      new
:depends:       openstack-utils
:platform:      linux
'''

from __future__ import absolute_import

# Import python libs
import logging
import time

# Import salt libs

# Import third party libs
import os.path
if os.path.isfile('/usr/bin/openstack-service'):
    HAS_OPENSTACK = True
else:
    HAS_OPENSTACK = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'openstack_mng'


def __virtual__():
    '''
    Only load this module if openstack-service is installed
    '''
    if HAS_OPENSTACK:
        return __virtualname__
    else:
        return (False, 'The openstack-service binary could not be found.')


def start_service(service_name):
    '''
    Start OpenStack service immiedately

    CLI Example:

    .. code-block:: bash
        salt '*' openstack_mng.start_service neutron
    '''

    ret = __salt__['cmd.run_all'](['/usr/bin/openstack-service', 'start', service_name])
    if ret.get('retcode', 0) == 0:
        return True

    return False


def stop_service(service_name):
    '''
    Stop OpenStack service immiedately

    CLI Example:

    .. code-block:: bash
        salt '*' openstack_mng.stop_service neutron
    '''

    ret = __salt__['cmd.run_all'](['/usr/bin/openstack-service', 'stop', service_name])
    if ret.get('retcode', 0) == 0:
        return True

    return False


def restart_service(service_name, minimum_running_time=None):
    '''
    Restart OpenStack service immiedately, or only if it's running longer than
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

            boot_time = float(open('/proc/uptime').read().split(' ')[0])

            expr_time = int(service_info.get('ExecMainStartTimestampMonotonic', 0)) / 1000000 < boot_time - minimum_running_time
            expr_active = True if service_info.get('ActiveState') == "active" else False

            if expr_time or not expr_active:
                # restart specific system service
                ret = __salt__['service.restart'](service)
                if ret:
                    ret_code = True

        return ret_code
    else:
        # just restart
        ret = __salt__['cmd.run_all'](['/usr/bin/openstack-service', 'restart', service_name])
        if ret.get('retcode', 0) == 0:
            return True

    return False
