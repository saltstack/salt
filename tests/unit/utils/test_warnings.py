# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.utils.test_warnings
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test ``salt.utils.warn_until`` and ``salt.utils.kwargs_warn_until``
'''

# Import python libs
from __future__ import absolute_import
import sys
import warnings

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import salt libs
from salt.utils import warn_until, kwargs_warn_until
from salt.version import SaltStackVersion


class WarnUntilTestCase(TestCase):

    def test_warn_until_warning_raised(self):
        # We *always* want *all* warnings thrown on this module
        warnings.filterwarnings('always', '', DeprecationWarning, __name__)

        def raise_warning(_version_info_=(0, 16, 0)):
            warn_until(
                (0, 17), 'Deprecation Message!',
                _version_info_=_version_info_

            )

        def raise_named_version_warning(_version_info_=(0, 16, 0)):
            warn_until(
                'Hydrogen', 'Deprecation Message!',
                _version_info_=_version_info_
            )

        # raise_warning should show warning until version info is >= (0, 17)
        with warnings.catch_warnings(record=True) as recorded_warnings:
            raise_warning()
            self.assertEqual(
                'Deprecation Message!', str(recorded_warnings[0].message)
            )

        # raise_warning should show warning until version info is >= (0, 17)
        with warnings.catch_warnings(record=True) as recorded_warnings:
            raise_named_version_warning()
            self.assertEqual(
                'Deprecation Message!', str(recorded_warnings[0].message)
            )

        # the deprecation warning is not issued because we passed
        # _dont_call_warning
        with warnings.catch_warnings(record=True) as recorded_warnings:
            warn_until(
                (0, 17), 'Foo', _dont_call_warnings=True,
                _version_info_=(0, 16)
            )
            self.assertEqual(0, len(recorded_warnings))

        # Let's set version info to (0, 17), a RuntimeError should be raised
        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_warnings.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'0.17.0 is released. Current version is now 0.17.0. '
                r'Please remove the warning.'):
            raise_warning(_version_info_=(0, 17, 0))

        # Let's set version info to (0, 17), a RuntimeError should be raised
        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_warnings.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'(.*) is released. Current version is now '
                r'([\d.]+). Please remove the warning.'):
            raise_named_version_warning(_version_info_=(getattr(sys, 'maxint', None) or getattr(sys, 'maxsize'), 16, 0))

        # Even though we're calling warn_until, we pass _dont_call_warnings
        # because we're only after the RuntimeError
        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_warnings.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'0.17.0 is released. Current version is now '
                r'(.*). Please remove the warning.'):
            warn_until(
                (0, 17), 'Foo', _dont_call_warnings=True
            )

        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_warnings.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'(.*) is released. Current version is now '
                r'(.*). Please remove the warning.'):
            warn_until(
                'Hydrogen', 'Foo', _dont_call_warnings=True,
                _version_info_=(getattr(sys, 'maxint', None) or getattr(sys, 'maxsize'), 16, 0)
            )

        # version on the deprecation message gets properly formatted
        with warnings.catch_warnings(record=True) as recorded_warnings:
            vrs = SaltStackVersion.from_name('Helium')
            warn_until(
                'Helium', 'Deprecation Message until {version}!',
                _version_info_=(vrs.major - 1, 0)
            )
            self.assertEqual(
                'Deprecation Message until {0}!'.format(vrs.formatted_version),
                str(recorded_warnings[0].message)
            )

    def test_kwargs_warn_until_warning_raised(self):
        # We *always* want *all* warnings thrown on this module
        warnings.filterwarnings('always', '', DeprecationWarning, __name__)

        def raise_warning(**kwargs):
            _version_info_ = kwargs.pop('_version_info_', (0, 16, 0))
            kwargs_warn_until(
                kwargs,
                (0, 17),
                _version_info_=_version_info_
            )

        # raise_warning({...}) should show warning until version info is >= (0, 17)
        with warnings.catch_warnings(record=True) as recorded_warnings:
            raise_warning(foo=42)  # with a kwarg
            self.assertEqual(
                'The following parameter(s) have been deprecated and '
                'will be removed in \'0.17.0\': \'foo\'.',
                str(recorded_warnings[0].message)
            )
        # With no **kwargs, should not show warning until version info is >= (0, 17)
        with warnings.catch_warnings(record=True) as recorded_warnings:
            kwargs_warn_until(
                {},  # no kwargs
                (0, 17),
                _version_info_=(0, 16, 0)
            )
            self.assertEqual(0, len(recorded_warnings))

        # Let's set version info to (0, 17), a RuntimeError should be raised
        # regardless of whether or not we pass any **kwargs.
        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_warnings.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'0.17.0 is released. Current version is now 0.17.0. '
                r'Please remove the warning.'):
            raise_warning(_version_info_=(0, 17))  # no kwargs

        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_warnings.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'0.17.0 is released. Current version is now 0.17.0. '
                r'Please remove the warning.'):
            raise_warning(bar='baz', qux='quux', _version_info_=(0, 17))  # some kwargs
