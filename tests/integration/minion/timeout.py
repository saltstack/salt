# -*- coding: utf-8 -*-
'''
Tests for various minion timeouts
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import integration
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../')


class MinionTimeoutTestCase(integration.ShellCase):
    '''
    Test minion timing functions
    '''
    def test_long_running_job(self):
        '''
        Test that we will wait longer than the job timeout for a minion to
        return.
        '''
        # Launch the command
        sleep_length = 30
        ret = self.run_salt('minion test.sleep {0}'.format(sleep_length), timeout=45)
        self.assertTrue(isinstance(ret, list), 'Return is not a list. Minion'
                ' may have returned error: {0}'.format(ret))
        self.assertTrue('True' in ret[1], 'Minion did not return True after '
                '{0} seconds.'.format(sleep_length))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MinionTimeoutTestCase, needs_daemon=True)
