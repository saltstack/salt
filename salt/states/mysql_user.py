'''
MySQL User Management
=====================
The mysql_database module is used to create and manage MySQL databases, databases can be set
as either absent or present

.. code-block:: yaml

    frank:
      mysql_user:
        - present
        - host: localhost
		- password: bobcat
'''

def present(name,
            host='localhost',
            password=None):
    '''
    Ensure that the named user is present with the specified properties

    name
        The name of the user to manage
    '''    
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0}@{1} is already present'.format(name,host,)}
    # check if user exists
    if __salt__['mysql.user_exists'](name,host):
        return ret        

    # The user is not present, make it!
    if __salt__['mysql.user_create'](name,host,password,):
        ret['comment'] = 'The user {0}@{1} has been added'.format(name,host,)
        ret['changes'][name] = 'Present'
    else:
        ret['comment'] = 'Failed to create user {0}@{1}'.format(name,host)
        ret['result'] = False

    return ret


def absent(name,
           host='localhost'):
    '''
    Ensure that the named user is absent

    name
        The name of the user to remove
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if db exists and remove it
    if __salt__['mysql.user_exists'](name,host,):
        if __salt__['mysql.user_remove'](name,host,):
            ret['comment'] = 'User {0}@{1} has been removed'.format(name,host,)
            ret['changes'][name] = 'Absent'
            return ret
        
    # fallback
    ret['comment'] = 'User {0}@{1} is not present, so it cannot be removed'.format(name,host,)
    return ret
