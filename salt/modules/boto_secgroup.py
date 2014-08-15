# -*- coding: utf-8 -*-
'''
Connection module for Amazon Security Groups

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit ec2 credentials but can
    also utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        secgroup.keyid: GKTADJGHEIQSXMKKRBJ08H
        secgroup.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        secgroup.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
'''

# Import Python libs
import logging

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.ec2
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from salt._compat import string_types
import salt.utils.odict as odict


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True


def exists(name=None, region=None, key=None, keyid=None, profile=None,
           vpc_id=None, group_id=None):
    '''
    Check to see if an security group exists.

    CLI example::

        salt myminion boto_secgroup.exists mysecgroup
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    group = _get_group(conn, name, vpc_id, group_id)
    if group:
        return True
    else:
        return False


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
            for key, val in grant.iteritems():
                _rule[key] = val
            split.append(_rule)
    return split


def _get_group(conn, name=None, vpc_id=None, group_id=None, region=None):
    '''
    Get a group object given a name, name and vpc_id or group_id. Return a
    boto.ec2.securitygroup.SecurityGroup object if the group is found, else
    return None.
    '''
    if name:
        if vpc_id is None:
            logging.debug('getting group for {0}'.format(name))
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
            return None
        elif vpc_id:
            logging.debug('getting group for {0} in vpc_id {1}'.format(name, vpc_id))
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


def get_group_id(name, vpc_id=None, region=None, key=None, keyid=None, profile=None):
    '''
    Get a Group ID given a Group Name or Group Name and VPC ID

    CLI example::

        salt myminion boto_secgroup.get_group_id mysecgroup
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    group = _get_group(conn, name, vpc_id)
    if group:
        return group.id
    else:
        return False


def get_config(name=None, group_id=None, region=None, key=None, keyid=None,
               profile=None, vpc_id=None):
    '''
    Get the configuration for a security group.

    CLI example::

        salt myminion boto_secgroup.get_config mysecgroup
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return None
    sg = _get_group(conn, name, vpc_id, group_id)
    if sg:
        ret = odict.OrderedDict()
        ret['name'] = sg.name
        # TODO: add support for vpc_id in return
        # ret['vpc_id'] = sg.vpc_id
        ret['group_id'] = sg.id
        ret['owner_id'] = sg.owner_id
        ret['description'] = sg.description
        # TODO: add support for tags
        _rules = []
        for rule in sg.rules:
            logging.debug('examining rule {0} for group {1}'.format(rule, sg.id))
            attrs = ['ip_protocol', 'from_port', 'to_port', 'grants']
            _rule = odict.OrderedDict()
            for attr in attrs:
                val = getattr(rule, attr)
                if not val:
                    continue
                if attr == 'grants':
                    _grants = []
                    for grant in val:
                        logging.debug('examining grant {0} for'.format(grant))
                        # reason for using both groupId and group_id
                        # the GroupOrCIDR object in versions of
                        # Boto < 2.4.0 has a groupId attribute but no group_id
                        # attribute
                        g_attrs = {'name': 'source_group_name',
                                   'owner_id': 'source_group_owner_id',
                                   'groupId': 'source_group_group_id',
                                   'group_id': 'source_group_group_id',
                                   'cidr_ip': 'cidr_ip'}
                        _grant = odict.OrderedDict()
                        for g_attr, g_attr_map in g_attrs.iteritems():
                            # hasattr used to check for availability of
                            # attribute prior to getattr()
                            # the GroupOrCIDR object in versions of
                            # Boto < 2.4.0 do not have a group_id attribute
                            if hasattr(grant, g_attr):
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
        ret['rules'] = _split_rules(_rules)
        return ret
    else:
        return None


def create(name, description, vpc_id=None, region=None, key=None, keyid=None,
           profile=None):
    '''
    Create an autoscale group.

    CLI example::

        salt myminion boto_secgroup.create mysecgroup 'My Security Group'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
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
           profile=None, vpc_id=None):
    '''
    Delete an autoscale group.

    CLI example::

        salt myminion boto_secgroup.delete mysecgroup
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    group = _get_group(conn, name, vpc_id, group_id)
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
              source_group_group_id=None, region=None, key=None,
              keyid=None, profile=None, vpc_id=None):
    '''
    Add a new rule to an existing security group.

    CLI example::

        salt myminion boto_secgroup.authorize mysecgroup ip_protocol=tcp from_port=80 to_port=80 cidr_ip='['10.0.0.0/8', '192.168.0.0/24']'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    group = _get_group(conn, name, vpc_id, group_id)
    if group:
        try:
            added = conn.authorize_security_group(
                src_security_group_name=source_group_name,
                src_security_group_owner_id=source_group_owner_id,
                ip_protocol=ip_protocol, from_port=from_port, to_port=to_port,
                cidr_ip=cidr_ip, group_id=group.id,
                src_security_group_group_id=source_group_group_id)
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
            log.debug(e)
            msg = ('Failed to add rule to security group {0} with id {1}.'
                   .format(group.name, group.id))
            log.error(msg)
            return False
    else:
        log.debug('Failed to add rule to security group.')
        return False


def revoke(name=None, source_group_name=None,
           source_group_owner_id=None, ip_protocol=None,
           from_port=None, to_port=None, cidr_ip=None, group_id=None,
           source_group_group_id=None, region=None, key=None,
           keyid=None, profile=None, vpc_id=None):
    '''
    Remove a rule from an existing security group.

    CLI example::

        salt myminion boto_secgroup.revoke mysecgroup ip_protocol=tcp from_port=80 to_port=80 cidr_ip='10.0.0.0/8'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    group = _get_group(conn, name, vpc_id, group_id)
    if group:
        try:
            revoked = conn.revoke_security_group(
                src_security_group_name=source_group_name,
                src_security_group_owner_id=source_group_owner_id,
                ip_protocol=ip_protocol, from_port=from_port, to_port=to_port,
                cidr_ip=cidr_ip, group_id=group.id,
                src_security_group_group_id=source_group_group_id)
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
            log.debug(e)
            msg = ('Failed to remove rule from security group {0} with id {1}.'
                   .format(group.name, group.id))
            log.error(msg)
            return False
    else:
        log.debug('Failed to remove rule from security group.')
        return False


def _get_conn(region, key, keyid, profile):
    '''
    Get a boto connection to ec2.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('secgroup.region'):
        region = __salt__['config.option']('secgroup.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('secgroup.key'):
        key = __salt__['config.option']('secgroup.key')
    if not keyid and __salt__['config.option']('secgroup.keyid'):
        keyid = __salt__['config.option']('secgroup.keyid')

    try:
        conn = boto.ec2.connect_to_region(region, aws_access_key_id=keyid,
                                          aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make ec2 connection for security groups.')
        return None
    return conn
