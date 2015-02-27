# -*- coding: utf-8 -*-
'''
Windows Object Access Control Lists

Ensure an ACL is present
    parameters:
        name - the path of the object
        objectType - Registry/File/Directory
        user - user account for the ace
        permission - permission for the ace (see module win_acl for available permissions for each objectType)
        acetype -  Allow/Deny
        propagation - how the ACL should apply to child objects (see module win_acl for available propagation types)

    .. code-block:: yaml

        addAcl:
          acl.present:
            - name: HKEY_LOCAL_MACHINE\\SOFTWARE\\mykey
            - objectType: Registry
            - user: FakeUser
            - permission: FulLControl
            - acetype: ALLOW
            - propagation: KEY&SUBKEYS

Ensure an ACL does not exist
    parameters:
        name - the path of the object
        objectType - Registry/File/Directory
        user - user account for the ace
        permission - permission for the ace (see module win_acl for available permissions for each objectType)
        acetype -  Allow/Deny
        propagation - how the ACL should apply to child objects (see module win_acl for available propagation types)

    .. code-block:: yaml

    removeAcl:
          acl.absent:
            - name: HKEY_LOCAL_MACHINE\\SOFTWARE\\mykey
            - objectType: Registry
            - user: FakeUser
            - permission: FulLControl
            - acetype: ALLOW
            - propagation: KEY&SUBKEYS

Ensure an object is inheriting permissions
    parameters:
        name - the path of the object
        objectType - Registry/File/Directory
        clear_existing_acl - True/False - when inheritance is enabled, should the existing ACL be kept or cleared out

    .. code-block:: yaml

    eInherit:
      acl.enableinheritance:
        - name: HKEY_LOCAL_MACHINE\\SOFTWARE\\mykey
        - objectType: Registry
        - clear_existing_acl: True

Ensure an object is not inheriting permissions
    parameters:
        name - the path of the object
        objectType - Registry/File/Directory
        copy_inherited_acl - True/False - if inheritance is enabled, should the inherited permissions be copied to the ACL when inheritance is disabled

        .. code-block:: yaml

    dInherit:
      acl.disableinheritance:
        - name: HKEY_LOCAL_MACHINE\\SOFTWARE\\mykey
        - objectType: Registry
        - copy_inherited_acl: False
'''

# Import salt libs
import salt.utils

__virtualname__ = 'win_dacl'


def __virtual__():
    '''
    Load this state if the win_acl module exists
    '''
    return 'win_dacl' if 'win_dacl.add_ace' in __salt__ else False


def present(name, objectType, user, permission, acetype, propagation):
    '''
    Ensure an ACE is present
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}
    tRet = __salt__['win_dacl.check_ace'](name, objectType, user, permission, acetype, propagation, True)
    if tRet['result']:
        if not tRet['Exists']:
            addRet = __salt__['win_dacl.add_ace'](name, objectType, user, permission, acetype, propagation)
            if addRet['result']:
                ret['result'] = True
                ret['changes'] = dict(ret['changes'], **addRet['changes'])
            else:
                ret['result'] = False
                ret['comment'] = ret['comment'] + addRet['comment']
    else:
        ret['result'] = False
        ret['comment'] = tRet['comment']
        return ret
    return ret


def absent(name, objectType, user, permission, acetype, propagation):
    '''
    Ensure a Linux ACL does not exist
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}
    tRet = __salt__['win_dacl.check_ace'](name, objectType, user, permission, acetype, propagation, True)
    if tRet['result']:
        if tRet['Exists']:
            addRet = __salt__['win_dacl.rm_ace'](name, objectType, user, permission, acetype, propagation)
            if addRet['result']:
                ret['result'] = True
                ret['changes'] = dict(ret['changes'], **addRet['changes'])
            else:
                ret['result'] = False
                ret['comment'] = ret['comment'] + addRet['comment']
    else:
        ret['result'] = False
        ret['comment'] = tRet['comment']
        return ret
    return ret


def enableinheritance(name, objectType, clear_existing_acl=False):
    '''
    Ensure an object in inheriting ACLs from its parent
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}
    tRet = __salt__['win_dacl.check_inheritance'](name, objectType)
    if tRet['result']:
        if not tRet['Inheritance']:
            eRet = __salt__['win_dacl.enable_inheritance'](name, objectType, clear_existing_acl)
            if eRet['result']:
                ret['result'] = True
                ret['changes'] = dict(ret['changes'], **eRet['changes'])
            else:
                ret['result'] = False
                ret['comment'] = ret['comment'] + eRet['comment']
    else:
        ret['result'] = False
        ret['comment'] = tRet['comment']
        return ret
    return ret


def disableinheritance(name, objectType, copy_inherited_acl=True):
    '''
    Ensure an object in inheriting ACLs from its parent
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}
    tRet = __salt__['win_dacl.check_inheritance'](name, objectType)
    if tRet['result']:
        if tRet['Inheritance']:
            eRet = __salt__['win_dacl.disable_inheritance'](name, objectType, copy_inherited_acl)
            if eRet['result']:
                ret['result'] = True
                ret['changes'] = dict(ret['changes'], **eRet['changes'])
            else:
                ret['result'] = False
                ret['comment'] = ret['comment'] + eRet['comment']
    else:
        ret['result'] = False
        ret['comment'] = tRet['comment']
        return ret
    return ret
