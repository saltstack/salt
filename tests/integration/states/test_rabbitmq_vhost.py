# -*- coding: utf-8 -*-

'''
Tests for the rabbitmq state
'''
# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
import tests.integration as integration


class RabbitVHostTestCase(integration.ModuleCase,
                          integration.SaltReturnAssertsMixin):
    '''
    Validate the rabbitmq virtual host states.
    '''
    def setUp(self):
        super(RabbitVHostTestCase, self).setUp()
        rabbit_installed = self.run_function('cmd.has_exec', ['rabbitmqctl'])

        if not rabbit_installed:
            self.skipTest('rabbitmq-server not installed')
        if os.geteuid() != 0:
            self.skipTest('You must be root to run this test')

    def test_present(self):
        '''
        rabbitmq_vhost.present null_host
        '''
        ret = self.run_state(
            'rabbitmq_vhost.present', name='null_host', test=True
        )
        self.assertSaltFalseReturn(ret)

    def absent(self):
        '''
        rabbitmq_vhost.absent null_host
        '''
        ret = self.run_state(
            'rabbitmq_vhost.absent', name='null_host', test=True
        )
        self.assertSaltFalseReturn(ret)
