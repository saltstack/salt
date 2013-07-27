# -*- coding: utf-8 -*-
'''
    tests.unit.modules.alternatives_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import alternatives

# Import 3rd party libs
try:
    from mock import MagicMock, patch
    HAS_MOCK = True
except ImportError:
    HAS_MOCK = False


alternatives.__salt__ = {}
alternatives.__grains__ = {'os_family': 'RedHat'}


@skipIf(HAS_MOCK is False, 'mock python module is unavailable')
class AlternativesTestCase(TestCase):

    def test_display(self):
        with patch.dict(alternatives.__grains__, {'os_family': 'RedHat'}):
            mock = MagicMock(return_value={'retcode': 0, 'stdout': 'salt'})
            with patch.dict(alternatives.__salt__, {'cmd.run_all': mock}):
                solution = alternatives.display('better-world')
                self.assertEqual('salt', solution)
                mock.assert_called_once_with(
                    'alternatives --display better-world'
                )

        with patch.dict(alternatives.__grains__, {'os_family': 'Ubuntu'}):
            mock = MagicMock(
                return_value={'retcode': 0, 'stdout': 'undoubtedly-salt'}
            )
            with patch.dict(alternatives.__salt__, {'cmd.run_all': mock}):
                solution = alternatives.display('better-world')
                self.assertEqual('undoubtedly-salt', solution)
                mock.assert_called_once_with(
                    'update-alternatives --display better-world'
                )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(AlternativesTestCase, needs_daemon=False)
