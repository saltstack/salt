# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.unit.utils.cloud_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt-cloud utilities module
'''

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
from salt.utils import cloud


class CloudUtilsTestCase(TestCase):

    def test_ssh_password_regex(self):
        '''Test matching ssh password patterns'''
        for pattern in ('Password for root@127.0.0.1:',
                        'root@127.0.0.1 Password:',
                        ' Password:'):
            self.assertNotEqual(
                cloud.SSH_PASSWORD_PROMP_RE.match(pattern), None
            )
            self.assertNotEqual(
                cloud.SSH_PASSWORD_PROMP_RE.match(pattern.lower()), None
            )
            self.assertNotEqual(
                cloud.SSH_PASSWORD_PROMP_RE.match(pattern.strip()), None
            )
            self.assertNotEqual(
                cloud.SSH_PASSWORD_PROMP_RE.match(pattern.lower().strip()), None
            )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CloudUtilsTestCase, needs_daemon=False)
