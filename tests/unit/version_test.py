# -*- coding: utf-8 -*-
'''
    tests.unit.version_test
    ~~~~~~~~~~~~~~~~~~~~~~~

    Test salt's regex git describe version parsing

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import re

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../')

# Import Salt libs
import salt.version


class VersionTestCase(TestCase):
    def test_git_describe_re(self):
        expect = (
            ('v0.12.0-19-g767d4f9', ('0', '12', '0', '19', 'g767d4f9')),
            ('v0.12.0-85-g2880105', ('0', '12', '0', '85', 'g2880105')),
            ('debian/0.11.1+ds-1-3-ga0afcbd', ('0', '11', '1', '3',
                                               'ga0afcbd')),
            ('0.12.1', ('0', '12', '1', None, None)),
            ('0.12.1', ('0', '12', '1', None, None)),
        )

        for vs, groups in expect:
            self.assertEqual(
                groups, re.search(salt.version.GIT_DESCRIBE_REGEX, vs).groups()
            )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VersionTestCase, needs_daemon=False)
