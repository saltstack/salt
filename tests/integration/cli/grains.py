# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Daniel Mizyrycki (mzdaniel@glidelink.net)`


    tests.integration.cli.grains
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test salt-ssh grains id work for localhost. (gh #16129)

    $ salt-ssh localhost grains.get id
    localhost:
        localhost
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import integration

# Import Salt Testing Libs
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


class SSHGrainsTest(integration.SSHCase):
    '''
    Test salt-ssh grains functionality
    Depend on proper environment set by integration.SSHCase class
    '''

    def test_grains_id(self):
        '''
        Test salt-ssh grains id work for localhost.
        '''
        cmd = self.run_function('grains.get', ['id'])
        self.assertEqual(cmd, 'localhost')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SSHGrainsTest)
