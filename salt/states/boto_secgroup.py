# -*- coding: utf-8 -*-
'''
Manage Security Groups
======================

.. versionadded:: 2014.7.0

Create and destroy Security Groups. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit EC2 credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    secgroup.keyid: GKTADJGHEIQSXMKKRBJ08H
    secgroup.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        region: us-east-1

.. code-block:: yaml

    Ensure mysecgroup exists:
        boto_secgroup.present:
            - name: mysecgroup
            - description: My security group
            - vpc_name: myvpc
            - rules:
                - ip_protocol: tcp
                  from_port: 80
                  to_port: 80
                  cidr_ip:
                    - 10.0.0.0/8
                    - 192.168.0.0/16
                - ip_protocol: tcp
                  from_port: 8080
                  to_port: 8090
                  cidr_ip:
                    - 10.0.0.0/8
                    - 192.168.0.0/16
                - ip_protocol: icmp
                  from_port: -1
                  to_port: -1
                  source_group_name: mysecgroup
            - rules_egress:
                - ip_protocol: all
                  from_port: -1
                  to_port: -1
                  cidr_ip:
                    - 10.0.0.0/8
                    - 192.168.0.0/16
            - tags:
                SomeTag: 'My Tag Value'
                SomeOtherTag: 'Other Tag Value'
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    # Using a profile from pillars
    Ensure mysecgroup exists:
        boto_secgroup.present:
            - name: mysecgroup
            - description: My security group
            - profile: myprofile

    # Passing in a profile
    Ensure mysecgroup exists:
        boto_secgroup.present:
            - name: mysecgroup
            - description: My security group
            - profile:
                keyid: GKTADJGHEIQSXMKKRBJ08H
                key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
                region: us-east-1

.. note::

    When using the ``profile`` parameter and ``region`` is set outside of
    the profile group, region is ignored and a default region will be used.

    If ``region`` is missing from the ``profile`` data set, ``us-east-1``
    will be used as the default region.

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging
import pprint

# Import salt libs
import salt.utils.dictupdate as dictupdate
from salt.exceptions import SaltInvocationError
from salt.ext import six

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_secgroup' if 'boto_secgroup.exists' in __salt__ else False


def present(
        name,
        description,
        vpc_id=None,
        vpc_name=None,
        rules=None,
        rules_egress=None,
        delete_ingress_rules=True,
        delete_egress_rules=True,
        region=None,
        key=None,
        keyid=None,
        profile=None,
        tags=None):
    '''
    Ensure the security group exists with the specified rules.

    name
        Name of the security group.

    description
        A description of this security group.

    vpc_id
        The ID of the VPC to create the security group in, if any. Exclusive with vpc_name.

    vpc_name
        The name of the VPC to create the security group in, if any. Exclusive with vpc_id.

        .. versionadded:: 2016.3.0

        .. versionadded:: 2015.8.2

    rules
        A list of ingress rule dicts. If not specified, ``rules=None``,
        the ingress rules will be unmanaged. If set to an empty list, ``[]``,
        then all ingress rules will be removed.

    rules_egress
        A list of egress rule dicts. If not specified, ``rules_egress=None``,
        the egress rules will be unmanaged. If set to an empty list, ``[]``,
        then all egress rules will be removed.

    delete_ingress_rules
        Some tools (EMR comes to mind) insist on adding rules on-the-fly, which
        salt will happily remove on the next run.  Set this param to False to
        avoid deleting rules which were added outside of salt.

    delete_egress_rules
        Some tools (EMR comes to mind) insist on adding rules on-the-fly, which
        salt will happily remove on the next run.  Set this param to False to
        avoid deleting rules which were added outside of salt.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key, and keyid.

    tags
        List of key:value pairs of tags to set on the security group

        .. versionadded:: 2016.3.0
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    _ret = _security_group_present(name, description, vpc_id=vpc_id,
                                   vpc_name=vpc_name, region=region,
                                   key=key, keyid=keyid, profile=profile)
    ret['changes'] = _ret['changes']
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
        elif ret['result'] is None:
            return ret
    if rules is not None:
        _ret = _rules_present(name, rules, delete_ingress_rules, vpc_id=vpc_id,
                              vpc_name=vpc_name, region=region, key=key,
                              keyid=keyid, profile=profile)
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
    if rules_egress is not None:
        _ret = _rules_egress_present(name, rules_egress, delete_egress_rules,
                                     vpc_id=vpc_id, vpc_name=vpc_name,
                                     region=region, key=key, keyid=keyid,
                                     profile=profile)
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
    _ret = _tags_present(
        name=name, tags=tags, vpc_id=vpc_id, vpc_name=vpc_name,
        region=region, key=key, keyid=keyid, profile=profile
    )
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
    return ret


def _security_group_present(name, description, vpc_id=None, vpc_name=None,
                            region=None, key=None, keyid=None, profile=None):
    '''
    given a group name or a group name and vpc id (or vpc name):
    1. determine if the group exists
    2. if the group does not exist, creates the group
    3. return the group's configuration and any changes made
    '''
    ret = {'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto_secgroup.exists'](name, region, key, keyid,
                                              profile, vpc_id, vpc_name)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'Security group {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_secgroup.create'](name=name, description=description,
                                                   vpc_id=vpc_id, vpc_name=vpc_name,
                                                   region=region, key=key, keyid=keyid,
                                                   profile=profile)
        if created:
            ret['changes']['old'] = {'secgroup': None}
            sg = __salt__['boto_secgroup.get_config'](name=name, group_id=None, region=region, key=key,
                                              keyid=keyid, profile=profile, vpc_id=vpc_id,
                                              vpc_name=vpc_name)
            ret['changes']['new'] = {'secgroup': sg}
            ret['comment'] = 'Security group {0} created.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} security group.'.format(name)
    else:
        ret['comment'] = 'Security group {0} present.'.format(name)
    return ret


def _split_rules(rules):
    '''
    Split rules with lists into individual rules.

    We accept some attributes as lists or strings. The data we get back from
    the execution module lists rules as individual rules. We need to split the
    provided rules into individual rules to compare them.
    '''
    split = []
    for rule in rules:
        cidr_ip = rule.get('cidr_ip')
        group_name = rule.get('source_group_name')
        group_id = rule.get('source_group_group_id')
        if cidr_ip and not isinstance(cidr_ip, six.string_types):
            for ip in cidr_ip:
                _rule = rule.copy()
                _rule['cidr_ip'] = ip
                split.append(_rule)
        elif group_name and not isinstance(group_name, six.string_types):
            for name in group_name:
                _rule = rule.copy()
                _rule['source_group_name'] = name
                split.append(_rule)
        elif group_id and not isinstance(group_id, six.string_types):
            for _id in group_id:
                _rule = rule.copy()
                _rule['source_group_group_id'] = _id
                split.append(_rule)
        else:
            split.append(rule)
    return split


def _check_rule(rule, _rule):
    '''
    Check to see if two rules are the same. Needed to compare rules fetched
    from boto, since they may not completely match rules defined in sls files
    but may be functionally equivalent.
    '''

    # We need to alter what Boto returns if no ports are specified
    # so that we can compare rules fairly.
    #
    # Boto returns None for from_port and to_port where we're required
    # to pass in "-1" instead.
    if _rule.get('from_port') is None:
        _rule['from_port'] = -1
    if _rule.get('to_port') is None:
        _rule['to_port'] = -1

    if (rule['ip_protocol'] == _rule['ip_protocol'] and
            six.text_type(rule['from_port']) == six.text_type(_rule['from_port']) and
            six.text_type(rule['to_port']) == six.text_type(_rule['to_port'])):
        _cidr_ip = _rule.get('cidr_ip')
        if _cidr_ip and _cidr_ip == rule.get('cidr_ip'):
            return True
        _owner_id = _rule.get('source_group_owner_id')
        if _owner_id and _owner_id == rule.get('source_group_owner_id'):
            return True
        _group_id = _rule.get('source_group_group_id')
        if _group_id and _group_id == rule.get('source_group_group_id'):
            return True
        _group_name = _rule.get('source_group_name')
        if _group_name and _group_id == rule.get('source_group_name'):
            return True
    return False


def _get_rule_changes(rules, _rules):
    '''
    given a list of desired rules (rules) and existing rules (_rules) return
    a list of rules to delete (to_delete) and to create (to_create)
    '''
    to_delete = []
    to_create = []
    # for each rule in state file
    # 1. validate rule
    # 2. determine if rule exists in existing security group rules
    for rule in rules:
        try:
            ip_protocol = six.text_type(rule.get('ip_protocol'))
        except KeyError:
            raise SaltInvocationError('ip_protocol, to_port, and from_port are'
                                      ' required arguments for security group'
                                      ' rules.')
        supported_protocols = ['tcp', '6', 6, 'udp', '17', 17, 'icmp', '1', 1,
                               'all', '-1', -1]
        if ip_protocol not in supported_protocols and (not
              '{0}'.format(ip_protocol).isdigit() or int(ip_protocol) > 255):
            raise SaltInvocationError(
                'Invalid ip_protocol {0} specified in security group rule.'.format(ip_protocol))
        # For the 'all' case, we need to change the protocol name to '-1'.
        if ip_protocol == 'all':
            rule['ip_protocol'] = '-1'
        cidr_ip = rule.get('cidr_ip', None)
        group_name = rule.get('source_group_name', None)
        group_id = rule.get('source_group_group_id', None)
        if cidr_ip and (group_id or group_name):
            raise SaltInvocationError('cidr_ip and source groups can not both'
                                      ' be specified in security group rules.')
        if group_id and group_name:
            raise SaltInvocationError('Either source_group_group_id or'
                                      ' source_group_name can be specified in'
                                      ' security group rules, but not both.')
        if not (cidr_ip or group_id or group_name):
            raise SaltInvocationError('cidr_ip, source_group_group_id, or'
                                      ' source_group_name must be provided for'
                                      ' security group rules.')
        rule_found = False
        # for each rule in existing security group ruleset determine if
        # new rule exists
        for _rule in _rules:
            if _check_rule(rule, _rule):
                rule_found = True
                break
        if not rule_found:
            to_create.append(rule)
    # for each rule in existing security group configuration
    # 1. determine if rules needed to be deleted
    for _rule in _rules:
        rule_found = False
        for rule in rules:
            if _check_rule(rule, _rule):
                rule_found = True
                break
        if not rule_found:
            # Can only supply name or id, not both. Since we're deleting
            # entries, it doesn't matter which we pick.
            _rule.pop('source_group_name', None)
            to_delete.append(_rule)
    log.debug('Rules to be deleted: %s', to_delete)
    log.debug('Rules to be created: %s', to_create)
    return (to_delete, to_create)


def _rules_present(name, rules, delete_ingress_rules=True, vpc_id=None,
                   vpc_name=None, region=None, key=None, keyid=None, profile=None):
    '''
    given a group name or group name and vpc_id (or vpc name):
    1. get lists of desired rule changes (using _get_rule_changes)
    2. authorize/create rules missing rules
    3. if delete_ingress_rules is True, delete/revoke non-requested rules
    4. return 'old' and 'new' group rules
    '''
    ret = {'result': True, 'comment': '', 'changes': {}}
    sg = __salt__['boto_secgroup.get_config'](name=name, group_id=None, region=region, key=key,
                                              keyid=keyid, profile=profile, vpc_id=vpc_id,
                                              vpc_name=vpc_name)
    if not sg:
        ret['comment'] = '{0} security group configuration could not be retrieved.'.format(name)
        ret['result'] = False
        return ret
    rules = _split_rules(rules)
    if vpc_id or vpc_name:
        for rule in rules:
            _source_group_name = rule.get('source_group_name', None)
            if _source_group_name:
                _group_id = __salt__['boto_secgroup.get_group_id'](
                    name=_source_group_name, vpc_id=vpc_id, vpc_name=vpc_name,
                    region=region, key=key, keyid=keyid, profile=profile
                )
                if not _group_id:
                    raise SaltInvocationError(
                        'source_group_name {0} does not map to a valid '
                        'source group id.'.format(_source_group_name)
                    )
                rule['source_group_name'] = None
                rule['source_group_group_id'] = _group_id
    # rules = rules that exist in salt state
    # sg['rules'] = that exist in present group
    to_delete, to_create = _get_rule_changes(rules, sg['rules'])
    to_delete = to_delete if delete_ingress_rules else []
    if to_create or to_delete:
        if __opts__['test']:
            msg = """Security group {0} set to have rules modified.
            To be created: {1}
            To be deleted: {2}""".format(name, pprint.pformat(to_create),
                                         pprint.pformat(to_delete))
            ret['comment'] = msg
            ret['result'] = None
            return ret
        if to_delete:
            deleted = True
            for rule in to_delete:
                _deleted = __salt__['boto_secgroup.revoke'](
                    name, vpc_id=vpc_id, vpc_name=vpc_name, region=region,
                    key=key, keyid=keyid, profile=profile, **rule)
                if not _deleted:
                    deleted = False
            if deleted:
                ret['comment'] = 'Removed rules on {0} security group.'.format(name)
            else:
                ret['comment'] = 'Failed to remove rules on {0} security group.'.format(name)
                ret['result'] = False
        if to_create:
            created = True
            for rule in to_create:
                _created = __salt__['boto_secgroup.authorize'](
                    name, vpc_id=vpc_id, vpc_name=vpc_name, region=region,
                    key=key, keyid=keyid, profile=profile, **rule)
                if not _created:
                    created = False
            if created:
                ret['comment'] = ' '.join([
                    ret['comment'],
                    'Created rules on {0} security group.'.format(name)
                ])
            else:
                ret['comment'] = ' '.join([
                    ret['comment'],
                    'Failed to create rules on {0} security group.'.format(name)
                ])
                ret['result'] = False
        ret['changes']['old'] = {'rules': sg['rules']}
        sg = __salt__['boto_secgroup.get_config'](name=name, group_id=None, region=region, key=key,
                                                  keyid=keyid, profile=profile, vpc_id=vpc_id,
                                                  vpc_name=vpc_name)
        ret['changes']['new'] = {'rules': sg['rules']}
    return ret


def _rules_egress_present(name, rules_egress, delete_egress_rules=True, vpc_id=None,
                          vpc_name=None, region=None, key=None, keyid=None, profile=None):
    '''
    given a group name or group name and vpc_id (or vpc name):
    1. get lists of desired rule changes (using _get_rule_changes)
    2. authorize/create missing rules
    3. if delete_egress_rules is True, delete/revoke non-requested rules
    4. return 'old' and 'new' group rules
    '''
    ret = {'result': True, 'comment': '', 'changes': {}}
    sg = __salt__['boto_secgroup.get_config'](name=name, group_id=None, region=region, key=key,
                                              keyid=keyid, profile=profile, vpc_id=vpc_id,
                                              vpc_name=vpc_name)
    if not sg:
        ret['comment'] = '{0} security group configuration could not be retrieved.'.format(name)
        ret['result'] = False
        return ret
    rules_egress = _split_rules(rules_egress)
    if vpc_id or vpc_name:
        for rule in rules_egress:
            _source_group_name = rule.get('source_group_name', None)
            if _source_group_name:
                _group_id = __salt__['boto_secgroup.get_group_id'](
                    name=_source_group_name, vpc_id=vpc_id, vpc_name=vpc_name,
                    region=region, key=key, keyid=keyid, profile=profile
                )
                if not _group_id:
                    raise SaltInvocationError(
                        'source_group_name {0} does not map to a valid '
                        'source group id.'.format(_source_group_name)
                    )
                rule['source_group_name'] = None
                rule['source_group_group_id'] = _group_id
    # rules_egress = rules that exist in salt state
    # sg['rules_egress'] = that exist in present group
    to_delete, to_create = _get_rule_changes(rules_egress, sg['rules_egress'])
    to_delete = to_delete if delete_egress_rules else []
    if to_create or to_delete:
        if __opts__['test']:
            msg = """Security group {0} set to have rules modified.
            To be created: {1}
            To be deleted: {2}""".format(name, pprint.pformat(to_create),
                                         pprint.pformat(to_delete))
            ret['comment'] = msg
            ret['result'] = None
            return ret
        if to_delete:
            deleted = True
            for rule in to_delete:
                _deleted = __salt__['boto_secgroup.revoke'](
                    name, vpc_id=vpc_id, vpc_name=vpc_name, region=region,
                    key=key, keyid=keyid, profile=profile, egress=True, **rule)
                if not _deleted:
                    deleted = False
            if deleted:
                ret['comment'] = ' '.join([
                    ret['comment'],
                    'Removed egress rule on {0} security group.'.format(name)
                ])
            else:
                ret['comment'] = ' '.join([
                    ret['comment'],
                    'Failed to remove egress rule on {0} security group.'.format(name)
                ])
                ret['result'] = False
        if to_create:
            created = True
            for rule in to_create:
                _created = __salt__['boto_secgroup.authorize'](
                    name, vpc_id=vpc_id, vpc_name=vpc_name, region=region,
                    key=key, keyid=keyid, profile=profile, egress=True, **rule)
                if not _created:
                    created = False
            if created:
                ret['comment'] = ' '.join([
                    ret['comment'],
                    'Created egress rules on {0} security group.'.format(name)
                ])
            else:
                ret['comment'] = ' '.join([
                    ret['comment'],
                    'Failed to create egress rules on {0} security group.'.format(name)
                ])
                ret['result'] = False

        ret['changes']['old'] = {'rules_egress': sg['rules_egress']}
        sg = __salt__['boto_secgroup.get_config'](name=name, group_id=None, region=region, key=key,
                                                  keyid=keyid, profile=profile, vpc_id=vpc_id,
                                                  vpc_name=vpc_name)
        ret['changes']['new'] = {'rules_egress': sg['rules_egress']}
    return ret


def absent(
        name,
        vpc_id=None,
        vpc_name=None,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure a security group with the specified name does not exist.

    name
        Name of the security group.

    vpc_id
        The ID of the VPC to remove the security group from, if any. Exclusive with vpc_name.

    vpc_name
        The name of the VPC to remove the security group from, if any. Exclusive with vpc_name.

        .. versionadded:: 2016.3.0

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.

        .. versionadded:: 2016.3.0
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    sg = __salt__['boto_secgroup.get_config'](name=name, group_id=None, region=region, key=key,
                                              keyid=keyid, profile=profile, vpc_id=vpc_id,
                                              vpc_name=vpc_name)

    if sg:
        if __opts__['test']:
            ret['comment'] = 'Security group {0} is set to be removed.'.format(name)
            ret['result'] = None
            return ret
        deleted = __salt__['boto_secgroup.delete'](name=name, group_id=None, region=region, key=key,
                                                   keyid=keyid, profile=profile, vpc_id=vpc_id,
                                                   vpc_name=vpc_name)
        if deleted:
            ret['changes']['old'] = {'secgroup': sg}
            ret['changes']['new'] = {'secgroup': None}
            ret['comment'] = 'Security group {0} deleted.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} security group.'.format(name)
    else:
        ret['comment'] = '{0} security group does not exist.'.format(name)
    return ret


def _tags_present(name, tags, vpc_id=None, vpc_name=None, region=None,
                  key=None, keyid=None, profile=None):
    '''
    helper function to validate tags are correct
    '''
    ret = {'result': True, 'comment': '', 'changes': {}}
    if tags:
        sg = __salt__['boto_secgroup.get_config'](name=name, group_id=None, region=region, key=key,
                                                  keyid=keyid, profile=profile, vpc_id=vpc_id,
                                                  vpc_name=vpc_name)
        if not sg:
            ret['comment'] = '{0} security group configuration could not be retrieved.'.format(name)
            ret['result'] = False
            return ret
        tags_to_add = tags
        tags_to_update = {}
        tags_to_remove = []
        if sg.get('tags'):
            for existing_tag in sg['tags']:
                if existing_tag not in tags:
                    if existing_tag not in tags_to_remove:
                        tags_to_remove.append(existing_tag)
                else:
                    if tags[existing_tag] != sg['tags'][existing_tag]:
                        tags_to_update[existing_tag] = tags[existing_tag]
                    tags_to_add.pop(existing_tag)
        if tags_to_remove:
            if __opts__['test']:
                msg = 'The following tag{0} set to be removed: {1}.'.format(
                        ('s are' if len(tags_to_remove) > 1 else ' is'), ', '.join(tags_to_remove))
                ret['comment'] = ' '.join([ret['comment'], msg])
                ret['result'] = None
            else:
                temp_ret = __salt__['boto_secgroup.delete_tags'](tags_to_remove,
                                                                 name=name,
                                                                 group_id=None,
                                                                 vpc_name=vpc_name,
                                                                 vpc_id=vpc_id,
                                                                 region=region,
                                                                 key=key,
                                                                 keyid=keyid,
                                                                 profile=profile)
                if not temp_ret:
                    ret['result'] = False
                    ret['comment'] = ' '.join([
                        ret['comment'],
                        'Error attempting to delete tags {0}.'.format(tags_to_remove)
                    ])
                    return ret
                if 'old' not in ret['changes']:
                    ret['changes'] = dictupdate.update(ret['changes'], {'old': {'tags': {}}})
                for rem_tag in tags_to_remove:
                    ret['changes']['old']['tags'][rem_tag] = sg['tags'][rem_tag]
        if tags_to_add or tags_to_update:
            if __opts__['test']:
                if tags_to_add:
                    msg = 'The following tag{0} set to be added: {1}.'.format(
                            ('s are' if len(tags_to_add.keys()) > 1 else ' is'),
                            ', '.join(tags_to_add.keys()))
                    ret['comment'] = ' '.join([ret['comment'], msg])
                    ret['result'] = None
                if tags_to_update:
                    msg = 'The following tag {0} set to be updated: {1}.'.format(
                            ('values are' if len(tags_to_update.keys()) > 1 else 'value is'),
                            ', '.join(tags_to_update.keys()))
                    ret['comment'] = ' '.join([ret['comment'], msg])
                    ret['result'] = None
            else:
                all_tag_changes = dictupdate.update(tags_to_add, tags_to_update)
                temp_ret = __salt__['boto_secgroup.set_tags'](all_tag_changes,
                                                              name=name,
                                                              group_id=None,
                                                              vpc_name=vpc_name,
                                                              vpc_id=vpc_id,
                                                              region=region,
                                                              key=key,
                                                              keyid=keyid,
                                                              profile=profile)
                if not temp_ret:
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
                    if 'tags' in sg:
                        if sg['tags']:
                            if tag in sg['tags']:
                                ret['changes']['old']['tags'][tag] = sg['tags'][tag]
        if not tags_to_update and not tags_to_remove and not tags_to_add:
            ret['comment'] = ' '.join([ret['comment'], 'Tags are already set.'])
    return ret
