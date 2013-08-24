# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

try:
    from mock import Mock, patch
    has_mock = True
except ImportError:
    has_mock = False
    patch = lambda x: lambda y: None

    def patchmultiple(x, __grains__, __salt__=None):
        return lambda y: None
    patch.multiple = patchmultiple

# Import salt libs
from salt.modules import postgres
postgres.__grains__ = None  # in order to stub it w/patch below
postgres.__salt__ = None  # in order to stub it w/patch below

if has_mock:
    SALT_STUB = {
        'config.option': Mock(),
        'cmd.run_all': Mock(),
        'file.chown': Mock(),
        'file.remove': Mock(),
    }
else:
    SALT_STUB = {}


@skipIf(has_mock is False, 'mock python module is unavailable')
class PostgresTestCase(TestCase):
    @patch.multiple(postgres,
                    __grains__={'os_family': 'Linux'},
                    __salt__=SALT_STUB)
    def test_run_psql(self):
        postgres._run_psql('echo "hi"')
        cmd = SALT_STUB['cmd.run_all']

        self.assertEquals('postgres', cmd.call_args[1]['runas'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PostgresTestCase, needs_daemon=False)
