# -*- coding: utf-8 -*-
'''
    tests.unit.modules.virtualenv_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

import sys

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import 3rd party libs
try:
    import virtualenv
except ImportError:
    # Let's create a fake virtualenv with what we need to run these tests
    import new
    virtualenv = new.module('virtualenv')
    virtualenv.__version__ = '1.9.1'
    sys.modules['virtualenv'] = virtualenv

try:
    from mock import MagicMock, patch
    has_mock = True
except ImportError:
    has_mock = False
    patch = lambda x: lambda y: None


# Import salt libs
from salt.modules import virtualenv_mod

virtualenv_mod.__salt__ = {'cmd.which_bin': lambda _: 'virtualenv'}


@skipIf(has_mock is False, 'mock python module is unavailable')
class VirtualenvTestCase(TestCase):

    def test_issue_6029_deprecated_distribute(self):
        VIRTUALENV_VERSION_INFO = virtualenv_mod.VIRTUALENV_VERSION_INFO

        virtualenv_mod.VIRTUALENV_VERSION_INFO = (1, 9, 1)
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})

        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create(
                '/tmp/foo', no_site_packages=True, distribute=True
            )
            mock.assert_called_once_with(
                'virtualenv --no-site-packages --distribute /tmp/foo',
                runas=None
            )

        virtualenv_mod.VIRTUALENV_VERSION_INFO = (1, 10)
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create(
                '/tmp/foo', no_site_packages=True, distribute=True
            )
            mock.assert_called_once_with(
                'virtualenv --no-site-packages /tmp/foo', runas=None
            )
        virtualenv_mod.VIRTUALENV_VERSION_INFO = VIRTUALENV_VERSION_INFO


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VirtualenvTestCase, needs_daemon=False)
