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
from tests.support.unit import TestCase
from tests.support.runtests import RUNTIME_VARS

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
        salt_dir = RUNTIME_VARS.CODE_DIR

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
