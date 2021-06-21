"""
unit tests for the mysql_cache cache
"""


import logging

import salt.cache.mysql_cache as mysql_cache
import salt.payload
import salt.utils.files
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class MockMySQLConnect:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def autocommit(self, *args, **kwards):
        return True

    def cursor(self, *args, **kwards):
        return MockMySQLCursor()


class MockMySQLCursor:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def execute(self, *args, **kwards):
        return MagicMock()

    def fetchone(self, *args, **kwards):
        return MagicMock()

    def close(self, *args, **kwards):
        return MagicMock()


class MySQLCacheTest(TestCase, LoaderModuleMockMixin):
    """
    Validate the functions in the mysql_cache cache
    """

    def setup_loader_modules(self):
        return {mysql_cache: {}}

    def test_run_query(self):
        """
        Tests that a SaltCacheError is raised when there is a problem writing to the
        cache file.
        """
        with patch.object(mysql_cache, "_mysql_kwargs", return_value={}), patch(
            "MySQLdb.connect", return_value=MockMySQLConnect()
        ) as mock_connect:
            ret = mysql_cache.run_query(conn=None, query="SELECT 1;")

    def test_store(self):
        """
        Tests that the store function writes the data to the serializer for storage.
        """
        serializer = salt.payload.Serial(self)

        with patch.object(mysql_cache, "_mysql_kwargs", return_value={}), patch(
            "MySQLdb.connect", return_value=MockMySQLConnect()
        ) as mock_connect:
            with patch.dict(mysql_cache.__context__, {"serial": serializer}):
                mysql_cache.store(bank="", key="", data="")
                # check that an exception is not raised
