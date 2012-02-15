'''
MySQL Grant Management
=====================
The mysql_grants module is used to grant and revoke MySQL permissions.

The ``name`` you pass in purely symbolic and does not have anything to do
with the grant itself.

The ``database`` parameter needs to specify a 'priv_level' in the same
specification as defined in the MySQL documentation:
 - *
 - *.*
 - db_name.*
 - db_name.tbl_name
 - etc...

.. code-block:: yaml

   frank_exampledb:
      mysql_grants:
       - present
       - grant: select,insert,update
       - database: exampledb.*
       - user: frank
       - host: localhost

   frank_otherdb:
     mysql_grants:
       - present
       - grant: all privileges
       - database: otherdb.*
       - user: frank

   restricted_singletable:
     mysql_grants:
       - present
       - grant: select
       - database: somedb.sometable
       - user: joe
'''

def present(name,
            grant=None,
            database=None,
            user=None,
            host='localhost'):
    '''
    Ensure that the grant is present with the specified properties

    name
        The name (key) of the grant to add

    grant
        The grant priv_type (ie. select,insert,update OR all privileges)

    database
        The database priv_level (ie. db.tbl OR db.*)

    user
        The user to apply the grant to

    host
        The MySQL server
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Grant {0} for {1}@{2} on {3} is already present'.format(
               grant,
               user,
               host,
               database
               )
           }
    # check if grant exists
    if __salt__['mysql.grant_exists'](grant,database,user,host):
        return ret

    # The grant is not present, make it!
    if __salt__['mysql.grant_add'](grant,database,user,host):
        ret['comment'] = 'Grant {0} for {1}@{2} on {3} has been added'.format(
                grant,
                user,
                host,
                database
                )
        ret['changes'][name] = 'Present'
    else:
        ret['comment'] = 'Failed to grant {0} for {1}@{2} on {3}'.format(
                grant,
                user,
                host,
                database
                )
        ret['result'] = False
    return ret


def absent(name,
           grant=None,
           database=None,
           user=None,
           host='localhost'):
    '''
    Ensure that the grant is absent

    name
        The name (key) of the grant to add

    grant
        The grant priv_type (ie. select,insert,update OR all privileges)

    database
        The database priv_level (ie. db.tbl OR db.*)

    user
        The user to apply the grant to

    host
        The MySQL server
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if db exists and remove it
    if __salt__['mysql.grant_exists'](grant,database,user,host,):
        if __salt__['mysql.grant_revoke'](grant,database,user,host):
            ret['comment'] = ('Grant {0} for {1}@{2} on {3} has been'
                              ' revoked').format(
                                      grant,
                                      user,
                                      host,
                                      database
                                      )
            ret['changes'][name] = 'Absent'
            return ret

    # fallback
    ret['comment'] = ('Grant {0} for {1}@{2} on {3} is not present, so it'
                      ' cannot be revoked').format(
                              grant,
                              user,
                              host,
                              database
                              )
    return ret
