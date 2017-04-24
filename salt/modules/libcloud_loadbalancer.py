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
    from libcloud.loadbalancer.base import Member
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


def destroy_balancer(balancer_id, profile):
    '''
    Destroy a load balancer

    :param balancer_id: LoadBalancer ID which should be used
    :type  balancer_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :return: ``True`` if the destroy was successful, otherwise ``False``.
    :rtype: ``bool``
    '''
    balancer = get_balancer(balancer_id, profile)
    conn = _get_driver(profile=profile)
    return conn.destroy_balancer(balancer)


def get_balancer_by_name(name, profile):
    '''
    Get the details for a load balancer by name

    :param name: Name of a load balancer you want to fetch
    :type  name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :return: the load balancer details
    '''
    conn = _get_driver(profile=profile)
    balancers = conn.list_balancers()
    match = [b for b in balancers if b.name == name]
    if len(match) == 1:
        return _simple_balancer(balancer)
    elif len(match) > 1:
        raise ValueError("Ambiguous argument, found mulitple records")
    else:
        raise ValueError("Bad argument, found no records")


def get_balancer(balancer_id, profile):
    '''
    Get the details for a load balancer by ID

    :param balancer_id: id of a load balancer you want to fetch
    :type  balancer_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :return: the load balancer details
    '''
    conn = _get_driver(profile=profile)
    balancer = conn.get_balancer(balancer_id)
    return _simple_balancer(balancer)


def list_supported_algorithms(profile):
    '''
    Get the supported algorithms for a profile

    :param profile: The profile key
    :type  profile: ``str``

    :return: The supported algorithms
    '''
    conn = _get_driver(profile=profile)
    return conn.list_supported_algorithms()


def balancer_attach_member(balancer_id, ip, port, profile):
    pass


def balancer_detach_member(balancer_id, member_id, profile):
    pass


def list_balancer_members(balancer, profile):
    pass

def _simple_balancer(balancer):
    return {
        'id': balancer.id,
        'name': balancer.name,
        'state': balancer.state,
        'ip': balancer.ip,
        'port': balancer.port,
        'extra': balancer.extra
    }


def _simple_member(member):
    return {
        'id': member.id,
        'ip': member.ip,
        'port': member.port,
        'balancer': _simple_balancer(member.balancer),
        'extra': member.extra
    }