# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.modules.gem as gem


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestGemModule(TestCase, LoaderModuleMockMixin):

    loader_module = gem

    def test_gem(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(gem.__salt__,
                        {'rvm.is_installed': MagicMock(return_value=False),
                         'rbenv.is_installed': MagicMock(return_value=False),
                         'cmd.run_all': mock}):
            gem._gem(['install', 'rails'])
            mock.assert_called_once_with(
                ['gem', 'install', 'rails'],
                runas=None,
                python_shell=False
            )

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        rvm_mock = MagicMock()
        with patch.dict(gem.__salt__,
                        {'rvm.is_installed': rvm_mock,
                         'rbenv.is_installed': rvm_mock,
                         'cmd.run_all': mock}):
            gem._gem(['install', 'rails'], gem_bin='/usr/local/bin/gem')
            self.assertEqual(
                False,
                rvm_mock.called,
                'Should never call rvm.is_installed if gem_bin provided'
            )
            mock.assert_called_once_with(
                ['/usr/local/bin/gem', 'install', 'rails'],
                runas=None,
                python_shell=False
            )

        mock = MagicMock(return_value=None)
        with patch.dict(gem.__salt__,
                        {'rvm.is_installed': MagicMock(return_value=True),
                         'rbenv.is_installed': MagicMock(return_value=False),
                         'rvm.do': mock}):
            gem._gem(['install', 'rails'], ruby='1.9.3')
            mock.assert_called_once_with(
                '1.9.3',
                ['gem', 'install', 'rails'],
                runas=None
            )

        mock = MagicMock(return_value=None)
        with patch.dict(gem.__salt__,
                        {'rvm.is_installed': MagicMock(return_value=False),
                         'rbenv.is_installed': MagicMock(return_value=True),
                         'rbenv.do': mock}):
            gem._gem(['install', 'rails'])
            mock.assert_called_once_with(
                ['gem', 'install', 'rails'],
                runas=None
            )

    def test_install_pre(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(gem.__salt__,
                        {'rvm.is_installed': MagicMock(return_value=False),
                         'rbenv.is_installed': MagicMock(return_value=False),
                         'cmd.run_all': mock}):
            gem.install('rails', pre_releases=True)
            mock.assert_called_once_with(
                ['gem', 'install', 'rails', '--no-rdoc', '--no-ri', '--pre'],
                runas=None,
                python_shell=False
            )

    def test_list(self):
        output = '''
actionmailer (2.3.14)
actionpack (2.3.14)
activerecord (2.3.14)
activeresource (2.3.14)
activesupport (3.0.5, 2.3.14)
rake (0.9.2, 0.8.7)
responds_to_parent (1.0.20091013)
sass (3.1.15, 3.1.7)
'''
        mock = MagicMock(return_value=output)
        with patch.object(gem, '_gem', new=mock):
            self.assertEqual(
                {'actionmailer': ['2.3.14'],
                 'actionpack': ['2.3.14'],
                 'activerecord': ['2.3.14'],
                 'activeresource': ['2.3.14'],
                 'activesupport': ['3.0.5', '2.3.14'],
                 'rake': ['0.9.2', '0.8.7'],
                 'responds_to_parent': ['1.0.20091013'],
                 'sass': ['3.1.15', '3.1.7']},
                gem.list_())

    def test_list_upgrades(self):
        output = '''
arel (5.0.1.20140414130214 < 6.0.0)
rails (4.1.9 < 4.2.0)
rake (10.3.2 < 10.4.2)
'''
        mock = MagicMock(return_value=output)
        with patch.object(gem, '_gem', new=mock):
            self.assertEqual(
                {'arel': '6.0.0',
                 'rails': '4.2.0',
                 'rake': '10.4.2'}, gem.list_upgrades()
            )

    def test_sources_list(self):
        output = '''*** CURRENT SOURCES ***

http://rubygems.org/
'''
        mock = MagicMock(return_value=output)
        with patch.object(gem, '_gem', new=mock):
            self.assertEqual(
                ['http://rubygems.org/'], gem.sources_list())
