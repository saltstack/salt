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
import salt.utils.compat

log = logging.getLogger(__name__)


def __virtual__():
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)


def state_result(result, message, name, changes=None):
    if changes is None:
        changes = {}
    return {'result': result, 
            'comment': message,
            'name': name,
            'changes': changes}


def balancer_present(name, port, protocol, profile, algorithm=None, members=None):
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

    :param algorithm: Load balancing algorithm, defaults to ROUND_ROBIN. See Algorithm type
        in Libcloud documentation for a full listing.
    :type algorithm: ``str``

    :param members: An optional list of members to create on deployment
    :type  members: ``list`` of ``dict`` (ip, port)
    '''
    balancers = __salt__['libcloud_loadbalancer.list_balancers'](profile)
    match = [z for z in balancers if z['name'] == name]
    if len(match) > 0:
        return state_result(True, "Balancer already exists", name)
    else:
        starting_members = None
        if members is not None:
            starting_members = []
            for m in members:
                starting_members.append(Member(id=None, ip=m['ip'], port=m['port']))
        balancer = __salt__['libcloud_loadbalancer.create_balancer'](
            name, port, protocol,
            profile, algorithm=algorithm,
            members=starting_members)
        return state_result(True, "Created new load balancer", name, balancer)


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
        return state_result(True, "Balancer already absent", name)
    else:
        result = __salt__['libcloud_loadbalancer.delete_balancer'](match['id'], profile)
        return state_result(result, "Deleted load balancer", name)


def member_present(ip, port, balancer_id, profile):
    '''
    Ensure a load balancer member is present

    :param ip: IP address for the new member
    :type  ip: ``str``

    :param port: Port for the new member
    :type  port: ``int``

    :param balancer_id: id of a load balancer you want to attach the member to
    :type  balancer_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``
    '''
    existing_members = __salt__['libcloud_loadbalancer.list_balancer_members'](balancer_id, profile)
    for member in existing_members:
        if member['ip'] == ip and member['port'] == port:
            return state_result(True, "Member already present", balancer_id)
    member = __salt__['libcloud_loadbalancer.balancer_attach_member'](balancer_id, ip, port, profile)
    return state_result(True, "Member added to balancer, id: {0}".format(member['id']), balancer_id, member)


def member_absent(ip, port, balancer_id, profile):
    '''
    Ensure a load balancer member is absent, based on IP and Port

    :param ip: IP address for the member
    :type  ip: ``str``

    :param port: Port for the member
    :type  port: ``int``

    :param balancer_id: id of a load balancer you want to detach the member from
    :type  balancer_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``
    '''
    existing_members = __salt__['libcloud_loadbalancer.list_balancer_members'](balancer_id, profile)
    for member in existing_members:
        if member['ip'] == ip and member['port'] == port:
            result = __salt__['libcloud_loadbalancer.balancer_detach_member'](balancer_id, member['id'], profile)
            return state_result(result, "Member removed", balancer_id)
    return state_result(True, "Member already absent", balancer_id)
