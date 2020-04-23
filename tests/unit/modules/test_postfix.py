# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.modules.postfix as postfix

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PostfixTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.postfix
    """

    def setup_loader_modules(self):
        return {postfix: {}}

    def test_show_master(self):
        """
        Test for return a dict of active config values
        """
        with patch.object(postfix, "_parse_master", return_value=({"A": "a"}, ["b"])):
            self.assertDictEqual(postfix.show_master("path"), {"A": "a"})

    def test_set_master(self):
        """
        Test for set a single config value in the master.cf file
        """
        with patch.object(postfix, "_parse_master", return_value=({"A": "a"}, ["b"])):
            with patch.object(postfix, "_write_conf", return_value=None):
                self.assertTrue(postfix.set_master("a", "b"))

    def test_show_main(self):
        """
        Test for return a dict of active config values
        """
        with patch.object(postfix, "_parse_main", return_value=({"A": "a"}, ["b"])):
            self.assertDictEqual(postfix.show_main("path"), {"A": "a"})

    def test_set_main(self):
        """
        Test for set a single config value in the master.cf file
        """
        with patch.object(postfix, "_parse_main", return_value=({"A": "a"}, ["b"])):
            with patch.object(postfix, "_write_conf", return_value=None):
                self.assertTrue(postfix.set_main("key", "value"))

    def test_show_queue(self):
        """
        Test for show contents of the mail queue
        """
        with patch.dict(postfix.__salt__, {"cmd.run": MagicMock(return_value="A\nB")}):
            self.assertEqual(postfix.show_queue(), [])

    def test_delete(self):
        """
        Test for delete message(s) from the mail queue
        """
        with patch.object(postfix, "show_queue", return_value={}):
            self.assertDictEqual(
                postfix.delete("queue_id"),
                {"result": False, "message": "No message in queue with ID queue_id"},
            )

        with patch.dict(
            postfix.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
        ):
            self.assertDictEqual(
                postfix.delete("ALL"),
                {"result": True, "message": "Successfully removed all messages"},
            )

    def test_hold(self):
        """
        Test for set held message(s) in the mail queue to unheld
        """
        with patch.object(postfix, "show_queue", return_value={}):
            self.assertDictEqual(
                postfix.hold("queue_id"),
                {"result": False, "message": "No message in queue with ID queue_id"},
            )

        with patch.dict(
            postfix.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
        ):
            self.assertDictEqual(
                postfix.hold("ALL"),
                {"result": True, "message": "Successfully placed all messages on hold"},
            )

    def test_unhold(self):
        """
        Test for put message(s) on hold from the mail queue
        """
        with patch.object(postfix, "show_queue", return_value={}):
            self.assertDictEqual(
                postfix.unhold("queue_id"),
                {"result": False, "message": "No message in queue with ID queue_id"},
            )

        with patch.dict(
            postfix.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
        ):
            self.assertDictEqual(
                postfix.unhold("ALL"),
                {"result": True, "message": "Successfully set all message as unheld"},
            )

    def test_requeue(self):
        """
        Test for requeue message(s) in the mail queue
        """
        with patch.object(postfix, "show_queue", return_value={}):
            self.assertDictEqual(
                postfix.requeue("queue_id"),
                {"result": False, "message": "No message in queue with ID queue_id"},
            )

        with patch.dict(
            postfix.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
        ):
            self.assertDictEqual(
                postfix.requeue("ALL"),
                {"result": True, "message": "Successfully requeued all messages"},
            )
