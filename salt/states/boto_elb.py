# -*- coding: utf-8 -*-
'''
Manage ELBs

.. versionadded:: 2014.7.0

Create and destroy ELBs. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit elb credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    elb.keyid: GKTADJGHEIQSXMKKRBJ08H
    elb.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        region: us-east-1

.. code-block:: yaml

    Ensure myelb ELB exists:
        boto_elb.present:
            - name: myelb
            - region: us-east-1
            - availability_zones:
                - us-east-1a
                - us-east-1c
                - us-east-1d
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            - listeners:
                - elb_port: 443
                  instance_port: 80
                  elb_protocol: HTTPS
                  instance_protocol: HTTP
                  certificate: 'arn:aws:iam::1111111:server-certificate/mycert'
                  policies:
                      - my-ssl-policy
                      - cookie-policy
                - elb_port: 8210
                  instance_port: 8210
                  elb_protocol: TCP
            - backends:
                - instance_port: 80
                  policies:
                      - enable-proxy-protocol
            - health_check:
                target: 'HTTP:80/'
            - attributes:
                cross_zone_load_balancing:
                  enabled: true
                access_log:
                  enabled: true
                  s3_bucket_name: 'mybucket'
                  s3_bucket_prefix: 'my-logs'
                  emit_interval: 5
                connecting_settings:
                  idle_timeout: 60
            - cnames:
                - name: mycname.example.com.
                  zone: example.com.
                  ttl: 60
                - name: myothercname.example.com.
                  zone: example.com.
            - security_groups:
                - my-security-group
            - policies:
                - policy_name: my-ssl-policy
                  policy_type: SSLNegotiationPolicyType
                  policy:
                    Protocol-TLSv1.2: true
                    Protocol-SSLv3: false
                    Server-Defined-Cipher-Order: true
                    ECDHE-ECDSA-AES128-GCM-SHA256: true
                - policy_name: cookie-policy
                  policy_type: LBCookieStickinessPolicyType
                  policy: {}  # no policy means this is a session cookie
                - policy_name: enable-proxy-protocol
                  policy_type: ProxyProtocolPolicyType
                  policy:
                    ProxyProtocol: true

    # Using a profile from pillars
    Ensure myelb ELB exists:
        boto_elb.present:
            - name: myelb
            - region: us-east-1
            - profile: myelbprofile

    # Passing in a profile
    Ensure myelb ELB exists:
        boto_elb.present:
            - name: myelb
            - region: us-east-1
            - profile:
                keyid: GKTADJGHEIQSXMKKRBJ08H
                key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's possible to specify attributes from pillars by specifying a pillar. You
can override the values defined in the pillard by setting the attributes on the
resource. The module will use the default pillar key 'boto_elb_attributes',
which allows you to set default attributes for all ELB resources.

Setting the attributes pillar:

.. code-block:: yaml

    my_elb_attributes:
      cross_zone_load_balancing:
        enabled: true
      connection_draining:
        enabled: true
        timeout: 20
      access_log:
        enabled: true
        s3_bucket_name: 'mybucket'
        s3_bucket_prefix: 'my-logs'
        emit_interval: 5

Overriding the attribute values on the resource:

.. code-block:: yaml

    Ensure myelb ELB exists:
        boto_elb.present:
            - name: myelb
            - region: us-east-1
            - attributes_from_pillar: my_elb_attributes
            # override cross_zone_load_balancing:enabled
            - attributes:
                cross_zone_load_balancing:
                  enabled: false
            - profile: myelbprofile

It's possible to specify cloudwatch alarms that will be setup along with the
ELB. Note the alarm name will be defined by the name attribute provided, plus
the ELB resource name.

.. code-block:: yaml

    Ensure myelb ELB exists:
        boto_elb.present:
            - name: myelb
            - region: us-east-1
            - profile: myelbprofile
            - alarms:
                UnHealthyHostCount:
                  name: 'ELB UnHealthyHostCount **MANAGED BY SALT**'
                  attributes:
                    metric: UnHealthyHostCount
                    namespace: AWS/ELB
                    statistic: Average
                    comparison: '>='
                    threshold: 1.0
                    period: 600
                    evaluation_periods: 6
                    unit: null
                    description: ELB UnHealthyHostCount
                    alarm_actions: ['arn:aws:sns:us-east-1:12345:myalarm']
                    insufficient_data_actions: []
                    ok_actions: ['arn:aws:sns:us-east-1:12345:myalarm']

You can also use alarms from pillars, and override values from the pillar
alarms by setting overrides on the resource. Note that 'boto_elb_alarms'
will be used as a default value for all resources, if defined and can be
used to ensure alarms are always set for a resource.

Setting the alarms in a pillar:

.. code-block:: yaml

    my_elb_alarm:
      UnHealthyHostCount:
        name: 'ELB UnHealthyHostCount **MANAGED BY SALT**'
        attributes:
          metric: UnHealthyHostCount
          namespace: AWS/ELB
          statistic: Average
          comparison: '>='
          threshold: 1.0
          period: 600
          evaluation_periods: 6
          unit: null
          description: ELB UnHealthyHostCount
          alarm_actions: ['arn:aws:sns:us-east-1:12345:myalarm']
          insufficient_data_actions: []
          ok_actions: ['arn:aws:sns:us-east-1:12345:myalarm']

Overriding the alarm values on the resource:

.. code-block:: yaml

    Ensure myelb ELB exists:
        boto_elb.present:
            - name: myelb
            - region: us-east-1
            - profile: myelbprofile
            - alarms_from_pillar: my_elb_alarm
            # override UnHealthyHostCount:attributes:threshold
            - alarms:
                UnHealthyHostCount:
                  attributes:
                    threshold: 2.0

Tags can also be set:

.. versionadded:: 2016.3.0

.. code-block:: yaml

    Ensure myelb ELB exists:
        boto_elb.present:
            - name: myelb
            - region: us-east-1
            - profile: myelbprofile
            - tags:
                MyTag: 'My Tag Value'
                OtherTag: 'My Other Value'
'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import hashlib
import re
import salt.utils.dictupdate as dictupdate
from salt.utils import exactly_one
from salt.exceptions import SaltInvocationError
import salt.ext.six as six

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_elb' if 'boto_elb.exists' in __salt__ else False


def present(
        name,
        listeners,
        availability_zones=None,
        subnets=None,
        subnet_names=None,
        security_groups=None,
        scheme='internet-facing',
        health_check=None,
        attributes=None,
        attributes_from_pillar="boto_elb_attributes",
        cnames=None,
        alarms=None,
        alarms_from_pillar="boto_elb_alarms",
        policies=None,
        policies_from_pillar="boto_elb_policies",
        backends=None,
        region=None,
        key=None,
        keyid=None,
        profile=None,
        wait_for_sync=True,
        tags=None,
        instance_ids=None,
        instance_names=None):
    '''
    Ensure the ELB exists.

    name
        Name of the ELB.

    availability_zones
        A list of availability zones for this ELB.

    listeners
        A list of listener lists; example::

            [
                ['443', 'HTTPS', 'arn:aws:iam::1111111:server-certificate/mycert'],
                ['8443', '80', 'HTTPS', 'HTTP', 'arn:aws:iam::1111111:server-certificate/mycert']
            ]

    subnets
        A list of subnet IDs in your VPC to attach to your LoadBalancer.

    subnet_names
        A list of subnet names in your VPC to attach to your LoadBalancer.

    security_groups
        The security groups assigned to your LoadBalancer within your VPC. Must
        be passed either as a list or a comma-separated string.

        For example, a list:

        .. code-block:: yaml

            - security_groups:
              - secgroup-one
              - secgroup-two

        Or as a comma-separated string:

        .. code-block:: yaml

            - security_groups: secgroup-one,secgroup-two

    scheme
        The type of a LoadBalancer, ``internet-facing`` or ``internal``. Once
        set, can not be modified.

    health_check
        A dict defining the health check for this ELB.

    attributes
        A dict defining the attributes to set on this ELB.
        Unknown keys will be silently ignored.

        See the :mod:`salt.modules.boto_elb.set_attributes` function for
        recognized attributes.

    attributes_from_pillar
        name of pillar dict that contains attributes.   Attributes defined for this specific
        state will override those from pillar.

    cnames
        A list of cname dicts with attributes needed for the DNS add_record state.
        By default the boto_route53.add_record state will be used, which requires: name, zone, ttl, and identifier.
        See the boto_route53 state for information about these attributes.
        Other DNS modules can be called by specifying the provider keyword.
        the cnames dict will be passed to the state as kwargs.

        See the :mod:`salt.states.boto_route53` state for information about
        these attributes.

    alarms:
        a dictionary of name->boto_cloudwatch_alarm sections to be associated with this ELB.
        All attributes should be specified except for dimension which will be
        automatically set to this ELB.

        See the :mod:`salt.states.boto_cloudwatch_alarm` state for information
        about these attributes.

    alarms_from_pillar:
        name of pillar dict that contains alarm settings.   Alarms defined for this specific
        state will override those from pillar.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.

    wait_for_sync
        Wait for an INSYNC change status from Route53.

    tags
        dict of tags

    instance_ids
        list of instance ids.  The state will ensure that these, and ONLY these, instances
        are registered with the ELB.  This is additive with instance_names.

    instance_names
        list of instance names.  The state will ensure that these, and ONLY these, instances
        are registered with the ELB.  This is additive with instance_ids.
    '''

    # load data from attributes_from_pillar and merge with attributes
    tmp = __salt__['config.option'](attributes_from_pillar, {})
    if attributes:
        attributes = dictupdate.update(tmp, attributes)
    else:
        attributes = tmp

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if security_groups:
        if isinstance(security_groups, six.string_types):
            security_groups = security_groups.split(',')
        elif not isinstance(security_groups, list):
            ret['result'] = False
            ret['comment'] = 'The \'security_group\' parameter must either be a list or ' \
                             'a comma-separated string.'
            return ret

    _ret = _elb_present(name, availability_zones, listeners, subnets, subnet_names,
                        security_groups, scheme, region, key, keyid, profile)
    ret['changes'] = _ret['changes']
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret

    if attributes:
        _ret = _attributes_present(name, attributes, region, key, keyid, profile)
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])

        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret

    _ret = _health_check_present(name, health_check, region, key, keyid,
                                 profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    if cnames:
        lb = __salt__['boto_elb.get_elb_config'](
            name, region, key, keyid, profile
        )
        if len(lb) > 0:
            for cname in cnames:
                _ret = None
                dns_provider = 'boto_route53'
                cname['record_type'] = 'CNAME'
                cname['value'] = lb['dns_name']
                if 'provider' in cname:
                    dns_provider = cname.pop('provider')
                if dns_provider == 'boto_route53':
                    if 'profile' not in cname:
                        cname['profile'] = profile
                    if 'key' not in cname:
                        cname['key'] = key
                    if 'keyid' not in cname:
                        cname['keyid'] = keyid
                    if 'region' not in cname:
                        cname['region'] = region
                    if 'wait_for_sync' not in cname:
                        cname['wait_for_sync'] = wait_for_sync
                _ret = __states__['.'.join([dns_provider, 'present'])](**cname)
                ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
                ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
                if not _ret['result']:
                    ret['result'] = _ret['result']
                    if ret['result'] is False:
                        return ret

    _ret = _alarms_present(name, alarms, alarms_from_pillar, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _policies_present(name, policies, policies_from_pillar, listeners,
                             backends, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _tags_present(name, tags, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret

    if not instance_ids:
        instance_ids = []
    if instance_names:
        # AWS borks on adding instances in "non-running" states, so filter 'em out.
        running_states = ('pending', 'rebooting', 'running', 'stopping', 'stopped')
        for n in instance_names:
            instance_ids += __salt__['boto_ec2.find_instances'](name=n, region=region,
                                                                key=key, keyid=keyid,
                                                                profile=profile,
                                                                in_states=running_states)
    # Backwards compat:  Only touch attached instances if requested (e.g. if some are defined).
    if instance_ids:
        if __opts__['test']:
            if __salt__['boto_elb.set_instances'](name, instance_ids, True, region,
                                                  key, keyid, profile):
                ret['comment'] += ' ELB {0} instances would be updated.'.format(name)
                return ret
        _ret = __salt__['boto_elb.set_instances'](name, instance_ids, False, region,
                                                  key, keyid, profile)
        if not _ret:
            ret['comment'] += "Failed to set requested instances."
            ret['result'] = _ret

    return ret


def register_instances(name, instances, region=None, key=None, keyid=None,
                       profile=None):
    '''
    Add EC2 instance(s) to an Elastic Load Balancer. Removing an instance from
    the ``instances`` list does not remove it from the ELB.

    name
        The name of the Elastic Load Balancer to add EC2 instances to.

    instances
        A list of EC2 instance IDs that this Elastic Load Balancer should
        distribute traffic to. This state will only ever append new instances
        to the ELB. EC2 instances already associated with this ELB will not be
        removed if they are not in the ``instances`` list.

    .. versionadded:: 2015.8.0

    .. code-block:: yaml

        add-instances:
          boto_elb.register_instances:
            - name: myloadbalancer
            - instances:
              - instance-id1
              - instance-id2
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    lb = __salt__['boto_elb.exists'](name, region, key, keyid, profile)
    if lb:
        health = __salt__['boto_elb.get_instance_health'](name,
                                                          region,
                                                          key,
                                                          keyid,
                                                          profile)
        nodes = []
        new = []
        for value in health:
            nodes.append(value['instance_id'])
        for value in instances:
            if value not in nodes:
                new.append(value)
        if len(new) == 0:
            ret['comment'] = 'Instance/s {0} already exist.' \
                              ''.format(str(instances).strip('[]'))
            ret['result'] = True
        else:
            if __opts__['test']:
                ret['comment'] = 'ELB {0} is set to register : {1}.'.format(name, new)
                return ret
            state = __salt__['boto_elb.register_instances'](name,
                                                            instances,
                                                            region,
                                                            key,
                                                            keyid,
                                                            profile)
            if state:
                ret['comment'] = 'Load Balancer {0} has been changed' \
                                 ''.format(name)
                ret['changes']['old'] = '\n'.join(nodes)
                new = set().union(nodes, instances)
                ret['changes']['new'] = '\n'.join(list(new))
                ret['result'] = True
            else:
                ret['comment'] = 'Load balancer {0} failed to add instances' \
                                 ''.format(name)
                ret['result'] = False
    else:
        ret['comment'] = 'Could not find lb {0}'.format(name)
    return ret


DEFAULT_PILLAR_LISTENER_POLICY_KEY = 'boto_elb_listener_policies'


def _elb_present(
        name,
        availability_zones,
        listeners,
        subnets,
        subnet_names,
        security_groups,
        scheme,
        region,
        key,
        keyid,
        profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    if not exactly_one((availability_zones, subnets, subnet_names)):
        raise SaltInvocationError('Exactly one of availability_zones, subnets, '
                                  'subnet_names must be provided as arguments.')
    if not listeners:
        listeners = []
    for listener in listeners:
        if len(listener) < 3:
            raise SaltInvocationError('Listeners must have at minimum port,'
                                      ' instance_port and protocol values in'
                                      ' the provided list.')
        if 'elb_port' not in listener:
            raise SaltInvocationError('elb_port is a required value for'
                                      ' listeners.')
        if 'instance_port' not in listener:
            raise SaltInvocationError('instance_port is a required value for'
                                      ' listeners.')
        if 'elb_protocol' not in listener:
            raise SaltInvocationError('elb_protocol is a required value for'
                                      ' listeners.')
        listener['elb_protocol'] = listener['elb_protocol'].upper()
        if listener['elb_protocol'] == 'HTTPS' and 'certificate' not in listener:
            raise SaltInvocationError('certificate is a required value for'
                                      ' listeners if HTTPS is set for'
                                      ' elb_protocol.')

        # best attempt at principle of least surprise here:
        #     only use the default pillar in cases where we don't explicitly
        #     define policies OR policies_from_pillar on a listener
        policies = listener.setdefault('policies', [])
        policies_pillar = listener.get('policies_from_pillar', None)
        if not policies and policies_pillar is None:
            policies_pillar = DEFAULT_PILLAR_LISTENER_POLICY_KEY
        if policies_pillar:
            policies += __salt__['pillar.get'](policies_pillar, {}).get(listener['elb_protocol'], [])

    # Look up subnet ids from names if provided
    if subnet_names:
        subnets = []
        for i in subnet_names:
            r = __salt__['boto_vpc.get_resource_id']('subnet', name=i, region=region,
                                                     key=key, keyid=keyid, profile=profile)
            if 'error' in r:
                ret['comment'] = 'Error looking up subnet ids: {0}'.format(r['error'])
                ret['result'] = False
                return ret
            if 'id' not in r:
                ret['comment'] = 'Subnet {0} does not exist.'.format(i)
                ret['result'] = False
                return ret
            subnets.append(r['id'])

    _security_groups = None
    if subnets:
        vpc_id = __salt__['boto_vpc.get_subnet_association'](subnets, region, key, keyid, profile)
        vpc_id = vpc_id.get('vpc_id')
        if not vpc_id:
            ret['comment'] = 'Subnets {0} do not map to a valid vpc id.'.format(subnets)
            ret['result'] = False
            return ret
        _security_groups = __salt__['boto_secgroup.convert_to_group_ids'](
            security_groups, vpc_id=vpc_id, region=region, key=key,
            keyid=keyid, profile=profile
        )
        if not _security_groups:
            msg = 'Security groups {0} do not map to valid security group ids.'
            ret['comment'] = msg.format(security_groups)
            ret['result'] = False
            return ret
    exists = __salt__['boto_elb.exists'](name, region, key, keyid, profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'ELB {0} is set to be created.'.format(name)
            return ret
        created = __salt__['boto_elb.create'](name=name,
                                              availability_zones=availability_zones,
                                              listeners=listeners, subnets=subnets,
                                              security_groups=_security_groups,
                                              scheme=scheme, region=region, key=key,
                                              keyid=keyid, profile=profile)
        if created:
            ret['changes']['old'] = {'elb': None}
            ret['changes']['new'] = {'elb': name}
            ret['comment'] = 'ELB {0} created.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} ELB.'.format(name)
    else:
        ret['comment'] = 'ELB {0} present.'.format(name)
        _ret = _security_groups_present(
            name, _security_groups, region, key, keyid, profile
        )
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
        _ret = _listeners_present(name, listeners, region, key, keyid,
                                  profile)
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
        if availability_zones:
            _ret = _zones_present(name, availability_zones, region, key, keyid,
                                  profile)
            ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
            ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
            if not _ret['result']:
                ret['result'] = _ret['result']
                if ret['result'] is False:
                    return ret
        elif subnets:
            _ret = _subnets_present(name, subnets, region, key, keyid,
                                    profile)
            ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
            ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
            if not _ret['result']:
                ret['result'] = _ret['result']
    return ret


def _listeners_present(
        name,
        listeners,
        region,
        key,
        keyid,
        profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid, profile)
    if not lb:
        msg = '{0} ELB configuration could not be retrieved.'.format(name)
        ret['comment'] = msg
        if not __opts__['test']:
            ret['result'] = False
        return ret
    if not listeners:
        listeners = []

    expected_listeners_by_tuple = {}
    for l in listeners:
        l_key = __salt__['boto_elb.listener_dict_to_tuple'](l)
        expected_listeners_by_tuple[l_key] = l
    actual_listeners_by_tuple = {}
    for l in lb['listeners']:
        l_key = __salt__['boto_elb.listener_dict_to_tuple'](l)
        actual_listeners_by_tuple[l_key] = l

    to_delete = []
    to_create = []

    for t, l in six.iteritems(expected_listeners_by_tuple):
        if t not in actual_listeners_by_tuple:
            to_create.append(l)
    for t, l in six.iteritems(actual_listeners_by_tuple):
        if t not in expected_listeners_by_tuple:
            to_delete.append(l)

    if __opts__['test']:
        msg = []
        if to_create or to_delete:
            msg.append('ELB {0} set to have listeners modified:'.format(name))
            for listener in to_create:
                msg.append('Listener {0} added.'.format(
                        __salt__['boto_elb.listener_dict_to_tuple'](listener)))
            for listener in to_delete:
                msg.append('Listener {0} deleted.'.format(
                        __salt__['boto_elb.listener_dict_to_tuple'](listener)))
        else:
            msg.append('Listeners already set on ELB {0}.'.format(name))
        ret['comment'] = ' '.join(msg)
        return ret

    if to_delete:
        ports = [l['elb_port'] for l in to_delete]
        deleted = __salt__['boto_elb.delete_listeners'](name, ports,
                                                        region, key, keyid,
                                                        profile)
        if deleted:
            ret['comment'] = 'Deleted listeners on {0} ELB.'.format(name)
        else:
            msg = 'Failed to delete listeners on {0} ELB.'.format(name)
            ret['comment'] = msg
            ret['result'] = False

    if to_create:
        created = __salt__['boto_elb.create_listeners'](name, to_create,
                                                        region, key, keyid,
                                                        profile)
        if created:
            msg = 'Created listeners on {0} ELB.'
            ret['comment'] = ' '.join([ret['comment'], msg.format(name)])
        else:
            msg = 'Failed to create listeners on {0} ELB.'
            ret['comment'] = ' '.join([ret['comment'], msg.format(name)])
            ret['result'] = False

    if to_create or to_delete:
        ret['changes']['listeners'] = {}
        ret['changes']['listeners']['old'] = lb['listeners']
        lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid,
                                                 profile)
        ret['changes']['listeners']['new'] = lb['listeners']
    else:
        ret['comment'] = 'Listeners already set on ELB {0}.'.format(name)

    return ret


def _security_groups_present(
        name,
        security_groups,
        region,
        key,
        keyid,
        profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid, profile)
    if not lb:
        msg = '{0} ELB configuration could not be retrieved.'.format(name)
        ret['comment'] = msg
        if not __opts__['test']:
            ret['result'] = False
        return ret
    if not security_groups:
        security_groups = []
    change_needed = False
    if set(security_groups) != set(lb['security_groups']):
        change_needed = True
    if change_needed:
        if __opts__['test']:
            msg = 'ELB {0} set to have security groups modified.'.format(name)
            ret['comment'] = msg
            return ret
        changed = __salt__['boto_elb.apply_security_groups'](
            name, security_groups, region, key, keyid, profile
        )
        if changed:
            msg = 'Modified security_groups on {0} ELB.'.format(name)
            ret['comment'] = msg
        else:
            msg = 'Failed to modify security_groups on {0} ELB.'.format(name)
            ret['comment'] = msg
            ret['result'] = False
        ret['changes']['old'] = {'security_groups': lb['security_groups']}
        ret['changes']['new'] = {'security_groups': security_groups}
    else:
        ret['comment'] = 'security_groups already set on ELB {0}.'.format(name)
    return ret


def _attributes_present(
        name,
        attributes,
        region,
        key,
        keyid,
        profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    _attributes = __salt__['boto_elb.get_attributes'](name, region, key, keyid,
                                                      profile)
    if not _attributes:
        if not __opts__['test']:
            ret['result'] = False
        msg = 'Failed to retrieve attributes for ELB {0}.'.format(name)
        ret['comment'] = msg
        return ret
    attrs_to_set = []
    if 'cross_zone_load_balancing' in attributes:
        czlb = attributes['cross_zone_load_balancing']
        _czlb = _attributes['cross_zone_load_balancing']
        if czlb['enabled'] != _czlb['enabled']:
            attrs_to_set.append('cross_zone_load_balancing')
    if 'connection_draining' in attributes:
        cd = attributes['connection_draining']
        _cd = _attributes['connection_draining']
        if (cd['enabled'] != _cd['enabled']
                or cd.get('timeout', 300) != _cd.get('timeout')):
            attrs_to_set.append('connection_draining')
    if 'connecting_settings' in attributes:
        cs = attributes['connecting_settings']
        _cs = _attributes['connecting_settings']
        if cs['idle_timeout'] != _cs['idle_timeout']:
            attrs_to_set.append('connecting_settings')
    if 'access_log' in attributes:
        for attr, val in six.iteritems(attributes['access_log']):
            if str(_attributes['access_log'][attr]) != str(val):
                attrs_to_set.append('access_log')
        if 's3_bucket_prefix' in attributes['access_log']:
            sbp = attributes['access_log']['s3_bucket_prefix']
            if sbp.startswith('/') or sbp.endswith('/'):
                raise SaltInvocationError('s3_bucket_prefix can not start or'
                                          ' end with /.')
    if attrs_to_set:
        if __opts__['test']:
            ret['comment'] = 'ELB {0} set to have attributes set.'.format(name)
            return ret
        was_set = __salt__['boto_elb.set_attributes'](name, attributes,
                                                      region, key, keyid,
                                                      profile)
        if was_set:
            ret['changes']['old'] = {'attributes': _attributes}
            ret['changes']['new'] = {'attributes': attributes}
            ret['comment'] = 'Set attributes on ELB {0}.'.format(name)
        else:
            ret['result'] = False
            msg = 'Failed to set attributes on ELB {0}.'.format(name)
            ret['comment'] = msg
    else:
        ret['comment'] = 'Attributes already set on ELB {0}.'.format(name)
    return ret


def _health_check_present(
        name,
        health_check,
        region,
        key,
        keyid,
        profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    if not health_check:
        health_check = {}
    _health_check = __salt__['boto_elb.get_health_check'](name, region, key,
                                                          keyid, profile)
    if not _health_check:
        if not __opts__['test']:
            ret['result'] = False
        msg = 'Failed to retrieve health_check for ELB {0}.'.format(name)
        ret['comment'] = msg
        return ret
    need_to_set = False
    for attr, val in six.iteritems(health_check):
        if str(_health_check[attr]) != str(val):
            need_to_set = True
    if need_to_set:
        if __opts__['test']:
            msg = 'ELB {0} set to have health check set.'.format(name)
            ret['comment'] = msg
            return ret
        was_set = __salt__['boto_elb.set_health_check'](name, health_check,
                                                        region, key, keyid,
                                                        profile)
        if was_set:
            ret['changes']['old'] = {'health_check': _health_check}
            _health_check = __salt__['boto_elb.get_health_check'](name, region,
                                                                  key, keyid,
                                                                  profile)
            ret['changes']['new'] = {'health_check': _health_check}
            ret['comment'] = 'Set health check on ELB {0}.'.format(name)
        else:
            ret['result'] = False
            msg = 'Failed to set health check on ELB {0}.'.format(name)
            ret['comment'] = msg
    else:
        ret['comment'] = 'Health check already set on ELB {0}.'.format(name)
    return ret


def _zones_present(
        name,
        availability_zones,
        region,
        key,
        keyid,
        profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid, profile)
    if not lb:
        if not __opts__['test']:
            ret['result'] = False
        msg = 'Failed to retrieve ELB {0}.'.format(name)
        ret['comment'] = msg
        return ret
    to_enable = []
    to_disable = []
    _zones = lb['availability_zones']
    for zone in availability_zones:
        if zone not in _zones:
            to_enable.append(zone)
    for zone in _zones:
        if zone not in availability_zones:
            to_disable.append(zone)
    if to_enable or to_disable:
        if __opts__['test']:
            msg = 'ELB {0} to have availability zones set.'.format(name)
            ret['comment'] = msg
            return ret
        if to_enable:
            enabled = __salt__['boto_elb.enable_availability_zones'](name,
                                                                     to_enable,
                                                                     region,
                                                                     key,
                                                                     keyid,
                                                                     profile)
            if enabled:
                msg = 'Enabled availability zones on {0} ELB.'.format(name)
                ret['comment'] = msg
            else:
                msg = 'Failed to enable availability zones on {0} ELB.'
                ret['comment'] = msg.format(name)
                ret['result'] = False
        if to_disable:
            disabled = __salt__['boto_elb.disable_availability_zones'](name,
                                                                       to_disable,
                                                                       region,
                                                                       key,
                                                                       keyid,
                                                                       profile)
            if disabled:
                msg = 'Disabled availability zones on {0} ELB.'
                ret['comment'] = ' '.join([ret['comment'], msg.format(name)])
            else:
                msg = 'Failed to disable availability zones on {0} ELB.'
                ret['comment'] = ' '.join([ret['comment'], msg.format(name)])
                ret['result'] = False
        ret['changes']['old'] = {'availability_zones':
                                 lb['availability_zones']}
        lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid,
                                                 profile)
        ret['changes']['new'] = {'availability_zones':
                                 lb['availability_zones']}
    else:
        msg = 'Availability zones already set on ELB {0}.'.format(name)
        ret['comment'] = msg
    return ret


def _subnets_present(
        name,
        subnets,
        region,
        key,
        keyid,
        profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    if not subnets:
        subnets = []
    lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid, profile)
    if not lb:
        if not __opts__['test']:
            ret['result'] = False
        msg = 'Failed to retrieve ELB {0}.'.format(name)
        ret['comment'] = msg
        return ret
    to_enable = []
    to_disable = []
    _subnets = lb['subnets']
    for subnet in subnets:
        if subnet not in _subnets:
            to_enable.append(subnet)
    for subnet in _subnets:
        if subnet not in subnets:
            to_disable.append(subnet)
    if to_enable or to_disable:
        if __opts__['test']:
            msg = 'ELB {0} to have subnets set.'.format(name)
            ret['comment'] = msg
            return ret
        if to_enable:
            attached = __salt__['boto_elb.attach_subnets'](name, to_enable,
                                                           region, key, keyid,
                                                           profile)
            if attached:
                msg = 'Attached subnets on {0} ELB.'.format(name)
                ret['comment'] = msg
            else:
                msg = 'Failed to attach subnets on {0} ELB.'
                ret['comment'] = msg.format(name)
                ret['result'] = False
        if to_disable:
            detached = __salt__['boto_elb.detach_subnets'](name, to_disable,
                                                           region, key, keyid,
                                                           profile)
            if detached:
                msg = 'Detached subnets on {0} ELB.'
                ret['comment'] = ' '.join([ret['comment'], msg.format(name)])
            else:
                msg = 'Failed to detach subnets on {0} ELB.'
                ret['comment'] = ' '.join([ret['comment'], msg.format(name)])
                ret['result'] = False
        ret['changes']['old'] = {'subnets': lb['subnets']}
        lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid,
                                                 profile)
        ret['changes']['new'] = {'subnets': lb['subnets']}
    else:
        msg = 'Subnets already set on ELB {0}.'.format(name)
        ret['comment'] = msg
    return ret


def _alarms_present(name, alarms, alarms_from_pillar, region, key, keyid, profile):
    '''helper method for present.  ensure that cloudwatch_alarms are set'''
    # load data from alarms_from_pillar
    tmp = __salt__['config.option'](alarms_from_pillar, {})
    # merge with data from alarms
    if alarms:
        tmp = dictupdate.update(tmp, alarms)
    # set alarms, using boto_cloudwatch_alarm.present
    merged_return_value = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    for _, info in six.iteritems(tmp):
        # add elb to name and description
        info["name"] = name + " " + info["name"]
        info["attributes"]["description"] = name + " " + info["attributes"]["description"]
        # add dimension attribute
        info["attributes"]["dimensions"] = {"LoadBalancerName": [name]}
        # set alarm
        kwargs = {
            "name": info["name"],
            "attributes": info["attributes"],
            "region": region,
            "key": key,
            "keyid": keyid,
            "profile": profile,
        }
        results = __states__['boto_cloudwatch_alarm.present'](**kwargs)
        if not results.get('result'):
            merged_return_value["result"] = results["result"]
        if results.get("changes", {}) != {}:
            merged_return_value["changes"][info["name"]] = results["changes"]
        if "comment" in results:
            merged_return_value["comment"] += results["comment"]
    return merged_return_value


def _policies_present(
        name,
        policies,
        policies_from_pillar,
        listeners,
        backends,
        region,
        key,
        keyid,
        profile):
    '''helper method for present. ensure that ELB policies are set'''
    if policies is None:
        policies = []
    pillar_policies = __salt__['config.option'](policies_from_pillar, [])
    policies = policies + pillar_policies
    if backends is None:
        backends = []

    # check for policy name uniqueness and correct type
    policy_names = set()
    for p in policies:
        if 'policy_name' not in p:
            raise SaltInvocationError('policy_name is a required value for '
                                      'policies.')
        if 'policy_type' not in p:
            raise SaltInvocationError('policy_type is a required value for '
                                      'policies.')
        if 'policy' not in p:
            raise SaltInvocationError('policy is a required value for '
                                      'listeners.')
        # check for unique policy names
        if p['policy_name'] in policy_names:
            raise SaltInvocationError('Policy names must be unique: policy {0}'
                    ' is declared twice.'.format(p['policy_name']))
        policy_names.add(p['policy_name'])

    # check that listeners refer to valid policy names
    for l in listeners:
        for p in l.get('policies', []):
            if p not in policy_names:
                raise SaltInvocationError('Listener {0} on ELB {1} refers to '
                        'undefined policy {2}.'.format(l['elb_port'], name, p))

    # check that backends refer to valid policy names
    for b in backends:
        for p in b.get('policies', []):
            if p not in policy_names:
                raise SaltInvocationError('Backend {0} on ELB {1} refers to '
                        'undefined policy '
                        '{2}.'.format(b['instance_port'], name, p))

    ret = {'result': True, 'comment': '', 'changes': {}}

    lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid, profile)
    if not lb:
        msg = '{0} ELB configuration could not be retrieved.'.format(name)
        ret['comment'] = msg
        if not __opts__['test']:
            ret['result'] = False
        return ret

    # Policies have two names:
    # - a short name ('name') that's only the policy name (e.g. testpolicy)
    # - a canonical name ('cname') that contains the policy type and hash
    #   (e.g. SSLNegotiationPolicy-testpolicy-14b32f668639cc8ea1391e062af98524)

    policies_by_cname = {}
    cnames_by_name = {}
    for p in policies:
        cname = _policy_cname(p)
        policies_by_cname[cname] = p
        cnames_by_name[p['policy_name']] = cname

    expected_policy_names = policies_by_cname.keys()
    actual_policy_names = lb['policies']

    # This is sadly a huge hack to get around the fact that AWS assigns a
    # default SSLNegotiationPolicyType policy (with the naming scheme
    # ELBSecurityPolicy-YYYY-MM) to all ELBs terminating SSL without an
    # explicit policy set. If we don't keep track of the default policies and
    # explicitly exclude them from deletion, orchestration will fail because we
    # attempt to delete the default policy that's being used by listeners that
    # were created with no explicit policy.
    default_aws_policies = set()

    expected_policies_by_listener = {}
    for l in listeners:
        expected_policies_by_listener[l['elb_port']] = set(
                [cnames_by_name[p] for p in l.get('policies', [])])

    actual_policies_by_listener = {}
    for l in lb['listeners']:
        listener_policies = set(l.get('policies', []))
        actual_policies_by_listener[l['elb_port']] = listener_policies
        # Determine if any actual listener policies look like default policies,
        # so we can exclude them from deletion below (see note about this hack
        # above).
        for p in listener_policies:
            if re.match(r'^ELBSecurityPolicy-\d{4}-\d{2}$', p):
                default_aws_policies.add(p)

    expected_policies_by_backend = {}
    for b in backends:
        expected_policies_by_backend[b['instance_port']] = set(
                [cnames_by_name[p] for p in b.get('policies', [])])

    actual_policies_by_backend = {}
    for b in lb['backends']:
        backend_policies = set(b.get('policies', []))
        actual_policies_by_backend[b['instance_port']] = backend_policies

    to_delete = []
    to_create = []

    for policy_name in expected_policy_names:
        if policy_name not in actual_policy_names:
            to_create.append(policy_name)
    for policy_name in actual_policy_names:
        if policy_name not in expected_policy_names:
            if policy_name not in default_aws_policies:
                to_delete.append(policy_name)

    listeners_to_update = set()
    for port, policies in six.iteritems(expected_policies_by_listener):
        if policies != actual_policies_by_listener.get(port, set()):
            listeners_to_update.add(port)
    for port, policies in six.iteritems(actual_policies_by_listener):
        if policies != expected_policies_by_listener.get(port, set()):
            listeners_to_update.add(port)

    backends_to_update = set()
    for port, policies in six.iteritems(expected_policies_by_backend):
        if policies != actual_policies_by_backend.get(port, set()):
            backends_to_update.add(port)
    for port, policies in six.iteritems(actual_policies_by_backend):
        if policies != expected_policies_by_backend.get(port, set()):
            backends_to_update.add(port)

    if __opts__['test']:
        msg = []
        if to_create or to_delete:
            msg.append('ELB {0} set to have policies modified:'.format(name))
            for policy in to_create:
                msg.append('Policy {0} added.'.format(policy))
            for policy in to_delete:
                msg.append('Policy {0} deleted.'.format(policy))
        else:
            msg.append('Policies already set on ELB {0}.'.format(name))
        for listener in listeners_to_update:
            msg.append('Listener {0} policies updated.'.format(listener))
        for backend in backends_to_update:
            msg.append('Backend {0} policies updated.'.format(backend))
        ret['comment'] = ' '.join(msg)
        return ret

    if to_create:
        for policy_name in to_create:
            created = __salt__['boto_elb.create_policy'](
                name=name,
                policy_name=policy_name,
                policy_type=policies_by_cname[policy_name]['policy_type'],
                policy=policies_by_cname[policy_name]['policy'],
                region=region,
                key=key,
                keyid=keyid,
                profile=profile)
            if created:
                ret['changes'].setdefault(policy_name, {})['new'] = policy_name
                comment = "Policy {0} was created on ELB {1}".format(
                        policy_name, name)
                ret['comment'] = ' '.join([ret['comment'], comment])
                ret['result'] = True
            else:
                ret['result'] = False
                return ret

    for port in listeners_to_update:
        policy_set = __salt__['boto_elb.set_listener_policy'](
                name=name,
                port=port,
                policies=list(expected_policies_by_listener.get(port, [])),
                region=region,
                key=key,
                keyid=keyid,
                profile=profile)
        if policy_set:
            policy_key = 'listener_{0}_policy'.format(port)
            ret['changes'][policy_key] = {
                    'old': list(actual_policies_by_listener.get(port, [])),
                    'new': list(expected_policies_by_listener.get(port, [])),
                    }
            comment = "Policy {0} was created on ELB {1} listener {2}".format(
                    expected_policies_by_listener[port], name, port)
            ret['comment'] = ' '.join([ret['comment'], comment])
            ret['result'] = True
        else:
            ret['result'] = False
            return ret

    for port in backends_to_update:
        policy_set = __salt__['boto_elb.set_backend_policy'](
                name=name,
                port=port,
                policies=list(expected_policies_by_backend.get(port, [])),
                region=region,
                key=key,
                keyid=keyid,
                profile=profile)
        if policy_set:
            policy_key = 'backend_{0}_policy'.format(port)
            ret['changes'][policy_key] = {
                    'old': list(actual_policies_by_backend.get(port, [])),
                    'new': list(expected_policies_by_backend.get(port, [])),
                    }
            comment = "Policy {0} was created on ELB {1} backend {2}".format(
                    expected_policies_by_backend[port], name, port)
            ret['comment'] = ' '.join([ret['comment'], comment])
            ret['result'] = True
        else:
            ret['result'] = False
            return ret

    if to_delete:
        for policy_name in to_delete:
            deleted = __salt__['boto_elb.delete_policy'](
                name=name,
                policy_name=policy_name,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile)
            if deleted:
                ret['changes'].setdefault(policy_name, {})['old'] = policy_name
                comment = "Policy {0} was deleted from ELB {1}".format(
                        policy_name, name)
                ret['comment'] = ' '.join([ret['comment'], comment])
                ret['result'] = True
            else:
                ret['result'] = False
                return ret
    return ret


def _policy_cname(policy_dict):
    policy_name = policy_dict['policy_name']
    policy_type = policy_dict['policy_type']
    policy = policy_dict['policy']
    canonical_policy_repr = str(sorted(list(six.iteritems(policy)), key=lambda x: str(x[0])))
    policy_hash = hashlib.md5(str(canonical_policy_repr)).hexdigest()
    if policy_type.endswith('Type'):
        policy_type = policy_type[:-4]
    return "{0}-{1}-{2}".format(policy_type, policy_name, policy_hash)


def absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure an ELB does not exist

    name
        name of the ELB
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    exists = __salt__['boto_elb.exists'](name, region, key, keyid, profile)
    if exists:
        if __opts__['test']:
            ret['comment'] = 'ELB {0} is set to be removed.'.format(name)
            return ret
        deleted = __salt__['boto_elb.delete'](name, region, key, keyid,
                                              profile)
        if deleted:
            ret['changes']['old'] = {'elb': name}
            ret['changes']['new'] = {'elb': None}
            ret['comment'] = 'ELB {0} deleted.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} ELB.'.format(name)
    else:
        ret['comment'] = '{0} ELB does not exist.'.format(name)
    return ret


def _tags_present(name,
                  tags,
                  region,
                  key,
                  keyid,
                  profile):
    '''
    helper function to validate tags on elb
    '''
    ret = {'result': True, 'comment': '', 'changes': {}}
    if tags:
        lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid, profile)

        tags_to_add = tags
        tags_to_update = {}
        tags_to_remove = []
        if lb['tags']:
            for _tag in lb['tags']:
                if _tag not in tags.keys():
                    if _tag not in tags_to_remove:
                        tags_to_remove.append(_tag)
                else:
                    if tags[_tag] != lb['tags'][_tag]:
                        tags_to_update[_tag] = tags[_tag]
                    tags_to_add.pop(_tag)
        if tags_to_remove:
            if __opts__['test']:
                msg = 'The following tag{0} set to be removed: {1}.'.format(
                        ('s are' if len(tags_to_remove) > 1 else ' is'), ', '.join(tags_to_remove))
                ret['comment'] = ' '.join([ret['comment'], msg])
            else:
                _ret = __salt__['boto_elb.delete_tags'](
                            name,
                            tags_to_remove,
                            region,
                            key,
                            keyid,
                            profile)
                if not _ret:
                    ret['result'] = False
                    msg = 'Error attempting to delete tag {0}.'.format(tags_to_remove)
                    ret['comment'] = ' '.join([ret['comment'], msg])
                    return ret
                if 'old' not in ret['changes']:
                    ret['changes'] = dictupdate.update(ret['changes'], {'old': {'tags': {}}})
                for _tag in tags_to_remove:
                    ret['changes']['old']['tags'][_tag] = lb['tags'][_tag]
        if tags_to_add or tags_to_update:
            if __opts__['test']:
                if tags_to_add:
                    msg = 'The following tag{0} set to be added: {1}.'.format(
                            ('s are' if len(tags_to_add.keys()) > 1 else ' is'),
                            ', '.join(tags_to_add.keys()))
                    ret['comment'] = ' '. join([ret['comment'], msg])
                if tags_to_update:
                    msg = 'The following tag {0} set to be updated: {1}.'.format(
                            ('values are' if len(tags_to_update.keys()) > 1 else 'value is'),
                            ', '.join(tags_to_update.keys()))
                    ret['comment'] = ' '.join([ret['comment'], msg])
            else:
                all_tag_changes = dictupdate.update(tags_to_add, tags_to_update)
                _ret = __salt__['boto_elb.set_tags'](
                            name,
                            all_tag_changes,
                            region,
                            key,
                            keyid,
                            profile)
                if not _ret:
                    ret['result'] = False
                    msg = 'Error attempting to set tags.'
                    ret['comment'] = ' '.join([ret['comment'], msg])
                    return ret
                if 'old' not in ret['changes']:
                    ret['changes'] = dictupdate.update(ret['changes'], {'old': {'tags': {}}})
                if 'new' not in ret['changes']:
                    ret['changes'] = dictupdate.update(ret['changes'], {'new': {'tags': {}}})
                for tag in all_tag_changes:
                    ret['changes']['new']['tags'][tag] = tags[tag]
                    if 'tags' in lb:
                        if lb['tags']:
                            if tag in lb['tags']:
                                ret['changes']['old']['tags'][tag] = lb['tags'][tag]
        if not tags_to_update and not tags_to_remove and not tags_to_add:
            msg = 'Tags are already set.'
            ret['comment'] = ' '.join([ret['comment'], msg])
    return ret
