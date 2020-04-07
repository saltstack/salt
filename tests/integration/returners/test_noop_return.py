# -*- coding: utf-8 -*-
"""
    tests.integration.returners.test_noop_return
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This test module is meant to cover the issue being fixed by:

        https://github.com/saltstack/salt/pull/54731
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import 3rd-party tests
import salt.ext.six as six

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@skipIf(six.PY3, "Runtest Log Hander Disabled for PY3, #41836")
class TestEventReturn(ModuleCase):
    def test_noop_return(self):
        with TstSuiteLoggingHandler(
            format="%(message)s", level=logging.DEBUG
        ) as handler:
            self.run_function("test.ping")
            assert (
                any("NOOP_RETURN" in s for s in handler.messages) is True
            ), "NOOP_RETURN not found in log messages"
