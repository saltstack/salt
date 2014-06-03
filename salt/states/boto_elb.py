# -*- coding: utf-8 -*-
'''
Manage ELBs
=================

.. versionadded:: Helium

Create and destroy ELBs. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses boto, which can be installed via package, or pip.

This module accepts explicit elb credentials but can also utilize
IAM roles assigned to the instance trough Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More Information available at:

http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

If IAM roles are not used you need to specify them either in a pillar or
in the minion's config file::

    elb.keyid: GKTADJGHEIQSXMKKRBJ08H
    elb.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify key, keyid and region via a profile, either
as a passed in dict, or as a string to pull from pillars or minion config:

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
'''
import salt.utils.dictupdate as dictupdate
from salt.exceptions import SaltInvocationError


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_elb' if 'boto_elb.exists' in __salt__ else False


def present(
        name,
        availability_zones,
        listeners,
        subnets=None,
        security_groups=None,
        scheme='internet-facing',
        health_check=None,
        attributes=None,
        cnames=None,
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
        A list of listener lists; example: [['443', 'HTTPS', 'arn:aws:iam::1111111:server-certificate/mycert'], ['8443', '80', 'HTTPS', 'HTTP', 'arn:aws:iam::1111111:server-certificate/mycert']]

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

    cnames
        A list of cname dicts with attributes: name, zone, ttl, and identifier.
        See the boto_route53 state for information about these attributes.

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
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    _ret = _elb_present(name, availability_zones, listeners, subnets,
                        security_groups, scheme, region, key, keyid, profile)
    ret['changes'] = _ret['changes']
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if _ret['result'] is not None:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _attributes_present(name, attributes, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if _ret['result'] is not None:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _health_check_present(name, health_check, region, key, keyid,
                                 profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if _ret['result'] is not None:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _cnames_present(name, cnames, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if _ret['result'] is not None:
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
    ret = {'result': None, 'comment': '', 'changes': {}}
    if not listeners:
        listeners = []
    _listeners = []
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
        # We define all listeners as complex listeners.
        if 'instance_protocol' not in listener:
            listener['instance_protocol'] = listener['elb_protocol'].upper()
        else:
            listener['instance_protocol'] = listener['instance_protocol'].upper()
        _listener = [listener['elb_port'], listener['instance_port'],
                     listener['elb_protocol'], listener['instance_protocol']]
        if 'certificate' in listener:
            _listener.append(listener['certificate'])
        _listeners.append(_listener)
    exists = __salt__['boto_elb.exists'](name, region, key, keyid, profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'ELB {0} is set to be created.'.format(name)
            return ret
        created = __salt__['boto_elb.create'](name, availability_zones,
                                              _listeners, subnets,
                                              security_groups, scheme, region,
                                              key, keyid, profile)
        if created:
            ret['result'] = True
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
        if _ret['result'] is not None:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
        _ret = _zones_present(name, availability_zones, region, key, keyid,
                              profile)
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if _ret['result'] is not None:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
        _ret = _subnets_present(name, subnets, region, key, keyid,
                                profile)
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if _ret['result'] is not None:
            ret['result'] = _ret['result']
    return ret


def _listeners_present(
        name,
        listeners,
        region,
        key,
        keyid,
        profile):
    ret = {'result': None, 'comment': '', 'changes': {}}
    lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid, profile)
    if not lb:
        msg = '{0} ELB configuration could not be retreived.'.format(name)
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
            return ret
        if to_delete:
            deleted = __salt__['boto_elb.delete_listeners'](name, to_delete,
                                                            region, key, keyid,
                                                            profile)
            if deleted:
                ret['comment'] = 'Deleted listeners on {0} ELB.'.format(name)
                ret['result'] = True
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
                if ret['result'] is not False:
                    ret['result'] = True
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
    ret = {'result': None, 'comment': '', 'changes': {}}
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
    if 'access_log' in attributes:
        for attr, val in attributes['access_log'].iteritems():
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
            ret['result'] = True
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
    ret = {'result': None, 'comment': '', 'changes': {}}
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
    for attr, val in health_check.iteritems():
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
            ret['result'] = True
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
    ret = {'result': None, 'comment': '', 'changes': {}}
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
                ret['result'] = True
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
                ret['result'] = True
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
    ret = {'result': None, 'comment': '', 'changes': {}}
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
                ret['result'] = True
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
                ret['result'] = True
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


def _cnames_present(
        name,
        cnames,
        region,
        key,
        keyid,
        profile):
    ret = {'result': None, 'comment': '', 'changes': {}}
    if not cnames:
        cnames = []
    lb = __salt__['boto_elb.get_elb_config'](name, region, key, keyid, profile)
    if not lb:
        if not __opts__['test']:
            ret['result'] = False
        msg = 'Failed to retrieve ELB {0}.'.format(name)
        ret['comment'] = msg
        return ret
    to_create = []
    to_update = []
    for cname in cnames:
        _name = cname.get('name', None)
        _zone = cname.get('zone', None)
        if not _name or not _zone:
            raise SaltInvocationError('cnames must provide name and zone'
                                      ' attributes.')
        record = __salt__['boto_route53.get_record'](_name, _zone, 'CNAME',
                                                     False, region, key,
                                                     keyid, profile)
        if not record:
            to_create.append(cname)
        elif record['value'].rstrip('.') != lb['dns_name'].rstrip('.'):
            to_update.append(cname)
    if to_create or to_update:
        if __opts__['test']:
            msg = 'ELB {0} to have cnames modified.'.format(name)
            ret['comment'] = msg
            return ret
        if to_create:
            created = []
            not_created = []
            for cname in to_create:
                _name = cname.get('name')
                _zone = cname.get('zone')
                _iden = cname.get('identifier', None)
                _ttl = cname.get('ttl', None)
                _created = __salt__['boto_route53.add_record'](
                    _name, lb['dns_name'], _zone, 'CNAME', _iden, _ttl, region,
                    key, keyid, profile)
                if _created:
                    created.append(_name)
                else:
                    not_created.append(_name)
            if created:
                msg = 'Created cnames {0}.'.format(','.join(created))
                ret['comment'] = msg
                ret['result'] = True
            if not_created:
                msg = 'Failed to create cnames {0}.'
                msg = msg.format(','.join(not_created))
                if 'comment' in ret:
                    ret['comment'] = ret['comment'] + ' ' + msg
                else:
                    ret['comment'] = msg
                ret['result'] = False
        if to_update:
            updated = []
            not_updated = []
            for cname in to_update:
                _name = cname.get('name')
                _zone = cname.get('zone')
                _iden = cname.get('identifier', None)
                _ttl = cname.get('ttl', None)
                _updated = __salt__['boto_route53.update_record'](
                    _name, lb['dns_name'], _zone, 'CNAME', _iden, _ttl, region,
                    key, keyid, profile)
                if _updated:
                    updated.append(_name)
                else:
                    not_updated.append(_name)
            if updated:
                msg = 'Updated cnames {0}.'.format(','.join(updated))
                if 'comment' in ret:
                    ret['comment'] = ret['comment'] + ' ' + msg
                else:
                    ret['comment'] = msg
                if ret['result'] is not False:
                    ret['result'] = True
            if not_updated:
                msg = 'Failed to update cnames {0}.'
                msg = msg.format(','.join(not_updated))
                if 'comment' in ret:
                    ret['comment'] = ret['comment'] + ' ' + msg
                else:
                    ret['comment'] = msg
                ret['result'] = False
        # We can't track old, since we'd need to know the zone to
        # search for the ELB in the value.
        ret['changes']['new'] = {'cnames': to_create + to_update}
    else:
        msg = 'cnames already set on ELB {0}.'.format(name)
        ret['comment'] = msg
    return ret


def absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    exists = __salt__['boto_elb.exists'](name, region, key, keyid, profile)
    if exists:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'ELB {0} is set to be removed.'.format(name)
            return ret
        deleted = __salt__['boto_elb.delete'](name, region, key, keyid,
                                              profile)
        if deleted:
            ret['result'] = True
            ret['changes']['old'] = {'elb': name}
            ret['changes']['new'] = {'elb': None}
            ret['comment'] = 'ELB {0} deleted.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} ELB.'.format(name)
    else:
        ret['comment'] = '{0} ELB does not exist.'.format(name)
    return ret
