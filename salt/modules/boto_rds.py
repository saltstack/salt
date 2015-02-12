# -*- coding: utf-8 -*-
'''
Connection module for Amazon RDS

.. versionadded:: 2014.7.1

:configuration: This module accepts explicit rds credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        rds.keyid: GKTADJGHEIQSXMKKRBJ08H
        rds.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        rds.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
'''
from __future__ import absolute_import

# Import Python libs
import logging
import json
import salt.ext.six as six
from salt.ext.six import string_types
import salt.utils.odict as odict

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.rds2
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True


def exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an RDS exists.

    CLI example::

        salt myminion boto_rds.exists myrds region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        rds = conn.describe_db_instances(db_instance_identifier=name)
        if rds:
            return True
        else:
            msg = 'Rds instance does not exist in region {0}'.format(region)
            log.debug(msg)
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def exists_option_group(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an RDS option group exists.

    CLI example::

        salt myminion boto_rds.exists_option_group myoptiongr region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        rds = conn.describe_option_groups(option_group_name=name)
        if rds:
            return True
        else:
            msg = 'Rds option group does not exist in region {}'.format(region)
            log.debug(msg)
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def exists_parameter_group(name, region=None, key=None, keyid=None,
                           profile=None):
    '''
    Check to see if an RDS parameter group exists.

    CLI example::

        salt myminion boto_rds.exists_parameter_group myparametergroup \
                region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        rds = conn.describe_db_parameter_groups(db_parameter_group_name=name)
        if rds:
            return True
        else:
            msg = ('Rds parameter group does not exist in'
                   'region {0}'.format(region))
            log.debug(msg)
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def exists_subnet_group(name, region=None, key=None, keyid=None,
                        profile=None):
    '''
    Check to see if an RDS subnet group exists.

    CLI example::

        salt myminion boto_rds.exists_subnet_group my-param-group \
                region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        rds = conn.describe_db_subnet_groups(db_subnet_group_name=name)
        if rds:
            return True
        else:
            msg = ('Rds subnet group does not exist in'
                   'region {0}'.format(region))
            log.debug(msg)
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def create(name, allocated_storage, db_instance_class,
           engine, master_username, master_user_password, region=None,
           key=None, keyid=None, profile=None, db_name=None,
           db_security_groups=None, vpc_security_group_ids=None,
           availability_zone=None, db_subnet_group_name=None,
           preferred_maintenance_window=None, db_parameter_group_name=None,
           backup_retention_period=None, preferred_backup_window=None,
           port=None, multi_az=None, engine_version=None,
           auto_minor_version_upgrade=None, license_model=None, iops=None,
           option_group_name=None, character_set_name=None,
           publicly_accessible=None, tags=None):
    '''
    Create an RDS

    CLI example to create an RDS::

        salt myminion boto_rds.create myrds 10 db.t2.micro MySQL sqlusr sqlpass
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if __salt__['boto_rds.exists'](name, region, key, keyid, profile):
        return True
    try:
        rds = conn.create_db_instance(name, allocated_storage,
                                      db_instance_class, engine,
                                      master_username, master_user_password,
                                      db_name, db_security_groups,
                                      vpc_security_group_ids,
                                      availability_zone, db_subnet_group_name,
                                      preferred_maintenance_window,
                                      db_parameter_group_name,
                                      backup_retention_period,
                                      preferred_backup_window, port, multi_az,
                                      engine_version,
                                      auto_minor_version_upgrade,
                                      license_model, iops, option_group_name,
                                      character_set_name, publicly_accessible,
                                      tags)
        if rds:
            log.info('Created RDS {0}'.format(name))
            return True
        else:
            msg = 'Failed to create RDS {0}'.format(name)
            log.error(msg)
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create RDS {0}'.format(name)
        log.error(msg)
        return False


def create_option_group(name, engine_name, major_engine_version,
                        option_group_description, tags=None, region=None,
                        key=None, keyid=None, profile=None):
    '''
    Create an RDS option group

    CLI example to create an RDS option group::

        salt myminion boto_rds.create_option_group my-opt-group mysql 5.6 \
                "group description"
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if __salt__['boto_rds.exists_option_group'](name, region, key, keyid,
                                                profile):
        return True
    try:
        rds = conn.create_option_group(name, engine_name,
                                       major_engine_version,
                                       option_group_description, tags)
        if rds:
            log.info('Created RDS option group {0}'.format(name))
            return True
        else:
            msg = 'Failed to create RDS option group {0}'.format(name)
            log.error(msg)
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create RDS option group {0}'.format(name)
        log.error(msg)
        return False


def create_parameter_group(name, db_parameter_group_family, description,
                           tags=None, region=None, key=None, keyid=None,
                           profile=None):
    '''
    Create an RDS parameter group

    CLI example to create an RDS parameter group::

        salt myminion boto_rds.create_parameter_group my-param-group mysql5.6 \
                "group description"
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if __salt__['boto_rds.exists_parameter_group'](name, region, key, keyid,
                                                   profile):
        return True
    try:
        rds = conn.create_db_parameter_group(name, db_parameter_group_family,
                                             description, tags)
        if rds:
            log.info('Created RDS parameter group {0}'.format(name))
            return True
        else:
            msg = 'Failed to create RDS parameter group {0}'.format(name)
            log.error(msg)
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create RDS parameter group {0}'.format(name)
        log.error(msg)
        return False


def create_subnet_group(name, db_subnet_group_description, subnet_ids,
                        tags=None, region=None, key=None, keyid=None,
                        profile=None):
    '''
    Create an RDS subnet group

    CLI example to create an RDS subnet group::

        salt myminion boto_rds.create_subnet_group my-subnet-group \
            "group description" '[subnet-12345678, subnet-87654321]' \
            region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if __salt__['boto_rds.exists_subnet_group'](name, region, key, keyid,
                                                profile):
        return True
    try:
        rds = conn.create_db_subnet_group(name, db_subnet_group_description,
                                          subnet_ids, tags)
        if rds:
            log.info('Created RDS subnet group {0}'.format(name))
            return True
        else:
            msg = 'Failed to create RDS subnet group {0}'.format(name)
            log.error(msg)
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create RDS subnet group {0}'.format(name)
        log.error(msg)
        return False


def update_parameter_group(name, parameters, apply_method="pending-reboot",
                           region=None, key=None, keyid=None, profile=None):
    '''
    Update an RDS parameter group.

    CLI example::

        salt myminion boto_rds.update_parameter_group my-param-group \
                parameters='{"back_log":1, "binlog_cache_size":4096}' \
                region=us-east-1
    '''

    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if not __salt__['boto_rds.exists_parameter_group'](name, region, key,
                                                       keyid, profile):
        return False
    param_list = []
    for key, value in parameters.iteritems():
        item = (key, value, apply_method)
        param_list.append(item)
        if not len(param_list):
            return False
    try:
        conn.modify_db_parameter_group(name, param_list)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to update RDS parameter group {0}'.format(name)
        log.error(msg)
        return False


def delete(name, skip_final_snapshot=None, final_db_snapshot_identifier=None,
           region=None, key=None, keyid=None, profile=None):
    '''
    Delete an RDS instance.

    CLI example::

        salt myminion boto_rds.delete myrds skip_final_snapshot=True \
                region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.delete_db_instance(name, skip_final_snapshot,
                                final_db_snapshot_identifier)
        msg = 'Deleted RDS instance {0}.'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete RDS instance {0}'.format(name)
        log.error(msg)
        return False


def delete_option_group(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete an RDS option group.

    CLI example::

        salt myminion boto_rds.delete_option_group my-opt-group \
                region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.delete_option_group(name)
        msg = 'Deleted RDS option group {0}.'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete RDS option group {0}'.format(name)
        log.error(msg)
        return False


def delete_parameter_group(name, region=None, key=None, keyid=None,
                           profile=None):
    '''
    Delete an RDS parameter group.

    CLI example::

        salt myminion boto_rds.delete_parameter_group my-param-group \
                region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.delete_db_parameter_group(name)
        msg = 'Deleted RDS parameter group {0}.'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete RDS parameter group {0}'.format(name)
        log.error(msg)
        return False


def delete_subnet_group(name, region=None, key=None, keyid=None,
                        profile=None):
    '''
    Delete an RDS subnet group.

    CLI example::

        salt myminion boto_rds.delete_subnet_group my-subnet-group \
                region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.delete_db_subnet_group(name)
        msg = 'Deleted RDS subnet group {0}.'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete RDS subnet group {0}'.format(name)
        log.error(msg)
        return False


def _get_conn(region, key, keyid, profile):
    '''
    Get a boto connection to RDS.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('rds.region'):
        region = __salt__['config.option']('rds.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('rds.key'):
        key = __salt__['config.option']('rds.key')
    if not keyid and __salt__['config.option']('rds.keyid'):
        keyid = __salt__['config.option']('rds.keyid')

    try:
        conn = boto.rds2.connect_to_region(region, aws_access_key_id=keyid,
                                           aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make boto rds connection.')
        return None
    return conn
