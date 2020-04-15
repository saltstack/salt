# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.rabbitmq_policy as rabbitmq_policy

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class RabbitmqPolicyTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.rabbitmq_policy
    """

    def setup_loader_modules(self):
        return {rabbitmq_policy: {}}

    # 'present' function tests: 1

    def test_present(self):
        """
        Test to ensure the RabbitMQ policy exists.
        """
        name = "HA"
        pattern = ".*"
        definition = '{"ha-mode":"all"}'

        ret = {"name": name, "changes": {}, "result": True, "comment": ""}

        mock = MagicMock(
            side_effect=[
                {
                    "/": {
                        name: {
                            "pattern": pattern,
                            "definition": definition,
                            "priority": 0,
                        }
                    }
                },
                {},
            ]
        )
        with patch.dict(rabbitmq_policy.__salt__, {"rabbitmq.list_policies": mock}):
            comt = "Policy / HA is already present"
            ret.update({"comment": comt})
            self.assertDictEqual(
                rabbitmq_policy.present(name, pattern, definition), ret
            )

            with patch.dict(rabbitmq_policy.__opts__, {"test": True}):
                comment = "Policy / HA is set to be created"
                changes = {"new": "HA", "old": {}}
                ret.update({"comment": comment, "result": None, "changes": changes})
                self.assertDictEqual(
                    rabbitmq_policy.present(name, pattern, definition), ret
                )

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to ensure the named policy is absent.
        """
        name = "HA"

        ret = {"name": name, "changes": {}, "result": True, "comment": ""}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(rabbitmq_policy.__salt__, {"rabbitmq.policy_exists": mock}):
            comment = "Policy '/ HA' is not present."
            ret.update({"comment": comment})
            self.assertDictEqual(rabbitmq_policy.absent(name), ret)

            with patch.dict(rabbitmq_policy.__opts__, {"test": True}):
                comment = "Policy '/ HA' will be removed."
                changes = {"new": "", "old": "HA"}
                ret.update({"comment": comment, "result": None, "changes": changes})
                self.assertDictEqual(rabbitmq_policy.absent(name), ret)
