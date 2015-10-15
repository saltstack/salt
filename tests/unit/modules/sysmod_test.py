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

sysmod.__salt__ = {}
sysmod.__opts__ = {}


class Mockstate(object):
    """
    Mock of State
    """
    class State(object):
        """
        Mock of State
        """
        states = []

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
        functions = []

        def __init__(self, opts):
            pass


class Mockloader(object):
    """
    Mock of loader
    """
    flag = None
    functions = []

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
        return []

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
        self.assertDictEqual(sysmod.doc(), {})

    # 'state_doc' function tests: 1

    def test_state_doc(self):
        '''
        Test if it return the docstrings for all states.
        '''
        self.assertDictEqual(sysmod.state_doc(), {})

        self.assertDictEqual(sysmod.state_doc('sys.doc'), {})

    # 'runner_doc' function tests: 1

    def test_runner_doc(self):
        '''
        Test if it return the docstrings for all runners.
        '''
        self.assertDictEqual(sysmod.runner_doc(), {})

        self.assertDictEqual(sysmod.runner_doc('sys.doc'), {})

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
        self.assertListEqual(sysmod.list_functions(), [])

        self.assertListEqual(sysmod.list_functions('sys'), [])

    # 'list_modules' function tests: 1

    def test_list_modules(self):
        '''
        Test if it list the modules loaded on the minion
        '''
        self.assertListEqual(sysmod.list_modules(), [])

        self.assertListEqual(sysmod.list_modules('s*'), [])

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
        self.assertListEqual(sysmod.list_state_functions(), [])

        self.assertListEqual(sysmod.list_state_functions('file.s*'), [])

    # 'list_state_modules' function tests: 1

    def test_list_state_modules(self):
        '''
        Test if it list the modules loaded on the minion.
        '''
        self.assertListEqual(sysmod.list_state_modules(), [])

        self.assertListEqual(sysmod.list_state_modules('mysql_*'), [])

    # 'list_runners' function tests: 1

    def test_list_runners(self):
        '''
        Test if it list the runners loaded on the minion.
        '''
        self.assertListEqual(sysmod.list_runners(), [])

        self.assertListEqual(sysmod.list_runners('m*'), [])

    # 'list_runner_functions' function tests: 1

    def test_list_runner_functions(self):
        '''
        Test if it list the functions for all runner modules.
        '''
        self.assertListEqual(sysmod.list_runner_functions(), [])

        self.assertListEqual(sysmod.list_runner_functions('state.*'), [])

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
        self.assertListEqual(sysmod.list_returner_functions(), [])

        self.assertListEqual(sysmod.list_returner_functions('sqlite3.get_*'),
                             [])

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
