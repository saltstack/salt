# -*- coding: utf-8 -*-
'''Unit test for saltcheck execution module'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import os.path

try:
    import salt.modules.saltcheck as saltcheck
    import salt.config
    import salt.syspaths as syspaths
except:
    raise

# Import Salt Testing Libs
try:
    from tests.support.mixins import LoaderModuleMockMixin
    from tests.support.unit import skipIf, TestCase
    from tests.support.mock import (
        MagicMock,
        patch,
        NO_MOCK,
        NO_MOCK_REASON
    )
except:
    raise


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LinuxSysctlTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.saltcheck module
    '''

    def setup_loader_modules(self):
        # Setting the environment to be local
        local_opts = salt.config.minion_config(
            os.path.join(syspaths.CONFIG_DIR, 'minion'))
        local_opts['file_client'] = 'local'
        patcher = patch('salt.config.minion_config',
                        MagicMock(return_value=local_opts))
        patcher.start()
        self.addCleanup(patcher.stop)
        return {saltcheck: {}}

    def test_call_salt_command(self):
        '''test simple test.echo module'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'sys.list_modules': MagicMock(return_value=['module1']),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            returned = sc_instance.call_salt_command(fun="test.echo", args=['hello'], kwargs=None)
            self.assertEqual(returned, 'hello')

    def test_update_master_cache(self):
        '''test master cache'''
        self.assertTrue(saltcheck.update_master_cache)

    def test_call_salt_command2(self):
        '''test simple test.echo module again'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'sys.list_modules': MagicMock(return_value=['module1']),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            returned = sc_instance.call_salt_command(fun="test.echo", args=['hello'], kwargs=None)
            self.assertNotEqual(returned, 'not-hello')

    def test__assert_equal1(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = {'a': 1, 'b': 2}
            bbb = {'a': 1, 'b': 2}
            mybool = sc_instance._SaltCheck__assert_equal(aaa, bbb)
            self.assertTrue(mybool)

    def test__assert_equal2(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_equal(False, True)
            self.assertNotEqual(mybool, True)

    def test__assert_not_equal1(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = {'a': 1, 'b': 2}
            bbb = {'a': 1, 'b': 2, 'c': 3}
            mybool = sc_instance._SaltCheck__assert_not_equal(aaa, bbb)
            self.assertTrue(mybool)

    def test__assert_not_equal2(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = {'a': 1, 'b': 2}
            bbb = {'a': 1, 'b': 2}
            mybool = sc_instance._SaltCheck__assert_not_equal(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_true1(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_equal(True, True)
            self.assertTrue(mybool)

    def test__assert_true2(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_equal(False, True)
            self.assertNotEqual(mybool, True)

    def test__assert_false1(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_false(False)
            self.assertTrue(mybool)

    def test__assert_false2(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_false(True)
            self.assertNotEqual(mybool, True)

    def test__assert_in1(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = "bob"
            mylist = ['alice', 'bob', 'charles', 'dana']
            mybool = sc_instance._SaltCheck__assert_in(aaa, mylist)
            self.assertTrue(mybool, True)

    def test__assert_in2(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = "elaine"
            mylist = ['alice', 'bob', 'charles', 'dana']
            mybool = sc_instance._SaltCheck__assert_in(aaa, mylist)
            self.assertNotEqual(mybool, True)

    def test__assert_not_in1(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = "elaine"
            mylist = ['alice', 'bob', 'charles', 'dana']
            mybool = sc_instance._SaltCheck__assert_not_in(aaa, mylist)
            self.assertTrue(mybool, True)

    def test__assert_not_in2(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = "bob"
            mylist = ['alice', 'bob', 'charles', 'dana']
            mybool = sc_instance._SaltCheck__assert_not_in(aaa, mylist)
            self.assertNotEqual(mybool, True)

    def test__assert_greater1(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 110
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_greater(aaa, bbb)
            self.assertTrue(mybool, True)

    def test__assert_greater2(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 110
            mybool = sc_instance._SaltCheck__assert_greater(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_greater3(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_greater(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_greater_equal1(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 110
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_greater_equal(aaa, bbb)
            self.assertTrue(mybool, True)

    def test__assert_greater_equal2(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 110
            mybool = sc_instance._SaltCheck__assert_greater_equal(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_greater_equal3(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_greater_equal(aaa, bbb)
            self.assertEqual(mybool, 'Pass')

    def test__assert_less1(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 99
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_less(aaa, bbb)
            self.assertTrue(mybool, True)

    def test__assert_less2(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 110
            bbb = 99
            mybool = sc_instance._SaltCheck__assert_less(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_less3(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_less(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_less_equal1(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 99
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_less_equal(aaa, bbb)
            self.assertTrue(mybool, True)

    def test__assert_less_equal2(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 110
            bbb = 99
            mybool = sc_instance._SaltCheck__assert_less_equal(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_less_equal3(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_less_equal(aaa, bbb)
            self.assertEqual(mybool, 'Pass')

    def test_run_test_1(self):
        '''test'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'sys.list_modules': MagicMock(return_value=['test']),
                                             'sys.list_functions': MagicMock(return_value=['test.echo']),
                                             'cp.cache_master': MagicMock(return_value=[True])}):
            returned = saltcheck.run_test(test={"module_and_function": "test.echo",
                                                "assertion": "assertEqual",
                                                "expected-return": "This works!",
                                                "args": ["This works!"]
                                                })
            self.assertEqual(returned, 'Pass')
