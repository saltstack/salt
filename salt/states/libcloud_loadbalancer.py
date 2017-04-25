# -*- coding: utf-8 -*-
'''
Apache Libcloud Load Balancer State
===================================

Manage load balancers using libcloud

    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`

Apache Libcloud load balancer management for a full list
of supported clouds, see http://libcloud.readthedocs.io/en/latest/loadbalancer/supported_providers.html

Clouds include Amazon ELB, ALB, Google, Aliyun, CloudStack, Softlayer

.. versionadded:: Oxygen

:configuration:
    This module uses a configuration profile for one or multiple Cloud providers

    .. code-block:: yaml

        libcloud_loadbalancer:
            profile_test1:
              driver: gce
              key: GOOG0123456789ABCXYZ
              secret: mysecret
            profile_test2:
              driver: alb
              key: 12345
              secret: mysecret

:depends: apache-libcloud
'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)


def state_result(result, message):
    return {'result': result, 'comment': message}


def balancer_present(name, port, protocol, profile):
    '''
    Ensures a load balancer is present.

    :param name: Load Balancer name
    :type  name: ``str``

    :param port: Port the load balancer should listen on, defaults to 80
    :type  port: ``str``

    :param protocol: Loadbalancer protocol, defaults to http.
    :type  protocol: ``str``

    :param profile: The profile key
    :type  profile: ``str``
    '''
    balancers = __salt__['libcloud_loadbalancer.list_balancers'](profile)
    match = [z for z in balancers if z['name'] == name]
    if len(match) > 0:
        return state_result(True, "Balancer already exists")
    else:
        result = __salt__['libcloud_loadbalancer.create_balancer'](name, port, protocol, profile)
        return state_result(result, "Created new load balancer")


def balancer_absent(name, profile):
    '''
    Ensures a load balancer is absent.

    :param name: Load Balancer name
    :type  name: ``str``

    :param profile: The profile key
    :type  profile: ``str``
    '''
    balancers = __salt__['libcloud_loadbalancer.list_balancers'](profile)
    match = [z for z in balancers if z['name'] == name]
    if len(match) == 0:
        return state_result(True, "Balancer already absent")
    else:
        result = __salt__['libcloud_loadbalancer.delete_balancer'](match['id'], profile)
        return state_result(result, "Deleted load balancer")


