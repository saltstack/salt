'''
tests for host state
'''

# Import python libs
import os
#
# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon

HFILE = os.path.join(integration.TMP, 'hosts')

class HostTest(integration.ModuleCase):
    '''
    Validate the host state
    '''
    def test_present(self):
        '''
        host.present
        '''
        ret = self.run_state('host.present', name='spam.bacon', ip='10.10.10.10')
        result = self.state_result(ret)
        self.assertTrue(result)
        with open(HFILE) as fp_:
            self.assertIn('{0}\t\t{1}'.format(ip, name), fp_.read())

