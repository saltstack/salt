# -*- coding: utf-8 -*-
"""
Management of SQLite3 databases
===============================

:depends:   - SQLite3 Python Module
:configuration: See :py:mod:`salt.modules.sqlite3` for setup instructions
.. versionadded:: 2016.3.0

The sqlite3 module is used to create and manage sqlite3 databases
and execute queries

Here is an example of creating a table using sql statements:

  .. code-block:: yaml

    users:
      sqlite3.table_present:
        - db: /var/www/data/app.sqlite
        - schema: CREATE TABLE `users` (`username` TEXT COLLATE NOCASE UNIQUE NOT NULL, `password` BLOB NOT NULL, `salt` BLOB NOT NULL, `last_login` INT)


Here is an example of creating a table using yaml/jinja instead of sql:

  .. code-block:: yaml

    users:
      sqlite3.table_present:
        - db: /var/www/app.sqlite
        - schema:
          - email TEXT COLLATE NOCASE UNIQUE NOT NULL
          - firstname TEXT NOT NULL
          - lastname TEXT NOT NULL
          - company TEXT NOT NULL
          - password BLOB NOT NULL
          - salt BLOB NOT NULL


Here is an example of making sure a table is absent:

  .. code-block:: yaml

    badservers:
      sqlite3.table_absent:
        - db: /var/www/data/users.sqlite


Sometimes you would to have specific data in tables to be used by other services
Here is an example of making sure rows with specific data exist:

  .. code-block:: yaml

    user_john_doe_xyz:
      sqlite3.row_present:
        - db: /var/www/app.sqlite
        - table: users
        - where_sql: email='john.doe@companyxyz.com'
        - data:
            email: john.doe@companyxyz.com
            lastname: doe
            firstname: john
            company: companyxyz.com
            password: abcdef012934125
            salt: abcdef012934125
        - require:
          - sqlite3: users


Here is an example of removing a row from a table:

  .. code-block:: yaml

    user_john_doe_abc:
      sqlite3.row_absent:
        - db: /var/www/app.sqlite
        - table: users
        - where_sql: email="john.doe@companyabc.com"
        - require:
          - sqlite3: users
"""

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.ext.six as six

try:
    import sqlite3

    HAS_SQLITE3 = True
except ImportError:
    HAS_SQLITE3 = False


def __virtual__():
    """
    Only load if the sqlite3 module is available
    """
    return HAS_SQLITE3


def row_absent(name, db, table, where_sql, where_args=None):
    """
    Makes sure the specified row is absent in db.  If multiple rows
    match where_sql, then the state will fail.

    name
        Only used as the unique ID

    db
        The database file name

    table
        The table name to check

    where_sql
        The sql to select the row to check

    where_args
        The list parameters to substitute in where_sql
    """
    changes = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}
    conn = None
    try:
        conn = sqlite3.connect(db, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = _dict_factory
        rows = None
        if where_args is None:
            rows = _query(conn,
                          "SELECT * FROM `" + table + "` WHERE " + where_sql)
        else:
            rows = _query(conn,
                          "SELECT * FROM `" + table + "` WHERE " + where_sql,
                          where_args)

        if len(rows) > 1:
            changes['result'] = False
            changes['comment'] = "More than one row matched the specified query"
        elif len(rows) == 1:
            if __opts__['test']:
                changes['result'] = True
                changes['comment'] = "Row will be removed in " + table
                changes['changes']['old'] = rows[0]

            else:
                cursor = conn.execute("DELETE FROM `" +
                                      table + "` WHERE " + where_sql,
                                      where_args)
                conn.commit()
                if cursor.rowcount == 1:
                    changes['result'] = True
                    changes['comment'] = "Row removed"
                    changes['changes']['old'] = rows[0]
                else:
                    changes['result'] = False
                    changes['comment'] = "Unable to remove row"
        else:
            changes['result'] = True
            changes['comment'] = 'Row is absent'

    except Exception as e:
        changes['result'] = False
        changes['comment'] = str(e)

    finally:
        if conn:
            conn.close()

    return changes


def row_present(name,
                db,
                table,
                data,
                where_sql,
                where_args=None,
                update=False):
    """
    Checks to make sure the given row exists. If row exists and update is True
    then row will be updated with data. Otherwise it will leave existing
    row unmodified and check it against data. If the existing data
    doesn't match data_check the state will fail.  If the row doesn't
    exist then it will insert data into the table. If more than one
    row matches, then the state will fail.

    name
        Only used as the unique ID

    db
        The database file name

    table
        The table name to check the data

    data
        The dictionary of key/value pairs to check against if
        row exists, insert into the table if it doesn't

    where_sql
        The sql to select the row to check

    where_args
        The list parameters to substitute in where_sql

    update
        True will replace the existing row with data
        When False and the row exists and data does not equal
        the row data then the state will fail
    """
    changes = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}
    conn = None
    try:
        conn = sqlite3.connect(db, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = _dict_factory
        rows = None
        if where_args is None:
            rows = _query(conn, "SELECT * FROM `" +
                                table + "` WHERE " + where_sql)
        else:
            rows = _query(conn, "SELECT * FROM `" +
                                table + "` WHERE " + where_sql,
                                where_args)

        if len(rows) > 1:
            changes['result'] = False
            changes['comment'] = 'More than one row matched the specified query'
        elif len(rows) == 1:
            for key, value in six.iteritems(data):
                if key in rows[0] and rows[0][key] != value:
                    if update:
                        if __opts__['test']:
                            changes['result'] = True
                            changes['comment'] = "Row will be update in " + table

                        else:
                            columns = []
                            params = []
                            for key, value in six.iteritems(data):
                                columns.append("`" + key + "`=?")
                                params.append(value)

                            if where_args is not None:
                                params += where_args

                            sql = "UPDATE `" + table + "` SET "
                            sql += ",".join(columns)
                            sql += " WHERE "
                            sql += where_sql
                            cursor = conn.execute(sql, params)
                            conn.commit()
                            if cursor.rowcount == 1:
                                changes['result'] = True
                                changes['comment'] = "Row updated"
                                changes['changes']['old'] = rows[0]
                                changes['changes']['new'] = data
                            else:
                                changes['result'] = False
                                changes['comment'] = "Row update failed"
                    else:
                        changes['result'] = False
                        changes['comment'] = "Existing data does" + \
                                             "not match desired state"
                        break

            if changes['result'] is None:
                changes['result'] = True
                changes['comment'] = "Row exists"
        else:
            if __opts__['test']:
                changes['result'] = True
                changes['changes']['new'] = data
                changes['comment'] = "Row will be inserted into " + table
            else:
                columns = []
                value_stmt = []
                values = []
                for key, value in six.iteritems(data):
                    value_stmt.append('?')
                    values.append(value)
                    columns.append("`" + key + "`")

                sql = "INSERT INTO `" + table + "` ("
                sql += ",".join(columns)
                sql += ") VALUES ("
                sql += ",".join(value_stmt)
                sql += ")"
                cursor = conn.execute(sql, values)
                conn.commit()
                if cursor.rowcount == 1:
                    changes['result'] = True
                    changes['changes']['new'] = data
                    changes['comment'] = 'Inserted row'
                else:
                    changes['result'] = False
                    changes['comment'] = "Unable to insert data"

    except Exception as e:
        changes['result'] = False
        changes['comment'] = str(e)

    finally:
        if conn:
            conn.close()

    return changes


def table_absent(name, db):
    """
    Make sure the specified table does not exist

    name
        The name of the table

    db
        The name of the database file
    """
    changes = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}
    conn = None
    try:
        conn = sqlite3.connect(db, detect_types=sqlite3.PARSE_DECLTYPES)
        tables = _query(conn, "SELECT sql FROM sqlite_master " +
                              " WHERE type='table' AND name=?", [name])

        if len(tables) == 1:
            if __opts__['test']:
                changes['result'] = True
                changes['comment'] = "'" + name + "' will be dropped"
            else:
                conn.execute("DROP TABLE " + name)
                conn.commit()
                changes['changes']['old'] = tables[0][0]
                changes['result'] = True
                changes['comment'] = "'" + name + "' was dropped"
        elif len(tables) == 0:
            changes['result'] = True
            changes['comment'] = "'" + name + "' is already absent"
        else:
            changes['result'] = False
            changes['comment'] = "Multiple tables with the same name='" + \
                                 name + "'"

    except Exception as e:
        changes['result'] = False
        changes['comment'] = str(e)

    finally:
        if conn:
            conn.close()

    return changes


def table_present(name, db, schema, force=False):
    """
    Make sure the specified table exists with the specified schema

    name
        The name of the table

    db
        The name of the database file

    schema
        The dictionary containing the schema information

    force
        If the name of the table exists and force is set to False,
        the state will fail.  If force is set to True, the existing
        table will be replaced with the new table
    """
    changes = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}
    conn = None
    try:
        conn = sqlite3.connect(db, detect_types=sqlite3.PARSE_DECLTYPES)
        tables = _query(conn,
                        "SELECT sql FROM sqlite_master " +
                        "WHERE type='table' AND name=?", [name])

        if len(tables) == 1:
            sql = None
            if isinstance(schema, str):
                sql = schema.strip()
            else:
                sql = _get_sql_from_schema(name, schema)

            if sql != tables[0][0]:
                if force:
                    if __opts__['test']:
                        changes['result'] = True
                        changes['changes']['old'] = tables[0][0]
                        changes['changes']['new'] = sql
                        changes['comment'] = "'" + name + "' will be replaced"
                    else:
                        conn.execute("DROP TABLE `" + name + "`")
                        conn.execute(sql)
                        conn.commit()
                        changes['result'] = True
                        changes['changes']['old'] = tables[0][0]
                        changes['changes']['new'] = sql
                        changes['comment'] = "Replaced '" + name + "'"
                else:
                    changes['result'] = False
                    changes['comment'] = "Expected schema=" + sql + \
                                         "\nactual schema=" + tables[0][0]
            else:
                changes['result'] = True
                changes['comment'] = "'" + name + \
                                     "' exists with matching schema"
        elif len(tables) == 0:
            # Create the table
            sql = None
            if isinstance(schema, str):
                sql = schema
            else:
                sql = _get_sql_from_schema(name, schema)
            if __opts__['test']:
                changes['result'] = True
                changes['changes']['new'] = sql
                changes['comment'] = "'" + name + "' will be created"
            else:
                conn.execute(sql)
                conn.commit()
                changes['result'] = True
                changes['changes']['new'] = sql
                changes['comment'] = "Created table '" + name + "'"
        else:
            changes['result'] = False
            changes['comment'] = 'Multiple tables with the same name=' + name

    except Exception as e:
        changes['result'] = False
        changes['comment'] = str(e)

    finally:
        if conn:
            conn.close()

    return changes


def _query(conn, sql, parameters=None):
    cursor = None
    if parameters is None:
        cursor = conn.execute(sql)
    else:
        cursor = conn.execute(sql, parameters)
    return cursor.fetchall()


def _get_sql_from_schema(name, schema):
    return "CREATE TABLE `" + name + "` (" + ",".join(schema) + ")"


def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d
