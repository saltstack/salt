# -*- coding: utf-8 -*-
'''
    tests.unit.doc_test
    ~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import os
import re

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.modules.cmdmod
import salt.utils.platform


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
        salt_dir = RUNTIME_VARS.CODE_DIR

        if salt.utils.platform.is_windows():
            # No grep in Windows, use findstr
            # findstr in windows doesn't prepend 'Binary` to binary files, so
            # use the '/P' switch to skip files with unprintable characters
            cmd = 'findstr /C:":doc:" /S /P {0}\\*'.format(salt_dir)
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
            key, val = regex.split(line, 1)

            # Don't test man pages, this file,
            # the tox virtualenv files, the page
            # that documents to not use ":doc:",
            # or the doc/conf.py file
            if 'man' in key \
                    or '.tox/' in key \
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
        '''
        # 'doc/ref/modules/all/salt.modules.zabbix.rst'
        # 'salt/modules/zabbix.py'
        salt_dir = RUNTIME_VARS.CODE_DIR

        # Build list of module files
        module_files = []
        skip_module_files = []
        module_dir = os.path.join(salt_dir, 'salt', 'modules')
        for file in os.listdir(module_dir):
            if file.endswith(".py"):
                module_name = os.path.splitext(file)[0]
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
            self.assertIn(module, module_docs)

        for doc_file in module_docs:
            self.assertIn(doc_file, module_files)
