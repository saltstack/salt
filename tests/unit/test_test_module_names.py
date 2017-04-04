# -*- coding: utf-8 -*-
'''
    tests.unit.test_test_module_name
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.paths import CODE_DIR

EXCLUDED_DIRS = [
    'tests/pkg',
    'tests/perf',
    'tests/support',
    'tests/unit/utils/cache_mods',
    'tests/unit/modules/inspectlib',
    'tests/unit/modules/zypp/',
    'tests/unit/templates/files',
    'tests/integration/files/',
    'tests/integration/cloud/helpers',
]
EXCLUDED_FILES = [
    'tests/eventlisten.py',
    'tests/buildpackage.py',
    'tests/saltsh.py',
    'tests/minionswarm.py',
    'tests/wheeltest.py',
    'tests/runtests.py',
    'tests/jenkins.py',
    'tests/salt-tcpdump.py',
    'tests/conftest.py',
    'tests/packdump.py',
    'tests/consist.py',
    'tests/modparser.py',
    'tests/committer_parser.py',
    'tests/unit/transport/mixins.py',
    'tests/integration/utils/testprogram.py',
]


class BadTestModuleNamesTestCase(TestCase):
    '''
    Unit test case for testing bad names for test modules
    '''

    maxDiff = None

    def test_module_name(self):
        '''
        Make sure all test modules conform to the test_*.py naming scheme
        '''
        excluded_dirs = tuple(EXCLUDED_DIRS)
        tests_dir = os.path.join(CODE_DIR, 'tests')
        bad_names = []
        for root, dirs, files in os.walk(tests_dir):
            reldir = os.path.relpath(root, CODE_DIR)
            if reldir.startswith(excluded_dirs) or reldir.endswith('__pycache__'):
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
