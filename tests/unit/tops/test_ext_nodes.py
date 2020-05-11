# -*- coding: utf-8 -*-
'''
Test ext_nodes master_tops module
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import subprocess
import textwrap

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch, MagicMock, NO_MOCK, NO_MOCK_REASON

# Import Salt libs
import salt.utils.stringutils
import salt.tops.ext_nodes as ext_nodes


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ExtNodesTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            ext_nodes: {
                '__opts__': {
                    'master_tops': {
                        # Since ext_nodes runs the command with shell=True,
                        # this will keep "command not found" errors from
                        # showing up on the console. We'll be mocking the
                        # communicate results anyway.
                        'ext_nodes': 'echo',
                    }
                }
            }
        }

    def test_ext_nodes(self):
        '''
        Confirm that subprocess.Popen works as expected and does not raise an
        exception (see https://github.com/saltstack/salt/pull/46863).
        '''
        stdout = salt.utils.stringutils.to_bytes(textwrap.dedent('''\
            classes:
              - one
              - two'''))
        communicate_mock = MagicMock(return_value=(stdout, None))
        with patch.object(subprocess.Popen, 'communicate', communicate_mock):
            ret = ext_nodes.top(opts={'id': 'foo'})
        self.assertEqual(ret, {'base': ['one', 'two']})

    def test_ext_nodes_with_environment(self):
        '''
        Same as above, but also tests that the matches are assigned to the proper
        environment if one is returned by the ext_nodes command.
        '''
        stdout = salt.utils.stringutils.to_bytes(textwrap.dedent('''\
            classes:
              - one
              - two
            environment: dev'''))
        communicate_mock = MagicMock(return_value=(stdout, None))
        with patch.object(subprocess.Popen, 'communicate', communicate_mock):
            ret = ext_nodes.top(opts={'id': 'foo'})
        self.assertEqual(ret, {'dev': ['one', 'two']})
