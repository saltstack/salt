# Import Salt Testing libs
import os
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class TestSyndic(integration.SyndicCase):
    '''
    Validate the syndic interface by testing the test module
    '''
    def test_config(self):
        syndic = integration.SYNDIC
        # id & pki dir are shared & so configured on the minion side
        self.assertEquals(syndic.opts['id'], 'minion')
        self.assertEquals(syndic.opts['pki_dir'], '/tmp/salttest/pki')
        # the rest is configured master side
        self.assertEquals(syndic.opts['master_uri'], 'tcp://127.0.0.1:54506')
        self.assertEquals(syndic.opts['master_port'], 54506)
        self.assertEquals(syndic.opts['master_ip'], '127.0.0.1')
        self.assertEquals(syndic.opts['master'], 'localhost')
        self.assertEquals(syndic.opts['sock_dir'], '/tmp/salttest/minion_sock')
        self.assertEquals(syndic.opts['cachedir'], '/tmp/salttest/cachedir')
        self.assertEquals(syndic.opts['log_file'], '/tmp/salttest/osyndic.log')
        self.assertEquals(syndic.opts['pidfile'], '/tmp/salttest/osyndic.pid')
        # Show that the options of localclient that repub to local master
        # are not merged with syndic ones
        self.assertEquals(
            syndic.opts['_master_conf_file'],
            os.path.join(integration.INTEGRATION_TEST_DIR, 'files', 'conf', 'minion'))
        self.assertEquals(syndic.opts['_minion_conf_file'], '/tmp/salt-tests-tmpdir/syndic.conf')

    def test_ping(self):
        '''
        test.ping
        '''
        self.assertTrue(self.run_function('test.ping'))

    def test_fib(self):
        '''
        test.fib
        '''
        self.assertEqual(
                self.run_function(
                    'test.fib',
                    ['40'],
                    )[0][-1],
                34
                )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestSyndic)
