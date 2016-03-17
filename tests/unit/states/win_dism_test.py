# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.states import win_dism as dism

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch
)

ensure_in_syspath('../../')

dism.__salt__ = {}


class DISMTestCase(TestCase):

    def test_install_capability(self):
        '''
            Test installing a capability with DISM
        '''
        expected = {
            'comment': "Capa2 was installed.\n",
            'changes': {'installed': 'Capa2'},
            'name': 'Capa2',
            'result': True
        }

        installed_mock = MagicMock(return_value=["Capa1"])
        install_mock = MagicMock(return_value={'retcode': 0})
        with patch.dict(dism.__salt__, {'dism.installed_capabilities': installed_mock,
                                        'dism.install_capability': install_mock}):
            out = dism.capability_installed('Capa2', 'somewhere', True)
            installed_mock.assert_called_once_with()
            install_mock.assert_called_once_with('Capa2', 'somewhere', True)
            self.assertEqual(out, expected)

    def test_install_capability_failure(self):
        '''
            Test installing a capability which fails with DISM
        '''
        expected = {
            'comment': "Capa2 was unable to be installed. Failed\n",
            'changes': {},
            'name': 'Capa2',
            'result': False
        }

        installed_mock = MagicMock(return_value=["Capa1"])
        install_mock = MagicMock(return_value={'retcode': 67, 'stdout': 'Failed'})
        with patch.dict(dism.__salt__, {'dism.installed_capabilities': installed_mock,
                                        'dism.install_capability': install_mock}):
            out = dism.capability_installed('Capa2', 'somewhere', True)
            installed_mock.assert_called_once_with()
            install_mock.assert_called_once_with('Capa2', 'somewhere', True)
            self.assertEqual(out, expected)

    def test_installed_capability(self):
        '''
            Test installing a capability already installed
        '''
        expected = {
            'comment': "Capa2 was already installed.\n",
            'changes': {},
            'name': 'Capa2',
            'result': True
        }

        installed_mock = MagicMock(return_value=["Capa1", "Capa2"])
        install_mock = MagicMock()
        with patch.dict(dism.__salt__, {'dism.installed_capabilities': installed_mock,
                                        'dism.install_capability': install_mock}):
            out = dism.capability_installed('Capa2', 'somewhere', True)
            installed_mock.assert_called_once_with()
            assert not install_mock.called
            self.assertEqual(out, expected)

    def test_install_feature(self):
        '''
            Test installing a feature with DISM
        '''
        expected = {
            'comment': "Feat1 was installed.\n",
            'changes': {'installed': 'Feat1'},
            'name': 'Feat1',
            'result': True
        }

        installed_mock = MagicMock(return_value=["Feat2"])
        install_mock = MagicMock(return_value={'retcode': 0})
        with patch.dict(dism.__salt__, {'dism.installed_features': installed_mock,
                                        'dism.install_feature': install_mock}):
            out = dism.feature_installed('Feat1', 'somewhere', True)
            installed_mock.assert_called_once_with()
            install_mock.assert_called_once_with('Feat1', 'somewhere', True)
            self.assertEqual(out, expected)

    def test_install_feature_failure(self):
        '''
            Test installing a feature which fails with DISM
        '''
        expected = {
            'comment': "Feat1 was unable to be installed. Failed\n",
            'changes': {},
            'name': 'Feat1',
            'result': False
        }

        installed_mock = MagicMock(return_value=["Feat3"])
        install_mock = MagicMock(return_value={'retcode': 67, 'stdout': 'Failed'})
        with patch.dict(dism.__salt__, {'dism.installed_features': installed_mock,
                                        'dism.install_feature': install_mock}):
            out = dism.feature_installed('Feat1', 'somewhere', True)
            installed_mock.assert_called_once_with()
            install_mock.assert_called_once_with('Feat1', 'somewhere', True)
            self.assertEqual(out, expected)

    def test_installed_feature(self):
        '''
            Test installing a feature already installed
        '''
        expected = {
            'comment': "Feat1 was already installed.\n",
            'changes': {},
            'name': 'Feat1',
            'result': True
        }

        installed_mock = MagicMock(return_value=["Feat1", "Feat2"])
        install_mock = MagicMock()
        with patch.dict(dism.__salt__, {'dism.installed_features': installed_mock,
                                        'dism.install_feature': install_mock}):
            out = dism.feature_installed('Feat1', 'somewhere', True)
            installed_mock.assert_called_once_with()
            assert not install_mock.called
            self.assertEqual(out, expected)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DISMTestCase, needs_daemon=False)
