# -*- coding: utf-8 -*-
'''
Connection module for Amazon EC2

.. versionadded:: 2015.8.0

:configuration: This module accepts explicit EC2 credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        ec2.keyid: GKTADJGHEIQSXMKKRBJ08H
        ec2.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        ec2.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid, and region via a profile, either
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

# Import Python libs
from __future__ import absolute_import
import logging
import time
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module

# Import Salt libs
import salt.ext.six as six
from salt.exceptions import SaltInvocationError, CommandExecutionError

# Import third party libs
try:
    # pylint: disable=unused-import
    import boto
    import boto.ec2
    # pylint: enable=unused-import
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    required_boto_version = '2.8.0'
    # the boto_ec2 execution module relies on the connect_to_region() method
    # which was added in boto 2.8.0
    # https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
    if not HAS_BOTO:
        return False
    elif _LooseVersion(boto.__version__) < _LooseVersion(required_boto_version):
        return False
    else:
        __utils__['boto.assign_funcs'](__name__, 'ec2', pack=__salt__)
        return True


def get_zones(region=None, key=None, keyid=None, profile=None):
    '''
    Get a list of AZs for the configured region.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.get_zones
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    return [z.name for z in conn.get_all_zones()]


def find_instances(instance_id=None, name=None, tags=None, region=None,
                   key=None, keyid=None, profile=None, return_objs=False):

    '''
    Given instance properties, find and return matching instance ids

    CLI Examples:

    .. code-block:: bash

        salt myminion boto_ec2.find_instances # Lists all instances
        salt myminion boto_ec2.find_instances name=myinstance
        salt myminion boto_ec2.find_instances tags='{"mytag": "value"}'

    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        filter_parameters = {'filters': {}}

        if instance_id:
            filter_parameters['instance_ids'] = [instance_id]

        if name:
            filter_parameters['filters']['tag:Name'] = name

        if tags:
            for tag_name, tag_value in six.iteritems(tags):
                filter_parameters['filters']['tag:{0}'.format(tag_name)] = tag_value

        reservations = conn.get_all_instances(**filter_parameters)
        instances = [i for r in reservations for i in r.instances]
        log.debug('The filters criteria {0} matched the following '
                  'instances:{1}'.format(filter_parameters, instances))

        if instances:
            if return_objs:
                return instances
            return [instance.id for instance in instances]
        else:
            return False
    except boto.exception.BotoServerError as exc:
        log.error(exc)
        return False


def terminate(instance_id=None, name=None, region=None,
              key=None, keyid=None, profile=None):
    '''
    Terminate the instance described by instance_id or name.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.terminate name=myinstance
        salt myminion boto_ec2.terminate instance_id=i-a46b9f
    '''
    instances = find_instances(instance_id=instance_id, name=name,
                               region=region, key=key, keyid=keyid,
                               profile=profile, return_objs=True)
    if instances in (False, None):
        return instances

    if len(instances) == 1:
        instances[0].terminate()
        return True
    else:
        log.warning('refusing to terminate multiple instances at once')
        return False


def get_id(name=None, tags=None, region=None, key=None,
           keyid=None, profile=None):

    '''
    Given instace properties, return the instance id if it exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.get_id myinstance

    '''
    instance_ids = find_instances(name=name, tags=tags, region=region, key=key,
                                  keyid=keyid, profile=profile)
    if instance_ids:
        log.info("Instance ids: {0}".format(" ".join(instance_ids)))
        if len(instance_ids) == 1:
            return instance_ids[0]
        else:
            raise CommandExecutionError('Found more than one instance '
                                        'matching the criteria.')
    else:
        log.warning('Could not find instance.')
        return None


def exists(instance_id=None, name=None, tags=None, region=None, key=None,
           keyid=None, profile=None):
    '''
    Given a instance id, check to see if the given instance id exists.

    Returns True if the given an instance with the given id, name, or tags
    exists; otherwise, False is returned.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.exists myinstance
    '''
    instances = find_instances(instance_id=instance_id, name=name, tags=tags,
                               region=region, key=key, keyid=keyid,
                               profile=profile)
    if instances:
        log.info('instance exists.')
        return True
    else:
        log.warning('instance does not exist.')
        return False


def run(image_id, name=None, tags=None, instance_type='m1.small',
        key_name=None, security_groups=None, user_data=None, placement=None,
        region=None, key=None, keyid=None, profile=None):
    '''
    Create and start an EC2 instance.

    Returns True if the instance was created; otherwise False.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.run ami-b80c2b87 name=myinstance

    '''
    #TODO: support multi-instance reservations

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    reservation = conn.run_instances(image_id, instance_type=instance_type,
                                     key_name=key_name,
                                     security_groups=security_groups,
                                     user_data=user_data,
                                     placement=placement)
    if not reservation:
        log.warning('instances could not be reserved')
        return False

    instance = reservation.instances[0]

    status = 'pending'
    while status == 'pending':
        time.sleep(5)
        status = instance.update()
    if status == 'running':
        if name:
            instance.add_tag('Name', name)
        if tags:
            instance.add_tags(tags)
        return True
    else:
        log.warning('instance could not be started -- '
                    'status is "{0}"'.format(status))


def get_key(key_name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if a key exists. Returns fingerprint and name if
    it does and False if it doesn't
    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.get_key mykey
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        key = conn.get_key_pair(key_name)
        log.debug("the key to return is : {0}".format(key))
        if key is None:
            return False
        return key.name, key.fingerprint
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def create_key(key_name, save_path, region=None, key=None, keyid=None,
               profile=None):
    '''
    Creates a key and saves it to a given path.
    Returns the private key.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.create mykey /root/
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        key = conn.create_key_pair(key_name)
        log.debug("the key to return is : {0}".format(key))
        key.save(save_path)
        return key.material
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def import_key(key_name, public_key_material, region=None, key=None,
               keyid=None, profile=None):
    '''
    Imports the public key from an RSA key pair that you created with a third-party tool.
    Supported formats:
    - OpenSSH public key format (e.g., the format in ~/.ssh/authorized_keys)
    - Base64 encoded DER format
    - SSH public key file format as specified in RFC4716
    - DSA keys are not supported. Make sure your key generator is set up to create RSA keys.
    Supported lengths: 1024, 2048, and 4096.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.import mykey publickey
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        key = conn.import_key_pair(key_name, public_key_material)
        log.debug("the key to return is : {0}".format(key))
        return key.fingerprint
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def delete_key(key_name, region=None, key=None, keyid=None, profile=None):
    '''
    Deletes a key. Always returns True

    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.delete_key mykey
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        key = conn.delete_key_pair(key_name)
        log.debug("the key to return is : {0}".format(key))
        return key
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def get_keys(keynames=None, filters=None, region=None, key=None,
             keyid=None, profile=None):
    '''
    Gets all keys or filters them by name and returns a list.
    keynames (list):: A list of the names of keypairs to retrieve.
    If not provided, all key pairs will be returned.
    filters (dict) :: Optional filters that can be used to limit the
    results returned. Filters are provided in the form of a dictionary
    consisting of filter names as the key and filter values as the
    value. The set of allowable filter names/values is dependent on
    the request being performed. Check the EC2 API guide for details.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.get_keys
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        keys = conn.get_all_key_pairs(keynames, filters)
        log.debug("the key to return is : {0}".format(keys))
        key_values = []
        if keys:
            for key in keys:
                key_values.append(key.name)
        return key_values
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def get_attribute(attribute, instance_name=None, instance_id=None, region=None, key=None, keyid=None, profile=None):
    '''
    Get an EC2 instance attribute.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.get_attribute sourceDestCheck instance_name=my_instance

    Available attributes:
        * instanceType
        * kernel
        * ramdisk
        * userData
        * disableApiTermination
        * instanceInitiatedShutdownBehavior
        * rootDeviceName
        * blockDeviceMapping
        * productCodes
        * sourceDestCheck
        * groupSet
        * ebsOptimized
        * sriovNetSupport
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    attribute_list = ['instanceType', 'kernel', 'ramdisk', 'userData', 'disableApiTermination',
                      'instanceInitiatedShutdownBehavior', 'rootDeviceName', 'blockDeviceMapping', 'productCodes',
                      'sourceDestCheck', 'groupSet', 'ebsOptimized', 'sriovNetSupport']
    if not any((instance_name, instance_id)):
        raise SaltInvocationError('At least one of the following must be specified: instance_name or instance_id.')
    if instance_name and instance_id:
        raise SaltInvocationError('Both instance_name and instance_id can not be specified in the same command.')
    if attribute not in attribute_list:
        raise SaltInvocationError('Attribute must be one of: {0}.'.format(attribute_list))
    try:
        if instance_name:
            instances = find_instances(name=instance_name, region=region, key=key, keyid=keyid, profile=profile)
            if len(instances) != 1:
                raise CommandExecutionError('Found more than one EC2 instance matching the criteria.')
            instance_id = instances[0]
        instance_attribute = conn.get_instance_attribute(instance_id, attribute)
        if not instance_attribute:
            return False
        return {attribute: instance_attribute[attribute]}
    except boto.exception.BotoServerError as exc:
        log.error(exc)
        return False


def set_attribute(attribute, attribute_value, instance_name=None, instance_id=None, region=None, key=None, keyid=None,
                  profile=None):
    '''
    Set an EC2 instance attribute.
    Returns whether the operation succeeded or not.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_ec2.set_attribute sourceDestCheck False instance_name=my_instance

    Available attributes:
        * instanceType
        * kernel
        * ramdisk
        * userData
        * disableApiTermination
        * instanceInitiatedShutdownBehavior
        * rootDeviceName
        * blockDeviceMapping
        * productCodes
        * sourceDestCheck
        * groupSet
        * ebsOptimized
        * sriovNetSupport
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    attribute_list = ['instanceType', 'kernel', 'ramdisk', 'userData', 'disableApiTermination',
                      'instanceInitiatedShutdownBehavior', 'rootDeviceName', 'blockDeviceMapping', 'productCodes',
                      'sourceDestCheck', 'groupSet', 'ebsOptimized', 'sriovNetSupport']
    if not any((instance_name, instance_id)):
        raise SaltInvocationError('At least one of the following must be specified: instance_name or instance_id.')
    if instance_name and instance_id:
        raise SaltInvocationError('Both instance_name and instance_id can not be specified in the same command.')
    if attribute not in attribute_list:
        raise SaltInvocationError('Attribute must be one of: {0}.'.format(attribute_list))
    try:
        if instance_name:
            instances = find_instances(name=instance_name, region=region, key=key, keyid=keyid, profile=profile)
            if len(instances) != 1:
                raise CommandExecutionError('Found more than one EC2 instance matching the criteria.')
            instance_id = instances[0]
        attribute = conn.modify_instance_attribute(instance_id, attribute, attribute_value)
        if not attribute:
            return False
        return attribute
    except boto.exception.BotoServerError as exc:
        log.error(exc)
        return False
