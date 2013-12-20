# -*- coding: utf-8 -*-
'''
Execution of MySQL queries
==========================

:depends:   - MySQLdb Python module
:configuration: See :py:mod:`salt.modules.mysql` for setup instructions.

The mysql_query module is used to execute queries on MySQL databases.

.. code-block:: yaml

    query_id:
      mysql_query.exec
        - database: my_database
        - query:    "SELECT * FROM table;"
        - output:   "/tmp/query_id.txt"
'''

import sys
import os.path


def __virtual__():
    '''
    Only load if the mysql module is available in __salt__
    '''
    return 'mysql_query' if 'mysql.query' in __salt__ else False


def _get_mysql_error():
    '''
    Look in module context for a MySQL error. Eventually we should make a less
    ugly way of doing this.
    '''
    return sys.modules[
        __salt__['test.ping'].__module__
    ].__context__.pop('mysql.error', None)


def run(name,
        database,
        query,
        output=None,
        overwrite=True,
        **connection_args):
    '''
    Execute an arbitrary query on the specified database

    name
        Used only as an ID

    database
        The name of the database to execute the query on

    query
        The query to execute

    output
        The file to store results (if defined)

    overwrite
        The file will be overwritten if it already exists (default)
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Database {0} is already present'.format(name)}
    # check if database exists
    if not __salt__['mysql.db_exists'](database, **connection_args):
        err = _get_mysql_error()
        if err is not None:
            ret['comment'] = err
            ret['result'] = False
            return ret

        ret['result'] = None
        ret['comment'] = ('Database {0} is not present'
                ).format(name)
        return ret

    # The database is present, execute the query
    results = __salt__['mysql.query'](database, query, **connection_args)
    ret['comment'] = results

    if output is not None:
        if overwrite or not os.path.isfile(output):
            ret['changes']['query'] = "Executed. Output into " + output
            with open(output, 'w') as output_file:
                for res in results['results']:
                    for idx, col in enumerate(results['columns']):
                        output_file.write(col + ':' + res[idx] + '\n')
    else:
        ret['changes']['query'] = "Executed"

    return ret
