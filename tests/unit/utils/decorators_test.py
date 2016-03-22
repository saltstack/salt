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
    def old_function(self):
        return "old"

    def new_function(self):
        return "new"

    def _mk_version(self, name):
        '''
        Make a version

        :return:
        '''
        return name, SaltStackVersion.from_name(name)

    def test_is_deprecated_log_message_appears(self):
        '''
        Use of is_deprecated will result to the log message,
        if expiration version is higher than current version.

        :return:
        '''
        globs = {
            '__opts__': {},
            'old_function': self.old_function,
        }

        messages = list()
        decorators.log = DummyLogger(messages)
        depr = decorators.is_deprecated(globs, "Beryllium")
        depr._curr_version = self._mk_version("Helium")[1]
        depr(self.old_function)()

        self.assertEqual(messages,
                         ['The function "old_function" is deprecated '
                          'and will expire in version "Beryllium".'])

    def with_deprecated_test(self):
        pass

if __name__ == '__main__':
    from integration import run_tests
    run_tests(DecoratorsTest, needs_daemon=False)
