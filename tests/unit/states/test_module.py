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
            cmd = {CMD: None}
            ret = module.xrun(**cmd)
            assert ret['comment'] == "Module function '{0}' is not available".format(cmd.keys()[0])
            assert not ret['result']

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
