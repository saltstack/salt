# -*- coding: utf-8 -*-

import os
import sys

from salt.cli.api import SaltAPI
from tests.support.helpers import slowTest
from tests.support.mock import patch
from tests.support.unit import TestCase


class SaltAPITestCase(TestCase):
    @slowTest
    def test_start_shutdown(self):
        api = SaltAPI()
        try:
            # testing environment will fail if we use default pidfile
            # overwrite sys.argv so salt-api does not use testing args
            with patch.object(
                sys, "argv", [sys.argv[0], "--pid-file", "salt-api-test.pid"]
            ):
                api.start()
                self.assertTrue(os.path.isfile("salt-api-test.pid"))
                os.remove("salt-api-test.pid")
        finally:
            self.assertRaises(SystemExit, api.shutdown)
