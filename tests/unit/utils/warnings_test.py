# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    tests.unit.utils.warnings_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test ``salt.utils.warn_until`` and ``salt.utils.kwargs_warn_until``
'''

# Import python libs
import warnings

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch
ensure_in_syspath('../../')

# Import salt libs
from salt.utils import warn_until, kwargs_warn_until

@skipIf(NO_MOCK, NO_MOCK_REASON)
class WarnUntilTestCase(TestCase):

    @patch('salt.version')
    def test_warn_until_warning_raised(self, salt_version_mock):
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
                r'line number ([\d]+), is supposed to be shown until version '
                r'\'0.17\' is released. Current version is now \'0.17\'. Please '
                r'remove the warning.'):
            raise_warning()

        # Even though we're calling warn_until, we pass _dont_call_warnings
        # because we're only after the RuntimeError
        with self.assertRaisesRegexp(
                RuntimeError,
                r'The warning triggered on filename \'(.*)warnings_test.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'\'0.17\' is released. Current version is now \'0.17\'. Please '
                r'remove the warning.'):
            warn_until(
                (0, 17), 'Foo', _dont_call_warnings=True
            )

    @patch('salt.version')
    def test_kwargs_warn_until_warning_raised(self, salt_version_mock):
        # We *always* want *all* warnings thrown on this module
        warnings.filterwarnings('always', '', DeprecationWarning, __name__)

        # Define a salt version info
        salt_version_mock.__version_info__ = (0, 16)

        def raise_warning(**kwargs):
            kwargs_warn_until(
                kwargs,
                (0, 17),
            )

        # raise_warning({...}) should show warning until version info is >= (0, 17)
        with warnings.catch_warnings(record=True) as recorded_warnings:
            raise_warning(foo=42) # with a kwarg
            self.assertEqual(
                'The following parameter(s) have been deprecated and '
                'will be removed in 0.17: \'foo\'.',
                str(recorded_warnings[0].message)
            )
        # With no **kwargs, should not show warning until version info is >= (0, 17)
        with warnings.catch_warnings(record=True) as recorded_warnings:
            kwargs_warn_until(
                {},  # no kwargs
                (0, 17),
            )
            self.assertEqual(0, len(recorded_warnings))

        # Let's set version info to (0, 17), a RuntimeError should be raised
        # regardless of whether or not we pass any **kwargs.
        salt_version_mock.__version_info__ = (0, 17)
        with self.assertRaisesRegexp(
                RuntimeError,
                r'The warning triggered on filename \'(.*)warnings_test.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'\'0.17\' is released. Current version is now \'0.17\'. Please '
                r'remove the warning.'):
            raise_warning()  # no kwargs
        with self.assertRaisesRegexp(
                RuntimeError,
                r'The warning triggered on filename \'(.*)warnings_test.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'\'0.17\' is released. Current version is now \'0.17\'. Please '
                r'remove the warning.'):
            raise_warning(bar='baz', qux='quux')  # some kwargs


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WarnUntilTestCase, needs_daemon=False)
