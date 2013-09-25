# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.

    tests.unit.version_test
    ~~~~~~~~~~~~~~~~~~~~~~~

    Test salt's regex git describe version parsing
'''

# Import python libs
import re

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../')

# Import Salt libs
from salt.version import SaltStackVersion


class VersionTestCase(TestCase):
    def test_version_parsing(self):
        strip_initial_non_numbers_regex = re.compile(r'(?:[^\d]+)?(?P<vs>.*)')
        expect = (
            ('v0.12.0-19-g767d4f9', (0, 12, 0, 0, 19, 'g767d4f9'), None),
            ('v0.12.0-85-g2880105', (0, 12, 0, 0, 85, 'g2880105'), None),
            ('debian/0.11.1+ds-1-3-ga0afcbd',
             (0, 11, 1, 0, 3, 'ga0afcbd'), '0.11.1-3-ga0afcbd'),
            ('0.12.1', (0, 12, 1, 0, 0, None), None),
            ('0.12.1', (0, 12, 1, 0, 0, None), None),
            ('0.17.0rc1', (0, 17, 0, 1, 0, None), None),
            ('v0.17.0rc1-1-g52ebdfd', (0, 17, 0, 1, 1, 'g52ebdfd'), None),

        )

        for vs, full_info, version in expect:
            saltstack_version = SaltStackVersion.parse(vs)
            self.assertEqual(
                saltstack_version.full_info, full_info
            )
            if version is None:
                version = \
                    strip_initial_non_numbers_regex.search(vs).group('vs')

            self.assertEqual(saltstack_version.string, version)

    def test_version_comparison(self):
        examples = (
            ('debian/0.11.1+ds-1-3-ga0afcbd', '0.11.1+ds-2'),
            ('v0.12.0-85-g2880105', 'v0.12.0-19-g767d4f9'),
            ('v0.17.0rc1-1-g52ebdfd', '0.17.0rc1'),
            ('v0.17.0', 'v0.17.0rc1')
        )
        for v1, v2 in examples:
            self.assertTrue(SaltStackVersion.parse(v1) > v2)
            self.assertTrue(SaltStackVersion.parse(v2) < v1)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VersionTestCase, needs_daemon=False)
