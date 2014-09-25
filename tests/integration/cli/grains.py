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
        ret = '{\n    "localhost": "localhost"\n}\n'
        cmd = self.run_ssh("grains.get id")
        self.assertEqual(cmd, ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SSHGrainsTest)
