# -*- coding: utf-8 -*-
'''
Connection module for Amazon ELB

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit elb credentials but can also utilize
    IAM roles assigned to the instance trough Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        elb.keyid: GKTADJGHEIQSXMKKRBJ08H
        elb.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        elb.region: us-east-1

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
import json

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.ec2
    import boto.ec2.elb as elb
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


def exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an ELB exists.

    CLI example::

        salt myminion boto_elb.exists myelb region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.get_all_load_balancers(load_balancer_names=[name])
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def get_elb_config(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an ELB exists.

    CLI example::

        salt myminion boto_elb.exists myelb region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return []
    try:
        lb = conn.get_all_load_balancers(load_balancer_names=[name])
        lb = lb[0]
        ret = {}
        ret['availability_zones'] = lb.availability_zones
        listeners = []
        for _listener in lb.listeners:
            # Making this a list makes our life easier and is also the only way
            # to include the certificate.
            complex_listener = list(_listener.get_complex_tuple())
            # boto, you're *killing* me with this. boto doesn't include the
            # certificate when calling get_complex_tuple, so you need to also
            # get the certificate. So. Much. Hate.
            if _listener.ssl_certificate_id:
                complex_listener.append(_listener.ssl_certificate_id)
            listeners.append(complex_listener)
        ret['listeners'] = listeners
        ret['subnets'] = lb.subnets
        ret['security_groups'] = lb.security_groups
        ret['scheme'] = lb.scheme
        ret['dns_name'] = lb.dns_name
        return ret
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return []


def create(name, availability_zones, listeners=None, subnets=None,
           security_groups=None, scheme='internet-facing',
           region=None, key=None, keyid=None,
           profile=None):
    '''
    Create an ELB

    CLI example to create an ELB::

        salt myminion boto_elb.create myelb '["us-east-1a", "us-east-1e"]' listeners='[["HTTPS", "HTTP", 443, 80, "arn:aws:iam::1111111:server-certificate/mycert"]]' region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if __salt__['boto_elb.exists'](name, region, key, keyid, profile):
        return True
    if isinstance(availability_zones, string_types):
        availability_zones = json.loads(availability_zones)
    if isinstance(listeners, string_types):
        listeners = json.loads(listeners)
    # Combining listeners and complex_listeners together makes our lives
    # easier in some ways, especially since during introspection you can
    # only get a combined set of listeners back from boto; however, boto
    # requires us to send in separate listeners and complex listeners and
    # the only real difference is the size. It feels like amazon/boto hate
    # developers and wish to make us suffer.
    _listeners = []
    _complex_listeners = []
    for listener in listeners:
        if len(listener) <= 3:
            _listeners.append(listener)
        else:
            _complex_listeners.append(listener)
    try:
        lb = conn.create_load_balancer(name, availability_zones, _listeners,
                                       subnets, security_groups, scheme,
                                       _complex_listeners)
        if lb:
            log.info('Created ELB {0}'.format(name))
            return True
        else:
            msg = 'Failed to create ELB {0}'.format(name)
            log.error(msg)
            return False
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create ELB {0}'.format(name)
        log.error(msg)
        return False


def delete(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete an ELB.

    CLI example to delete an ELB::

        salt myminion boto_elb.delete myelb region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if not __salt__['boto_elb.exists'](name, region, key, keyid, profile):
        return True
    try:
        conn.delete_load_balancer(name)
        msg = 'Deleted ELB {0}.'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete ELB {0}'.format(name)
        log.error(msg)
        return False


def create_listeners(name, listeners=None, region=None, key=None, keyid=None,
                     profile=None):
    '''
    Create listeners on an ELB.

    CLI example::

        salt myminion boto_elb.create_listeners myelb listeners='[["HTTPS", "HTTP", 443, 80, "arn:aws:iam::11  11111:server-certificate/mycert"]]'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if isinstance(listeners, string_types):
        listeners = json.loads(listeners)
    # Combining listeners and complex_listeners together makes our lives
    # easier in some ways, especially since during introspection you can
    # only get a combined set of listeners back from boto; however, boto
    # requires us to send in separate listeners and complex listeners and
    # the only real difference is the size. It feels like amazon/boto hate
    # developers and wish to make us suffer.
    _listeners = []
    _complex_listeners = []
    for listener in listeners:
        if len(listener) <= 3:
            _listeners.append(listener)
        else:
            _complex_listeners.append(listener)
    try:
        conn.create_load_balancer_listeners(name, _listeners,
                                            _complex_listeners)
        msg = 'Created ELB listeners on {0}'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create ELB listeners on {0}'.format(name)
        log.error(msg)
        return False


def delete_listeners(name, ports, region=None, key=None, keyid=None,
                     profile=None):
    '''
    Delete listeners on an ELB.

    CLI example::

        salt myminion boto_elb.delete_listeners myelb '[80,443]'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if isinstance(ports, string_types):
        ports = json.loads(ports)
    try:
        conn.delete_load_balancer_listeners(name, ports)
        msg = 'Deleted ELB listeners on {0}'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete ELB listeners on {0}'.format(name)
        log.error(msg)
        return False


def enable_availability_zones(name, availability_zones, region=None, key=None,
                              keyid=None, profile=None):
    '''
    Enable availability zones for ELB.

    CLI example::

        salt myminion boto_elb.enable_availability_zones myelb '["us-east-1a"]'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if isinstance(availability_zones, string_types):
        availability_zones = json.loads(availability_zones)
    try:
        conn.enable_availability_zones(name, availability_zones)
        msg = 'Enabled availability_zones on ELB {0}'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to enable availability_zones on ELB {0}'.format(name)
        log.error(msg)
        return False


def disable_availability_zones(name, availability_zones, region=None, key=None,
                               keyid=None, profile=None):
    '''
    Disable availability zones for ELB.

    CLI example::

        salt myminion boto_elb.disable_availability_zones myelb '["us-east-1a"]'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if isinstance(availability_zones, string_types):
        availability_zones = json.loads(availability_zones)
    try:
        conn.disable_availability_zones(name, availability_zones)
        msg = 'Disabled availability_zones on ELB {0}'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to disable availability_zones on ELB {0}'.format(name)
        log.error(msg)
        return False


def attach_subnets(name, subnets, region=None, key=None, keyid=None,
                   profile=None):
    '''
    Attach ELB to subnets.

    CLI example::

        salt myminion boto_elb.attach_subnets myelb '["mysubnet"]'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if isinstance(subnets, string_types):
        subnets = json.loads(subnets)
    try:
        conn.attach_lb_to_subnets(name, subnets)
        msg = 'Attached ELB {0} on subnets.'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to attach ELB {0} on subnets.'.format(name)
        log.error(msg)
        return False


def detach_subnets(name, subnets, region=None, key=None, keyid=None,
                   profile=None):
    '''
    Detach ELB from subnets.

    CLI example::

        salt myminion boto_elb.detach_subnets myelb '["mysubnet"]'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if isinstance(subnets, string_types):
        subnets = json.loads(subnets)
    try:
        conn.detach_lb_from_subnets(name, subnets)
        msg = 'Detatched ELB {0} from subnets.'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to detach ELB {0} from subnets.'.format(name)
        log.error(msg)
        return False


def get_attributes(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if attributes are set on an ELB.

    CLI example::

        salt myminion boto_elb.get_attributes myelb
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return {}
    try:
        lbattrs = conn.get_all_lb_attributes(name)
        ret = odict.OrderedDict()
        ret['access_log'] = odict.OrderedDict()
        ret['cross_zone_load_balancing'] = odict.OrderedDict()
        al = lbattrs.access_log
        czlb = lbattrs.cross_zone_load_balancing
        ret['access_log']['enabled'] = al.enabled
        ret['access_log']['s3_bucket_name'] = al.s3_bucket_name
        ret['access_log']['s3_bucket_prefix'] = al.s3_bucket_prefix
        ret['access_log']['emit_interval'] = al.emit_interval
        ret['cross_zone_load_balancing']['enabled'] = czlb.enabled
        return ret
    except boto.exception.BotoServerError as e:
        log.debug(e)
        log.error('ELB {0} does not exist.'.format(name))
        return {}


def set_attributes(name, attributes, region=None, key=None, keyid=None,
                   profile=None):
    '''
    Set attributes on an ELB.

    CLI example to set attributes on an ELB::

        salt myminion boto_elb.set_attributes myelb '{"access_log": {"enabled": "true", "s3_bucket_name": "mybucket", "s3_bucket_prefix": "mylogs/", "emit_interval": "5"}}' region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    al = attributes.get('access_log', {})
    czlb = attributes.get('cross_zone_load_balancing', {})
    if not al and not czlb:
        log.error('No supported attributes for ELB.')
        return False
    if al:
        _al = elb.attributes.AccessLogAttribute()
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
        _czlb = elb.attributes.CrossZoneLoadBalancingAttribute()
        _czlb.enabled = czlb['enabled']
        added_attr = conn.modify_lb_attribute(name, 'crossZoneLoadBalancing',
                                              _czlb.enabled)
        if added_attr:
            msg = 'Added cross_zone_load_balancing attribute to {0} elb.'
            log.info(msg.format(name))
        else:
            log.error('Failed to add cross_zone_load_balancing attribute.')
            return False
    return True


def get_health_check(name, region=None, key=None, keyid=None, profile=None):
    '''
    Get the health check configured for this ELB.

    CLI example::

        salt myminion boto_elb.get_health_check myelb
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return {}
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
    except boto.exception.BotoServerError as e:
        log.debug(e)
        log.error('ELB {0} does not exist.'.format(name))
        return {}


def set_health_check(name, health_check, region=None, key=None, keyid=None,
                     profile=None):
    '''
    Set attributes on an ELB.

    CLI example to set attributes on an ELB::

        salt myminion boto_elb.set_health_check myelb '{"target": "HTTP:80/"}'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    hc = elb.HealthCheck(**health_check)
    try:
        conn.configure_health_check(name, hc)
        log.info('Configured health check on ELB {0}'.format(name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        log.info('Failed to configure health check on ELB {0}'.format(name))
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

    CLI example::

        salt myminion boto_elb.register_instances myelb instance_id
        salt myminion boto_elb.register_instances myelb "[instance_id,instance_id]"
    '''
    # convert instances to list type, enabling consistent use of instances
    # variable throughout the register_instances method
    if isinstance(instances, str) or isinstance(instances, unicode):
        instances = [instances]
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        registered_instances = conn.register_instances(name, instances)
    except boto.exception.BotoServerError as e:
        log.warn(e)
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

    CLI example::

        salt myminion boto_elb.deregister_instances myelb instance_id
        salt myminion boto_elb.deregister_instances myelb "[instance_id, instance_id]"
    '''
    # convert instances to list type, enabling consistent use of instances
    # variable throughout the deregister_instances method
    if isinstance(instances, str) or isinstance(instances, unicode):
        instances = [instances]
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        registered_instances = conn.deregister_instances(name, instances)
    except boto.exception.BotoServerError as e:
        # if the instance(s) given as an argument are not members of the ELB
        # boto returns e.error_code == 'InvalidInstance'
        # deregister_instances returns "None" because the instances are
        # effectively deregistered from ELB
        if e.error_code == 'InvalidInstance':
            log.warn('One or more of instance(s) {0} are not part of ELB {1}.'
                     ' deregister_instances not performed.'
                     .format(instances, name))
            return None
        else:
            log.warn(e)
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

    CLI example::

        salt myminion boto_elb.get_instance_health myelb
        salt myminion boto_elb.get_instance_health myelb region=us-east-1 instances="[instance_id,instance_id]"
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return []
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
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return []


def _get_conn(region, key, keyid, profile):
    '''
    Get a boto connection to ELB.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('elb.region'):
        region = __salt__['config.option']('elb.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('elb.key'):
        key = __salt__['config.option']('elb.key')
    if not keyid and __salt__['config.option']('elb.keyid'):
        keyid = __salt__['config.option']('elb.keyid')

    try:
        conn = elb.connect_to_region(region, aws_access_key_id=keyid,
                                              aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make boto elb connection.')
        return None
    return conn
