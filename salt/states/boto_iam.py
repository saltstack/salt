# -*- coding: utf-8 -*-
'''
Manage IAM objects
==================

.. versionadded:: 2015.8.0

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit IAM credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    delete-user:
      boto_iam.user_absent:
        - name: myuser
        - delete_keys: true


.. code-block:: yaml

    delete-keys:
      boto_iam.keys_absent:
        - access_keys:
          - 'AKIAJHTMIQ2ASDFLASDF'
          - 'PQIAJHTMIQ2ASRTLASFR'
        - user_name: myuser

.. code-block:: yaml

    create-user:
      boto_iam.user_present:
        - name: myuser
        - policies:
            mypolicy: |
                {
                    "Version": "2012-10-17",
                    "Statement": [{
                    "Effect": "Allow",
                    "Action": "*",
                    "Resource": "*"}]
                }
        - password: NewPassword$$1
        - region: eu-west-1
        - keyid: 'AKIAJHTMIQ2ASDFLASDF'
        - key: 'fdkjsafkljsASSADFalkfjasdf'

.. code-block:: yaml

    create-group:
      boto_iam.group_present:
        - name: mygroup
        - users:
          - myuser
          - myuser1
        - policies:
            mypolicy: |
                {
                    "Version": "2012-10-17",
                    "Statement": [{
                    "Effect": "Allow",
                    "Action": "*",
                    "Resource": "*"}]
                }
        - region: eu-west-1
        - keyid: 'AKIAJHTMIQ2ASDFLASDF'
        - key: 'safsdfsal;fdkjsafkljsASSADFalkfj'

.. code-block:: yaml

    change-policy:
      boto_iam.account_policy:
        - change_password: True
        - region: eu-west-1
        - keyid: 'AKIAJHTMIQ2ASDFLASDF'
        - key: 'safsdfsal;fdkjsafkljsASSADFalkfj'

.. code-block:: yaml

    create server certificate:
      boto_iam.server_cert_present:
        - name: mycert
        - public_key: salt://base/mycert.crt
        - private_key: salt://base/mycert.key
        - cert_chain: salt://base/mycert_chain.crt
        - region: eu-west-1
        - keyid: 'AKIAJHTMIQ2ASDFLASDF'
        - key: 'fdkjsafkljsASSADFalkfjasdf'

.. code-block:: yaml

    delete server certificate:
      boto_iam.server_cert_absent:
        - name: mycert

.. code-block:: yaml

    create keys for user:
      boto_iam.keys_present:
        - name: myusername
        - number: 2
        - save_dir: /root
        - region: eu-west-1
        - keyid: 'AKIAJHTMIQ2ASDFLASDF'
        - key: 'fdkjsafkljsASSADFalkfjasdf'
'''

# Import Python Libs
from __future__ import absolute_import
import logging
import json
import os

# Import Salt Libs
import salt.utils
import salt.utils.odict as odict
import salt.utils.dictupdate as dictupdate
import salt.ext.six as six
from salt.ext.six import string_types
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import 3rd party libs
try:
    from salt._compat import ElementTree as ET
    HAS_ELEMENT_TREE = True
except ImportError:
    HAS_ELEMENT_TREE = False

log = logging.getLogger(__name__)

__virtualname__ = 'boto_iam'


def __virtual__():
    '''
    Only load if elementtree xml library and boto are available.
    '''
    if not HAS_ELEMENT_TREE:
        return (False, 'Cannot load {0} state: ElementTree library unavailable'.format(__virtualname__))

    if 'boto_iam.get_user' in __salt__:
        return True
    else:
        return (False, 'Cannot load {0} state: boto_iam module unavailable'.format(__virtualname__))


def user_absent(name, delete_keys=None, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the IAM user is absent. User cannot be deleted if it has keys.

    name (string)
        The name of the new user.

    delete_keys (bool)
        Delete all keys from user.

    region (string)
        Region to connect to.

    key (string)
        Secret key to be used.

    keyid (string)
        Access key to be used.

    profile (dict)
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if not __salt__['boto_iam.get_user'](name, region, key, keyid, profile):
        ret['result'] = True
        ret['comment'] = 'IAM User {0} does not exist.'.format(name)
        return ret
    if 'true' == str(delete_keys).lower():
        keys = __salt__['boto_iam.get_all_access_keys'](user_name=name, region=region, key=key,
                                                        keyid=keyid, profile=profile)
        log.debug('Keys for user {0} are {1}.'.format(name, keys))
        if isinstance(keys, dict):
            keys = keys['list_access_keys_response']['list_access_keys_result']['access_key_metadata']
            for k in keys:
                if __opts__['test']:
                    ret['comment'] = 'Access key {0} is set to be deleted.'.format(k['access_key_id'])
                    ret['result'] = None
                    return ret
                ret = _delete_key(ret, k['access_key_id'], name, region, key, keyid, profile)
    if __opts__['test']:
        ret['comment'] = 'IAM user {0} is set to be deleted.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_iam.delete_user'](name, region, key, keyid, profile)
    if deleted is True:
        ret['comment'] = os.linesep.join([ret['comment'], 'IAM user {0} is deleted.'.format(name)])
        ret['result'] = True
        ret['changes']['deleted'] = name
        return ret
    ret['comment'] = 'IAM user {0} could not be deleted.\n {1}'.format(name, deleted)
    ret['result'] = False
    return ret


def keys_present(name, number, save_dir, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the IAM access keys are present.

    name (string)
        The name of the new user.

    number (int)
        Number of keys that user should have.

    save_dir (string)
        The directory that the key/keys will be saved. Keys are saved to a file named according
        to the username privided.

    region (string)
        Region to connect to.

    key (string)
        Secret key to be used.

    keyid (string)
        Access key to be used.

    profile (dict)
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if not __salt__['boto_iam.get_user'](name, region, key, keyid, profile):
        ret['result'] = False
        ret['comment'] = 'IAM User {0} does not exist.'.format(name)
        return ret
    if not isinstance(number, int):
        ret['comment'] = 'The number of keys must be an integer.'
        ret['result'] = False
        return ret
    if not os.path.isdir(save_dir):
        ret['comment'] = 'The directory {0} does not exist.'.format(save_dir)
        ret['result'] = False
        return ret
    keys = __salt__['boto_iam.get_all_access_keys'](user_name=name, region=region, key=key,
                                                    keyid=keyid, profile=profile)
    if isinstance(keys, str):
        log.debug('keys are : false {0}'.format(keys))
        error, message = _get_error(keys)
        ret['comment'] = 'Could not get keys.\n{0}\n{1}'.format(error, message)
        ret['result'] = False
        return ret
    keys = keys['list_access_keys_response']['list_access_keys_result']['access_key_metadata']
    log.debug('Keys are : {0}.'.format(keys))
    if len(keys) >= number:
        ret['comment'] = 'The number of keys exist for user {0}'.format(name)
        ret['result'] = True
        return ret
    if __opts__['test']:
        ret['comment'] = 'Access key is set to be created for {0}.'.format(name)
        ret['result'] = None
        return ret
    new_keys = {}
    for i in range(number-len(keys)):
        created = __salt__['boto_iam.create_access_key'](name, region, key, keyid, profile)
        if isinstance(created, str):
            error, message = _get_error(created)
            ret['comment'] = 'Could not create keys.\n{0}\n{1}'.format(error, message)
            ret['result'] = False
            return ret
        log.debug('Created is : {0}'.format(created))
        response = 'create_access_key_response'
        result = 'create_access_key_result'
        new_keys['key-{0}'.format(i)] = created[response][result]['access_key']['access_key_id']
        new_keys['key_id-{0}'.format(i)] = created[response][result]['access_key']['secret_access_key']
    try:
        with salt.utils.fopen('{0}/{1}'.format(save_dir, name), 'a') as _wrf:
            for key_id, access_key in new_keys.items():
                _wrf.write('{0}\n{1}\n'.format(key_id, access_key))
        ret['comment'] = 'Keys have been written to file {0}/{1}.'.format(save_dir, name)
        ret['result'] = True
        ret['changes'] = new_keys
        return ret
    except IOError:
        ret['comment'] = 'Could not write to file {0}/{1}.'.format(save_dir, name)
        ret['result'] = False
        return ret


def keys_absent(access_keys, user_name, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the IAM user access_key_id is absent.

    access_key_id (list)
        A list of access key ids

    user_name (string)
        The username of the user

    region (string)
        Region to connect to.

    key (string)
        Secret key to be used.

    keyid (string)
        Access key to be used.

    profile (dict)
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': access_keys, 'result': True, 'comment': '', 'changes': {}}
    if not __salt__['boto_iam.get_user'](user_name, region, key, keyid, profile):
        ret['result'] = False
        ret['comment'] = 'IAM User {0} does not exist.'.format(user_name)
        return ret
    for k in access_keys:
        ret = _delete_key(ret, k, user_name, region, key, keyid, profile)
    return ret


def _delete_key(ret, access_key_id, user_name, region=None, key=None, keyid=None, profile=None):
    keys = __salt__['boto_iam.get_all_access_keys'](user_name=user_name, region=region, key=key,
                                                    keyid=keyid, profile=profile)
    log.debug('Keys for user {1} are : {0}.'.format(keys, user_name))
    if isinstance(keys, str):
        log.debug('Keys {0} are a string. Something went wrong.'.format(keys))
        ret['comment'] = os.linesep.join([ret['comment'], 'Key {0} could not be deleted.'.format(access_key_id)])
        return ret
    keys = keys['list_access_keys_response']['list_access_keys_result']['access_key_metadata']
    for k in keys:
        log.debug('Key is: {0} and is compared with: {1}'.format(k['access_key_id'], access_key_id))
        if str(k['access_key_id']) == str(access_key_id):
            if __opts__['test']:
                ret['comment'] = 'Access key {0} is set to be deleted.'.format(access_key_id)
                ret['result'] = None
                return ret
            deleted = __salt__['boto_iam.delete_access_key'](access_key_id, user_name, region, key,
                                                             keyid, profile)
            if deleted:
                ret['comment'] = os.linesep.join([ret['comment'], 'Key {0} has been deleted.'.format(access_key_id)])
                ret['changes'][access_key_id] = 'deleted'
                return ret
            ret['comment'] = os.linesep.join([ret['comment'], 'Key {0} could not be deleted.'.format(access_key_id)])
            return ret
        ret['comment'] = os.linesep.join([ret['comment'], 'Key {0} does not exist.'.format(k)])
        return ret


def user_present(name, policies=None, policies_from_pillars=None, password=None, path=None, region=None, key=None,
                 keyid=None, profile=None):
    '''
    Ensure the IAM user is present

    name (string)
        The name of the new user.

    policies (dict)
        A dict of IAM group policy documents.

    policies_from_pillars (list)
        A list of pillars that contain role policy dicts. Policies in the
        pillars will be merged in the order defined in the list and key
        conflicts will be handled by later defined keys overriding earlier
        defined keys. The policies defined here will be merged with the
        policies defined in the policies argument. If keys conflict, the keys
        in the policies argument will override the keys defined in
        policies_from_pillars.

    password (string)
        The password for the new user. Must comply with account policy.

    path (string)
        The path of the user. Default is '/'.

        .. versionadded:: 2015.8.2

    region (string)
        Region to connect to.

    key (string)
        Secret key to be used.

    keyid (string)
        Access key to be used.

    profile (dict)
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if not policies:
        policies = {}
    if not policies_from_pillars:
        policies_from_pillars = []
    _policies = {}
    for policy in policies_from_pillars:
        _policy = __salt__['pillar.get'](policy)
        _policies.update(_policy)
    _policies.update(policies)
    exists = __salt__['boto_iam.get_user'](name, region, key, keyid, profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'IAM user {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_iam.create_user'](name, path, region, key, keyid, profile)
        if created:
            ret['changes']['user'] = created
            ret['comment'] = os.linesep.join([ret['comment'], 'User {0} has been created.'.format(name)])
            if password:
                ret = _case_password(ret, name, password, region, key, keyid, profile)
            _ret = _user_policies_present(name, _policies, region, key, keyid, profile)
            ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
            ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    else:
        ret['comment'] = os.linesep.join([ret['comment'], 'User {0} is present.'.format(name)])
        if password:
            ret = _case_password(ret, name, password, region, key, keyid, profile)
        _ret = _user_policies_present(name, _policies, region, key, keyid, profile)
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    return ret


def _user_policies_present(name, policies=None, region=None, key=None, keyid=None, profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    policies_to_create = {}
    policies_to_delete = []
    for policy_name, policy in six.iteritems(policies):
        if isinstance(policy, string_types):
            dict_policy = json.loads(
                policy, object_pairs_hook=odict.OrderedDict
            )
        else:
            dict_policy = policy
        _policy = __salt__['boto_iam.get_user_policy'](
            name, policy_name, region, key, keyid, profile
        )
        if _policy != dict_policy:
            policies_to_create[policy_name] = policy
    _list = __salt__['boto_iam.get_all_user_policies'](
        user_name=name, region=region, key=key, keyid=keyid, profile=profile
    )
    for policy_name in _list:
        if policy_name not in policies:
            policies_to_delete.append(policy_name)
    if policies_to_create or policies_to_delete:
        _to_modify = list(policies_to_delete)
        _to_modify.extend(policies_to_create)
        if __opts__['test']:
            msg = '{0} policies to be modified on user {1}.'
            ret['comment'] = msg.format(', '.join(_to_modify), name)
            ret['result'] = None
            return ret
        ret['changes']['old'] = {'policies': _list}
        for policy_name, policy in six.iteritems(policies_to_create):
            policy_set = __salt__['boto_iam.put_user_policy'](
                name, policy_name, policy, region, key, keyid, profile
            )
            if not policy_set:
                _list = __salt__['boto_iam.get_all_user_policies'](
                    user_name=name, region=region, key=key, keyid=keyid, profile=profile
                )
                ret['changes']['new'] = {'policies': _list}
                ret['result'] = False
                msg = 'Failed to add policy {0} for user {1}'
                ret['comment'] = msg.format(policy_name, name)
                return ret
        for policy_name in policies_to_delete:
            policy_unset = __salt__['boto_iam.delete_user_policy'](
                name, policy_name, region, key, keyid, profile
            )
            if not policy_unset:
                _list = __salt__['boto_iam.get_all_user_policies'](
                    user_name=name, region=region, key=key, keyid=keyid, profile=profile
                )
                ret['changes']['new'] = {'policies': _list}
                ret['result'] = False
                msg = 'Failed to add policy {0} to user {1}'
                ret['comment'] = msg.format(policy_name, name)
                return ret
        _list = __salt__['boto_iam.get_all_user_policies'](
            user_name=name, region=region, key=key, keyid=keyid, profile=profile
        )
        ret['changes']['new'] = {'policies': _list}
        msg = '{0} policies modified on user {1}.'
        ret['comment'] = msg.format(', '.join(_list), name)
    return ret


def _case_password(ret, name, password, region=None, key=None, keyid=None, profile=None):
    if __opts__['test']:
        ret['comment'] = 'Login policy for {0} is set to be changed.'.format(name)
        ret['result'] = None
        return ret
    login = __salt__['boto_iam.create_login_profile'](name, password, region, key, keyid, profile)
    log.debug('Login is : {0}.'.format(login))
    if login:
        if 'Conflict' in login:
            ret['comment'] = os.linesep.join([ret['comment'], 'Login profile for user {0} exists.'.format(name)])
        else:
            ret['comment'] = os.linesep.join([ret['comment'], 'Password has been added to User {0}.'.format(name)])
            ret['changes']['password'] = password
    else:
        ret['result'] = False
        ret['comment'] = os.linesep.join([ret['comment'], 'Password for user {0} could not be set.\nPlease check your password policy.'.format(name)])
    return ret


def group_present(name, policies=None, policies_from_pillars=None, users=None, region=None, key=None, keyid=None, profile=None, path='/'):
    '''
    Ensure the IAM group is present

    name (string)
        The name of the new group.

    path (string)
        The path for the group, defaults to '/'

    policies (dict)
        A dict of IAM group policy documents.

    policies_from_pillars (list)
        A list of pillars that contain role policy dicts. Policies in the
        pillars will be merged in the order defined in the list and key
        conflicts will be handled by later defined keys overriding earlier
        defined keys. The policies defined here will be merged with the
        policies defined in the policies argument. If keys conflict, the keys
        in the policies argument will override the keys defined in
        policies_from_pillars.

    users (list)
        A list of users to be added to the group.

    region (string)
        Region to connect to.

    key (string)
        Secret key to be used.

    keyid (string)
        Access key to be used.

    profile (dict)
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if not policies:
        policies = {}
    if not policies_from_pillars:
        policies_from_pillars = []
    _policies = {}
    for policy in policies_from_pillars:
        _policy = __salt__['pillar.get'](policy)
        _policies.update(_policy)
    _policies.update(policies)
    exists = __salt__['boto_iam.get_group'](group_name=name, region=region, key=key, keyid=keyid, profile=profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'IAM group {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_iam.create_group'](group_name=name, path=path, region=region, key=key, keyid=keyid, profile=profile)
        if not created:
            ret['comment'] = 'Failed to create IAM group {0}.'.format(name)
            ret['result'] = False
            return ret
        ret['changes']['group'] = created
        ret['comment'] = os.linesep.join([ret['comment'], 'Group {0} has been created.'.format(name)])
    else:
        ret['comment'] = os.linesep.join([ret['comment'], 'Group {0} is present.'.format(name)])
    # Group exists, ensure group policies and users are set.
    _ret = _group_policies_present(
        name, _policies, region, key, keyid, profile
    )
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        return ret
    if users is not None:
        log.debug('Users are : {0}.'.format(users))
        group_result = __salt__['boto_iam.get_group'](group_name=name, region=region, key=key, keyid=keyid, profile=profile)
        ret = _case_group(ret, users, name, group_result, region, key, keyid, profile)
    return ret


def _case_group(ret, users, group_name, group_result, region, key, keyid, profile):
    _users = []
    for user in group_result['get_group_response']['get_group_result']['users']:
        _users.append(user['user_name'])
    log.debug('upstream users are {0}'.format(_users))
    for user in users:
        log.debug('users are {0}'.format(user))
        if user in _users:
            log.debug('user exists')
            ret['comment'] = os.linesep.join([ret['comment'], 'User {0} is already a member of group {1}.'.format(user, group_name)])
            continue
        else:
            log.debug('user is set to be added {0}'.format(user))
            if __opts__['test']:
                ret['comment'] = 'User {0} is set to be added to group {1}.'.format(user, group_name)
                ret['result'] = None
            else:
                addret = __salt__['boto_iam.add_user_to_group'](user, group_name, region=region, key=key, keyid=keyid, profile=profile)
                ret['comment'] = os.linesep.join([ret['comment'], 'User {0} has been added to group {1}.'.format(user, group_name)])
                ret['changes'][user] = group_name
    for user in _users:
        if user not in users:
            if __opts__['test']:
                ret['comment'] = os.linesep.join([ret['comment'], 'User {0} is set to be removed from group {1}.'.format(user, group_name)])
                ret['result'] = None
            else:
                remret = __salt__['boto_iam.remove_user_from_group'](group_name=group_name, user_name=user, region=region,
                                                                     key=key, keyid=keyid, profile=profile)
                ret['comment'] = os.linesep.join([ret['comment'], 'User {0} has been removed from group {1}.'.format(user, group_name)])
                ret['changes'][user] = 'Removed from group {0}.'.format(group_name)
    return ret


def _group_policies_present(
        name,
        policies=None,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    policies_to_create = {}
    policies_to_delete = []
    for policy_name, policy in six.iteritems(policies):
        if isinstance(policy, string_types):
            dict_policy = json.loads(
                policy, object_pairs_hook=odict.OrderedDict
            )
        else:
            dict_policy = policy
        _policy = __salt__['boto_iam.get_group_policy'](
            name, policy_name, region, key, keyid, profile
        )
        if _policy != dict_policy:
            policies_to_create[policy_name] = policy
    _list = __salt__['boto_iam.get_all_group_policies'](
        name, region, key, keyid, profile
    )
    for policy_name in _list:
        if policy_name not in policies:
            policies_to_delete.append(policy_name)
    if policies_to_create or policies_to_delete:
        _to_modify = list(policies_to_delete)
        _to_modify.extend(policies_to_create)
        if __opts__['test']:
            msg = '{0} policies to be modified on group {1}.'
            ret['comment'] = msg.format(', '.join(_to_modify), name)
            ret['result'] = None
            return ret
        ret['changes']['old'] = {'policies': _list}
        for policy_name, policy in six.iteritems(policies_to_create):
            policy_set = __salt__['boto_iam.put_group_policy'](
                name, policy_name, policy, region, key, keyid, profile
            )
            if not policy_set:
                _list = __salt__['boto_iam.get_all_group_policies'](
                    name, region, key, keyid, profile
                )
                ret['changes']['new'] = {'policies': _list}
                ret['result'] = False
                msg = 'Failed to add policy {0} to group {1}'
                ret['comment'] = msg.format(policy_name, name)
                return ret
        for policy_name in policies_to_delete:
            policy_unset = __salt__['boto_iam.delete_group_policy'](
                name, policy_name, region, key, keyid, profile
            )
            if not policy_unset:
                _list = __salt__['boto_iam.get_all_group_policies'](
                    name, region, key, keyid, profile
                )
                ret['changes']['new'] = {'policies': _list}
                ret['result'] = False
                msg = 'Failed to add policy {0} to group {1}'
                ret['comment'] = msg.format(policy_name, name)
                return ret
        _list = __salt__['boto_iam.get_all_group_policies'](
            name, region, key, keyid, profile
        )
        ret['changes']['new'] = {'policies': _list}
        msg = '{0} policies modified on group {1}.'
        ret['comment'] = msg.format(', '.join(_list), name)
    return ret


def account_policy(allow_users_to_change_password=None, hard_expiry=None, max_password_age=None,
                   minimum_password_length=None,
                   password_reuse_prevention=None,
                   require_lowercase_characters=None,
                   require_numbers=None, require_symbols=None,
                   require_uppercase_characters=None,
                   region=None, key=None, keyid=None,
                   profile=None):
    '''
    Change account policy.

    allow_users_to_change_password (bool)
        Allows all IAM users in your account to
        use the AWS Management Console to change their own passwords.

    hard_expiry (bool)
        Prevents IAM users from setting a new password after their
        password has expired.

    max_password_age (int)
        The number of days that an IAM user password is valid.

    minimum_password_length (int)
        The minimum number of characters allowed in an IAM user password.

    password_reuse_prevention (int)
        Specifies the number of previous passwords
        that IAM users are prevented from reusing.

    require_lowercase_characters (bool)
        Specifies whether IAM user passwords
        must contain at least one lowercase character from the ISO basic Latin alphabet (a to z).

    require_numbers (bool)
        Specifies whether IAM user passwords must contain at
        least one numeric character (0 to 9).

    require_symbols (bool)
        Specifies whether IAM user passwords must contain at
        least one of the following non-alphanumeric characters: ! @ # $ % ^ & * ( ) _ + - = [ ] { } | '

    require_uppercase_characters (bool)
        Specifies whether IAM user passwords must
        contain at least one uppercase character from the ISO basic Latin alphabet (A to Z).

    region (string)
        Region to connect to.

    key (string)
        Secret key to be used.

    keyid (string)
        Access key to be used.

    profile (dict)
        A dict with region, key and keyid, or a pillar key (string)
    '''
    config = locals()
    ret = {'name': 'Account Policy', 'result': True, 'comment': '', 'changes': {}}
    info = __salt__['boto_iam.get_account_policy'](region, key, keyid, profile)
    if not info:
        ret['comment'] = 'Account policy is not Enabled.'
        ret['result'] = False
        return ret
    for key, value in config.items():
        if key == 'region' or key == 'key' or key == 'keyid' or key == 'profile':
            continue
        if value is not None and str(info[key]) != str(value).lower():
            ret['comment'] = os.linesep.join([ret['comment'], 'Policy value {0} has been set to {1}.'.format(value, info[key])])
            ret['changes'][key] = str(value).lower()
    if not ret['changes']:
        ret['comment'] = 'Account policy is not changed.'
        return ret
    if __opts__['test']:
        ret['comment'] = 'Account policy is set to be changed.'
        ret['result'] = None
        return ret
    if __salt__['boto_iam.update_account_password_policy'](allow_users_to_change_password,
                                                           hard_expiry,
                                                           max_password_age,
                                                           minimum_password_length,
                                                           password_reuse_prevention,
                                                           require_lowercase_characters,
                                                           require_numbers,
                                                           require_symbols,
                                                           require_uppercase_characters,
                                                           region, key, keyid, profile):
        return ret
    ret['comment'] = 'Account policy is not changed.'
    ret['changes'] = None
    ret['result'] = False
    return ret


def server_cert_absent(name, region=None, key=None, keyid=None, profile=None):
    '''
    Deletes a server certificate.

    name (string)
        The name for the server certificate. Do not include the path in this value.

    region (string)
        The name of the region to connect to.

    key (string)
        The key to be used in order to connect

    keyid (string)
        The keyid to be used in order to connect

    profile (string)
        The profile that contains a dict of region, key, keyid
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto_iam.get_server_certificate'](name, region, key, keyid, profile)
    if not exists:
        ret['comment'] = 'Certificate {0} does not exist.'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Server certificate {0} is set to be deleted.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_iam.delete_server_cert'](name, region, key, keyid, profile)
    if not deleted:
        ret['result'] = False
        ret['comment'] = 'Certificate {0} failed to be deleted.'.format(name)
        return ret
    ret['comment'] = 'Certificate {0} was deleted.'.format(name)
    ret['changes'] = deleted
    return ret


def server_cert_present(name, public_key, private_key, cert_chain=None, path=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Crete server certificate.

    name (string)
        The name for the server certificate. Do not include the path in this value.

    public_key (string)
        The contents of the public key certificate in PEM-encoded format.

    private_key (string)
        The contents of the private key in PEM-encoded format.

    cert_chain (string)
        The contents of the certificate chain. This is typically a
        concatenation of the PEM-encoded public key certificates of the chain.

    path (string)
        The path for the server certificate.

    region (string)
        The name of the region to connect to.

    key (string)
        The key to be used in order to connect

    keyid (string)
        The keyid to be used in order to connect

    profile (string)
        The profile that contains a dict of region, key, keyid
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto_iam.get_server_certificate'](name, region, key, keyid, profile)
    log.debug('Variables are : {0}.'.format(locals()))
    if exists:
        ret['comment'] = 'Certificate {0} exists.'.format(name)
        return ret
    if 'salt://' in public_key:
        try:
            public_key = __salt__['cp.get_file_str'](public_key)
        except IOError as e:
            log.debug(e)
            ret['comment'] = 'File {0} not found.'.format(public_key)
            ret['result'] = False
            return ret
    if 'salt://' in private_key:
        try:
            private_key = __salt__['cp.get_file_str'](private_key)
        except IOError as e:
            log.debug(e)
            ret['comment'] = 'File {0} not found.'.format(private_key)
            ret['result'] = False
            return ret
    if cert_chain is not None and 'salt://' in cert_chain:
        try:
            cert_chain = __salt__['cp.get_file_str'](cert_chain)
        except IOError as e:
            log.debug(e)
            ret['comment'] = 'File {0} not found.'.format(cert_chain)
            ret['result'] = False
            return ret
    if __opts__['test']:
        ret['comment'] = 'Server certificate {0} is set to be created.'.format(name)
        ret['result'] = None
        return ret
    created = __salt__['boto_iam.upload_server_cert'](name, public_key, private_key, cert_chain,
                                                      path, region, key, keyid, profile)
    if created is not False:
        ret['comment'] = 'Certificate {0} was created.'.format(name)
        ret['changes'] = created
        return ret
    ret['result'] = False
    ret['comment'] = 'Certificate {0} failed to be created.'.format(name)
    return ret


def _get_error(error):
    # Converts boto exception to string that can be used to output error.
    error = '\n'.join(error.split('\n')[1:])
    error = ET.fromstring(error)
    code = error[0][1].text
    message = error[0][2].text
    return code, message
