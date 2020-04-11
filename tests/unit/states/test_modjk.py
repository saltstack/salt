# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.modjk as modjk
from salt.ext import six

# Import Salt Testing Libs
from tests.support.unit import TestCase

if six.PY2:
    LIST_NOT_STR = "workers should be a list not a <type 'unicode'>"
else:
    LIST_NOT_STR = "workers should be a list not a <class 'str'>"


class ModjkTestCase(TestCase):
    """
    Test cases for salt.states.modjk
    """

    # 'worker_stopped' function tests: 1

    def test_worker_stopped(self):
        """
        Test to stop all the workers in the modjk load balancer
        """
        name = "loadbalancer"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        ret.update({"comment": LIST_NOT_STR})
        self.assertDictEqual(modjk.worker_stopped(name, "app1"), ret)

    # 'worker_activated' function tests: 1

    def test_worker_activated(self):
        """
        Test to activate all the workers in the modjk load balancer
        """
        name = "loadbalancer"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        ret.update({"comment": LIST_NOT_STR})
        self.assertDictEqual(modjk.worker_activated(name, "app1"), ret)

    # 'worker_disabled' function tests: 1

    def test_worker_disabled(self):
        """
        Test to disable all the workers in the modjk load balancer
        """
        name = "loadbalancer"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        ret.update({"comment": LIST_NOT_STR})
        self.assertDictEqual(modjk.worker_disabled(name, "app1"), ret)

    # 'worker_recover' function tests: 1

    def test_worker_recover(self):
        """
        Test to recover all the workers in the modjk load balancer
        """
        name = "loadbalancer"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        ret.update({"comment": LIST_NOT_STR})
        self.assertDictEqual(modjk.worker_recover(name, "app1"), ret)
