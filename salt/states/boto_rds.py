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

.. code-block:: yaml

    Ensure parameter group exists:
        create-parameter-group:
          boto_rds.parameter_present:
            - name: myparametergroup
            - db_parameter_group_family: mysql5.6
            - description: "parameter group family"
            - parameters:
              - binlog_cache_size: 32768
              - binlog_checksum: CRC32
            - region: eu-west-1
.. note::

    This state module uses ``boto.rds2``, which requires a different tagging syntax than
    some of the other boto states. The ``tags`` key and value set noted in the example
    above is the required yaml notation that ``rds2`` depends upon to function properly.
    For more information, please see `Issue #28715`_.

.. _Issue #28715: https://github.com/saltstack/salt/issues/28715


'''

# Import Python Libs
from __future__ import absolute_import
import logging
import os

# Import Salt Libs
from salt.exceptions import SaltInvocationError
from salt.utils import exactly_one


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
            db_security_groups=None,
            vpc_security_group_ids=None,
            availability_zone=None,
            db_subnet_group_name=None,
            preferred_maintenance_window=None,
            db_parameter_group_name=None,
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
            region=None,
            key=None,
            keyid=None,
            profile=None):
    '''
    Ensure RDS instance exists.

    name
        Name of the RDS instance.

    allocated_storage
        The amount of storage (in gigabytes) to be initially allocated for the
        database instance.

    db_instance_class
        The compute and memory capacity of the Amazon RDS DB instance.

    engine
        The name of the database engine to be used for this instance. Supported
        engine types are: MySQL, oracle-se1, oracle-se, oracle-ee, sqlserver-ee,
        sqlserver-se, sqlserver-ex, sqlserver-web, and postgres. For more
        information, please see the ``engine`` argument in the boto_rds
        `create_dbinstance`_ documentation.

    master_username
        The name of master user for the client DB instance.

    master_user_password
        The password for the master database user. Can be any printable ASCII
        character except "/", '"', or "@".

    db_name
        The database name for the restored DB instance.

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

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    .. _create_dbinstance: http://boto.readthedocs.org/en/latest/ref/rds.html#boto.rds.RDSConnection.create_dbinstance
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }
    _ret = _rds_present(name, allocated_storage,
                        db_instance_class, engine,
                        master_username, master_user_password, db_name,
                        db_security_groups, vpc_security_group_ids,
                        availability_zone, db_subnet_group_name,
                        preferred_maintenance_window, db_parameter_group_name,
                        backup_retention_period, preferred_backup_window, port,
                        multi_az, engine_version, auto_minor_version_upgrade,
                        license_model, iops, option_group_name,
                        character_set_name, publicly_accessible, wait_status,
                        tags, region, key, keyid, profile)
    ret['changes'] = _ret['changes']
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    return ret


def _rds_present(name, allocated_storage, db_instance_class,
                 engine, master_username, master_user_password, db_name=None,
                 db_security_groups=None, vpc_security_group_ids=None,
                 availability_zone=None, db_subnet_group_name=None,
                 preferred_maintenance_window=None,
                 db_parameter_group_name=None, backup_retention_period=None,
                 preferred_backup_window=None, port=None, multi_az=None,
                 engine_version=None, auto_minor_version_upgrade=None,
                 license_model=None, iops=None, option_group_name=None,
                 character_set_name=None, publicly_accessible=None,
                 wait_status=None, tags=None, region=None, key=None,
                 keyid=None, profile=None):
    ret = {'result': True,
           'comment': '',
           'changes': {}
           }
    exists = __salt__['boto_rds.exists'](name, tags, region, key, keyid,
                                         profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'RDS {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_rds.create'](name, allocated_storage,
                                              db_instance_class,
                                              engine, master_username,
                                              master_user_password, db_name,
                                              db_security_groups,
                                              vpc_security_group_ids,
                                              availability_zone,
                                              db_subnet_group_name,
                                              preferred_maintenance_window,
                                              db_parameter_group_name,
                                              backup_retention_period,
                                              preferred_backup_window, port,
                                              multi_az, engine_version,
                                              auto_minor_version_upgrade,
                                              license_model, iops,
                                              option_group_name,
                                              character_set_name,
                                              publicly_accessible,
                                              wait_status, tags, region, key,
                                              keyid, profile)
        if not created:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} RDS.'.format(name)
            return ret
        _describe = __salt__['boto_rds.describe'](name, tags, region, key,
                                                  keyid, profile)
        ret['changes']['old'] = {'rds': None}
        ret['changes']['new'] = {'rds': _describe}
        ret['comment'] = 'RDS {0} created.'.format(name)
    else:
        ret['comment'] = 'RDS replica {0} exists.'.format(name)
    return ret


def replica_present(name, source, db_instance_class=None, availability_zone=None, port=None,
                    auto_minor_version_upgrade=None, iops=None, option_group_name=None,
                    publicly_accessible=None, tags=None, region=None, key=None, keyid=None,
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
    if not exactly_one((subnet_ids, subnet_names)):
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
            r = __salt__['boto_vpc.get_resource_id']('subnet',
                                                     name=i,
                                                     region=region,
                                                     key=key,
                                                     keyid=keyid,
                                                     profile=profile)

            if 'error' in r:
                msg = 'Error looking up subnet ids: {0}'.format(
                    r['error']['message'])
                ret['comment'] = msg
                ret['result'] = False
                return ret
            if r['id'] is None:
                msg = 'Subnet {0} does not exist.'.format(i)
                ret['comment'] = msg
                ret['result'] = False
                return ret
            subnet_ids.append(r['id'])

    exists = __salt__['boto_rds.subnet_group_exists'](name=name, tags=tags, region=region, key=key,
                                                      keyid=keyid, profile=profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'Subnet group {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_rds.create_subnet_group'](name=name, subnet_ids=subnet_ids,
                                                           description=description, tags=tags, region=region,
                                                           key=key, keyid=keyid, profile=profile)
        if not created:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} subnet group.'.format(name)
            return ret
        ret['changes']['old'] = None
        ret['changes']['new'] = name
        ret['comment'] = 'Subnet {0} created.'.format(name)
        return ret
    ret['comment'] = 'Subnet present.'
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

    .. _create_dbinstance: http://boto.readthedocs.org/en/latest/ref/rds.html#boto.rds.RDSConnection.create_dbinstance

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


def parameter_present(name, db_parameter_group_family, description, parameters=None,
                      apply_method="pending-reboot", tags=None, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure DB parameter group exists and update parameters.

    name
        The name for the parameter group.

    db_parameter_group_family
        The DB parameter group family name. A
        DB parameter group can be associated with one and only one DB
        parameter group family, and can be applied only to a DB instance
        running a database engine and engine version compatible with that
        DB parameter group family.

    description
        Parameter group description.

    parameters
        The DB parameters that need to be changed of type dictionary.

    apply_method
        The `apply-immediate` method can be used only for dynamic
        parameters; the `pending-reboot` method can be used with MySQL
        and Oracle DB instances for either dynamic or static
        parameters. For Microsoft SQL Server DB instances, the
        `pending-reboot` method can be used only for static
        parameters.

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
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }
    exists = __salt__['boto_rds.parameter_group_exists'](name=name, tags=tags, region=region, key=key,
                                                         keyid=keyid, profile=profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'Parameter group {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_rds.create_parameter_group'](name=name, db_parameter_group_family=db_parameter_group_family,
                                                              description=description, tags=tags, region=region,
                                                              key=key, keyid=keyid, profile=profile)
        if not created:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} parameter group.'.format(name)
            return ret
        ret['changes']['New Parameter Group'] = name
        ret['comment'] = 'Parameter group {0} created.'.format(name)
    else:
        ret['comment'] = 'Parameter group {0} present.'.format(name)
    if parameters is not None:
        params = {}
        changed = {}
        for items in parameters:
            for k, value in items.items():
                params[k] = value
        logging.debug('Parameters from user are : {0}.'.format(params))
        options = __salt__['boto_rds.describe_parameters'](name=name, region=region, key=key, keyid=keyid, profile=profile)
        if not options:
            ret['result'] = False
            ret['comment'] = os.linesep.join([ret['comment'], 'Faled to get parameters for group  {0}.'.format(name)])
            return ret
        options = options['DescribeDBParametersResponse']['DescribeDBParametersResult']['Parameters']
        for values in options:
            if values['ParameterName'] in params and str(params.get(values['ParameterName'])) != str(values['ParameterValue']):
                logging.debug('Values that are being compared are {0}:{1} .'.format(params.get(values['ParameterName']), values['ParameterValue']))
                changed[values['ParameterName']] = params.get(values['ParameterName'])
        if len(changed) > 0:
            if __opts__['test']:
                ret['comment'] = os.linesep.join([ret['comment'], 'Parameters {0} for group {1} are set to be changed.'.format(changed, name)])
                ret['result'] = None
                return ret
            update = __salt__['boto_rds.update_parameter_group'](name, parameters=changed, apply_method=apply_method, tags=tags, region=region,
                                                                 key=key, keyid=keyid, profile=profile)
            if not update:
                ret['result'] = False
                ret['comment'] = os.linesep.join([ret['comment'], 'Failed to change parameters {0} for group {1}.'.format(changed, name)])
                return ret
            ret['changes']['Parameters'] = changed
            ret['comment'] = os.linesep.join([ret['comment'], 'Parameters {0} for group {1} are changed.'.format(changed, name)])
        else:
            ret['comment'] = os.linesep.join([ret['comment'], 'Parameters {0} for group {1} are present.'.format(params, name)])
    return ret
