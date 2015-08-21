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
                - elb_port: 8210
                  instance_port: 8210
                  elb_protocol: TCP
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
            - cnames:
                - name: mycname.example.com.
                  zone: example.com.
                  ttl: 60
                - name: myothercname.example.com.
                  zone: example.com.

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
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
import salt.utils.dictupdate as dictupdate
from salt.exceptions import SaltInvocationError
import salt.ext.six as six


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
        security_groups=None,
        scheme='internet-facing',
        health_check=None,
        attributes=None,
        attributes_from_pillar="boto_elb_attributes",
        cnames=None,
        alarms=None,
        alarms_from_pillar="boto_elb_alarms",
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the IAM role exists.

    name
        Name of the IAM role.

    availability_zones
        A list of availability zones for this ELB.

    listeners
        A list of listener lists; example:
        [
            ['443', 'HTTPS', 'arn:aws:iam::1111111:server-certificate/mycert'],
            ['8443', '80', 'HTTPS', 'HTTP', 'arn:aws:iam::1111111:server-certificate/mycert']
        ]

    subnets
        A list of subnet IDs in your VPC to attach to your LoadBalancer.

    security_groups
        The security groups assigned to your LoadBalancer within your VPC.

    scheme
        The type of a LoadBalancer. internet-facing or internal. Once set, can not be modified.

    health_check
        A dict defining the health check for this ELB.

    attributes
        A dict defining the attributes to set on this ELB.

    attributes_from_pillar
        name of pillar dict that contains attributes.   Attributes defined for this specific
        state will override those from pillar.

    cnames
        A list of cname dicts with attributes: name, zone, ttl, and identifier.
        See the boto_route53 state for information about these attributes.

    alarms:
        a dictionary of name->boto_cloudwatch_alarm sections to be associated with this ELB.
        All attributes should be specified except for dimension which will be
        automatically set to this ELB.
        See the boto_cloudwatch_alarm state for information about these attributes.

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
    '''

    # load data from attributes_from_pillar and merge with attributes
    tmp = __salt__['config.option'](attributes_from_pillar, {})
    if attributes:
        attributes = dictupdate.update(tmp, attributes)
    else:
        attributes = tmp

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    _ret = _elb_present(name, availability_zones, listeners, subnets,
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
        for cname in cnames:
            _ret = __salt__['state.single'](
                'boto_route53.present',
                name=cname.get('name'),
                value=lb['dns_name'],
                zone=cname.get('zone'),
                record_type='CNAME',
                identifier=cname.get('identifier', None),
                ttl=cname.get('ttl', None),
                region=region,
                key=key,
                keyid=keyid,
                profile=profile
            )
            _ret = _ret.values()[0]
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
    return ret


def _elb_present(
        name,
        availability_zones,
        listeners,
        subnets,
        security_groups,
        scheme,
        region,
        key,
        keyid,
        profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    if not (availability_zones or subnets):
        raise SaltInvocationError('Either availability_zones or subnets must'
                                  ' be provided as arguments.')
    if availability_zones and subnets:
        raise SaltInvocationError('availability_zones and subnets are mutually'
                                  ' exclusive arguments.')
    if not listeners:
        listeners = []
    _listeners = []
    for listener in listeners:
        if len(listener) < 3:
            raise SaltInvocationError('Listeners must have at minimum port,'
                                      ' instance_port and protocol values in'
                                      ' the provided list.')
        for config in ('elb_port', 'instance_port', 'elb_protocol'):
            if not listener.get(config):
                raise SaltInvocationError(
                    '{0} is a required value for listeners.'.format(config)
                )

        listener['elb_protocol'] = listener['elb_protocol'].upper()
        if listener['elb_protocol'] == 'HTTPS' and 'certificate' not in listener:
            raise SaltInvocationError('certificate is a required value for'
                                      ' listeners if HTTPS is set for'
                                      ' elb_protocol.')
        # We define all listeners as complex listeners.
        if not listener.get('instance_protocol'):
            listener['instance_protocol'] = listener['elb_protocol'].upper()
        else:
            listener['instance_protocol'] = listener['instance_protocol'].upper()
        _listener = [listener['elb_port'], listener['instance_port'],
                     listener['elb_protocol'], listener['instance_protocol']]
        if 'certificate' in listener:
            _listener.append(listener['certificate'])
        _listeners.append(_listener)
    if subnets:
        vpc_id = __salt__['boto_vpc.get_subnet_association'](
            subnets, region, key, keyid, profile
        )
        if not vpc_id:
            msg = 'Subnets {0} do not map to a valid vpc id.'.format(subnets)
            raise SaltInvocationError(msg)
        security_groups = __salt__['boto_secgroup.convert_to_group_ids'](
            security_groups, vpc_id, region, key, keyid, profile
        )
        if not security_groups:
            msg = 'Security groups {0} do not map to valid security group ids.'
            msg = msg.format(security_groups)
            raise SaltInvocationError(msg)
    exists = __salt__['boto_elb.exists'](name, region, key, keyid, profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'ELB {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_elb.create'](name, availability_zones,
                                              _listeners, subnets,
                                              security_groups, scheme, region,
                                              key, keyid, profile)
        if created:
            ret['changes']['old'] = {'elb': None}
            ret['changes']['new'] = {'elb': name}
            ret['comment'] = 'ELB {0} created.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} ELB.'.format(name)
    else:
        ret['comment'] = 'ELB {0} present.'.format(name)
        _ret = _listeners_present(name, _listeners, region, key, keyid,
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
        ret['result'] = False
        return ret
    if not listeners:
        listeners = []
    to_delete = []
    to_create = []
    for listener in listeners:
        if listener not in lb['listeners']:
            to_create.append(listener)
    for listener in lb['listeners']:
        if listener not in listeners:
            to_delete.append(listener[0])
    if to_create or to_delete:
        if __opts__['test']:
            msg = 'ELB {0} set to have listeners modified.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        if to_delete:
            deleted = __salt__['boto_elb.delete_listeners'](name, to_delete,
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
        ret['changes']['old'] = {'listeners': lb['listeners']}
        lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid,
                                                 profile)
        ret['changes']['new'] = {'listeners': lb['listeners']}
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
            ret['result'] = None
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
            ret['result'] = True
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
            ret['result'] = None
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
            ret['result'] = None
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
    for _, info in tmp.items():
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
        ret = __salt__["state.single"]('boto_cloudwatch_alarm.present', **kwargs)
        results = ret.values()[0]
        if not results["result"]:
            merged_return_value["result"] = results["result"]
        if results.get("changes", {}) != {}:
            merged_return_value["changes"][info["name"]] = results["changes"]
        if "comment" in results:
            merged_return_value["comment"] += results["comment"]
    return merged_return_value


def absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    exists = __salt__['boto_elb.exists'](name, region, key, keyid, profile)
    if exists:
        if __opts__['test']:
            ret['comment'] = 'ELB {0} is set to be removed.'.format(name)
            ret['result'] = None
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
