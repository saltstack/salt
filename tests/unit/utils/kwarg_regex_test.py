# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    unit.utils.kwarg_regex_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Pytohn libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt libs
from salt.utils.args import KWARG_REGEX


class KwargRegexTest(TestCase):
    def test_arguments_regex(self):
        argument_matches = (
            ('pip=1.1', ('pip', '1.1')),
            ('pip==1.1', None),
            ('pip=1.2=1', ('pip', '1.2=1')),
        )
        for argument, match in argument_matches:
            if match is None:
                self.assertIsNone(KWARG_REGEX.match(argument))
            else:
                self.assertEqual(
                    KWARG_REGEX.match(argument).groups(), match
                )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(KwargRegexTest, needs_daemon=False)
