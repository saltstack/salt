"""
:codeauthor: Shane Lee <slee@saltstack.com>
"""
import copy
import glob
import os

import pytest
import salt.config
import salt.loader
import salt.modules.win_lgpo as win_lgpo
import salt.states.win_lgpo
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase, skipIf


class WinLGPOTestCase(TestCase):
    """
    Test cases for salt.modules.win_lgpo
    """

    encoded_null = chr(0).encode("utf-16-le")

    def test__getAdmlDisplayName(self):
        display_name = "$(string.KeepAliveTime1)"
        adml_xml_data = "junk, we are mocking the return"
        obj_xpath = Mock()
        obj_xpath.text = "300000 or 5 minutes (recommended) "
        mock_xpath_obj = MagicMock(return_value=[obj_xpath])
        with patch.object(win_lgpo, "ADML_DISPLAY_NAME_XPATH", mock_xpath_obj):
            result = win_lgpo._getAdmlDisplayName(
                adml_xml_data=adml_xml_data, display_name=display_name
            )
        expected = "300000 or 5 minutes (recommended)"
        self.assertEqual(result, expected)

    def test__regexSearchKeyValueCombo_enabled(self):
        """
        Make sure
        """
        policy_data = (
            b"[\x00s\x00o\x00f\x00t\x00w\x00a\x00r\x00e\x00\\\x00p"
            b"\x00o\x00l\x00i\x00c\x00i\x00e\x00s\x00\\\x00m\x00i"
            b"\x00c\x00r\x00o\x00s\x00o\x00f\x00t\x00\\\x00w\x00i"
            b"\x00n\x00d\x00o\x00w\x00s\x00\\\x00w\x00i\x00n\x00d"
            b"\x00o\x00w\x00s\x00 \x00e\x00r\x00r\x00o\x00r\x00 "
            b"\x00r\x00e\x00p\x00o\x00r\x00t\x00i\x00n\x00g\x00\\"
            b"\x00c\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00\x00;\x00D"
            b"\x00e\x00f\x00a\x00u\x00l\x00t\x00C\x00o\x00n\x00s"
            b"\x00e\x00n\x00t\x00\x00\x00;\x00\x01\x00\x00\x00;\x00"
            b"\x04\x00\x00\x00;\x00\x02\x00\x00\x00]\x00"
        )
        policy_regpath = (
            b"\x00s\x00o\x00f\x00t\x00w\x00a\x00r\x00e\x00\\\x00p"
            b"\x00o\x00l\x00i\x00c\x00i\x00e\x00s\x00\\\x00m\x00i"
            b"\x00c\x00r\x00o\x00s\x00o\x00f\x00t\x00\\\x00w\x00i"
            b"\x00n\x00d\x00o\x00w\x00s\x00\\\x00w\x00i\x00n\x00d"
            b"\x00o\x00w\x00s\x00 \x00e\x00r\x00r\x00o\x00r\x00 "
            b"\x00r\x00e\x00p\x00o\x00r\x00t\x00i\x00n\x00g\x00\\"
            b"\x00c\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00"
        )
        policy_regkey = (
            b"\x00D\x00e\x00f\x00a\x00u\x00l\x00t\x00C\x00o\x00n"
            b"\x00s\x00e\x00n\x00t\x00\x00"
        )
        test = win_lgpo._regexSearchKeyValueCombo(
            policy_data=policy_data,
            policy_regpath=policy_regpath,
            policy_regkey=policy_regkey,
        )
        self.assertEqual(test, policy_data)

    def test__regexSearchKeyValueCombo_not_configured(self):
        """
        Make sure
        """
        policy_data = b""
        policy_regpath = (
            b"\x00s\x00o\x00f\x00t\x00w\x00a\x00r\x00e\x00\\\x00p"
            b"\x00o\x00l\x00i\x00c\x00i\x00e\x00s\x00\\\x00m\x00i"
            b"\x00c\x00r\x00o\x00s\x00o\x00f\x00t\x00\\\x00w\x00i"
            b"\x00n\x00d\x00o\x00w\x00s\x00\\\x00w\x00i\x00n\x00d"
            b"\x00o\x00w\x00s\x00 \x00e\x00r\x00r\x00o\x00r\x00 "
            b"\x00r\x00e\x00p\x00o\x00r\x00t\x00i\x00n\x00g\x00\\"
            b"\x00c\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00"
        )
        policy_regkey = (
            b"\x00D\x00e\x00f\x00a\x00u\x00l\x00t\x00C\x00o\x00n"
            b"\x00s\x00e\x00n\x00t\x00\x00"
        )
        test = win_lgpo._regexSearchKeyValueCombo(
            policy_data=policy_data,
            policy_regpath=policy_regpath,
            policy_regkey=policy_regkey,
        )
        self.assertIsNone(test)

    def test__regexSearchKeyValueCombo_disabled(self):
        """
        Make sure
        """
        policy_data = (
            b"[\x00s\x00o\x00f\x00t\x00w\x00a\x00r\x00e\x00\\\x00p"
            b"\x00o\x00l\x00i\x00c\x00i\x00e\x00s\x00\\\x00m\x00i"
            b"\x00c\x00r\x00o\x00s\x00o\x00f\x00t\x00\\\x00w\x00i"
            b"\x00n\x00d\x00o\x00w\x00s\x00\\\x00w\x00i\x00n\x00d"
            b"\x00o\x00w\x00s\x00 \x00e\x00r\x00r\x00o\x00r\x00 "
            b"\x00r\x00e\x00p\x00o\x00r\x00t\x00i\x00n\x00g\x00\\"
            b"\x00c\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00\x00;\x00*"
            b"\x00*\x00d\x00e\x00l\x00.\x00D\x00e\x00f\x00a\x00u"
            b"\x00l\x00t\x00C\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00"
            b"\x00;\x00\x01\x00\x00\x00;\x00\x04\x00\x00\x00;\x00 "
            b"\x00\x00\x00]\x00"
        )
        policy_regpath = (
            b"\x00s\x00o\x00f\x00t\x00w\x00a\x00r\x00e\x00\\\x00p"
            b"\x00o\x00l\x00i\x00c\x00i\x00e\x00s\x00\\\x00m\x00i"
            b"\x00c\x00r\x00o\x00s\x00o\x00f\x00t\x00\\\x00w\x00i"
            b"\x00n\x00d\x00o\x00w\x00s\x00\\\x00w\x00i\x00n\x00d"
            b"\x00o\x00w\x00s\x00 \x00e\x00r\x00r\x00o\x00r\x00 "
            b"\x00r\x00e\x00p\x00o\x00r\x00t\x00i\x00n\x00g\x00\\"
            b"\x00c\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00"
        )
        policy_regkey = (
            b"\x00D\x00e\x00f\x00a\x00u\x00l\x00t\x00C\x00o\x00n"
            b"\x00s\x00e\x00n\x00t\x00\x00"
        )
        test = win_lgpo._regexSearchKeyValueCombo(
            policy_data=policy_data,
            policy_regpath=policy_regpath,
            policy_regkey=policy_regkey,
        )
        self.assertEqual(test, policy_data)

    def test__encode_string(self):
        """
        ``_encode_string`` should return a null terminated ``utf-16-le`` encoded
        string when a string value is passed
        """
        encoded_value = b"".join(
            ["Salt is awesome".encode("utf-16-le"), self.encoded_null]
        )
        value = win_lgpo._encode_string("Salt is awesome")
        self.assertEqual(value, encoded_value)

    def test__encode_string_empty_string(self):
        """
        ``_encode_string`` should return an encoded null when an empty string
        value is passed
        """
        value = win_lgpo._encode_string("")
        self.assertEqual(value, self.encoded_null)

    def test__encode_string_error(self):
        """
        ``_encode_string`` should raise an error if a non-string value is passed
        """
        self.assertRaises(TypeError, win_lgpo._encode_string, [1])
        test_list = ["item1", "item2"]
        self.assertRaises(TypeError, win_lgpo._encode_string, [test_list])
        test_dict = {"key1": "value1", "key2": "value2"}
        self.assertRaises(TypeError, win_lgpo._encode_string, [test_dict])

    def test__encode_string_none(self):
        """
        ``_encode_string`` should return an encoded null when ``None`` is passed
        """
        value = win_lgpo._encode_string(None)
        self.assertEqual(value, self.encoded_null)

    def test__multi_string_get_transform_list(self):
        """
        ``_multi_string_get_transform`` should return the list when a list is
        passed
        """
        test_value = ["Spongebob", "Squarepants"]
        value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
        self.assertEqual(value, test_value)

    def test__multi_string_get_transform_none(self):
        """
        ``_multi_string_get_transform`` should return "Not Defined" when
        ``None`` is passed
        """
        test_value = None
        value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
        self.assertEqual(value, "Not Defined")

    def test__multi_string_get_transform_invalid(self):
        """
        ``_multi_string_get_transform`` should return "Not Defined" when
        ``None`` is passed
        """
        test_value = "Some String"
        value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
        self.assertEqual(value, "Invalid Value")

    def test__multi_string_put_transform_list(self):
        """
        ``_multi_string_put_transform`` should return the list when a list is
        passed
        """
        test_value = ["Spongebob", "Squarepants"]
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, test_value)

    def test__multi_string_put_transform_none(self):
        """
        ``_multi_string_put_transform`` should return ``None`` when
        "Not Defined" is passed
        """
        test_value = "Not Defined"
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, None)

    def test__multi_string_put_transform_list_from_string(self):
        """
        ``_multi_string_put_transform`` should return a list when a comma
        delimited string is passed
        """
        test_value = "Spongebob,Squarepants"
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, ["Spongebob", "Squarepants"])

    def test__multi_string_put_transform_invalid(self):
        """
        ``_multi_string_put_transform`` should return "Invalid" value if neither
        string nor list is passed
        """
        test_value = None
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, "Invalid Value")


@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinLGPOGetPolicyADMXTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test functions related to the ``get_policy`` function using policy templates
    (admx/adml)
    """

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        cls.utils = salt.loader.utils(cls.opts)
        cls.modules = salt.loader.minion_mods(cls.opts, utils=cls.utils)

    @classmethod
    def tearDownClass(cls):
        cls.opts = cls.utils = cls.modules = None

    def setup_loader_modules(self):
        return {
            win_lgpo: {
                "__opts__": copy.deepcopy(self.opts),
                "__salt__": self.modules,
                "__utils__": self.utils,
            }
        }

    def test_get_policy_name(self):
        result = win_lgpo.get_policy(
            policy_name="Allow Telemetry",
            policy_class="machine",
            return_value_only=True,
            return_full_policy_names=True,
            hierarchical_return=False,
        )
        expected = "Not Configured"
        self.assertEqual(result, expected)

    def test_get_policy_id(self):
        result = win_lgpo.get_policy(
            policy_name="AllowTelemetry",
            policy_class="machine",
            return_value_only=True,
            return_full_policy_names=True,
            hierarchical_return=False,
        )
        expected = "Not Configured"
        self.assertEqual(result, expected)

    def test_get_policy_name_full_return_full_names(self):
        result = win_lgpo.get_policy(
            policy_name="Allow Telemetry",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=True,
            hierarchical_return=False,
        )
        expected = {
            "Windows Components\\Data Collection and Preview Builds\\Allow Telemetry": (
                "Not Configured"
            )
        }
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_full_names(self):
        result = win_lgpo.get_policy(
            policy_name="AllowTelemetry",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=True,
            hierarchical_return=False,
        )
        expected = {
            "Windows Components\\Data Collection and Preview Builds\\Allow Telemetry": (
                "Not Configured"
            )
        }
        self.assertDictEqual(result, expected)

    def test_get_policy_name_full_return_ids(self):
        result = win_lgpo.get_policy(
            policy_name="Allow Telemetry",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=False,
            hierarchical_return=False,
        )
        expected = {"AllowTelemetry": "Not Configured"}
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_ids(self):
        result = win_lgpo.get_policy(
            policy_name="AllowTelemetry",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=False,
            hierarchical_return=False,
        )
        expected = {"AllowTelemetry": "Not Configured"}
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_ids_hierarchical(self):
        result = win_lgpo.get_policy(
            policy_name="AllowTelemetry",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=False,
            hierarchical_return=True,
        )
        expected = {
            "Computer Configuration": {
                "Administrative Templates": {
                    "WindowsComponents": {
                        "DataCollectionAndPreviewBuilds": {
                            "AllowTelemetry": "Not Configured"
                        }
                    }
                }
            }
        }
        self.assertDictEqual(result, expected)

    def test_get_policy_name_return_full_names_hierarchical(self):
        result = win_lgpo.get_policy(
            policy_name="Allow Telemetry",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=True,
            hierarchical_return=True,
        )
        expected = {
            "Computer Configuration": {
                "Administrative Templates": {
                    "Windows Components": {
                        "Data Collection and Preview Builds": {
                            "Allow Telemetry": "Not Configured"
                        }
                    }
                }
            }
        }
        self.assertDictEqual(result, expected)

    @pytest.mark.destructive_test
    def test__load_policy_definitions(self):
        """
        Test that unexpected files in the PolicyDefinitions directory won't
        cause the _load_policy_definitions function to explode
        https://gitlab.com/saltstack/enterprise/lock/issues/3826
        """
        # The PolicyDefinitions directory should only contain ADMX files. We
        # want to make sure the `_load_policy_definitions` function skips non
        # ADMX files in this directory.
        # Create a bogus ADML file in PolicyDefinitions directory
        bogus_fle = os.path.join("c:\\Windows\\PolicyDefinitions", "_bogus.adml")
        cache_dir = os.path.join(win_lgpo.__opts__["cachedir"], "lgpo", "policy_defs")
        try:
            with salt.utils.files.fopen(bogus_fle, "w+") as fh:
                fh.write("<junk></junk>")
            # This function doesn't return anything (None), it just loads
            # the XPath structures into __context__. We're just making sure it
            # doesn't stack trace here
            self.assertIsNone(win_lgpo._load_policy_definitions())
        finally:
            # Remove source file
            os.remove(bogus_fle)
            # Remove cached file
            search_string = "{}\\_bogus*.adml".format(cache_dir)
            for file_name in glob.glob(search_string):
                os.remove(file_name)


@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinLGPOGetPolicyFromPolicyInfoTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test functions related to the ``get_policy`` function using _policy_info
    object
    """

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        cls.utils = salt.loader.utils(cls.opts)
        cls.modules = salt.loader.minion_mods(cls.opts, utils=cls.utils)

    @classmethod
    def tearDownClass(cls):
        cls.opts = cls.utils = cls.modules = None

    def setup_loader_modules(self):
        return {
            win_lgpo: {
                "__opts__": copy.deepcopy(self.opts),
                "__salt__": self.modules,
                "__utils__": self.utils,
            }
        }

    def test_get_policy_name(self):
        result = win_lgpo.get_policy(
            policy_name="Network firewall: Public: Settings: Display a notification",
            policy_class="machine",
            return_value_only=True,
            return_full_policy_names=True,
            hierarchical_return=False,
        )
        expected = "Not configured"
        self.assertEqual(result, expected)

    def test_get_policy_id(self):
        result = win_lgpo.get_policy(
            policy_name="WfwPublicSettingsNotification",
            policy_class="machine",
            return_value_only=True,
            return_full_policy_names=True,
            hierarchical_return=False,
        )
        expected = "Not configured"
        self.assertEqual(result, expected)

    def test_get_policy_name_full_return(self):
        result = win_lgpo.get_policy(
            policy_name="Network firewall: Public: Settings: Display a notification",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=True,
            hierarchical_return=False,
        )
        expected = {
            "Network firewall: Public: Settings: Display a notification": (
                "Not configured"
            )
        }
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return(self):
        result = win_lgpo.get_policy(
            policy_name="WfwPublicSettingsNotification",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=True,
            hierarchical_return=False,
        )
        expected = {
            "Network firewall: Public: Settings: Display a notification": (
                "Not configured"
            )
        }
        self.assertDictEqual(result, expected)

    def test_get_policy_name_full_return_ids(self):
        result = win_lgpo.get_policy(
            policy_name="Network firewall: Public: Settings: Display a notification",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=False,
            hierarchical_return=False,
        )
        expected = {
            "Network firewall: Public: Settings: Display a notification": (
                "Not configured"
            )
        }
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_ids(self):
        result = win_lgpo.get_policy(
            policy_name="WfwPublicSettingsNotification",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=False,
            hierarchical_return=False,
        )
        expected = {"WfwPublicSettingsNotification": "Not configured"}
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_ids_hierarchical(self):
        result = win_lgpo.get_policy(
            policy_name="WfwPublicSettingsNotification",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=False,
            hierarchical_return=True,
        )
        expected = {
            "Computer Configuration": {
                "Windows Settings": {
                    "Security Settings": {
                        "Windows Firewall with Advanced Security": {
                            "Windows Firewall with Advanced Security - Local Group Policy Object": {
                                "WfwPublicSettingsNotification": "Not configured"
                            }
                        }
                    }
                }
            }
        }
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_full_names_hierarchical(self):
        result = win_lgpo.get_policy(
            policy_name="WfwPublicSettingsNotification",
            policy_class="machine",
            return_value_only=False,
            return_full_policy_names=True,
            hierarchical_return=True,
        )
        expected = {
            "Computer Configuration": {
                "Windows Settings": {
                    "Security Settings": {
                        "Windows Firewall with Advanced Security": {
                            "Windows Firewall with Advanced Security - Local Group Policy Object": {
                                "Network firewall: Public: Settings: Display a notification": (
                                    "Not configured"
                                )
                            }
                        }
                    }
                }
            }
        }
        self.assertDictEqual(result, expected)


@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinLGPOPolicyInfoMechanismsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test getting local group policy settings defined in the _policy_info object
    Go through each mechanism
    """

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        cls.utils = salt.loader.utils(cls.opts)
        cls.modules = salt.loader.minion_mods(cls.opts, utils=cls.utils)
        cls.policy_data = salt.modules.win_lgpo._policy_info()

    @classmethod
    def tearDownClass(cls):
        cls.opts = cls.utils = cls.modules = cls.policy_data = None

    def setup_loader_modules(self):
        return {
            win_lgpo: {
                "__opts__": copy.deepcopy(self.opts),
                "__salt__": self.modules,
                "__utils__": self.utils,
            }
        }

    def _test_policy(self, policy_name):
        """
        Helper function to get current setting
        """
        policy_definition = self.policy_data.policies["Machine"]["policies"][
            policy_name
        ]
        return salt.modules.win_lgpo._get_policy_info_setting(policy_definition)

    def test_registry_mechanism(self):
        """
        Test getting policy value using the Registry mechanism
        """
        policy_name = "RemoteRegistryExactPaths"
        result = self._test_policy(policy_name=policy_name)
        expected = [
            "System\\CurrentControlSet\\Control\\ProductOptions",
            "System\\CurrentControlSet\\Control\\Server Applications",
            "Software\\Microsoft\\Windows NT\\CurrentVersion",
        ]
        self.assertListEqual(result, expected)

    def test_secedit_mechanism(self):
        """
        Test getting policy value using the Secedit mechanism
        """
        policy_name = "LSAAnonymousNameLookup"
        result = self._test_policy(policy_name=policy_name)
        expected = "Disabled"
        self.assertEqual(result, expected)

    def test_netsh_mechanism(self):
        """
        Test getting the policy value using the NetSH mechanism
        """
        policy_name = "WfwDomainState"
        all_settings = {
            "State": "NotConfigured",
            "Inbound": "NotConfigured",
            "Outbound": "NotConfigured",
            "LocalFirewallRules": "NotConfigured",
            "LocalConSecRules": "NotConfigured",
            "InboundUserNotification": "NotConfigured",
            "RemoteManagement": "NotConfigured",
            "UnicastResponseToMulticast": "NotConfigured",
            "LogAllowedConnections": "NotConfigured",
            "LogDroppedConnections": "NotConfigured",
            "FileName": "NotConfigured",
            "MaxFileSize": "NotConfigured",
        }
        with patch(
            "salt.utils.win_lgpo_netsh.get_all_settings", return_value=all_settings
        ):
            result = self._test_policy(policy_name=policy_name)
        expected = "Not configured"
        self.assertEqual(result, expected)

    @pytest.mark.destructive_test
    def test_adv_audit_mechanism(self):
        """
        Test getting the policy value using the AdvAudit mechanism
        """
        system_root = os.environ.get("SystemRoot", "C:\\Windows")
        f_audit = os.path.join(system_root, "security", "audit", "audit.csv")
        f_audit_gpo = os.path.join(
            system_root,
            "System32",
            "GroupPolicy",
            "Machine",
            "Microsoft",
            "Windows NT",
            "Audit",
            "audit.csv",
        )
        if os.path.exists(f_audit):
            os.remove(f_audit)
        if os.path.exists(f_audit_gpo):
            os.remove(f_audit_gpo)
        policy_name = "AuditCredentialValidation"
        result = self._test_policy(policy_name=policy_name)
        expected = "Not Configured"
        self.assertEqual(result, expected)

    def test_net_user_modal_mechanism(self):
        """
        Test getting the policy value using the NetUserModal mechanism
        """
        policy_name = "PasswordHistory"
        result = self._test_policy(policy_name=policy_name)
        expected = 0
        self.assertEqual(result, expected)

    def test_lsa_rights_mechanism(self):
        """
        Test getting the policy value using the LsaRights mechanism
        """
        policy_name = "SeTrustedCredManAccessPrivilege"
        result = self._test_policy(policy_name=policy_name)
        expected = []
        self.assertEqual(result, expected)

    def test_script_ini_mechanism(self):
        """
        Test getting the policy value using the ScriptIni value
        """
        policy_name = "StartupScripts"
        result = self._test_policy(policy_name=policy_name)
        expected = None
        self.assertEqual(result, expected)


@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
@pytest.mark.destructive_test
class WinLGPOGetPointAndPrintNCTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test variations of the Point and Print Restrictions policy when Not
    Configured (NC)
    """

    not_configured = False

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        cls.utils = salt.loader.utils(cls.opts)
        cls.modules = salt.loader.minion_mods(cls.opts, utils=cls.utils)

    @classmethod
    def tearDownClass(cls):
        cls.opts = cls.utils = cls.modules = None

    def setup_loader_modules(self):
        return {
            win_lgpo: {
                "__opts__": copy.deepcopy(self.opts),
                "__salt__": self.modules,
                "__utils__": self.utils,
            }
        }

    def setUp(self):
        if not self.not_configured:
            computer_policy = {"Point and Print Restrictions": "Not Configured"}
            win_lgpo.set_(computer_policy=computer_policy)
            self.not_configured = True

    def _get_policy_adm_setting(
        self, policy_name, policy_class, return_full_policy_names, hierarchical_return
    ):
        """
        Helper function to get current setting
        """
        # Get the policy
        success, policy_obj, _, _ = salt.modules.win_lgpo._lookup_admin_template(
            policy_name=policy_name, policy_class=policy_class, adml_language="en-US"
        )
        if success:
            return salt.modules.win_lgpo._get_policy_adm_setting(
                admx_policy=policy_obj,
                policy_class=policy_class,
                adml_language="en-US",
                return_full_policy_names=return_full_policy_names,
                hierarchical_return=hierarchical_return,
            )
        return "Policy Not Found"

    def test_point_and_print_not_configured(self):
        result = self._get_policy_adm_setting(
            policy_name="Point and Print Restrictions",
            policy_class="Machine",
            return_full_policy_names=False,
            hierarchical_return=False,
        )
        expected = {"PointAndPrint_Restrictions_Win7": "Not Configured"}
        self.assertDictEqual(result, expected)

    def test_point_and_print_not_configured_hierarchical(self):
        result = self._get_policy_adm_setting(
            policy_name="Point and Print Restrictions",
            policy_class="Machine",
            return_full_policy_names=False,
            hierarchical_return=True,
        )
        expected = {
            "Computer Configuration": {
                "Administrative Templates": {
                    "Printers": {"PointAndPrint_Restrictions_Win7": "Not Configured"}
                }
            }
        }
        self.assertDictEqual(result, expected)

    def test_point_and_print_not_configured_full_names(self):
        result = self._get_policy_adm_setting(
            policy_name="Point and Print Restrictions",
            policy_class="Machine",
            return_full_policy_names=True,
            hierarchical_return=False,
        )
        expected = {"Printers\\Point and Print Restrictions": "Not Configured"}
        self.assertDictEqual(result, expected)

    def test_point_and_print_not_configured_full_names_hierarchical(self):
        result = self._get_policy_adm_setting(
            policy_name="Point and Print Restrictions",
            policy_class="Machine",
            return_full_policy_names=True,
            hierarchical_return=True,
        )
        expected = {
            "Computer Configuration": {
                "Administrative Templates": {
                    "Printers": {"Point and Print Restrictions": "Not Configured"}
                }
            }
        }
        self.assertDictEqual(result, expected)


@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
@pytest.mark.destructive_test
class WinLGPOGetPointAndPrintENTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test variations of the Point and Print Restrictions policy when Enabled (EN)
    """

    configured = False

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        cls.utils = salt.loader.utils(cls.opts)
        cls.modules = salt.loader.minion_mods(cls.opts, utils=cls.utils)

    @classmethod
    def tearDownClass(cls):
        cls.opts = cls.utils = cls.modules = None

    def setup_loader_modules(self):
        return {
            win_lgpo: {
                "__opts__": copy.deepcopy(self.opts),
                "__salt__": self.modules,
                "__utils__": self.utils,
            }
        }

    def setUp(self):
        if not self.configured:
            computer_policy = {
                "Point and Print Restrictions": {
                    "Users can only point and print to these servers": True,
                    "Enter fully qualified server names separated by semicolons": (
                        "fakeserver1;fakeserver2"
                    ),
                    "Users can only point and print to machines in their forest": True,
                    "When installing drivers for a new connection": (
                        "Show warning and elevation prompt"
                    ),
                    "When updating drivers for an existing connection": (
                        "Show warning only"
                    ),
                },
            }
            win_lgpo.set_(computer_policy=computer_policy)
            self.configured = True

    def _get_policy_adm_setting(
        self, policy_name, policy_class, return_full_policy_names, hierarchical_return
    ):
        """
        Helper function to get current setting
        """
        # Get the policy
        success, policy_obj, _, _ = salt.modules.win_lgpo._lookup_admin_template(
            policy_name=policy_name, policy_class=policy_class, adml_language="en-US"
        )
        if success:
            results = salt.modules.win_lgpo._get_policy_adm_setting(
                admx_policy=policy_obj,
                policy_class=policy_class,
                adml_language="en-US",
                return_full_policy_names=return_full_policy_names,
                hierarchical_return=hierarchical_return,
            )
            return results
        return "Policy Not Found"

    @pytest.mark.slow_test
    def test_point_and_print_enabled(self):
        result = self._get_policy_adm_setting(
            policy_name="Point and Print Restrictions",
            policy_class="Machine",
            return_full_policy_names=False,
            hierarchical_return=False,
        )
        expected = {
            "PointAndPrint_Restrictions_Win7": {
                "PointAndPrint_NoWarningNoElevationOnInstall_Enum": (
                    "Show warning and elevation prompt"
                ),
                "PointAndPrint_NoWarningNoElevationOnUpdate_Enum": "Show warning only",
                "PointAndPrint_TrustedForest_Chk": True,
                "PointAndPrint_TrustedServers_Chk": True,
                "PointAndPrint_TrustedServers_Edit": "fakeserver1;fakeserver2",
            }
        }
        self.assertDictEqual(result, expected)

    def test_point_and_print_enabled_hierarchical(self):
        result = self._get_policy_adm_setting(
            policy_name="Point and Print Restrictions",
            policy_class="Machine",
            return_full_policy_names=False,
            hierarchical_return=True,
        )
        expected = {
            "Computer Configuration": {
                "Administrative Templates": {
                    "Printers": {
                        "PointAndPrint_Restrictions_Win7": {
                            "PointAndPrint_NoWarningNoElevationOnInstall_Enum": (
                                "Show warning and elevation prompt"
                            ),
                            "PointAndPrint_NoWarningNoElevationOnUpdate_Enum": (
                                "Show warning only"
                            ),
                            "PointAndPrint_TrustedForest_Chk": True,
                            "PointAndPrint_TrustedServers_Chk": True,
                            "PointAndPrint_TrustedServers_Edit": (
                                "fakeserver1;fakeserver2"
                            ),
                        }
                    }
                }
            }
        }
        self.assertDictEqual(result, expected)

    def test_point_and_print_enabled_full_names(self):
        result = self._get_policy_adm_setting(
            policy_name="Point and Print Restrictions",
            policy_class="Machine",
            return_full_policy_names=True,
            hierarchical_return=False,
        )
        expected = {
            "Printers\\Point and Print Restrictions": {
                "Enter fully qualified server names separated by semicolons": (
                    "fakeserver1;fakeserver2"
                ),
                "When installing drivers for a new connection": (
                    "Show warning and elevation prompt"
                ),
                "Users can only point and print to machines in their forest": True,
                "Users can only point and print to these servers": True,
                "When updating drivers for an existing connection": "Show warning only",
            }
        }
        self.assertDictEqual(result, expected)

    @pytest.mark.slow_test
    def test_point_and_print_enabled_full_names_hierarchical(self):
        result = self._get_policy_adm_setting(
            policy_name="Point and Print Restrictions",
            policy_class="Machine",
            return_full_policy_names=True,
            hierarchical_return=True,
        )
        expected = {
            "Computer Configuration": {
                "Administrative Templates": {
                    "Printers": {
                        "Point and Print Restrictions": {
                            "Enter fully qualified server names separated by semicolons": (
                                "fakeserver1;fakeserver2"
                            ),
                            "When installing drivers for a new connection": (
                                "Show warning and elevation prompt"
                            ),
                            "Users can only point and print to machines in their forest": True,
                            "Users can only point and print to these servers": True,
                            "When updating drivers for an existing connection": (
                                "Show warning only"
                            ),
                        }
                    }
                }
            }
        }
        self.assertDictEqual(result, expected)


@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinLGPOGetPolicyFromPolicyResources(TestCase, LoaderModuleMockMixin):
    """
    Test functions related to policy info gathered from ADMX/ADML files
    """

    adml_data = None

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        cls.utils = salt.loader.utils(cls.opts)
        cls.modules = salt.loader.minion_mods(cls.opts, utils=cls.utils)

    @classmethod
    def tearDownClass(cls):
        cls.opts = cls.utils = cls.modules = None

    def setup_loader_modules(self):
        return {
            win_lgpo: {
                "__opts__": copy.deepcopy(self.opts),
                "__salt__": self.modules,
                "__utils__": self.utils,
            }
        }

    def setUp(self):
        if self.adml_data is None:
            self.adml_data = win_lgpo._get_policy_resources(language="en-US")

    def test__getAdmlPresentationRefId(self):
        ref_id = "LetAppsAccessAccountInfo_Enum"
        expected = "Default for all apps"
        result = win_lgpo._getAdmlPresentationRefId(self.adml_data, ref_id)
        self.assertEqual(result, expected)

    def test__getAdmlPresentationRefId_result_text_is_none(self):
        ref_id = "LetAppsAccessAccountInfo_UserInControlOfTheseApps_List"
        expected = (
            "Put user in control of these specific apps (use Package Family Names)"
        )
        result = win_lgpo._getAdmlPresentationRefId(self.adml_data, ref_id)
        self.assertEqual(result, expected)
