# Import python libs
import os

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


class TestWhich(TestCase):
    def test_salt_utils_which(self):
        '''
        Tests salt.utils.which function to ensure that it returns True as
        expected.
        '''
        self.assertTrue(salt.utils.which('sh'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestWhich, needs_daemon=False)
