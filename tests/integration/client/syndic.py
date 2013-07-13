# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class TestSyndic(integration.SyndicCase):
    '''
    Validate the syndic interface by testing the test module
    '''
    def test_config(self):
        # id & pki dir are shared & so configured on the minion side
        self.assertEquals(self._test_daemon.syndic.opts['id'], 'minion')
        self.assertEquals(self._test_daemon.syndic.opts['pki_dir'], '/tmp/salttest/pki')
        # the rest is configured master side
        self.assertEquals(self._test_daemon.syndic.opts['master_uri'], 'tcp://127.0.0.1:54506')
        self.assertEquals(self._test_daemon.syndic.opts['master_port'], 54506)
        self.assertEquals(self._test_daemon.syndic.opts['master_ip'], '127.0.0.1')
        self.assertEquals(self._test_daemon.syndic.opts['master'], 'localhost')
        self.assertEquals(self._test_daemon.syndic.opts['sock_dir'], '/tmp/salttest/.salt-unix')
        self.assertEquals(self._test_daemon.syndic.opts['cachedir'], '/tmp/salttest/cache')
        self.assertEquals(self._test_daemon.syndic.opts['log_file'], '/tmp/salttest/osyndic.log')
        self.assertEquals(self._test_daemon.syndic.opts['pidfile'], '/tmp/salttest/osyndic.pid')
        # Show that the options of localclient that repub to local master
        # are not merged with syndic ones
        self.assertEquals(self._test_daemon.syndic.lopts['id'], 'minion')
        self.assertEquals(self._test_daemon.syndic.lopts['pki_dir'], '/tmp/salttest/pki')
        self.assertEquals(self._test_daemon.syndic.lopts['sock_dir'], '/tmp/salttest/.salt-unix')
        # this test is pretty useless, as we connect directly to a socket
        self.assertEquals(self._test_daemon.syndic.lopts['master_port'], 64506)

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
