'''
MySQL Database Management
===============
The mysql_database module is used to create and manage MySQL databases, databases can be set
as either absent or present

.. code-block:: yaml

    frank:
      mysql_database:
        - present
'''

def present(name):
    '''
    Ensure that the named database is present with the specified properties

    name
        The name of the database to manage
    '''    
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Database {0} is already present'.format(name)}
    # check if database exists
    if __salt__['mysql.db_exists'](name):
        return ret        

    # The database is not present, make it!
    if __salt__['mysql.db_create'](name):
        ret['comment'] = 'The database {0} has been created'.format(name)
        ret['changes'][name] = 'Present'
    else:
        ret['comment'] = 'Failed to create database {0}'.format(name)
        ret['result'] = False

    return ret


def absent(name):
    '''
    Ensure that the named database is absent

    name
        The name of the database to remove
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if db exists and remove it
    if __salt__['mysql.db_exists'](name):
        if __salt__['mysql.db_remove'](name):
            ret['comment'] = 'Database {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret
        
    # fallback
    ret['comment'] = 'Database {0} is not present, so it cannot be removed'.format(name)
    return ret