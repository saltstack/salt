# -*- coding: utf-8 -*-
'''
Connection module for Amazon EC2

.. versionadded:: TBD

:configuration: This module accepts explicit EC2 credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        ec2.keyid: GKTADJGHEIQSXMKKRBJ08H
        ec2.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        ec2.region: us-east-1

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
from __future__ import absolute_import
import logging
import time
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module

# Import Salt libs
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Import third party libs
import salt.ext.six as six
# pylint: disable=import-error
try:
    # pylint: disable=import-error
    import boto
    import boto.ec2
    # pylint: enable=import-error
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=import-error


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
        return True


def find_instances(instance_id=None, name=None, tags=None, region=None,
                   key=None, keyid=None, profile=None, **kwargs):

    '''
    Given instance properties, find and return matching instance ids

    CLI examples::
    .. code-block:: bash

        salt myminion boto_ec2.find_instances # Lists all instances
        salt myminion boto_ec2.find_instances name=myinstance
        salt myminion boto_ec2.find_instances tags='{"mytag": "value"}'

    '''
    conn = _get_conn(region, key, keyid, profile, kwargs)
    if not conn:
        return False

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
            if kwargs.get('return_objs'):
                return instances
            return [instance.id for instance in instances]
        else:
            return False
    except boto.exception.BotoServerError as exc:
        log.error(exc)
        return False


def terminate(instance_id=None, name=None, region=None,
              key=None, keyid=None, profile=None, **kwargs):
    instances = find_instances(instance_id=instance_id, name=name,
                               region=region, key=key, keyid=keyid,
                               profile=profile, return_objs=True, **kwargs)
    if instances in (False, None):
        return instances

    if len(instances) == 1:
        instances[0].terminate()
        return True
    else:
        log.warning('refusing to terminate multiple instances at once')
        return False


def get_id(name=None, tags=None, region=None, key=None,
           keyid=None, profile=None, **kwargs):

    '''
    Given instace properties, return the instance id if it exist.

    CLI example::

    .. code-block:: bash

        salt myminion boto_ec2.get_id myinstance

    '''
    conn = _get_conn(region, key, keyid, profile, kwargs)
    if not conn:
        return None

    instance_ids = find_instances(name=name, tags=tags, conn=conn)
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
           keyid=None, profile=None, **kwargs):
    '''
    Given a instance id, check to see if the given instance id exists.

    Returns True if the given an instance with the given id, name, or tags
    exists; otherwise, False is returned.

    CLI example::

    .. code-block:: bash

        salt myminion boto_ec2.exists myinstance

    '''
    conn = _get_conn(region, key, keyid, profile, kwargs)
    if not conn:
        return False

    instances = find_instances(instance_id=instance_id, name=name, tags=tags, conn=conn)
    if instances:
        log.info('instance exists.')
        return True
    else:
        log.warning('instance does not exist.')
        return False


def run(image_id, name=None, tags=None, instance_type='m1.small',
        key_name=None, security_groups=None, user_data=None, placement=None,
        region=None, key=None, keyid=None, profile=None, **kwargs):
    '''
    Create and start an EC2 instance.

    Returns True if the instance was created; otherwise False.

    CLI example::

    .. code-block:: bash

        salt myminion boto_ec2.run ami-b80c2b87 name=myinstance

    '''
    #TODO: support multi-instance reservations

    conn = _get_conn(region, key, keyid, profile, kwargs)
    if not conn:
        return False

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
        return False


def _get_conn(region, key, keyid, profile, kwargs):
    '''
    Get a boto connection to ec2.
    '''
    if kwargs and 'conn' in kwargs:
        return kwargs['conn']

    if profile:
        if isinstance(profile, six.string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('ec2.region'):
        region = __salt__['config.option']('ec2.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('ec2.key'):
        key = __salt__['config.option']('ec2.key')
    if not keyid and __salt__['config.option']('ec2.keyid'):
        keyid = __salt__['config.option']('ec2.keyid')

    try:
        conn = boto.ec2.connect_to_region(region, aws_access_key_id=keyid,
                                          aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make boto autoscale connection.')
        return None
    return conn
