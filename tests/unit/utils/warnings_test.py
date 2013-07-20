# -*- coding: utf-8 -*-
'''
    tests.unit.utils.warnings_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test ``salt.utils.warn_until``

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import warnings

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
from salt.utils import warn_until

# Import 3rd party libs
try:
    from mock import patch
    HAS_MOCK = True
except ImportError:
    HAS_MOCK = False


@skipIf(HAS_MOCK is False, 'mock python module is unavailable')
class WarnUntilTestCase(TestCase):

    @patch('salt.version')
    def test_warning_raised(self, salt_version_mock):
        # We *always* want *all* warnings thrown on this module
        warnings.filterwarnings('always', '', DeprecationWarning, __name__)

        # Define a salt version info
        salt_version_mock.__version_info__ = (0, 16)

        def raise_warning():
            warn_until(
                (0, 17), 'Deprecation Message!'
            )

        # raise_warning should show warning until version info is >= (0, 17)
        with warnings.catch_warnings(record=True) as recorded_warnings:
            raise_warning()
            self.assertEqual(
                'Deprecation Message!', str(recorded_warnings[0].message)
            )

        # the deprecation warning is not issued because we passed
        # _dont_call_warning
        with warnings.catch_warnings(record=True) as recorded_warnings:
            warn_until(
                (0, 17), 'Foo', _dont_call_warnings=True
            )
            self.assertEqual(0, len(recorded_warnings))

        # Let's set version info to (0, 17), a RuntimeError should be raised
        salt_version_mock.__version_info__ = (0, 17)
        with self.assertRaisesRegexp(
                RuntimeError,
                r'The warning triggered on filename \'(.*)warnings_test.py\', '
                r'line number ([\d]+), is supposed to be shown until salt '
                r'\'0.17\' is released. Salt version is now \'0.17\'. Please '
                r'remove the warning.'):
            raise_warning()

        # Even though we're calling warn_until, we pass _dont_call_warnings
        # because we're only after the RuntimeError
        with self.assertRaisesRegexp(
                RuntimeError,
                r'The warning triggered on filename \'(.*)warnings_test.py\', '
                r'line number ([\d]+), is supposed to be shown until salt '
                r'\'0.17\' is released. Salt version is now \'0.17\'. Please '
                r'remove the warning.'):
            warn_until(
                (0, 17), 'Foo', _dont_call_warnings=True
            )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WarnUntilTestCase, needs_daemon=False)
