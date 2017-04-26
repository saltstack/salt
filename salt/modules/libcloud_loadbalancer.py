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
import salt.ext.six as six
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)

# Import third party libs
REQUIRED_LIBCLOUD_VERSION = '1.5.0'
try:
    #pylint: disable=unused-import
    import libcloud
    from libcloud.loadbalancer.providers import get_driver
    from libcloud.loadbalancer.base import Member, Algorithm
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


def _algorithm_maps():
    return {
        'RANDOM': Algorithm.RANDOM,
        'ROUND_ROBIN': Algorithm.ROUND_ROBIN,
        'LEAST_CONNECTIONS': Algorithm.LEAST_CONNECTIONS,
        'WEIGHTED_ROUND_ROBIN': Algorithm.WEIGHTED_ROUND_ROBIN,
        'WEIGHTED_LEAST_CONNECTIONS': Algorithm.WEIGHTED_LEAST_CONNECTIONS,
        'SHORTEST_RESPONSE': Algorithm.SHORTEST_RESPONSE,
        'PERSISTENT_IP': Algorithm.PERSISTENT_IP
    }


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


def list_balancers(profile, **libcloud_kwargs):
    '''
    Return a list of load balancers.

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_balancers method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.list_balancers profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    balancers = conn.list_balancers(**libcloud_kwargs)
    ret = []
    for balancer in balancers:
        ret.append(_simple_balancer(balancer))
    return ret


def list_protocols(profile, **libcloud_kwargs):
    '''
    Return a list of supported protocols.

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_protocols method
    :type  libcloud_kwargs: ``dict``

    :return: a list of supported protocols
    :rtype: ``list`` of ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.list_protocols profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    return conn.list_protocols(**libcloud_kwargs)


def create_balancer(name, port, protocol, profile, algorithm=None, members=None, **libcloud_kwargs):
    '''
    Create a new load balancer instance

    :param name: Name of the new load balancer (required)
    :type  name: ``str``

    :param port: Port the load balancer should listen on, defaults to 80
    :type  port: ``str``

    :param protocol: Loadbalancer protocol, defaults to http.
    :type  protocol: ``str``

    :param algorithm: Load balancing algorithm, defaults to ROUND_ROBIN. See Algorithm type
        in Libcloud documentation for a full listing.
    :type algorithm: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's create_balancer method
    :type  libcloud_kwargs: ``dict``

    :return: The details of the new balancer

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.create_balancer my_balancer 80 http profile1
    '''
    if algorithm is None:
        algorithm = Algorithm.ROUND_ROBIN
    else:
        if isinstance(algorithm, six.string_types):
            algorithm = _algorithm_maps()[algorithm]
    if members is None:
        members = []

    _sanitize_kwargs(libcloud_kwargs)
    conn = _get_driver(profile=profile)
    balancer = conn.create_balancer(name, port, protocol, algorithm, members, **libcloud_kwargs)
    return _simple_balancer(balancer)


def destroy_balancer(balancer_id, profile, **libcloud_kwargs):
    '''
    Destroy a load balancer

    :param balancer_id: LoadBalancer ID which should be used
    :type  balancer_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's destroy_balancer method
    :type  libcloud_kwargs: ``dict``

    :return: ``True`` if the destroy was successful, otherwise ``False``.
    :rtype: ``bool``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.destroy_balancer balancer_1 profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    balancer = conn.get_balancer(balancer_id)
    return conn.destroy_balancer(balancer, **libcloud_kwargs)


def get_balancer_by_name(name, profile, **libcloud_kwargs):
    '''
    Get the details for a load balancer by name

    :param name: Name of a load balancer you want to fetch
    :type  name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_balancers method
    :type  libcloud_kwargs: ``dict``

    :return: the load balancer details

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.get_balancer_by_name my_balancer profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    balancers = conn.list_balancers(**libcloud_kwargs)
    match = [b for b in balancers if b.name == name]
    if len(match) == 1:
        return _simple_balancer(match[0])
    elif len(match) > 1:
        raise ValueError("Ambiguous argument, found mulitple records")
    else:
        raise ValueError("Bad argument, found no records")


def get_balancer(balancer_id, profile, **libcloud_kwargs):
    '''
    Get the details for a load balancer by ID

    :param balancer_id: id of a load balancer you want to fetch
    :type  balancer_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's get_balancer method
    :type  libcloud_kwargs: ``dict``

    :return: the load balancer details

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.get_balancer balancer123 profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    balancer = conn.get_balancer(balancer_id, **libcloud_kwargs)
    return _simple_balancer(balancer)


def list_supported_algorithms(profile, **libcloud_kwargs):
    '''
    Get the supported algorithms for a profile

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_supported_algorithms method
    :type  libcloud_kwargs: ``dict``

    :return: The supported algorithms

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.list_supported_algorithms profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    return conn.list_supported_algorithms(**libcloud_kwargs)


def balancer_attach_member(balancer_id, ip, port, profile, extra=None, **libcloud_kwargs):
    '''
    Add a new member to the load balancer

    :param balancer_id: id of a load balancer you want to fetch
    :type  balancer_id: ``str``

    :param ip: IP address for the new member
    :type  ip: ``str``

    :param port: Port for the new member
    :type  port: ``int``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's balancer_attach_member method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.balancer_attach_member balancer123 1.2.3.4 80 profile1
    '''
    conn = _get_driver(profile=profile)
    _sanitize_kwargs(libcloud_kwargs)
    member = Member(id=None, ip=ip, port=port, balancer=None, extra=extra)
    balancer = conn.get_balancer(balancer_id)
    member_saved = conn.balancer_attach_member(balancer, member, **libcloud_kwargs)
    return _simple_member(member_saved)


def balancer_detach_member(balancer_id, member_id, profile, **libcloud_kwargs):
    '''
    Add a new member to the load balancer

    :param balancer_id: id of a load balancer you want to fetch
    :type  balancer_id: ``str``

    :param ip: IP address for the new member
    :type  ip: ``str``

    :param port: Port for the new member
    :type  port: ``int``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's balancer_detach_member method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.balancer_detach_member balancer123 member123 profile1
    '''
    conn = _get_driver(profile=profile)
    balancer = conn.get_balancer(balancer_id)
    members = conn.balancer_list_members(balancer=balancer)
    match = [member for member in members if member.id == member_id]
    if len(match) > 1:
        raise ValueError("Ambiguous argument, found mulitple records")
    elif len(match) == 0:
        raise ValueError("Bad argument, found no records")
    else:
        member = match[0]
    _sanitize_kwargs(libcloud_kwargs)
    return conn.balancer_detach_member(balancer=balancer, member=member, **libcloud_kwargs)


def list_balancer_members(balancer_id, profile, **libcloud_kwargs):
    '''
    List the members of a load balancer

    :param balancer_id: id of a load balancer you want to fetch
    :type  balancer_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_balancer_members method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.list_balancer_members balancer123 profile1
    '''
    conn = _get_driver(profile=profile)
    balancer = conn.get_balancer(balancer_id)
    _sanitize_kwargs(libcloud_kwargs)
    members = conn.balancer_list_members(balancer=balancer, **libcloud_kwargs)
    return [_simple_member(member) for member in members]


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


def _sanitize_kwargs(kwargs):
    '''
    Remove internal arguments from the command line keyword listing

    :param kwargs: The keyword argument dictionary
    :type  kwargs: ``dict``
    '''
    clean = {}
    for key, val in kwargs.items():
        if key.startswith('__'):
            del kwargs[key]
    return kwargs
