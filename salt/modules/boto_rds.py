# -*- coding: utf-8 -*-
'''
Connection module for Amazon RDS

.. versionadded:: 2015.8.0

:configuration: This module accepts explicit rds credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles.
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

:depends: boto3
'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602


# Import Python libs
from __future__ import absolute_import
import logging
from salt.exceptions import SaltInvocationError
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module
from time import time, sleep

# Import Salt libs
import salt.utils.boto3
import salt.utils.compat
import salt.utils
import salt.ext.six as six

log = logging.getLogger(__name__)

# Import third party libs
# pylint: disable=import-error
try:
    #pylint: disable=unused-import
    import boto
    import boto3
    #pylint: enable=unused-import
    from botocore.exceptions import ClientError
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=import-error


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    required_boto3_version = '1.2.1'
    if not HAS_BOTO:
        return (False, 'The boto_rds module could not be loaded: '
                'boto libraries not found')
    elif _LooseVersion(boto3.__version__) < _LooseVersion(required_boto3_version):
        return (False, 'The boto_rds module could not be loaded: '
                'boto version {0} or later must be installed.'.format(required_boto3_version))
    else:
        return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO:
        __utils__['boto3.assign_funcs'](__name__, 'rds')


def exists(name, tags=None, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an RDS exists.

    CLI example::

        salt myminion boto_rds.exists myrds region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        rds = conn.describe_db_instances(DBInstanceIdentifier=name)
        return {'exists': bool(rds)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def option_group_exists(name, tags=None, region=None, key=None, keyid=None,
                        profile=None):
    '''
    Check to see if an RDS option group exists.

    CLI example::

        salt myminion boto_rds.option_group_exists myoptiongr region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        rds = conn.describe_option_groups(OptionGroupName=name)
        return {'exists': bool(rds)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


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
        rds = conn.describe_db_parameter_groups(DBParameterGroupName=name)
        return {'exists': bool(rds)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


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
        rds = conn.describe_db_subnet_groups(DBSubnetGroupName=name)
        return {'exists': bool(rds)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def create(name, allocated_storage, db_instance_class, engine,
           master_username, master_user_password, DBname=None,
           DBSecurityGroups=None, vpc_security_group_ids=None,
           availability_zone=None, db_subnet_group_name=None,
           preferred_maintenance_window=None, db_parameter_group_name=None,
           backup_retention_period=None, preferred_backup_window=None,
           Port=None, MultiAZ=None, EngineVersion=None,
           AutoMinorVersionUpgrade=None, LicenseModel=None, Iops=None,
           OptionGroupName=None, CharacterSetName=None,
           publicly_accessible=None, wait_status=None, tags=None,
           DBClusterIdentifier=None, storage_type=None,
           TdeCredentialArn=None, TdeCredentialPassword=None,
           StorageEncrypted=None, KmsKeyId=None, Domain=None,
           CopyTagsToSnapshot=None, MonitoringInterval=None,
           MonitoringRoleArn=None, DomainIAMRoleName=None, region=None,
           PromotionTier=None, key=None, keyid=None, profile=None):
    '''
    Create an RDS

    CLI example to create an RDS::

        salt myminion boto_rds.create myrds 10 db.t2.micro MySQL sqlusr sqlpassw
    '''
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
    if availability_zone and MultiAZ:
        raise SaltInvocationError('availability_zone and multi_az are mutually'
                                  ' exclusive arguments.')
    if wait_status:
        wait_statuses = ['available', 'modifying', 'backing-up']
        if wait_status not in wait_statuses:
            raise SaltInvocationError('wait_status can be one of: '
                                      '{0}'.format(wait_statuses))

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        kwargs = {}
        for key in ('DomainIAMRoleName', 'LicenseModel',
                    'TdeCredentialArn',
                    'TdeCredentialPassword', 'DBname', 'Domain',
                    'EngineVersion', 'OptionGroupName',
                    'CharacterSetName', 'MonitoringRoleArn',
                    'DBClusterIdentifier', 'KmsKeyId'):
            if locals()[key] is not None:
                kwargs[key] = str(locals()[key])

        for key in ('MonitoringInterval', 'PromotionTier',
                    'Iops', 'Port'):
            if locals()[key] is not None:
                kwargs[key] = int(locals()[key])

        for key in ('CopyTagsToSnapshot', 'MultiAZ',
                    'AutoMinorVersionUpgrade', 'StorageEncrypted'):
            if locals()[key] is not None:
                kwargs[key] = bool(locals()[key])

        taglist = _tag_doc(tags)

        rds = conn.create_db_instance(DBInstanceIdentifier=name,
                                      AllocatedStorage=allocated_storage,
                                      DBInstanceClass=db_instance_class,
                                      Engine=engine,
                                      MasterUsername=master_username,
                                      MasterUserPassword=master_user_password,
                                      VpcSecurityGroupIds=vpc_security_group_ids,
                                      AvailabilityZone=availability_zone,
                                      DBSubnetGroupName=db_subnet_group_name,
                                      PreferredMaintenanceWindow=preferred_maintenance_window,
                                      DBParameterGroupName=db_parameter_group_name,
                                      BackupRetentionPeriod=backup_retention_period,
                                      PreferredBackupWindow=preferred_backup_window,
                                      PubliclyAccessible=publicly_accessible,
                                      StorageType=storage_type, Tags=taglist,
                                      **kwargs)

        if not rds:
            return {'created': False}
        if not wait_status:
            log.info('Created RDS instance {0}.'.format(name))
            return {'created': True}

        while True:
            log.info('Waiting 10 secs...')
            sleep(10)
            _describe = describe(name=name, tags=tags, region=region, key=key,
                                 keyid=keyid, profile=profile)
            if not _describe:
                return {'created': True}
            if _describe['db_instance_status'] == wait_status:
                log.info('Created RDS {0} with current status '
                         '{1}'.format(name, _describe['db_instance_status']))
                return {'created': True}
            log.info('Current status: {0}'.format(_describe['db_instance_status']))

    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def create_read_replica(name, source_name, db_instance_class=None,
                        availability_zone=None, port=None,
                        auto_minor_version_upgrade=None, iops=None,
                        option_group_name=None, publicly_accessible=None,
                        tags=None, db_subnet_group_name=None,
                        storage_type=None, copy_tags_to_snapshot=None,
                        monitoring_interval=None, monitoring_role_arn=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Create an RDS read replica

    CLI example to create an RDS  read replica::

        salt myminion boto_rds.create_read_replica replicaname source_name
    '''
    if not backup_retention_period:
        raise SaltInvocationError('backup_retention_period is required')
    if not __salt__['boto_rds.exists'](source_name, tags, region, key, keyid, profile):
        return False
    if __salt__['boto_rds.exists'](name, tags, region, key, keyid, profile):
        return True

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        kwargs = {}
        for key in ('OptionGroupName', 'MonitoringRoleArn'):
            if locals()[key] is not None:
                kwargs[key] = str(locals()[key])

        for key in ('MonitoringInterval', 'Iops', 'Port'):
            if locals()[key] is not None:
                kwargs[key] = int(locals()[key])

        for key in ('CopyTagsToSnapshot', 'AutoMinorVersionUpgrade'):
            if locals()[key] is not None:
                kwargs[key] = bool(locals()[key])

        taglist = _tag_doc(tags)

        rds_replica = conn.create_db_instance_read_replica(DBInstanceIdentifier=name,
                                                           SourceDBInstanceIdentifier=source_name,
                                                           DBInstanceClass=db_instance_class,
                                                           AvailabilityZone=availability_zone,
                                                           Port=port,
                                                           AutoMinorVersionUpgrade=auto_minor_version_upgrade,
                                                           Iops=iops, OptionGroupName=option_group_name,
                                                           PubliclyAccessible=publicly_accessible,
                                                           Tags=taglist, DBSubnetGroupName=db_subnet_group_name,
                                                           StorageType=storage_type,
                                                           CopyTagsToSnapshot=copy_tags_to_snapshot,
                                                           MonitoringInterval=monitoring_interval,
                                                           MonitoringRoleArn=monitoring_role_arn)


        return {'exists': bool(rds_replica)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


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
        taglist = _tag_doc(tags)
        rds = conn.create_option_group(OptionGroupName=name,
                                       EngineName=engine_name,
                                       MajorEngineVersion=major_engine_version,
                                       OptionGroupDescription=option_group_description,
                                       Tags=taglist)

        return {'exists': bool(rds)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def create_parameter_group(name, db_parameter_group_family, description,
                           tags=None, region=None, key=None, keyid=None,
                           profile=None):
    '''
    Create an RDS parameter group

    CLI example to create an RDS parameter group::

        salt myminion boto_rds.create_parameter_group my-param-group mysql5.6 \
                "group description"
    '''
    if __salt__['boto_rds.parameter_group_exists'](name, tags, region, key,
                                                   keyid, profile):
        return True
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        taglist = _tag_doc(tags)
        rds = conn.create_db_parameter_group(DBParameterGroupName=name,
                                             DBParameterGroupFamily=db_parameter_group_family,
                                             Description=description,
                                             Tags=taglist)
        if not rds:
            msg = 'Failed to create RDS parameter group {0}'.format(name)
            log.error(msg)
            return {'created': False}
        log.info('Created RDS parameter group {0}'.format(name))
        return {'exists': bool(rds)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def create_subnet_group(name, description, subnet_ids, tags=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Create an RDS subnet group

    CLI example to create an RDS subnet group::

        salt myminion boto_rds.create_subnet_group my-subnet-group \
            "group description" '[subnet-12345678, subnet-87654321]' \
            region=us-east-1
    '''
    r = __salt__['boto_rds.subnet_group_exists'](name, tags, region, key,
                                                 keyid, profile)
    if r.get('exists'):
        return {'exists': True}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        taglist = _tag_doc(tags)
        rds = conn.create_db_subnet_group(DBSubnetGroupName=name,
                                          DBSubnetGroupDescription=description,
                                          SubnetIds=subnet_ids, Tags=taglist)

        return {'created': bool(rds)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


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
        conn.modify_db_parameter_group(DBParameterGroupName=name,
                                       Parameters=param_list)
        return {'exists': bool(rds)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


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
        return {'exists': False}
    try:
        rds = conn.describe_db_instances(DBInstanceIdentifier=name)

        if rds:
            keys = ('DBInstanceIdentifier', 'DBInstanceClass', 'Engine',
                    'DBInstanceStatus', 'DBName', 'AllocatedStorage',
                    'PreferredBackupWindow', 'BackupRetentionPeriod',
                    'AvailabilityZone', 'PreferredMaintenanceWindow',
                    'LatestRestorableTime', 'EngineVersion',
                    'AutoMinorVersionUpgrade', 'LicenseModel',
                    'Iops', 'CharacterSetName', 'PubliclyAccessible',
                    'StorageType', 'TdeCredentialArn', 'DBInstancePort',
                    'DBClusterIdentifier', 'StorageEncrypted', 'KmsKeyId',
                    'DbiResourceId', 'CACertificateIdentifier',
                    'CopyTagsToSnapshot', 'MonitoringInterval',
                    'MonitoringRoleArn', 'PromotionTier',
                    'DomainMemberships')
            return {'rds': dict([(k, rds.get(k)) for k in keys])}
        else:
            return {'rds': None}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def get_endpoint(name, tags=None, region=None, key=None, keyid=None,
                 profile=None):
    '''
    Return the endpoint of an RDS instance.

    CLI example::

        salt myminion boto_rds.get_endpoint myrds

    '''
    endpoint = 'None'
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not __salt__['boto_rds.exists'](name, tags, region, key, keyid,
                                       profile):
        return {'exists': False}
    try:
        rds = conn.describe_db_instances(DBInstanceIdentifier=name)

        if rds:
            inst = rds['DBInstances'][0]['Endpoint']
            endpoint = '{0}:{1}'.format(inst.get('Address'), inst.get('Port'))

    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

    return endpoint


def delete(name, skip_final_snapshot=None, final_db_snapshot_identifier=None,
           region=None, key=None, keyid=None, profile=None,
           wait_for_deletion=True, timeout=180):
    '''
    Delete an RDS instance.

    CLI example::

        salt myminion boto_rds.delete myrds skip_final_snapshot=True \
                region=us-east-1
    '''
    if timeout == 180 and not skip_final_snapshot:
        timeout = 420

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not skip_final_snapshot and not final_db_snapshot_identifier:
        raise SaltInvocationError('At least one of the following must'
                                  ' be specified: skip_final_snapshot'
                                  ' final_db_snapshot_identifier')
    try:
        conn.delete_db_instance(DBInstanceIdentifier=name,
                                SkipFinalSnapshot=skip_final_snapshot,
                                FinalDBSnapshotIdentifier=final_db_snapshot_identifier)

        if not wait_for_deletion:
            log.info('Deleted RDS instance {0}.'.format(name))
            return True
        start_time = time()
        while True:
            if not __salt__['boto_rds.exists'](name=name, region=region,
                                               key=key, keyid=keyid,
                                               profile=profile):
                log.info('Deleted RDS instance {0} completely.'.format(name))
                return True
            if time() - start_time > timeout:
                raise SaltInvocationError('RDS instance {0} has not been '
                                          'deleted completely after {1} '
                                          'seconds'.format(name, timeout))
            sleep(10)
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def delete_option_group(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete an RDS option group.

    CLI example::

        salt myminion boto_rds.delete_option_group my-opt-group \
                region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        conn.delete_option_group(OptionGroupName=name)
        msg = 'Deleted RDS option group {0}.'.format(name)
        log.info(msg)
        return True
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


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
        conn.delete_db_parameter_group(DBParameterGroupName=name)
        msg = 'Deleted RDS parameter group {0}.'.format(name)
        log.info(msg)
        return True
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


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
        conn.delete_db_subnet_group(DBSubnetGroupName=name)
        msg = 'Deleted RDS subnet group {0}.'.format(name)
        log.info(msg)
        return True
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def _tag_doc(tags):
    taglist = []
    if tags is not None:
        for k, v in tags.iteritems():
            if str(k).startswith('__'):
                continue
            taglist.append({'Key': str(k), 'Value': str(v)})
    return taglist
