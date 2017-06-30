# -*- coding: utf-8 -*-
'''
    tests.unit.doc_test
    ~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import Salt libs
import tests.integration as integration
import salt.modules.cmdmod


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
        salt_dir = integration.CODE_DIR
        salt_dir += '/'
        cmd = 'grep -r :doc: ' + salt_dir

        grep_call = salt.modules.cmdmod.run_stdout(cmd=cmd).split('\n')

        test_ret = {}
        for line in grep_call:
            # Skip any .pyc files that may be present
            if line.startswith('Binary'):
                continue

            key, val = line.split(':', 1)

            # Don't test man pages, this file,
            # the page that documents to not use ":doc:", or
            # the doc/conf.py file
            if 'man' in key \
                    or key.endswith('test_doc.py') \
                    or key.endswith('doc/conf.py') \
                    or key.endswith('/conventions/documentation.rst') \
                    or key.endswith('doc/topics/releases/2016.11.2.rst') \
                    or key.endswith('doc/topics/releases/2016.11.3.rst') \
                    or key.endswith('doc/topics/releases/2016.3.5.rst'):
                continue

            # Set up test return dict
            if test_ret.get(key) is None:
                test_ret[key] = [val.lstrip()]
            else:
                test_ret[key].append(val.lstrip())

        # Allow test results to show files with :doc: ref, rather than truncating
        self.maxDiff = None

        # test_ret should be empty, otherwise there are :doc: references present
        self.assertEqual(test_ret, {})
