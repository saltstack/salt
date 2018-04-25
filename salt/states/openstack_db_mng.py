# -*- coding: utf-8 -*-
'''
Management of databases for Openstack projects
==================


:depends:   - oslo_db, alembic, Openstack Python module

This module is used to migrate database for Openstacks projects
keystone, nova, cinder, heat, neutron, glance, mistral, manila

.. code-block:: yaml

    keystone:
      openstack_db_mng.migration:
        - connection: mysql://keystone:keystone@localhost/keystone

    openstack_db_mng.migration:
      - name: neutron
      - connection: mysql://neutron:neutron@localhost/neutron
      - mysql_engine: ndbcluster

:codeauthor: David Homolka <david.homolka@ultimum.io>
'''
from __future__ import absolute_import

# Import salt libs
from salt.exceptions import SaltInvocationError, SaltException


def __virtual__():
    '''
    Only load if the openstack_db_mng module is in __salt__
    '''
    if 'openstack_db_mng.check_db_migration' not in __salt__:
        return False
    if 'openstack_db_mng.db_migration' not in __salt__:
        return False
    return True


def migration(name, connection, mysql_engine=None, user=None, group=None):
    '''
    Migration database for Openstack service.

    name
        The name of the Openstack service to use (e.g.: keystone, nova, cinder, heat, neutron, glance, mistral, manila)

    connection
        URL to database

    mysql_engine
        MySQL storage engine of current existing tables(innodb, ndbcluster) - (only used for neutron)

    user
        User to run migration command as.

    group
        Group to run migration command as.
    '''

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    try:
        check_db_migration = __salt__['openstack_db_mng.check_db_migration'](name, connection)
    except (SaltInvocationError, SaltException) as exc:
        ret['comment'] = (
            'Unable to check database migration \'{0}\': {1}'
            .format(name, exc)
        )
        return ret

    if check_db_migration:
        try:
            db_migration = __salt__['openstack_db_mng.db_migration'](name, mysql_engine=mysql_engine,
                                                                     user=user, group=group)
        except (SaltInvocationError, SaltException) as exc:
            ret['comment'] = (
                'Unable to database migration \'{0}\': {1}'
                .format(name, exc)
            )
            return ret

        if db_migration is True:
            ret['result'] = True
            ret['changes']['db_migration'] = name
        else:
            ret['comment'] = db_migration[1]
    else:
        ret['result'] = True
        ret['comment'] = 'Database {0} is in last migration.'.format(name)

    return ret
