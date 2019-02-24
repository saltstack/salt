# -*- coding: utf-8 -*-
'''
    :codeauthor: Marek Marczykowski-Górecki <marmarek@invisiblethingslab.com>
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.pkgrepo as pkgrepo


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PkgrepoTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.pkgrepo
    '''
    def setup_loader_modules(self):
        return {pkgrepo: {'__opts__': {'test': False},
                          '__env__': 'base'}}

    def setUp(self):
        super(PkgrepoTestCase, self).setUp()
        self.context_path = patch(__name__ + '.__context__', create=True)
        self.context_path.start()

    def tearDown(self):
        self.context_path.stop()
        super(PkgrepoTestCase, self).tearDown()

    def test_pkgrepo_managed_Ubuntu_new(self):
        with patch.dict(pkgrepo.__grains__,
                        {'os': 'Ubuntu',
                         'os_family': 'Debian'}):
            repo = 'deb http://archive.ubuntu.com/ubuntu artful-backports main'
            mod_repo = MagicMock()
            get_repo = MagicMock(side_effect=[
                    None, {'uri': repo, 'disabled': False}])
            ping = MagicMock(__module__=__name__)
            with patch.dict(pkgrepo.__salt__,
                            {'pkg.get_repo': get_repo,
                             'pkg.mod_repo': mod_repo,
                             'test.ping': ping}):
                ret = pkgrepo.managed(repo)
                self.assertTrue(ret['result'])
                self.assertDictEqual(ret['changes'], {'repo': repo})
                mod_repo.assert_called_once_with(repo, disabled=False, saltenv='base')

    def test_pkgrepo_managed_Ubuntu_existing(self):
        with patch.dict(pkgrepo.__grains__,
                        {'os': 'Ubuntu',
                         'os_family': 'Debian'}):
            repo = 'deb http://archive.ubuntu.com/ubuntu artful-backports main'
            mod_repo = MagicMock()
            get_repo = MagicMock(side_effect=[
                    {'uri': repo, 'disabled': True},
                    {'uri': repo, 'disabled': False}])
            ping = MagicMock(__module__=__name__)
            with patch.dict(pkgrepo.__salt__,
                            {'pkg.get_repo': get_repo,
                             'pkg.mod_repo': mod_repo,
                             'test.ping': ping}):
                ret = pkgrepo.managed(repo)
                self.assertTrue(ret['result'])
                self.assertDictEqual(ret['changes'],
                        {'disabled': {'new': False, 'old': True}})
                mod_repo.assert_called_once_with(repo, disabled=False, saltenv='base')

    def test_pkgrepo_managed_Debian_new(self):
        with patch.dict(pkgrepo.__grains__,
                        {'os': 'Debian',
                         'os_family': 'Debian'}):
            repo = 'deb http://deb.debian.org/debian stretch-backports main'
            mod_repo = MagicMock()
            get_repo = MagicMock(side_effect=[
                    None, {'uri': repo, 'disabled': False}])
            ping = MagicMock(__module__=__name__)
            with patch.dict(pkgrepo.__salt__,
                            {'pkg.get_repo': get_repo,
                             'pkg.mod_repo': mod_repo,
                             'test.ping': ping}):
                ret = pkgrepo.managed(repo)
                self.assertTrue(ret['result'])
                self.assertDictEqual(ret['changes'], {'repo': repo})
                mod_repo.assert_called_once_with(repo, disabled=False, saltenv='base')

    def test_pkgrepo_managed_Debian_existing(self):
        with patch.dict(pkgrepo.__grains__,
                        {'os': 'Debian',
                         'os_family': 'Debian'}):
            repo = 'deb http://deb.debian.org/debian stretch-backports main'
            mod_repo = MagicMock()
            get_repo = MagicMock(side_effect=[
                    {'uri': repo, 'disabled': True},
                    {'uri': repo, 'disabled': False}])
            ping = MagicMock(__module__=__name__)
            with patch.dict(pkgrepo.__salt__,
                            {'pkg.get_repo': get_repo,
                             'pkg.mod_repo': mod_repo,
                             'test.ping': ping}):
                ret = pkgrepo.managed(repo)
                self.assertTrue(ret['result'])
                self.assertDictEqual(ret['changes'],
                        {'disabled': {'new': False, 'old': True}})
                mod_repo.assert_called_once_with(repo, disabled=False, saltenv='base')
