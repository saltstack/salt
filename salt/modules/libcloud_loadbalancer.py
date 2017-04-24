# -*- coding: utf-8 -*-
'''
Apache Libcloud Load Balancer Management
========================================

Connection module for Apache Libcloud Storage load balancer management for a full list
of supported clouds, see http://libcloud.readthedocs.io/en/latest/loadbalancer/supported_providers.html

Clouds include Amazon ELB, ALB, Google, Aliyun, CloudStack, Softlayer

.. versionadded:: Oxygen

:configuration:
    This module uses a configuration profile for one or multiple Storage providers

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
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

from __future__ import absolute_import

# Import Python libs
import logging

# Import salt libs
import salt.utils.compat
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)

# Import third party libs
REQUIRED_LIBCLOUD_VERSION = '1.5.0'
try:
    #pylint: disable=unused-import
    import libcloud
    from libcloud.loadbalancer.providers import get_driver
    #pylint: enable=unused-import
    if hasattr(libcloud, '__version__') and _LooseVersion(libcloud.__version__) < _LooseVersion(REQUIRED_LIBCLOUD_VERSION):
        raise ImportError()
    logging.getLogger('libcloud').setLevel(logging.CRITICAL)
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False


def __virtual__():
    '''
    Only load if libcloud libraries exist.
    '''
    if not HAS_LIBCLOUD:
        msg = ('A apache-libcloud library with version at least {0} was not '
               'found').format(REQUIRED_LIBCLOUD_VERSION)
        return (False, msg)
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)


def _get_driver(profile):
    config = __salt__['config.option']('libcloud_loadbalancer')[profile]
    cls = get_driver(config['driver'])
    args = config
    del args['driver']
    args['key'] = config.get('key')
    args['secret'] = config.get('secret', None)
    args['secure'] = config.get('secure', True)
    args['host'] = config.get('host', None)
    args['port'] = config.get('port', None)
    return cls(**args)


def list_balancers(profile):
    '''
    Return a list of load balancers.

    :param profile: The profile key
    :type  profile: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.list_balancers profile1
    '''
    conn = _get_driver(profile=profile)
    balancers = conn.list_balancers()
    ret = []
    for balancer in balancers:
        ret.append(_simple_balancer(balancer))
    return ret


def list_protocols(profile):
    '''
    Return a list of supported protocols.

    :param profile: The profile key
    :type  profile: ``str``

    :return: a list of supported protocols
    :rtype: ``list`` of ``str``
    '''
    conn = _get_driver(profile=profile)
    return conn.list_protocols()


def create_balancer(name, port, protocol, profile, algorithm=1, members=[]):
    '''
    Create a new load balancer instance

    :param name: Name of the new load balancer (required)
    :type  name: ``str``

    :param port: Port the load balancer should listen on, defaults to 80
    :type  port: ``str``

    :param protocol: Loadbalancer protocol, defaults to http.
    :type  protocol: ``str``

    :param algorithm: Load balancing algorithm, defaults to ROUND_ROBIN (1).
    :type algorithm: ``int``

    :param profile: The profile key
    :type  profile: ``str``

    :return: The details of the new balancer
    '''
    conn = _get_driver(profile=profile)
    balancer = conn.create_balancer(name, port, protocol, algorithm, [])
    return _simple_balancer(balancer)


def _simple_balancer(balancer):
    return {
        'id' = balancer.id,
        'name' = balancer.name,
        'state' = balancer.state,
        'ip' = balancer.ip,
        'port' = balancer.port,
        'extra' = balancer.extra
    }
