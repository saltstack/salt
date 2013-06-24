'''
tests for host state
'''

# Import python libs
import os
import shutil

# Import salt libs
try:
    import integration
except ImportError:
    if __name__ == '__main__':
        import sys
        sys.path.insert(
            0, os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '../../'
                )
            )
        )
    import integration
import salt.utils

HFILE = os.path.join(integration.TMP, 'hosts')


class HostTest(integration.ModuleCase, integration.SaltReturnAssertsMixIn):
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
        self.assertSaltTrueReturn(ret)
        with salt.utils.fopen(HFILE) as fp_:
            output = fp_.read()
            self.assertIn('{0}\t\t{1}'.format(ip, name), output)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(HostTest)
