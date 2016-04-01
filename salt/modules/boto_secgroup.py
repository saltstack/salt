# -*- coding: utf-8 -*-
'''
Connection module for Amazon Security Groups

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit ec2 credentials but can
    also utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        secgroup.keyid: GKTADJGHEIQSXMKKRBJ08H
        secgroup.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        secgroup.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

from __future__ import absolute_import

# Import Python libs
import logging
import re
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module
import salt.ext.six as six
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

# Import third party libs
try:
    # pylint: disable=unused-import
    import boto
    import boto.ec2
    # pylint: enable=unused-import
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

import salt.utils.odict as odict


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    required_boto_version = '2.4.0'
    # Boto < 2.4.0 GroupOrCIDR objects have different attributes than
    # Boto >= 2.4.0 GroupOrCIDR objects
    # Differences include no group_id attribute in Boto < 2.4.0 and returning
    # a groupId attribute when a GroupOrCIDR object authorizes an IP range
    # Support for Boto < 2.4.0 can be added if needed
    if not HAS_BOTO:
        return False
    elif _LooseVersion(boto.__version__) < _LooseVersion(required_boto_version):
        return False
    else:
        __utils__['boto.assign_funcs'](__name__, 'ec2', pack=__salt__)
        return True


def exists(name=None, region=None, key=None, keyid=None, profile=None,
           vpc_id=None, vpc_name=None, group_id=None):
    '''
    Check to see if a security group exists.

    CLI example::

        salt myminion boto_secgroup.exists mysecgroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    group = _get_group(conn, name, vpc_id, vpc_name, group_id, region, key, keyid, profile)
    if group:
        return True
    else:
        return False


def _check_vpc(vpc_id, vpc_name, region, key, keyid, profile):
    data = __salt__['boto_vpc.get_id'](name=vpc_name, region=region,
                                       key=key, keyid=keyid, profile=profile)
    try:
        return data.get('id')
    except TypeError:
        return None
    except KeyError:
        return None


def _split_rules(rules):
    '''
    Split rules with combined grants into individual rules.

    Amazon returns a set of rules with the same protocol, from and to ports
    together as a single rule with a set of grants. Authorizing and revoking
    rules, however, is done as a split set of rules. This function splits the
    rules up.
    '''
    split = []
    for rule in rules:
        ip_protocol = rule.get('ip_protocol')
        to_port = rule.get('to_port')
        from_port = rule.get('from_port')
        grants = rule.get('grants')
        for grant in grants:
            _rule = {'ip_protocol': ip_protocol,
                     'to_port': to_port,
                     'from_port': from_port}
            for key, val in six.iteritems(grant):
                _rule[key] = val
            split.append(_rule)
    return split


def _get_group(conn=None, name=None, vpc_id=None, vpc_name=None, group_id=None,
               region=None, key=None, keyid=None, profile=None):  # pylint: disable=W0613
    '''
    Get a group object given a name, name and vpc_id/vpc_name or group_id. Return
    a boto.ec2.securitygroup.SecurityGroup object if the group is found, else
    return None.
    '''
    if vpc_name and vpc_id:
        raise SaltInvocationError('The params \'vpc_id\' and \'vpc_name\' '
                                  'are mutually exclusive.')

    if not vpc_id and vpc_name:
        try:
            vpc_id = _check_vpc(vpc_id, vpc_name, region, key, keyid, profile)
        except boto.exception.BotoServerError as e:
            log.debug(e)
            return None

    if name:
        if vpc_id is None:
            log.debug('getting group for {0}'.format(name))
            group_filter = {'group-name': name}
            filtered_groups = conn.get_all_security_groups(filters=group_filter)
            # security groups can have the same name if groups exist in both
            # EC2-Classic and EC2-VPC
            # iterate through groups to ensure we return the EC2-Classic
            # security group
            for group in filtered_groups:
                # a group in EC2-Classic will have vpc_id set to None
                if group.vpc_id is None:
                    return group
            # If there are more security groups, and no vpc_id, we can't know which one to choose.
            if len(filtered_groups) > 1:
                raise Exception('Security group belongs to more VPCs, specify the VPC ID!')
            elif len(filtered_groups) == 1:
                return filtered_groups[0]
            return None
        elif vpc_id:
            log.debug('getting group for {0} in vpc_id {1}'.format(name, vpc_id))
            group_filter = {'group-name': name, 'vpc_id': vpc_id}
            filtered_groups = conn.get_all_security_groups(filters=group_filter)
            if len(filtered_groups) == 1:
                return filtered_groups[0]
            else:
                return None
        else:
            return None
    elif group_id:
        try:
            groups = conn.get_all_security_groups(group_ids=[group_id])
        except boto.exception.BotoServerError as e:
            log.debug(e)
            return None
        if len(groups) == 1:
            return groups[0]
        else:
            return None
    else:
        return None


def _parse_rules(sg, rules):
    _rules = []
    for rule in rules:
        log.debug('examining rule {0} for group {1}'.format(rule, sg.id))
        attrs = ['ip_protocol', 'from_port', 'to_port', 'grants']
        _rule = odict.OrderedDict()
        for attr in attrs:
            val = getattr(rule, attr)
            if not val:
                continue
            if attr == 'grants':
                _grants = []
                for grant in val:
                    log.debug('examining grant {0} for'.format(grant))
                    g_attrs = {'name': 'source_group_name',
                               'owner_id': 'source_group_owner_id',
                               'group_id': 'source_group_group_id',
                               'cidr_ip': 'cidr_ip'}
                    _grant = odict.OrderedDict()
                    for g_attr, g_attr_map in six.iteritems(g_attrs):
                        g_val = getattr(grant, g_attr)
                        if not g_val:
                            continue
                        _grant[g_attr_map] = g_val
                    _grants.append(_grant)
                _rule['grants'] = _grants
            elif attr == 'from_port':
                _rule[attr] = int(val)
            elif attr == 'to_port':
                _rule[attr] = int(val)
            else:
                _rule[attr] = val
        _rules.append(_rule)
    return _rules


def get_group_id(name, vpc_id=None, vpc_name=None, region=None, key=None,
                 keyid=None, profile=None):
    '''
    Get a Group ID given a Group Name or Group Name and VPC ID

    CLI example::

        salt myminion boto_secgroup.get_group_id mysecgroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    group = _get_group(conn=conn, name=name, vpc_id=vpc_id, vpc_name=vpc_name,
                       region=region, key=key, keyid=keyid, profile=profile)
    if group:
        return group.id
    else:
        return False


def convert_to_group_ids(groups, vpc_id, vpc_name=None, region=None, key=None,
                         keyid=None, profile=None):
    '''
    Given a list of security groups and a vpc_id, convert_to_group_ids will
    convert all list items in the given list to security group ids.

    CLI example::

        salt myminion boto_secgroup.convert_to_group_ids mysecgroup vpc-89yhh7h
    '''
    log.debug('security group contents {0} pre-conversion'.format(groups))
    group_ids = []
    for group in groups:
        if re.match('sg-.*', group):
            log.debug('group {0} is a group id. get_group_id not called.'
                      .format(group))
            group_ids.append(group)
        else:
            log.debug('calling boto_secgroup.get_group_id for'
                      ' group name {0}'.format(group))
            group_id = get_group_id(group, vpc_id, vpc_name, region, key, keyid, profile)
            log.debug('group name {0} has group id {1}'.format(
                group, group_id)
            )
            group_ids.append(str(group_id))
    log.debug('security group contents {0} post-conversion'.format(group_ids))
    return group_ids


def get_config(name=None, group_id=None, region=None, key=None, keyid=None,
               profile=None, vpc_id=None, vpc_name=None):
    '''
    Get the configuration for a security group.

    CLI example::

        salt myminion boto_secgroup.get_config mysecgroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    sg = _get_group(conn, name, vpc_id, vpc_name, group_id, region, key, keyid, profile)
    if sg:
        ret = odict.OrderedDict()
        ret['name'] = sg.name
        # TODO: add support for vpc_id in return
        # ret['vpc_id'] = sg.vpc_id
        ret['group_id'] = sg.id
        ret['owner_id'] = sg.owner_id
        ret['description'] = sg.description
        # TODO: add support for tags
        _rules = _parse_rules(sg, sg.rules)
        _rules_egress = _parse_rules(sg, sg.rules_egress)
        ret['rules'] = _split_rules(_rules)
        ret['rules_egress'] = _split_rules(_rules_egress)
        return ret
    else:
        return None


def create(name, description, vpc_id=None, vpc_name=None, region=None, key=None,
           keyid=None, profile=None):
    '''
    Create a security group.

    CLI example::

        salt myminion boto_secgroup.create mysecgroup 'My Security Group'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not vpc_id and vpc_name:
        try:
            vpc_id = _check_vpc(vpc_id, vpc_name, region, key, keyid, profile)
        except boto.exception.BotoServerError as e:
            log.debug(e)
            return False

    created = conn.create_security_group(name, description, vpc_id)
    if created:
        log.info('Created security group {0}.'.format(name))
        return True
    else:
        msg = 'Failed to create security group {0}.'.format(name)
        log.error(msg)
        return False


def delete(name=None, group_id=None, region=None, key=None, keyid=None,
           profile=None, vpc_id=None, vpc_name=None):
    '''
    Delete a security group.

    CLI example::

        salt myminion boto_secgroup.delete mysecgroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    group = _get_group(conn, name, vpc_id, vpc_name, group_id, region, key, keyid, profile)
    if group:
        deleted = conn.delete_security_group(group_id=group.id)
        if deleted:
            log.info('Deleted security group {0} with id {1}.'.format(group.name,
                                                                      group.id))
            return True
        else:
            msg = 'Failed to delete security group {0}.'.format(name)
            log.error(msg)
            return False
    else:
        log.debug('Security group not found.')
        return False


def authorize(name=None, source_group_name=None,
              source_group_owner_id=None, ip_protocol=None,
              from_port=None, to_port=None, cidr_ip=None, group_id=None,
              source_group_group_id=None, region=None, key=None, keyid=None,
              profile=None, vpc_id=None, vpc_name=None, egress=False):
    '''
    Add a new rule to an existing security group.

    CLI example::

        salt myminion boto_secgroup.authorize mysecgroup ip_protocol=tcp from_port=80 to_port=80 cidr_ip='['10.0.0.0/8', '192.168.0.0/24']'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    group = _get_group(conn, name, vpc_id, vpc_name, group_id, region, key, keyid, profile)
    if group:
        try:
            added = None
            if not egress:
                added = conn.authorize_security_group(
                    src_security_group_name=source_group_name,
                    src_security_group_owner_id=source_group_owner_id,
                    ip_protocol=ip_protocol, from_port=from_port, to_port=to_port,
                    cidr_ip=cidr_ip, group_id=group.id,
                    src_security_group_group_id=source_group_group_id)
            else:
                added = conn.authorize_security_group_egress(
                    ip_protocol=ip_protocol, from_port=from_port, to_port=to_port,
                    cidr_ip=cidr_ip, group_id=group.id,
                    src_group_id=source_group_group_id)
            if added:
                log.info('Added rule to security group {0} with id {1}'
                         .format(group.name, group.id))
                return True
            else:
                msg = ('Failed to add rule to security group {0} with id {1}.'
                       .format(group.name, group.id))
                log.error(msg)
                return False
        except boto.exception.EC2ResponseError as e:
            msg = ('Failed to add rule to security group {0} with id {1}.'
                   .format(group.name, group.id))
            log.error(msg)
            log.error(e)
            return False
    else:
        log.error('Failed to add rule to security group.')
        return False


def revoke(name=None, source_group_name=None,
           source_group_owner_id=None, ip_protocol=None,
           from_port=None, to_port=None, cidr_ip=None, group_id=None,
           source_group_group_id=None, region=None, key=None, keyid=None,
           profile=None, vpc_id=None, vpc_name=None, egress=False):
    '''
    Remove a rule from an existing security group.

    CLI example::

        salt myminion boto_secgroup.revoke mysecgroup ip_protocol=tcp from_port=80 to_port=80 cidr_ip='10.0.0.0/8'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    group = _get_group(conn, name, vpc_id, vpc_name, group_id, region, key, keyid, profile)
    if group:
        try:
            revoked = None
            if not egress:
                revoked = conn.revoke_security_group(
                    src_security_group_name=source_group_name,
                    src_security_group_owner_id=source_group_owner_id,
                    ip_protocol=ip_protocol, from_port=from_port, to_port=to_port,
                    cidr_ip=cidr_ip, group_id=group.id,
                    src_security_group_group_id=source_group_group_id)
            else:
                revoked = conn.revoke_security_group_egress(
                    ip_protocol=ip_protocol, from_port=from_port, to_port=to_port,
                    cidr_ip=cidr_ip, group_id=group.id,
                    src_group_id=source_group_group_id)

            if revoked:
                log.info('Removed rule from security group {0} with id {1}.'
                         .format(group.name, group.id))
                return True
            else:
                msg = ('Failed to remove rule from security group {0} with id {1}.'
                       .format(group.name, group.id))
                log.error(msg)
                return False
        except boto.exception.EC2ResponseError as e:
            msg = ('Failed to remove rule from security group {0} with id {1}.'
                   .format(group.name, group.id))
            log.error(msg)
            log.error(e)
            return False
    else:
        log.error('Failed to remove rule from security group.')
        return False
