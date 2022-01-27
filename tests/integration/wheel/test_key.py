import pytest
import salt.wheel
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.unit import TestCase


@pytest.mark.windows_whitelisted
@pytest.mark.usefixtures("salt_sub_minion")
class KeyWheelModuleTest(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
        self.wheel = salt.wheel.Wheel(dict(self.get_config("client_config")))

    def tearDown(self):
        del self.wheel

    @pytest.mark.slow_test
    def test_list_all(self):
        ret = self.wheel.cmd("key.list_all", print_event=False)
        for host in ["minion", "sub_minion"]:
            self.assertIn(host, ret["minions"])

    @pytest.mark.slow_test
    def test_gen(self):
        ret = self.wheel.cmd(
            "key.gen", kwarg={"id_": "soundtechniciansrock"}, print_event=False
        )

        self.assertIn("pub", ret)
        self.assertIn("priv", ret)
        try:
            self.assertTrue(ret.get("pub", "").startswith("-----BEGIN PUBLIC KEY-----"))
        except AssertionError:
            self.assertTrue(
                ret.get("pub", "").startswith("-----BEGIN RSA PUBLIC KEY-----")
            )

        self.assertTrue(
            ret.get("priv", "").startswith("-----BEGIN RSA PRIVATE KEY-----")
        )

    @pytest.mark.slow_test
    def test_master_key_str(self):
        ret = self.wheel.cmd("key.master_key_str", print_event=False)
        self.assertIn("local", ret)
        self.assertIn("master.pub", ret.get("local"))
        self.assertTrue(
            ret.get("local").get("master.pub").startswith("-----BEGIN PUBLIC KEY-----")
        )
