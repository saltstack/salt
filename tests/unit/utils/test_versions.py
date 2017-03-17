# -*- coding: utf-8 -*-
'''
    tests.unit.version_test
    ~~~~~~~~~~~~~~~~~~~~~~~

    These tests are copied from python's source `Lib/distutils/tests/test_version.py`
    Some new examples were added and some adjustments were made to run tests in python 2 and 3
'''
# pylint: disable=string-substitution-usage-error

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import Salt libs
from salt.utils.versions import LooseVersion, StrictVersion

# Import 3rd-party libs
import salt.ext.six as six

if six.PY2:
    cmp_method = '__cmp__'
else:
    cmp_method = '_cmp'


class VersionTestCase(TestCase):

    def test_prerelease(self):
        version = StrictVersion('1.2.3a1')
        self.assertEqual(version.version, (1, 2, 3))
        self.assertEqual(version.prerelease, ('a', 1))
        self.assertEqual(str(version), '1.2.3a1')

        version = StrictVersion('1.2.0')
        self.assertEqual(str(version), '1.2')

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
