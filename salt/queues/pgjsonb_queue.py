# -*- coding: utf-8 -*-
'''
.. versionadded:: 2016.3.0

This is a queue with postgres as the backend.  It uses the jsonb store to
store information for queues.

:depends:       python-psycopg2

To enable this queue, the following needs to be configured in your master
config. These are the defaults:

.. code-block:: yaml

    queue.pgjsonb.host: 'salt'
    queue.pgjsonb.user: 'salt'
    queue.pgjsonb.pass: 'salt'
    queue.pgjsonb.db: 'salt'
    queue.pgjsonb.port: 5432

Use the following Pg database schema:

.. code-block:: sql

    CREATE DATABASE  salt WITH ENCODING 'utf-8';

    --
    -- Table structure for table `salt`
    --
    DROP TABLE IF EXISTS salt;
    CREATE OR REPLACE TABLE salt(
       id SERIAL PRIMARY KEY,
       data jsonb NOT NULL
    );

.. code-block:: bash

    salt-run queue.insert test '{"name": "redis", "host": "172.16.0.8", "port": 6379}' backend=pgjsonb
    salt-run queue.process_queue test all backend=pgjsonb
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
from contextlib import contextmanager
import sys

# import salt libs
import salt.utils.json
from salt.ext import six
from salt.exceptions import SaltInvocationError, SaltMasterError

try:
    import psycopg2
    HAS_PG = True
except ImportError:
    HAS_PG = False

import logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pgjsonb'


def __virtual__():
    if HAS_PG is False:
        return False
    return __virtualname__


@contextmanager
def _conn(commit=False):
    '''
    Return an postgres cursor
    '''
    defaults = {'host': 'localhost',
                'user': 'salt',
                'password': 'salt',
                'dbname': 'salt',
                'port': 5432}

    conn_kwargs = {}
    for key, value in defaults.items():
        conn_kwargs[key] = __opts__.get('queue.{0}.{1}'.format(__virtualname__, key), value)
    try:
        conn = psycopg2.connect(**conn_kwargs)
    except psycopg2.OperationalError as exc:
        raise SaltMasterError('pgjsonb returner could not connect to database: {exc}'.format(exc=exc))

    cursor = conn.cursor()

    try:
        yield cursor
    except psycopg2.DatabaseError as err:
        error = err.args
        sys.stderr.write(six.text_type(error))
        cursor.execute("ROLLBACK")
        raise err
    else:
        if commit:
            cursor.execute("COMMIT")
        else:
            cursor.execute("ROLLBACK")
    finally:
        conn.close()


def _list_tables(cur):
    cmd = "select relname from pg_class where relkind='r' and relname !~ '^(pg_|sql_)';"
    log.debug('SQL Query: %s', cmd)
    cur.execute(cmd)
    result = cur.fetchall()
    return [x[0] for x in result]


def _create_table(cur, queue):
    cmd = 'CREATE TABLE {0}(id SERIAL PRIMARY KEY, '\
          'data jsonb NOT NULL)'.format(queue)
    log.debug('SQL Query: %s', cmd)
    cur.execute(cmd)
    return True


def _list_items(queue):
    '''
    Private function to list contents of a queue
    '''
    with _conn() as cur:
        cmd = 'SELECT data FROM {0}'.format(queue)
        log.debug('SQL Query: %s', cmd)
        cur.execute(cmd)
        contents = cur.fetchall()
        return contents


def list_queues():
    '''
    Return a list of Salt Queues on the Salt Master
    '''
    with _conn() as cur:
        queues = _list_tables(cur)
    return queues


def list_items(queue):
    '''
    List contents of a queue
    '''
    itemstuple = _list_items(queue)
    items = [item[0] for item in itemstuple]
    return items


def list_length(queue):
    '''
    Provide the number of items in a queue
    '''
    items = _list_items(queue)
    return len(items)


def _queue_exists(queue):
    '''
    Does this queue exist
    :param queue: Name of the queue
    :type str
    :return: True if this queue exists and
    False otherwise
    :rtype bool
    '''
    return queue in list_queues()


def handle_queue_creation(queue):
    if not _queue_exists(queue):
        with _conn(commit=True) as cur:
            log.debug('Queue %s does not exist. Creating', queue)
            _create_table(cur, queue)
    else:
        log.debug('Queue %s already exists.', queue)


def insert(queue, items):
    '''
    Add an item or items to a queue
    '''
    handle_queue_creation(queue)

    with _conn(commit=True) as cur:
        if isinstance(items, dict):
            items = salt.utils.json.dumps(items)
            cmd = str('''INSERT INTO {0}(data) VALUES('{1}')''').format(queue, items)  # future lint: disable=blacklisted-function
            log.debug('SQL Query: %s', cmd)
            try:
                cur.execute(cmd)
            except psycopg2.IntegrityError as esc:
                return ('Item already exists in this queue. '
                        'postgres error: {0}'.format(esc))
        if isinstance(items, list):
            items = [(salt.utils.json.dumps(el),) for el in items]
            cmd = str("INSERT INTO {0}(data) VALUES (%s)").format(queue)  # future lint: disable=blacklisted-function
            log.debug('SQL Query: %s', cmd)
            try:
                cur.executemany(cmd, items)
            except psycopg2.IntegrityError as esc:
                return ('One or more items already exists in this queue. '
                        'postgres error: {0}'.format(esc))
    return True


def delete(queue, items):
    '''
    Delete an item or items from a queue
    '''
    with _conn(commit=True) as cur:
        if isinstance(items, dict):
            cmd = str("""DELETE FROM {0} WHERE data = '{1}'""").format(  # future lint: disable=blacklisted-function
                queue,
                salt.utils.json.dumps(items))
            log.debug('SQL Query: %s', cmd)
            cur.execute(cmd)
            return True
        if isinstance(items, list):
            items = [(salt.utils.json.dumps(el),) for el in items]
            cmd = 'DELETE FROM {0} WHERE data = %s'.format(queue)
            log.debug('SQL Query: %s', cmd)
            cur.executemany(cmd, items)
    return True


def pop(queue, quantity=1, is_runner=False):
    '''
    Pop one or more or all items from the queue return them.
    '''
    cmd = 'SELECT id, data FROM {0}'.format(queue)
    if quantity != 'all':
        try:
            quantity = int(quantity)
        except ValueError as exc:
            error_txt = ('Quantity must be an integer or "all".\n'
                         'Error: "{0}".'.format(exc))
            raise SaltInvocationError(error_txt)
        cmd = ''.join([cmd, ' LIMIT {0};'.format(quantity)])
    log.debug('SQL Query: %s', cmd)
    items = []
    with _conn(commit=True) as cur:
        cur.execute(cmd)
        result = cur.fetchall()
        if len(result) > 0:
            ids = [six.text_type(item[0]) for item in result]
            items = [item[1] for item in result]
            idlist = "','".join(ids)
            del_cmd = '''DELETE FROM {0} WHERE id IN ('{1}');'''.format(
                queue, idlist)

            log.debug('SQL Query: %s', del_cmd)

            cur.execute(del_cmd)
    return items
