# -*- coding: utf-8 -*-
"""
unit tests for the cache runner
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.runners.cache as cache
import salt.utils.master
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class CacheTest(TestCase, LoaderModuleMockMixin):
    """
    Validate the cache runner
    """

    def setup_loader_modules(self):
        return {
            cache: {
                "__opts__": {
                    "cache": "localfs",
                    "pki_dir": RUNTIME_VARS.TMP,
                    "key_cache": True,
                }
            }
        }

    def test_grains(self):
        """
        test cache.grains runner
        """
        mock_minion = ["Larry"]
        mock_ret = {}
        self.assertEqual(cache.grains(minion=mock_minion), mock_ret)

        mock_data = "grain stuff"

        class MockMaster(object):
            def __init__(self, *args, **kwargs):
                pass

            def get_minion_grains(self):
                return mock_data

        with patch.object(salt.utils.master, "MasterPillarUtil", MockMaster):
            self.assertEqual(cache.grains(), mock_data)
