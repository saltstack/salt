"""Unit test for saltcheck execution module"""

import os.path

import pytest

import salt.config
import salt.modules.saltcheck as saltcheck
import salt.syspaths as syspaths
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SaltcheckTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.saltcheck module
    """

    def setup_loader_modules(self):
        # Setting the environment to be local
        local_opts = salt.config.minion_config(
            os.path.join(syspaths.CONFIG_DIR, "minion")
        )
        local_opts["file_client"] = "local"
        local_opts["conf_file"] = "/etc/salt/minion"
        patcher = patch("salt.config.minion_config", MagicMock(return_value=local_opts))
        patcher.start()
        self.addCleanup(patcher.stop)
        return {saltcheck: {"__opts__": local_opts}}

    @pytest.mark.slow_test
    def test_call_salt_command(self):
        """test simple test.echo module"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "sys.list_modules": MagicMock(return_value=["module1"]),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            returned = sc_instance._call_salt_command(
                fun="test.echo", args=["hello"], kwargs=None
            )
            self.assertEqual(returned, "hello")

    @pytest.mark.slow_test
    def test_call_salt_command2(self):
        """test simple test.echo module again"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "sys.list_modules": MagicMock(return_value=["module1"]),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            returned = sc_instance._call_salt_command(
                fun="test.echo", args=["hello"], kwargs=None
            )
            self.assertNotEqual(returned, "not-hello")

    def test_call_saltcheck_with_proxy(self):
        """test fail to load saltcheck module if proxy"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "sys.list_modules": MagicMock(return_value=["module1"]),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ), patch("salt.utils.platform.is_proxy", MagicMock(return_value=[True])):
            ret, message = saltcheck.__virtual__()
            self.assertFalse(ret)
            self.assertEqual(
                message,
                "The saltcheck execution module failed to load: only available on"
                " minions.",
            )

    def test__assert_equal1(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = {"a": 1, "b": 2}
            bbb = {"a": 1, "b": 2}
            mybool = sc_instance._SaltCheck__assert_equal(aaa, bbb)
            self.assertTrue(mybool)

    def test__assert_equal2(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_equal(False, True)
            self.assertNotEqual(mybool, True)

    def test__assert_not_equal1(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = {"a": 1, "b": 2}
            bbb = {"a": 1, "b": 2, "c": 3}
            mybool = sc_instance._SaltCheck__assert_not_equal(aaa, bbb)
            self.assertTrue(mybool)

    def test__assert_not_equal2(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = {"a": 1, "b": 2}
            bbb = {"a": 1, "b": 2}
            mybool = sc_instance._SaltCheck__assert_not_equal(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_true1(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_equal(True, True)
            self.assertTrue(mybool)

    def test__assert_true2(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_equal(False, True)
            self.assertNotEqual(mybool, True)

    def test__assert_false1(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_false(False)
            self.assertTrue(mybool)

    def test__assert_false2(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_false(True)
            self.assertNotEqual(mybool, True)

    def test__assert_in1(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = "bob"
            mylist = ["alice", "bob", "charles", "dana"]
            mybool = sc_instance._SaltCheck__assert_in(aaa, mylist)
            self.assertTrue(mybool, True)

    def test__assert_in2(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = "elaine"
            mylist = ["alice", "bob", "charles", "dana"]
            mybool = sc_instance._SaltCheck__assert_in(aaa, mylist)
            self.assertNotEqual(mybool, True)

    def test__assert_not_in1(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = "elaine"
            mylist = ["alice", "bob", "charles", "dana"]
            mybool = sc_instance._SaltCheck__assert_not_in(aaa, mylist)
            self.assertTrue(mybool, True)

    def test__assert_not_in2(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = "bob"
            mylist = ["alice", "bob", "charles", "dana"]
            mybool = sc_instance._SaltCheck__assert_not_in(aaa, mylist)
            self.assertNotEqual(mybool, True)

    def test__assert_greater1(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 110
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_greater(aaa, bbb)
            self.assertTrue(mybool, True)

    def test__assert_greater2(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 110
            mybool = sc_instance._SaltCheck__assert_greater(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_greater3(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_greater(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_greater_equal1(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 110
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_greater_equal(aaa, bbb)
            self.assertTrue(mybool, True)

    def test__assert_greater_equal2(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 110
            mybool = sc_instance._SaltCheck__assert_greater_equal(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_greater_equal3(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_greater_equal(aaa, bbb)
            self.assertEqual(mybool, "Pass")

    def test__assert_less1(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 99
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_less(aaa, bbb)
            self.assertTrue(mybool, True)

    def test__assert_less2(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 110
            bbb = 99
            mybool = sc_instance._SaltCheck__assert_less(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_less3(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_less(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_less_equal1(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 99
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_less_equal(aaa, bbb)
            self.assertTrue(mybool, True)

    def test__assert_less_equal2(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 110
            bbb = 99
            mybool = sc_instance._SaltCheck__assert_less_equal(aaa, bbb)
            self.assertNotEqual(mybool, True)

    def test__assert_less_equal3(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            aaa = 100
            bbb = 100
            mybool = sc_instance._SaltCheck__assert_less_equal(aaa, bbb)
            self.assertEqual(mybool, "Pass")

    def test__assert_empty(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_empty("")
            self.assertEqual(mybool, "Pass")

    def test__assert_empty_fail(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_empty("data")
            self.assertNotEqual(mybool, "Pass")

    def test__assert__not_empty(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_not_empty("data")
            self.assertEqual(mybool, "Pass")

    def test__assert__not_empty_fail(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            sc_instance = saltcheck.SaltCheck()
            mybool = sc_instance._SaltCheck__assert_not_empty("")
            self.assertNotEqual(mybool, "Pass")

    @pytest.mark.slow_test
    def test_run_test_1(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "sys.list_modules": MagicMock(return_value=["test"]),
                "sys.list_functions": MagicMock(return_value=["test.echo"]),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            returned = saltcheck.run_test(
                test={
                    "module_and_function": "test.echo",
                    "assertion": "assertEqual",
                    "expected_return": "This works!",
                    "args": ["This works!"],
                }
            )
            self.assertEqual(returned["status"], "Pass")

    def test_run_test_muliassert(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "sys.list_modules": MagicMock(return_value=["test"]),
                "sys.list_functions": MagicMock(return_value=["test.echo"]),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            returned = saltcheck.run_test(
                test={
                    "module_and_function": "test.echo",
                    "assertions": [
                        {"assertion": "assertEqual", "expected_return": "This works!"},
                        {"assertion": "assertEqual", "expected_return": "This works!"},
                    ],
                    "args": ["This works!"],
                }
            )
            self.assertEqual(returned["status"], "Pass")

    def test_run_test_muliassert_failure(self):
        """test"""
        with patch.dict(
            saltcheck.__salt__,
            {
                "config.get": MagicMock(return_value=True),
                "sys.list_modules": MagicMock(return_value=["test"]),
                "sys.list_functions": MagicMock(return_value=["test.echo"]),
                "cp.cache_master": MagicMock(return_value=[True]),
            },
        ):
            returned = saltcheck.run_test(
                test={
                    "module_and_function": "test.echo",
                    "assertions": [
                        {"assertion": "assertEqual", "expected_return": "WRONG"},
                        {"assertion": "assertEqual", "expected_return": "This works!"},
                    ],
                    "args": ["This works!"],
                }
            )
            self.assertEqual(returned["status"], "Fail")

    def test_report_highstate_tests(self):
        """test report_highstate_tests"""
        expected_output = {
            "TEST REPORT RESULTS": {
                "States missing tests": ["state1"],
                "Missing Tests": 1,
                "States with tests": ["found"],
            }
        }
        with patch("salt.modules.saltcheck._get_top_states") as mocked_get_top:
            mocked_get_top.return_value = ["state1", "found"]
            with patch("salt.modules.saltcheck.StateTestLoader") as mocked_stl:
                instance = mocked_stl.return_value
                instance.found_states = ["found"]
                returned = saltcheck.report_highstate_tests()
                self.assertEqual(returned, expected_output)

    def test_validation(self):
        """test validation of tests"""
        sc_instance = saltcheck.SaltCheck()

        # Fail on empty test
        test_dict = {}
        expected_return = False
        val_ret = sc_instance._SaltCheck__is_valid_test(test_dict)
        self.assertEqual(val_ret, expected_return)

        # Succeed on standard test
        test_dict = {
            "module_and_function": "test.echo",
            "args": ["hello"],
            "kwargs": {},
            "assertion": "assertEqual",
            "expected_return": "hello",
        }
        expected_return = True
        with patch.dict(
            saltcheck.__salt__,
            {
                "sys.list_modules": MagicMock(return_value=["test"]),
                "sys.list_functions": MagicMock(return_value=["test.echo"]),
            },
        ):
            val_ret = sc_instance._SaltCheck__is_valid_test(test_dict)
            self.assertEqual(val_ret, expected_return)

        # Succeed on standard test with older expected-return syntax
        test_dict = {
            "module_and_function": "test.echo",
            "args": ["hello"],
            "kwargs": {},
            "assertion": "assertEqual",
            "expected-return": "hello",
        }
        expected_return = True
        with patch.dict(
            saltcheck.__salt__,
            {
                "sys.list_modules": MagicMock(return_value=["test"]),
                "sys.list_functions": MagicMock(return_value=["test.echo"]),
            },
        ):
            val_ret = sc_instance._SaltCheck__is_valid_test(test_dict)
            self.assertEqual(val_ret, expected_return)

        # Do not require expected_return for some assertions
        assertions = ["assertEmpty", "assertNotEmpty", "assertTrue", "assertFalse"]
        for assertion in assertions:
            test_dict = {"module_and_function": "test.echo", "args": ["hello"]}
            test_dict["assertion"] = assertion
            expected_return = True
            with patch.dict(
                saltcheck.__salt__,
                {
                    "sys.list_modules": MagicMock(return_value=["test"]),
                    "sys.list_functions": MagicMock(return_value=["test.echo"]),
                },
            ):
                val_ret = sc_instance._SaltCheck__is_valid_test(test_dict)
                self.assertEqual(val_ret, expected_return)

        # Fail on invalid module
        test_dict = {
            "module_and_function": "broken.echo",
            "args": ["hello"],
            "kwargs": {},
            "assertion": "assertEqual",
            "expected_return": "hello",
        }
        expected_return = False
        with patch.dict(
            saltcheck.__salt__,
            {
                "sys.list_modules": MagicMock(return_value=["test"]),
                "sys.list_functions": MagicMock(return_value=["test.echo"]),
            },
        ):
            val_ret = sc_instance._SaltCheck__is_valid_test(test_dict)
            self.assertEqual(val_ret, expected_return)

        # Fail on invalid function
        test_dict = {
            "module_and_function": "test.broken",
            "args": ["hello"],
            "kwargs": {},
            "assertion": "assertEqual",
            "expected_return": "hello",
        }
        expected_return = False
        with patch.dict(
            saltcheck.__salt__,
            {
                "sys.list_modules": MagicMock(return_value=["test"]),
                "sys.list_functions": MagicMock(return_value=["test.echo"]),
            },
        ):
            val_ret = sc_instance._SaltCheck__is_valid_test(test_dict)
            self.assertEqual(val_ret, expected_return)

        # Fail on missing expected_return
        test_dict = {
            "module_and_function": "test.echo",
            "args": ["hello"],
            "kwargs": {},
            "assertion": "assertEqual",
        }
        expected_return = False
        with patch.dict(
            saltcheck.__salt__,
            {
                "sys.list_modules": MagicMock(return_value=["test"]),
                "sys.list_functions": MagicMock(return_value=["test.echo"]),
            },
        ):
            val_ret = sc_instance._SaltCheck__is_valid_test(test_dict)
            self.assertEqual(val_ret, expected_return)

        # Fail on empty expected_return
        test_dict = {
            "module_and_function": "test.echo",
            "args": ["hello"],
            "kwargs": {},
            "assertion": "assertEqual",
            "expected_return": None,
        }
        expected_return = False
        with patch.dict(
            saltcheck.__salt__,
            {
                "sys.list_modules": MagicMock(return_value=["test"]),
                "sys.list_functions": MagicMock(return_value=["test.echo"]),
            },
        ):
            val_ret = sc_instance._SaltCheck__is_valid_test(test_dict)
            self.assertEqual(val_ret, expected_return)

        # Succeed on m_and_f saltcheck.state_apply with only args
        test_dict = {"module_and_function": "saltcheck.state_apply", "args": ["common"]}
        expected_return = True
        with patch.dict(
            saltcheck.__salt__,
            {
                "sys.list_modules": MagicMock(return_value=["saltcheck"]),
                "sys.list_functions": MagicMock(return_value=["saltcheck.state_apply"]),
            },
        ):
            val_ret = sc_instance._SaltCheck__is_valid_test(test_dict)
            self.assertEqual(val_ret, expected_return)

        # Succeed on multiple assertions
        test_dict = {
            "module_and_function": "test.echo",
            "args": ["somearg"],
            "assertions": [
                {
                    "assertion": "assertEqual",
                    "assertion_section": "0:program",
                    "expected_return": "systemd-resolve",
                },
                {
                    "assertion": "assertEqual",
                    "assertion_section": "0:proto",
                    "expected_return": "udp",
                },
            ],
        }
        expected_return = True
        with patch.dict(
            saltcheck.__salt__,
            {
                "sys.list_modules": MagicMock(return_value=["test"]),
                "sys.list_functions": MagicMock(return_value=["test.echo"]),
            },
        ):
            val_ret = sc_instance._SaltCheck__is_valid_test(test_dict)
            self.assertEqual(val_ret, expected_return)

    def test_sls_path_generation(self):
        """test generation of sls paths"""
        with patch.dict(
            saltcheck.__salt__,
            {"config.get": MagicMock(return_value="saltcheck-tests")},
        ):
            testLoader = saltcheck.StateTestLoader()

            state_name = "teststate"
            expected_return = [
                "salt://teststate/saltcheck-tests",
                "salt:///saltcheck-tests",
            ]
            ret = testLoader._generate_sls_path(state_name)
            self.assertEqual(ret, expected_return)

            state_name = "teststate.long.path"
            expected_return = [
                "salt://teststate/long/path/saltcheck-tests",
                "salt://teststate/long/saltcheck-tests",
                "salt://teststate/saltcheck-tests",
            ]
            ret = testLoader._generate_sls_path(state_name)
            self.assertEqual(ret, expected_return)

            state_name = "teststate.really.long.path"
            expected_return = [
                "salt://teststate/really/long/path/saltcheck-tests",
                "salt://teststate/really/long/saltcheck-tests",
                "salt://teststate/saltcheck-tests",
            ]
            ret = testLoader._generate_sls_path(state_name)
            self.assertEqual(ret, expected_return)

    def test_generate_output(self):
        # passing states
        sc_results = {
            "a_state": {
                "test_id1": {"status": "Pass", "duration": 1.987},
                "test_id2": {"status": "Pass", "duration": 1.123},
            }
        }
        expected_output = [
            {
                "a_state": {
                    "test_id1": {"status": "Pass", "duration": 1.987},
                    "test_id2": {"status": "Pass", "duration": 1.123},
                }
            },
            {
                "TEST RESULTS": {
                    "Execution Time": 3.11,
                    "Passed": 2,
                    "Failed": 0,
                    "Skipped": 0,
                    "Missing Tests": 0,
                }
            },
        ]
        ret = saltcheck._generate_out_list(sc_results)
        self.assertEqual(ret, expected_output)

        # Skipped
        sc_results = {
            "a_state": {
                "test_id1": {"status": "Skip", "duration": 1.987},
                "test_id2": {"status": "Pass", "duration": 1.123},
            }
        }
        expected_output = [
            {
                "a_state": {
                    "test_id1": {"status": "Skip", "duration": 1.987},
                    "test_id2": {"status": "Pass", "duration": 1.123},
                }
            },
            {
                "TEST RESULTS": {
                    "Execution Time": 3.11,
                    "Passed": 1,
                    "Failed": 0,
                    "Skipped": 1,
                    "Missing Tests": 0,
                }
            },
        ]
        ret = saltcheck._generate_out_list(sc_results)
        self.assertEqual(ret, expected_output)

        # Failed (does not test setting __context__)
        sc_results = {
            "a_state": {
                "test_id1": {"status": "Failed", "duration": 1.987},
                "test_id2": {"status": "Pass", "duration": 1.123},
            }
        }
        expected_output = [
            {
                "a_state": {
                    "test_id1": {"status": "Failed", "duration": 1.987},
                    "test_id2": {"status": "Pass", "duration": 1.123},
                }
            },
            {
                "TEST RESULTS": {
                    "Execution Time": 3.11,
                    "Passed": 1,
                    "Failed": 1,
                    "Skipped": 0,
                    "Missing Tests": 0,
                }
            },
        ]
        ret = saltcheck._generate_out_list(sc_results)
        self.assertEqual(ret, expected_output)

        # missing states
        sc_results = {
            "a_state": {
                "test_id1": {"status": "Pass", "duration": 1.987},
                "test_id2": {"status": "Pass", "duration": 1.123},
            },
            "b_state": {},
        }
        expected_output = [
            {
                "a_state": {
                    "test_id1": {"status": "Pass", "duration": 1.987},
                    "test_id2": {"status": "Pass", "duration": 1.123},
                }
            },
            {"b_state": {}},
            {
                "TEST RESULTS": {
                    "Execution Time": 3.11,
                    "Passed": 2,
                    "Failed": 0,
                    "Skipped": 0,
                    "Missing Tests": 1,
                }
            },
        ]
        ret = saltcheck._generate_out_list(sc_results)
        self.assertEqual(ret, expected_output)

        # Failed with only_fails
        sc_results = {
            "a_state": {
                "test_id1": {
                    "assertion1": {
                        "status": "Pass",
                        "module.function [args]": 'cmd.run ["ls /etc/salt/master"]',
                        "saltcheck assertion": "IS NOT EMPTY /etc/salt/master",
                    },
                    "assertion2": {
                        "status": "Pass",
                        "module.function [args]": 'cmd.run ["ls /etc/salt/master"]',
                        "saltcheck assertion": "master IN /etc/salt/master",
                    },
                    "status": "Pass",
                    "duration": 1.4383,
                },
                "test_id2": {
                    "assertion1": {"status": "Fail: /etc/salt/master is not empty"},
                    "status": "Fail",
                    "duration": 0.308,
                },
                "test_id3": {
                    "assertion1": {"status": "Fail: /etc/salt/master is not empty"},
                    "status": "Fail",
                    "duration": 0.3073,
                },
            },
            "b_state": {
                "test_id4": {
                    "assertion1": {
                        "status": "Pass",
                        "module.function [args]": 'cmd.run ["ls /etc/salt/master"]',
                        "saltcheck assertion": "IS NOT EMPTY /etc/salt/master",
                    },
                    "assertion2": {
                        "status": "Pass",
                        "module.function [args]": 'cmd.run ["ls /etc/salt/master"]',
                        "saltcheck assertion": "master IN /etc/salt/master",
                    },
                    "status": "Pass",
                    "duration": 0.3057,
                },
                "test_id5": {
                    "assertion1": {"status": "Fail: /etc/salt/master is not empty"},
                    "status": "Fail",
                    "duration": 0.3066,
                },
                "test_id6": {
                    "assertion1": {"status": "Fail: /etc/salt/master is not empty"},
                    "status": "Fail",
                    "duration": 0.3076,
                },
            },
        }
        expected_output = [
            {
                "a_state": {
                    "test_id2": {
                        "assertion1": {"status": "Fail: /etc/salt/master is not empty"},
                        "status": "Fail",
                        "duration": 0.308,
                    },
                    "test_id3": {
                        "assertion1": {"status": "Fail: /etc/salt/master is not empty"},
                        "status": "Fail",
                        "duration": 0.3073,
                    },
                }
            },
            {
                "b_state": {
                    "test_id5": {
                        "assertion1": {"status": "Fail: /etc/salt/master is not empty"},
                        "status": "Fail",
                        "duration": 0.3066,
                    },
                    "test_id6": {
                        "assertion1": {"status": "Fail: /etc/salt/master is not empty"},
                        "status": "Fail",
                        "duration": 0.3076,
                    },
                }
            },
            {
                "TEST RESULTS": {
                    "Execution Time": 2.9735,
                    "Passed": 2,
                    "Failed": 4,
                    "Skipped": 0,
                    "Missing Tests": 0,
                }
            },
        ]
        ret = saltcheck._generate_out_list(sc_results, only_fails=True)
        self.assertEqual(ret, expected_output)
