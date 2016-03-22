# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk (bo@suse.de)`
    unit.utils.decorators_test
'''

# Import Pytohn libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salt.utils import decorators
from salt.version import SaltStackVersion

ensure_in_syspath('../../')


class DummyLogger(object):
    '''
    Dummy logger accepts everything and simply logs
    '''
    def __init__(self, messages):
        self._messages = messages

    def __getattr__(self, item):
        return self._log

    def _log(self, msg):
        self._messages.append(msg)


class DecoratorsTest(TestCase):
    '''
    Testing decorators.
    '''
    def deprecated_function(self):
        return "deprecated"

    def new_function(self):
        return "new"


    def _get_hi_ver(self):
        '''
        Get higher version.

        :return:
        '''
        return SaltStackVersion.from_name("Beryllium")

    def _get_lo_ver(self):
        '''
        Get lower version.

        :return:
        '''
        return SaltStackVersion.from_name("Helium")

    def test_is_deprecated(self):
        '''
        Test deprecated decorator class.

        :return:
        '''
        globs = {
            '__opts__': {},
            'deprecated_function': self.deprecated_function,
        }

        messages = list()
        decorators.log = DummyLogger(messages)
        depr = decorators.is_deprecated(globs, "Boron")
        depr(self.deprecated_function)()

        self.assertEqual(messages,
                         ['The function "deprecated_function" is deprecated '
                          'and will expire in version "Boron".'])

    def with_deprecated_test(self):
        pass

if __name__ == '__main__':
    from integration import run_tests
    run_tests(DecoratorsTest, needs_daemon=False)
