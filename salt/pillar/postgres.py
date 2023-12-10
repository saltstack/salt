"""
Retrieve Pillar data by doing a postgres query

.. versionadded:: 2017.7.0

:maturity: new
:depends: psycopg2
:platform: all

Complete Example
================

.. code-block:: yaml

    postgres:
      user: 'salt'
      pass: 'super_secret_password'
      db: 'salt_db'

    ext_pillar:
      - postgres:
          fromdb:
            query: 'SELECT col1,col2,col3,col4,col5,col6,col7
                      FROM some_random_table
                     WHERE minion_pattern LIKE %s'
            depth: 5
            as_list: True
            with_lists: [1,3]
"""

import logging
from contextlib import contextmanager

from salt.pillar.sql_base import SqlBaseExtPillar

# Set up logging
log = logging.getLogger(__name__)

try:
    import psycopg2

    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False


def __virtual__():
    if not HAS_POSTGRES:
        return False
    return True


class POSTGRESExtPillar(SqlBaseExtPillar):
    """
    This class receives and processes the database rows from POSTGRES.
    """

    @classmethod
    def _db_name(cls):
        return "POSTGRES"

    def _get_options(self):
        """
        Returns options used for the POSTGRES connection.
        """
        defaults = {
            "host": "localhost",
            "user": "salt",
            "pass": "salt",
            "db": "salt",
            "port": 5432,
        }
        _options = {}
        _opts = __opts__.get("postgres", {})
        for attr in defaults:
            if attr not in _opts:
                log.debug("Using default for POSTGRES %s", attr)
                _options[attr] = defaults[attr]
                continue
            _options[attr] = _opts[attr]
        return _options

    @contextmanager
    def _get_cursor(self):
        """
        Yield a POSTGRES cursor
        """
        _options = self._get_options()
        conn = psycopg2.connect(
            host=_options["host"],
            user=_options["user"],
            password=_options["pass"],
            dbname=_options["db"],
            port=_options["port"],
        )
        cursor = conn.cursor()
        try:
            yield cursor
            log.debug("Connected to POSTGRES DB")
        except psycopg2.DatabaseError as err:
            log.exception("Error in ext_pillar POSTGRES: %s", err.args)
        finally:
            conn.close()

    def extract_queries(self, args, kwargs):  # pylint: disable=useless-super-delegation
        """
        This function normalizes the config block into a set of queries we
        can use.  The return is a list of consistently laid out dicts.
        """
        return super().extract_queries(args, kwargs)


def ext_pillar(minion_id, pillar, *args, **kwargs):
    """
    Execute queries against POSTGRES, merge and return as a dict
    """
    return POSTGRESExtPillar().fetch(minion_id, pillar, *args, **kwargs)
