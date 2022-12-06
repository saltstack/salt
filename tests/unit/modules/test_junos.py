"""
    :codeauthor: Rajvi Dhimar <rajvidhimar95@gmail.com>
"""
import os

import pytest
import yaml

import salt.modules.junos as junos
from tests.support.mixins import LoaderModuleMockMixin, XMLEqualityMixin
from tests.support.mock import ANY, MagicMock, PropertyMock, call, mock_open, patch
from tests.support.unit import TestCase

try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree

try:
    import jnpr.junos.op as tables_dir
    import jxmlease  # pylint: disable=unused-import
    from jnpr.junos.device import Device
    from jnpr.junos.exception import ConnectClosedError, LockError, UnlockError
    from jnpr.junos.utils.config import Config
    from jnpr.junos.utils.sw import SW

    HAS_JUNOS = True
except ImportError:
    HAS_JUNOS = False


@pytest.mark.skipif(
    not HAS_JUNOS, reason="The junos-eznc and jxmlease modules are required"
)
class Test_Junos_Module(TestCase, LoaderModuleMockMixin, XMLEqualityMixin):
    def setup_loader_modules(self):
        return {
            junos: {
                "__proxy__": {
                    "junos.conn": self.make_connect,
                    "junos.get_serialized_facts": self.get_facts,
                    "junos.reboot_active": MagicMock(return_value=True),
                    "junos.reboot_clear": MagicMock(return_value=True),
                },
                "__salt__": {
                    "cp.get_template": self.mock_cp,
                    "cp.get_file": self.mock_cp,
                    "file.file_exists": MagicMock(return_value=True),
                    "slsutil.renderer": MagicMock(
                        return_value="set system host-name dummy"
                    ),
                    "event.fire_master": MagicMock(return_value=None),
                },
                "_restart_connection": MagicMock(return_value=None),
            },
        }

    def mock_cp(self, *args, **kwargs):
        pass

    def make_connect(self):
        with patch("ncclient.manager.connect") as mock_connect:
            self.dev = Device(
                host="1.1.1.1",
                user="test",
                password="test123",
                fact_style="old",
                gather_facts=False,
            )
            self.dev.open()
            self.dev.timeout = 30
            self.dev.bind(cu=Config)
            self.dev.bind(sw=SW)
            self.addCleanup(delattr, self, "dev")
            return self.dev

    def raise_exception(self, *args, **kwargs):
        raise Exception("Test exception")

    def get_facts(self):
        facts = {
            "2RE": True,
            "HOME": "/var/home/regress",
            "RE0": {
                "last_reboot_reason": "0x200:normal shutdown",
                "mastership_state": "master",
                "model": "RE-VMX",
                "status": "OK",
                "up_time": "11 days, 23 hours, 16 minutes, 54 seconds",
            },
            "RE1": {
                "last_reboot_reason": "0x200:normal shutdown",
                "mastership_state": "backup",
                "model": "RE-VMX",
                "status": "OK",
                "up_time": "11 days, 23 hours, 16 minutes, 41 seconds",
            },
            "RE_hw_mi": False,
            "current_re": ["re0", "master", "node", "fwdd", "member", "pfem"],
            "domain": "englab.juniper.net",
            "fqdn": "R1_re0.englab.juniper.net",
            "hostname": "R1_re0",
            "hostname_info": {"re0": "R1_re0", "re1": "R1_re01"},
            "ifd_style": "CLASSIC",
            "junos_info": {
                "re0": {
                    "object": {
                        "build": None,
                        "major": (16, 1),
                        "minor": "20160413_0837_aamish",
                        "type": "I",
                    },
                    "text": "16.1I20160413_0837_aamish",
                },
                "re1": {
                    "object": {
                        "build": None,
                        "major": (16, 1),
                        "minor": "20160413_0837_aamish",
                        "type": "I",
                    },
                    "text": "16.1I20160413_0837_aamish",
                },
            },
            "master": "RE0",
            "model": "MX240",
            "model_info": {"re0": "MX240", "re1": "MX240"},
            "personality": "MX",
            "re_info": {
                "default": {
                    "0": {
                        "last_reboot_reason": "0x200:normal shutdown",
                        "mastership_state": "master",
                        "model": "RE-VMX",
                        "status": "OK",
                    },
                    "1": {
                        "last_reboot_reason": "0x200:normal shutdown",
                        "mastership_state": "backup",
                        "model": "RE-VMX",
                        "status": "OK",
                    },
                    "default": {
                        "last_reboot_reason": "0x200:normal shutdown",
                        "mastership_state": "master",
                        "model": "RE-VMX",
                        "status": "OK",
                    },
                }
            },
            "re_master": {"default": "0"},
            "serialnumber": "VMX4eaf",
            "srx_cluster": None,
            "switch_style": "BRIDGE_DOMAIN",
            "vc_capable": False,
            "vc_fabric": None,
            "vc_master": None,
            "vc_mode": None,
            "version": "16.1I20160413_0837_aamish",
            "version_RE0": "16.1I20160413_0837_aamish",
            "version_RE1": "16.1I20160413_0837_aamish",
            "version_info": {
                "build": None,
                "major": (16, 1),
                "minor": "20160413_0837_aamish",
                "type": "I",
            },
            "virtual": True,
        }
        return facts

    def test__timeout_decorator(self):
        with patch(
            "jnpr.junos.Device.timeout", new_callable=PropertyMock
        ) as mock_timeout:
            mock_timeout.return_value = 30

            def function(x):
                return x

            decorator = junos._timeout_decorator(function)
            decorator("Test Mock", dev_timeout=10)
            calls = [call(), call(10), call(30)]
            mock_timeout.assert_has_calls(calls)

    def test__timeout_cleankwargs_decorator(self):
        with patch(
            "jnpr.junos.Device.timeout", new_callable=PropertyMock
        ) as mock_timeout:
            mock_timeout.return_value = 30

            def function(x):
                return x

            decorator = junos._timeout_decorator_cleankwargs(function)
            decorator("Test Mock", dev_timeout=10, __pub_args="abc")
            calls = [call(), call(10), call(30)]
            mock_timeout.assert_has_calls(calls)

    def test_facts_refresh(self):
        with patch("salt.modules.saltutil.sync_grains") as mock_sync_grains:
            ret = dict()
            ret["facts"] = {
                "2RE": True,
                "HOME": "/var/home/regress",
                "RE0": {
                    "last_reboot_reason": "0x200:normal shutdown",
                    "mastership_state": "master",
                    "model": "RE-VMX",
                    "status": "OK",
                    "up_time": "11 days, 23 hours, 16 minutes, 54 seconds",
                },
                "RE1": {
                    "last_reboot_reason": "0x200:normal shutdown",
                    "mastership_state": "backup",
                    "model": "RE-VMX",
                    "status": "OK",
                    "up_time": "11 days, 23 hours, 16 minutes, 41 seconds",
                },
                "RE_hw_mi": False,
                "current_re": ["re0", "master", "node", "fwdd", "member", "pfem"],
                "domain": "englab.juniper.net",
                "fqdn": "R1_re0.englab.juniper.net",
                "hostname": "R1_re0",
                "hostname_info": {"re0": "R1_re0", "re1": "R1_re01"},
                "ifd_style": "CLASSIC",
                "junos_info": {
                    "re0": {
                        "object": {
                            "build": None,
                            "major": (16, 1),
                            "minor": "20160413_0837_aamish",
                            "type": "I",
                        },
                        "text": "16.1I20160413_0837_aamish",
                    },
                    "re1": {
                        "object": {
                            "build": None,
                            "major": (16, 1),
                            "minor": "20160413_0837_aamish",
                            "type": "I",
                        },
                        "text": "16.1I20160413_0837_aamish",
                    },
                },
                "master": "RE0",
                "model": "MX240",
                "model_info": {"re0": "MX240", "re1": "MX240"},
                "personality": "MX",
                "re_info": {
                    "default": {
                        "0": {
                            "last_reboot_reason": "0x200:normal shutdown",
                            "mastership_state": "master",
                            "model": "RE-VMX",
                            "status": "OK",
                        },
                        "1": {
                            "last_reboot_reason": "0x200:normal shutdown",
                            "mastership_state": "backup",
                            "model": "RE-VMX",
                            "status": "OK",
                        },
                        "default": {
                            "last_reboot_reason": "0x200:normal shutdown",
                            "mastership_state": "master",
                            "model": "RE-VMX",
                            "status": "OK",
                        },
                    }
                },
                "re_master": {"default": "0"},
                "serialnumber": "VMX4eaf",
                "srx_cluster": None,
                "switch_style": "BRIDGE_DOMAIN",
                "vc_capable": False,
                "vc_fabric": None,
                "vc_master": None,
                "vc_mode": None,
                "version": "16.1I20160413_0837_aamish",
                "version_RE0": "16.1I20160413_0837_aamish",
                "version_RE1": "16.1I20160413_0837_aamish",
                "version_info": {
                    "build": None,
                    "major": (16, 1),
                    "minor": "20160413_0837_aamish",
                    "type": "I",
                },
                "virtual": True,
            }
            ret["out"] = True
            self.assertEqual(junos.facts_refresh(), ret)

    def test_facts_refresh_exception(self):
        with patch("jnpr.junos.device.Device.facts_refresh") as mock_facts_refresh:
            mock_facts_refresh.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Execution failed due to "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.facts_refresh(), ret)

    def test_facts(self):
        ret = dict()
        ret["facts"] = {
            "2RE": True,
            "HOME": "/var/home/regress",
            "RE0": {
                "last_reboot_reason": "0x200:normal shutdown",
                "mastership_state": "master",
                "model": "RE-VMX",
                "status": "OK",
                "up_time": "11 days, 23 hours, 16 minutes, 54 seconds",
            },
            "RE1": {
                "last_reboot_reason": "0x200:normal shutdown",
                "mastership_state": "backup",
                "model": "RE-VMX",
                "status": "OK",
                "up_time": "11 days, 23 hours, 16 minutes, 41 seconds",
            },
            "RE_hw_mi": False,
            "current_re": ["re0", "master", "node", "fwdd", "member", "pfem"],
            "domain": "englab.juniper.net",
            "fqdn": "R1_re0.englab.juniper.net",
            "hostname": "R1_re0",
            "hostname_info": {"re0": "R1_re0", "re1": "R1_re01"},
            "ifd_style": "CLASSIC",
            "junos_info": {
                "re0": {
                    "object": {
                        "build": None,
                        "major": (16, 1),
                        "minor": "20160413_0837_aamish",
                        "type": "I",
                    },
                    "text": "16.1I20160413_0837_aamish",
                },
                "re1": {
                    "object": {
                        "build": None,
                        "major": (16, 1),
                        "minor": "20160413_0837_aamish",
                        "type": "I",
                    },
                    "text": "16.1I20160413_0837_aamish",
                },
            },
            "master": "RE0",
            "model": "MX240",
            "model_info": {"re0": "MX240", "re1": "MX240"},
            "personality": "MX",
            "re_info": {
                "default": {
                    "0": {
                        "last_reboot_reason": "0x200:normal shutdown",
                        "mastership_state": "master",
                        "model": "RE-VMX",
                        "status": "OK",
                    },
                    "1": {
                        "last_reboot_reason": "0x200:normal shutdown",
                        "mastership_state": "backup",
                        "model": "RE-VMX",
                        "status": "OK",
                    },
                    "default": {
                        "last_reboot_reason": "0x200:normal shutdown",
                        "mastership_state": "master",
                        "model": "RE-VMX",
                        "status": "OK",
                    },
                }
            },
            "re_master": {"default": "0"},
            "serialnumber": "VMX4eaf",
            "srx_cluster": None,
            "switch_style": "BRIDGE_DOMAIN",
            "vc_capable": False,
            "vc_fabric": None,
            "vc_master": None,
            "vc_mode": None,
            "version": "16.1I20160413_0837_aamish",
            "version_RE0": "16.1I20160413_0837_aamish",
            "version_RE1": "16.1I20160413_0837_aamish",
            "version_info": {
                "build": None,
                "major": (16, 1),
                "minor": "20160413_0837_aamish",
                "type": "I",
            },
            "virtual": True,
        }
        ret["out"] = True
        self.assertEqual(junos.facts(), ret)

    def test_facts_exception(self):
        with patch.dict(
            junos.__proxy__, {"junos.get_serialized_facts": self.raise_exception}
        ):
            ret = dict()
            ret["message"] = 'Could not display facts due to "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.facts(), ret)

    def test_set_hostname_without_args(self):
        ret = dict()
        ret["message"] = "Please provide the hostname."
        ret["out"] = False
        self.assertEqual(junos.set_hostname(), ret)

    def test_set_hostname_load_called_with_valid_name(self):
        with patch("jnpr.junos.utils.config.Config.load") as mock_load:
            junos.set_hostname("test-name")
            mock_load.assert_called_with("set system host-name test-name", format="set")

    def test_set_hostname_raise_exception_for_load(self):
        with patch("jnpr.junos.utils.config.Config.load") as mock_load:
            mock_load.side_effect = self.raise_exception
            ret = dict()
            ret[
                "message"
            ] = 'Could not load configuration due to error "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.set_hostname("Test-name"), ret)

    def test_set_hostname_raise_exception_for_commit_check(self):
        with patch("jnpr.junos.utils.config.Config.commit_check") as mock_commit_check:
            mock_commit_check.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Could not commit check due to error "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.set_hostname("test-name"), ret)

    def test_set_hostname_one_arg_parsed_correctly(self):
        with patch("jnpr.junos.utils.config.Config.load") as mock_load, patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit:
            mock_commit_check.return_value = True
            args = {
                "comment": "Committed via salt",
                "__pub_user": "root",
                "__pub_arg": ["test-name", {"comment": "Committed via salt"}],
                "__pub_fun": "junos.set_hostname",
                "__pub_jid": "20170220210915624885",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }

            junos.set_hostname("test-name", **args)
            mock_commit.assert_called_with(comment="Committed via salt")

    def test_set_hostname_more_than_one_args_parsed_correctly(self):
        with patch("jnpr.junos.utils.config.Config.load") as mock_load, patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit:
            mock_commit_check.return_value = True
            args = {
                "comment": "Committed via salt",
                "__pub_user": "root",
                "__pub_arg": [
                    "test-name",
                    {"comment": "Committed via salt", "confirm": 5},
                ],
                "__pub_fun": "junos.set_hostname",
                "__pub_jid": "20170220210915624885",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }

            junos.set_hostname("test-name", **args)
            mock_commit.assert_called_with(comment="Committed via salt", confirm=5)

    def test_set_hostname_successful_return_message(self):
        with patch("jnpr.junos.utils.config.Config.load") as mock_load, patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit:
            mock_commit_check.return_value = True
            args = {
                "comment": "Committed via salt",
                "__pub_user": "root",
                "__pub_arg": ["test-name", {"comment": "Committed via salt"}],
                "__pub_fun": "junos.set_hostname",
                "__pub_jid": "20170220210915624885",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            ret = dict()
            ret["message"] = "Successfully changed hostname."
            ret["out"] = True
            self.assertEqual(junos.set_hostname("test-name", **args), ret)

    def test_set_hostname_raise_exception_for_commit(self):
        with patch("jnpr.junos.utils.config.Config.commit") as mock_commit:
            mock_commit.side_effect = self.raise_exception
            ret = dict()
            ret[
                "message"
            ] = 'Successfully loaded host-name but commit failed with "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.set_hostname("test-name"), ret)

    def test_set_hostname_fail_commit_check(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch("salt.modules.junos.rollback") as mock_rollback:
            mock_commit_check.return_value = False
            ret = dict()
            ret["out"] = False
            ret[
                "message"
            ] = "Successfully loaded host-name but pre-commit check failed."
            self.assertEqual(junos.set_hostname("test"), ret)

    def test_commit_without_args(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit:
            mock_commit.return_value = True
            mock_commit_check.return_value = True
            ret = dict()
            ret["message"] = "Commit Successful."
            ret["out"] = True
            self.assertEqual(junos.commit(), ret)

    def test_commit_raise_commit_check_exception(self):
        with patch("jnpr.junos.utils.config.Config.commit_check") as mock_commit_check:
            mock_commit_check.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Could not perform commit check due to "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.commit(), ret)

    def test_commit_raise_commit_exception(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit:
            mock_commit_check.return_value = True
            mock_commit.side_effect = self.raise_exception
            ret = dict()
            ret["out"] = False
            ret[
                "message"
            ] = 'Commit check succeeded but actual commit failed with "Test exception"'
            self.assertEqual(junos.commit(), ret)

    def test_commit_with_single_argument(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit:
            mock_commit_check.return_value = True
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"sync": True}],
                "sync": True,
                "__pub_fun": "junos.commit",
                "__pub_jid": "20170221182531323467",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            junos.commit(**args)
            mock_commit.assert_called_with(detail=False, sync=True)

    def test_commit_with_multiple_arguments(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit:
            mock_commit_check.return_value = True
            args = {
                "comment": "comitted via salt",
                "__pub_user": "root",
                "__pub_arg": [
                    {"comment": "comitted via salt", "confirm": 3, "detail": True}
                ],
                "confirm": 3,
                "detail": True,
                "__pub_fun": "junos.commit",
                "__pub_jid": "20170221182856987820",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            junos.commit(**args)
            mock_commit.assert_called_with(
                comment="comitted via salt", detail=True, confirm=3
            )

    def test_commit_pyez_commit_returning_false(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit:
            mock_commit.return_value = False
            mock_commit_check.return_value = True
            ret = dict()
            ret["message"] = "Commit failed."
            ret["out"] = False
            self.assertEqual(junos.commit(), ret)

    def test_commit_pyez_commit_check_returns_false(self):
        with patch("jnpr.junos.utils.config.Config.commit_check") as mock_commit_check:
            mock_commit_check.return_value = False
            ret = dict()
            ret["out"] = False
            ret["message"] = "Pre-commit check failed."
            self.assertEqual(junos.commit(), ret)

    def test_rollback_exception(self):
        with patch("jnpr.junos.utils.config.Config.rollback") as mock_rollback:
            mock_rollback.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Rollback failed due to "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.rollback(), ret)

    def test_rollback_without_args_success(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit, patch(
            "jnpr.junos.utils.config.Config.rollback"
        ) as mock_rollback:
            mock_commit_check.return_value = True
            mock_rollback.return_value = True
            ret = dict()
            ret["message"] = "Rollback successful"
            ret["out"] = True
            self.assertEqual(junos.rollback(), ret)

    def test_rollback_without_args_fail(self):
        with patch("jnpr.junos.utils.config.Config.rollback") as mock_rollback:
            mock_rollback.return_value = False
            ret = dict()
            ret["message"] = "Rollback failed"
            ret["out"] = False
            self.assertEqual(junos.rollback(), ret)

    def test_rollback_with_id(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit, patch(
            "jnpr.junos.utils.config.Config.rollback"
        ) as mock_rollback:
            mock_commit_check.return_value = True
            junos.rollback(id=5)
            mock_rollback.assert_called_with(5)

    def test_rollback_with_id_and_single_arg(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit, patch(
            "jnpr.junos.utils.config.Config.rollback"
        ) as mock_rollback:
            mock_commit_check.return_value = True
            args = {
                "__pub_user": "root",
                "__pub_arg": [2, {"confirm": 2}],
                "confirm": 2,
                "__pub_fun": "junos.rollback",
                "__pub_jid": "20170221184518526067",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            junos.rollback(id=2, **args)
            mock_rollback.assert_called_with(2)
            mock_commit.assert_called_with(confirm=2)

    def test_rollback_with_id_and_multiple_args(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit, patch(
            "jnpr.junos.utils.config.Config.rollback"
        ) as mock_rollback:
            mock_commit_check.return_value = True
            args = {
                "comment": "Comitted via salt",
                "__pub_user": "root",
                "__pub_arg": [
                    2,
                    {"comment": "Comitted via salt", "dev_timeout": 40, "confirm": 1},
                ],
                "confirm": 1,
                "__pub_fun": "junos.rollback",
                "__pub_jid": "20170221192708251721",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            junos.rollback(id=2, **args)
            mock_rollback.assert_called_with(2)
            mock_commit.assert_called_with(
                comment="Comitted via salt", confirm=1, dev_timeout=40
            )

    def test_rollback_with_only_single_arg(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit, patch(
            "jnpr.junos.utils.config.Config.rollback"
        ) as mock_rollback:
            mock_commit_check.return_value = True
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"sync": True}],
                "sync": True,
                "__pub_fun": "junos.rollback",
                "__pub_jid": "20170221193615696475",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            junos.rollback(**args)
            mock_rollback.assert_called_once_with(0)
            mock_commit.assert_called_once_with(sync=True)

    def test_rollback_with_only_multiple_args_no_id(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit, patch(
            "jnpr.junos.utils.config.Config.rollback"
        ) as mock_rollback:
            mock_commit_check.return_value = True
            args = {
                "comment": "Comitted via salt",
                "__pub_user": "root",
                "__pub_arg": [
                    {"comment": "Comitted via salt", "confirm": 3, "sync": True}
                ],
                "confirm": 3,
                "sync": True,
                "__pub_fun": "junos.rollback",
                "__pub_jid": "20170221193945996362",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            junos.rollback(**args)
            mock_rollback.assert_called_with(0)
            mock_commit.assert_called_once_with(
                sync=True, confirm=3, comment="Comitted via salt"
            )

    def test_rollback_with_diffs_file_option_when_diff_is_None(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit, patch(
            "jnpr.junos.utils.config.Config.rollback"
        ) as mock_rollback, patch(
            "salt.utils.files.fopen"
        ) as mock_fopen, patch(
            "jnpr.junos.utils.config.Config.diff"
        ) as mock_diff:
            mock_commit_check.return_value = True
            mock_diff.return_value = "diff"
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"diffs_file": "/home/regress/diff", "confirm": 2}],
                "confirm": 2,
                "__pub_fun": "junos.rollback",
                "__pub_jid": "20170221205153884009",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
                "diffs_file": "/home/regress/diff",
            }
            junos.rollback(**args)
            mock_fopen.assert_called_with("/home/regress/diff", "w")

    def test_rollback_with_diffs_file_option(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit, patch(
            "jnpr.junos.utils.config.Config.rollback"
        ) as mock_rollback, patch(
            "salt.utils.files.fopen"
        ) as mock_fopen, patch(
            "jnpr.junos.utils.config.Config.diff"
        ) as mock_diff:
            mock_commit_check.return_value = True
            mock_diff.return_value = None
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"diffs_file": "/home/regress/diff", "confirm": 2}],
                "confirm": 2,
                "__pub_fun": "junos.rollback",
                "__pub_jid": "20170221205153884009",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
                "diffs_file": "/home/regress/diff",
            }
            junos.rollback(**args)
            assert not mock_fopen.called

    def test_rollback_commit_check_exception(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.rollback"
        ) as mock_rollback:
            mock_commit_check.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Could not commit check due to "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.rollback(), ret)

    def test_rollback_commit_exception(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.commit"
        ) as mock_commit, patch(
            "jnpr.junos.utils.config.Config.rollback"
        ) as mock_rollback:
            mock_commit_check.return_value = True
            mock_commit.side_effect = self.raise_exception
            ret = dict()
            ret[
                "message"
            ] = 'Rollback successful but commit failed with error "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.rollback(), ret)

    def test_rollback_commit_check_fails(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.rollback"
        ) as mock_rollback:
            mock_commit_check.return_value = False
            ret = dict()
            ret["message"] = "Rollback successful but pre-commit check failed."
            ret["out"] = False
            self.assertEqual(junos.rollback(), ret)

    def test_diff_without_args(self):
        with patch("jnpr.junos.utils.config.Config.diff") as mock_diff:
            junos.diff()
            mock_diff.assert_called_with(rb_id=0)

    def test_diff_with_arg(self):
        with patch("jnpr.junos.utils.config.Config.diff") as mock_diff:
            junos.diff(id=2)
            mock_diff.assert_called_with(rb_id=2)

    def test_diff_exception(self):
        with patch("jnpr.junos.utils.config.Config.diff") as mock_diff:
            mock_diff.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Could not get diff with error "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.diff(), ret)

    def test_ping_without_args(self):
        ret = dict()
        ret["message"] = "Please specify the destination ip to ping."
        ret["out"] = False
        self.assertEqual(junos.ping(), ret)

    def test_ping(self):
        with patch("jnpr.junos.device.Device.execute") as mock_execute:
            junos.ping("1.1.1.1")
            args = mock_execute.call_args
            rpc = "<ping><count>5</count><host>1.1.1.1</host></ping>"
            self.assertEqualXML(args[0][0], rpc)

    def test_ping_ttl(self):
        with patch("jnpr.junos.device.Device.execute") as mock_execute:
            args = {
                "__pub_user": "sudo_drajvi",
                "__pub_arg": ["1.1.1.1", {"ttl": 3}],
                "__pub_fun": "junos.ping",
                "__pub_jid": "20170306165237683279",
                "__pub_tgt": "mac_min",
                "ttl": 3,
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            junos.ping("1.1.1.1", **args)
            exec_args = mock_execute.call_args
            rpc = "<ping><count>5</count><host>1.1.1.1</host><ttl>3</ttl></ping>"
            self.assertEqualXML(exec_args[0][0], rpc)

    def test_ping_exception(self):
        with patch("jnpr.junos.device.Device.execute") as mock_execute:
            mock_execute.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Execution failed due to "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.ping("1.1.1.1"), ret)

    def test_cli_without_args(self):
        ret = dict()
        ret["message"] = "Please provide the CLI command to be executed."
        ret["out"] = False
        self.assertEqual(junos.cli(), ret)

    def test_cli_with_format_as_empty_string(self):
        with patch("jnpr.junos.device.Device.cli") as mock_cli:
            junos.cli("show version", format="")
            mock_cli.assert_called_with("show version", "text", warning=False)

    def test_cli(self):
        with patch("jnpr.junos.device.Device.cli") as mock_cli:
            mock_cli.return_vale = "CLI result"
            ret = dict()
            ret["message"] = "CLI result"
            ret["out"] = True
            junos.cli("show version")
            mock_cli.assert_called_with("show version", "text", warning=False)

    def test_cli_format_xml(self):
        with patch("salt.modules.junos.jxmlease.parse") as mock_jxml, patch(
            "salt.modules.junos.etree.tostring"
        ) as mock_to_string, patch("jnpr.junos.device.Device.cli") as mock_cli:
            mock_cli.return_value = "<root><a>test</a></root>"
            mock_jxml.return_value = "<root><a>test</a></root>"
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"format": "xml"}],
                "format": "xml",
                "__pub_fun": "junos.cli",
                "__pub_jid": "20170221182531323467",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            ret = dict()
            ret["message"] = "<root><a>test</a></root>"
            ret["out"] = True
            self.assertEqual(junos.cli("show version", **args), ret)
            mock_cli.assert_called_with("show version", "xml", warning=False)
            mock_to_string.assert_called_once_with("<root><a>test</a></root>")
            assert mock_jxml.called

    def test_cli_exception_in_cli(self):
        with patch("jnpr.junos.device.Device.cli") as mock_cli:
            mock_cli.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Execution failed due to "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.cli("show version"), ret)

    def test_cli_output_save(self):
        with patch("jnpr.junos.device.Device.cli") as mock_cli, patch(
            "salt.utils.files.fopen"
        ) as mock_fopen:
            mock_cli.return_value = "Test return"
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"format": "text", "dest": "/path/to/file"}],
                "format": "text",
                "dest": "/path/to/file",
                "__pub_fun": "junos.cli",
                "__pub_jid": "20170221182531323467",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            ret = dict()
            ret["message"] = "Test return"
            ret["out"] = True
            self.assertEqual(junos.cli("show version", **args), ret)
            mock_fopen.assert_called_with("/path/to/file", "w")
            mock_cli.assert_called_with("show version", "text", warning=False)

    def test_cli_output_save_ioexception(self):
        with patch("jnpr.junos.device.Device.cli") as mock_cli, patch(
            "salt.utils.files.fopen"
        ) as mock_fopen:
            mock_cli.return_value = "Test return"
            mock_fopen.side_effect = IOError()
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"format": "text", "dest": "/path/to/file"}],
                "format": "text",
                "dest": "/path/to/file",
                "__pub_fun": "junos.cli",
                "__pub_jid": "20170221182531323467",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            ret = dict()
            ret["message"] = 'Unable to open "/path/to/file" to write'
            ret["out"] = False
            self.assertEqual(junos.cli("show version", **args), ret)

    def test_shutdown_without_args(self):
        ret = dict()
        ret["message"] = "Provide either one of the arguments: shutdown or reboot."
        ret["out"] = False
        self.assertEqual(junos.shutdown(), ret)

    def test_shutdown_with_reboot_args(self):
        with patch("salt.modules.junos.SW.reboot") as mock_reboot:
            ret = dict()
            ret["message"] = "Successfully powered off/rebooted."
            ret["out"] = True
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"reboot": True}],
                "reboot": True,
                "__pub_fun": "junos.shutdown",
                "__pub_jid": "20170222213858582619",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            self.assertEqual(junos.shutdown(**args), ret)
            assert mock_reboot.called

    def test_shutdown_with_poweroff_args(self):
        with patch("salt.modules.junos.SW.poweroff") as mock_poweroff:
            ret = dict()
            ret["message"] = "Successfully powered off/rebooted."
            ret["out"] = True
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"shutdown": True}],
                "reboot": True,
                "__pub_fun": "junos.shutdown",
                "__pub_jid": "20170222213858582619",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            self.assertEqual(junos.shutdown(**args), ret)
            assert mock_poweroff.called

    def test_shutdown_with_shutdown_as_false(self):
        ret = dict()
        ret["message"] = "Nothing to be done."
        ret["out"] = False
        args = {
            "__pub_user": "root",
            "__pub_arg": [{"shutdown": False}],
            "reboot": True,
            "__pub_fun": "junos.shutdown",
            "__pub_jid": "20170222213858582619",
            "__pub_tgt": "mac_min",
            "__pub_tgt_type": "glob",
            "__pub_ret": "",
        }
        self.assertEqual(junos.shutdown(**args), ret)

    def test_shutdown_with_in_min_arg(self):
        with patch("salt.modules.junos.SW.poweroff") as mock_poweroff:
            args = {
                "__pub_user": "root",
                "in_min": 10,
                "__pub_arg": [{"in_min": 10, "shutdown": True}],
                "reboot": True,
                "__pub_fun": "junos.shutdown",
                "__pub_jid": "20170222231445709212",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            junos.shutdown(**args)
            mock_poweroff.assert_called_with(in_min=10)

    def test_shutdown_with_at_arg(self):
        with patch("salt.modules.junos.SW.reboot") as mock_reboot:
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"at": "12:00 pm", "reboot": True}],
                "reboot": True,
                "__pub_fun": "junos.shutdown",
                "__pub_jid": "201702276857",
                "at": "12:00 pm",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            junos.shutdown(**args)
            mock_reboot.assert_called_with(at="12:00 pm")

    def test_shutdown_fail_with_exception(self):
        with patch("salt.modules.junos.SW.poweroff") as mock_poweroff:
            mock_poweroff.side_effect = self.raise_exception
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"shutdown": True}],
                "shutdown": True,
                "__pub_fun": "junos.shutdown",
                "__pub_jid": "20170222213858582619",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            ret = dict()
            ret["message"] = 'Could not poweroff/reboot because "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.shutdown(**args), ret)

    def test_install_config_without_args(self):
        ret = dict()
        ret[
            "message"
        ] = "Please provide the salt path where the configuration is present"
        ret["out"] = False
        self.assertEqual(junos.install_config(), ret)

    def test_install_config_cp_fails(self):
        with patch.dict(
            junos.__salt__, {"file.file_exists": MagicMock(return_value=False)}
        ):
            ret = dict()
            ret = dict()
            ret["message"] = "Invalid file path."
            ret["out"] = False
            self.assertEqual(junos.install_config("path"), ret)

    def test_install_config_file_cp_fails(self):
        with patch.dict(
            junos.__salt__, {"file.file_exists": MagicMock(return_value=False)}
        ):
            ret = dict()
            ret = dict()
            ret["message"] = "Invalid file path."
            ret["out"] = False
            self.assertEqual(junos.install_config("path"), ret)

    def test_install_config(self):
        with patch.dict(
            junos.__salt__,
            {
                "cp.is_cached": MagicMock(return_value="test/path/config"),
                "cp.hash_file": MagicMock(
                    return_value={"hash_type": "sha256", "hsum": "a386e49c17"}
                ),
                "file.get_hash": MagicMock(return_value="a386e49c17"),
            },
        ):
            with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
                "jnpr.junos.utils.config.Config.commit_check"
            ) as mock_commit_check, patch(
                "jnpr.junos.utils.config.Config.diff"
            ) as mock_diff, patch(
                "jnpr.junos.utils.config.Config.load"
            ) as mock_load, patch(
                "salt.utils.files.safe_rm"
            ) as mock_safe_rm, patch(
                "salt.utils.files.mkstemp"
            ) as mock_mkstemp, patch(
                "salt.utils.files.fopen", mock_open(), create=True
            ) as m_open, patch(
                "os.path.isfile"
            ) as mock_isfile, patch(
                "os.path.getsize"
            ) as mock_getsize:
                mock_isfile.return_value = True
                mock_getsize.return_value = 10
                mock_mkstemp.return_value = "test/path/config"
                mock_diff.return_value = "diff"
                mock_commit_check.return_value = True

                ret = dict()
                ret["message"] = "Successfully loaded and committed!"
                ret["out"] = True
                self.assertEqual(
                    junos.install_config("salt://actual/path/config.set"), ret
                )
                mock_load.assert_called_with(path="test/path/config", format="set")

    def test_install_config_xml_file(self):
        with patch.dict(
            junos.__salt__,
            {
                "cp.is_cached": MagicMock(return_value="test/path/config"),
                "cp.hash_file": MagicMock(
                    return_value={"hash_type": "sha256", "hsum": "a386e49c17"}
                ),
                "file.get_hash": MagicMock(return_value="a386e49c17"),
            },
        ):
            with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
                "jnpr.junos.utils.config.Config.commit_check"
            ) as mock_commit_check, patch(
                "jnpr.junos.utils.config.Config.diff"
            ) as mock_diff, patch(
                "jnpr.junos.utils.config.Config.load"
            ) as mock_load, patch(
                "salt.utils.files.safe_rm"
            ) as mock_safe_rm, patch(
                "salt.utils.files.mkstemp"
            ) as mock_mkstemp, patch(
                "os.path.isfile"
            ) as mock_isfile, patch(
                "salt.utils.files.fopen", mock_open(), create=True
            ) as m_open, patch(
                "os.path.getsize"
            ) as mock_getsize:
                mock_isfile.return_value = True
                mock_getsize.return_value = 10
                mock_mkstemp.return_value = "test/path/config"
                mock_diff.return_value = "diff"
                mock_commit_check.return_value = True

                ret = dict()
                ret["message"] = "Successfully loaded and committed!"
                ret["out"] = True
                self.assertEqual(
                    junos.install_config("salt://actual/path/config.xml"), ret
                )
                mock_load.assert_called_with(path="test/path/config", format="xml")

    def test_install_config_text_file(self):
        with patch.dict(
            junos.__salt__,
            {
                "cp.is_cached": MagicMock(return_value="test/path/config"),
                "cp.hash_file": MagicMock(
                    return_value={"hash_type": "sha256", "hsum": "a386e49c17"}
                ),
                "file.get_hash": MagicMock(return_value="a386e49c17"),
            },
        ):
            with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
                "jnpr.junos.utils.config.Config.commit_check"
            ) as mock_commit_check, patch(
                "jnpr.junos.utils.config.Config.diff"
            ) as mock_diff, patch(
                "jnpr.junos.utils.config.Config.load"
            ) as mock_load, patch(
                "salt.utils.files.safe_rm"
            ) as mock_safe_rm, patch(
                "salt.utils.files.mkstemp"
            ) as mock_mkstemp, patch(
                "os.path.isfile"
            ) as mock_isfile, patch(
                "salt.utils.files.fopen", mock_open(), create=True
            ) as m_open, patch(
                "os.path.getsize"
            ) as mock_getsize:
                mock_isfile.return_value = True
                mock_getsize.return_value = 10
                mock_mkstemp.return_value = "test/path/config"
                mock_diff.return_value = "diff"
                mock_commit_check.return_value = True

                ret = dict()
                ret["message"] = "Successfully loaded and committed!"
                ret["out"] = True
                self.assertEqual(junos.install_config("salt://actual/path/config"), ret)
                mock_load.assert_called_with(path="test/path/config", format="text")

    def test_install_config_cache_not_exists(self):
        with patch.dict(
            junos.__salt__,
            {
                "cp.is_cached": MagicMock(return_value=None),
                "file.rmdir": MagicMock(return_value="True"),
            },
        ):
            with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
                "jnpr.junos.utils.config.Config.commit_check"
            ) as mock_commit_check, patch(
                "jnpr.junos.utils.config.Config.diff"
            ) as mock_diff, patch(
                "jnpr.junos.utils.config.Config.load"
            ) as mock_load, patch(
                "salt.utils.files.safe_rm"
            ) as mock_safe_rm, patch(
                "salt.utils.files.mkstemp"
            ) as mock_mkstemp, patch(
                "tempfile.mkdtemp"
            ) as mock_mkdtemp, patch(
                "os.path.isfile"
            ) as mock_isfile, patch(
                "salt.utils.files.fopen", mock_open(), create=True
            ) as m_open, patch(
                "os.path.getsize"
            ) as mock_getsize:
                mock_isfile.return_value = True
                mock_getsize.return_value = 10
                mock_mkstemp.return_value = "test/path/config"
                mock_diff.return_value = "diff"
                mock_commit_check.return_value = True
                mock_mkdtemp.return_value = "/tmp/argr5351afd"

                ret = dict()
                ret["message"] = "Successfully loaded and committed!"
                ret["out"] = True
                self.assertEqual(
                    junos.install_config(
                        "salt://actual/path/config", template_vars=True
                    ),
                    ret,
                )
                mock_mkstemp.assert_called_with()

    def test_install_config_replace(self):
        with patch.dict(
            junos.__salt__,
            {
                "cp.is_cached": MagicMock(return_value="test/path/config"),
                "cp.hash_file": MagicMock(
                    return_value={"hash_type": "sha256", "hsum": "a386e49c17"}
                ),
                "file.get_hash": MagicMock(return_value="a386e49c17"),
            },
        ):
            with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
                "jnpr.junos.utils.config.Config.commit_check"
            ) as mock_commit_check, patch(
                "jnpr.junos.utils.config.Config.diff"
            ) as mock_diff, patch(
                "jnpr.junos.utils.config.Config.load"
            ) as mock_load, patch(
                "salt.utils.files.safe_rm"
            ) as mock_safe_rm, patch(
                "salt.utils.files.mkstemp"
            ) as mock_mkstemp, patch(
                "os.path.isfile"
            ) as mock_isfile, patch(
                "salt.utils.files.fopen", mock_open(), create=True
            ) as m_open, patch(
                "os.path.getsize"
            ) as mock_getsize:
                mock_isfile.return_value = True
                mock_getsize.return_value = 10
                mock_mkstemp.return_value = "test/path/config"
                mock_diff.return_value = "diff"
                mock_commit_check.return_value = True

                args = {
                    "__pub_user": "root",
                    "__pub_arg": [{"replace": True}],
                    "replace": True,
                    "__pub_fun": "junos.install_config",
                    "__pub_jid": "20170222213858582619",
                    "__pub_tgt": "mac_min",
                    "__pub_tgt_type": "glob",
                    "__pub_ret": "",
                }

                ret = dict()
                ret["message"] = "Successfully loaded and committed!"
                ret["out"] = True
                self.assertEqual(
                    junos.install_config("salt://actual/path/config.set", **args), ret
                )
                mock_load.assert_called_with(
                    path="test/path/config", format="set", merge=False
                )

    def test_install_config_overwrite(self):
        with patch.dict(
            junos.__salt__,
            {
                "cp.is_cached": MagicMock(return_value="test/path/config"),
                "cp.hash_file": MagicMock(
                    return_value={"hash_type": "sha256", "hsum": "a386e49c17"}
                ),
                "file.get_hash": MagicMock(return_value="a386e49c17"),
            },
        ):
            with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
                "jnpr.junos.utils.config.Config.commit_check"
            ) as mock_commit_check, patch(
                "jnpr.junos.utils.config.Config.diff"
            ) as mock_diff, patch(
                "jnpr.junos.utils.config.Config.load"
            ) as mock_load, patch(
                "salt.utils.files.safe_rm"
            ) as mock_safe_rm, patch(
                "salt.utils.files.mkstemp"
            ) as mock_mkstemp, patch(
                "os.path.isfile"
            ) as mock_isfile, patch(
                "salt.utils.files.fopen", mock_open(), create=True
            ) as m_open, patch(
                "os.path.getsize"
            ) as mock_getsize:
                mock_isfile.return_value = True
                mock_getsize.return_value = 10
                mock_mkstemp.return_value = "test/path/config"
                mock_diff.return_value = "diff"
                mock_commit_check.return_value = True

                args = {
                    "__pub_user": "root",
                    "__pub_arg": [{"overwrite": True}],
                    "overwrite": True,
                    "__pub_fun": "junos.install_config",
                    "__pub_jid": "20170222213858582619",
                    "__pub_tgt": "mac_min",
                    "__pub_tgt_type": "glob",
                    "__pub_ret": "",
                }

                ret = dict()
                ret["message"] = "Successfully loaded and committed!"
                ret["out"] = True
                self.assertEqual(
                    junos.install_config("salt://actual/path/config.xml", **args), ret
                )
                mock_load.assert_called_with(
                    path="test/path/config", format="xml", overwrite=True
                )

    def test_install_config_overwrite_false(self):
        with patch.dict(
            junos.__salt__,
            {
                "cp.is_cached": MagicMock(return_value="test/path/config"),
                "cp.hash_file": MagicMock(
                    return_value={"hash_type": "sha256", "hsum": "a386e49c17"}
                ),
                "file.get_hash": MagicMock(return_value="a386e49c17"),
            },
        ):
            with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
                "jnpr.junos.utils.config.Config.commit_check"
            ) as mock_commit_check, patch(
                "jnpr.junos.utils.config.Config.diff"
            ) as mock_diff, patch(
                "jnpr.junos.utils.config.Config.load"
            ) as mock_load, patch(
                "salt.utils.files.safe_rm"
            ) as mock_safe_rm, patch(
                "salt.utils.files.mkstemp"
            ) as mock_mkstemp, patch(
                "os.path.isfile"
            ) as mock_isfile, patch(
                "salt.utils.files.fopen", mock_open(), create=True
            ) as m_open, patch(
                "os.path.getsize"
            ) as mock_getsize:
                mock_isfile.return_value = True
                mock_getsize.return_value = 10
                mock_mkstemp.return_value = "test/path/config"
                mock_diff.return_value = "diff"
                mock_commit_check.return_value = True

                args = {
                    "__pub_user": "root",
                    "__pub_arg": [{"overwrite": False}],
                    "overwrite": False,
                    "__pub_fun": "junos.install_config",
                    "__pub_jid": "20170222213858582619",
                    "__pub_tgt": "mac_min",
                    "__pub_tgt_type": "glob",
                    "__pub_ret": "",
                }

                ret = dict()
                ret["message"] = "Successfully loaded and committed!"
                ret["out"] = True
                self.assertEqual(
                    junos.install_config("salt://actual/path/config", **args), ret
                )
                mock_load.assert_called_with(
                    path="test/path/config", format="text", merge=True
                )

    def test_install_config_load_causes_exception(self):
        with patch("jnpr.junos.utils.config.Config.diff") as mock_diff, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch("salt.utils.files.safe_rm") as mock_safe_rm, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = "test/path/config"
            mock_load.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Could not load configuration due to : "Test exception"'
            ret["format"] = "set"
            ret["out"] = False
            self.assertEqual(junos.install_config(path="actual/path/config.set"), ret)

    def test_install_config_no_diff(self):
        with patch("jnpr.junos.utils.config.Config.diff") as mock_diff, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch("salt.utils.files.safe_rm") as mock_safe_rm, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = "test/path/config"
            mock_diff.return_value = None
            ret = dict()
            ret["message"] = "Configuration already applied!"
            ret["out"] = True
            self.assertEqual(junos.install_config("actual/path/config"), ret)

    def test_install_config_write_diff(self):
        with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.diff"
        ) as mock_diff, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "salt.utils.files.fopen"
        ) as mock_fopen, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = "test/path/config"
            mock_diff.return_value = "diff"
            mock_commit_check.return_value = True

            args = {
                "__pub_user": "root",
                "__pub_arg": [{"diffs_file": "copy/config/here"}],
                "diffs_file": "copy/config/here",
                "__pub_fun": "junos.install_config",
                "__pub_jid": "20170222213858582619",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }

            ret = dict()
            ret["message"] = "Successfully loaded and committed!"
            ret["out"] = True
            self.assertEqual(junos.install_config("actual/path/config", **args), ret)
            mock_fopen.assert_called_with("copy/config/here", "w")

    def test_install_config_write_diff_exception(self):
        with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.diff"
        ) as mock_diff, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as mock_fopen, patch(
            "salt.utils.stringutils.to_str"
        ) as mock_strgutils, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = "test/path/config"
            mock_diff.return_value = "diff"
            mock_commit_check.return_value = True
            mock_strgutils.side_effect = self.raise_exception

            args = {
                "__pub_user": "root",
                "__pub_arg": [{"diffs_file": "copy/config/here"}],
                "diffs_file": "copy/config/here",
                "__pub_fun": "junos.install_config",
                "__pub_jid": "20170222213858582619",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }

            ret = dict()
            ret["message"] = "Could not write into diffs_file due to: 'Test exception'"
            ret["out"] = False
            self.assertEqual(junos.install_config("actual/path/config", **args), ret)

    def test_install_config_commit_params(self):
        with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.diff"
        ) as mock_diff, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = "test/path/config"
            mock_diff.return_value = "diff"
            mock_commit_check.return_value = True
            args = {
                "comment": "comitted via salt",
                "__pub_user": "root",
                "__pub_arg": [{"comment": "comitted via salt", "confirm": 3}],
                "confirm": 3,
                "__pub_fun": "junos.commit",
                "__pub_jid": "20170221182856987820",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            ret = dict()
            ret["message"] = "Successfully loaded and committed!"
            ret["out"] = True
            self.assertEqual(junos.install_config("actual/path/config", **args), ret)
            mock_commit.assert_called_with(comment="comitted via salt", confirm=3)

    def test_install_config_commit_check_fails(self):
        with patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.diff"
        ) as mock_diff, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = "test/path/config"
            mock_diff.return_value = "diff"
            mock_commit_check.return_value = False

            ret = dict()
            ret["message"] = (
                "Loaded configuration but commit check failed, hence rolling back"
                " configuration."
            )
            ret["out"] = False
            self.assertEqual(junos.install_config("actual/path/config.xml"), ret)

    def test_install_config_commit_exception(self):
        with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.diff"
        ) as mock_diff, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = "test/path/config"
            mock_diff.return_value = "diff"
            mock_commit_check.return_value = True
            mock_commit.side_effect = self.raise_exception
            ret = dict()
            ret[
                "message"
            ] = 'Commit check successful but commit failed with "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.install_config("actual/path/config"), ret)

    def test_install_config_test_mode(self):
        with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.diff"
        ) as mock_diff, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = "test/path/config"
            mock_diff.return_value = "diff"
            mock_commit_check.return_value = True
            ret = dict()
            ret["message"] = (
                "Commit check passed, but skipping commit for dry-run and rolling back"
                " configuration."
            )
            ret["out"] = True
            self.assertEqual(junos.install_config("actual/path/config", test=True), ret)
            mock_commit.assert_not_called()

    def test_install_config_write_diff_dynamic_mode(self):
        with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.diff"
        ) as mock_diff, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = "test/path/config"
            mock_diff.return_value = "diff"
            mock_commit_check.return_value = True
            ret = dict()
            ret[
                "message"
            ] = "Write diff is not supported with dynamic/ephemeral configuration mode"
            ret["out"] = False
            self.assertEqual(
                junos.install_config(
                    "actual/path/config", mode="dynamic", diffs_file="/path/to/dif"
                ),
                ret,
            )
            mock_commit.assert_not_called()

    def test_install_config_unknown_mode(self):
        with patch("jnpr.junos.utils.config.Config.commit") as mock_commit, patch(
            "jnpr.junos.utils.config.Config.commit_check"
        ) as mock_commit_check, patch(
            "jnpr.junos.utils.config.Config.diff"
        ) as mock_diff, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_isfile.return_value = True
            mock_getsize.return_value = 10
            mock_mkstemp.return_value = "test/path/config"
            mock_diff.return_value = "diff"
            mock_commit_check.return_value = True
            ret = dict()
            ret["message"] = "install_config failed due to: unsupported action: abcdef"
            ret["out"] = False
            self.assertEqual(
                junos.install_config("actual/path/config", mode="abcdef"), ret
            )
            mock_commit.assert_not_called()

    def test_zeroize(self):
        with patch("jnpr.junos.device.Device.cli") as mock_cli:
            result = junos.zeroize()
            ret = dict()
            ret["out"] = True
            ret["message"] = "Completed zeroize and rebooted"
            mock_cli.assert_called_once_with("request system zeroize")
            self.assertEqual(result, ret)

    def test_zeroize_throw_exception(self):
        with patch("jnpr.junos.device.Device.cli") as mock_cli:
            mock_cli.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Could not zeroize due to : "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.zeroize(), ret)

    def test_install_os_without_args(self):
        ret = dict()
        ret[
            "message"
        ] = "Please provide the salt path where the junos image is present."
        ret["out"] = False
        self.assertEqual(junos.install_os(), ret)

    def test_install_os_cp_fails(self):
        with patch.dict(
            junos.__salt__,
            {
                "cp.is_cached": MagicMock(return_value="/pat/to/tmp/file"),
                "cp.hash_file": MagicMock(
                    return_value={"hash_type": "sha256", "hsum": "a386e49c17"}
                ),
                "file.get_hash": MagicMock(return_value="xxxx"),
                "file.rmdir": MagicMock(return_value="True"),
            },
        ):
            with patch("jnpr.junos.utils.sw.SW.install") as mock_install, patch(
                "salt.utils.files.safe_rm"
            ) as mock_safe_rm, patch(
                "salt.utils.files.fopen", mock_open(), create=True
            ) as m_open, patch(
                "salt.utils.files.mkstemp"
            ) as mock_mkstemp, patch(
                "os.path.isfile"
            ) as mock_isfile, patch(
                "os.path.getsize"
            ) as mock_getsize:
                mock_getsize.return_value = 10
                mock_isfile.return_value = False
                mock_install.return_value = (
                    False,
                    "Invalid path. Please provide a valid image path",
                )
                ret = dict()
                ret["message"] = (
                    "Installation failed. Reason: Invalid path. Please provide a valid"
                    " image path"
                )
                ret["out"] = False
                self.assertEqual(junos.install_os("salt://image/path/"), ret)

    def test_install_os_image_cp_fails(self):
        with patch.dict(
            junos.__salt__, {"file.file_exists": MagicMock(return_value=False)}
        ):
            ret = dict()
            ret["message"] = "Invalid path. Please provide a valid image path"
            ret["out"] = False
            self.assertEqual(junos.install_os("/image/path/"), ret)

    def test_install_os(self):
        with patch.dict(
            junos.__salt__,
            {
                "cp.is_cached": MagicMock(return_value="test/path/config"),
                "cp.hash_file": MagicMock(
                    return_value={"hash_type": "sha256", "hsum": "a386e49c17"}
                ),
                "file.get_hash": MagicMock(return_value="a386e49c17"),
            },
        ):
            with patch("jnpr.junos.utils.sw.SW.install") as mock_install, patch(
                "salt.utils.files.safe_rm"
            ) as mock_safe_rm, patch(
                "salt.utils.files.fopen", mock_open(), create=True
            ) as m_open, patch(
                "salt.utils.files.mkstemp"
            ) as mock_mkstemp, patch(
                "os.path.isfile"
            ) as mock_isfile, patch(
                "os.path.getsize"
            ) as mock_getsize:
                mock_getsize.return_value = 10
                mock_isfile.return_value = True
                mock_install.return_value = True, "installed"
                ret = dict()
                ret["out"] = True
                ret["message"] = "Installed the os."
                self.assertEqual(junos.install_os("path"), ret)

    def test_install_os_failure(self):
        with patch("jnpr.junos.utils.sw.SW.install") as mock_install, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = True
            mock_install.return_value = False, "because we are testing failure"
            ret = dict()
            ret["out"] = False
            ret[
                "message"
            ] = "Installation failed. Reason: because we are testing failure"
            self.assertEqual(junos.install_os("path"), ret)

    def test_install_os_with_reboot_arg(self):
        with patch("jnpr.junos.utils.sw.SW.install") as mock_install, patch(
            "jnpr.junos.utils.sw.SW.reboot"
        ) as mock_reboot, patch("salt.utils.files.safe_rm") as mock_safe_rm, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = True
            mock_install.return_value = True, "installed"
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"reboot": True}],
                "reboot": True,
                "__pub_fun": "junos.install_os",
                "__pub_jid": "20170222213858582619",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            ret = dict()
            ret["message"] = "Successfully installed and rebooted!"
            ret["out"] = True
            self.assertEqual(junos.install_os("path", **args), ret)

    def test_install_os_pyez_install_throws_exception(self):
        with patch("jnpr.junos.utils.sw.SW.install") as mock_install, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = True
            mock_install.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Installation failed due to: "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.install_os("path"), ret)

    def test_install_os_with_reboot_raises_exception(self):
        with patch("jnpr.junos.utils.sw.SW.install") as mock_install, patch(
            "jnpr.junos.utils.sw.SW.reboot"
        ) as mock_reboot, patch("salt.utils.files.safe_rm") as mock_safe_rm, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = True
            mock_install.return_value = True, "installed"
            mock_reboot.side_effect = self.raise_exception
            args = {
                "__pub_user": "root",
                "__pub_arg": [{"reboot": True}],
                "reboot": True,
                "__pub_fun": "junos.install_os",
                "__pub_jid": "20170222213858582619",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            ret = dict()
            ret[
                "message"
            ] = 'Installation successful but reboot failed due to : "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.install_os("path", **args), ret)

    def test_install_os_no_copy(self):
        with patch("jnpr.junos.utils.sw.SW.install") as mock_install, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = True
            mock_install.return_value = True, "installed"
            ret = dict()
            ret["out"] = True
            ret["message"] = "Installed the os."
            self.assertEqual(junos.install_os("path", no_copy=True), ret)
            mock_install.assert_called_with(
                "path", no_copy=True, progress=True, timeout=1800
            )
            mock_mkstemp.assert_not_called()
            mock_safe_rm.assert_not_called()

    def test_install_os_issu(self):
        with patch("jnpr.junos.utils.sw.SW.install") as mock_install, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = True
            mock_install.return_value = True, "installed"
            ret = dict()
            ret["out"] = True
            ret["message"] = "Installed the os."
            self.assertEqual(junos.install_os("path", issu=True), ret)
            mock_install.assert_called_with(ANY, issu=True, progress=True, timeout=1800)

    def test_install_os_add_params(self):
        with patch("jnpr.junos.utils.sw.SW.install") as mock_install, patch(
            "salt.utils.files.safe_rm"
        ) as mock_safe_rm, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstemp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "os.path.getsize"
        ) as mock_getsize:
            mock_getsize.return_value = 10
            mock_isfile.return_value = True
            mock_install.return_value = True, "installed"
            ret = dict()
            ret["out"] = True
            ret["message"] = "Installed the os."
            remote_path = "/path/to/file"
            self.assertEqual(
                junos.install_os(
                    "path", remote_path=remote_path, nssu=True, validate=True
                ),
                ret,
            )
            mock_install.assert_called_with(
                ANY,
                nssu=True,
                remote_path=remote_path,
                progress=True,
                validate=True,
                timeout=1800,
            )

    def test_file_copy_without_args(self):
        self.assertRaises(TypeError, junos.file_copy)

    @patch("paramiko.SSHClient")
    @patch("scp.SCPClient.put")
    @patch("scp.SCPClient.__init__")
    def test_file_copy_invalid_src(self, mock_scpclient, mock_put, mock_ssh):
        mock_scpclient.return_value = None
        invalid_path = "invalid/file/path"
        mock_put.side_effect = Exception(invalid_path)
        with patch("os.path.isfile") as mock_isfile:
            mock_isfile.return_value = False
            ret = dict()
            ret["message"] = 'Could not copy file : "invalid/file/path"'
            ret["out"] = False
            self.assertEqual(junos.file_copy(invalid_path, "file"), ret)

    def test_file_copy_without_dest(self):
        self.assertRaises(TypeError, junos.file_copy, src="/home/user/config.set")

    def test_file_copy(self):
        with patch("salt.modules.junos.SCP") as mock_scp, patch(
            "os.path.isfile"
        ) as mock_isfile:
            mock_isfile.return_value = True
            ret = dict()
            ret["message"] = "Successfully copied file from test/src/file to file"
            ret["out"] = True
            self.assertEqual(junos.file_copy(dest="file", src="test/src/file"), ret)

    def test_file_copy_exception(self):
        with patch("salt.modules.junos.SCP") as mock_scp, patch(
            "os.path.isfile"
        ) as mock_isfile:
            mock_isfile.return_value = True
            mock_scp.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'Could not copy file : "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.file_copy(dest="file", src="test/src/file"), ret)

    # These test cases test the __virtual__ function, used internally by salt
    # to check if the given module is loadable. This function is not used by
    # an external user.

    def test_virtual_proxy_unavailable(self):
        with patch.dict(junos.__opts__, {}):
            res = (
                False,
                "The junos or dependent module could not be loaded: "
                "junos-eznc or jxmlease or yamlordereddictloader or "
                "proxy could not be loaded.",
            )
            self.assertEqual(junos.__virtual__(), res)

    def test_virtual_all_true(self):
        with patch.dict(junos.__opts__, {"proxy": "test"}):
            self.assertEqual(junos.__virtual__(), "junos")

    def test_rpc_without_args(self):
        ret = dict()
        ret["message"] = "Please provide the rpc to execute."
        ret["out"] = False
        self.assertEqual(junos.rpc(), ret)

    def test_rpc_get_config_exception(self):
        with patch("jnpr.junos.device.Device.execute") as mock_execute:
            mock_execute.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'RPC execution failed due to "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.rpc("get_config"), ret)

    def test_rpc_get_config_filter(self):
        with patch("jnpr.junos.device.Device.execute") as mock_execute:
            mock_execute.return_value = etree.XML("<reply><rpc/></reply>")
            args = {
                "__pub_user": "root",
                "__pub_arg": [
                    "get-config",
                    {"filter": "<configuration><system/></configuration>"},
                ],
                "__pub_fun": "junos.rpc",
                "__pub_jid": "20170314162715866528",
                "__pub_tgt": "mac_min",
                "__pub_tgt_type": "glob",
                "filter": "<configuration><system/></configuration>",
                "__pub_ret": "",
            }
            junos.rpc("get-config", **args)
            exec_args = mock_execute.call_args
            expected_rpc = (
                "<get-configuration "
                'format="xml"><configuration><system/></configuration></get-configuration>'
            )
            self.assertEqualXML(exec_args[0][0], expected_rpc)

    def test_rpc_get_interface_information(self):
        with patch("jnpr.junos.device.Device.execute") as mock_execute:
            junos.rpc("get-interface-information", format="json")
            args = mock_execute.call_args
            expected_rpc = '<get-interface-information format="json"/>'
            self.assertEqualXML(args[0][0], expected_rpc)

    def test_rpc_get_interface_information_with_kwargs(self):
        with patch("jnpr.junos.device.Device.execute") as mock_execute:
            args = {
                "__pub_user": "root",
                "__pub_arg": [
                    "get-interface-information",
                    "",
                    "text",
                    {"terse": True, "interface_name": "lo0", "format": "text"},
                ],
                "format": "text",
                "terse": True,
                "__pub_fun": "junos.rpc",
                "__pub_jid": "20170314160943363563",
                "__pub_tgt": "mac_min",
                "interface_name": "lo0",
                "__pub_tgt_type": "glob",
                "__pub_ret": "",
            }
            junos.rpc("get-interface-information", **args)
            args = mock_execute.call_args
            expected_rpc = (
                '<get-interface-information format="text">'
                "<terse/><interface-name>lo0</interface-name></get-interface-information>"
            )
            self.assertEqualXML(etree.tostring(args[0][0]), expected_rpc)

    def test_rpc_get_chassis_inventory_filter_as_arg(self):
        with patch("salt.modules.junos.jxmlease.parse") as mock_jxmlease, patch(
            "salt.modules.junos.etree.tostring"
        ) as mock_tostring, patch(
            "salt.modules.junos.logging.Logger.warning"
        ) as mock_warning, patch(
            "jnpr.junos.device.Device.execute"
        ) as mock_execute:
            junos.rpc(
                "get-chassis-inventory",
                filter="<configuration><system/></configuration>",
            )
            mock_warning.assert_called_with(
                'Filter ignored as it is only used with "get-config" rpc'
            )

    def test_rpc_get_interface_information_exception(self):
        with patch("jnpr.junos.device.Device.execute") as mock_execute:
            mock_execute.side_effect = self.raise_exception
            ret = dict()
            ret["message"] = 'RPC execution failed due to "Test exception"'
            ret["out"] = False
            self.assertEqual(junos.rpc("get_interface_information"), ret)

    def test_rpc_write_file_format_text(self):
        with patch("jnpr.junos.device.Device.execute") as mock_execute:
            mock_execute.return_value = etree.XML(
                "<rpc-reply>text rpc reply</rpc-reply>"
            )
            with patch("salt.utils.files.fopen", mock_open(), create=True) as m_open:
                junos.rpc("get-chassis-inventory", dest="/path/to/file", format="text")
                writes = m_open.write_calls()
                assert writes == ["text rpc reply"], writes

    def test_rpc_write_file_format_json(self):
        with patch("jnpr.junos.device.Device.execute") as mock_execute, patch(
            "salt.utils.json.dumps"
        ) as mock_dumps:
            mock_dumps.return_value = "json rpc reply"
            with patch("salt.utils.files.fopen", mock_open(), create=True) as m_open:
                junos.rpc("get-chassis-inventory", dest="/path/to/file", format="json")
                writes = m_open.write_calls()
                assert writes == ["json rpc reply"], writes

    def test_rpc_write_file(self):
        with patch("salt.modules.junos.jxmlease.parse") as mock_parse, patch(
            "salt.modules.junos.etree.tostring"
        ) as mock_tostring, patch("jnpr.junos.device.Device.execute") as mock_execute:
            mock_tostring.return_value = "xml rpc reply"
            with patch("salt.utils.files.fopen", mock_open(), create=True) as m_open:
                junos.rpc("get-chassis-inventory", dest="/path/to/file")
                writes = m_open.write_calls()
                assert writes == ["xml rpc reply"], writes

    def test_lock_success(self):
        ret_exp = {"out": True, "message": "Successfully locked the configuration."}
        ret = junos.lock()
        self.assertEqual(ret, ret_exp)

    def test_lock_error(self):
        ret_exp = {"out": False, "message": 'Could not gain lock due to : "LockError"'}
        with patch("jnpr.junos.utils.config.Config.lock") as mock_lock:
            mock_lock.side_effect = LockError(None)
            ret = junos.lock()
            self.assertEqual(ret, ret_exp)

    def test_unlock_success(self):
        ret_exp = {"out": True, "message": "Successfully unlocked the configuration."}
        ret = junos.unlock()
        self.assertEqual(ret, ret_exp)

    def test_unlock_error(self):
        ret_exp = {
            "out": False,
            "message": 'Could not unlock configuration due to : "UnlockError"',
        }
        with patch("jnpr.junos.utils.config.Config.unlock") as mock_unlock:
            mock_unlock.side_effect = UnlockError(None)
            ret = junos.unlock()
            self.assertEqual(ret, ret_exp)

    def test_load_none_path(self):
        ret_exp = {
            "out": False,
            "message": (
                "Please provide the salt path where the configuration is present"
            ),
        }
        ret = junos.load()
        self.assertEqual(ret, ret_exp)

    def test_load_wrong_tmp_file(self):
        ret_exp = {
            "out": False,
            "message": (
                'Could not load configuration due to : "[Errno 2] No such file or'
                " directory: '/pat/to/tmp/file'\""
            ),
            "format": "text",
        }
        with patch.dict(
            junos.__salt__,
            {
                "cp.is_cached": MagicMock(return_value="/pat/to/tmp/file"),
                "cp.hash_file": MagicMock(
                    return_value={"hash_type": "sha256", "hsum": "a386e49c17"}
                ),
                "file.get_hash": MagicMock(return_value="a386e49c17"),
            },
        ):
            with patch(
                "salt.utils.files.fopen", mock_open(), create=True
            ) as m_open, patch("os.path.getsize") as mock_getsize, patch(
                "salt.utils.files.mkstemp"
            ) as mock_mkstmp:
                mock_mkstmp.return_value = "/pat/to/tmp/file"
                mock_getsize.return_value = 1000
                ret = junos.load("salt://path/to/file")
                self.assertEqual(ret, ret_exp)

    def test_load_invalid_path(self):
        with patch("salt.utils.files.mkstemp") as mock_mkstmp:
            mock_mkstmp.return_value = "/path/to/file"
            self.assertRaises(FileNotFoundError, junos.load, path="/path/to/file")

    def test_load_no_extension(self):
        ret_exp = {"out": True, "message": "Successfully loaded the configuration."}
        with patch("os.path.getsize") as mock_getsize, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstmp, patch(
            "os.path.isfile"
        ) as mock_isfile:
            mock_getsize.return_value = 1000
            mock_mkstmp.return_value = "/path/to/file"
            mock_isfile.return_value = True
            ret = junos.load("/path/to/file")
            mock_load.assert_called_with(format="text", path="/path/to/file")
            self.assertEqual(ret, ret_exp)

    def test_load_xml_extension(self):
        ret_exp = {"out": True, "message": "Successfully loaded the configuration."}
        with patch("os.path.getsize") as mock_getsize, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch("os.path.isfile") as mock_isfile, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstmp:
            mock_getsize.return_value = 1000
            mock_mkstmp.return_value = "/path/to/file.xml"
            mock_isfile.return_value = True
            ret = junos.load("/path/to/file.xml")
            mock_load.assert_called_with(format="xml", path="/path/to/file.xml")
            self.assertEqual(ret, ret_exp)

    def test_load_xml_extension_with_kwargs(self):
        ret_exp = {"out": True, "message": "Successfully loaded the configuration."}
        with patch("os.path.getsize") as mock_getsize, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch("salt.utils.files.mkstemp") as mock_mkstmp, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "salt.utils.files.fopen"
        ) as fopen, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstmp:
            mock_mkstmp.return_value = "/path/to/file"
            mock_isfile.return_value = True
            ret = junos.load("/path/to/file.xml", template_vars=dict(hostname="test"))
            mock_load.assert_called_with(
                format="xml", path="/path/to/file", template_vars={"hostname": "test"}
            )
            self.assertEqual(ret, ret_exp)

    def test_load_set_extension(self):
        ret_exp = {"out": True, "message": "Successfully loaded the configuration."}
        with patch("os.path.getsize") as mock_getsize, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch("salt.utils.files.mkstemp") as mock_mkstmp, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.isfile"
        ) as mock_isfile:
            mock_getsize.return_value = 1000
            mock_mkstmp.return_value = "/path/to/file.set"
            mock_isfile.return_value = True
            ret = junos.load("/path/to/file.set")
            mock_load.assert_called_with(format="set", path="/path/to/file.set")
            self.assertEqual(ret, ret_exp)

    def test_load_replace_true(self):
        ret_exp = {"out": True, "message": "Successfully loaded the configuration."}
        with patch("os.path.getsize") as mock_getsize, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch("salt.utils.files.mkstemp") as mock_mkstmp, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.isfile"
        ) as mock_isfile:
            mock_getsize.return_value = 1000
            mock_mkstmp.return_value = "/path/to/file"
            mock_isfile.return_value = True
            ret = junos.load("/path/to/file", replace=True)
            mock_load.assert_called_with(
                format="text", merge=False, path="/path/to/file"
            )
            self.assertEqual(ret, ret_exp)

    def test_load_replace_false(self):
        ret_exp = {"out": True, "message": "Successfully loaded the configuration."}
        with patch("os.path.getsize") as mock_getsize, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch("salt.utils.files.mkstemp") as mock_mkstmp, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.isfile"
        ) as mock_isfile:
            mock_getsize.return_value = 1000
            mock_mkstmp.return_value = "/path/to/file"
            mock_isfile.return_value = True
            ret = junos.load("/path/to/file", replace=False)
            mock_load.assert_called_with(
                format="text", replace=False, path="/path/to/file"
            )
            self.assertEqual(ret, ret_exp)

    def test_load_overwrite_true(self):
        ret_exp = {"out": True, "message": "Successfully loaded the configuration."}
        with patch("os.path.getsize") as mock_getsize, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch("salt.utils.files.mkstemp") as mock_mkstmp, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.isfile"
        ) as mock_isfile:
            mock_getsize.return_value = 1000
            mock_mkstmp.return_value = "/path/to/file"
            mock_isfile.return_value = True
            ret = junos.load("/path/to/file", overwrite=True)
            mock_load.assert_called_with(
                format="text", overwrite=True, path="/path/to/file"
            )
            self.assertEqual(ret, ret_exp)

    def test_load_overwrite_false(self):
        ret_exp = {"out": True, "message": "Successfully loaded the configuration."}
        with patch("os.path.getsize") as mock_getsize, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "salt.utils.files.mkstemp"
        ) as mock_mkstmp, patch(
            "os.path.isfile"
        ) as mock_isfile:
            mock_getsize.return_value = 1000
            mock_mkstmp.return_value = "/path/to/file"
            mock_isfile.return_value = True
            ret = junos.load("/path/to/file", overwrite=False)
            mock_load.assert_called_with(
                format="text", merge=True, path="/path/to/file"
            )
            self.assertEqual(ret, ret_exp)

    def test_load_error(self):
        ret_exp = {
            "out": False,
            "format": "text",
            "message": 'Could not load configuration due to : "Test Error"',
        }
        with patch("os.path.getsize") as mock_getsize, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load, patch("salt.utils.files.mkstemp") as mock_mkstmp, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch(
            "os.path.isfile"
        ) as mock_isfile:
            mock_getsize.return_value = 1000
            mock_mkstmp.return_value = "/path/to/file"
            mock_isfile.return_value = True
            mock_load.side_effect = Exception("Test Error")
            ret = junos.load("/path/to/file")
            self.assertEqual(ret, ret_exp)

    def test_load_template(self):
        ret_exp = {
            "out": True,
            "message": "Successfully loaded the configuration.",
        }
        with patch("os.path.getsize") as mock_getsize, patch(
            "jnpr.junos.utils.config.Config.load"
        ) as mock_load:
            ret = junos.load("tests/unit/modules/templates/basic2.j2", test=True)
            self.assertEqual(ret, ret_exp)

    def test_commit_check_success(self):
        ret_exp = {"out": True, "message": "Commit check succeeded."}
        ret = junos.commit_check()
        self.assertEqual(ret, ret_exp)

    def test_commit_check_error(self):
        ret_exp = {"out": False, "message": "Commit check failed with "}
        with patch("jnpr.junos.utils.config.Config.commit_check") as mock_check:
            mock_check.side_effect = Exception
            ret = junos.commit_check()
            self.assertEqual(ret, ret_exp)

    def test_get_table_wrong_path(self):
        table = "ModuleTable"
        file = "sample.yml"
        path = "/path/to/file"
        ret_exp = {
            "out": False,
            "hostname": "1.1.1.1",
            "tablename": "ModuleTable",
            "message": "Given table file {} cannot be located".format(file),
        }
        with patch.dict(
            junos.__salt__, {"file.file_exists": MagicMock(return_value=False)}
        ):
            with patch("jnpr.junos.factory.FactoryLoader.load") as mock_load, patch(
                "salt.utils.files.fopen"
            ) as mock_fopen, patch(
                "jnpr.junos.factory.FactoryLoader.load"
            ) as mock_load:
                ret = junos.get_table(table, file, path)
                self.assertEqual(ret, ret_exp)
                mock_load.assert_not_called()

    def test_get_table_no_path_no_file(self):
        table = "ModuleTable"
        file = "inventory.yml"
        ret_exp = {
            "out": False,
            "hostname": "1.1.1.1",
            "tablename": "ModuleTable",
            "message": "Given table file {} cannot be located".format(file),
        }
        with patch.dict(
            junos.__salt__, {"file.file_exists": MagicMock(return_value=False)}
        ):
            with patch("jnpr.junos.factory.FactoryLoader.load") as mock_load, patch(
                "glob.glob"
            ) as mock_fopen:
                mock_fopen.return_value = []
                ret = junos.get_table(table, file)
                self.assertEqual(ret, ret_exp)
                mock_load.assert_not_called()

    def test_get_table_yaml_load_error(self):
        table = "ModuleTable"
        file = "inventory.yml"
        path = "/path/to/file"
        message = "File not located test"
        ret_exp = {
            "out": False,
            "hostname": "1.1.1.1",
            "tablename": "ModuleTable",
            "message": "Uncaught exception during YAML Load - please report: {}".format(
                message
            ),
        }
        with patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as mock_file, patch("glob.glob") as mock_fopen, patch.object(
            yaml, "load"
        ) as mock_yamlload:
            mock_fopen.return_value = ["/path/to/file"]
            mock_yamlload.side_effect = OSError(message)
            ret = junos.get_table(table, file, path)
            self.assertEqual(ret, ret_exp)

    def test_get_table_api_error(self):
        table = "sample"
        file = "inventory.yml"
        table_yamlload = {
            "ModuleTable": {
                "item": (
                    ".//chassis-sub-module|.//chassis-module|.//chassis-sub-sub-module"
                ),
                "key": "name",
                "rpc": "get-chassis-inventory",
                "view": "ModuleTableView",
            },
            "ModuleTableView": {
                "fields": {
                    "jname": "name",
                    "pn": "part-number",
                    "sn": "serial-number",
                    "type": "description",
                    "ver": "version",
                },
            },
        }
        ret_exp = {
            "out": False,
            "hostname": "1.1.1.1",
            "tablename": "sample",
            "message": (
                "Uncaught exception during get API call - please report: '{}'".format(
                    str(table)
                )
            ),
        }
        with patch("jnpr.junos.device.Device.execute") as mock_execute, patch(
            "yaml.load"
        ) as mock_yamlload, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open:
            mock_yamlload.return_value = table_yamlload
            ret = junos.get_table(table, file)
            self.assertEqual(ret["out"], ret_exp["out"])
            self.assertEqual(ret["tablename"], ret_exp["tablename"])
            self.assertEqual(ret["message"], ret_exp["message"])

    def test_get_table_connect_closed_error(self):
        table = "ModuleTable"
        file = "inventory.yml"
        table_yamlload = {
            "ModuleTable": {
                "item": (
                    ".//chassis-sub-module|.//chassis-module|.//chassis-sub-sub-module"
                ),
                "key": "name",
                "rpc": "get-chassis-inventory",
                "view": "ModuleTableView",
            },
            "ModuleTableView": {
                "fields": {
                    "jname": "name",
                    "pn": "part-number",
                    "sn": "serial-number",
                    "type": "description",
                    "ver": "version",
                },
            },
        }
        ret_exp = {
            "out": False,
            "hostname": "1.1.1.1",
            "tablename": "ModuleTable",
            "message": (
                "Got ConnectClosedError exception. Connection lost with Device(1.1.1.1)"
            ),
        }
        with patch("jnpr.junos.factory.optable.OpTable.get") as mock_load, patch(
            "yaml.load"
        ) as mock_yamlload, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open:
            dev = Device(host="1.1.1.1", user="rick")
            mock_load.side_effect = ConnectClosedError(dev)
            mock_yamlload.return_value = table_yamlload
            ret = junos.get_table(table, file)
            self.assertEqual(ret["out"], ret_exp["out"])
            self.assertEqual(ret["tablename"], ret_exp["tablename"])
            self.assertEqual(ret["message"], ret_exp["message"])

    def test_get_table_inventory(self):
        table = "ModuleTable"
        file = "inventory.yml"
        pyez_tables_path = os.path.dirname(os.path.abspath(tables_dir.__file__))
        path = pyez_tables_path
        table_yamlload = {
            "ModuleTable": {
                "item": (
                    ".//chassis-sub-module|.//chassis-module|.//chassis-sub-sub-module"
                ),
                "key": "name",
                "rpc": "get-chassis-inventory",
                "view": "ModuleTableView",
            },
            "ModuleTableView": {
                "fields": {
                    "jname": "name",
                    "pn": "part-number",
                    "sn": "serial-number",
                    "type": "description",
                    "ver": "version",
                },
            },
        }
        with patch("jnpr.junos.device.Device.execute") as mock_execute, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch("yaml.load") as mock_yamlload, patch(
            "salt.utils.json.dumps"
        ) as mock_dumps:
            mock_dumps.return_value = "json rpc reply"
            mock_yamlload.return_value = table_yamlload
            ret = junos.get_table(table, file, path)
            self.assertEqual(ret["out"], True)

    def test_get_table_no_path_inventory(self):
        table = "ModuleTable"
        file = "inventory.yml"
        table_yamlload = {
            "ModuleTable": {
                "item": (
                    ".//chassis-sub-module|.//chassis-module|.//chassis-sub-sub-module"
                ),
                "key": "name",
                "rpc": "get-chassis-inventory",
                "view": "ModuleTableView",
            },
            "ModuleTableView": {
                "fields": {
                    "jname": "name",
                    "pn": "part-number",
                    "sn": "serial-number",
                    "type": "description",
                    "ver": "version",
                },
            },
        }
        with patch("jnpr.junos.device.Device.execute") as mock_execute, patch(
            "salt.utils.files.fopen", mock_open(), create=True
        ) as m_open, patch("yaml.load") as mock_yamlload, patch(
            "salt.utils.json.dumps"
        ) as mock_dumps:
            mock_dumps.return_value = "json rpc reply"
            mock_yamlload.return_value = table_yamlload
            ret = junos.get_table(table, file)
            self.assertEqual(ret["out"], True)
