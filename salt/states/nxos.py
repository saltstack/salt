# -*- coding: utf-8 -*-
'''
State module for Cisco NX OS Switches Proxy minions

.. versionadded: Carbon

For documentation on setting up the nxos proxy minion look in the documentation
for :doc:`salt.proxy.nxos</ref/proxy/all/salt.proxy.nxos>`.
'''
import re


def __virtual__():
    return 'nxos.cmd' in __salt__


def user_present(name, password=None, roles=None, encrypted=False, crypt_salt=None, algorithm='sha256'):
    '''
    Ensure a user is present with the specified groups

    name
        Name of user

    password
        Encrypted or Plain Text password for user

    roles
        List of roles the user should be assigned.  Any roles not in this list will be removed

    encrypted
        Whether the password is encrypted already or not.  Defaults to False

    crypt_salt
        Salt to use when encrypting the password.  Default is None (salt is
        randomly generated for unhashed passwords)

    algorithm
        Algorithm to use for hashing password.  Defaults to sha256.
        Accepts md5, blowfish, sha256, sha512

        .. note: sha512 may make the hash too long to save in NX OS which limits the has to 64 characters

    Examples:

    .. code-block:: yaml

        create:
          nxos.user_present:
            - name: daniel
            - roles:
              - vdc-admin

        set_password:
          nxos.user_present:
            - name: daniel
            - password: admin
            - roles:
              - network-admin

        update:
          nxos.user_present:
            - name: daniel
            - password: AiN9jaoP
            - roles:
              - network-admin
              - vdc-admin

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    change_password = False
    if password is not None:
        change_password = not __salt__['nxos.cmd']('check_password',
                                       username=name,
                                       password=password,
                                       encrypted=encrypted)

    change_roles = False
    if roles is not None:
        cur_roles = __salt__['nxos.cmd']('get_roles', username=name)
        change_roles = set(roles) != set(cur_roles)

    old_user = __salt__['nxos.cmd']('get_user', username=name)

    if not any([change_password, change_roles, not old_user]):
        ret['result'] = True
        ret['comment'] = 'User already exists'
        return ret

    if change_roles is True:
        remove_roles = set(cur_roles) - set(roles)
        add_roles = set(roles) - set(cur_roles)

    if __opts__['test'] is True:
        ret['result'] = None
        if not old_user:
            ret['comment'] = 'User will be created'
            if password is not None:
                ret['changes']['password'] = True
            if roles is not None:
                ret['changes']['role'] = {'add': roles,
                                          'remove': [], }
            return ret
        if change_password is True:
            ret['comment'] = 'User will be updated'
            ret['changes']['password'] = True
        if change_roles is True:
            ret['comment'] = 'User will be updated'
            ret['changes']['roles'] = {'add': list(add_roles),
                                      'remove': list(remove_roles)}
        return ret

    if change_password is True:
        new_user = __salt__['nxos.cmd']('set_password',
                                         username=name,
                                         password=password,
                                         encrypted=encrypted,
                                         role=roles[0] if roles else None,
                                         crypt_salt=crypt_salt,
                                         algorithm=algorithm)
        ret['changes']['password'] = {
            'new': new_user,
            'old': old_user,
        }
    if change_roles is True:
        for role in add_roles:
            __salt__['nxos.cmd']('set_role', username=name, role=role)
        for role in remove_roles:
            __salt__['nxos.cmd']('unset_role', username=name, role=role)
        ret['changes']['roles'] = {
            'new': __salt__['nxos.cmd']('get_roles', username=name),
            'old': cur_roles,
        }

    correct_password = True
    if password is not None:
        correct_password = __salt__['nxos.cmd']('check_password',
                                    username=name,
                                    password=password,
                                    encrypted=encrypted)

    correct_roles = True
    if roles is not None:
        cur_roles = __salt__['nxos.cmd']('get_roles', username=name)
        correct_roles = set(roles) != set(cur_roles)

    if not correct_roles:
        ret['comment'] = 'Failed to set correct roles'
    elif not correct_password:
        ret['comment'] = 'Failed to set correct password'
    else:
        ret['comment'] = 'User set correctly'
        ret['result'] = True

    return ret


def user_absent(name):
    '''
    Ensure a user is not present

    name
        username to remove if it exists

    Examples:

    .. code-block:: yaml

        delete:
          nxos.user_absent:
            - name: daniel
    '''

    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    old_user = __salt__['nxos.cmd']('get_user', username=name)

    if not old_user:
        ret['result'] = True
        ret['comment'] = 'User does not exist'
        return ret

    if __opts__['test'] is True and old_user:
        ret['result'] = None
        ret['comment'] = 'User will be removed'
        ret['changes']['old'] = old_user
        ret['changes']['new'] = ''
        return ret

    __salt__['nxos.cmd']('remove_user', username=name)

    if __salt__['nxos.cmd']('get_user', username=name):
        ret['comment'] = 'Failed to remove user'
    else:
        ret['result'] = True
        ret['comment'] = 'User removed'
        ret['changes']['old'] = old_user
        ret['changes']['new'] = ''
    return ret


def config_present(name):
    '''
    Ensure a specific configuration line exists in the running config

    name
        config line to set

    Examples:

    .. code-block:: yaml

        add snmp group:
          nxos.config_present:
            - names:
              - snmp-server community randoSNMPstringHERE group network-operator
              - snmp-server community AnotherRandomSNMPSTring group network-admin

        add snmp acl:
          nxos.config_present:
            - names:
              - snmp-server community randoSNMPstringHERE use-acl snmp-acl-ro
              - snmp-server community AnotherRandomSNMPSTring use-acl snmp-acl-rw
    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    matches = __salt__['nxos.cmd']('find', name)

    if matches:
        ret['result'] = True
        ret['comment'] = 'Config is already set'

    elif __opts__['test'] is True:
        ret['result'] = None
        ret['comment'] = 'Config will be added'
        ret['changes']['new'] = name

    else:
        __salt__['nxos.cmd']('add_config', name)
        matches = __salt__['nxos.cmd']('find', name)
        if matches:
            ret['result'] = True
            ret['comment'] = 'Successfully added config'
            ret['changes']['new'] = name
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to add config'

    return ret


def config_absent(name):
    '''
    Ensure a specific configuration line does not exist in the running config

    name
        config line to remove

    Examples:

    .. code-block:: yaml

        add snmp group:
          nxos.config_absent:
            - names:
              - snmp-server community randoSNMPstringHERE group network-operator
              - snmp-server community AnotherRandomSNMPSTring group network-admin

    .. note::
        For certain cases extra lines could be removed based on dependencies.
        In this example, included after the example for config_present, the
        ACLs would be removed because they depend on the existance of the
        group.

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    matches = __salt__['nxos.cmd']('find', name)

    if not matches:
        ret['result'] = True
        ret['comment'] = 'Config is already absent'

    elif __opts__['test'] is True:
        ret['result'] = None
        ret['comment'] = 'Config will be removed'
        ret['changes']['new'] = name

    else:
        __salt__['nxos.cmd']('delete_config', name)
        matches = __salt__['nxos.cmd']('find', name)
        if not matches:
            ret['result'] = True
            ret['comment'] = 'Successfully deleted config'
            ret['changes']['new'] = name
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete config'

    return ret


def replace(name, repl, full_match=False):
    '''
    Replace all instances of a string or full line in the running config

    name
        String to replace

    repl
        The replacement text

    full_match
        Whether `name` will match the full line or only a subset of the line.
        Defaults to False. When False, .* is added around `name` for matching
        in the `show run` config.

    Examples:

    .. code-block:: yaml

        replace snmp string:
          nxos.replace:
            - name: randoSNMPstringHERE
            - repl: NEWrandoSNMPstringHERE

        replace full snmp string:
          nxos.replace:
            - name: ^snmp-server community randoSNMPstringHERE group network-operator$
            - repl: snmp-server community NEWrandoSNMPstringHERE group network-operator
            - full_match: True

    .. note::
        The first example will replace the SNMP string on both the group and
        the ACL, so you will not lose the ACL setting.  Because the second is
        an exact match of the line, when the group is removed, the ACL is
        removed, but not readded, because it was not matched.

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    if full_match is False:
        search = '^.*{0}.*$'.format(name)
    else:
        search = name

    matches = __salt__['nxos.cmd']('find', search)

    if not matches:
        ret['result'] = True
        ret['comment'] = 'Nothing found to replace'
        return ret

    if __opts__['test'] is True:
        ret['result'] = None
        ret['comment'] = 'Configs will be changed'
        ret['changes']['old'] = matches
        ret['changes']['new'] = [re.sub(name, repl, match) for match in matches]
        return ret

    ret['changes'] = __salt__['nxos.cmd']('replace', name, repl, full_match=full_match)

    matches = __salt__['nxos.cmd']('find', search)

    if matches:
        ret['result'] = False
        ret['comment'] = 'Failed to replace all instances of "{0}"'.format(name)
    else:
        ret['result'] = True
        ret['comment'] = 'Successfully replaced all instances of "{0}" with "{1}"'.format(name, repl)

    return ret
