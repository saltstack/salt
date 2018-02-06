# -*- coding: utf-8 -*-
'''
    tests.unit.version_test
    ~~~~~~~~~~~~~~~~~~~~~~~

    These tests are copied from python's source `Lib/distutils/tests/test_version.py`
    Some new examples were added and some adjustments were made to run tests in python 2 and 3
'''
# pylint: disable=string-substitution-usage-error

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import sys
import warnings

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON

# Import Salt libs
import salt.version
import salt.utils.versions
from salt.utils.versions import LooseVersion, StrictVersion

# Import 3rd-party libs
from salt.ext import six

if six.PY2:
    cmp_method = '__cmp__'
else:
    cmp_method = '_cmp'


class VersionTestCase(TestCase):

    def test_prerelease(self):
        version = StrictVersion('1.2.3a1')
        self.assertEqual(version.version, (1, 2, 3))
        self.assertEqual(version.prerelease, ('a', 1))
        self.assertEqual(six.text_type(version), '1.2.3a1')

        version = StrictVersion('1.2.0')
        self.assertEqual(six.text_type(version), '1.2')

    def test_cmp_strict(self):
        versions = (('1.5.1', '1.5.2b2', -1),
                    ('161', '3.10a', ValueError),
                    ('8.02', '8.02', 0),
                    ('3.4j', '1996.07.12', ValueError),
                    ('3.2.pl0', '3.1.1.6', ValueError),
                    ('2g6', '11g', ValueError),
                    ('0.9', '2.2', -1),
                    ('1.2.1', '1.2', 1),
                    ('1.1', '1.2.2', -1),
                    ('1.2', '1.1', 1),
                    ('1.2.1', '1.2.2', -1),
                    ('1.2.2', '1.2', 1),
                    ('1.2', '1.2.2', -1),
                    ('0.4.0', '0.4', 0),
                    ('1.13++', '5.5.kw', ValueError),
                    # Added by us
                    ('1.1.1a1', '1.1.1', -1)
                    )

        for v1, v2, wanted in versions:
            try:
                res = getattr(StrictVersion(v1), cmp_method)(StrictVersion(v2))
            except ValueError:
                if wanted is ValueError:
                    continue
                else:
                    raise AssertionError(("cmp(%s, %s) "
                                          "shouldn't raise ValueError") % (v1, v2))
            self.assertEqual(res, wanted,
                             'cmp(%s, %s) should be %s, got %s' %
                             (v1, v2, wanted, res))

    def test_cmp(self):
        versions = (('1.5.1', '1.5.2b2', -1),
                    ('161', '3.10a', 1),
                    ('8.02', '8.02', 0),
                    ('3.4j', '1996.07.12', -1),
                    ('3.2.pl0', '3.1.1.6', 1),
                    ('2g6', '11g', -1),
                    ('0.960923', '2.2beta29', -1),
                    ('1.13++', '5.5.kw', -1),
                    # Added by us
                    ('3.10.0-514.el7', '3.10.0-514.6.1.el7', 1),
                    ('2.2.2', '2.12.1', -1)
                    )

        for v1, v2, wanted in versions:
            res = getattr(LooseVersion(v1), cmp_method)(LooseVersion(v2))
            self.assertEqual(res, wanted,
                             'cmp(%s, %s) should be %s, got %s' %
                             (v1, v2, wanted, res))


class VersionFuncsTestCase(TestCase):

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_compare(self):
        ret = salt.utils.versions.compare('1.0', '==', '1.0')
        self.assertTrue(ret)

        ret = salt.utils.versions.compare('1.0', '!=', '1.0')
        self.assertFalse(ret)

        with patch.object(salt.utils.versions, 'log') as log_mock:
            ret = salt.utils.versions.compare('1.0', 'HAH I AM NOT A COMP OPERATOR! I AM YOUR FATHER!', '1.0')
            self.assertTrue(log_mock.error.called)

    def test_kwargs_warn_until(self):
        # Test invalid version arg
        self.assertRaises(RuntimeError, salt.utils.versions.kwargs_warn_until, {}, [])

    def test_warn_until_warning_raised(self):
        # We *always* want *all* warnings thrown on this module
        warnings.filterwarnings('always', '', DeprecationWarning, __name__)

        def raise_warning(_version_info_=(0, 16, 0)):
            salt.utils.versions.warn_until(
                (0, 17), 'Deprecation Message!',
                _version_info_=_version_info_

            )

        def raise_named_version_warning(_version_info_=(0, 16, 0)):
            salt.utils.versions.warn_until(
                'Hydrogen', 'Deprecation Message!',
                _version_info_=_version_info_
            )

        # raise_warning should show warning until version info is >= (0, 17)
        with warnings.catch_warnings(record=True) as recorded_warnings:
            raise_warning()
            self.assertEqual(
                'Deprecation Message!', six.text_type(recorded_warnings[0].message)
            )

        # raise_warning should show warning until version info is >= (0, 17)
        with warnings.catch_warnings(record=True) as recorded_warnings:
            raise_named_version_warning()
            self.assertEqual(
                'Deprecation Message!', six.text_type(recorded_warnings[0].message)
            )

        # the deprecation warning is not issued because we passed
        # _dont_call_warning
        with warnings.catch_warnings(record=True) as recorded_warnings:
            salt.utils.versions.warn_until(
                (0, 17), 'Foo', _dont_call_warnings=True,
                _version_info_=(0, 16)
            )
            self.assertEqual(0, len(recorded_warnings))

        # Let's set version info to (0, 17), a RuntimeError should be raised
        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_versions.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'0.17.0 is released. Current version is now 0.17.0. '
                r'Please remove the warning.'):
            raise_warning(_version_info_=(0, 17, 0))

        # Let's set version info to (0, 17), a RuntimeError should be raised
        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_versions.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'(.*) is released. Current version is now '
                r'([\d.]+). Please remove the warning.'):
            raise_named_version_warning(_version_info_=(getattr(sys, 'maxint', None) or getattr(sys, 'maxsize'), 16, 0))

        # Even though we're calling warn_until, we pass _dont_call_warnings
        # because we're only after the RuntimeError
        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_versions.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'0.17.0 is released. Current version is now '
                r'(.*). Please remove the warning.'):
            salt.utils.versions.warn_until(
                (0, 17), 'Foo', _dont_call_warnings=True
            )

        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_versions.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'(.*) is released. Current version is now '
                r'(.*). Please remove the warning.'):
            salt.utils.versions.warn_until(
                'Hydrogen', 'Foo', _dont_call_warnings=True,
                _version_info_=(getattr(sys, 'maxint', None) or getattr(sys, 'maxsize'), 16, 0)
            )

        # version on the deprecation message gets properly formatted
        with warnings.catch_warnings(record=True) as recorded_warnings:
            vrs = salt.version.SaltStackVersion.from_name('Helium')
            salt.utils.versions.warn_until(
                'Helium', 'Deprecation Message until {version}!',
                _version_info_=(vrs.major - 1, 0)
            )
            self.assertEqual(
                'Deprecation Message until {0}!'.format(vrs.formatted_version),
                six.text_type(recorded_warnings[0].message)
            )

    def test_kwargs_warn_until_warning_raised(self):
        # We *always* want *all* warnings thrown on this module
        warnings.filterwarnings('always', '', DeprecationWarning, __name__)

        def raise_warning(**kwargs):
            _version_info_ = kwargs.pop('_version_info_', (0, 16, 0))
            salt.utils.versions.kwargs_warn_until(
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
                six.text_type(recorded_warnings[0].message)
            )
        # With no **kwargs, should not show warning until version info is >= (0, 17)
        with warnings.catch_warnings(record=True) as recorded_warnings:
            salt.utils.versions.kwargs_warn_until(
                {},  # no kwargs
                (0, 17),
                _version_info_=(0, 16, 0)
            )
            self.assertEqual(0, len(recorded_warnings))

        # Let's set version info to (0, 17), a RuntimeError should be raised
        # regardless of whether or not we pass any **kwargs.
        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_versions.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'0.17.0 is released. Current version is now 0.17.0. '
                r'Please remove the warning.'):
            raise_warning(_version_info_=(0, 17))  # no kwargs

        with self.assertRaisesRegex(
                RuntimeError,
                r'The warning triggered on filename \'(.*)test_versions.py\', '
                r'line number ([\d]+), is supposed to be shown until version '
                r'0.17.0 is released. Current version is now 0.17.0. '
                r'Please remove the warning.'):
            raise_warning(bar='baz', qux='quux', _version_info_=(0, 17))  # some kwargs
