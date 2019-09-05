# -*- coding: utf-8 -*-
'''
    :synopsis: Unit Tests for Aptly module 'module.aptly'
    :platform: Linux
    :maturity: develop
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import copy

# Import Salt Libs
from salt.utils.dictupdate import merge_recurse
import salt.modules.aptly as aptly

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)


CONFIG = '''
{
    "rootDir": "/var/aptly/.aptly",
    "downloadConcurrency": 4,
    "downloadSpeedLimit": 0,
    "architectures": [],
    "dependencyFollowSuggests": false,
    "dependencyFollowRecommends": false,
    "dependencyFollowAllVariants": false,
    "dependencyFollowSource": false,
    "dependencyVerboseResolve": false,
    "gpgDisableSign": false,
    "gpgDisableVerify": false,
    "gpgProvider": "gpg",
    "downloadSourcePackages": false,
    "skipLegacyPool": false,
    "ppaDistributorID": "Test PPA",
    "ppaCodename": "",
    "skipContentsPublishing": false,
    "FileSystemPublishEndpoints": {},
    "S3PublishEndpoints": {},
    "SwiftPublishEndpoints": {}
}
'''

UNPARSED_REPO = '''
Name: devtest
Comment: Packages for the devtest project
Default Distribution: xenial
Default Component: main
Number of packages: 3
'''

UNPARSED_REPO_WITH_PACKAGES = '''
Name: devtest
Comment: Packages for the devtest project
Default Distribution: xenial
Default Component: main
Number of packages: 3
Packages:
  libdevtest-2019.1.1-1.xenial_amd64
  devtest-common-2019.1.1-1.xenial_amd64
  devtest-http-2019.1.1-1.xenial_amd64
'''

REPO = {
    'comment': 'Packages for the devtest project',
    'default_component': 'main',
    'default_distribution': 'xenial',
    'name': 'devtest',
    'number_of_packages': 3
}

REPO_WITH_PACKAGES = merge_recurse(REPO, {
    'packages': [
        'libdevtest-2019.1.1-1.xenial_amd64',
        'devtest-common-2019.1.1-1.xenial_amd64',
        'devtest-http-2019.1.1-1.xenial_amd64'
    ]
})


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AptlyTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.aptly
    '''
    def setup_loader_modules(self):
        return {aptly: {}}

    def test_get_config(self):
        '''
        Test - Get the configuration data.
        '''
        with patch.dict(aptly.__salt__), \
            patch('salt.modules.aptly._cmd_run',
                  MagicMock(return_value=CONFIG)), \
            patch('salt.modules.aptly._validate_config',
                  MagicMock(return_value=None)):
            self.assertIsInstance(aptly.get_config(), dict)

    def test_get_config_failed(self):
        '''
        Test - Get invalid configuration data.
        '''
        error_text = "ERROR: invalid character '#' looking for beginning of value"
        with patch.dict(aptly.__salt__), \
            patch('salt.modules.aptly._cmd_run',
                  MagicMock(return_value=error_text)), \
            patch('salt.modules.aptly._validate_config',
                  MagicMock(return_value=None)):
            self.assertRaises(ValueError, aptly.get_config)

    def test_list_repos(self):
        '''
        Test - List the local package repositories.
        '''
        kwargs = {
            'with_packages': False
        }
        repos = {REPO['name']: REPO}
        repos_with_packages = {REPO['name']: REPO_WITH_PACKAGES}
        list_cmd_output = 'devtest\n'

        mock_get_repo = MagicMock(return_value=REPO)
        with patch.dict(aptly.__salt__, {'aptly.get_repo': mock_get_repo}), \
            patch('salt.modules.aptly._cmd_run',
                  MagicMock(return_value=list_cmd_output)), \
            patch('salt.modules.aptly._validate_config',
                  MagicMock(return_value=None)):
            self.assertEqual(aptly.list_repos(**kwargs), repos)

        kwargs['with_packages'] = True
        mock_get_repo = MagicMock(return_value=REPO_WITH_PACKAGES)
        with patch.dict(aptly.__salt__, {'aptly.get_repo': mock_get_repo}), \
            patch('salt.modules.aptly._cmd_run',
                  MagicMock(return_value=list_cmd_output)), \
            patch('salt.modules.aptly._validate_config',
                  MagicMock(return_value=None)):
            self.assertEqual(aptly.list_repos(**kwargs), repos_with_packages)

    def test_get_repo(self):
        '''
        Test - Get detailed information about the local package repository.
        '''
        kwargs = {
            'name': 'devtest',
            'with_packages': False
        }
        with patch.dict(aptly.__salt__), \
            patch('salt.modules.aptly._cmd_run',
                  MagicMock(return_value=UNPARSED_REPO)), \
            patch('salt.modules.aptly._validate_config',
                  MagicMock(return_value=None)):
            self.assertEqual(aptly.get_repo(**kwargs), REPO)

        kwargs['with_packages'] = True
        with patch.dict(aptly.__salt__), \
            patch('salt.modules.aptly._cmd_run',
                  MagicMock(return_value=UNPARSED_REPO_WITH_PACKAGES)), \
            patch('salt.modules.aptly._validate_config',
                  MagicMock(return_value=None)):
            self.assertEqual(aptly.get_repo(**kwargs), REPO_WITH_PACKAGES)

    def test_new_repo(self):
        '''
        Test - Create a new local package repository.
        '''
        kwargs = {
            'name': 'devtest',
            'comment': 'Packages for the devtest project',
            'component': 'main',
            'distribution': 'xenial'
        }
        cmd_output = ("\nLocal repo [{}]: {} successfully added.\nYou can run 'aptly repo add"
                      " {} ...' to add packages to repository.\n").format(kwargs['name'],
                                                                          kwargs['comment'],
                                                                          kwargs['name'])
        mock_get_repo = MagicMock(side_effect=[dict(), REPO])
        with patch.dict(aptly.__salt__, {'aptly.get_repo': mock_get_repo}), \
            patch('salt.modules.aptly._cmd_run',
                  MagicMock(return_value=cmd_output)), \
            patch('salt.modules.aptly._validate_config',
                  MagicMock(return_value=None)):
            self.assertTrue(aptly.new_repo(**kwargs))

    def test_delete_repo(self):
        '''
        Test - Remove a local package repository.
        '''
        kwargs = {
            'name': 'devtest'
        }
        cmd_output = "\nLocal repo `{}` has been removed.\n".format(kwargs['name'])
        mock_get_repo = MagicMock(side_effect=[copy.deepcopy(REPO), dict()])
        with patch.dict(aptly.__salt__, {'aptly.get_repo': mock_get_repo}), \
            patch('salt.modules.aptly._cmd_run',
                  MagicMock(return_value=cmd_output)), \
            patch('salt.modules.aptly._validate_config',
                  MagicMock(return_value=None)):
            self.assertTrue(aptly.delete_repo(**kwargs))
