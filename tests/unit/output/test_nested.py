# -*- coding: utf-8 -*-
'''
Unit tests for the Nested outputter
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase

# Import Salt Libs
import salt.output.nested as nested


class NestedOutputterTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.output.nested
    '''
    def setup_loader_modules(self):
        return {
            nested: {
                '__opts__': {
                    'extension_modules': '',
                    'color': True
                }
            }
        }

    def setUp(self):
        # The example from the documentation for the test.arg execution function
        # Same function from the highstate outputter
        self.data = {
            'local': {
                'args': (1, 'two', 3.1),
                'kwargs': {
                    u'__pub_pid': 25938,
                    'wow': {
                        'a': 1,
                        'b': 'hello'
                    },
                    u'__pub_fun': 'test.arg',
                    u'__pub_jid': '20171207105927331329',
                    u'__pub_tgt': 'salt-call',
                    'txt': 'hello'
                }
            }
        }
        self.addCleanup(delattr, self, 'data')

    def test_output_with_colors(self):
        # Should look exacly like that, with the default color scheme:
        #
        # local:
        #    ----------
        #    args:
        #        - 1
        #        - two
        #        - 3.1
        #    kwargs:
        #        ----------
        #        __pub_fun:
        #            test.arg
        #        __pub_jid:
        #            20171207105927331329
        #        __pub_pid:
        #            25938
        #        __pub_tgt:
        #            salt-call
        #        txt:
        #            hello
        #        wow:
        #            ----------
        #            a:
        #                1
        #            b:
        #                hello
        expected_output_str = (
            '\x1b[0;36mlocal\x1b[0;0m:\n    \x1b[0;36m----------\x1b[0;0m\n    \x1b[0;36margs\x1b[0;0m:\n'
            '        \x1b[0;1;33m- 1\x1b[0;0m\n        \x1b[0;32m- two\x1b[0;0m\n        \x1b[0;1;33m- 3.1\x1b[0;0m\n'
            '    \x1b[0;36mkwargs\x1b[0;0m:\n        \x1b[0;36m----------\x1b[0;0m\n'
            '        \x1b[0;36m__pub_fun\x1b[0;0m:\n            \x1b[0;32mtest.arg\x1b[0;0m\n'
            '        \x1b[0;36m__pub_jid\x1b[0;0m:\n            \x1b[0;32m20171207105927331329\x1b[0;0m\n'
            '        \x1b[0;36m__pub_pid\x1b[0;0m:\n            \x1b[0;1;33m25938\x1b[0;0m\n'
            '        \x1b[0;36m__pub_tgt\x1b[0;0m:\n            \x1b[0;32msalt-call\x1b[0;0m\n'
            '        \x1b[0;36mtxt\x1b[0;0m:\n            \x1b[0;32mhello\x1b[0;0m\n        \x1b[0;36mwow\x1b[0;0m:\n'
            '            \x1b[0;36m----------\x1b[0;0m\n            \x1b[0;36ma\x1b[0;0m:\n'
            '                \x1b[0;1;33m1\x1b[0;0m\n            \x1b[0;36mb\x1b[0;0m:\n'
            '                \x1b[0;32mhello\x1b[0;0m'
        )
        ret = nested.output(self.data)
        self.assertEqual(ret, expected_output_str)

    def test_output_with_retcode(self):
        # Non-zero retcode should change the colors
        # Same output format as above, just different colors
        expected_output_str = (
            '\x1b[0;31mlocal\x1b[0;0m:\n    \x1b[0;31m----------\x1b[0;0m\n    \x1b[0;31margs\x1b[0;0m:\n'
            '        \x1b[0;1;33m- 1\x1b[0;0m\n        \x1b[0;32m- two\x1b[0;0m\n        \x1b[0;1;33m- 3.1\x1b[0;0m\n'
            '    \x1b[0;31mkwargs\x1b[0;0m:\n        \x1b[0;31m----------\x1b[0;0m\n'
            '        \x1b[0;31m__pub_fun\x1b[0;0m:\n            \x1b[0;32mtest.arg\x1b[0;0m\n'
            '        \x1b[0;31m__pub_jid\x1b[0;0m:\n            \x1b[0;32m20171207105927331329\x1b[0;0m\n'
            '        \x1b[0;31m__pub_pid\x1b[0;0m:\n            \x1b[0;1;33m25938\x1b[0;0m\n'
            '        \x1b[0;31m__pub_tgt\x1b[0;0m:\n            \x1b[0;32msalt-call\x1b[0;0m\n'
            '        \x1b[0;31mtxt\x1b[0;0m:\n            \x1b[0;32mhello\x1b[0;0m\n        \x1b[0;31mwow\x1b[0;0m:\n'
            '            \x1b[0;31m----------\x1b[0;0m\n            \x1b[0;31ma\x1b[0;0m:\n'
            '                \x1b[0;1;33m1\x1b[0;0m\n            \x1b[0;31mb\x1b[0;0m:\n'
            '                \x1b[0;32mhello\x1b[0;0m'
        )
        # You can notice that in test_output_with_colors the color code is \x1b[0;36m, i.e., GREEN,
        # while here the color code is \x1b[0;31m, i.e., RED (failure)
        ret = nested.output(self.data, _retcode=1)
        self.assertEqual(ret, expected_output_str)

    def test_output_with_indent(self):
        # Everything must be indented by exactly two spaces
        # (using nested_indent=2 sent to nested.output as kwarg)
        expected_output_str = (
           '  \x1b[0;36m----------\x1b[0;0m\n  \x1b[0;36mlocal\x1b[0;0m:\n      \x1b[0;36m----------\x1b[0;0m\n'
           '      \x1b[0;36margs\x1b[0;0m:\n          \x1b[0;1;33m- 1\x1b[0;0m\n          \x1b[0;32m- two\x1b[0;0m\n'
           '          \x1b[0;1;33m- 3.1\x1b[0;0m\n      \x1b[0;36mkwargs\x1b[0;0m:\n'
           '          \x1b[0;36m----------\x1b[0;0m\n          \x1b[0;36m__pub_fun\x1b[0;0m:\n'
           '              \x1b[0;32mtest.arg\x1b[0;0m\n          \x1b[0;36m__pub_jid\x1b[0;0m:\n'
           '              \x1b[0;32m20171207105927331329\x1b[0;0m\n          \x1b[0;36m__pub_pid\x1b[0;0m:\n'
           '              \x1b[0;1;33m25938\x1b[0;0m\n          \x1b[0;36m__pub_tgt\x1b[0;0m:\n'
           '              \x1b[0;32msalt-call\x1b[0;0m\n          \x1b[0;36mtxt\x1b[0;0m:\n'
           '              \x1b[0;32mhello\x1b[0;0m\n          \x1b[0;36mwow\x1b[0;0m:\n'
           '              \x1b[0;36m----------\x1b[0;0m\n              \x1b[0;36ma\x1b[0;0m:\n'
           '                  \x1b[0;1;33m1\x1b[0;0m\n              \x1b[0;36mb\x1b[0;0m:\n'
           '                  \x1b[0;32mhello\x1b[0;0m'
        )
        ret = nested.output(self.data, nested_indent=2)
        self.assertEqual(ret, expected_output_str)
