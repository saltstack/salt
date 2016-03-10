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
          win_dacl.present:
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
          win_dacl.absent:
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
      win_dacl.enableinheritance:
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
      win_dacl.disableinheritance:
        - name: HKEY_LOCAL_MACHINE\\SOFTWARE\\mykey
        - objectType: Registry
        - copy_inherited_acl: False
'''


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
           'comment': ''}
    tRet = __salt__['win_dacl.check_ace'](name, objectType, user, permission, acetype, propagation, True)
    if tRet['result']:
        if not tRet['Exists']:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'The ACE is set to be added.'
                ret['changes']['Added ACEs'] = ((
                    '{0} {1} {2} on {3}'
                    ).format(user, acetype, permission, propagation))
                return ret
            addRet = __salt__['win_dacl.add_ace'](name, objectType, user, permission, acetype, propagation)
            if addRet['result']:
                ret['result'] = True
                ret['changes'] = dict(ret['changes'], **addRet['changes'])
            else:
                ret['result'] = False
                ret['comment'] = ' '.join([ret['comment'], addRet['comment']])
        else:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'The ACE is present.'
    else:
        ret['result'] = False
        ret['comment'] = tRet['comment']
    return ret


def absent(name, objectType, user, permission, acetype, propagation):
    '''
    Ensure a Linux ACL does not exist
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    tRet = __salt__['win_dacl.check_ace'](name, objectType, user, permission, acetype, propagation, True)
    if tRet['result']:
        if tRet['Exists']:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'The ACE is set to be removed.'
                ret['changes']['Removed ACEs'] = ((
                    '{0} {1} {2} on {3}'
                    ).format(user, acetype, permission, propagation))
                return ret
            addRet = __salt__['win_dacl.rm_ace'](name, objectType, user, permission, acetype, propagation)
            if addRet['result']:
                ret['result'] = True
                ret['changes'] = dict(ret['changes'], **addRet['changes'])
            else:
                ret['result'] = False
                ret['comment'] = ' '.join([ret['comment'], addRet['comment']])
        else:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'The ACE is not present.'
    else:
        ret['result'] = False
        ret['comment'] = tRet['comment']
    return ret


def inherit(name, objectType, clear_existing_acl=False):
    '''
    Ensure an object is inheriting ACLs from its parent
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    tRet = __salt__['win_dacl.check_inheritance'](name, objectType)
    if tRet['result']:
        if not tRet['Inheritance']:
            if __opts__['test']:
                ret['result'] = None
                ret['changes']['Inheritance'] = "Enabled"
                ret['comment'] = 'Inheritance is set to be enabled.'
                ret['changes']['Existing ACLs'] = (
                    'Are set to be removed' if clear_existing_acl else 'Are set to be kept')
                return ret
            eRet = __salt__['win_dacl.enable_inheritance'](name, objectType, clear_existing_acl)
            if eRet['result']:
                ret['result'] = True
                ret['changes'] = dict(ret['changes'], **eRet['changes'])
            else:
                ret['result'] = False
                ret['comment'] = ' '.join([ret['comment'], eRet['comment']])
        else:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'Inheritance is enabled.'
    else:
        ret['result'] = False
        ret['comment'] = tRet['comment']
    return ret


def disinherit(name, objectType, copy_inherited_acl=True):
    '''
    Ensure an object is not inheriting ACLs from its parent
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    tRet = __salt__['win_dacl.check_inheritance'](name, objectType)
    if tRet['result']:
        if tRet['Inheritance']:
            if __opts__['test']:
                ret['result'] = None
                ret['changes']['Inheritance'] = "Disabled"
                ret['comment'] = 'Inheritance is set to be disabled.'
                ret['changes']['Inherited ACLs'] = (
                        'Are set to be kept' if copy_inherited_acl else 'Are set to be removed')
                return ret
            eRet = __salt__['win_dacl.disable_inheritance'](name, objectType, copy_inherited_acl)
            ret['result'] = eRet['result']
            if eRet['result']:
                ret['changes'] = dict(ret['changes'], **eRet['changes'])
            else:
                ret['comment'] = ' '.join([ret['comment'], eRet['comment']])
        else:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'Inheritance is disabled.'
    else:
        ret['result'] = False
        ret['comment'] = tRet['comment']
    return ret
