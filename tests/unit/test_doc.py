# -*- coding: utf-8 -*-
'''
    tests.unit.doc_test
    ~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import os
import re
import logging

# Import Salt Testing libs
from tests.support.paths import CODE_DIR
from tests.support.unit import TestCase

# Import Salt libs
import salt.modules.cmdmod
import salt.utils.platform


log = logging.getLogger(__name__)


class DocTestCase(TestCase):
    '''
    Unit test case for testing doc files and strings.
    '''

    def test_check_for_doc_inline_markup(self):
        '''
        We should not be using the ``:doc:`` inline markup option when
        cross-referencing locations. Use ``:ref:`` or ``:mod:`` instead.

        This test checks for reference to ``:doc:`` usage.

        See Issue #12788 for more information.

        https://github.com/saltstack/salt/issues/12788
        '''
        salt_dir = CODE_DIR

        if salt.utils.platform.is_windows():
            if salt.utils.path.which('bash'):
                # Use grep from git-bash when it exists.
                cmd = 'bash -c \'grep -r :doc: ./salt/'
                grep_call = salt.modules.cmdmod.run_stdout(cmd=cmd, cwd=salt_dir).split(os.linesep)
            else:
                # No grep in Windows, use findstr
                # findstr in windows doesn't prepend 'Binary` to binary files, so
                # use the '/P' switch to skip files with unprintable characters
                cmd = 'findstr /C:":doc:" /S /P {0}\\*'.format(salt_dir)
                grep_call = salt.modules.cmdmod.run_stdout(cmd=cmd).split(os.linesep)
        else:
            salt_dir += '/'
            cmd = 'grep -r :doc: ' + salt_dir
            grep_call = salt.modules.cmdmod.run_stdout(cmd=cmd).split(os.linesep)

        test_ret = {}
        for line in grep_call:
            # Skip any .pyc files that may be present
            if line.startswith('Binary'):
                continue

            # Only split on colons not followed by a '\' as is the case with
            # Windows Drives
            regex = re.compile(r':(?!\\)')
            try:
                key, val = regex.split(line, 1)
            except ValueError:
                log.error("Could not split line: %s", line)
                continue

            # Don't test man pages, this file, the tox or nox virtualenv files,
            # the page that documents to not use ":doc:", the doc/conf.py file
            # or the artifacts directory on nox CI test runs
            if 'man' in key \
                    or '.tox{}'.format(os.sep) in key \
                    or '.nox{}'.format(os.sep) in key \
                    or 'artifacts{}'.format(os.sep) in key \
                    or key.endswith('test_doc.py') \
                    or key.endswith(os.sep.join(['doc', 'conf.py'])) \
                    or key.endswith(os.sep.join(['conventions', 'documentation.rst'])) \
                    or key.endswith(os.sep.join(['doc', 'topics', 'releases', '2016.11.2.rst'])) \
                    or key.endswith(os.sep.join(['doc', 'topics', 'releases', '2016.11.3.rst'])) \
                    or key.endswith(os.sep.join(['doc', 'topics', 'releases', '2016.3.5.rst'])):
                continue

            # Set up test return dict
            if test_ret.get(key) is None:
                test_ret[key] = [val.strip()]
            else:
                test_ret[key].append(val.strip())

        # Allow test results to show files with :doc: ref, rather than truncating
        self.maxDiff = None

        # test_ret should be empty, otherwise there are :doc: references present
        self.assertEqual(test_ret, {})

    def test_module_doc_files(self):
        '''
        Ensure modules have associated documentation

        doc example: doc/ref/modules/all/salt.modules.zabbix.rst
        execution module example: salt/modules/zabbix.py
        '''

        salt_dir = RUNTIME_VARS.CODE_DIR

        # Build list of module files
        module_files = []
        skip_module_files = ['__init__']
        module_dir = os.path.join(salt_dir, 'salt', 'modules')
        for file in os.listdir(module_dir):
            if file.endswith(".py"):
                module_name = os.path.splitext(file)[0]
                if not module_name in skip_module_files:
                    module_files.append(module_name)

        # Build list of module documentation files
        module_docs = []
        skip_doc_files = ['index', 'group', 'inspectlib', 'inspectlib.collector', 'inspectlib.dbhandle',
                       'inspectlib.entities', 'inspectlib.exceptions', 'inspectlib.fsdb',
                       'inspectlib.kiwiproc', 'inspectlib.query', 'kernelpkg', 'pkg', 'user']
        module_doc_dir = os.path.join(salt_dir, 'doc', 'ref', 'modules', 'all')
        for file in os.listdir(module_doc_dir):
            if file.endswith(".rst"):
                doc_name = os.path.splitext(file)[0]
                if doc_name.startswith('salt.modules.'):
                        doc_name = doc_name[13:]
                if not doc_name in skip_doc_files:
                    module_docs.append(doc_name)

        # Check that every module has associated documentaiton file
        for module in module_files:
            self.assertIn(module,
                          module_docs,
                          'Module file {0} is missing documentation in {1}'.format(module,
                                                                                   module_doc_dir))

        for doc_file in module_docs:
            self.assertIn(doc_file,
                          module_files,
                          'Doc file {0} is missing associated module in {1}'.format(doc_file,
                                                                                    module_dir))


    def test_state_doc_files(self):
        '''
        Ensure states have associated documentation

        doc example: doc\ref\states\all\salt.states.zabbix_host.rst
        state example: salt\states\zabbix_host.py
        '''

        salt_dir = RUNTIME_VARS.CODE_DIR

        # Build list of state files
        state_files = []
        skip_state_files = ['__init__']
        state_dir = os.path.join(salt_dir, 'salt', 'states')
        for file in os.listdir(state_dir):
            if file.endswith(".py"):
                state_name = os.path.splitext(file)[0]
                if not state_name in skip_state_files:
                    state_files.append(state_name)

        # Build list of state documentation files
        state_docs = []
        skip_doc_files = ['index', 'all']
        state_doc_dir = os.path.join(salt_dir, 'doc', 'ref', 'states', 'all')
        for file in os.listdir(state_doc_dir):
            if file.endswith(".rst"):
                doc_name = os.path.splitext(file)[0]
                if doc_name.startswith('salt.states.'):
                        doc_name = doc_name[12:]
                if not doc_name in skip_doc_files:
                    state_docs.append(doc_name)

        # Check that every state has associated documentaiton file
        for state in state_files:
            self.assertIn(state,
                          state_docs,
                          'State file {0} is missing documentation in {1}'.format(state,
                                                                                  state_doc_dir))

        for doc_file in state_docs:
            self.assertIn(doc_file,
                          state_files,
                          'Doc file {0} is missing associated state in {1}'.format(doc_file,
                                                                                   state_doc_dir))
