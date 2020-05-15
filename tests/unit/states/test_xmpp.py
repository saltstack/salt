# -*- coding: utf-8 -*-
"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.xmpp as xmpp

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class XmppTestCase(TestCase, LoaderModuleMockMixin):
    """
        Validate the xmpp state
    """

    def setup_loader_modules(self):
        return {xmpp: {}}

    def test_send_msg(self):
        """
            Test to send a message to an XMPP user
        """
        ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}
        with patch.dict(xmpp.__opts__, {"test": True}):
            ret.update({"comment": "Need to send message to myaccount: salt"})
            self.assertDictEqual(
                xmpp.send_msg("salt", "myaccount", "salt@saltstack.com"), ret
            )

        with patch.dict(xmpp.__opts__, {"test": False}):
            mock = MagicMock(return_value=True)
            with patch.dict(
                xmpp.__salt__, {"xmpp.send_msg": mock, "xmpp.send_msg_multi": mock}
            ):
                ret.update(
                    {"result": True, "comment": "Sent message to myaccount: salt"}
                )
                self.assertDictEqual(
                    xmpp.send_msg("salt", "myaccount", "salt@saltstack.com"), ret
                )
