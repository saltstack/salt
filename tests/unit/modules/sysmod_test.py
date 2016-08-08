# -*- coding: utf-8 -*-
'''
:codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import sysmod

_modules = set()
_functions = [
    'exist.exist',

    'sys.doc', 'sys.list_functions', 'sys.list_modules',
    'sysctl.get', 'sysctl.show',
    'system.halt', 'system.reboot',

    'udev.name', 'udev.path',
    'user.add', 'user.info', 'user.rename',
]

sysmod.__salt__ = {}
sysmod.__opts__ = {}

for func in _functions:
    sysmod.__salt__[func] = None
    _modules.add(func.split('.')[0])
_modules = sorted(list(_modules))


class Mockstate(object):
    """
    Mock of State
    """
    class State(object):
        """
        Mock of State
        """
        states = {}
        for func in _functions:
            states[func] = None

        def __init__(self, opts):
            pass


class Mockrunner(object):
    """
    Mock of runner
    """
    class Runner(object):
        """
        Mock of Runner
        """
        functions = {}
        for func in _functions:
            functions[func] = None

        def __init__(self, opts):
            pass


class Mockloader(object):
    """
    Mock of loader
    """
    flag = None
    functions = []	# ? does not have any effect on existing tests

    def __init__(self):
        self.opts = None
        self.lst = None

    def returners(self, opts, lst):
        """
        Mock of returners method
        """
        self.opts = opts
        self.lst = lst
        if self.flag:
            return {}
        return sysmod.__salt__

    def render(self, opts, lst):
        """
        Mock of returners method
        """
        self.opts = opts
        self.lst = lst
        return {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.state', Mockstate())
@patch('salt.runner', Mockrunner())
@patch('salt.loader', Mockloader())
class SysmodTestCase(TestCase):
    '''
    Test cases for salt.modules.sysmod
    '''
    # 'doc' function tests: 1

    def test_doc(self):
        '''
        Test if it return the docstrings for all modules.
        '''
        self.assertDictEqual(sysmod.doc(), sysmod.__salt__)

        self.assertDictEqual(sysmod.doc('sys.doc'), {'sys.doc': None})

    # 'state_doc' function tests: 1

    def test_state_doc(self):
        '''
        Test if it return the docstrings for all states.
        '''
        self.assertDictEqual(sysmod.state_doc(), sysmod.__salt__)

        self.assertDictEqual(sysmod.state_doc('sys.doc'), {'sys.doc': None})

    # 'runner_doc' function tests: 1

    def test_runner_doc(self):
        '''
        Test if it return the docstrings for all runners.
        '''
        self.assertDictEqual(sysmod.runner_doc(), sysmod.__salt__)

        self.assertDictEqual(sysmod.runner_doc('sys.doc'), {'sys.doc': None})

    # 'returner_doc' function tests: 1

    def test_returner_doc(self):
        '''
        Test if it return the docstrings for all returners.
        '''
        self.assertDictEqual(sysmod.returner_doc(), {})

        self.assertDictEqual(sysmod.returner_doc('sqlite3.get_*'), {})

    # 'renderer_doc' function tests: 1

    def test_renderer_doc(self):
        '''
        Test if it return the docstrings for all renderers.
        '''
        self.assertDictEqual(sysmod.renderer_doc(), {})

        self.assertDictEqual(sysmod.renderer_doc('c*', 'j*'), {})

    # 'list_functions' function tests: 1

    def test_list_functions(self):
        '''
        Test if it list the functions for all modules.
        '''
        self.assertListEqual(sysmod.list_functions(), _functions)

        self.assertListEqual(sysmod.list_functions('nonexist'), [])

        # list all functions in/given a specific module
        self.assertListEqual(sysmod.list_functions('sys'), ['sys.doc', 'sys.list_functions', 'sys.list_modules'])

        # globs can be used for both module names and function names:
        self.assertListEqual(sysmod.list_functions('sys*'), ['sys.doc', 'sys.list_functions', 'sys.list_modules', 'sysctl.get', 'sysctl.show', 'system.halt', 'system.reboot'])
        self.assertListEqual(sysmod.list_functions('sys.list*'), ['sys.list_functions', 'sys.list_modules'])

        # "list", or check for a specific function:
        self.assertListEqual(sysmod.list_functions('sys.list'), [])
        self.assertListEqual(sysmod.list_functions('exist.exist'), ['exist.exist'])

    # 'list_modules' function tests: 1

    def test_list_modules(self):
        '''
        Test if it list the modules loaded on the minion
        '''
        self.assertListEqual(sysmod.list_modules(), _modules)

        self.assertListEqual(sysmod.list_modules('nonexist'), [])

        self.assertListEqual(sysmod.list_modules('user'), ['user'])

        self.assertListEqual(sysmod.list_modules('s*'), ['sys', 'sysctl', 'system'])

    # 'reload_modules' function tests: 1

    def test_reload_modules(self):
        '''
        Test if it tell the minion to reload the execution modules
        '''
        self.assertTrue(sysmod.reload_modules())

    # 'argspec' function tests: 1

    def test_argspec(self):
        '''
        Test if it return the argument specification
        of functions in Salt execution modules.
        '''
        self.assertDictEqual(sysmod.argspec(), {})

    # 'state_argspec' function tests: 1

    def test_state_argspec(self):
        '''
        Test if it return the argument specification
        of functions in Salt state modules.
        '''
        self.assertDictEqual(sysmod.state_argspec(), {})

    # 'returner_argspec' function tests: 1

    def test_returner_argspec(self):
        '''
        Test if it return the argument specification
        of functions in Salt returner modules.
        '''
        self.assertDictEqual(sysmod.returner_argspec(), {})

    # 'runner_argspec' function tests: 1

    def test_runner_argspec(self):
        '''
        Test if it return the argument specification of functions in Salt runner
        modules.
        '''
        self.assertDictEqual(sysmod.runner_argspec(), {})

    # 'list_state_functions' function tests: 1

    def test_list_state_functions(self):
        '''
        Test if it list the functions for all state modules.
        '''
        self.assertListEqual(sysmod.list_state_functions(), _functions)

        self.assertListEqual(sysmod.list_state_functions('nonexist'), [])

        # list all functions in/given a specific module
        self.assertListEqual(sysmod.list_state_functions('sys'), ['sys.doc', 'sys.list_functions', 'sys.list_modules'])

        # globs can be used for both module names and function names:
        self.assertListEqual(sysmod.list_state_functions('sys*'), ['sys.doc', 'sys.list_functions', 'sys.list_modules', 'sysctl.get', 'sysctl.show', 'system.halt', 'system.reboot'])
        self.assertListEqual(sysmod.list_state_functions('sys.list*'), ['sys.list_functions', 'sys.list_modules'])

        # "list", or check for a specific function:
        self.assertListEqual(sysmod.list_state_functions('sys.list'), [])
        self.assertListEqual(sysmod.list_state_functions('exist.exist'), ['exist.exist'])

    # 'list_state_modules' function tests: 1

    def test_list_state_modules(self):
        '''
        Test if it list the modules loaded on the minion.
        '''
        self.assertListEqual(sysmod.list_state_modules(), _modules)

        self.assertListEqual(sysmod.list_state_modules('nonexist'), [])

        self.assertListEqual(sysmod.list_state_modules('user'), ['user'])

        self.assertListEqual(sysmod.list_state_modules('s*'), ['sys', 'sysctl', 'system'])

    # 'list_runners' function tests: 1

    def test_list_runners(self):
        '''
        Test if it list the runners loaded on the minion.
        '''
        self.assertListEqual(sysmod.list_runners(), _modules)

        self.assertListEqual(sysmod.list_runners('m*'), [])

    # 'list_runner_functions' function tests: 1

    def test_list_runner_functions(self):
        '''
        Test if it list the functions for all runner modules.
        '''
        self.assertListEqual(sysmod.list_runner_functions(), _functions)

        self.assertListEqual(sysmod.list_runner_functions('nonexist'), [])

        # list all functions in/given a specific module
        self.assertListEqual(sysmod.list_runner_functions('sys'), ['sys.doc', 'sys.list_functions', 'sys.list_modules'])

        # globs can be used for both module names and function names:
        self.assertListEqual(sysmod.list_runner_functions('sys*'), ['sys.doc', 'sys.list_functions', 'sys.list_modules', 'sysctl.get', 'sysctl.show', 'system.halt', 'system.reboot'])
        self.assertListEqual(sysmod.list_runner_functions('sys.list*'), ['sys.list_functions', 'sys.list_modules'])

        # "list", or check for a specific function:
        self.assertListEqual(sysmod.list_runner_functions('sys.list'), [])
        self.assertListEqual(sysmod.list_runner_functions('exist.exist'), ['exist.exist'])

    # 'list_returners' function tests: 1

    def test_list_returners(self):
        '''
        Test if it list the runners loaded on the minion
        '''
        Mockloader.flag = True
        self.assertListEqual(sysmod.list_returners(), [])

        self.assertListEqual(sysmod.list_returners('s*'), [])

    # 'list_returner_functions' function tests: 1

    def test_list_returner_functions(self):
        '''
        Test if it list the functions for all returner modules.
        '''
        self.assertListEqual(sysmod.list_returner_functions(), _functions)

        self.assertListEqual(sysmod.list_returner_functions('nonexist'), [])

        # list all functions in/given a specific module
        self.assertListEqual(sysmod.list_returner_functions('sys'), ['sys.doc', 'sys.list_functions', 'sys.list_modules'])

        # globs can be used for both module names and function names:
        self.assertListEqual(sysmod.list_returner_functions('sys*'), ['sys.doc', 'sys.list_functions', 'sys.list_modules', 'sysctl.get', 'sysctl.show', 'system.halt', 'system.reboot'])
        self.assertListEqual(sysmod.list_returner_functions('sys.list*'), ['sys.list_functions', 'sys.list_modules'])

        # "list", or check for a specific function:
        self.assertListEqual(sysmod.list_returner_functions('sys.list'), [])
        self.assertListEqual(sysmod.list_returner_functions('exist.exist'), ['exist.exist'])

    # 'list_renderers' function tests: 1

    def test_list_renderers(self):
        '''
        Test if it list the renderers loaded on the minion.
        '''
        self.assertListEqual(sysmod.list_renderers(), [])

        self.assertListEqual(sysmod.list_renderers('sqlite3.get_*'), [])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SysmodTestCase, needs_daemon=False)
