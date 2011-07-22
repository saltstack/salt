#!/usr/bin/env python

"""
Unit tests for salt/modules/monitor.py.
"""

import doctest
import unittest
import salt.log

def dummy(*args, **kwargs):
    pass

class TestMonitor(unittest.TestCase):

    def setUp(self):
        opts = {}
        functions = {'test.echo' : dummy}

        # Late import so logging works correctly
        import salt.monitor
        self.testobj = salt.monitor.Monitor(opts, functions)

    def _test_expand(self, intext, expected):
        self.assertEqual(self.testobj._expand_references(intext), expected)

    def _test_call(self, intext, expected):
        self.assertEqual(self.testobj._expand_call(intext), expected)

    def _test_conditional(self, incond, inactions, expected):
        actual = self.testobj._expand_conditional(incond, inactions)
        self.assertEqual(actual, expected)

    def test_doc(self):
        doctest.testmod(salt.monitor)

    def test_plain_text_passthrough(self):
        self._test_expand('salt.cmd',    'salt.cmd')      # passthrough
        self._test_expand('sys.argv[0]', 'sys.argv[0]')   # unquoted
        self._test_expand('123',         '123')           # text
        self._test_expand('abc',         'abc')
        self._test_expand('abc 123',     'abc 123')
        self._test_expand('3.14159265',  '3.14159265')

    def test_quoting(self):
        self._test_expand("'123'",       "'123'")
        self._test_expand("'abc'",       "'abc'")
        self._test_expand("'abc 123'",   "'abc 123'")
        self._test_expand('"abc 123"',   "'abc 123'")
        self._test_expand("bob's stuff", "bob's stuff")
        self._test_expand('say "what?"', 'say "what?"')
        self._test_expand("'",            "'")
        self._test_expand("''",           "''")

    def test_escape_sequences(self):
        self._test_expand('\\', '\\')                 # escape at end of string
        self._test_expand('\\abc', '\\abc')           # escape non-special char
        self._test_expand('\\\\', '\\')               # escape escape char
        self._test_expand('\\$', '$')                 # escape reference
        self._test_expand('\\$value', '$value')       # escape reference
        self._test_expand('\\${value}', '${value}')   # escape reference

    def test_reserved_chars(self):
        self._test_expand('{}', '{}')                       # not formatting
        self._test_expand('abc{}123', 'abc{}123')           # not formatting
        self._test_expand("'{$x}'", "'{{{}}}'.format(x)")   # needs escape
        self._test_expand("'}$x{'", "'}}{}{{'.format(x)")   # needs escape
        self._test_expand("'$x {}'", "'{} {{}}'.format(x)") # needs escape

    def test_simple_references(self):
        self._test_expand('$value', 'value')            # unquoted variable
        self._test_expand('${value}', 'value')          # unquoted variable
        self._test_expand("'$value'", 'str(value)')     # just quoted variable
        self._test_expand("'${value}'", 'str(value)')   # just quoted variable
        self._test_expand("'v=$v'", "'v={}'.format(v)") # quoted var plus text

    def test_multiple_references(self):
        self._test_expand('$key=$value', 'key=value')         # e.g. kwargs param
        self._test_expand('${key}=${value}', 'key=value')     # e.g. kwargs param
        self._test_expand("'$key=$value'", "'{}={}'.format(key, value)")
        self._test_expand("'${key}=${value}'", "'{}={}'.format(key, value)")
        self._test_expand("${value['available']}/${value['total']}",
                          "value['available']/value['total']")
        self._test_expand("'${value['available']}/${value['total']}'",
                          "'{}/{}'.format(value['available'], value['total'])")

    def test_expression_references(self):
        self._test_expand("${value['available']<1024*1024}",
                          "value['available']<1024*1024")
        self._test_expand("${value['available']}<1024*1024",
                          "value['available']<1024*1024")

    def test_conditional_expansion(self):
        self._test_expand("if value['available'] * 100 / value['total'] < 90:",
                          "if value['available'] * 100 / value['total'] < 90:")
        self._test_expand("if ${value['available']} * 100 / ${value['total']} < 90:",
                          "if value['available'] * 100 / value['total'] < 90:")
        self._test_expand("if ${value['available'] * 100} / ${value['total']} < 90:",
                          "if value['available'] * 100 / value['total'] < 90:")
        self._test_expand("if ${value['available'] * 100 / value['total']} < 90:",
                          "if value['available'] * 100 / value['total'] < 90:")

    def test_expand_call(self):
        self._test_call("test.echo",
                        "functions['test.echo']()")
        self._test_call("test.echo 'hello, world'",
                        "functions['test.echo']('hello, world')")
        self._test_call("test.echo '${value[\"available\"]/(1024*1024)} MB ${value[\"available\"]*100/value[\"total\"]}%'",
                        "functions['test.echo']('{} MB {}%'.format(value[\"available\"]/(1024*1024), "\
                                    "value[\"available\"]*100/value[\"total\"]))")

    def test_expand_conditional(self):
        self._test_conditional("${value['available']} > 100", [],
                               [ "if value['available'] > 100:",
                                 "    pass" ])

        self._test_conditional("${value['available']} > 100 and ${value['total']} < 1000",
                               [ "test.echo \"${value['available']} too low\"" ],
                               [ "if value['available'] > 100 and value['total'] < 1000:",
                                 "    functions['test.echo']('{} too low'.format(value['available']))" ])

def test_suite():
    salt.log.setup_console_logger("none")
    return unittest.TestLoader().loadTestsFromName(__name__)
