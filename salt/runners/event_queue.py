# -*- coding: utf-8 -*-
'''
This is the default local master event queue
'''

# Import python libs
from __future__ import print_function
from pprint import pprint
import glob
import logging
import os
import sqlite3 as lite


log = logging.getLogger(__name__)

queue_dir = '/var/cache/salt/master/queues'


def _conn(queue):
    '''
    Return an sqlite connection
    '''
    db = os.path.join(queue_dir, '{0}.db'.format(queue))
    print('Connecting to:  ', db)

    con = lite.connect(db)
    tables = _list_tables(con)
    if queue not in tables:
        _create_table(con, queue)
    return con


def _list_tables(con):
    with con:
        cur = con.cursor()
        cur.execute('SELECT name FROM sqlite_master WHERE type = "table"')
        result = cur.fetchall()
        return [x[0] for x in result]


def _create_table(con, queue):
    with con:
        cur = con.cursor()
        cmd = 'CREATE TABLE {0}(id INTEGER PRIMARY KEY, '\
              'name TEXT UNIQUE)'.format(queue)
        cur.execute(cmd)


def _list_items(queue):
    '''
    Private function to list contents of a queue
    '''
    con = _conn(queue)
    with con:
        cur = con.cursor()
        cmd = 'SELECT * FROM {0}'.format(queue)
        cur.execute(cmd)
        contents = cur.fetchall()
    return contents


def _list_queues():
    '''
    Return a list of sqlite databases in the queue_dir
    '''
    files = os.path.join(queue_dir, '*.db')
    paths = glob.glob(files)
    queues = [os.path.splitext(os.path.basename(item))[0] for item in paths]

    return queues


def list_queues():
    '''
    Return a list of Salt Queues on the Salt Master

    CLI Example:

        salt-run queue.list_queue_files
    '''
    queues = _list_queues()
    pprint(queues)
    return queues


def list_items(queue):
    '''
    List contents of a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.list_items myqueue
    '''
    items = _list_items(queue)
    for item in items:
        print(item[1])
    return items


def list_length(queue):
    '''
    Provide the number of items in a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.list_length myqueue
    '''
    items = _list_items(queue)
    print(len(items))
    return len(items)


def insert(queue, items):
    '''
    Add an item or items to a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.insert myqueue myitem
        salt-run queue.insert myqueue "['item1', 'item2', 'item3']"
    '''
    con = _conn(queue)
    with con:
        cur = con.cursor()
        if isinstance(items, str):
            cmd = 'INSERT INTO {0}(name) VALUES("{1}")'.format(queue, items)
            try:
                cur.execute(cmd)
            except lite.IntegrityError as esc:
                print('Item already exists in this queue. '
                       'sqlite error: {0}'.format(esc))
        if isinstance(items, list):
            cmd = 'INSERT INTO {0}(name) VALUES(?)'.format(queue)
            newitems = []
            for item in items:
                newitems.append((item,))
                # we need a list of one item tuples here
            try:
                cur.executemany(cmd, newitems)
            except lite.IntegrityError as esc:
                print('One or more item already exists in this queue. '
                      'sqlite error: {0}'.format(esc))
    return True


def delete(queue, items):
    '''
    Delete an item or items from a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.delete myqueue myitem
        salt-run queue.delete myqueue "['item1', 'item2', 'item3']"
    '''
    con = _conn(queue)
    with con:
        cur = con.cursor()
        if isinstance(items, str):
            cmd = 'DELETE FROM {0} WHERE name = "{1}"'.format(queue, items)
            cur.execute(cmd)
            return True
        if isinstance(items, list):
            cmd = 'DELETE FROM {0} WHERE name = ?'.format(queue)
            newitems = []
            for item in items:
                newitems.append((item,))
                # we need a list of one item tuples here
            cur.executemany(cmd, newitems)
        return True


def pop(queue, quantity=1):
    '''
    Pop all items from the queue or a certain number of items from the queue
    and return them.

    CLI Example:

    .. code-block:: bash

        salt-run queue.pop myqueue
        salt-run queue.pop myqueue 6
        salt-run queue.pop myqueue all
    '''
    cmd = 'SELECT name FROM {0}'.format(queue)
    if quantity != 'all':
        quantity = int(quantity)
        cmd = ''.join([cmd, ' LIMIT {0}'.format(quantity)])
    con = _conn(queue)
    items = []
    with con:
        cur = con.cursor()
        result = cur.execute(cmd).fetchall()
        if len(result) > 0:
            items = [item[0] for item in result]
            itemlist = '","'.join(items)
            del_cmd = 'DELETE FROM {0} WHERE name IN ("{1}")'.format(
                                                               queue, itemlist)
            cur.execute(del_cmd)
        con.commit()
    log.info(items)
    print(items)
    return items
