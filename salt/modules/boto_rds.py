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
# pylint whinging perfectly valid code
#pylint: disable=W0106


# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import time

# Import Salt libs
import salt.utils.boto3
import salt.utils.compat
import salt.utils.odict as odict
import salt.utils.versions
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

# Import third party libs
from salt.ext import six
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

boto3_param_map = {
    'allocated_storage': ('AllocatedStorage', int),
    'allow_major_version_upgrade': ('AllowMajorVersionUpgrade', bool),
    'apply_immediately': ('ApplyImmediately', bool),
    'auto_minor_version_upgrade': ('AutoMinorVersionUpgrade', bool),
    'availability_zone': ('AvailabilityZone', str),
    'backup_retention_period': ('BackupRetentionPeriod', int),
    'ca_certificate_identifier': ('CACertificateIdentifier', str),
    'character_set_name': ('CharacterSetName', str),
    'copy_tags_to_snapshot': ('CopyTagsToSnapshot', bool),
    'db_cluster_identifier': ('DBClusterIdentifier', str),
    'db_instance_class': ('DBInstanceClass', str),
    'db_name': ('DBName', str),
    'db_parameter_group_name': ('DBParameterGroupName', str),
    'db_port_number': ('DBPortNumber', int),
    'db_security_groups': ('DBSecurityGroups', list),
    'db_subnet_group_name': ('DBSubnetGroupName', str),
    'domain': ('Domain', str),
    'domain_iam_role_name': ('DomainIAMRoleName', str),
    'engine': ('Engine', str),
    'engine_version': ('EngineVersion', str),
    'iops': ('Iops', int),
    'kms_key_id': ('KmsKeyId', str),
    'license_model': ('LicenseModel', str),
    'master_user_password': ('MasterUserPassword', str),
    'master_username': ('MasterUsername', str),
    'monitoring_interval': ('MonitoringInterval', int),
    'monitoring_role_arn': ('MonitoringRoleArn', str),
    'multi_az': ('MultiAZ', bool),
    'name': ('DBInstanceIdentifier', str),
    'new_db_instance_identifier': ('NewDBInstanceIdentifier', str),
    'option_group_name': ('OptionGroupName', str),
    'port': ('Port', int),
    'preferred_backup_window': ('PreferredBackupWindow', str),
    'preferred_maintenance_window': ('PreferredMaintenanceWindow', str),
    'promotion_tier': ('PromotionTier', int),
    'publicly_accessible': ('PubliclyAccessible', bool),
    'storage_encrypted': ('StorageEncrypted', bool),
    'storage_type': ('StorageType', str),
    'tags': ('Tags', list),
    'tde_credential_arn': ('TdeCredentialArn', str),
    'tde_credential_password': ('TdeCredentialPassword', str),
    'vpc_security_group_ids': ('VpcSecurityGroupIds', list),
}


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    return salt.utils.versions.check_boto_reqs(
        boto3_ver='1.3.1'
    )


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
        return {'exists': bool(rds), 'error': None}
    except ClientError as e:
        resp = {}
        if e.response['Error']['Code'] == 'DBParameterGroupNotFound':
            resp['exists'] = False
        resp['error'] = salt.utils.boto3.get_error(e)
        return resp


def subnet_group_exists(name, tags=None, region=None, key=None, keyid=None,
                        profile=None):
    '''
    Check to see if an RDS subnet group exists.

    CLI example::

        salt myminion boto_rds.subnet_group_exists my-param-group \
                region=us-east-1
    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'exists': bool(conn)}

        rds = conn.describe_db_subnet_groups(DBSubnetGroupName=name)
        return {'exists': bool(rds)}
    except ClientError as e:
        if "DBSubnetGroupNotFoundFault" in e.message:
            return {'exists': False}
        else:
            return {'error': salt.utils.boto3.get_error(e)}


def create(name, allocated_storage, db_instance_class, engine,
           master_username, master_user_password, db_name=None,
           db_security_groups=None, vpc_security_group_ids=None,
           vpc_security_groups=None, availability_zone=None,
           db_subnet_group_name=None, preferred_maintenance_window=None,
           db_parameter_group_name=None, backup_retention_period=None,
           preferred_backup_window=None, port=None, multi_az=None,
           engine_version=None, auto_minor_version_upgrade=None,
           license_model=None, iops=None, option_group_name=None,
           character_set_name=None, publicly_accessible=None, wait_status=None,
           tags=None, db_cluster_identifier=None, storage_type=None,
           tde_credential_arn=None, tde_credential_password=None,
           storage_encrypted=None, kms_key_id=None, domain=None,
           copy_tags_to_snapshot=None, monitoring_interval=None,
           monitoring_role_arn=None, domain_iam_role_name=None, region=None,
           promotion_tier=None, key=None, keyid=None, profile=None):
    '''
    Create an RDS Instance

    CLI example to create an RDS Instance::

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
    if availability_zone and multi_az:
        raise SaltInvocationError('availability_zone and multi_az are mutually'
                                  ' exclusive arguments.')
    if wait_status:
        wait_stati = ['available', 'modifying', 'backing-up']
        if wait_status not in wait_stati:
            raise SaltInvocationError(
                'wait_status can be one of: {0}'.format(wait_stati))
    if vpc_security_groups:
        v_tmp = __salt__['boto_secgroup.convert_to_group_ids'](
                groups=vpc_security_groups, region=region, key=key, keyid=keyid,
                profile=profile)
        vpc_security_group_ids = (vpc_security_group_ids + v_tmp
                                  if vpc_security_group_ids else v_tmp)

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'results': bool(conn)}

        kwargs = {}
        boto_params = set(boto3_param_map.keys())
        keys = set(locals().keys())
        tags = _tag_doc(tags)

        for param_key in keys.intersection(boto_params):
            val = locals()[param_key]
            if val is not None:
                mapped = boto3_param_map[param_key]
                kwargs[mapped[0]] = mapped[1](val)

        # Validation doesn't want parameters that are None
        # https://github.com/boto/boto3/issues/400
        kwargs = dict((k, v) for k, v in six.iteritems(kwargs) if v is not None)

        rds = conn.create_db_instance(**kwargs)

        if not rds:
            return {'created': False}
        if not wait_status:
            return {'created': True, 'message':
                    'RDS instance {0} created.'.format(name)}

        while True:
            jmespath = 'DBInstances[*].DBInstanceStatus'
            status = describe_db_instances(name=name, jmespath=jmespath,
                                           region=region, key=key, keyid=keyid,
                                           profile=profile)
            if len(status):
                stat = status[0]
            else:
                # Whoops, something is horribly wrong...
                return {'created': False,
                        'error': "RDS instance {0} should have been created but"
                                 " now I can't find it.".format(name)}
            if stat == wait_status:
                return {'created': True,
                        'message': 'RDS instance {0} created (current status '
                        '{1})'.format(name, stat)}
            time.sleep(10)
            log.info('Instance status after 10 seconds is: %s', stat)

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
    res = __salt__['boto_rds.exists'](source_name, tags, region, key, keyid, profile)
    if not res.get('exists'):
        return {'exists': bool(res), 'message':
                'RDS instance source {0} does not exists.'.format(source_name)}

    res = __salt__['boto_rds.exists'](name, tags, region, key, keyid, profile)
    if res.get('exists'):
        return {'exists': bool(res), 'message':
                'RDS replica instance {0} already exists.'.format(name)}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        kwargs = {}
        for key in ('OptionGroupName', 'MonitoringRoleArn'):
            if locals()[key] is not None:
                kwargs[key] = str(locals()[key])  # future lint: disable=blacklisted-function

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
                                                           PubliclyAccessible=publicly_accessible,
                                                           Tags=taglist, DBSubnetGroupName=db_subnet_group_name,
                                                           StorageType=storage_type,
                                                           **kwargs)

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
    res = __salt__['boto_rds.option_group_exists'](name, tags, region, key, keyid,
                                                   profile)
    if res.get('exists'):
        return {'exists': bool(res)}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'results': bool(conn)}

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
    res = __salt__['boto_rds.parameter_group_exists'](name, tags, region, key,
                                                      keyid, profile)
    if res.get('exists'):
        return {'exists': bool(res)}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'results': bool(conn)}

        taglist = _tag_doc(tags)
        rds = conn.create_db_parameter_group(DBParameterGroupName=name,
                                             DBParameterGroupFamily=db_parameter_group_family,
                                             Description=description,
                                             Tags=taglist)
        if not rds:
            return {'created': False, 'message':
                    'Failed to create RDS parameter group {0}'.format(name)}

        return {'exists': bool(rds), 'message':
                'Created RDS parameter group {0}'.format(name)}
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
    res = __salt__['boto_rds.subnet_group_exists'](name, tags, region, key,
                                                 keyid, profile)
    if res.get('exists'):
        return {'exists': bool(res)}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'results': bool(conn)}

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

    res = __salt__['boto_rds.parameter_group_exists'](name, tags, region, key,
                                                      keyid, profile)
    if not res.get('exists'):
        return {'exists': bool(res), 'message':
                'RDS parameter group {0} does not exist.'.format(name)}

    param_list = []
    for key, value in six.iteritems(parameters):
        item = odict.OrderedDict()
        item.update({'ParameterName': key})
        item.update({'ApplyMethod': apply_method})
        if type(value) is bool:
            item.update({'ParameterValue': 'on' if value else 'off'})
        else:
            item.update({'ParameterValue': str(value)})  # future lint: disable=blacklisted-function
        param_list.append(item)

    if not len(param_list):
        return {'results': False}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'results': bool(conn)}

        res = conn.modify_db_parameter_group(DBParameterGroupName=name,
                                             Parameters=param_list)
        return {'results': bool(res)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def describe(name, tags=None, region=None, key=None, keyid=None,
             profile=None):
    '''
    Return RDS instance details.

    CLI example::

        salt myminion boto_rds.describe myrds

    '''
    res = __salt__['boto_rds.exists'](name, tags, region, key, keyid,
                                      profile)
    if not res.get('exists'):
        return {'exists': bool(res), 'message':
                'RDS instance {0} does not exist.'.format(name)}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'results': bool(conn)}

        rds = conn.describe_db_instances(DBInstanceIdentifier=name)
        rds = [
            i for i in rds.get('DBInstances', [])
            if i.get('DBInstanceIdentifier') == name
        ].pop(0)

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
    except IndexError:
        return {'rds': None}


def describe_db_instances(name=None, filters=None, jmespath='DBInstances',
                          region=None, key=None, keyid=None, profile=None):
    '''
    Return a detailed listing of some, or all, DB Instances visible in the
    current scope.  Arbitrary subelements or subsections of the returned dataset
    can be selected by passing in a valid JMSEPath filter as well.

    CLI example::

        salt myminion boto_rds.describe_db_instances jmespath='DBInstances[*].DBInstanceIdentifier'

    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    pag = conn.get_paginator('describe_db_instances')
    args = {}
    args.update({'DBInstanceIdentifier': name}) if name else None
    args.update({'Filters': filters}) if filters else None
    pit = pag.paginate(**args)
    pit = pit.search(jmespath) if jmespath else pit
    try:
        return [p for p in pit]
    except ClientError as e:
        code = getattr(e, 'response', {}).get('Error', {}).get('Code')
        if code != 'DBInstanceNotFound':
            log.error(salt.utils.boto3.get_error(e))
    return []


def describe_db_subnet_groups(name=None, filters=None, jmespath='DBSubnetGroups',
                              region=None, key=None, keyid=None, profile=None):
    '''
    Return a detailed listing of some, or all, DB Subnet Groups visible in the
    current scope.  Arbitrary subelements or subsections of the returned dataset
    can be selected by passing in a valid JMSEPath filter as well.

    CLI example::

        salt myminion boto_rds.describe_db_subnet_groups

    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    pag = conn.get_paginator('describe_db_subnet_groups')
    args = {}
    args.update({'DBSubnetGroupName': name}) if name else None
    args.update({'Filters': filters}) if filters else None
    pit = pag.paginate(**args)
    pit = pit.search(jmespath) if jmespath else pit
    return [p for p in pit]


def get_endpoint(name, tags=None, region=None, key=None, keyid=None,
                 profile=None):
    '''
    Return the endpoint of an RDS instance.

    CLI example::

        salt myminion boto_rds.get_endpoint myrds

    '''
    endpoint = False
    res = __salt__['boto_rds.exists'](name, tags, region, key, keyid,
                                      profile)
    if res.get('exists'):
        try:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            if conn:
                rds = conn.describe_db_instances(DBInstanceIdentifier=name)

                if rds and 'Endpoint' in rds['DBInstances'][0]:
                    endpoint = rds['DBInstances'][0]['Endpoint']['Address']
                    return endpoint

        except ClientError as e:
            return {'error': salt.utils.boto3.get_error(e)}

    return endpoint


def delete(name, skip_final_snapshot=None, final_db_snapshot_identifier=None,
           region=None, key=None, keyid=None, profile=None, tags=None,
           wait_for_deletion=True, timeout=180):
    '''
    Delete an RDS instance.

    CLI example::

        salt myminion boto_rds.delete myrds skip_final_snapshot=True \
                region=us-east-1
    '''
    if timeout == 180 and not skip_final_snapshot:
        timeout = 420

    if not skip_final_snapshot and not final_db_snapshot_identifier:
        raise SaltInvocationError('At least one of the following must'
                                  ' be specified: skip_final_snapshot'
                                  ' final_db_snapshot_identifier')

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'deleted': bool(conn)}

        kwargs = {}
        if locals()['skip_final_snapshot'] is not None:
            kwargs['SkipFinalSnapshot'] = bool(locals()['skip_final_snapshot'])

        if locals()['final_db_snapshot_identifier'] is not None:
            kwargs['FinalDBSnapshotIdentifier'] = str(locals()['final_db_snapshot_identifier'])  # future lint: disable=blacklisted-function

        res = conn.delete_db_instance(DBInstanceIdentifier=name, **kwargs)

        if not wait_for_deletion:
            return {'deleted': bool(res), 'message':
                    'Deleted RDS instance {0}.'.format(name)}

        start_time = time.time()
        while True:
            res = __salt__['boto_rds.exists'](name=name, tags=tags, region=region,
                                               key=key, keyid=keyid,
                                               profile=profile)
            if not res.get('exists'):
                return {'deleted': bool(res), 'message':
                        'Deleted RDS instance {0} completely.'.format(name)}

            if time.time() - start_time > timeout:
                raise SaltInvocationError('RDS instance {0} has not been '
                                          'deleted completely after {1} '
                                          'seconds'.format(name, timeout))
            log.info('Waiting up to %s seconds for RDS instance %s to be '
                     'deleted.', timeout, name)
            time.sleep(10)
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def delete_option_group(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete an RDS option group.

    CLI example::

        salt myminion boto_rds.delete_option_group my-opt-group \
                region=us-east-1
    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'deleted': bool(conn)}

        res = conn.delete_option_group(OptionGroupName=name)
        if not res:
            return {'deleted': bool(res), 'message':
                    'Failed to delete RDS option group {0}.'.format(name)}

        return {'deleted': bool(res), 'message':
                'Deleted RDS option group {0}.'.format(name)}
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
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'results': bool(conn)}

        r = conn.delete_db_parameter_group(DBParameterGroupName=name)
        return {'deleted': bool(r), 'message':
                'Deleted RDS parameter group {0}.'.format(name)}
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
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'results': bool(conn)}

        r = conn.delete_db_subnet_group(DBSubnetGroupName=name)
        return {'deleted': bool(r), 'message':
                'Deleted RDS subnet group {0}.'.format(name)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def describe_parameter_group(name, Filters=None, MaxRecords=None, Marker=None,
                             region=None, key=None, keyid=None, profile=None):
    '''
    Returns a list of `DBParameterGroup` descriptions.
    CLI example to description of parameter group::

        salt myminion boto_rds.describe_parameter_group parametergroupname\
            region=us-east-1
    '''
    res = __salt__['boto_rds.parameter_group_exists'](name, tags=None,
                                                      region=region, key=key,
                                                      keyid=keyid,
                                                      profile=profile)
    if not res.get('exists'):
        return {'exists': bool(res)}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'results': bool(conn)}

        kwargs = {}
        for key in ('Marker', 'Filters'):
            if locals()[key] is not None:
                kwargs[key] = str(locals()[key])  # future lint: disable=blacklisted-function

        if locals()['MaxRecords'] is not None:
            kwargs['MaxRecords'] = int(locals()['MaxRecords'])

        info = conn.describe_db_parameter_groups(DBParameterGroupName=name,
                                                 **kwargs)

        if not info:
            return {'results': bool(info), 'message':
                    'Failed to get RDS description for group {0}.'.format(name)}

        return {'results': bool(info), 'message':
                'Got RDS descrition for group {0}.'.format(name)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def describe_parameters(name, Source=None, MaxRecords=None, Marker=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Returns a list of `DBParameterGroup` parameters.
    CLI example to description of parameters ::

        salt myminion boto_rds.describe_parameters parametergroupname\
            region=us-east-1
    '''
    res = __salt__['boto_rds.parameter_group_exists'](name, tags=None,
                                                      region=region, key=key,
                                                      keyid=keyid,
                                                      profile=profile)
    if not res.get('exists'):
        return {'result': False,
                'message': 'Parameter group {0} does not exist'.format(name)}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'result': False,
                    'message': 'Could not establish a connection to RDS'}

        kwargs = {}
        kwargs.update({'DBParameterGroupName': name})
        for key in ('Marker', 'Source'):
            if locals()[key] is not None:
                kwargs[key] = str(locals()[key])  # future lint: disable=blacklisted-function

        if locals()['MaxRecords'] is not None:
            kwargs['MaxRecords'] = int(locals()['MaxRecords'])

        pag = conn.get_paginator('describe_db_parameters')
        pit = pag.paginate(**kwargs)

        keys = ['ParameterName', 'ParameterValue', 'Description',
                'Source', 'ApplyType', 'DataType', 'AllowedValues',
                'IsModifieable', 'MinimumEngineVersion', 'ApplyMethod']

        parameters = odict.OrderedDict()
        ret = {'result':  True}

        for p in pit:
            for result in p['Parameters']:
                data = odict.OrderedDict()
                for k in keys:
                    data[k] = result.get(k)

                parameters[result.get('ParameterName')] = data

        ret['parameters'] = parameters
        return ret
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def modify_db_instance(name,
                       allocated_storage=None,
                       allow_major_version_upgrade=None,
                       apply_immediately=None,
                       auto_minor_version_upgrade=None,
                       backup_retention_period=None,
                       ca_certificate_identifier=None,
                       character_set_name=None,
                       copy_tags_to_snapshot=None,
                       db_cluster_identifier=None,
                       db_instance_class=None,
                       db_name=None,
                       db_parameter_group_name=None,
                       db_port_number=None,
                       db_security_groups=None,
                       db_subnet_group_name=None,
                       domain=None,
                       domain_iam_role_name=None,
                       engine_version=None,
                       iops=None,
                       kms_key_id=None,
                       license_model=None,
                       master_user_password=None,
                       monitoring_interval=None,
                       monitoring_role_arn=None,
                       multi_az=None,
                       new_db_instance_identifier=None,
                       option_group_name=None,
                       preferred_backup_window=None,
                       preferred_maintenance_window=None,
                       promotion_tier=None,
                       publicly_accessible=None,
                       storage_encrypted=None,
                       storage_type=None,
                       tde_credential_arn=None,
                       tde_credential_password=None,
                       vpc_security_group_ids=None,
                       region=None, key=None, keyid=None, profile=None):
    '''
    Modify settings for a DB instance.
    CLI example to description of parameters ::

        salt myminion boto_rds.modify_db_instance db_instance_identifier region=us-east-1
    '''
    res = __salt__['boto_rds.exists'](name, tags=None, region=region, key=key, keyid=keyid, profile=profile)
    if not res.get('exists'):
        return {'modified': False, 'message':
                'RDS db instance {0} does not exist.'.format(name)}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not conn:
            return {'modified': False}

        kwargs = {}
        excluded = set(('name',))
        boto_params = set(boto3_param_map.keys())
        keys = set(locals().keys())
        for key in keys.intersection(boto_params).difference(excluded):
            val = locals()[key]
            if val is not None:
                mapped = boto3_param_map[key]
                kwargs[mapped[0]] = mapped[1](val)

        info = conn.modify_db_instance(DBInstanceIdentifier=name, **kwargs)

        if not info:
            return {'modified': bool(info), 'message':
                    'Failed to modify RDS db instance {0}.'.format(name)}

        return {'modified': bool(info), 'message':
                'Modified RDS db instance {0}.'.format(name),
                'results': dict(info)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def _tag_doc(tags):
    taglist = []
    if tags is not None:
        for k, v in six.iteritems(tags):
            if six.text_type(k).startswith('__'):
                continue
            taglist.append({'Key': six.text_type(k), 'Value': six.text_type(v)})
    return taglist
