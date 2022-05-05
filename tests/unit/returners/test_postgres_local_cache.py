"""
tests.unit.returners.postgres_local_cache_test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the postgres_local_cache.
"""

import json
import logging
import os
import shutil

import salt.returners.postgres_local_cache as postgres_local_cache
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class PostgresLocalCacheTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for the postgre_local_cache returner.
    """

    @classmethod
    def setUpClass(cls):
        cls.TMP_CACHE_DIR = os.path.join(RUNTIME_VARS.TMP, "salt_test_job_cache")
        cls.TMP_JID_DIR = os.path.join(cls.TMP_CACHE_DIR, "jobs")

    def setup_loader_modules(self):
        return {
            postgres_local_cache: {
                "__opts__": {"cachedir": self.TMP_CACHE_DIR, "keep_jobs": 1}
            }
        }

    def tearDown(self):
        """
        Clean up after tests.

        Note that a setUp function is not used in this TestCase because the
        _make_tmp_jid_dirs replaces it.
        """
        if os.path.exists(self.TMP_CACHE_DIR):
            shutil.rmtree(self.TMP_CACHE_DIR)

    def test_returner(self):
        """
        Tests that the returner function
        """
        load = {
            "tgt_type": "glob",
            "fun_args": [],
            "jid": "20200108221839189167",
            "return": True,
            "retcode": 0,
            "success": True,
            "tgt": "minion",
            "cmd": "_return",
            "_stamp": "2020-01-08T22:18:39.197774",
            "arg": [],
            "fun": "test.ping",
            "id": "minion",
        }

        expected = {"return": "True", "retcode": 0, "success": True}

        connect_mock = MagicMock()
        with patch.object(postgres_local_cache, "_get_conn", connect_mock):
            postgres_local_cache.returner(load)

            return_val = None
            for call in connect_mock.mock_calls:
                for arg in call.args:
                    if isinstance(arg, tuple):
                        for val in arg:
                            if isinstance(val, str) and "return" in val:
                                return_val = json.loads(val)

            self.assertIsNotNone(return_val, None)
            self.assertDictEqual(return_val, expected)

    def test_returner_unicode_exception(self):
        """
        Tests that the returner function
        """
        return_val = "Trüe"

        load = {
            "tgt_type": "glob",
            "fun_args": [],
            "jid": "20200108221839189167",
            "return": return_val,
            "retcode": 0,
            "success": True,
            "tgt": "minion",
            "cmd": "_return",
            "_stamp": "2020-01-08T22:18:39.197774",
            "arg": [],
            "fun": "test.ping",
            "id": "minion",
        }

        expected = {"return": "Trüe", "retcode": 0, "success": True}

        connect_mock = MagicMock()
        with patch.object(postgres_local_cache, "_get_conn", connect_mock):
            postgres_local_cache.returner(load)

            return_val = None
            search_string = "return"
            for call in connect_mock.mock_calls:
                for arg in call.args:
                    if isinstance(arg, tuple):
                        for val in arg:
                            if isinstance(val, str):
                                if search_string in val:
                                    return_val = json.loads(val)

            self.assertIsNotNone(return_val, None)
            self.assertDictEqual(return_val, expected)
