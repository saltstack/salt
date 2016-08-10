# -*- coding: utf-8 -*-
'''
Github User State Module

.. versionadded:: 2016.3.0.

This state is used to ensure presence of users in the Organization.

.. code-block:: yaml

    ensure user test is present in github:
        github.present:
            - name: 'Example TestUser1'
            - email: example@domain.com
            - username: 'gitexample'
'''


def __virtual__():
    '''
    Only load if the github module is available in __salt__
    '''
    return 'github' if 'github.list_users' in __salt__ else False


def present(name, profile="github", **kwargs):
    '''
    Ensure a user is present

    .. code-block:: yaml

        ensure user test is present in github:
            github.present:
                - fullname: 'Example TestUser1'
                - email: 'example@domain.com'
                - name: 'gitexample'

    The following parameters are required:

    name
        This is the github handle of the user in the organization
    '''

    email = kwargs.get('email')
    full_name = kwargs.get('fullname')

    ret = {
        'name': name,
        'changes': {},
        'result': None,
        'comment': ''
    }

    target = __salt__['github.get_user'](name, profile=profile, **kwargs)

    # If the user has a valid github handle and is not in the org already
    if not target:
        ret['result'] = False
        ret['comment'] = 'Couldnt find user {0}'.format(name)
    elif isinstance(target, bool) and target:
        ret['comment'] = 'User {0} is already in the org '.format(name)
        ret['result'] = True
    elif not target.get('in_org', False) and target.get('membership_state') != 'pending':
        if __opts__['test']:
            ret['comment'] = 'User {0} will be added to the org'.format(name)
            return ret

        # add the user
        result = __salt__['github.add_user'](
            name, profile=profile, **kwargs
        )

        if result:
            ret['changes'].setdefault('old', None)
            ret['changes'].setdefault('new', 'User {0} exists in the org now'.format(name))
            ret['result'] = True
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to add user {0} to the org'.format(name)
    else:
        ret['comment'] = 'User {0} has already been invited.'.format(name)
        ret['result'] = None

    return ret


def absent(name, profile="github", **kwargs):
    '''
    Ensure a github user is absent

    .. code-block:: yaml

        ensure user test is absent in github:
            github.absent:
                - name: 'Example TestUser1'
                - email: example@domain.com
                - username: 'gitexample'

    The following parameters are required:

    name
        Github handle of the user in organization

    '''
    email = kwargs.get('email')
    full_name = kwargs.get('fullname')

    ret = {
        'name': name,
        'changes': {},
        'result': None,
        'comment': 'User {0} is absent.'.format(name)
    }

    target = __salt__['github.get_user'](name, profile=profile, **kwargs)

    if not target:
        ret['comment'] = 'User {0} does not exist'.format(name)
        ret['result'] = True
        return ret
    elif isinstance(target, bool) and target:
        if __opts__['test']:
            ret['comment'] = "User {0} will be deleted".format(name)
            ret['result'] = None
            return ret

        result = __salt__['github.remove_user'](name, profile=profile, **kwargs)

        if result:
            ret['comment'] = 'Deleted user {0}'.format(name)
            ret['changes'].setdefault('old', 'User {0} exists'.format(name))
            ret['changes'].setdefault('new', 'User {0} deleted'.format(name))
            ret['result'] = True
        else:
            ret['comment'] = 'Failed to delete {0}'.format(name)
            ret['result'] = False
    else:
        ret['comment'] = "User {0} has already been deleted!".format(name)

        if __opts__['test']:
            ret['result'] = None
            return ret

        ret['result'] = True

    return ret
