# -*- coding: utf-8 -*-
'''
Management of PostgreSQL Privileges
===================================

The postgres_privileges module is used to manage Postgres privileges.
Privileges can be set as either absent or present.

Privileges can be set on the following database object types:

* database
* schema
* tablespace
* table
* sequence
* function
* language
* group

.. versionadded:: Boron

.. code-block:: yaml
    set-user-privs:
      postgres_privileges.present:
        - maintenance_db: testdb

.. code-block:: yaml
    remove-user-privs:
      postgres_privileges.absent:
        - maintenance_db: testdb

.. versionadded:: Boron

'''
from __future__ import absolute_import


def __virtual__():
    '''
    Only load if the postgres module is present
    '''
    return 'postgres.privilege_create' in __salt__


def present(name,
            maintenance_db,
            user=None,
            db_password=None,
            db_host=None,
            db_port=None,
            db_user=None):
    '''
    Set the requested privilege(s) on the specified object(s)
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': ''
    }


def absent(name,
            maintenance_db,
            user=None,
            db_password=None,
            db_host=None,
            db_port=None,
            db_user=None):
    '''
    Revoke the requested privilege(s) on the specificed object(s)
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': ''
    }
