# -*- coding: utf-8 -*-

"""
Test the directory roster.
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt Testing Libs
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
)
from tests.support import mixins
from tests.support.unit import skipIf, TestCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.paths import TESTS_DIR

# Import Salt Libs
import salt.config
import salt.loader
import salt.roster.dir as dir_

# Import 3rd-party libs
from salt.ext import six

ROSTER_DIR = os.path.join(TESTS_DIR, 'unit/files/rosters/dir')
ROSTER_DOMAIN = 'test.roster.domain'
EXPECTED = {
    'basic': {
        'test1_us-east-2_test_basic': {
            'host': '127.0.0.2',
            'port': 22,
            'sudo': True,
            'user': 'scoundrel',
        }
    },
    'domain': {
        'test1_us-east-2_test_domain': {
            'host': 'test1_us-east-2_test_domain.' + ROSTER_DOMAIN,
            'port': 2222,
            'user': 'george',
        }
    },
    'empty': {
        'test1_us-east-2_test_empty': {
            'host': 'test1_us-east-2_test_empty.' + ROSTER_DOMAIN,
        }
    },
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DirRosterTestCase(TestCase, mixins.LoaderModuleMockMixin):
    """Test the directory roster"""

    def setup_loader_modules(self):
        opts = salt.config.master_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'master'))
        utils = salt.loader.utils(opts, whitelist=['json', 'stringutils', 'roster_matcher'])
        runner = salt.loader.runner(opts, utils=utils, whitelist=['salt'])
        return {
            dir_: {
                '__opts__': {
                    'extension_modules': '',
                    'optimization_order': [0, 1, 2],
                    'renderer': 'jinja|yaml',
                    'renderer_blacklist': [],
                    'renderer_whitelist': [],
                    'roster_dir': ROSTER_DIR,
                    'roster_domain': ROSTER_DOMAIN,
                },
                '__runner__': runner,
                '__utils__': utils,
            }
        }

    def _test_match(self, ret, expected):
        """
        assertDictEquals is too strict with OrderedDicts. The order isn't crucial
        for roster entries, so we test that they contain the expected members directly.
        """
        self.assertNotEqual(ret, {}, 'Found no matches, expected {}'.format(expected))
        for minion, data in ret.items():
            self.assertIn(minion, expected, 'Expected minion {} to match, but it did not'.format(minion))
            self.assertDictEqual(dict(data), expected[minion],
                                 'Data for minion {} did not match expectations'.format(minion))

    def test_basic_glob(self):
        """Test that minion files in the directory roster match and render."""
        expected = EXPECTED['basic']
        ret = dir_.targets('*_basic', saltenv='')
        self._test_match(ret, expected)

    def test_basic_re(self):
        """Test that minion files in the directory roster match and render."""
        expected = EXPECTED['basic']
        ret = dir_.targets('.*basic$', 'pcre', saltenv='')
        self._test_match(ret, expected)

    def test_basic_list(self):
        """Test that minion files in the directory roster match and render."""
        expected = EXPECTED['basic']
        ret = dir_.targets(expected.keys(), 'list', saltenv='')
        self._test_match(ret, expected)

    def test_roster_domain(self):
        """Test that when roster_domain is configured, it will provide a default hostname
        in the roster of {filename}.{roster_domain}, so that users can use the minion
        id as the local hostname without having to supply the fqdn everywhere."""
        expected = EXPECTED['domain']
        ret = dir_.targets(expected.keys(), 'list', saltenv='')
        self._test_match(ret, expected)

    def test_empty(self):
        """Test that an empty roster file matches its hostname"""
        expected = EXPECTED['empty']
        ret = dir_.targets('*_empty', saltenv='')
        self._test_match(ret, expected)

    def test_nomatch(self):
        """Test that no errors happen when no files match"""
        try:
            ret = dir_.targets('', saltenv='')
        except:
            self.fail('No files matched, which is OK, but we raised an exception and we should not have.')
            raise
        self.assertEqual(len(ret), 0, 'Expected empty target list to yield zero targets.')

    def test_badfile(self):
        """Test error handling when we can't render a file"""
        ret = dir_.targets('*badfile', saltenv='')
        self.assertEqual(len(ret), 0)

    @skipIf(not six.PY3, "Can only assertLogs in PY3")
    def test_badfile_logging(self):
        """Test error handling when we can't render a file"""
        with self.assertLogs('salt.roster.dir', level='WARNING') as logged:
            dir_.targets('*badfile', saltenv='')
            self.assertIn('test1_us-east-2_test_badfile', logged.output[0])
