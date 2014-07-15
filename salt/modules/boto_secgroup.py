# -*- coding: utf-8 -*-
'''
Connection module for Amazon Security Groups

.. versionadded:: Helium

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


def _get_group_id(conn, name, vpc_id=None):
    '''
    Given a name or name and vpc_id return a group id or None.
    '''
    logging.debug('getting group_id for {0}'.format(name))
    if vpc_id is None:
        group_filter = {'group-name': name}
        filtered_groups = conn.get_all_security_groups(filters=group_filter)
        # security groups can have the same name if groups exist in both
        # EC2-Classic and EC2-VPC
        # iterate through groups to ensure we return the EC2-Classic
        # security group
        for group in filtered_groups:
            # a group in EC2-Classic will have vpc_id set to None
            if group.vpc_id is None:
                logging.debug("ec2-vpc security group {0} with group_id {1} found."
                              .format(name, filtered_groups[0].id))
                return group.id
        return None
    elif vpc_id:
        group_filter = {'group-name': name, 'vpc_id': vpc_id}
        filtered_groups = conn.get_all_security_groups(filters=group_filter)
        if len(filtered_groups) == 1:
            logging.debug("ec2-vpc security group {0} with group_id {1} found."
                          .format(name, filtered_groups[0].id))
            return filtered_groups[0].id
        else:
            return None
    else:
        return None


def _exists_group_id(conn, group_id):
    '''
    Given a group id check to see if the security group exists
    '''
    logging.debug('ec2-vpc security group lookup by group_id')
    group_filter = {'group-id': group_id}
    filtered_groups = conn.get_all_security_groups(filters=group_filter)
    if len(filtered_groups) == 1:
        return True
    else:
        return False


def exists(name=None, group_id=None, vpc_id=None, region=None, key=None, keyid=None,
           profile=None):
    '''
    Check to see if a security group exists.

    CLI examples::

        salt myminion boto_secgroup.exists name=mysecgroup
        or
        salt myminion boto_secgroup.exists name=mysecgroup vpc_id=vpc-1476ae71
        or
        salt myminion boto_secgroup.exists group_id=sg-3269ae58

    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        if name:
            group_id = _get_group_id(conn, name, vpc_id)
        if group_id:
            return _exists_group_id(conn, group_id)
        else:
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
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


def get_config(name=None, group_id=None, vpc_id=None, region=None, key=None,
               keyid=None, profile=None):
    '''
    Get the configuration for a security group.

    CLI examples::

        salt myminion boto_secgroup.get_config mysecgroup
        or
        salt myminion boto_secgroup.get_config mysecgroup vpc_id=vpc-1476ae71
        or
        salt myminion boto_secgroup.get_config group_id=sg-3269ae58

    '''
    # if name or security group does not exist or an error occurs, return None
    # if an error occurs, return {}
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return None
    if not (name or group_id):
        return None
    try:
        sg = None
        if name:
            group_id = _get_group_id(conn, name, vpc_id)
        if group_id:
            group_filter = {'group-id': group_id}
            filtered_groups = conn.get_all_security_groups(filters=group_filter)
            if len(filtered_groups) == 1:
                sg = filtered_groups[0]
        if sg is None:
            return {}
    except boto.exception.BotoServerError as e:
        msg = 'Failed to get config for security group {0}.'.format(name)
        log.error(msg)
        log.debug(e)
        return {}
    ret = odict.OrderedDict()
    ret['name'] = sg.name
    ret['group_id'] = sg.id
    ret['owner_id'] = sg.owner_id
    ret['description'] = sg.description
    # TODO: add support for tags
    _rules = []
    for rule in sg.rules:
        attrs = ['ip_protocol', 'from_port', 'to_port', 'grants']
        _rule = odict.OrderedDict()
        for attr in attrs:
            val = getattr(rule, attr)
            if not val:
                continue
            if attr == 'grants':
                _grants = []
                for grant in val:
                    g_attrs = {'name': 'source_group_name',
                               'owner_id': 'source_group_owner_id',
                               'group_id': 'source_group_group_id',
                               'cidr_ip': 'cidr_ip'}
                    _grant = odict.OrderedDict()
                    for g_attr, g_attr_map in g_attrs.iteritems():
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


def create(name, description, vpc_id=None, region=None, key=None, keyid=None,
           profile=None):
    '''
    Create an autoscale group.

    CLI examples::

        salt myminion boto_secgroup.create mysecgroup 'My Security Group'
        or
        salt myminion boto_secgroup.create mysecgroup 'My Security Group' vpc_id=vpc-1476ae71
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        created = conn.create_security_group(name, description, vpc_id)
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False
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

    CLI examples::

        salt myminion boto_secgroup.delete mysecgroup
        or
        salt myminion boto_secgroup.delete mysecgroup vpc_id=vpc-1476ae71
        or
        salt myminion boto_secgroup.delete group_id=sg-3269ae58
    '''
    conn = _get_conn(region, key, keyid, profile)

    if not conn:
        return False
    if name:
        group_id = _get_group_id(conn, name, vpc_id)
        log.info('security group {0} has group_id {1}.'.format(name, group_id))
    if group_id:
        try:
            deleted = conn.delete_security_group(group_id=group_id)
        except boto.exception.BotoServerError as e:
            log.debug(e)
            return False
    else:
        deleted = False
    if deleted:
        log.info('Deleted security group {0}.'.format(group_id))
        return True
    else:
        msg = 'Failed to delete security group {0}.'.format(group_id)
        log.error(msg)
        return False


def authorize(name=None, source_group_name=None,
              source_group_owner_id=None, ip_protocol=None,
              from_port=None, to_port=None, cidr_ip=None, group_id=None,
              source_group_group_id=None, region=None, key=None,
              keyid=None, profile=None, vpc_id=None):
    '''
    Add a new rule to an existing security group.

    CLI examples::

        salt myminion boto_secgroup.authorize mysecgroup ip_protocol=tcp from_port=80 to_port=80 cidr_ip='['10.0.0.0/8', '192.168.0.0/24']'
        or
        salt myminion boto_secgroup.authorize mysecgroup vpc_id=vpc-1476ae71 ip_protocol=tcp from_port=80 to_port=80 cidr_ip='['10.0.0.0/8', '192.168.0.0/24']'
        or
        salt myminion boto_secgroup.authorize group_id=sg-3269ae58 ip_protocol=tcp from_port=80 to_port=80 cidr_ip='['10.0.0.0/8', '192.168.0.0/24']'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        if name:
            group_id = _get_group_id(conn, name, vpc_id)
            log.info('security group {0} has group_id {1}.'.format(name, group_id))
        added = conn.authorize_security_group(
            src_security_group_name=source_group_name,
            src_security_group_owner_id=source_group_owner_id,
            ip_protocol=ip_protocol, from_port=from_port, to_port=to_port,
            cidr_ip=cidr_ip, group_id=group_id,
            src_security_group_group_id=source_group_group_id)
        if added:
            log.info('Added rule to security group {0}.'.format(group_id))
            return True
    except boto.exception.EC2ResponseError as e:
        log.debug(e)
        msg = 'Failed to add rule to security group {0}.'.format(group_id)
        log.error(msg)
        return False


def revoke(name=None, source_group_name=None,
           source_group_owner_id=None, ip_protocol=None,
           from_port=None, to_port=None, cidr_ip=None, group_id=None,
           source_group_group_id=None, region=None, key=None,
           keyid=None, profile=None, vpc_id=None):
    '''
    Remove a rule from an existing security group.

    CLI examples::

        salt myminion boto_secgroup.revoke mysecgroup ip_protocol=tcp from_port=80 to_port=80 cidr_ip='10.0.0.0/8'
        or
        salt myminion boto_secgroup.revoke mysecgroup vpc_id=vpc-1476ae71 ip_protocol=tcp from_port=80 to_port=80 cidr_ip='10.0.0.0/8'
        or
        salt myminion boto_secgroup.revoke group_id=sg-3269ae58 ip_protocol=tcp from_port=80 to_port=80 cidr_ip='10.0.0.0/8'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        if name:
            group_id = _get_group_id(conn, name, vpc_id)
            log.info('security group {0} has group_id {1}.'.format(name, group_id))
        revoked = conn.revoke_security_group(
            src_security_group_name=source_group_name,
            src_security_group_owner_id=source_group_owner_id,
            ip_protocol=ip_protocol, from_port=from_port, to_port=to_port,
            cidr_ip=cidr_ip, group_id=group_id,
            src_security_group_group_id=source_group_group_id)
        if revoked:
            log.info('Removed rule from security group {0}.'.format(group_id))
            return True
    except boto.exception.EC2ResponseError as e:
        log.debug(e)
        msg = 'Failed to remove rule from security group {0}.'.format(group_id)
        log.error(msg)
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
