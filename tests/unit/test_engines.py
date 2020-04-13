# -*- coding: utf-8 -*-
"""
unit tests for the Salt engines
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

import salt.config

# Import Salt Libs
import salt.engines as engines
import salt.utils.process

# Import 3rd-party libs
from salt.ext import six

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class EngineTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.engine.sqs_events
    """

    def setup_loader_modules(self):
        return {engines: {}}

    def test_engine_module(self):
        """
        Test
        """
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts["__role"] = "minion"
        mock_opts["engines"] = [
            {"test_one": {"engine_module": "test"}},
            {"test_two": {"engine_module": "test"}},
        ]

        process_manager = salt.utils.process.ProcessManager()
        with patch.dict(engines.__opts__, mock_opts):
            salt.engines.start_engines(mock_opts, process_manager)
            process_map = process_manager._process_map
            count = 0
            for proc in six.iterkeys(process_map):
                count += 1
                fun = process_map[proc]["Process"].fun

                # Ensure function is start from the test engine
                self.assertEqual(fun, "test.start")

            # Ensure there were two engine started
            self.assertEqual(count, len(mock_opts["engines"]))
