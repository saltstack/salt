# -*- coding: utf-8 -*-
"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.logadm as logadm

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class LogadmTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.logadm
    """

    def setup_loader_modules(self):
        return {logadm: {}}

    def test_show_conf(self):
        """
        Test for Show parsed configuration
        """
        with patch.object(logadm, "_parse_conf", return_value=True):
            self.assertTrue(logadm.show_conf("conf_file"))

    def test_rotate(self):
        """
        Test for Set up pattern for logging.
        """
        with patch.dict(
            logadm.__salt__,
            {"cmd.run_all": MagicMock(return_value={"retcode": 1, "stderr": "stderr"})},
        ):
            self.assertEqual(
                logadm.rotate("name"),
                {"Output": "stderr", "Error": "Failed in adding log"},
            )

        with patch.dict(
            logadm.__salt__,
            {"cmd.run_all": MagicMock(return_value={"retcode": 0, "stderr": "stderr"})},
        ):
            self.assertEqual(logadm.rotate("name"), {"Result": "Success"})

    def test_remove(self):
        """
        Test for Remove log pattern from logadm
        """
        with patch.dict(
            logadm.__salt__,
            {"cmd.run_all": MagicMock(return_value={"retcode": 1, "stderr": "stderr"})},
        ):
            self.assertEqual(
                logadm.remove("name"),
                {
                    "Output": "stderr",
                    "Error": "Failure in removing log. Possibly\
 already removed?",
                },
            )

        with patch.dict(
            logadm.__salt__,
            {"cmd.run_all": MagicMock(return_value={"retcode": 0, "stderr": "stderr"})},
        ):
            self.assertEqual(logadm.remove("name"), {"Result": "Success"})
