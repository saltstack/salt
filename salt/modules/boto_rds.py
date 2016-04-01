# -*- coding: utf-8 -*-
'''
Connection module for Amazon RDS

.. versionadded:: 2015.8.0

:configuration: This module accepts explicit rds credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        rds.keyid: GKTADJGHEIQSXMKKRBJ08H
        rds.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        rds.region: us-east-1

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
from salt.exceptions import SaltInvocationError
from time import sleep

log = logging.getLogger(__name__)

# Import third party libs
import salt.ext.six as six
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
    __utils__['boto.assign_funcs'](__name__, 'rds', module='rds2', pack=__salt__)
    return True


def exists(name, tags=None, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an RDS exists.

    CLI example::

        salt myminion boto_rds.exists myrds region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        rds = conn.describe_db_instances(db_instance_identifier=name)
        if not rds:
            msg = 'Rds instance does not exist in region {0}'.format(region)
            log.debug(msg)
            return False
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def option_group_exists(name, tags=None, region=None, key=None, keyid=None,
                        profile=None):
    '''
    Check to see if an RDS option group exists.

    CLI example::

        salt myminion boto_rds.option_group_exists myoptiongr region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        rds = conn.describe_option_groups(option_group_name=name)
        if not rds:
            msg = ('Rds option group does not exist in region '
                   '{0}'.format(region)
                   )
            log.debug(msg)
            return False
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def parameter_group_exists(name, tags=None, region=None, key=None, keyid=None,
                           profile=None):
    '''
    Check to see if an RDS parameter group exists.

    CLI example::

        salt myminion boto_rds.parameter_group_exists myparametergroup \
                region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        rds = conn.describe_db_parameter_groups(db_parameter_group_name=name)
        if not rds:
            msg = ('Rds parameter group does not exist in'
                   'region {0}'.format(region))
            log.debug(msg)
            return False
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def subnet_group_exists(name, tags=None, region=None, key=None, keyid=None,
                        profile=None):
    '''
    Check to see if an RDS subnet group exists.

    CLI example::

        salt myminion boto_rds.subnet_group_exists my-param-group \
                region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        rds = conn.describe_db_subnet_groups(db_subnet_group_name=name)
        if not rds:
            msg = ('Rds subnet group does not exist in'
                   'region {0}'.format(region))
            log.debug(msg)
            return False
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def create(name, allocated_storage, db_instance_class, engine,
           master_username, master_user_password, db_name=None,
           db_security_groups=None, vpc_security_group_ids=None,
           availability_zone=None, db_subnet_group_name=None,
           preferred_maintenance_window=None, db_parameter_group_name=None,
           backup_retention_period=None, preferred_backup_window=None,
           port=None, multi_az=None, engine_version=None,
           auto_minor_version_upgrade=None, license_model=None, iops=None,
           option_group_name=None, character_set_name=None,
           publicly_accessible=None, wait_status=None, tags=None, region=None,
           key=None, keyid=None, profile=None):
    '''
    Create an RDS

    CLI example to create an RDS::

        salt myminion boto_rds.create myrds 10 db.t2.micro MySQL sqlusr sqlpassw
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if __salt__['boto_rds.exists'](name, tags, region, key, keyid, profile):
        return True

    if not allocated_storage:
        raise SaltInvocationError('allocated_storage is required')
    if not db_instance_class:
        raise SaltInvocationError('db_instance_class is required')
    if not engine:
        raise SaltInvocationError('engine is required')
    if not master_username:
        raise SaltInvocationError('master_username is required')
    if not master_user_password:
        raise SaltInvocationError('master_user_password is required')
    if availability_zone and multi_az:
        raise SaltInvocationError('availability_zone and multi_az are mutually'
                                  ' exclusive arguments.')
    if wait_status:
        wait_statuses = ['available', 'modifying', 'backing-up']
        if wait_status not in wait_statuses:
            raise SaltInvocationError('wait_status can be one of: '
                                      '{0}'.format(wait_statuses))
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
                                      license_model, iops,
                                      option_group_name, character_set_name,
                                      publicly_accessible, tags)
        if not rds:
            msg = 'Failed to create RDS {0}'.format(name)
            log.error(msg)
            return False
        if not wait_status:
            log.info('Created RDS {0}'.format(name))
            return True
        while True:
            sleep(10)
            _describe = describe(name, tags, region, key, keyid, profile)
            if not _describe:
                return True
            if _describe['db_instance_status'] in wait_statuses:
                log.info('Created RDS {0} with current status '
                         '{1}'.format(name, _describe['db_instance_status']))
                return True

    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create RDS {0}, reason: {1}'.format(name, e.body)
        log.error(msg)
        return False


def create_read_replica(name, source_name, db_instance_class=None,
                        availability_zone=None, port=None,
                        auto_minor_version_upgrade=None, iops=None,
                        option_group_name=None, publicly_accessible=None,
                        tags=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Create an RDS read replica

    CLI example to create an RDS  read replica::

        salt myminion boto_rds.create_read_replica replicaname source_name
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not __salt__['boto_rds.exists'](source_name, tags, region, key, keyid, profile):
        return False
    if __salt__['boto_rds.exists'](name, tags, region, key, keyid, profile):
        return True
    try:
        rds_replica = conn.create_db_instance_read_replica(name, source_name,
                                                           db_instance_class,
                                                           availability_zone,
                                                           port,
                                                           auto_minor_version_upgrade,
                                                           iops, option_group_name,
                                                           publicly_accessible,
                                                           tags)
        if rds_replica:
            log.info('Created replica {0} from {1}'.format(name, source_name))
            return True
        else:
            msg = 'Failed to create RDS replica {0}'.format(name)
            log.error(msg)
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create RDS replica {0}'.format(name)
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
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if __salt__['boto_rds.option_group_exists'](name, tags, region, key, keyid,
                                                profile):
        return True
    try:
        rds = conn.create_option_group(name, engine_name,
                                       major_engine_version,
                                       option_group_description, tags)
        if not rds:
            msg = 'Failed to create RDS option group {0}'.format(name)
            log.error(msg)
            return False
        log.info('Created RDS option group {0}'.format(name))
        return True
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
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if __salt__['boto_rds.parameter_group_exists'](name, tags, region, key,
                                                   keyid, profile):
        return True
    try:
        rds = conn.create_db_parameter_group(name, db_parameter_group_family,
                                             description, tags)
        if not rds:
            msg = 'Failed to create RDS parameter group {0}'.format(name)
            log.error(msg)
            return False
        log.info('Created RDS parameter group {0}'.format(name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create RDS parameter group {0}'.format(name)
        log.error(msg)
        return False


def create_subnet_group(name, description, subnet_ids, tags=None, region=None, key=None, keyid=None, profile=None):
    '''
    Create an RDS subnet group

    CLI example to create an RDS subnet group::

        salt myminion boto_rds.create_subnet_group my-subnet-group \
            "group description" '[subnet-12345678, subnet-87654321]' \
            region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if __salt__['boto_rds.subnet_group_exists'](name, tags, region, key, keyid,
                                                profile):
        return True
    try:
        rds = conn.create_db_subnet_group(name, description, subnet_ids, tags)
        if not rds:
            msg = 'Failed to create RDS subnet group {0}'.format(name)
            log.error(msg)
            return False
        log.info('Created RDS subnet group {0}'.format(name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create RDS subnet group {0}'.format(name)
        log.error(msg)
        return False


def update_parameter_group(name, parameters, apply_method="pending-reboot",
                           tags=None, region=None, key=None, keyid=None,
                           profile=None):
    '''
    Update an RDS parameter group.

    CLI example::

        salt myminion boto_rds.update_parameter_group my-param-group \
                parameters='{"back_log":1, "binlog_cache_size":4096}' \
                region=us-east-1
    '''

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not __salt__['boto_rds.parameter_group_exists'](name, tags, region, key,
                                                       keyid, profile):
        return False
    param_list = []
    for key, value in six.iteritems(parameters):
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


def describe(name, tags=None, region=None, key=None, keyid=None,
             profile=None):
    '''
    Return RDS instance details.

    CLI example::

        salt myminion boto_rds.describe myrds

    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not __salt__['boto_rds.exists'](name, tags, region, key, keyid,
                                       profile):
        return False
    try:
        rds = conn.describe_db_instances(db_instance_identifier=name)
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False
    _rds = rds['DescribeDBInstancesResponse']['DescribeDBInstancesResult']['DBInstances'][0]
    return _pythonize_dict(_rds)


def get_endpoint(name, tags=None, region=None, key=None, keyid=None,
                 profile=None):
    '''
    Return the enpoint of an RDS instance.

    CLI example::

        salt myminion boto_rds.get_endpoint myrds

    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not __salt__['boto_rds.exists'](name, tags, region, key, keyid,
                                       profile):
        return False
    try:
        rds = conn.describe_db_instances(db_instance_identifier=name)
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False
    insts = rds['DescribeDBInstancesResponse']['DescribeDBInstancesResult']
    endpoints = []
    for instance in insts['DBInstances']:
        endpoints.append(instance['Endpoint']['Address'])
    return endpoints[0]


def delete(name, skip_final_snapshot=None, final_db_snapshot_identifier=None,
           region=None, key=None, keyid=None, profile=None):
    '''
    Delete an RDS instance.

    CLI example::

        salt myminion boto_rds.delete myrds skip_final_snapshot=True \
                region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not skip_final_snapshot and not final_db_snapshot_identifier:
        raise SaltInvocationError('At least on of the following must'
                                  ' be specified: skip_final_snapshot'
                                  ' final_db_snapshot_identifier')
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
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

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
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

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
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

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


def _pythonize_dict(dictionary):
    _ret = dict((boto.utils.pythonize_name(k), _pythonize_dict(v) if
                 hasattr(v, 'keys') else v) for k, v in dictionary.items())
    return _ret
