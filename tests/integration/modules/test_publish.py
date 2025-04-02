import pytest

from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin


@pytest.mark.windows_whitelisted
class PublishModuleTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the publish module
    """

    @pytest.mark.slow_test
    def test_publish(self):
        """
        publish.publish
        """
        ret = self.run_function(
            "publish.publish", ["minion", "test.ping"], f_timeout=50
        )
        self.assertEqual(ret, {"minion": True})

        ret = self.run_function(
            "publish.publish",
            ["minion", "test.kwarg"],
            f_arg="cheese=spam",
            f_timeout=50,
        )
        ret = ret["minion"]

        check_true = (
            "cheese",
            "__pub_arg",
            "__pub_fun",
            "__pub_id",
            "__pub_jid",
            "__pub_ret",
            "__pub_tgt",
            "__pub_tgt_type",
        )
        for name in check_true:
            if name not in ret:
                print(name)
            self.assertTrue(name in ret)

        self.assertEqual(ret["cheese"], "spam")
        self.assertEqual(ret["__pub_arg"], [{"__kwarg__": True, "cheese": "spam"}])
        self.assertEqual(ret["__pub_id"], "minion")
        self.assertEqual(ret["__pub_fun"], "test.kwarg")

    @pytest.mark.slow_test
    def test_publish_yaml_args(self):
        """
        test publish.publish yaml args formatting
        """
        ret = self.run_function(
            "publish.publish", ["minion", "test.ping"], f_timeout=50
        )
        self.assertEqual(ret, {"minion": True})

        test_args_list = ["saltines, si", "crackers, nein", "cheese, indeed"]
        test_args = '["{args[0]}", "{args[1]}", "{args[2]}"]'.format(
            args=test_args_list
        )
        ret = self.run_function(
            "publish.publish", ["minion", "test.arg", test_args], f_timeout=50
        )
        ret = ret["minion"]

        check_true = (
            "__pub_arg",
            "__pub_fun",
            "__pub_id",
            "__pub_jid",
            "__pub_ret",
            "__pub_tgt",
            "__pub_tgt_type",
        )
        for name in check_true:
            if name not in ret["kwargs"]:
                print(name)
            self.assertTrue(name in ret["kwargs"])

        self.assertEqual(ret["args"], test_args_list)
        self.assertEqual(ret["kwargs"]["__pub_id"], "minion")
        self.assertEqual(ret["kwargs"]["__pub_fun"], "test.arg")

    @pytest.mark.slow_test
    def test_full_data(self):
        """
        publish.full_data
        """
        ret = self.run_function(
            "publish.full_data", ["minion", "test.fib", 20], f_timeout=50
        )
        self.assertTrue(ret)
        self.assertEqual(ret["minion"]["ret"][0], 6765)

    @pytest.mark.slow_test
    def test_kwarg(self):
        """
        Verify that the pub data is making it to the minion functions
        """
        ret = self.run_function(
            "publish.full_data",
            ["minion", "test.kwarg"],
            f_arg="cheese=spam",
            f_timeout=50,
        )
        ret = ret["minion"]["ret"]

        check_true = (
            "cheese",
            "__pub_arg",
            "__pub_fun",
            "__pub_id",
            "__pub_jid",
            "__pub_ret",
            "__pub_tgt",
            "__pub_tgt_type",
        )
        for name in check_true:
            if name not in ret:
                print(name)
            self.assertTrue(name in ret)

        self.assertEqual(ret["cheese"], "spam")
        self.assertEqual(ret["__pub_arg"], [{"__kwarg__": True, "cheese": "spam"}])
        self.assertEqual(ret["__pub_id"], "minion")
        self.assertEqual(ret["__pub_fun"], "test.kwarg")

        ret = self.run_function(
            "publish.full_data", ["minion", "test.kwarg"], cheese="spam", f_timeout=50
        )
        self.assertIn("The following keyword arguments are not valid", ret)

    @pytest.mark.slow_test
    def test_reject_minion(self):
        """
        Test bad authentication
        """
        ret = self.run_function(
            "publish.publish", ["minion", "cmd.run", ["echo foo"]], f_timeout=50
        )
        self.assertEqual(ret, {})
