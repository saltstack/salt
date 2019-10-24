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
import salt.utils.stringutils

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.paths import CODE_DIR, test_mods

EXCLUDED_DIRS = [
    os.path.join('tests', 'pkg'),
    os.path.join('tests', 'perf'),
    os.path.join('tests', 'support'),
    os.path.join('tests', 'unit', 'utils', 'cache_mods'),
    os.path.join('tests', 'unit', 'modules', 'inspectlib'),
    os.path.join('tests', 'unit', 'modules', 'zypp'),
    os.path.join('tests', 'unit', 'templates', 'files'),
    os.path.join('tests', 'integration', 'files'),
    os.path.join('tests', 'unit', 'files'),
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
    os.path.join('tests', 'virtualname.py'),
    os.path.join('tests', 'committer_parser.py'),
    os.path.join('tests', 'zypp_plugin.py'),
    os.path.join('tests', 'tox-helper.py'),
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

    def test_module_name_source_match(self):
        '''
        Check all the test mods and check if they correspond to actual files in
        the codebase. If this test fails, then a test module is likely not
        named correctly, and should be adjusted.

        If a test module doesn't have a natural name match (as does this very
        file), then its should be included in the "ignore" tuple below.
        However, if there is no matching source code file, then you should
        consider mapping it to files manually via tests/filename_map.yml.
        '''
        ignore = (
            'unit.test_doc',
            'unit.test_mock',
            'unit.test_module_names',
            'unit.test_virtualname',
            'unit.test_simple',
            'unit.test_zypp_plugins',
            'unit.test_proxy_minion',
            'unit.cache.test_cache',
            'unit.serializers.test_serializers',
            'unit.states.test_postgres',
            'integration.cli.test_custom_module',
            'integration.cli.test_grains',
            'integration.client.test_kwarg',
            'integration.client.test_runner',
            'integration.client.test_standard',
            'integration.client.test_syndic',
            'integration.cloud.test_cloud',
            'integration.doc.test_man',
            'integration.externalapi.test_venafiapi',
            'integration.grains.test_custom',
            'integration.loader.test_ext_grains',
            'integration.loader.test_ext_modules',
            'integration.logging.test_jid_logging',
            'integration.master.test_event_return',
            'integration.minion.test_blackout',
            'integration.minion.test_pillar',
            'integration.minion.test_timeout',
            'integration.modules.test_decorators',
            'integration.modules.test_pkg',
            'integration.modules.test_state_jinja_filters',
            'integration.modules.test_sysctl',
            'integration.netapi.test_client',
            'integration.netapi.rest_tornado.test_app',
            'integration.netapi.rest_cherrypy.test_app_pam',
            'integration.output.test_output',
            'integration.pillar.test_pillar_include',
            'integration.proxy.test_shell',
            'integration.proxy.test_simple',
            'integration.reactor.test_reactor',
            'integration.returners.test_noop_return',
            'integration.runners.test_runner_returns',
            'integration.scheduler.test_error',
            'integration.scheduler.test_eval',
            'integration.scheduler.test_postpone',
            'integration.scheduler.test_skip',
            'integration.scheduler.test_maxrunning',
            'integration.scheduler.test_helpers',
            'integration.scheduler.test_run_job',
            'integration.shell.test_spm',
            'integration.shell.test_cp',
            'integration.shell.test_syndic',
            'integration.shell.test_proxy',
            'integration.shell.test_auth',
            'integration.shell.test_call',
            'integration.shell.test_arguments',
            'integration.shell.test_matcher',
            'integration.shell.test_master_tops',
            'integration.shell.test_saltcli',
            'integration.shell.test_master',
            'integration.shell.test_key',
            'integration.shell.test_runner',
            'integration.shell.test_cloud',
            'integration.shell.test_enabled',
            'integration.shell.test_minion',
            'integration.spm.test_build',
            'integration.spm.test_files',
            'integration.spm.test_info',
            'integration.spm.test_install',
            'integration.spm.test_remove',
            'integration.spm.test_repo',
            'integration.ssh.test_deploy',
            'integration.ssh.test_grains',
            'integration.ssh.test_jinja_filters',
            'integration.ssh.test_master',
            'integration.ssh.test_mine',
            'integration.ssh.test_pillar',
            'integration.ssh.test_raw',
            'integration.ssh.test_state',
            'integration.states.test_compiler',
            'integration.states.test_handle_error',
            'integration.states.test_handle_iorder',
            'integration.states.test_match',
            'integration.states.test_renderers',
            'integration.wheel.test_client',
            'multimaster.minion.test_event',
        )
        errors = []

        def _format_errors(errors):
            msg = (
                'The following {0} test module(s) could not be matched to a '
                'source code file:\n\n'.format(len(errors))
            )
            msg += ''.join(errors)
            return msg

        for mod_name in test_mods():
            if mod_name in ignore:
                # Test module is being ignored, skip it
                continue

            # Separate the test_foo away from the rest of the mod name, because
            # we'll need to remove the "test_" from the beginning and add .py
            stem, flower = mod_name.rsplit('.', 1)
            # Lop off the integration/unit from the beginning of the mod name
            try:
                stem = stem.split('.', 1)[1]
            except IndexError:
                # This test mod was in the root of the unit/integration dir
                stem = ''

            # The path from the root of the repo
            relpath = salt.utils.path.join(
                'salt',
                stem.replace('.', os.sep),
                '.'.join((flower[5:], 'py')))

            # The full path to the file we expect to find
            abspath = salt.utils.path.join(CODE_DIR, relpath)

            if not os.path.isfile(abspath):
                # Maybe this is in a dunder init?
                alt_relpath = salt.utils.path.join(relpath[:-3], '__init__.py')
                alt_abspath = salt.utils.path.join(abspath[:-3], '__init__.py')
                if os.path.isfile(alt_abspath):
                    # Yep, it is. Carry on!
                    continue

                errors.append(
                    '{0} (expected: {1})\n'.format(mod_name, relpath)
                )

        assert not errors, _format_errors(errors)
