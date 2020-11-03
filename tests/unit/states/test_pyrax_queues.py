# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.pyrax_queues as pyrax_queues

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PyraxQueuesTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.pyrax_queues
    """

    def setup_loader_modules(self):
        return {pyrax_queues: {}}

    # 'present' function tests: 1

    def test_present(self):
        """
        Test to ensure the RackSpace queue exists.
        """
        name = "myqueue"
        provider = "my-pyrax"

        ret = {"name": name, "changes": {}, "result": True, "comment": ""}

        mock_dct = MagicMock(
            side_effect=[
                {provider: {"salt": True}},
                {provider: {"salt": False}},
                {provider: {"salt": False}},
                False,
            ]
        )
        with patch.dict(pyrax_queues.__salt__, {"cloud.action": mock_dct}):
            comt = "{0} present.".format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(pyrax_queues.present(name, provider), ret)

            with patch.dict(pyrax_queues.__opts__, {"test": True}):
                comt = "Rackspace queue myqueue is set to be created."
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(pyrax_queues.present(name, provider), ret)

            with patch.dict(pyrax_queues.__opts__, {"test": False}):
                comt = "Failed to create myqueue Rackspace queue."
                ret.update({"comment": comt, "result": False})
                self.assertDictEqual(pyrax_queues.present(name, provider), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to ensure the named Rackspace queue is deleted.
        """
        name = "myqueue"
        provider = "my-pyrax"

        ret = {"name": name, "changes": {}, "result": True, "comment": ""}

        mock_dct = MagicMock(
            side_effect=[{provider: {"salt": False}}, {provider: {"salt": True}}]
        )
        with patch.dict(pyrax_queues.__salt__, {"cloud.action": mock_dct}):
            comt = "myqueue does not exist."
            ret.update({"comment": comt})
            self.assertDictEqual(pyrax_queues.absent(name, provider), ret)

            with patch.dict(pyrax_queues.__opts__, {"test": True}):
                comt = "Rackspace queue myqueue is set to be removed."
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(pyrax_queues.absent(name, provider), ret)
