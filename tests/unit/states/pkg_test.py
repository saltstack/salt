# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Joe Julian <me@joejulian.name>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import pkg

pkg.__salt__ = {}
pkg.__opts__ = {'cachedir': '/tmp', 'test': True}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PkgTestCase(TestCase):
    '''
    Test cases for salt.states.pkg
    '''
    # 'update_packaging_site' function tests: 1

    def test_install_multiple_packages_already_installed(self):
        '''
        Test to execute latest
        '''
        name = "lot"
        pkgs = ['git', 'salt-zmq', 'vim']
        normalized_pkgs = {'vim': None, 'git': None, 'salt-zmq': None}

        ret = {'name': name,
               'result': True,
               'comment': 'All packages are up-to-date ({0}).'.format(", ".join(pkgs)),
               'changes': {}}

        mock_t = MagicMock(return_value=True)
        mock_pkg_version = MagicMock(
            return_value={
                'git': '2.9.3-1',
                'salt-zmq': '2016.3.2-1',
                'vim': '7.4.2143-1'})
        mock__repack_pkgs = MagicMock(return_value=normalized_pkgs)
        with patch.dict(pkg.__salt__, {'pkg.version': mock_pkg_version}):
            with patch.dict(pkg.__salt__, {'pkg.latest_version': mock_pkg_version}):
                with patch.object(pkg, '_repack_pkgs', mock__repack_pkgs):
                    self.assertDictEqual(pkg.latest(name, pkgs=pkgs), ret)

    def test_install_multiple_packages_not_installed(self):
        '''
        Test to execute latest
        '''
        name = "lot"
        pkgs = ['git', 'salt-zmq', 'vim']
        normalized_pkgs = {'vim': None, 'git': None, 'salt-zmq': None}

        ret = {
            'name': name,
            'result': None,
            'comment': 'The following packages are set to be installed/upgraded: ' +
                       'git, vim The following packages are already up-to-date: ' +
                       'salt-zmq (2016.3.2-1)',
            'changes': {}}

        mock_t = MagicMock(return_value=True)
        mock_pkg_version = MagicMock(
            return_value={'git': None, 'salt-zmq': '2016.3.2-1', 'vim': None})
        mock_pkg_latest_version = MagicMock(
            return_value={
                'git': '2.9.3-1',
                'salt-zmq': '2016.3.2-1',
                'vim': '7.4.2143-1'})
        mock_pkg_install = MagicMock(
            return_value={
                'git': {
                    'new': '2.9.3-1',
                    'old': None},
                'vim': {
                    'new': '7.4.2143-1',
                    'old': None}})
        mock__repack_pkgs = MagicMock(return_value=normalized_pkgs)
        with patch.dict(pkg.__salt__, {'pkg.version': mock_pkg_version}):
            with patch.dict(pkg.__salt__, {'pkg.latest_version': mock_pkg_latest_version}):
                with patch.dict(pkg.__salt__, {'pkg.install': mock_pkg_install}):
                    with patch.object(pkg, '_repack_pkgs', mock__repack_pkgs):
                        self.assertDictEqual(pkg.latest(name, pkgs=pkgs), ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(PkgTestCase, needs_daemon=False)
