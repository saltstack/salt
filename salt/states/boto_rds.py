# -*- coding: utf-8 -*-
'''
Manage RDSs
===========

.. versionadded:: 2015.8.0

Create and destroy RDS instances. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit rds credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    rds.keyid: GKTADJGHEIQSXMKKRBJ08H
    rds.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure myrds RDS exists:
      boto_rds.present:
        - name: myrds
        - allocated_storage: 5
        - storage_type: standard
        - db_instance_class: db.t2.micro
        - engine: MySQL
        - master_username: myuser
        - master_user_password: mypass
        - region: us-east-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        - tags:
          -
            - key1
            - value1
          -
            - key2
            - value2

.. note::

:depends: boto3

'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
from salt.exceptions import SaltInvocationError
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_rds' if 'boto_rds.exists' in __salt__ else False


def present(name,
            allocated_storage,
            db_instance_class,
            engine,
            master_username,
            master_user_password,
            db_name=None,
            storage_type=None,
            db_security_groups=None,
            vpc_security_group_ids=None,
            availability_zone=None,
            db_subnet_group_name=None,
            preferred_maintenance_window=None,
            db_parameter_group_name=None,
            db_cluster_identifier=None,
            tde_credential_arn=None,
            tde_credential_password=None,
            storage_encrypted=None,
            kms_keyid=None,
            backup_retention_period=None,
            preferred_backup_window=None,
            port=None,
            multi_az=None,
            engine_version=None,
            auto_minor_version_upgrade=None,
            license_model=None,
            iops=None,
            option_group_name=None,
            character_set_name=None,
            publicly_accessible=None,
            wait_status=None,
            tags=None,
            copy_tags_to_snapshot=None,
            region=None,
            domain=None,
            key=None,
            keyid=None,
            monitoring_interval=None,
            monitoring_role_arn=None,
            domain_iam_role_name=None,
            promotion_tier=None,
            profile=None):
    '''
    Ensure RDS instance exists.

    name
        Name of the RDS state definition.

    allocated_storage
        The amount of storage (in gigabytes) to be initially allocated for the
        database instance.

    db_instance_class
        The compute and memory capacity of the Amazon RDS DB instance.

    engine
        The name of the database engine to be used for this instance. Supported
        engine types are: MySQL, mariadb, oracle-se1, oracle-se, oracle-ee, sqlserver-ee,
        sqlserver-se, sqlserver-ex, sqlserver-web, postgres and aurora. For more
        information, please see the ``engine`` argument in the Boto3 RDS
        `create_db_instance`_ documentation.

    master_username
        The name of master user for the client DB instance.

    master_user_password
        The password for the master database user. Can be any printable ASCII
        character except "/", '"', or "@".

    db_name
        The meaning of this parameter differs according to the database engine you use.
        See the Boto3 RDS documentation to determine the appropriate value for your configuration.
        https://boto3.readthedocs.io/en/latest/reference/services/rds.html#RDS.Client.create_db_instance

    storage_type
        Specifies the storage type to be associated with the DB instance.
        Options are standard, gp2 and io1. If you specify io1, you must also include
        a value for the Iops parameter.

    db_security_groups
        A list of DB security groups to associate with this DB instance.

    vpc_security_group_ids
        A list of EC2 VPC security groups to associate with this DB instance.

    availability_zone
        The EC2 Availability Zone that the database instance will be created
        in.

    db_subnet_group_name
        A DB subnet group to associate with this DB instance.

    preferred_maintenance_window
        The weekly time range (in UTC) during which system maintenance can
        occur.

    db_parameter_group_name
        A DB parameter group to associate with this DB instance.

    db_cluster_identifier
        If the DB instance is a member of a DB cluster, contains the name of
        the DB cluster that the DB instance is a member of.

    tde_credential_arn
        The ARN from the Key Store with which the instance is associated for
        TDE encryption.

    tde_credential_password
        The password to use for TDE encryption if an encryption key is not used.

    storage_encrypted
        Specifies whether the DB instance is encrypted.

    kms_keyid
        If storage_encrypted is true, the KMS key identifier for the encrypted
        DB instance.

    backup_retention_period
        The number of days for which automated backups are retained.

    preferred_backup_window
        The daily time range during which automated backups are created if
        automated backups are enabled.

    port
        The port number on which the database accepts connections.

    multi_az
        Specifies if the DB instance is a Multi-AZ deployment. You cannot set
        the AvailabilityZone parameter if the MultiAZ parameter is set to true.

    engine_version
        The version number of the database engine to use.

    auto_minor_version_upgrade
        Indicates that minor engine upgrades will be applied automatically to
        the DB instance during the maintenance window.

    license_model
        License model information for this DB instance.

    iops
        The amount of Provisioned IOPS (input/output operations per second) to
        be initially allocated for the DB instance.

    option_group_name
        Indicates that the DB instance should be associated with the specified
        option group.

    character_set_name
        For supported engines, indicates that the DB instance should be
        associated with the specified CharacterSet.

    publicly_accessible
        Specifies the accessibility options for the DB instance. A value of
        true specifies an Internet-facing instance with a publicly resolvable
        DNS name, which resolves to a public IP address. A value of false
        specifies an internal instance with a DNS name that resolves to a
        private IP address.

    wait_status
        Wait for the RDS instance to reach a desired status before finishing
        the state. Available states: available, modifying, backing-up

    tags
        A list of tags.

    copy_tags_to_snapshot
        Specifies whether tags are copied from the DB instance to snapshots of
        the DB instance.

    region
        Region to connect to.

    domain
        The identifier of the Active Directory Domain.

    key
        AWS secret key to be used.

    keyid
        AWS access key to be used.

    monitoring_interval
        The interval, in seconds, between points when Enhanced Monitoring
        metrics are collected for the DB instance.

    monitoring_role_arn
        The ARN for the IAM role that permits RDS to send Enhanced Monitoring
        metrics to CloudWatch Logs.

    domain_iam_role_name
        Specify the name of the IAM role to be used when making API calls to
        the Directory Service.

    promotion_tier
        A value that specifies the order in which an Aurora Replica is
        promoted to the primary instance after a failure of the existing
        primary instance. For more information, see Fault Tolerance for an
        Aurora DB Cluster .

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    .. _create_dbinstance: https://boto3.readthedocs.io/en/latest/reference/services/rds.html#RDS.Client.create_db_instance
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_rds.exists'](name, region, key, keyid, profile)

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'RDS instance {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret

        r = __salt__['boto_rds.create'](name, allocated_storage,
                                        db_instance_class, engine,
                                        master_username,
                                        master_user_password,
                                        db_name, db_security_groups,
                                        vpc_security_group_ids,
                                        availability_zone,
                                        db_subnet_group_name,
                                        preferred_maintenance_window,
                                        db_parameter_group_name,
                                        backup_retention_period,
                                        preferred_backup_window,
                                        port, multi_az, engine_version,
                                        auto_minor_version_upgrade,
                                        license_model, iops,
                                        option_group_name,
                                        character_set_name,
                                        publicly_accessible, wait_status,
                                        tags, db_cluster_identifier,
                                        storage_type, tde_credential_arn,
                                        tde_credential_password,
                                        storage_encrypted, kms_keyid,
                                        domain, copy_tags_to_snapshot,
                                        monitoring_interval,
                                        monitoring_role_arn,
                                        domain_iam_role_name, region,
                                        promotion_tier, key, keyid, profile)

        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create RDS instance {0}.'.format(r['error']['message'])
            return ret

        _describe = __salt__['boto_rds.describe'](name, region, key, keyid, profile)
        ret['changes']['old'] = {'instance': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'RDS instance {0} created.'.format(name)
    else:
        ret['comment'] = 'RDS instance {0} exists.'.format(name)
    return ret


def replica_present(name, source, db_instance_class=None,
                    availability_zone=None, port=None,
                    auto_minor_version_upgrade=None, iops=None,
                    option_group_name=None, publicly_accessible=None,
                    tags=None, region=None, key=None, keyid=None,
                    profile=None):
    '''
    Ensure RDS replica exists.

    .. code-block:: yaml

        Ensure myrds replica RDS exists:
          boto_rds.create_replica:
            - name: myreplica
            - source: mydb
    '''
    ret = {'name': name,
           'result': None,
           'comment': '',
           'changes': {}
           }
    replica_exists = __salt__['boto_rds.exists'](name, tags, region, key,
                                                 keyid, profile)
    if not replica_exists:
        if __opts__['test']:
            ret['comment'] = 'RDS read replica {0} is set to be created '.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_rds.create_read_replica'](name, source,
                                                           db_instance_class,
                                                           availability_zone, port,
                                                           auto_minor_version_upgrade,
                                                           iops, option_group_name,
                                                           publicly_accessible,
                                                           tags, region, key,
                                                           keyid, profile)
        if created:
            config = __salt__['boto_rds.describe'](name, tags, region,
                                                   key, keyid, profile)
            ret['result'] = True
            ret['comment'] = 'RDS replica {0} created.'.format(name)
            ret['changes']['old'] = None
            ret['changes']['new'] = config
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create RDS replica {0}.'.format(name)
    else:
        ret['result'] = True
        ret['comment'] = 'RDS replica {0} exists.'.format(name)
    return ret


def subnet_group_present(name, description, subnet_ids=None, subnet_names=None,
                         tags=None, region=None, key=None, keyid=None,
                         profile=None):
    '''
    Ensure DB subnet group exists.

    name
        The name for the DB subnet group. This value is stored as a lowercase string.

    subnet_ids
        A list of the EC2 Subnet IDs for the DB subnet group.
        Either subnet_ids or subnet_names must be provided.

    subnet_names
        A list of The EC2 Subnet names for the DB subnet group.
        Either subnet_ids or subnet_names must be provided.

    description
        Subnet group description.

    tags
        A list of tags.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''
    if not salt.utils.exactly_one((subnet_ids, subnet_names)):
        raise SaltInvocationError('One (but not both) of subnet_ids or '
                                  'subnet_names must be provided.')

    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    if not subnet_ids:
        subnet_ids = []

    if subnet_names:
        for i in subnet_names:
            r = __salt__['boto_vpc.get_resource_id']('subnet', name=i,
                                                     region=region,
                                                     key=key, keyid=keyid,
                                                     profile=profile)

            if 'error' in r:
                ret['comment'] = 'Error looking up subnet ids: {0}'.format(
                    r['error']['message'])
                ret['result'] = False
                return ret
            if r['id'] is None:
                ret['comment'] = 'Subnet {0} does not exist.'.format(i)
                ret['result'] = False
                return ret
            subnet_ids.append(r['id'])

    for i in subnet_ids:
        r = __salt__['boto_rds.create_subnet_group'](name=name,
                                                     description=description,
                                                     subnet_ids=subnet_ids,
                                                     tags=tags, region=region,
                                                     key=key, keyid=keyid,
                                                     profile=profile)

        if not r.get('exists'):
            if __opts__['test']:
                ret['comment'] = 'Subnet group {0} is set to be created.'.format(name)
                ret['result'] = None
                return ret
            if not r.get('created'):
                ret['result'] = False
                ret['comment'] = 'Failed to create {0} subnet group.'.format(r['error']['message'])
                return ret

            _describe = __salt__['boto_rds.describe']('subnet',
                                                      name=i,
                                                      region=region,
                                                      key=key,
                                                      keyid=keyid,
                                                      profile=profile)

            ret['changes']['old'] = None
            ret['changes']['new'] = _describe
            ret['comment'] = 'Subnet {0} created.'.format(name)
        else:
            ret['comment'] = 'Subnet {0} present.'.format(name)

        return ret


def absent(name, skip_final_snapshot=None, final_db_snapshot_identifier=None,
           tags=None, region=None, key=None, keyid=None, profile=None,
           wait_for_deletion=True, timeout=180):
    '''
    Ensure RDS instance is absent.

    name
        Name of the RDS instance.

    skip_final_snapshot
        Whether a final db snapshot is created before the instance is deleted.
        If True, no snapshot is created.
        If False, a snapshot is created before deleting the instance.

    final_db_snapshot_identifier
        If a final snapshot is requested, this is the identifier used for that
        snapshot.

    tags
        A list of tags.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    .. _create_db_instance: http://boto.readthedocs.org/en/latest/ref/rds.html#boto.rds.RDSConnection.create_dbinstance

    wait_for_deletion (bool)
        Wait for the RDS instance to be deleted completely before finishing
        the state.

    timeout (in seconds)
        The amount of time that can pass before raising an Exception.
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    exists = __salt__['boto_rds.exists'](name, tags, region, key, keyid,
                                         profile)
    if not exists:
        ret['result'] = True
        ret['comment'] = '{0} RDS does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'RDS {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_rds.delete'](name, skip_final_snapshot,
                                          final_db_snapshot_identifier,
                                          region, key, keyid, profile,
                                          wait_for_deletion, timeout)
    if not deleted:
        ret['result'] = False
        ret['comment'] = 'Failed to delete {0} RDS.'.format(name)
        return ret
    ret['changes']['old'] = name
    ret['changes']['new'] = None
    ret['comment'] = 'RDS {0} deleted.'.format(name)
    return ret


def subnet_group_absent(name, tags=None, region=None, key=None, keyid=None, profile=None):
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    exists = __salt__['boto_rds.subnet_group_exists'](name=name, tags=tags, region=region, key=key,
                                                      keyid=keyid, profile=profile)
    if not exists:
        ret['result'] = True
        ret['comment'] = '{0} RDS subnet group does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'RDS subnet group {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_rds.delete_subnet_group'](name, region, key, keyid, profile)
    if not deleted:
        ret['result'] = False
        ret['comment'] = 'Failed to delete {0} RDS subnet group.'.format(name)
        return ret
    ret['changes']['old'] = name
    ret['changes']['new'] = None
    ret['comment'] = 'RDS subnet group {0} deleted.'.format(name)
    return ret
