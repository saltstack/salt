"""
.. versionadded:: 2014.7.0

This is the default local master event queue built on sqlite.  By default, an
sqlite3 database file is created in the `sqlite_queue_dir` which is found at::

    /var/cache/salt/master/queues

It's possible to store the sqlite3 database files by setting `sqlite_queue_dir`
to another location::

    sqlite_queue_dir: /home/myuser/salt/master/queues
"""

import glob
import logging
import os
import re
import sqlite3

import salt.utils.json
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "sqlite"


def __virtual__():
    # All python servers should have sqlite3 and so be able to use
    # this default sqlite queue system
    return __virtualname__


def _conn(queue):
    """
    Return an sqlite connection
    """
    queue_dir = __opts__["sqlite_queue_dir"]
    db = os.path.join(queue_dir, f"{queue}.db")
    log.debug("Connecting to: %s", db)

    con = sqlite3.connect(db)
    tables = _list_tables(con)
    if queue not in tables:
        _create_table(con, queue)
    return con


def _list_tables(con):
    with con:
        cur = con.cursor()
        cmd = 'SELECT name FROM sqlite_master WHERE type = "table"'
        log.debug("SQL Query: %s", cmd)
        cur.execute(cmd)
        result = cur.fetchall()
        return [x[0] for x in result]


def _create_table(con, queue):
    with con:
        cur = con.cursor()
        cmd = f"CREATE TABLE {queue}(id INTEGER PRIMARY KEY, name TEXT UNIQUE)"
        log.debug("SQL Query: %s", cmd)
        cur.execute(cmd)
    return True


def _list_items(queue):
    """
    Private function to list contents of a queue
    """
    con = _conn(queue)
    with con:
        cur = con.cursor()
        cmd = f"SELECT name FROM {queue}"
        log.debug("SQL Query: %s", cmd)
        cur.execute(cmd)
        contents = cur.fetchall()
    return contents


def _list_queues():
    """
    Return a list of sqlite databases in the queue_dir
    """
    queue_dir = __opts__["sqlite_queue_dir"]
    files = os.path.join(queue_dir, "*.db")
    paths = glob.glob(files)
    queues = [os.path.splitext(os.path.basename(item))[0] for item in paths]

    return queues


def list_queues():
    """
    Return a list of Salt Queues on the Salt Master
    """
    queues = _list_queues()
    return queues


def list_items(queue):
    """
    List contents of a queue
    """
    itemstuple = _list_items(queue)
    items = [item[0] for item in itemstuple]
    return items


def list_length(queue):
    """
    Provide the number of items in a queue
    """
    items = _list_items(queue)
    return len(items)


def _quote_escape(item):
    """
    Make sure single quotes are escaped properly in sqlite3 fashion.
    e.g.: ' becomes ''
    """

    rex_sqlquote = re.compile("'", re.M)

    return rex_sqlquote.sub("''", item)


def insert(queue, items):
    """
    Add an item or items to a queue
    """
    con = _conn(queue)
    with con:
        cur = con.cursor()
        if isinstance(items, str):
            items = _quote_escape(items)
            cmd = f"INSERT INTO {queue}(name) VALUES('{items}')"
            log.debug("SQL Query: %s", cmd)
            try:
                cur.execute(cmd)
            except sqlite3.IntegrityError as esc:
                return f"Item already exists in this queue. sqlite error: {esc}"
        if isinstance(items, list):
            items = [_quote_escape(el) for el in items]
            cmd = f"INSERT INTO {queue}(name) VALUES(?)"
            log.debug("SQL Query: %s", cmd)
            newitems = []
            for item in items:
                newitems.append((item,))
                # we need a list of one item tuples here
            try:
                cur.executemany(cmd, newitems)
            except sqlite3.IntegrityError as esc:
                return (
                    "One or more items already exists in this queue. "
                    "sqlite error: {}".format(esc)
                )
        if isinstance(items, dict):
            items = salt.utils.json.dumps(items).replace('"', "'")
            items = _quote_escape(items)
            cmd = f"INSERT INTO {queue}(name) VALUES('{items}')"
            log.debug("SQL Query: %s", cmd)
            try:
                cur.execute(cmd)
            except sqlite3.IntegrityError as esc:
                return f"Item already exists in this queue. sqlite error: {esc}"
    return True


def delete(queue, items):
    """
    Delete an item or items from a queue
    """
    con = _conn(queue)
    with con:
        cur = con.cursor()
        if isinstance(items, str):
            items = _quote_escape(items)
            cmd = f"DELETE FROM {queue} WHERE name = '{items}'"
            log.debug("SQL Query: %s", cmd)
            cur.execute(cmd)
            return True
        if isinstance(items, list):
            items = [_quote_escape(el) for el in items]
            cmd = f"DELETE FROM {queue} WHERE name = ?"
            log.debug("SQL Query: %s", cmd)
            newitems = []
            for item in items:
                newitems.append((item,))
                # we need a list of one item tuples here
            cur.executemany(cmd, newitems)
        if isinstance(items, dict):
            items = salt.utils.json.dumps(items).replace('"', "'")
            items = _quote_escape(items)
            cmd = f"DELETE FROM {queue} WHERE name = '{items}'"
            log.debug("SQL Query: %s", cmd)
            cur.execute(cmd)
            return True
        return True


def pop(queue, quantity=1, is_runner=False):
    """
    Pop one or more or all items from the queue return them.
    """
    cmd = f"SELECT name FROM {queue}"
    if quantity != "all":
        try:
            quantity = int(quantity)
        except ValueError as exc:
            error_txt = 'Quantity must be an integer or "all".\nError: "{}".'.format(
                exc
            )
            raise SaltInvocationError(error_txt)
        cmd = "".join([cmd, f" LIMIT {quantity}"])
    log.debug("SQL Query: %s", cmd)
    con = _conn(queue)
    items = []
    with con:
        cur = con.cursor()
        result = cur.execute(cmd).fetchall()
        if len(result) > 0:
            items = [item[0] for item in result]
            itemlist = '","'.join(items)
            _quote_escape(itemlist)
            del_cmd = f'DELETE FROM {queue} WHERE name IN ("{itemlist}")'

            log.debug("SQL Query: %s", del_cmd)

            cur.execute(del_cmd)
        con.commit()
    if is_runner:
        items = [salt.utils.json.loads(item[0].replace("'", '"')) for item in result]
    log.info(items)
    return items
