from mock import Mock, patch

from saltunittest import TestCase, TestLoader, TextTestRunner

from salt.modules import postgres
postgres.__grains__ = None # in order to stub it w/patch below
postgres.__salt__ = None # in order to stub it w/patch below

SALT_STUB = {
    'config.option': Mock(),
    'cmd.run_all': Mock(),
}


class PostgresTestCase(TestCase):
    @patch.multiple(postgres, __grains__={ 'os_family': 'FreeBSD' })
    def test_get_runas_bsd(self):
        self.assertEqual('pgsql', postgres._get_runas())

    @patch.multiple(postgres, __grains__={ 'os_family': 'Linux' })
    def test_get_runas_other(self):
        self.assertEqual('postgres', postgres._get_runas())

    @patch.multiple(postgres, __grains__={ 'os_family': 'Linux' }, __salt__=SALT_STUB)
    def test_run_psql(self):
        postgres._run_psql('echo "hi"')
        cmd = SALT_STUB['cmd.run_all'] 

        self.assertEquals('postgres', cmd.call_args[1]['runas'])

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(PostgresTestCase)
    TextTestRunner(verbosity=1).run(tests)
