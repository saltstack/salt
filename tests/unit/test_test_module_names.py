# -*- coding: utf-8 -*-
'''
    tests.unit.test_test_module_name
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import fnmatch
import os

# Import Salt libs
import salt.utils.path

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.paths import CODE_DIR

EXCLUDED_DIRS = [
    os.path.join('tests', 'pkg'),
    os.path.join('tests', 'perf'),
    os.path.join('tests', 'support'),
    os.path.join('tests', 'unit', 'utils', 'cache_mods'),
    os.path.join('tests', 'unit', 'modules', 'inspectlib'),
    os.path.join('tests', 'unit', 'modules', 'zypp'),
    os.path.join('tests', 'unit', 'templates', 'files'),
    os.path.join('tests', 'integration', 'files'),
    os.path.join('tests', 'integration', 'cloud', 'helpers'),
    os.path.join('tests', 'kitchen', 'tests'),
]
INCLUDED_DIRS = [
    os.path.join('tests', 'kitchen', 'tests', '*', 'tests', '*'),
]
EXCLUDED_FILES = [
    os.path.join('tests', 'eventlisten.py'),
    os.path.join('tests', 'buildpackage.py'),
    os.path.join('tests', 'saltsh.py'),
    os.path.join('tests', 'minionswarm.py'),
    os.path.join('tests', 'wheeltest.py'),
    os.path.join('tests', 'runtests.py'),
    os.path.join('tests', 'jenkins.py'),
    os.path.join('tests', 'salt-tcpdump.py'),
    os.path.join('tests', 'conftest.py'),
    os.path.join('tests', 'packdump.py'),
    os.path.join('tests', 'consist.py'),
    os.path.join('tests', 'modparser.py'),
    os.path.join('tests', 'committer_parser.py'),
    os.path.join('tests', 'zypp_plugin.py'),
    os.path.join('tests', 'unit', 'transport', 'mixins.py'),
    os.path.join('tests', 'integration', 'utils', 'testprogram.py'),
]


class BadTestModuleNamesTestCase(TestCase):
    '''
    Unit test case for testing bad names for test modules
    '''

    maxDiff = None

    def _match_dirs(self, reldir, matchdirs):
        return any(fnmatch.fnmatchcase(reldir, mdir) for mdir in matchdirs)

    def test_module_name(self):
        '''
        Make sure all test modules conform to the test_*.py naming scheme
        '''
        excluded_dirs, included_dirs = tuple(EXCLUDED_DIRS), tuple(INCLUDED_DIRS)
        tests_dir = os.path.join(CODE_DIR, 'tests')
        bad_names = []
        for root, dirs, files in salt.utils.path.os_walk(tests_dir):
            reldir = os.path.relpath(root, CODE_DIR)
            if (reldir.startswith(excluded_dirs) and not self._match_dirs(reldir, included_dirs)) \
                    or reldir.endswith('__pycache__'):
                continue
            for fname in files:
                if fname == '__init__.py' or not fname.endswith('.py'):
                    continue
                relpath = os.path.join(reldir, fname)
                if relpath in EXCLUDED_FILES:
                    continue
                if not fname.startswith('test_'):
                    bad_names.append(relpath)

        error_msg = '\n\nPlease rename the following files:\n'
        for path in bad_names:
            directory, filename = path.rsplit(os.sep, 1)
            filename, ext = os.path.splitext(filename)
            error_msg += '  {} -> {}/test_{}.py\n'.format(path, directory, filename.split('_test')[0])

        error_msg += '\nIf you believe one of the entries above should be ignored, please add it to either\n'
        error_msg += '\'EXCLUDED_DIRS\' or \'EXCLUDED_FILES\' in \'tests/unit/test_module_names.py\'.\n'
        error_msg += 'If it is a tests module, then please rename as suggested.'
        self.assertEqual([], bad_names, error_msg)
