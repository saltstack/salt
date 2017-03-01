# -*- coding: utf-8 -*-
'''
:codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import sysmod


class MockDocstringable(object):
    def __init__(self, docstr):
        self.__doc__ = docstr

    def set_module_docstring(self, docstr):
        self.__globals__ = {'__doc__': docstr}


_modules = set()
_functions = [
    'exist.exist',

    'sys.doc', 'sys.list_functions', 'sys.list_modules',
    'sysctl.get', 'sysctl.show',
    'system.halt', 'system.reboot',

    'udev.name', 'udev.path',
    'user.add', 'user.info', 'user.rename',
]
_docstrings = {}
_statedocstrings = {}

sysmod.__salt__ = {}
sysmod.__opts__ = {}


for func in _functions:
    docstring = 'docstring for {0}'.format(func)

    sysmod.__salt__[func] = MockDocstringable(docstring)
    _docstrings[func] = docstring

    module = func.split('.')[0]
    _statedocstrings[func] = docstring
    _statedocstrings[module] = 'docstring for {0}'.format(module)

    _modules.add(func.split('.')[0])

_modules = sorted(list(_modules))


class Mockstate(object):
    """
    Mock of State
    """
    class State(object):
        """
        Mock state functions
        """
        states = {}
        for func in _functions:
            docstring = 'docstring for {0}'.format(func)
            mock = MockDocstringable(docstring)
            mock.set_module_docstring('docstring for {0}'.format(func.split('.')[0]))
            states[func] = mock

        def __init__(self, opts):
            pass


class Mockrunner(object):
    """
    Mock of runner
    """
    class Runner(object):
        """
        Mock runner functions
        """
        functions = sysmod.__salt__

        def __init__(self, opts):
            pass


class Mockloader(object):
    """
    Mock of loader
    """
    functions = []  # ? does not have any effect on existing tests

    def __init__(self):
        pass

    def returners(self, opts, lst):
        """
        Mock returner functions
        """
        return sysmod.__salt__

    def render(self, opts, lst):
        """
        Mock renderers
        """
        return sysmod.__salt__  # renderers do not have '.'s; but whatever. This is for convenience


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.state', Mockstate())
@patch('salt.runner', Mockrunner())
@patch('salt.loader', Mockloader())
class SysmodTestCase(TestCase):
    '''
    Test cases for salt.modules.sysmod
    '''
    # 'doc' function tests: 2

    def test_doc(self):
        '''
        Test if it returns the docstrings for all modules.
        '''
        self.assertDictEqual(sysmod.doc(), _docstrings)

        self.assertDictEqual(sysmod.doc('sys.doc'), {'sys.doc': 'docstring for sys.doc'})

    # 'state_doc' function tests: 2

    def test_state_doc(self):
        '''
        Test if it returns the docstrings for all states.
        '''
        self.assertDictEqual(sysmod.state_doc(), _statedocstrings)

        self.assertDictEqual(sysmod.state_doc('sys.doc'), {'sys': 'docstring for sys', 'sys.doc': 'docstring for sys.doc'})

    # 'runner_doc' function tests: 2

    def test_runner_doc(self):
        '''
        Test if it returns the docstrings for all runners.
        '''
        self.assertDictEqual(sysmod.runner_doc(), _docstrings)

        self.assertDictEqual(sysmod.runner_doc('sys.doc'), {'sys.doc': 'docstring for sys.doc'})

    # 'returner_doc' function tests: 2

    def test_returner_doc(self):
        '''
        Test if it returns the docstrings for all returners.
        '''
        self.assertDictEqual(sysmod.returner_doc(), _docstrings)

        self.assertDictEqual(sysmod.returner_doc('sys.doc'), {'sys.doc': 'docstring for sys.doc'})

    # 'renderer_doc' function tests: 2

    def test_renderer_doc(self):
        '''
        Test if it returns the docstrings for all renderers.
        '''
        self.assertDictEqual(sysmod.renderer_doc(), _docstrings)

        self.assertDictEqual(sysmod.renderer_doc('sys.doc'), {'sys.doc': 'docstring for sys.doc'})

    # 'list_functions' function tests: 7

    def test_list_functions(self):
        '''
        Test if it lists the functions for all modules.
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

    # 'list_modules' function tests: 4

    def test_list_modules(self):
        '''
        Test if it lists the modules loaded on the minion
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

    # 'list_state_functions' function tests: 7

    def test_list_state_functions(self):
        '''
        Test if it lists the functions for all state modules.
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

    # 'list_state_modules' function tests: 4

    def test_list_state_modules(self):
        '''
        Test if it lists the modules loaded on the minion.
        '''
        self.assertListEqual(sysmod.list_state_modules(), _modules)

        self.assertListEqual(sysmod.list_state_modules('nonexist'), [])

        self.assertListEqual(sysmod.list_state_modules('user'), ['user'])

        self.assertListEqual(sysmod.list_state_modules('s*'), ['sys', 'sysctl', 'system'])

    # 'list_runners' function tests: 4

    def test_list_runners(self):
        '''
        Test if it list the runners loaded on the minion.
        '''
        self.assertListEqual(sysmod.list_runners(), _modules)

        self.assertListEqual(sysmod.list_runners('nonexist'), [])

        self.assertListEqual(sysmod.list_runners('user'), ['user'])

        self.assertListEqual(sysmod.list_runners('s*'), ['sys', 'sysctl', 'system'])

    # 'list_runner_functions' function tests: 7

    def test_list_runner_functions(self):
        '''
        Test if it lists the functions for all runner modules.
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

    # 'list_returners' function tests: 4

    def test_list_returners(self):
        '''
        Test if it lists the returners loaded on the minion
        '''
        self.assertListEqual(sysmod.list_returners(), _modules)

        self.assertListEqual(sysmod.list_returners('nonexist'), [])

        self.assertListEqual(sysmod.list_returners('user'), ['user'])

        self.assertListEqual(sysmod.list_returners('s*'), ['sys', 'sysctl', 'system'])

    # 'list_returner_functions' function tests: 7

    def test_list_returner_functions(self):
        '''
        Test if it lists the functions for all returner modules.
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

    # 'list_renderers' function tests: 4

    def test_list_renderers(self):
        '''
        Test if it list the renderers loaded on the minion.
        '''
        self.assertListEqual(sysmod.list_renderers(), _functions)

        self.assertListEqual(sysmod.list_renderers('nonexist'), [])

        self.assertListEqual(sysmod.list_renderers('user.info'), ['user.info'])

        self.assertListEqual(sysmod.list_renderers('syst*'), ['system.halt', 'system.reboot'])
