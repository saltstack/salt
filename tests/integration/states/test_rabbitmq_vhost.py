# -*- coding: utf-8 -*-

"""
Tests for the rabbitmq state
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import skip_if_not_root
from tests.support.mixins import SaltReturnAssertsMixin


@skip_if_not_root
class RabbitVHostTestCase(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the rabbitmq virtual host states.
    """

    def setUp(self):
        super(RabbitVHostTestCase, self).setUp()
        rabbit_installed = self.run_function("cmd.has_exec", ["rabbitmqctl"])

        if not rabbit_installed:
            self.skipTest("rabbitmq-server not installed")

    def test_present(self):
        """
        rabbitmq_vhost.present null_host
        """
        ret = self.run_state("rabbitmq_vhost.present", name="null_host", test=True)
        self.assertSaltFalseReturn(ret)

    def absent(self):
        """
        rabbitmq_vhost.absent null_host
        """
        ret = self.run_state("rabbitmq_vhost.absent", name="null_host", test=True)
        self.assertSaltFalseReturn(ret)
