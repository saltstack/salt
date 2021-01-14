# -*- coding: utf-8 -*-
"""
    :codeauthor: Alexander Pyatkin <asp@thexyz.net>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.webutil as htpasswd

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class HtpasswdTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.webutil
    """

    def setup_loader_modules(self):
        return {htpasswd: {"__opts__": {"test": False}}}

    def test_user_exists_already(self):
        """
        Test if it returns True when user already exists in htpasswd file
        """

        mock = MagicMock(return_value={"retcode": 0})

        with patch.dict(htpasswd.__salt__, {"file.grep": mock}):
            ret = htpasswd.user_exists("larry", "badpass", "/etc/httpd/htpasswd")
            expected = {
                "name": "larry",
                "result": True,
                "comment": "User already known",
                "changes": {},
            }
            self.assertEqual(ret, expected)

    def test_new_user_success(self):
        """
        Test if it returns True when new user is added to htpasswd file
        """

        mock_grep = MagicMock(return_value={"retcode": 1})
        mock_useradd = MagicMock(return_value={"retcode": 0, "stderr": "Success"})

        with patch.dict(
            htpasswd.__salt__, {"file.grep": mock_grep, "webutil.useradd": mock_useradd}
        ):
            ret = htpasswd.user_exists("larry", "badpass", "/etc/httpd/htpasswd")
            expected = {
                "name": "larry",
                "result": True,
                "comment": "Success",
                "changes": {"larry": True},
            }
            self.assertEqual(ret, expected)

    def test_new_user_error(self):
        """
        Test if it returns False when adding user to htpasswd failed
        """

        mock_grep = MagicMock(return_value={"retcode": 1})
        mock_useradd = MagicMock(return_value={"retcode": 1, "stderr": "Error"})

        with patch.dict(
            htpasswd.__salt__, {"file.grep": mock_grep, "webutil.useradd": mock_useradd}
        ):
            ret = htpasswd.user_exists("larry", "badpass", "/etc/httpd/htpasswd")
            expected = {
                "name": "larry",
                "result": False,
                "comment": "Error",
                "changes": {},
            }
            self.assertEqual(ret, expected)
