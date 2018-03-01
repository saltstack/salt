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

.. code-block:: yaml

    create policy:
      boto_iam.policy_present:
        - name: myname
        - policy_document: '{"MyPolicy": "Statement": [{"Action": ["sqs:*"], "Effect": "Allow", "Resource": ["arn:aws:sqs:*:*:*"], "Sid": "MyPolicySqs1"}]}'
        - region: eu-west-1
        - keyid: 'AKIAJHTMIQ2ASDFLASDF'
        - key: 'fdkjsafkljsASSADFalkfjasdf'

.. code-block:: yaml

    add-saml-provider:
      boto_iam.saml_provider_present:
        - name: my_saml_provider
        - saml_metadata_document: salt://base/files/provider.xml
        - keyid: 'AKIAJHTMIQ2ASDFLASDF'
        - key: 'safsdfsal;fdkjsafkljsASSADFalkfj'
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os

# Import Salt Libs
import salt.utils.data
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.odict as odict
import salt.utils.dictupdate as dictupdate
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import 3rd party libs
try:
    from salt._compat import ElementTree as ET
    HAS_ELEMENT_TREE = True
except ImportError:
    HAS_ELEMENT_TREE = False

log = logging.getLogger(__name__)

__virtualname__ = 'boto_iam'


if six.PY2:
    def _byteify(thing):
        # Note that we intentionally don't treat odicts here - they won't
        # compare equal in many circumstances where AWS treats them the same...
        if isinstance(thing, dict):
            return dict([(_byteify(k), _byteify(v)) for k, v in six.iteritems(thing)])
        elif isinstance(thing, list):
            return [_byteify(m) for m in thing]
        elif isinstance(thing, six.text_type):  # pylint: disable=W1699
            return thing.encode('utf-8')
        else:
            return thing

else:  # six.PY3
    def _byteify(text):
        return text


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


def user_absent(name, delete_keys=True, delete_mfa_devices=True, delete_profile=True, region=None, key=None, keyid=None, profile=None):
    '''

    .. versionadded:: 2015.8.0

    Ensure the IAM user is absent. User cannot be deleted if it has keys.

    name (string)
        The name of the new user.

    delete_keys (bool)
        Delete all keys from user.

    delete_mfa_devices (bool)
        Delete all mfa devices from user.

        .. versionadded:: 2016.3.0

    delete_profile (bool)
        Delete profile from user.

        .. versionadded:: 2016.3.0

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
    # delete the user's access keys
    if delete_keys:
        keys = __salt__['boto_iam.get_all_access_keys'](user_name=name, region=region, key=key,
                                                        keyid=keyid, profile=profile)
        log.debug('Keys for user %s are %s.', name, keys)
        if isinstance(keys, dict):
            keys = keys['list_access_keys_response']['list_access_keys_result']['access_key_metadata']
            for k in keys:
                if __opts__['test']:
                    ret['comment'] = ' '.join([ret['comment'], 'Key {0} is set to be deleted.'.format(k['access_key_id'])])
                    ret['result'] = None
                else:
                    if _delete_key(ret, k['access_key_id'], name, region, key, keyid, profile):
                        ret['comment'] = ' '.join([ret['comment'], 'Key {0} has been deleted.'.format(k['access_key_id'])])
                        ret['changes'][k['access_key_id']] = 'deleted'
    # delete the user's MFA tokens
    if delete_mfa_devices:
        devices = __salt__['boto_iam.get_all_mfa_devices'](user_name=name, region=region, key=key, keyid=keyid, profile=profile)
        if devices:
            for d in devices:
                serial = d['serial_number']
                if __opts__['test']:
                    ret['comment'] = ' '.join([ret['comment'], 'IAM user {0} MFA device {1} is set to be deactivated.'.format(name, serial)])
                    ret['result'] = None
                else:
                    mfa_deactivated = __salt__['boto_iam.deactivate_mfa_device'](user_name=name, serial=serial, region=region, key=key, keyid=keyid, profile=profile)
                    if mfa_deactivated:
                        ret['comment'] = ' '.join([ret['comment'], 'IAM user {0} MFA device {1} is deactivated.'.format(name, serial)])
                if __opts__['test']:
                    ret['comment'] = ' '.join([ret['comment'], 'Virtual MFA device {0} is set to be deleted.'.format(serial)])
                    ret['result'] = None
                else:
                    mfa_deleted = __salt__['boto_iam.delete_virtual_mfa_device'](serial=serial, region=region, key=key, keyid=keyid, profile=profile)
                    if mfa_deleted:
                        ret['comment'] = ' '.join([ret['comment'], 'Virtual MFA device {0} is deleted.'.format(serial)])
    # delete the user's login profile
    if delete_profile:
        if __opts__['test']:
            ret['comment'] = ' '.join([ret['comment'], 'IAM user {0} login profile is set to be deleted.'.format(name)])
            ret['result'] = None
        else:
            profile_deleted = __salt__['boto_iam.delete_login_profile'](name, region, key, keyid, profile)
            if profile_deleted:
                ret['comment'] = ' '.join([ret['comment'], 'IAM user {0} login profile is deleted.'.format(name)])
    if __opts__['test']:
        ret['comment'] = ' '.join([ret['comment'], 'IAM user {0} managed policies are set to be detached.'.format(name)])
        ret['result'] = None
    else:
        _ret = _user_policies_detached(name, region, key, keyid, profile)
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
    if __opts__['test']:
        ret['comment'] = ' '.join([ret['comment'], 'IAM user {0} inline policies are set to be deleted.'.format(name)])
        ret['result'] = None
    else:
        _ret = _user_policies_deleted(name, region, key, keyid, profile)
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
    # finally, actually delete the user
    if __opts__['test']:
        ret['comment'] = ' '.join([ret['comment'], 'IAM user {0} is set to be deleted.'.format(name)])
        ret['result'] = None
        return ret
    deleted = __salt__['boto_iam.delete_user'](name, region, key, keyid, profile)
    if deleted is True:
        ret['comment'] = ' '.join([ret['comment'], 'IAM user {0} is deleted.'.format(name)])
        ret['result'] = True
        ret['changes']['deleted'] = name
        return ret
    ret['comment'] = 'IAM user {0} could not be deleted.\n {1}'.format(name, deleted)
    ret['result'] = False
    return ret


def keys_present(name, number, save_dir, region=None, key=None, keyid=None, profile=None,
                 save_format="{2}\n{0}\n{3}\n{1}\n"):
    '''

    .. versionadded:: 2015.8.0

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

    save_format (dict)
        Save format is repeated for each key. Default format is "{2}\n{0}\n{3}\n{1}\n",
        where {0} and {1} are placeholders for new key_id and key respectively,
        whereas {2} and {3} are "key_id-{number}" and 'key-{number}' strings kept for compatibility.
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
    if isinstance(keys, six.string_types):
        log.debug('keys are : false %s', keys)
        error, message = _get_error(keys)
        ret['comment'] = 'Could not get keys.\n{0}\n{1}'.format(error, message)
        ret['result'] = False
        return ret
    keys = keys['list_access_keys_response']['list_access_keys_result']['access_key_metadata']
    log.debug('Keys are : %s.', keys)
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
        if isinstance(created, six.string_types):
            error, message = _get_error(created)
            ret['comment'] = 'Could not create keys.\n{0}\n{1}'.format(error, message)
            ret['result'] = False
            return ret
        log.debug('Created is : %s', created)
        response = 'create_access_key_response'
        result = 'create_access_key_result'
        new_keys[six.text_type(i)] = {}
        new_keys[six.text_type(i)]['key_id'] = created[response][result]['access_key']['access_key_id']
        new_keys[six.text_type(i)]['secret_key'] = created[response][result]['access_key']['secret_access_key']
    try:
        with salt.utils.files.fopen('{0}/{1}'.format(save_dir, name), 'a') as _wrf:
            for key_num, key in new_keys.items():
                key_id = key['key_id']
                secret_key = key['secret_key']
                _wrf.write(salt.utils.stringutils.to_str(
                    save_format.format(
                        key_id,
                        secret_key,
                        'key_id-{0}'.format(key_num),
                        'key-{0}'.format(key_num)
                    )
                ))
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

    .. versionadded:: 2015.8.0

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
    log.debug('Keys for user %s are : %s.', keys, user_name)
    if isinstance(keys, six.string_types):
        log.debug('Keys %s are a string. Something went wrong.', keys)
        ret['comment'] = ' '.join([ret['comment'], 'Key {0} could not be deleted.'.format(access_key_id)])
        return ret
    keys = keys['list_access_keys_response']['list_access_keys_result']['access_key_metadata']
    for k in keys:
        log.debug('Key is: %s and is compared with: %s', k['access_key_id'], access_key_id)
        if six.text_type(k['access_key_id']) == six.text_type(access_key_id):
            if __opts__['test']:
                ret['comment'] = 'Access key {0} is set to be deleted.'.format(access_key_id)
                ret['result'] = None
                return ret
            deleted = __salt__['boto_iam.delete_access_key'](access_key_id, user_name, region, key,
                                                             keyid, profile)
            if deleted:
                ret['comment'] = ' '.join([ret['comment'], 'Key {0} has been deleted.'.format(access_key_id)])
                ret['changes'][access_key_id] = 'deleted'
                return ret
            ret['comment'] = ' '.join([ret['comment'], 'Key {0} could not be deleted.'.format(access_key_id)])
            return ret
        ret['comment'] = ' '.join([ret['comment'], 'Key {0} does not exist.'.format(k)])
        return ret


def user_present(name, policies=None, policies_from_pillars=None, managed_policies=None, password=None, path=None,
                 region=None, key=None, keyid=None, profile=None):
    '''

    .. versionadded:: 2015.8.0

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

    managed_policies (list)
        A list of managed policy names or ARNs that should be attached to this
        user.

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
    if not managed_policies:
        managed_policies = []
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
            ret['comment'] = ' '.join([ret['comment'], 'User {0} has been created.'.format(name)])
            if password:
                ret = _case_password(ret, name, password, region, key, keyid, profile)
            _ret = _user_policies_present(name, _policies, region, key, keyid, profile)
            ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
            ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    else:
        ret['comment'] = ' '.join([ret['comment'], 'User {0} is present.'.format(name)])
        if password:
            ret = _case_password(ret, name, password, region, key, keyid, profile)
        _ret = _user_policies_present(name, _policies, region, key, keyid, profile)
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    _ret = _user_policies_attached(name, managed_policies, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        return ret
    return ret


def _user_policies_present(name, policies=None, region=None, key=None, keyid=None, profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    policies_to_create = {}
    policies_to_delete = []
    for policy_name, policy in six.iteritems(policies):
        if isinstance(policy, six.string_types):
            dict_policy = _byteify(salt.utils.json.loads(policy, object_pairs_hook=odict.OrderedDict))
        else:
            dict_policy = _byteify(policy)
        _policy = _byteify(__salt__['boto_iam.get_user_policy'](name, policy_name, region, key, keyid, profile))
        if _policy != dict_policy:
            log.debug("Policy mismatch:\n%s\n%s", _policy, dict_policy)
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
            ret['comment'] = '{0} policies to be modified on user {1}.'.format(', '.join(_to_modify), name)
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
                ret['comment'] = 'Failed to add policy {0} for user {1}'.format(policy_name, name)
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
                ret['comment'] = 'Failed to add policy {0} to user {1}'.format(policy_name, name)
                return ret
        _list = __salt__['boto_iam.get_all_user_policies'](
            user_name=name, region=region, key=key, keyid=keyid, profile=profile
        )
        ret['changes']['new'] = {'policies': _list}
        ret['comment'] = '{0} policies modified on user {1}.'.format(', '.join(_list), name)
    return ret


def _user_policies_attached(
        name,
        managed_policies=None,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    policies_to_attach = []
    policies_to_detach = []
    for policy in managed_policies or []:
        entities = __salt__['boto_iam.list_entities_for_policy'](policy,
                                       entity_filter='User',
                                       region=region, key=key, keyid=keyid,
                                       profile=profile)
        found = False
        for userdict in entities.get('policy_users', []):
            if name == userdict.get('user_name'):
                found = True
                break
        if not found:
            policies_to_attach.append(policy)
    _list = __salt__['boto_iam.list_attached_user_policies'](name, region=region, key=key, keyid=keyid,
                                                    profile=profile)
    oldpolicies = [x.get('policy_arn') for x in _list]
    for policy_data in _list:
        if policy_data.get('policy_name') not in managed_policies \
                  and policy_data.get('policy_arn') not in managed_policies:
            policies_to_detach.append(policy_data.get('policy_arn'))
    if policies_to_attach or policies_to_detach:
        _to_modify = list(policies_to_detach)
        _to_modify.extend(policies_to_attach)
        if __opts__['test']:
            ret['comment'] = '{0} policies to be modified on user {1}.'.format(', '.join(_to_modify), name)
            ret['result'] = None
            return ret
        ret['changes']['old'] = {'managed_policies': oldpolicies}
        for policy_name in policies_to_attach:
            policy_set = __salt__['boto_iam.attach_user_policy'](policy_name,
                                                                 name,
                                                                 region=region, key=key,
                                                                 keyid=keyid,
                                                                 profile=profile)
            if not policy_set:
                _list = __salt__['boto_iam.list_attached_user_policies'](name, region=region,
                                                                key=key,
                                                                keyid=keyid,
                                                                profile=profile)
                newpolicies = [x.get('policy_arn') for x in _list]
                ret['changes']['new'] = {'managed_policies': newpolicies}
                ret['result'] = False
                ret['comment'] = 'Failed to add policy {0} to user {1}'.format(policy_name, name)
                return ret
        for policy_name in policies_to_detach:
            policy_unset = __salt__['boto_iam.detach_user_policy'](policy_name,
                                                                   name,
                                                                   region=region, key=key,
                                                                   keyid=keyid,
                                                                   profile=profile)
            if not policy_unset:
                _list = __salt__['boto_iam.list_attached_user_policies'](name, region=region,
                                                                key=key,
                                                                keyid=keyid,
                                                                profile=profile)
                newpolicies = [x.get('policy_arn') for x in _list]
                ret['changes']['new'] = {'managed_policies': newpolicies}
                ret['result'] = False
                ret['comment'] = 'Failed to remove policy {0} from user {1}'.format(policy_name, name)
                return ret
        _list = __salt__['boto_iam.list_attached_user_policies'](name, region=region, key=key,
                                                        keyid=keyid,
                                                        profile=profile)
        newpolicies = [x.get('policy_arn') for x in _list]
        log.debug(newpolicies)
        ret['changes']['new'] = {'managed_policies': newpolicies}
        ret['comment'] = '{0} policies modified on user {1}.'.format(', '.join(newpolicies), name)
    return ret


def _user_policies_detached(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    _list = __salt__['boto_iam.list_attached_user_policies'](user_name=name,
                        region=region, key=key, keyid=keyid, profile=profile)
    oldpolicies = [x.get('policy_arn') for x in _list]
    if not _list:
        ret['comment'] = 'No attached policies in user {0}.'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = '{0} policies to be detached from user {1}.'.format(', '.join(oldpolicies), name)
        ret['result'] = None
        return ret
    ret['changes']['old'] = {'managed_policies': oldpolicies}
    for policy_arn in oldpolicies:
        policy_unset = __salt__['boto_iam.detach_user_policy'](policy_arn,
                                                               name,
                                                               region=region, key=key,
                                                               keyid=keyid,
                                                               profile=profile)
        if not policy_unset:
            _list = __salt__['boto_iam.list_attached_user_policies'](name, region=region,
                                                            key=key, keyid=keyid,
                                                            profile=profile)
            newpolicies = [x.get('policy_arn') for x in _list]
            ret['changes']['new'] = {'managed_policies': newpolicies}
            ret['result'] = False
            ret['comment'] = 'Failed to detach {0} from user {1}'.format(policy_arn, name)
            return ret
    _list = __salt__['boto_iam.list_attached_user_policies'](name, region=region, key=key,
                                                    keyid=keyid, profile=profile)
    newpolicies = [x.get('policy_arn') for x in _list]
    ret['changes']['new'] = {'managed_policies': newpolicies}
    ret['comment'] = '{0} policies detached from user {1}.'.format(', '.join(oldpolicies), name)
    return ret


def _user_policies_deleted(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    oldpolicies = __salt__['boto_iam.get_all_user_policies'](user_name=name,
                        region=region, key=key, keyid=keyid, profile=profile)
    if not oldpolicies:
        ret['comment'] = 'No inline policies in user {0}.'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = '{0} policies to be deleted from user {1}.'.format(', '.join(oldpolicies), name)
        ret['result'] = None
        return ret
    ret['changes']['old'] = {'inline_policies': oldpolicies}
    for policy_name in oldpolicies:
        policy_deleted = __salt__['boto_iam.delete_user_policy'](name,
                                                                 policy_name,
                                                                 region=region, key=key,
                                                                 keyid=keyid,
                                                                 profile=profile)
        if not policy_deleted:
            newpolicies = __salt__['boto_iam.get_all_user_policies'](name, region=region,
                                                                     key=key, keyid=keyid,
                                                                     profile=profile)
            ret['changes']['new'] = {'inline_policies': newpolicies}
            ret['result'] = False
            ret['comment'] = 'Failed to detach {0} from user {1}'.format(policy_name, name)
            return ret
    newpolicies = __salt__['boto_iam.get_all_user_policies'](name, region=region, key=key,
                                                             keyid=keyid, profile=profile)
    ret['changes']['new'] = {'inline_policies': newpolicies}
    ret['comment'] = '{0} policies deleted from user {1}.'.format(', '.join(oldpolicies), name)
    return ret


def _case_password(ret, name, password, region=None, key=None, keyid=None, profile=None):
    if __opts__['test']:
        ret['comment'] = 'Login policy for {0} is set to be changed.'.format(name)
        ret['result'] = None
        return ret
    login = __salt__['boto_iam.create_login_profile'](name, password, region, key, keyid, profile)
    log.debug('Login is : %s.', login)
    if login:
        if 'Conflict' in login:
            ret['comment'] = ' '.join([ret['comment'], 'Login profile for user {0} exists.'.format(name)])
        else:
            ret['comment'] = ' '.join([ret['comment'], 'Password has been added to User {0}.'.format(name)])
            ret['changes']['password'] = 'REDACTED'
    else:
        ret['result'] = False
        ret['comment'] = ' '.join([ret['comment'], 'Password for user {0} could not be set.\nPlease check your password policy.'.format(name)])
    return ret


def group_absent(name, region=None, key=None, keyid=None, profile=None):
    '''

    .. versionadded:: 2015.8.0

    Ensure the IAM group is absent.

    name (string)
        The name of the group.

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
    if not __salt__['boto_iam.get_group'](name, region, key, keyid, profile):
        ret['result'] = True
        ret['comment'] = 'IAM Group {0} does not exist.'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = ' '.join([ret['comment'], 'IAM group {0} managed policies are set to be detached.'.format(name)])
        ret['result'] = None
    else:
        _ret = _group_policies_detached(name, region, key, keyid, profile)
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
    if __opts__['test']:
        ret['comment'] = ' '.join([ret['comment'], 'IAM group {0} inline policies are set to be deleted.'.format(name)])
        ret['result'] = None
    else:
        _ret = _group_policies_deleted(name, region, key, keyid, profile)
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
    ret['comment'] = ' '.join([ret['comment'], 'IAM group {0} users are set to be removed.'.format(name)])
    existing_users = __salt__['boto_iam.get_group_members'](group_name=name, region=region, key=key, keyid=keyid, profile=profile)
    _ret = _case_group(ret, [], name, existing_users, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        return ret
    # finally, actually delete the group
    if __opts__['test']:
        ret['comment'] = ' '.join([ret['comment'], 'IAM group {0} is set to be deleted.'.format(name)])
        ret['result'] = None
        return ret
    deleted = __salt__['boto_iam.delete_group'](name, region, key, keyid, profile)
    if deleted is True:
        ret['comment'] = ' '.join([ret['comment'], 'IAM group {0} is deleted.'.format(name)])
        ret['result'] = True
        ret['changes']['deleted'] = name
        return ret
    ret['comment'] = 'IAM group {0} could not be deleted.\n {1}'.format(name, deleted)
    ret['result'] = False
    return ret


def group_present(name, policies=None, policies_from_pillars=None, managed_policies=None, users=None, path='/', region=None, key=None, keyid=None, profile=None, delete_policies=True):
    '''

    .. versionadded:: 2015.8.0

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

    managed_policies (list)
        A list of policy names or ARNs that should be attached to this group.

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

    delete_policies (boolean)
        Delete or detach existing policies that are not in the given list of policies.
        Default value is ``True``. If ``False`` is specified, existing policies
        will not be deleted or detached allowing manual modifications on the IAM group
        to be persistent.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if not policies:
        policies = {}
    if not policies_from_pillars:
        policies_from_pillars = []
    if not managed_policies:
        managed_policies = []
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
        ret['comment'] = ' '.join([ret['comment'], 'Group {0} has been created.'.format(name)])
    else:
        ret['comment'] = ' '.join([ret['comment'], 'Group {0} is present.'.format(name)])
    # Group exists, ensure group policies and users are set.
    _ret = _group_policies_present(
        name, _policies, region, key, keyid, profile, delete_policies
    )
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        return ret
    _ret = _group_policies_attached(name, managed_policies, region, key, keyid, profile, delete_policies)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        return ret
    if users is not None:
        log.debug('Users are : %s.', users)
        existing_users = __salt__['boto_iam.get_group_members'](group_name=name, region=region, key=key, keyid=keyid, profile=profile)
        ret = _case_group(ret, users, name, existing_users, region, key, keyid, profile)
    return ret


def _case_group(ret, users, group_name, existing_users, region, key, keyid, profile):
    _users = []
    for user in existing_users:
        _users.append(user['user_name'])
    log.debug('upstream users are %s', _users)
    for user in users:
        log.debug('users are %s', user)
        if user in _users:
            log.debug('user exists')
            ret['comment'] = ' '.join([ret['comment'], 'User {0} is already a member of group {1}.'.format(user, group_name)])
            continue
        else:
            log.debug('user is set to be added %s', user)
            if __opts__['test']:
                ret['comment'] = 'User {0} is set to be added to group {1}.'.format(user, group_name)
                ret['result'] = None
            else:
                __salt__['boto_iam.add_user_to_group'](user, group_name, region, key, keyid, profile)
                ret['comment'] = ' '.join([ret['comment'], 'User {0} has been added to group {1}.'.format(user, group_name)])
                ret['changes'][user] = group_name
    for user in _users:
        if user not in users:
            if __opts__['test']:
                ret['comment'] = ' '.join([ret['comment'], 'User {0} is set to be removed from group {1}.'.format(user, group_name)])
                ret['result'] = None
            else:
                __salt__['boto_iam.remove_user_from_group'](group_name=group_name, user_name=user, region=region,
                                                            key=key, keyid=keyid, profile=profile)
                ret['comment'] = ' '.join([ret['comment'], 'User {0} has been removed from group {1}.'.format(user, group_name)])
                ret['changes'][user] = 'Removed from group {0}.'.format(group_name)
    return ret


def _group_policies_present(
        name,
        policies=None,
        region=None,
        key=None,
        keyid=None,
        profile=None,
        delete_policies=True):
    ret = {'result': True, 'comment': '', 'changes': {}}
    policies_to_create = {}
    policies_to_delete = []
    for policy_name, policy in six.iteritems(policies):
        if isinstance(policy, six.string_types):
            dict_policy = _byteify(salt.utils.json.loads(policy, object_pairs_hook=odict.OrderedDict))
        else:
            dict_policy = _byteify(policy)
        _policy = _byteify(__salt__['boto_iam.get_group_policy'](name, policy_name, region, key, keyid, profile))
        if _policy != dict_policy:
            log.debug("Policy mismatch:\n%s\n%s", _policy, dict_policy)
            policies_to_create[policy_name] = policy
    _list = __salt__['boto_iam.get_all_group_policies'](
        name, region, key, keyid, profile
    )
    for policy_name in _list:
        if delete_policies and policy_name not in policies:
            policies_to_delete.append(policy_name)
    if policies_to_create or policies_to_delete:
        _to_modify = list(policies_to_delete)
        _to_modify.extend(policies_to_create)
        if __opts__['test']:
            ret['comment'] = '{0} policies to be modified on group {1}.'.format(', '.join(_to_modify), name)
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
                ret['comment'] = 'Failed to add policy {0} to group {1}'.format(policy_name, name)
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
                ret['comment'] = 'Failed to add policy {0} to group {1}'.format(policy_name, name)
                return ret
        _list = __salt__['boto_iam.get_all_group_policies'](
            name, region, key, keyid, profile
        )
        ret['changes']['new'] = {'policies': _list}
        ret['comment'] = '{0} policies modified on group {1}.'.format(', '.join(_list), name)
    return ret


def _group_policies_attached(
        name,
        managed_policies=None,
        region=None,
        key=None,
        keyid=None,
        profile=None,
        detach_policies=True):
    ret = {'result': True, 'comment': '', 'changes': {}}
    policies_to_attach = []
    policies_to_detach = []
    for policy in managed_policies or []:
        entities = __salt__['boto_iam.list_entities_for_policy'](policy,
                                       entity_filter='Group',
                                       region=region, key=key, keyid=keyid,
                                       profile=profile)
        found = False
        for groupdict in entities.get('policy_groups', []):
            if name == groupdict.get('group_name'):
                found = True
                break
        if not found:
            policies_to_attach.append(policy)
    _list = __salt__['boto_iam.list_attached_group_policies'](name, region=region, key=key, keyid=keyid,
                                                    profile=profile)
    oldpolicies = [x.get('policy_arn') for x in _list]
    for policy_data in _list:
        if detach_policies \
                  and policy_data.get('policy_name') not in managed_policies \
                  and policy_data.get('policy_arn') not in managed_policies:
            policies_to_detach.append(policy_data.get('policy_arn'))
    if policies_to_attach or policies_to_detach:
        _to_modify = list(policies_to_detach)
        _to_modify.extend(policies_to_attach)
        if __opts__['test']:
            ret['comment'] = '{0} policies to be modified on group {1}.'.format(', '.join(_to_modify), name)
            ret['result'] = None
            return ret
        ret['changes']['old'] = {'managed_policies': oldpolicies}
        for policy_name in policies_to_attach:
            policy_set = __salt__['boto_iam.attach_group_policy'](policy_name,
                                                                 name,
                                                                 region=region, key=key,
                                                                 keyid=keyid,
                                                                 profile=profile)
            if not policy_set:
                _list = __salt__['boto_iam.list_attached_group_policies'](name, region=region,
                                                                key=key, keyid=keyid,
                                                                profile=profile)
                newpolicies = [x.get('policy_arn') for x in _list]
                ret['changes']['new'] = {'managed_policies': newpolicies}
                ret['result'] = False
                ret['comment'] = 'Failed to add policy {0} to group {1}'.format(policy_name, name)
                return ret
        for policy_name in policies_to_detach:
            policy_unset = __salt__['boto_iam.detach_group_policy'](policy_name,
                                                                   name,
                                                                   region=region, key=key,
                                                                   keyid=keyid,
                                                                   profile=profile)
            if not policy_unset:
                _list = __salt__['boto_iam.list_attached_group_policies'](name, region=region,
                                                                key=key, keyid=keyid,
                                                                profile=profile)
                newpolicies = [x.get('policy_arn') for x in _list]
                ret['changes']['new'] = {'managed_policies': newpolicies}
                ret['result'] = False
                ret['comment'] = 'Failed to remove policy {0} from group {1}'.format(policy_name, name)
                return ret
        _list = __salt__['boto_iam.list_attached_group_policies'](name, region=region, key=key,
                                                        keyid=keyid, profile=profile)
        newpolicies = [x.get('policy_arn') for x in _list]
        log.debug(newpolicies)
        ret['changes']['new'] = {'managed_policies': newpolicies}
        ret['comment'] = '{0} policies modified on group {1}.'.format(', '.join(newpolicies), name)
    return ret


def _group_policies_detached(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    _list = __salt__['boto_iam.list_attached_group_policies'](group_name=name,
                        region=region, key=key, keyid=keyid, profile=profile)
    oldpolicies = [x.get('policy_arn') for x in _list]
    if not _list:
        ret['comment'] = 'No attached policies in group {0}.'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = '{0} policies to be detached from group {1}.'.format(', '.join(oldpolicies), name)
        ret['result'] = None
        return ret
    ret['changes']['old'] = {'managed_policies': oldpolicies}
    for policy_arn in oldpolicies:
        policy_unset = __salt__['boto_iam.detach_group_policy'](policy_arn,
                                                               name,
                                                               region=region, key=key,
                                                               keyid=keyid,
                                                               profile=profile)
        if not policy_unset:
            _list = __salt__['boto_iam.list_attached_group_policies'](name, region=region,
                                                            key=key, keyid=keyid,
                                                            profile=profile)
            newpolicies = [x.get('policy_arn') for x in _list]
            ret['changes']['new'] = {'managed_policies': newpolicies}
            ret['result'] = False
            ret['comment'] = 'Failed to detach {0} from group {1}'.format(policy_arn, name)
            return ret
    _list = __salt__['boto_iam.list_attached_group_policies'](name, region=region, key=key,
                                                    keyid=keyid, profile=profile)
    newpolicies = [x.get('policy_arn') for x in _list]
    ret['changes']['new'] = {'managed_policies': newpolicies}
    ret['comment'] = '{0} policies detached from group {1}.'.format(', '.join(newpolicies), name)
    return ret


def _group_policies_deleted(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    oldpolicies = __salt__['boto_iam.get_all_group_policies'](group_name=name,
                        region=region, key=key, keyid=keyid, profile=profile)
    if not oldpolicies:
        ret['comment'] = 'No inline policies in group {0}.'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = '{0} policies to be deleted from group {1}.'.format(', '.join(oldpolicies), name)
        ret['result'] = None
        return ret
    ret['changes']['old'] = {'inline_policies': oldpolicies}
    for policy_name in oldpolicies:
        policy_deleted = __salt__['boto_iam.delete_group_policy'](name,
                                                                 policy_name,
                                                                 region=region, key=key,
                                                                 keyid=keyid,
                                                                 profile=profile)
        if not policy_deleted:
            newpolicies = __salt__['boto_iam.get_all_group_policies'](name, region=region,
                                                                     key=key, keyid=keyid,
                                                                     profile=profile)
            ret['changes']['new'] = {'inline_policies': newpolicies}
            ret['result'] = False
            ret['comment'] = 'Failed to detach {0} from group {1}'.format(policy_name, name)
            return ret
    newpolicies = __salt__['boto_iam.get_all_group_policies'](name, region=region, key=key,
                                                             keyid=keyid, profile=profile)
    ret['changes']['new'] = {'inline_policies': newpolicies}
    ret['comment'] = '{0} policies deleted from group {1}.'.format(', '.join(oldpolicies), name)
    return ret


def account_policy(name=None, allow_users_to_change_password=None,
                   hard_expiry=None, max_password_age=None,
                   minimum_password_length=None, password_reuse_prevention=None,
                   require_lowercase_characters=None, require_numbers=None,
                   require_symbols=None, require_uppercase_characters=None,
                   region=None, key=None, keyid=None, profile=None):
    '''
    Change account policy.

    .. versionadded:: 2015.8.0

    name (string)
        The name of the account policy

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
        if key in ('region', 'key', 'keyid', 'profile', 'name'):
            continue
        if value is not None and six.text_type(info[key]) != six.text_type(value).lower():
            ret['comment'] = ' '.join([ret['comment'], 'Policy value {0} has been set to {1}.'.format(value, info[key])])
            ret['changes'][key] = six.text_type(value).lower()
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

    .. versionadded:: 2015.8.0

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

    .. versionadded:: 2015.8.0

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
    log.debug('Variables are : %s.', locals())
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


def policy_present(name, policy_document, path=None, description=None,
                 region=None, key=None, keyid=None, profile=None):
    '''

    .. versionadded:: 2015.8.0

    Ensure the IAM managed policy is present

    name (string)
        The name of the new policy.

    policy_document (dict)
        The document of the new policy

    path (string)
        The path in which the policy will be created. Default is '/'.

    description (string)
        Description

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
    policy = __salt__['boto_iam.get_policy'](name, region, key, keyid, profile)
    if not policy:
        if __opts__['test']:
            ret['comment'] = 'IAM policy {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_iam.create_policy'](name, policy_document, path, description, region, key, keyid, profile)
        if created:
            ret['changes']['policy'] = created
            ret['comment'] = ' '.join([ret['comment'], 'Policy {0} has been created.'.format(name)])
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to update policy.'
            ret['changes'] = {}
            return ret
    else:
        policy = policy.get('policy', {})
        ret['comment'] = ' '.join([ret['comment'], 'Policy {0} is present.'.format(name)])
        _describe = __salt__['boto_iam.get_policy_version'](name, policy.get('default_version_id'),
                                                       region, key, keyid, profile).get('policy_version', {})
        if isinstance(_describe['document'], six.string_types):
            describeDict = salt.utils.json.loads(_describe['document'])
        else:
            describeDict = _describe['document']

        if isinstance(policy_document, six.string_types):
            policy_document = salt.utils.json.loads(policy_document)

        r = salt.utils.data.compare_dicts(describeDict, policy_document)

        if bool(r):
            if __opts__['test']:
                ret['comment'] = 'Policy {0} set to be modified.'.format(name)
                ret['result'] = None
                return ret

            ret['comment'] = ' '.join([ret['comment'], 'Policy to be modified'])
            policy_document = salt.utils.json.dumps(policy_document)

            r = __salt__['boto_iam.create_policy_version'](policy_name=name,
                                               policy_document=policy_document,
                                               set_as_default=True,
                                               region=region, key=key,
                                               keyid=keyid, profile=profile)
            if not r.get('created'):
                ret['result'] = False
                ret['comment'] = 'Failed to update policy: {0}.'.format(r['error']['message'])
                ret['changes'] = {}
                return ret

            __salt__['boto_iam.delete_policy_version'](policy_name=name,
                                               version_id=policy['default_version_id'],
                                               region=region, key=key,
                                               keyid=keyid, profile=profile)

            ret['changes'].setdefault('new', {})['document'] = policy_document
            ret['changes'].setdefault('old', {})['document'] = _describe['document']
    return ret


def policy_absent(name,
                 region=None, key=None, keyid=None, profile=None):
    '''

    .. versionadded:: 2015.8.0

    Ensure the IAM managed policy with the specified name is absent

    name (string)
        The name of the new policy.

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

    r = __salt__['boto_iam.policy_exists'](name,
                       region=region, key=key, keyid=keyid, profile=profile)
    if not r:
        ret['comment'] = 'Policy {0} does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Policy {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    # delete non-default versions
    versions = __salt__['boto_iam.list_policy_versions'](name,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if versions:
        for version in versions:
            if version.get('is_default_version', False) in ('true', True):
                continue
            r = __salt__['boto_iam.delete_policy_version'](name,
                                    version_id=version.get('version_id'),
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
            if not r:
                ret['result'] = False
                ret['comment'] = 'Failed to delete policy {0}.'.format(name)
                return ret
    r = __salt__['boto_iam.delete_policy'](name,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete policy {0}.'.format(name)
        return ret
    ret['changes']['old'] = {'policy': name}
    ret['changes']['new'] = {'policy': None}
    ret['comment'] = 'Policy {0} deleted.'.format(name)
    return ret


def saml_provider_present(name, saml_metadata_document, region=None, key=None, keyid=None, profile=None):
    '''

    .. versionadded:: 2016.11.0

    Ensure the SAML provider with the specified name is present.

    name (string)
        The name of the SAML provider.

    saml_metadata_document (string)
        The xml document of the SAML provider.

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
    if 'salt://' in saml_metadata_document:
        try:
            saml_metadata_document = __salt__['cp.get_file_str'](saml_metadata_document)
            ET.fromstring(saml_metadata_document)
        except IOError as e:
            log.debug(e)
            ret['comment'] = 'SAML document file {0} not found or could not be loaded'.format(name)
            ret['result'] = False
            return ret
    for provider in __salt__['boto_iam.list_saml_providers'](region=region,
                                                             key=key, keyid=keyid,
                                                             profile=profile):
        if provider == name:
            ret['comment'] = 'SAML provider {0} is present.'.format(name)
            return ret
    if __opts__['test']:
        ret['comment'] = 'SAML provider {0} is set to be create.'.format(name)
        ret['result'] = None
        return ret
    created = __salt__['boto_iam.create_saml_provider'](name, saml_metadata_document,
                                                        region=region, key=key, keyid=keyid,
                                                        profile=profile)
    if created:
        ret['comment'] = 'SAML provider {0} was created.'.format(name)
        ret['changes']['new'] = name
        return ret
    ret['result'] = False
    ret['comment'] = 'SAML provider {0} failed to be created.'.format(name)
    return ret


def saml_provider_absent(name, region=None, key=None, keyid=None, profile=None):
    '''

    .. versionadded:: 2016.11.0

    Ensure the SAML provider with the specified name is absent.

    name (string)
        The name of the SAML provider.

    saml_metadata_document (string)
        The xml document of the SAML provider.

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
    provider = __salt__['boto_iam.list_saml_providers'](region=region,
                                                        key=key, keyid=keyid,
                                                        profile=profile)
    if len(provider) == 0:
        ret['comment'] = 'SAML provider {0} is absent.'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'SAML provider {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_iam.delete_saml_provider'](name, region=region,
                                                        key=key, keyid=keyid,
                                                        profile=profile)
    if deleted is not False:
        ret['comment'] = 'SAML provider {0} was deleted.'.format(name)
        ret['changes']['old'] = name
        return ret
    ret['result'] = False
    ret['comment'] = 'SAML provider {0} failed to be deleted.'.format(name)
    return ret


def _get_error(error):
    # Converts boto exception to string that can be used to output error.
    error = '\n'.join(error.split('\n')[1:])
    error = ET.fromstring(error)
    code = error[0][1].text
    message = error[0][2].text
    return code, message
