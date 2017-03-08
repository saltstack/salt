# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas (nicole@saltstack.com)`
'''

# Import Python Libs
from __future__ import absolute_import
from inspect import ArgSpec

# Import Salt Libs
from salt.states import module

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

CMD = 'foo.bar'
MOCK = MagicMock()
module.__salt__ = {CMD: MOCK}
module.__opts__ = {'test': False}


def _mocked_func_named(name, names=('Fred', 'Swen',)):
    '''
    Mocked function with named defaults.

    :param name:
    :param names:
    :return:
    '''
    return {'name': name, 'names': names}

@skipIf(NO_MOCK, NO_MOCK_REASON)
class ModuleStateTest(TestCase):
    '''
    Tests module state (salt/states/module.py)
    '''

    aspec = ArgSpec(args=['hello', 'world'],
                    varargs=None,
                    keywords=None,
                    defaults=False)

    def test_xrun_module_not_available(self):
        '''
        Tests the return of module.xrun state when the module function is not available.
        :return:
        '''
        with patch.dict(module.__salt__, {}, clear=True):
            ret = module.xrun(**{CMD: None})
            assert ret['comment'] == "Module function '{0}' is not available".format(CMD)
            assert not ret['result']

    def test_xrun_testmode(self):
        '''
        Tests the return of the module.xrun state when test=True is passed.
        :return:
        '''
        with patch.dict(module.__opts__, {'test': True}):
            ret = module.xrun(**{CMD: None})
            assert ret['comment'] == "Module function '{0}' is set to execute".format(CMD)
            assert ret['result']

    def test_xrun_missing_arg(self):
        '''
        Tests the return of module.xrun state when arguments are missing
        :return:
        '''
        with patch.dict(module.__salt__, {CMD: _mocked_func_named}):
            ret = module.xrun(**{CMD: None})
            assert ret['comment'] == "'{0}' failed: Missing arguments: name".format(CMD)


    def test_module_run_module_not_available(self):
        '''
        Tests the return of module.run state when the module function
        name isn't available
        '''
        with patch.dict(module.__salt__, {}, clear=True):
            ret = module.run(CMD)
            comment = 'Module function {0} is not available'.format(CMD)
            self.assertEqual(ret['comment'], comment)
            self.assertFalse(ret['result'])

    def test_module_run_test_true(self):
        '''
        Tests the return of module.run state when test=True is passed in
        '''
        with patch.dict(module.__opts__, {'test': True}):
            ret = module.run(CMD)
            comment = 'Module function {0} is set to execute'.format(CMD)
            self.assertEqual(ret['comment'], comment)

    @patch('salt.utils.args.get_function_argspec', MagicMock(return_value=aspec))
    def test_module_run_missing_arg(self):
        '''
        Tests the return of module.run state when arguments are missing
        '''
        ret = module.run(CMD)
        comment = 'The following arguments are missing:'
        self.assertIn(comment, ret['comment'])
        self.assertIn('world', ret['comment'])
        self.assertIn('hello', ret['comment'])
