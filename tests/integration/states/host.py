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
    '''
    Validate the host state
    '''

    def setUp(self):
        shutil.copyfile(os.path.join(integration.FILES, 'hosts'), HFILE)
        super(HostTest, self).setUp()

    def tearDown(self):
        if os.path.exists(HFILE):
            os.remove(HFILE)
        super(HostTest, self).tearDown()

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
