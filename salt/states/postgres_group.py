'''
Management of PostgreSQL groups (roles).
========================================

The postgres_group module is used to create and manage Postgres groups.

.. code-block:: yaml

    frank:
      postgres_group.present
'''

def present(name,
            createdb=False,
            createuser=False,
            encrypted=False,
            superuser=False,
            replication=False,
            password=None,
            groups=None,
            runas=None):
    '''
    Ensure that the named group is present with the specified privileges

    name
        The name of the group to manage

    createdb
        Is the group allowed to create databases?

    createuser
        Is the group allowed to create other users?

    encrypted
        Should the password be encrypted in the system catalog?

    superuser
        Should the new group be a "superuser"

    replication
        Should the new group be allowed to initiate streaming replication

    password
        The group's pasword

    groups
        A string of comma seperated groups the group should be in

    runas
        System user all operation should be preformed on behalf of
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Group {0} is already present'.format(name)}

    # check if user exists
    if __salt__['postgres.user_exists'](name, runas=runas):
        return ret

    # The user is not present, make it!
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Group {0} is set to be created'.format(name)
        return ret
    if __salt__['postgres.group_create'](groupname=name,
                                         createdb=createdb,
                                         createuser=createuser,
                                         encrypted=encrypted,
                                         superuser=superuser,
                                         replication=replication,
                                         password=password,
                                         groups=groups,
                                         runas=runas):
        ret['comment'] = 'The group {0} has been created'.format(name)
        ret['changes'][name] = 'Present'
    else:
        ret['comment'] = 'Failed to create group {0}'.format(name)
        ret['result'] = False

    return ret


def absent(name, runas=None):
    '''
    Ensure that the named group is absent

    name
        The groupname of the group to remove

    runas
        System user all operation should be preformed on behalf of
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # check if group exists and remove it
    if __salt__['postgres.user_exists'](name, runas=runas):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Group {0} is set to be removed'.format(name)
            return ret
        if __salt__['postgres.group_remove'](name, runas=runas):
            ret['comment'] = 'Group {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret
    else:
        ret['comment'] = 'Group {0} is not present, so it cannot be removed'.format(name)

    return ret
