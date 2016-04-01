# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath, requires_salt_modules

ensure_in_syspath('../../')

# Import salt libs
import integration


@skipIf(os.geteuid() != 0, 'You must be root to run this test')
@requires_salt_modules('rabbitmq')
class RabbitModuleTest(integration.ModuleCase):
    '''
    Validates the rabbitmqctl functions.
    To run these tests, you will need to be able to access the rabbitmqctl
    commands.
    '''
    def test_user_exists(self):
        '''
        Find out whether a user exists.
        '''
        ret = self.run_function('rabbitmq.user_exists', ['null_user'])
        self.assertEqual(ret, False)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RabbitModuleTest)
