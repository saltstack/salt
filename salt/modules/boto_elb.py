# -*- coding: utf-8 -*-
'''
Connection module for Amazon ELB

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit elb credentials but can also utilize
    IAM roles assigned to the instance trough Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        elb.keyid: GKTADJGHEIQSXMKKRBJ08H
        elb.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        elb.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto >= 2.33.0
'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

from __future__ import absolute_import

# Import Python libs
import logging
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module
import json
import salt.ext.six as six

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    # connection settings were added in 2.33.0
    required_boto_version = '2.33.0'
    if (_LooseVersion(boto.__version__) <
            _LooseVersion(required_boto_version)):
        msg = 'boto_elb requires boto {0}.'.format(required_boto_version)
        logging.debug(msg)
        raise ImportError()
    import boto.ec2
    from boto.ec2.elb import HealthCheck
    from boto.ec2.elb.attributes import AccessLogAttribute
    from boto.ec2.elb.attributes import ConnectionDrainingAttribute
    from boto.ec2.elb.attributes import ConnectionSettingAttribute
    from boto.ec2.elb.attributes import CrossZoneLoadBalancingAttribute
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# Import Salt libs
from salt.ext.six import string_types
import salt.utils.odict as odict


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return (False, "The boto_elb module cannot be loaded: boto library not found")
    __utils__['boto.assign_funcs'](__name__, 'elb', module='ec2.elb')
    return True


def exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an ELB exists.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.exists myelb region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        elb = conn.get_all_load_balancers(load_balancer_names=[name])
        if elb:
            return True
        else:
            msg = 'The load balancer does not exist in region {0}'.format(region)
            log.debug(msg)
            return False
    except boto.exception.BotoServerError as error:
        log.debug(error)
        return False


def get_elb_config(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an ELB exists.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.exists myelb region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        lb = conn.get_all_load_balancers(load_balancer_names=[name])
        lb = lb[0]
        ret = {}
        ret['availability_zones'] = lb.availability_zones
        listeners = []
        for _listener in lb.listeners:
            listener_dict = {}
            listener_dict['elb_port'] = _listener.load_balancer_port
            listener_dict['elb_protocol'] = _listener.protocol
            listener_dict['instance_port'] = _listener.instance_port
            listener_dict['instance_protocol'] = _listener.instance_protocol
            listener_dict['policies'] = _listener.policy_names
            if _listener.ssl_certificate_id:
                listener_dict['certificate'] = _listener.ssl_certificate_id
            listeners.append(listener_dict)
        ret['listeners'] = listeners
        backends = []
        for _backend in lb.backends:
            bs_dict = {}
            bs_dict['instance_port'] = _backend.instance_port
            bs_dict['policies'] = [p.policy_name for p in _backend.policies]
            backends.append(bs_dict)
        ret['backends'] = backends
        ret['subnets'] = lb.subnets
        ret['security_groups'] = lb.security_groups
        ret['scheme'] = lb.scheme
        ret['dns_name'] = lb.dns_name
        ret['tags'] = _get_all_tags(conn, name)
        lb_policy_lists = [
            lb.policies.app_cookie_stickiness_policies,
            lb.policies.lb_cookie_stickiness_policies,
            lb.policies.other_policies
            ]
        policies = []
        for policy_list in lb_policy_lists:
            policies += [p.policy_name for p in policy_list]
        ret['policies'] = policies
        return ret
    except boto.exception.BotoServerError as error:
        log.debug(error)
        return {}


def listener_dict_to_tuple(listener):
    '''
    Convert an ELB listener dict into a listener tuple used by certain parts of
    the AWS ELB API.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.listener_dict_to_tuple '{"elb_port":80,"instance_port":80,"elb_protocol":"HTTP"}'
    '''
    # We define all listeners as complex listeners.
    if 'instance_protocol' not in listener:
        instance_protocol = listener['elb_protocol'].upper()
    else:
        instance_protocol = listener['instance_protocol'].upper()
    listener_tuple = [listener['elb_port'], listener['instance_port'],
                      listener['elb_protocol'], instance_protocol]
    if 'certificate' in listener:
        listener_tuple.append(listener['certificate'])
    return tuple(listener_tuple)


def create(name, availability_zones, listeners, subnets=None,
           security_groups=None, scheme='internet-facing',
           region=None, key=None, keyid=None,
           profile=None):
    '''
    Create an ELB

    CLI example to create an ELB:

    .. code-block:: bash

        salt myminion boto_elb.create myelb '["us-east-1a", "us-east-1e"]' '{"elb_port": 443, "elb_protocol": "HTTPS", ...}' region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if exists(name, region, key, keyid, profile):
        return True
    if isinstance(availability_zones, string_types):
        availability_zones = json.loads(availability_zones)

    if isinstance(listeners, string_types):
        listeners = json.loads(listeners)

    _complex_listeners = []
    for listener in listeners:
        _complex_listeners.append(listener_dict_to_tuple(listener))
    try:
        lb = conn.create_load_balancer(name, availability_zones, [],
                                       subnets, security_groups, scheme,
                                       _complex_listeners)
        if lb:
            log.info('Created ELB {0}'.format(name))
            return True
        else:
            msg = 'Failed to create ELB {0}'.format(name)
            log.error(msg)
            return False
    except boto.exception.BotoServerError as error:
        log.debug(error)
        msg = 'Failed to create ELB {0}: {1}'.format(name, error)
        log.error(msg)
        return False


def delete(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete an ELB.

    CLI example to delete an ELB:

    .. code-block:: bash

        salt myminion boto_elb.delete myelb region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not exists(name, region, key, keyid, profile):
        return True
    try:
        conn.delete_load_balancer(name)
        msg = 'Deleted ELB {0}.'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as error:
        log.debug(error)
        msg = 'Failed to delete ELB {0}'.format(name)
        log.error(msg)
        return False


def create_listeners(name, listeners, region=None, key=None, keyid=None,
                     profile=None):
    '''
    Create listeners on an ELB.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.create_listeners myelb '[["HTTPS", "HTTP", 443, 80, "arn:aws:iam::11  11111:server-certificate/mycert"]]'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(listeners, string_types):
        listeners = json.loads(listeners)

    _complex_listeners = []
    for listener in listeners:
        _complex_listeners.append(listener_dict_to_tuple(listener))
    try:
        conn.create_load_balancer_listeners(name, [], _complex_listeners)
        msg = 'Created ELB listeners on {0}'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as error:
        log.debug(error)
        msg = 'Failed to create ELB listeners on {0}: {1}'.format(name, error)
        log.error(msg)
        return False


def delete_listeners(name, ports, region=None, key=None, keyid=None,
                     profile=None):
    '''
    Delete listeners on an ELB.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.delete_listeners myelb '[80,443]'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(ports, string_types):
        ports = json.loads(ports)
    try:
        conn.delete_load_balancer_listeners(name, ports)
        msg = 'Deleted ELB listeners on {0}'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as error:
        log.debug(error)
        msg = 'Failed to delete ELB listeners on {0}: {1}'.format(name, error)
        log.error(msg)
        return False


def apply_security_groups(name, security_groups, region=None, key=None,
                          keyid=None, profile=None):
    '''
    Apply security groups to ELB.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.apply_security_groups myelb '["mysecgroup1"]'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(security_groups, string_types):
        security_groups = json.loads(security_groups)
    try:
        conn.apply_security_groups_to_lb(name, security_groups)
        msg = 'Applied security_groups on ELB {0}'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to appply security_groups on ELB {0}: {1}'
        msg = msg.format(name, e.message)
        log.error(msg)
        return False


def enable_availability_zones(name, availability_zones, region=None, key=None,
                              keyid=None, profile=None):
    '''
    Enable availability zones for ELB.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.enable_availability_zones myelb '["us-east-1a"]'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(availability_zones, string_types):
        availability_zones = json.loads(availability_zones)
    try:
        conn.enable_availability_zones(name, availability_zones)
        msg = 'Enabled availability_zones on ELB {0}'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as error:
        log.debug(error)
        msg = 'Failed to enable availability_zones on ELB {0}: {1}'.format(name, error)
        log.error(msg)
        return False


def disable_availability_zones(name, availability_zones, region=None, key=None,
                               keyid=None, profile=None):
    '''
    Disable availability zones for ELB.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.disable_availability_zones myelb '["us-east-1a"]'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(availability_zones, string_types):
        availability_zones = json.loads(availability_zones)
    try:
        conn.disable_availability_zones(name, availability_zones)
        msg = 'Disabled availability_zones on ELB {0}'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as error:
        log.debug(error)
        msg = 'Failed to disable availability_zones on ELB {0}: {1}'.format(name, error)
        log.error(msg)
        return False


def attach_subnets(name, subnets, region=None, key=None, keyid=None,
                   profile=None):
    '''
    Attach ELB to subnets.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.attach_subnets myelb '["mysubnet"]'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(subnets, string_types):
        subnets = json.loads(subnets)
    try:
        conn.attach_lb_to_subnets(name, subnets)
        msg = 'Attached ELB {0} on subnets.'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as error:
        log.debug(error)
        msg = 'Failed to attach ELB {0} on subnets: {1}'.format(name, error)
        log.error(msg)
        return False


def detach_subnets(name, subnets, region=None, key=None, keyid=None,
                   profile=None):
    '''
    Detach ELB from subnets.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.detach_subnets myelb '["mysubnet"]'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(subnets, string_types):
        subnets = json.loads(subnets)
    try:
        conn.detach_lb_from_subnets(name, subnets)
        msg = 'Detached ELB {0} from subnets.'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as error:
        log.debug(error)
        msg = 'Failed to detach ELB {0} from subnets: {1}'.format(name, error)
        log.error(msg)
        return False


def get_attributes(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if attributes are set on an ELB.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.get_attributes myelb
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        lbattrs = conn.get_all_lb_attributes(name)
        ret = odict.OrderedDict()
        ret['access_log'] = odict.OrderedDict()
        ret['cross_zone_load_balancing'] = odict.OrderedDict()
        ret['connection_draining'] = odict.OrderedDict()
        ret['connecting_settings'] = odict.OrderedDict()
        al = lbattrs.access_log
        czlb = lbattrs.cross_zone_load_balancing
        cd = lbattrs.connection_draining
        cs = lbattrs.connecting_settings
        ret['access_log']['enabled'] = al.enabled
        ret['access_log']['s3_bucket_name'] = al.s3_bucket_name
        ret['access_log']['s3_bucket_prefix'] = al.s3_bucket_prefix
        ret['access_log']['emit_interval'] = al.emit_interval
        ret['cross_zone_load_balancing']['enabled'] = czlb.enabled
        ret['connection_draining']['enabled'] = cd.enabled
        ret['connection_draining']['timeout'] = cd.timeout
        ret['connecting_settings']['idle_timeout'] = cs.idle_timeout
        return ret
    except boto.exception.BotoServerError as error:
        log.debug(error)
        log.error('ELB {0} does not exist: {1}'.format(name, error))
        return {}


def set_attributes(name, attributes, region=None, key=None, keyid=None,
                   profile=None):
    '''
    Set attributes on an ELB.

    CLI example to set attributes on an ELB:

    .. code-block:: bash

        salt myminion boto_elb.set_attributes myelb '{"access_log": {"enabled": "true", "s3_bucket_name": "mybucket", "s3_bucket_prefix": "mylogs/", "emit_interval": "5"}}' region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    al = attributes.get('access_log', {})
    czlb = attributes.get('cross_zone_load_balancing', {})
    cd = attributes.get('connection_draining', {})
    cs = attributes.get('connecting_settings', {})
    if not al and not czlb and not cd and not cs:
        log.error('No supported attributes for ELB.')
        return False
    if al:
        _al = AccessLogAttribute()
        _al.enabled = al.get('enabled', False)
        if not _al.enabled:
            msg = 'Access log attribute configured, but enabled config missing'
            log.error(msg)
            return False
        _al.s3_bucket_name = al.get('s3_bucket_name', None)
        _al.s3_bucket_prefix = al.get('s3_bucket_prefix', None)
        _al.emit_interval = al.get('emit_interval', None)
        added_attr = conn.modify_lb_attribute(name, 'accessLog', _al)
        if added_attr:
            log.info('Added access_log attribute to {0} elb.'.format(name))
        else:
            msg = 'Failed to add access_log attribute to {0} elb.'
            log.error(msg.format(name))
            return False
    if czlb:
        _czlb = CrossZoneLoadBalancingAttribute()
        _czlb.enabled = czlb['enabled']
        added_attr = conn.modify_lb_attribute(name, 'crossZoneLoadBalancing',
                                              _czlb.enabled)
        if added_attr:
            msg = 'Added cross_zone_load_balancing attribute to {0} elb.'
            log.info(msg.format(name))
        else:
            log.error('Failed to add cross_zone_load_balancing attribute.')
            return False
    if cd:
        _cd = ConnectionDrainingAttribute()
        _cd.enabled = cd['enabled']
        _cd.timeout = cd.get('timeout', 300)
        added_attr = conn.modify_lb_attribute(name, 'connectionDraining', _cd)
        if added_attr:
            msg = 'Added connection_draining attribute to {0} elb.'
            log.info(msg.format(name))
        else:
            log.error('Failed to add connection_draining attribute.')
            return False
    if cs:
        _cs = ConnectionSettingAttribute()
        _cs.idle_timeout = cs.get('idle_timeout', 60)
        added_attr = conn.modify_lb_attribute(name, 'connectingSettings', _cs)
        if added_attr:
            msg = 'Added connecting_settings attribute to {0} elb.'
            log.info(msg.format(name))
        else:
            log.error('Failed to add connecting_settings attribute.')
            return False
    return True


def get_health_check(name, region=None, key=None, keyid=None, profile=None):
    '''
    Get the health check configured for this ELB.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.get_health_check myelb
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        lb = conn.get_all_load_balancers(load_balancer_names=[name])
        lb = lb[0]
        ret = odict.OrderedDict()
        hc = lb.health_check
        ret['interval'] = hc.interval
        ret['target'] = hc.target
        ret['healthy_threshold'] = hc.healthy_threshold
        ret['timeout'] = hc.timeout
        ret['unhealthy_threshold'] = hc.unhealthy_threshold
        return ret
    except boto.exception.BotoServerError as error:
        log.debug(error)
        log.error('ELB {0} does not exist: {1}'.format(name, error))
        return {}


def set_health_check(name, health_check, region=None, key=None, keyid=None,
                     profile=None):
    '''
    Set attributes on an ELB.

    CLI example to set attributes on an ELB:

    .. code-block:: bash

        salt myminion boto_elb.set_health_check myelb '{"target": "HTTP:80/"}'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    hc = HealthCheck(**health_check)
    try:
        conn.configure_health_check(name, hc)
        log.info('Configured health check on ELB {0}'.format(name))
    except boto.exception.BotoServerError as error:
        log.debug(error)
        log.info('Failed to configure health check on ELB {0}: {1}'.format(name, error))
        return False
    return True


def register_instances(name, instances, region=None, key=None, keyid=None,
                       profile=None):
    '''
    Register instances with an ELB.  Instances is either a string
    instance id or a list of string instance id's.

    Returns:

    - ``True``: instance(s) registered successfully
    - ``False``: instance(s) failed to be registered

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.register_instances myelb instance_id
        salt myminion boto_elb.register_instances myelb "[instance_id,instance_id]"
    '''
    # convert instances to list type, enabling consistent use of instances
    # variable throughout the register_instances method
    if isinstance(instances, str) or isinstance(instances, six.text_type):
        instances = [instances]
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        registered_instances = conn.register_instances(name, instances)
    except boto.exception.BotoServerError as error:
        log.warn(error)
        return False
    registered_instance_ids = [instance.id for instance in
                               registered_instances]
    # register_failues is a set that will contain any instances that were not
    # able to be registered with the given ELB
    register_failures = set(instances).difference(set(registered_instance_ids))
    if register_failures:
        log.warn('Instance(s): {0} not registered with ELB {1}.'
                 .format(list(register_failures), name))
        register_result = False
    else:
        register_result = True
    return register_result


def deregister_instances(name, instances, region=None, key=None, keyid=None,
                         profile=None):
    '''
    Deregister instances with an ELB.  Instances is either a string
    instance id or a list of string instance id's.

    Returns:

    - ``True``: instance(s) deregistered successfully
    - ``False``: instance(s) failed to be deregistered
    - ``None``: instance(s) not valid or not registered, no action taken

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.deregister_instances myelb instance_id
        salt myminion boto_elb.deregister_instances myelb "[instance_id, instance_id]"
    '''
    # convert instances to list type, enabling consistent use of instances
    # variable throughout the deregister_instances method
    if isinstance(instances, str) or isinstance(instances, six.text_type):
        instances = [instances]
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        registered_instances = conn.deregister_instances(name, instances)
    except boto.exception.BotoServerError as error:
        # if the instance(s) given as an argument are not members of the ELB
        # boto returns error.error_code == 'InvalidInstance'
        # deregister_instances returns "None" because the instances are
        # effectively deregistered from ELB
        if error.error_code == 'InvalidInstance':
            log.warn('One or more of instance(s) {0} are not part of ELB {1}.'
                     ' deregister_instances not performed.'
                     .format(instances, name))
            return None
        else:
            log.warn(error)
            return False
    registered_instance_ids = [instance.id for instance in
                               registered_instances]
    # deregister_failures is a set that will contain any instances that were
    # unable to be deregistered from the given ELB
    deregister_failures = set(instances).intersection(set(registered_instance_ids))
    if deregister_failures:
        log.warn('Instance(s): {0} not deregistered from ELB {1}.'
                 .format(list(deregister_failures), name))
        deregister_result = False
    else:
        deregister_result = True
    return deregister_result


def get_instance_health(name, region=None, key=None, keyid=None, profile=None, instances=None):
    '''
    Get a list of instances and their health state

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.get_instance_health myelb
        salt myminion boto_elb.get_instance_health myelb region=us-east-1 instances="[instance_id,instance_id]"
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        instance_states = conn.describe_instance_health(name, instances)
        ret = []
        for _instance in instance_states:
            ret.append({'instance_id': _instance.instance_id,
                        'description': _instance.description,
                        'state': _instance.state,
                        'reason_code': _instance.reason_code
                        })
        return ret
    except boto.exception.BotoServerError as error:
        log.debug(error)
        return []


def create_policy(name, policy_name, policy_type, policy, region=None,
                  key=None, keyid=None, profile=None):
    '''
    Create an ELB policy.

    .. versionadded:: Boron

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.create_policy myelb mypolicy LBCookieStickinessPolicyType '{"CookieExpirationPeriod": 3600}'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not exists(name, region, key, keyid, profile):
        return False
    try:
        success = conn.create_lb_policy(name, policy_name, policy_type, policy)
        if success:
            log.info('Created policy {0} on ELB {1}'.format(policy_name, name))
            return True
        else:
            msg = 'Failed to create policy {0} on ELB {1}'.format(policy_name, name)
            log.error(msg)
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create policy {0} on ELB {1}: {2}'.format(policy_name, name, e.message)
        log.error(msg)
        return False


def delete_policy(name, policy_name, region=None, key=None, keyid=None,
                  profile=None):
    '''
    Delete an ELB policy.

    .. versionadded:: Boron

    CLI example:

    .. code-block:: bash

        salt myminion boto_elb.delete_policy myelb mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not exists(name, region, key, keyid, profile):
        return True
    try:
        conn.delete_lb_policy(name, policy_name)
        log.info('Deleted policy {0} on ELB {1}'.format(policy_name, name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete policy {0} on ELB {1}: {2}'.format(policy_name, name, e.message)
        log.error(msg)
        return False


def set_listener_policy(name, port, policies=None, region=None, key=None,
                        keyid=None, profile=None):
    '''
    Set the policies of an ELB listener.

    .. versionadded:: Boron

    CLI example:

    .. code-block:: Bash

        salt myminion boto_elb.set_listener_policy myelb 443 "[policy1,policy2]"
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not exists(name, region, key, keyid, profile):
        return True
    if policies is None:
        policies = []
    try:
        conn.set_lb_policies_of_listener(name, port, policies)
        log.info('Set policies {0} on ELB {1} listener {2}'.format(policies, name, port))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        log.info('Failed to set policy {0} on ELB {1} listener {2}: {3}'.format(policies, name, port, e.message))
        return False
    return True


def set_backend_policy(name, port, policies=None, region=None, key=None,
                       keyid=None, profile=None):
    '''
    Set the policies of an ELB backend server.

    CLI example:

        salt myminion boto_elb.set_backend_policy myelb 443 "[policy1,policy2]"
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not exists(name, region, key, keyid, profile):
        return True
    if policies is None:
        policies = []
    try:
        conn.set_lb_policies_of_backend_server(name, port, policies)
        log.info('Set policies {0} on ELB {1} backend server {2}'.format(policies, name, port))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        log.info('Failed to set policy {0} on ELB {1} backend server {2}: {3}'.format(policies, name, port, e.message))
        return False
    return True


def set_tags(name, tags, region=None, key=None, keyid=None, profile=None):
    '''
    Add the tags on an ELB

    .. versionadded:: Boron

    name
        name of the ELB

    tags
        dict of name/value pair tags

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.set_tags my-elb-name "{'Tag1': 'Value', 'Tag2': 'Another Value'}"
    '''

    if exists(name, region, key, keyid, profile):
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        ret = _add_tags(conn, name, tags)
        return ret
    else:
        return False


def delete_tags(name, tags, region=None, key=None, keyid=None, profile=None):
    '''
    Add the tags on an ELB

    name
        name of the ELB

    tags
        list of tags to remove

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.delete_tags my-elb-name ['TagToRemove1', 'TagToRemove2']
    '''
    if exists(name, region, key, keyid, profile):
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        ret = _remove_tags(conn, name, tags)
        return ret
    else:
        return False


def _build_tag_param_list(params, tags):
    '''
    helper function to build a tag parameter list to send
    '''
    keys = sorted(tags.keys())
    i = 1
    for key in keys:
        value = tags[key]
        params['Tags.member.{0}.Key'.format(i)] = key
        if value is not None:
            params['Tags.member.{0}.Value'.format(i)] = value
        i += 1


def _get_all_tags(conn, load_balancer_names=None):
    '''
    Retrieve all the metadata tags associated with your ELB(s).

    :type load_balancer_names: list
    :param load_balancer_names: An optional list of load balancer names.

    :rtype: list
    :return: A list of :class:`boto.ec2.elb.tag.Tag` objects
    '''
    params = {}
    if load_balancer_names:
        conn.build_list_params(params, load_balancer_names,
                               'LoadBalancerNames.member.%d')

    tags = conn.get_object(
        'DescribeTags',
        params,
        __utils__['boto_elb_tag.get_tag_descriptions'](),
        verb='POST'
    )
    if tags[load_balancer_names]:
        return tags[load_balancer_names]
    else:
        return None


def _add_tags(conn, load_balancer_names, tags):
    '''
    Create new metadata tags for the specified resource ids.

    :type load_balancer_names: list
    :param load_balancer_names: A list of load balancer names.

    :type tags: dict
    :param tags: A dictionary containing the name/value pairs.
                 If you want to create only a tag name, the
                 value for that tag should be the empty string
                 (e.g. '').
    '''
    params = {}
    conn.build_list_params(params, load_balancer_names,
                           'LoadBalancerNames.member.%d')
    _build_tag_param_list(params, tags)
    return conn.get_status('AddTags', params, verb='POST')


def _remove_tags(conn, load_balancer_names, tags):
    '''
    Delete metadata tags for the specified resource ids.

    :type load_balancer_names: list
    :param load_balancer_names: A list of load balancer names.

    :type tags: list
    :param tags: A list containing just tag names for the tags to be
                 deleted.
    '''
    params = {}
    conn.build_list_params(params, load_balancer_names,
                           'LoadBalancerNames.member.%d')
    conn.build_list_params(params, tags,
                           'Tags.member.%d.Key')
    return conn.get_status('RemoveTags', params, verb='POST')
