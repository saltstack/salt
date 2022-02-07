"""
Test case for the etcd SDB module
"""


import logging

import salt.sdb.etcd_db as etcd_db
import salt.utils.etcd_util as etcd_util
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, create_autospec, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class TestEtcdSDB(LoaderModuleMockMixin, TestCase):
    """
    Test case for the etcd_db SDB module
    """

    def setup_loader_modules(self):
        return {
            etcd_db: {
                "__opts__": {
                    "myetcd": {
                        "url": "http://127.0.0.1",
                        "auth": {"token": "test", "method": "token"},
                    }
                }
            }
        }

    def setUp(self):
        self.instance = create_autospec(etcd_util.EtcdClient)
        self.EtcdClientMock = MagicMock()
        self.EtcdClientMock.return_value = self.instance

    def tearDown(self):
        del self.instance
        del self.EtcdClientMock

    def test_set(self):
        """
        Test salt.sdb.etcd_db.set function
        """
        with patch("salt.sdb.etcd_db._get_conn", self.EtcdClientMock):
            etcd_db.set_("sdb://myetcd/path/to/foo/bar", "super awesome")

        self.assertEqual(
            self.instance.set.call_args_list,
            [call("sdb://myetcd/path/to/foo/bar", "super awesome")],
        )

        self.assertEqual(
            self.instance.get.call_args_list,
            [call("sdb://myetcd/path/to/foo/bar")],
        )

    def test_get(self):
        """
        Test salt.sdb.etcd_db.get function
        """
        with patch("salt.sdb.etcd_db._get_conn", self.EtcdClientMock):
            etcd_db.get("sdb://myetcd/path/to/foo/bar")

        self.assertEqual(
            self.instance.get.call_args_list,
            [call("sdb://myetcd/path/to/foo/bar")],
        )
