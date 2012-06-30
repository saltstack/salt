'''
tests for host state
'''

# Import python libs
import os
import shutil
#
# Import salt libs
import integration

HFILE = os.path.join(integration.TMP, 'hosts')


class HostTest(integration.ModuleCase):
    def setUp(self):
        shutil.copy(os.path.join(
                integration.INTEGRATION_TEST_DIR, 'files', 'hosts'),
                    self.master_opts['hosts.file'])
        shutil.copy(os.path.join(
                integration.INTEGRATION_TEST_DIR, 'files', 'hosts'),
                    self.minion_opts['hosts.file'])

    def tearDown(self):
        os.remove(self.master_opts['hosts.file'])
        os.remove(self.minion_opts['hosts.file'])

    '''
    Validate the host state
    '''
    def test_present(self):
        '''
        host.present
        '''
        name = 'spam.bacon'
        ip = '10.10.10.10'
        ret = self.run_state('host.present', name=name, ip=ip)
        result = self.state_result(ret)
        self.assertTrue(result)
        with open(HFILE) as fp_:
            output = fp_.read()
            self.assertIn('{0}\t\t{1}'.format(ip, name), output)
