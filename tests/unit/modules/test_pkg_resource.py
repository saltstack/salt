# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import yaml

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils
import salt.modules.pkg_resource as pkg_resource
import salt.ext.six as six

# Globals
pkg_resource.__grains__ = {}
pkg_resource.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PkgresTestCase(TestCase):
    '''
    Test cases for salt.modules.pkg_resource
    '''
    def test_pack_sources(self):
        '''
            Test to accepts list of dicts (or a string representing a
            list of dicts) and packs the key/value pairs into a single dict.
        '''
        with patch.object(yaml,
                          'safe_load',
                          MagicMock(side_effect=yaml.parser.ParserError('f'))):
            with patch.dict(pkg_resource.__salt__,
                            {'pkg.normalize_name': MagicMock()}):
                self.assertDictEqual(pkg_resource.pack_sources('sources'), {})

                self.assertDictEqual(pkg_resource.pack_sources(['A', 'a']), {})

                self.assertTrue(pkg_resource.pack_sources([{'A': 'a'}]))

    def test_parse_targets(self):
        '''
            Test to parses the input to pkg.install and
            returns back the package(s) to be installed. Returns a
            list of packages, as well as a string noting whether the
            packages are to come from a repository or a binary package.
        '''
        with patch.dict(pkg_resource.__grains__, {'os': 'A'}):
            self.assertEqual(pkg_resource.parse_targets(pkgs='a',
                                                        sources='a'),
                             (None, None))

            with patch.object(pkg_resource, '_repack_pkgs',
                              return_value=False):
                self.assertEqual(pkg_resource.parse_targets(pkgs='a'),
                                 (None, None))

            with patch.object(pkg_resource, '_repack_pkgs',
                              return_value='A'):
                self.assertEqual(pkg_resource.parse_targets(pkgs='a'),
                                 ('A', 'repository'))

        with patch.dict(pkg_resource.__grains__, {'os': 'MacOS1'}):
            with patch.object(pkg_resource, 'pack_sources',
                              return_value=False):
                self.assertEqual(pkg_resource.parse_targets(sources='s'),
                                 (None, None))

            with patch.object(pkg_resource, 'pack_sources',
                              return_value={'A': '/a'}):
                with patch.dict(pkg_resource.__salt__,
                                {'config.valid_fileproto':
                                 MagicMock(return_value=False)}):
                    self.assertEqual(pkg_resource.parse_targets(sources='s'),
                                     (['/a'], 'file'))

            with patch.object(pkg_resource, 'pack_sources',
                              return_value={'A': 'a'}):
                with patch.dict(pkg_resource.__salt__,
                                {'config.valid_fileproto':
                                 MagicMock(return_value=False)}):
                    self.assertEqual(pkg_resource.parse_targets(name='n'),
                                     ({'n': None}, 'repository'))

                    self.assertEqual(pkg_resource.parse_targets(),
                                     (None, None))

    def test_version(self):
        '''
            Test to Common interface for obtaining the version
            of installed packages.
        '''
        with patch.object(salt.utils, 'is_true', return_value=True):
            mock = MagicMock(return_value={'A': 'B'})
            with patch.dict(pkg_resource.__salt__,
                            {'pkg.list_pkgs': mock}):
                self.assertEqual(pkg_resource.version('A'), 'B')

                self.assertDictEqual(pkg_resource.version(), {})

            mock = MagicMock(return_value={})
            with patch.dict(pkg_resource.__salt__, {'pkg.list_pkgs': mock}):
                with patch('builtins.next' if six.PY3 else '__builtin__.next') as mock_next:
                    mock_next.side_effect = StopIteration()
                    self.assertEqual(pkg_resource.version('A'), '')

    def test_add_pkg(self):
        '''
            Test to add a package to a dict of installed packages.
        '''
        self.assertIsNone(pkg_resource.add_pkg({'pkgs': []}, 'name', 'version'))

    def test_sort_pkglist(self):
        '''
            Test to accepts a dict obtained from pkg.list_pkgs() and sorts
            in place the list of versions for any packages that have multiple
            versions installed, so that two package lists can be compared
            to one another.
        '''
        self.assertIsNone(pkg_resource.sort_pkglist({}))

    def test_stringify(self):
        '''
            Test to takes a dict of package name/version information
            and joins each list of
            installed versions into a string.
        '''
        self.assertIsNone(pkg_resource.stringify({}))

    def test_version_clean(self):
        '''
            Test to clean the version string removing extra data.
        '''
        with patch.dict(pkg_resource.__salt__, {'pkg.version_clean':
                                                MagicMock(return_value='A')}):
            self.assertEqual(pkg_resource.version_clean('version'), 'A')

        self.assertEqual(pkg_resource.version_clean('v'), 'v')

    def test_check_extra_requirements(self):
        '''
            Test to check if the installed package already
            has the given requirements.
        '''
        with patch.dict(pkg_resource.__salt__, {'pkg.check_extra_requirements':
                                                MagicMock(return_value='A')}):
            self.assertEqual(pkg_resource.check_extra_requirements('a', 'b'),
                             'A')

        self.assertTrue(pkg_resource.check_extra_requirements('a', False))
