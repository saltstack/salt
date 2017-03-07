# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Late import so mock can do its job
import salt.states.gem as gem
gem.__salt__ = {}
gem.__opts__ = {'test': False}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestGemState(TestCase):

    def test_installed(self):
        gems = {'foo': ['1.0'], 'bar': ['2.0']}
        gem_list = MagicMock(return_value=gems)
        gem_install_succeeds = MagicMock(return_value=True)
        gem_install_fails = MagicMock(return_value=False)

        with patch.dict(gem.__salt__, {'gem.list': gem_list}):
            with patch.dict(gem.__salt__,
                            {'gem.install': gem_install_succeeds}):
                ret = gem.installed('foo')
                self.assertEqual(True, ret['result'])
                ret = gem.installed('quux')
                self.assertEqual(True, ret['result'])
                gem_install_succeeds.assert_called_once_with(
                    'quux', pre_releases=False, ruby=None, runas=None,
                    version=None, proxy=None, rdoc=False, source=None,
                    ri=False, gem_bin=None
                )

            with patch.dict(gem.__salt__,
                            {'gem.install': gem_install_fails}):
                ret = gem.installed('quux')
                self.assertEqual(False, ret['result'])
                gem_install_fails.assert_called_once_with(
                    'quux', pre_releases=False, ruby=None, runas=None,
                    version=None, proxy=None, rdoc=False, source=None,
                    ri=False, gem_bin=None
                )

    def test_removed(self):
        gems = ['foo', 'bar']
        gem_list = MagicMock(return_value=gems)
        gem_uninstall_succeeds = MagicMock(return_value=True)
        gem_uninstall_fails = MagicMock(return_value=False)
        with patch.dict(gem.__salt__, {'gem.list': gem_list}):
            with patch.dict(gem.__salt__,
                            {'gem.uninstall': gem_uninstall_succeeds}):
                ret = gem.removed('quux')
                self.assertEqual(True, ret['result'])
                ret = gem.removed('foo')
                self.assertEqual(True, ret['result'])
                gem_uninstall_succeeds.assert_called_once_with(
                    'foo', None, runas=None, gem_bin=None)

            with patch.dict(gem.__salt__,
                            {'gem.uninstall': gem_uninstall_fails}):
                ret = gem.removed('bar')
                self.assertEqual(False, ret['result'])
                gem_uninstall_fails.assert_called_once_with(
                    'bar', None, runas=None, gem_bin=None)

    def test_sources_add(self):
        gem_sources = ['http://foo', 'http://bar']
        gem_sources_list = MagicMock(return_value=gem_sources)
        gem_sources_add_succeeds = MagicMock(return_value=True)
        gem_sources_add_fails = MagicMock(return_value=False)
        with patch.dict(gem.__salt__, {'gem.sources_list': gem_sources_list}):
            with patch.dict(gem.__salt__, {'gem.sources_add': gem_sources_add_succeeds}):
                ret = gem.sources_add('http://foo')
                self.assertEqual(True, ret['result'])
                ret = gem.sources_add('http://fui')
                self.assertEqual(True, ret['result'])
                gem_sources_add_succeeds.assert_called_once_with(
                    source_uri='http://fui', ruby=None, runas=None)
            with patch.dict(gem.__salt__, {'gem.sources_add': gem_sources_add_fails}):
                ret = gem.sources_add('http://fui')
                self.assertEqual(False, ret['result'])
                gem_sources_add_fails.assert_called_once_with(
                    source_uri='http://fui', ruby=None, runas=None)

    def test_sources_remove(self):
        gem_sources = ['http://foo', 'http://bar']
        gem_sources_list = MagicMock(return_value=gem_sources)
        gem_sources_remove_succeeds = MagicMock(return_value=True)
        gem_sources_remove_fails = MagicMock(return_value=False)
        with patch.dict(gem.__salt__, {'gem.sources_list': gem_sources_list}):
            with patch.dict(gem.__salt__, {'gem.sources_remove': gem_sources_remove_succeeds}):
                ret = gem.sources_remove('http://fui')
                self.assertEqual(True, ret['result'])
                ret = gem.sources_remove('http://foo')
                self.assertEqual(True, ret['result'])
                gem_sources_remove_succeeds.assert_called_once_with(
                    source_uri='http://foo', ruby=None, runas=None)
            with patch.dict(gem.__salt__, {'gem.sources_remove': gem_sources_remove_fails}):
                ret = gem.sources_remove('http://bar')
                self.assertEqual(False, ret['result'])
                gem_sources_remove_fails.assert_called_once_with(
                    source_uri='http://bar', ruby=None, runas=None)
