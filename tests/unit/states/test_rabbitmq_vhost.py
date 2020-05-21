# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.rabbitmq_vhost as rabbitmq_vhost

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class RabbitmqVhostTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.rabbitmq_vhost
    """

    def setup_loader_modules(self):
        return {rabbitmq_vhost: {}}

    # 'present' function tests: 1

    def test_present(self):
        """
        Test to ensure the RabbitMQ VHost exists.
        """
        name = "virtual_host"

        ret = {
            "name": name,
            "changes": {"new": "virtual_host", "old": ""},
            "result": None,
            "comment": "Virtual Host 'virtual_host' will be created.",
        }

        mock = MagicMock(return_value=False)
        with patch.dict(rabbitmq_vhost.__salt__, {"rabbitmq.vhost_exists": mock}):
            with patch.dict(rabbitmq_vhost.__opts__, {"test": True}):
                self.assertDictEqual(rabbitmq_vhost.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to ensure the named user is absent.
        """
        name = "myqueue"

        ret = {
            "name": name,
            "changes": {},
            "result": True,
            "comment": "Virtual Host '{0}' is not present.".format(name),
        }

        mock = MagicMock(return_value=False)
        with patch.dict(rabbitmq_vhost.__salt__, {"rabbitmq.vhost_exists": mock}):
            self.assertDictEqual(rabbitmq_vhost.absent(name), ret)
