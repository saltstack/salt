# -*- coding: utf-8 -*-

'''
Tests for the rabbitmq state
'''

# Import python libs
import os

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class RabbitUserTestCase(integration.ModuleCase,
                         integration.SaltReturnAssertsMixIn):
    '''
    Validate the rabbitmq user states.
    '''
    def setUp(self):
        super(RabbitUserTestCase, self).setUp()
        rabbit_installed = self.run_function('cmd.has_exec', ['rabbitmqctl'])

        if not rabbit_installed:
            self.skipTest('rabbitmq-server not installed')
        if os.geteuid() != 0:
            self.skipTest('You must be root to run this test')

    def test_present(self):
        '''
        rabbitmq_user.present null_name
        '''
        ret = self.run_state(
            'rabbitmq_user.present', name='null_name', test=True
        )
        self.assertSaltFalseReturn(ret)
        self.assertInSaltComment('User null_name is set to be created', ret)

    def absent(self):
        '''
        rabbitmq_user.absent null_name
        '''
        ret = self.run_state(
            'rabbitmq_user.absent', name='null_name', test=True
        )
        self.assertSaltFalseReturn(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RabbitUserTestCase)
