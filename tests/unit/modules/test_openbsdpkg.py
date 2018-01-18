# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Eric Radman <ericshane@eradman.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    call,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.openbsdpkg as openbsdpkg


@skipIf(NO_MOCK, NO_MOCK_REASON)
class OpenbsdpkgTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.openbsdpkg
    '''
    def setup_loader_modules(self):
        return {openbsdpkg: {}}

    def test_list_pkgs(self):
        '''
        Test for listing installed packages.
        '''
        def _add_data(data, key, value):
            data[key] = value

        pkg_info_out = [
            'png-1.6.23',
            'vim-7.4.1467p1-gtk2',  # vim--gtk2
            'ruby-2.3.1p1'  # ruby%2.3
        ]
        run_stdout_mock = MagicMock(return_value='\n'.join(pkg_info_out))
        patches = {
            'cmd.run_stdout': run_stdout_mock,
            'pkg_resource.add_pkg': _add_data,
            'pkg_resource.sort_pkglist': MagicMock(),
            'pkg_resource.stringify': MagicMock(),
        }
        with patch.dict(openbsdpkg.__salt__, patches):
            pkgs = openbsdpkg.list_pkgs()
            self.assertDictEqual(pkgs, {
                'png': '1.6.23',
                'vim--gtk2': '7.4.1467p1',
                'ruby': '2.3.1p1'})
        run_stdout_mock.assert_called_once_with('pkg_info -q -a',
                                                output_loglevel='trace')

    def test_install_pkgs(self):
        '''
        Test package install behavior for the following conditions:
        - only base package name is given ('png')
        - a flavor is specified ('vim--gtk2')
        - a branch is specified ('ruby%2.3')
        '''
        class ListPackages(object):
            def __init__(self):
                self._iteration = 0

            def __call__(self):
                pkg_lists = [
                     {'vim': '7.4.1467p1-gtk2'},
                     {'png': '1.6.23', 'vim': '7.4.1467p1-gtk2', 'ruby': '2.3.1p1'}
                ]
                pkgs = pkg_lists[self._iteration]
                self._iteration += 1
                return pkgs

        parsed_targets = (
            {'vim--gtk2': None, 'png': None, 'ruby%2.3': None},
            "repository"
        )
        cmd_out = {
            'retcode': 0,
            'stdout': 'quirks-2.241 signed on 2016-07-26T16:56:10Z',
            'stderr': ''
        }
        run_all_mock = MagicMock(return_value=cmd_out)
        patches = {
            'cmd.run_all': run_all_mock,
            'pkg_resource.parse_targets': MagicMock(return_value=parsed_targets),
            'pkg_resource.stringify': MagicMock(),
            'pkg_resource.sort_pkglist': MagicMock(),
        }

        with patch.dict(openbsdpkg.__salt__, patches):
            with patch('salt.modules.openbsdpkg.list_pkgs', ListPackages()):
                added = openbsdpkg.install()
                expected = {
                    'png': {'new': '1.6.23', 'old': ''},
                    'ruby': {'new': '2.3.1p1', 'old': ''}
                }
                self.assertDictEqual(added, expected)
        expected_calls = [
            call('pkg_add -x -I png--%', output_loglevel='trace', python_shell=False),
            call('pkg_add -x -I ruby--%2.3', output_loglevel='trace', python_shell=False),
            call('pkg_add -x -I vim--gtk2%', output_loglevel='trace', python_shell=False),
        ]
        run_all_mock.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(run_all_mock.call_count, 3)
