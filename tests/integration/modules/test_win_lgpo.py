import logging
import os
import re

import pytest
import salt.utils.files
import salt.utils.platform
import salt.utils.win_reg as reg
from tests.support.case import ModuleCase
from tests.support.helpers import random_string
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@skipIf(not salt.utils.platform.is_windows(), "windows test only")
class WinLgpoTest(ModuleCase):
    """
    Tests for salt.modules.win_lgpo
    """

    osrelease = None

    def _testRegistryPolicy(
        self,
        policy_name,
        policy_config,
        registry_value_hive,
        registry_value_path,
        registry_value_vname,
        expected_value_data,
        expected_value_type=None,
        expect_value_exists=True,
    ):
        """
        Takes a registry based policy name and config and validates that the
        expected registry value exists and has the correct data

        policy_name
            name of the registry based policy to configure
        policy_config
            the configuration of the policy
        registry_value_hive
            the registry hive that the policy registry path is in
        registry_value_path
            the registry value path that the policy updates
        registry_value_vname
            the registry value name
        expected_value_data
            the expected data that the value will contain
        expected_value_type
            the registry value type (i.e. REG_SZ, REG_DWORD, etc)
        expect_value_exists
            define if it expected for a registry value to exist
            some policies when set to 'Not Defined' delete the registry value
        """
        ret = self.run_function(
            "lgpo.set_computer_policy", (policy_name, policy_config)
        )
        self.assertTrue(ret)
        val = reg.read_value(
            registry_value_hive, registry_value_path, registry_value_vname
        )
        if expect_value_exists:
            self.assertTrue(
                val["success"],
                msg="Failed to obtain the registry data for policy {}".format(
                    policy_name
                ),
            )
        self.assertEqual(
            val["vdata"],
            expected_value_data,
            "The registry value data {} does not match the expected value {} for"
            " policy {}".format(val["vdata"], expected_value_data, policy_name),
        )
        if expected_value_type:
            self.assertEqual(
                val["vtype"],
                expected_value_type,
                "The registry value type {} does not match the expected type {} for"
                " policy {}".format(val["vtype"], expected_value_type, policy_name),
            )

    def _testSeceditPolicy(
        self,
        policy_name,
        policy_config,
        expected_regexes,
        cumulative_rights_assignments=True,
    ):
        """
        Takes a secedit policy name and config and validates that the expected
        output is returned from secedit

        policy_name
            name of the secedit policy to configure
        policy_config
            the configuration of the policy
        expected_regexes
            the expected regexes to be found in the secedit output file
        """
        ret = self.run_function(
            "lgpo.set_computer_policy",
            (policy_name, policy_config),
            cumulative_rights_assignments=cumulative_rights_assignments,
        )
        self.assertTrue(ret)
        secedit_output_file = os.path.join(
            RUNTIME_VARS.TMP, random_string("secedit-output-")
        )
        secedit_output = self.run_function(
            "cmd.run", (), cmd="secedit /export /cfg {}".format(secedit_output_file)
        )
        secedit_file_content = None
        if secedit_output:
            with salt.utils.files.fopen(
                secedit_output_file, encoding="utf-16"
            ) as _reader:
                secedit_file_content = _reader.read()
        for expected_regex in expected_regexes:
            match = re.search(
                expected_regex, secedit_file_content, re.IGNORECASE | re.MULTILINE
            )
            self.assertIsNotNone(
                match,
                'Failed validating policy "{}" configuration, regex "{}" not found in'
                " secedit output".format(policy_name, expected_regex),
            )

    def _testAdmxPolicy(
        self,
        policy_name,
        policy_config,
        expected_regexes,
        assert_true=True,
        policy_class="Machine",
    ):
        """
        Takes a ADMX policy name and config and validates that the expected
        output is returned from lgpo looking at the Registry.pol file

        policy_name
            name of the ADMX policy to configure
        policy_config
            the configuration of the policy
        expected_regexes
            the expected regexes to be found in the lgpo parse output
        assert_true
            set to false if expecting the module run to fail
        policy_class
            the policy class this policy belongs to, either Machine or User
        """
        lgpo_function = "set_computer_policy"
        lgpo_class = "/m"
        lgpo_folder = "Machine"
        lgpo_top_level = "Computer Configuration"
        if policy_class.lower() == "user":
            lgpo_function = "set_user_policy"
            lgpo_class = "/u"
            lgpo_folder = "User"
            lgpo_top_level = "User Configuration"

        ret = self.run_function(
            "lgpo.{}".format(lgpo_function), (policy_name, policy_config)
        )
        log.debug("lgpo set_computer_policy ret == %s", ret)
        cmd = [
            "lgpo.exe",
            "/parse",
            lgpo_class,
            r"c:\Windows\System32\GroupPolicy\{}\Registry.pol".format(lgpo_folder),
        ]
        if assert_true:
            self.assertTrue(ret)
            lgpo_output = self.run_function("cmd.run", (), cmd=" ".join(cmd))
            # validate that the lgpo output doesn't say the format is invalid
            self.assertIsNone(
                re.search(r"Invalid file format\.", lgpo_output, re.IGNORECASE),
                msg="Failed validating Registry.pol file format",
            )
            # validate that the regexes we expect are in the output
            for expected_regex in expected_regexes:
                match = re.search(expected_regex, lgpo_output, re.IGNORECASE)
                self.assertIsNotNone(
                    match,
                    msg=(
                        'Failed validating policy "{}" configuration, regex '
                        '"{}" not found in lgpo output:\n{}'
                        "".format(policy_name, expected_regex, lgpo_output)
                    ),
                )
            # validate the lgpo also sees the right setting
            this_policy_info = self.run_function(
                "lgpo.get_policy_info",
                (),
                policy_name=policy_name,
                policy_class=policy_class,
            )
            ret = self.run_function(
                "lgpo.get", (), policy_class=policy_class, return_not_configured=True
            )
            self.assertTrue(
                lgpo_top_level in ret, msg="lgpo did not return the expected entries"
            )
            found_policy = False
            output_policy_name = None
            if "policy_aliases" in this_policy_info:
                for policy_alias in this_policy_info["policy_aliases"]:
                    if policy_alias in ret[lgpo_top_level]:
                        found_policy = True
                        output_policy_name = policy_alias
                        break
            else:
                found_policy = policy_name in ret[lgpo_top_level]
            self.assertTrue(
                found_policy, msg="The configured policy is not in the lgpo.get output"
            )
            if isinstance(policy_config, list):
                for this_item in policy_config:
                    self.assertTrue(
                        this_item in ret[lgpo_top_level][output_policy_name],
                        msg="Item {} not found in policy configuration".format(
                            this_item
                        ),
                    )
            elif isinstance(policy_config, dict):
                for this_item, this_val in policy_config.items():
                    item_correct = False
                    actual_val = None
                    if (
                        "policy_elements" in this_policy_info
                        and this_policy_info["policy_elements"]
                    ):
                        for policy_element in this_policy_info["policy_elements"]:
                            if item_correct:
                                break
                            if (
                                "element_aliases" in policy_element
                                and policy_element["element_aliases"]
                            ):
                                if this_item in policy_element["element_aliases"]:
                                    for element_alias in policy_element[
                                        "element_aliases"
                                    ]:
                                        if (
                                            element_alias
                                            in ret[lgpo_top_level][output_policy_name]
                                        ):
                                            actual_val = ret[lgpo_top_level][
                                                output_policy_name
                                            ][element_alias]
                                            if (
                                                ret[lgpo_top_level][output_policy_name][
                                                    element_alias
                                                ]
                                                == this_val
                                            ):
                                                item_correct = True
                                                break
                    self.assertTrue(
                        item_correct,
                        msg=(
                            'Item "{}" does not have the expected value of "{}"{}'.format(
                                this_item,
                                this_val,
                                ' value found: "{}"'.format(actual_val)
                                if actual_val
                                else "",
                            )
                        ),
                    )
            else:
                self.assertEqual(
                    ret[lgpo_top_level][output_policy_name],
                    policy_config,
                    msg="lgpo did not return the expected value for the policy",
                )
        else:
            # expecting it to fail
            self.assertNotEqual(ret, True)

    def runTest(self):
        """
        runTest method
        """

    @classmethod
    def setUpClass(cls):
        """
        class setup function, only runs once

        downloads and extracts the lgpo.exe tool into c:/windows/system32
        for use in validating the registry.pol files

        gets osrelease grain for tests that are only applicable to certain
        windows versions
        """
        osrelease_grains = cls().run_function("grains.item", ["osrelease"])
        if "osrelease" in osrelease_grains:
            cls.osrelease = osrelease_grains["osrelease"]
        else:
            log.debug("Unable to get osrelease grain")
        if not os.path.exists(r"c:\windows\system32\lgpo.exe"):
            log.debug("lgpo.exe does not exist, attempting to download/extract")
            ret = cls().run_function(
                "state.single",
                ("archive.extracted", r"c:\windows\system32"),
                source="https://download.microsoft.com/download/8/5/C/85C25433-A1B0-4FFA-9429-7E023E7DA8D8/LGPO.zip",
                archive_format="zip",
                source_hash="sha256=6ffb6416366652993c992280e29faea3507b5b5aa661c33ba1af31f48acea9c4",
                enforce_toplevel=False,
            )
            log.debug("ret from archive.unzip == %s", ret)

    @pytest.mark.destructive_test
    def test_set_user_policy_point_and_print_restrictions(self):
        """
        Test setting/unsetting/changing the PointAndPrint_Restrictions user policy
        """
        # Disable Point and Print Restrictions
        self._testAdmxPolicy(
            r"Control Panel\Printers\Point and Print Restrictions",
            "Disabled",
            [
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*Restricted[\s]*DWORD:0",
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*TrustedServers[\s]*DELETE",
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*ServerList[\s]*DELETE",
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*InForest[\s]*DELETE",
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*NoWarningNoElevationOnInstall[\s]*DELETE",
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*UpdatePromptSettings[\s]*DELETE",
            ],
            policy_class="User",
        )
        # Enable Point and Print Restrictions
        self._testAdmxPolicy(
            r"Point and Print Restrictions",
            {
                "Users can only point and print to these servers": True,
                "Enter fully qualified server names separated by semicolons": (
                    "fakeserver1;fakeserver2"
                ),
                "Users can only point and print to machines in their forest": True,
                "When installing drivers for a new connection": (
                    "Show warning and elevation prompt"
                ),
                "When updating drivers for an existing connection": "Show warning only",
            },
            [
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*Restricted[\s]*DWORD:1",
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*TrustedServers[\s]*DWORD:1",
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*ServerList[\s]*SZ:fakeserver1;fakeserver2",
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*InForest[\s]*DWORD:1",
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*NoWarningNoElevationOnInstall[\s]*DWORD:0",
                r"User[\s]*Software\\Policies\\Microsoft\\Windows"
                r" NT\\Printers\\PointAndPrint[\s]*UpdatePromptSettings[\s]*DWORD:1",
            ],
            policy_class="User",
        )
        # set Point and Print Restrictions to 'Not Configured'
        self._testAdmxPolicy(
            r"Control Panel\Printers\Point and Print Restrictions",
            "Not Configured",
            [
                r"; Source file: "
                r" c:\\windows\\system32\\grouppolicy\\user\\registry.pol[\s]*; PARSING"
                r" COMPLETED."
            ],
            policy_class="User",
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_NTP_Client(self):
        """
        Test setting/unsetting/changing NTP Client policies
        """
        # Disable Configure NTP Client
        self._testAdmxPolicy(
            r"System\Windows Time Service\Time Providers\Configure Windows NTP Client",
            "Disabled",
            [
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\Parameters[\s]*NtpServer[\s]*DELETE",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\Parameters[\s]*Type[\s]*DELETE",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*CrossSiteSyncFlags[\s]*DELETE",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*ResolvePeerBackoffMinutes[\s]*DELETE",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*ResolvePeerBackoffMaxTimes[\s]*DELETE",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*SpecialPollInterval[\s]*DELETE",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*EventLogFlags[\s]*DELETE",
            ],
        )
        # Enable Configure NTP Client
        self._testAdmxPolicy(
            r"System\Windows Time Service\Time Providers\Configure Windows NTP Client",
            {
                "NtpServer": "time.windows.com,0x9",
                "Type": "NT5DS",
                "CrossSiteSyncFlags": 2,
                "ResolvePeerBackoffMinutes": 15,
                "ResolvePeerBackoffMaxTimes": 7,
                "W32TIME_SpecialPollInterval": 3600,
                "W32TIME_NtpClientEventLogFlags": 0,
            },
            [
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\Parameters[\s]*NtpServer[\s]*SZ:time.windows.com,0x9",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\Parameters[\s]*Type[\s]*SZ:NT5DS",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*CrossSiteSyncFlags[\s]*DWORD:2",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*ResolvePeerBackoffMinutes[\s]*DWORD:15",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*ResolvePeerBackoffMaxTimes[\s]*DWORD:7",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*SpecialPollInterval[\s]*DWORD:3600",
                r"Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*EventLogFlags[\s]*DWORD:0",
            ],
        )
        # set Configure NTP Client to 'Not Configured'
        self._testAdmxPolicy(
            r"System\Windows Time Service\Time Providers\Configure Windows NTP Client",
            "Not Configured",
            [
                r"; Source file: "
                r" c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*;"
                r" PARSING COMPLETED."
            ],
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_RA_Unsolicit(self):
        """
        Test setting/unsetting/changing RA_Unsolicit policy
        """

        # Disable RA_Unsolicit
        log.debug("Attempting to disable RA_Unsolicit")
        self._testAdmxPolicy(
            "RA_Unsolicit",
            "Disabled",
            [
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fAllowUnsolicited[\s]*DWORD:0",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fAllowUnsolicitedFullControl[\s]*DELETE",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services\\RAUnsolicit[\s]*\*[\s]*DELETEALLVALUES",
            ],
        )
        # configure RA_Unsolicit
        log.debug("Attempting to configure RA_Unsolicit")
        self._testAdmxPolicy(
            "RA_Unsolicit",
            {
                "Permit remote control of this computer": (
                    "Allow helpers to remotely control the computer"
                ),
                "Helpers": ["administrators", "user1"],
            },
            [
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services\\RAUnsolicit[\s]*user1[\s]*SZ:user1[\s]*",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services\\RAUnsolicit[\s]*administrators[\s]*SZ:administrators[\s]*",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fAllowUnsolicited[\s]*DWORD:1",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fAllowUnsolicitedFullControl[\s]*DWORD:1",
            ],
        )
        # Not Configure RA_Unsolicit
        log.debug("Attempting to set RA_Unsolicit to Not Configured")
        self._testAdmxPolicy(
            "RA_Unsolicit",
            "Not Configured",
            [
                r"; Source file: "
                r" c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*;"
                r" PARSING COMPLETED."
            ],
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_Pol_HardenedPaths(self):
        # Disable Pol_HardenedPaths
        log.debug("Attempting to disable Pol_HardenedPaths")
        self._testAdmxPolicy(
            "Pol_HardenedPaths",
            "Disabled",
            [
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows\\NetworkProvider\\HardenedPaths[\s]*\*[\s]*DELETEALLVALUES"
            ],
        )
        # Configure Pol_HardenedPaths
        log.debug("Attempting to configure Pol_HardenedPaths")
        self._testAdmxPolicy(
            "Pol_HardenedPaths",
            {
                "Hardened UNC Paths": {
                    r"\\*\NETLOGON": (
                        "RequireMutualAuthentication=1, RequireIntegrity=1"
                    ),
                    r"\\*\SYSVOL": "RequireMutualAuthentication=1, RequireIntegrity=1",
                }
            },
            [
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows\\NetworkProvider\\HardenedPaths[\s]*\\\\\*\\NETLOGON[\s]*SZ:RequireMutualAuthentication=1,"
                r" RequireIntegrity=1[\s]*",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows\\NetworkProvider\\HardenedPaths[\s]*\\\\\*\\SYSVOL[\s]*SZ:RequireMutualAuthentication=1,"
                r" RequireIntegrity=1[\s]*",
            ],
        )
        # Not Configure Pol_HardenedPaths
        log.debug("Attempting to set Pol_HardenedPaths to Not Configured")
        self._testAdmxPolicy(
            "Pol_HardenedPaths",
            "Not Configured",
            [
                r"; Source file: "
                r" c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*;"
                r" PARSING COMPLETED."
            ],
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_WindowsUpdate(self):
        """
        Test setting/unsetting/changing WindowsUpdate policy
        """
        # Configure Automatic Updates has different options in different builds
        # and releases of Windows, so we'll get the elements and add them if
        # they are present. Newer elements will need to be added manually as
        # they are released by Microsoft
        result = self.run_function(
            "lgpo.get_policy_info",
            ["Configure Automatic Updates"],
            policy_class="machine",
        )
        the_policy = {}
        the_policy_check_enabled = [
            r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*NoAutoUpdate[\s]*DWORD:0",
        ]
        the_policy_check_disabled = [
            r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*NoAutoUpdate[\s]*DWORD:1",
        ]
        for item in result["policy_elements"]:
            if "Configure automatic updating" in item["element_aliases"]:
                the_policy.update(
                    {
                        "Configure automatic updating": (
                            "4 - Auto download and schedule the install"
                        ),
                    }
                )
                the_policy_check_enabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AUOptions[\s]*DWORD:4",
                )
                the_policy_check_disabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AUOptions[\s]*DELETE",
                )
            elif "Install during automatic maintenance" in item["element_aliases"]:
                the_policy.update({"Install during automatic maintenance": True})
                the_policy_check_enabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AutomaticMaintenanceEnabled[\s]*DWORD:1\s*",
                )
                the_policy_check_disabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AutomaticMaintenanceEnabled[\s]*DELETE",
                )
            elif "Scheduled install day" in item["element_aliases"]:
                the_policy.update({"Scheduled install day": "7 - Every Saturday"})
                the_policy_check_enabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallDay[\s]*DWORD:7",
                )
                the_policy_check_disabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallDay[\s]*DELETE",
                )
            elif "Scheduled install time" in item["element_aliases"]:
                the_policy.update({"Scheduled install time": "17:00"})
                the_policy_check_enabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallTime[\s]*DWORD:17",
                )
                the_policy_check_disabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallTime[\s]*DELETE",
                )
            elif (
                "Install updates for other Microsoft products"
                in item["element_aliases"]
            ):
                the_policy.update(
                    {"Install updates for other Microsoft products": True}
                )
                the_policy_check_enabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AllowMUUpdateService[\s]*DWORD:1\s*"
                )
                the_policy_check_disabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AllowMUUpdateService[\s]*DELETE"
                )
            elif "AutoUpdateSchEveryWeek" in item["element_aliases"]:
                the_policy.update({"AutoUpdateSchEveryWeek": True})
                the_policy_check_enabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallEveryWeek[\s]*DWORD:1\s*"
                )
                the_policy_check_disabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallEveryWeek[\s]*DELETE"
                )
            elif "First week of the month" in item["element_aliases"]:
                the_policy.update({"First week of the month": True})
                the_policy_check_enabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallFirstWeek[\s]*DWORD:1\s*"
                )
                the_policy_check_disabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallFirstWeek[\s]*DELETE"
                )
            elif "Second week of the month" in item["element_aliases"]:
                the_policy.update({"Second week of the month": True})
                the_policy_check_enabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallSecondWeek[\s]*DWORD:1\s*"
                )
                the_policy_check_disabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallSecondWeek[\s]*DELETE"
                )
            elif "Third week of the month" in item["element_aliases"]:
                the_policy.update({"Third week of the month": True})
                the_policy_check_enabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallThirdWeek[\s]*DWORD:1\s*"
                )
                the_policy_check_disabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallThirdWeek[\s]*DELETE"
                )
            elif "Fourth week of the month" in item["element_aliases"]:
                the_policy.update({"Fourth week of the month": True})
                the_policy_check_enabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallFourthWeek[\s]*DWORD:1\s*"
                )
                the_policy_check_disabled.append(
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallFourthWeek[\s]*DELETE"
                )

        # enable Automatic Updates
        self._testAdmxPolicy(
            r"Windows Components\Windows Update\Configure Automatic Updates",
            the_policy,
            the_policy_check_enabled,
        )

        # disable Configure Automatic Updates
        self._testAdmxPolicy(
            r"Windows Components\Windows Update\Configure Automatic Updates",
            "Disabled",
            the_policy_check_disabled,
        )

        # set Configure Automatic Updates to 'Not Configured'
        self._testAdmxPolicy(
            r"Windows Components\Windows Update\Configure Automatic Updates",
            "Not Configured",
            [
                r"; Source file: "
                r" c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*;"
                r" PARSING COMPLETED."
            ],
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_ClipboardRedirection(self):
        """
        Test setting/unsetting/changing ClipboardRedirection policy
        """
        # Enable/Disable/Not Configured "Do not allow Clipboard redirection"
        self._testAdmxPolicy(
            r"Windows Components\Remote Desktop Services\Remote Desktop Session"
            r" Host\Device and Resource Redirection\Do not allow Clipboard redirection",
            "Enabled",
            [
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fDisableClip[\s]*DWORD:1"
            ],
        )
        self._testAdmxPolicy(
            r"Windows Components\Remote Desktop Services\Remote Desktop Session"
            r" Host\Device and Resource Redirection\Do not allow Clipboard redirection",
            "Disabled",
            [
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fDisableClip[\s]*DWORD:0"
            ],
        )
        self._testAdmxPolicy(
            r"Windows Components\Remote Desktop Services\Remote Desktop Session"
            r" Host\Device and Resource Redirection\Do not allow Clipboard redirection",
            "Not Configured",
            [
                r"; Source file: "
                r" c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*;"
                r" PARSING COMPLETED."
            ],
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_LockoutDuration(self):
        """
        Test setting LockoutDuration
        """
        # For LockoutDuration to be meaningful, first configure
        # LockoutThreshold
        self._testSeceditPolicy("LockoutThreshold", 3, [r"^LockoutBadCount = 3"])

        # Next set the LockoutDuration non-zero value, as this is required
        # before setting LockoutWindow
        self._testSeceditPolicy("LockoutDuration", 60, [r"^LockoutDuration = 60"])

        # Now set LockoutWindow to a valid value <= LockoutDuration. If this
        # is not set, then the LockoutDuration zero value is ignored by the
        # Windows API (leading to a false sense of accomplishment)
        self._testSeceditPolicy("LockoutWindow", 60, [r"^ResetLockoutCount = 60"])

        # set LockoutDuration zero value, the secedit zero value is -1
        self._testSeceditPolicy("LockoutDuration", 0, [r"^LockoutDuration = -1"])

    @pytest.mark.destructive_test
    def test_set_computer_policy_GuestAccountStatus(self):
        """
        Test setting/unsetting/changing GuestAccountStatus
        """
        # disable GuestAccountStatus
        self._testSeceditPolicy(
            "GuestAccountStatus", "Disabled", [r"^EnableGuestAccount = 0"]
        )
        # enable GuestAccountStatus
        self._testSeceditPolicy(
            "GuestAccountStatus", "Enabled", [r"^EnableGuestAccount = 1"]
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_PasswordComplexity(self):
        """
        Test setting/unsetting/changing PasswordComplexity
        """
        # disable PasswordComplexity
        self._testSeceditPolicy(
            "Password must meet complexity requirements",
            "Disabled",
            [r"^PasswordComplexity = 0"],
        )
        # enable PasswordComplexity
        self._testSeceditPolicy(
            "PasswordComplexity", "Enabled", [r"^PasswordComplexity = 1"]
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_PasswordLen(self):
        """
        Test setting/unsetting/changing PasswordLength
        """
        # set Minimum password length
        self._testSeceditPolicy(
            "Minimum password length", 10, [r"^MinimumPasswordLength = 10"]
        )
        # set MinimumPasswordLength = 0
        self._testSeceditPolicy("MinPasswordLen", 0, [r"^MinimumPasswordLength = 0"])

    @pytest.mark.destructive_test
    def test_set_computer_policy_SeNetworkLogonRight(self):
        """
        Test setting/unsetting/changing PasswordLength
        """
        # set SeNetworkLogonRight to only Administrators
        self._testSeceditPolicy(
            "Access this computer from the network",
            ["Administrators"],
            [r"^SeNetworkLogonRight = \*S-1-5-32-544"],
            cumulative_rights_assignments=False,
        )
        # set SeNetworkLogonRight back to the default
        self._testSeceditPolicy(
            "SeNetworkLogonRight",
            ["Everyone", "Administrators", "Users", "Backup Operators"],
            [
                r"^SeNetworkLogonRight ="
                r" \*S-1-1-0,\*S-1-5-32-544,\*S-1-5-32-545,\*S-1-5-32-551"
            ],
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_multipleAdmxPolicies(self):
        """
        Tests setting several ADMX policies in succession and validating the configuration w/lgop
        """
        # set one policy
        self._testAdmxPolicy(
            r"Windows Components\Remote Desktop Services\Remote Desktop Session"
            r" Host\Device and Resource Redirection\Do not allow Clipboard redirection",
            "Disabled",
            [
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fDisableClip[\s]*DWORD:0"
            ],
        )

        # set another policy and make sure both this policy and the previous are okay
        self._testAdmxPolicy(
            "RA_Unsolicit",
            {
                "Permit remote control of this computer": (
                    "Allow helpers to remotely control the computer"
                ),
                "Helpers": ["administrators", "user1"],
            },
            [
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fDisableClip[\s]*DWORD:0",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services\\RAUnsolicit[\s]*user1[\s]*SZ:user1[\s]*",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services\\RAUnsolicit[\s]*administrators[\s]*SZ:administrators[\s]*",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fAllowUnsolicited[\s]*DWORD:1",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fAllowUnsolicitedFullControl[\s]*DWORD:1",
            ],
        )
        # Configure Automatic Updates and validate everything is still okay
        self._testAdmxPolicy(
            r"Windows Components\Windows Update\Configure Automatic Updates",
            "Disabled",
            [
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fDisableClip[\s]*DWORD:0",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services\\RAUnsolicit[\s]*user1[\s]*SZ:user1[\s]*",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services\\RAUnsolicit[\s]*administrators[\s]*SZ:administrators[\s]*",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fAllowUnsolicited[\s]*DWORD:1",
                r"Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal"
                r" Services[\s]*fAllowUnsolicitedFullControl[\s]*DWORD:1",
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*NoAutoUpdate[\s]*DWORD:1",
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AUOptions[\s]*DELETE",
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AutomaticMaintenanceEnabled[\s]*DELETE",
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallDay[\s]*DELETE",
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallTime[\s]*DELETE",
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AllowMUUpdateService[\s]*DELETE",
            ],
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_DisableDomainCreds(self):
        """
        Tests Enable/Disable of DisableDomainCreds policy
        """
        self._testRegistryPolicy(
            policy_name="DisableDomainCreds",
            policy_config="Enabled",
            registry_value_hive="HKEY_LOCAL_MACHINE",
            registry_value_path="SYSTEM\\CurrentControlSet\\Control\\Lsa",
            registry_value_vname="DisableDomainCreds",
            expected_value_data=1,
        )
        self._testRegistryPolicy(
            policy_name=(
                "Network access: Do not allow storage of passwords and credentials for"
                " network authentication"
            ),
            policy_config="Disabled",
            registry_value_hive="HKEY_LOCAL_MACHINE",
            registry_value_path="SYSTEM\\CurrentControlSet\\Control\\Lsa",
            registry_value_vname="DisableDomainCreds",
            expected_value_data=0,
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_ForceGuest(self):
        """
        Tests changing ForceGuest policy
        """
        self._testRegistryPolicy(
            policy_name="ForceGuest",
            policy_config="Guest only - local users authenticate as Guest",
            registry_value_hive="HKEY_LOCAL_MACHINE",
            registry_value_path="SYSTEM\\CurrentControlSet\\Control\\Lsa",
            registry_value_vname="ForceGuest",
            expected_value_data=1,
        )
        self._testRegistryPolicy(
            policy_name="Network access: Sharing and security model for local accounts",
            policy_config="Classic - local users authenticate as themselves",
            registry_value_hive="HKEY_LOCAL_MACHINE",
            registry_value_path="SYSTEM\\CurrentControlSet\\Control\\Lsa",
            registry_value_vname="ForceGuest",
            expected_value_data=0,
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_DisableUXWUAccess(self):
        """
        Tests changing DisableUXWUAccess
        #50079 shows using the 'Remove access to use all Windows Update features' failed
        Policy only exists on 2016
        """
        valid_osreleases = ["2016Server"]
        if self.osrelease not in valid_osreleases:
            self.skipTest(
                "DisableUXWUAccess policy is only applicable if the osrelease grain"
                " is {}".format(" or ".join(valid_osreleases))
            )
        else:
            self._testAdmxPolicy(
                r"DisableUXWUAccess",
                "Enabled",
                [
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*SetDisableUXWUAccess[\s]*DWORD:1"
                ],
            )
            self._testAdmxPolicy(
                r"Remove access to use all Windows Update features",
                "Disabled",
                [
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*SetDisableUXWUAccess[\s]*DWORD:0"
                ],
            )
            self._testAdmxPolicy(
                r"Windows Components\Windows Update\Remove access to use all Windows"
                r" Update features",
                "Not Configured",
                [
                    r"; Source file: "
                    r" c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*;"
                    r" PARSING COMPLETED."
                ],
            )

    @pytest.mark.destructive_test
    def test_set_computer_policy_Access_data_sources_across_domains(self):
        """
        Tests that a policy that has multiple names
        """
        self._testAdmxPolicy(
            r"Access data sources across domains", "Enabled", [], assert_true=False
        )
        self._testAdmxPolicy(
            r"Windows Components\Internet Explorer\Internet Control Panel\Security"
            r" Page\Internet Zone\Access data sources across domains",
            {"Access data sources across domains": "Prompt"},
            [
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\CurrentVersion\\Internet"
                r" Settings\\Zones\\3[\s]*1406[\s]*DWORD:1"
            ],
        )
        self._testAdmxPolicy(
            r"Windows Components\Internet Explorer\Internet Control Panel\Security"
            r" Page\Internet Zone\Access data sources across domains",
            {"Access data sources across domains": "Enable"},
            [
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\CurrentVersion\\Internet"
                r" Settings\\Zones\\3[\s]*1406[\s]*DWORD:0"
            ],
        )
        self._testAdmxPolicy(
            r"Windows Components\Internet Explorer\Internet Control Panel\Security"
            r" Page\Internet Zone\Access data sources across domains",
            "Disabled",
            [
                r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\CurrentVersion\\Internet"
                r" Settings\\Zones\\3[\s]*1406[\s]*DELETE"
            ],
        )

    @pytest.mark.destructive_test
    def test_set_computer_policy_ActiveHours(self):
        """
        Test configuring the ActiveHours policy, #47784
        Only applies to 2016Server
        # activehours.sls
            active_hours_policy:
              lgpo.set:
                - computer_policy:
                    'ActiveHours':
                        'ActiveHoursStartTime': '8 AM'
                        'ActiveHoursEndTime': '7 PM'
        """
        valid_osreleases = ["2016Server"]
        if self.osrelease not in valid_osreleases:
            self.skipTest(
                "ActiveHours policy is only applicable if the osrelease grain is {}".format(
                    " or ".join(valid_osreleases)
                )
            )
        else:
            self._testAdmxPolicy(
                r"ActiveHours",
                {"ActiveHoursStartTime": "8 AM", "ActiveHoursEndTime": "7 PM"},
                [
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*SetActiveHours[\s]*DWORD:1",
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursStart[\s]*DWORD:8",
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursEnd[\s]*DWORD:19",
                ],
            )
            self._testAdmxPolicy(
                r"ActiveHours",
                {"ActiveHoursStartTime": "5 AM", "ActiveHoursEndTime": "10 PM"},
                [
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*SetActiveHours[\s]*DWORD:1",
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursStart[\s]*DWORD:5",
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursEnd[\s]*DWORD:22",
                ],
            )
            self._testAdmxPolicy(
                "Turn off auto-restart for updates during active hours",
                "Disabled",
                [
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*SetActiveHours[\s]*DWORD:0",
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursStart[\s]*DELETE",
                    r"Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursEnd[\s]*DELETE",
                ],
            )
            self._testAdmxPolicy(
                r"Windows Components\Windows Update\Turn off auto-restart for updates"
                r" during active hours",
                "Not Configured",
                [
                    r"; Source file: "
                    r" c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*;"
                    r" PARSING COMPLETED."
                ],
            )

    @pytest.mark.destructive_test
    def test_set_computer_policy_AllowTelemetry(self):
        """
        Tests that a the AllowTelemetry policy is applied correctly and that it
        doesn't appear in subsequent group policy states as having changed
        """
        valid_osreleases = ["10", "2016Server", "2019Server"]
        if self.osrelease not in valid_osreleases:
            self.skipTest(
                "Allow Telemetry policy is only applicable if the "
                "osrelease grain is {}".format(" or ".join(valid_osreleases))
            )
        else:
            self._testAdmxPolicy(
                "Allow Telemetry",
                {"AllowTelemetry": "1 - Basic"},
                [
                    r"Software\\Policies\\Microsoft\\Windows\\DataCollection[\s]*AllowTelemetry[\s]*DWORD:1"
                ],
                assert_true=True,
            )
            # This policy does not exist on newer Windows builds
            result = self.run_function(
                "lgpo.get_policy_info",
                ["Disable pre-release features or settings"],
                policy_class="machine",
            )
            if result["policy_found"]:
                result = self.run_function(
                    "state.single",
                    ["lgpo.set"],
                    name="state",
                    computer_policy={
                        "Disable pre-release features or settings": "Disabled"
                    },
                )
                name = "lgpo_|-state_|-state_|-set"
                expected = {
                    "new": {
                        "Computer Configuration": {
                            "Disable pre-release features or settings": "Disabled"
                        }
                    },
                    "old": {
                        "Computer Configuration": {
                            "Disable pre-release features or settings": "Not Configured"
                        }
                    },
                }
                self.assertDictEqual(result[name]["changes"], expected)
            else:
                result = self.run_function(
                    "lgpo.get_policy_info",
                    ["Manage preview builds"],
                    policy_class="machine",
                )
                if result["policy_found"]:
                    result = self.run_function(
                        "state.single",
                        ["lgpo.set"],
                        name="state",
                        computer_policy={"Manage preview builds": "Disabled"},
                    )
                    name = "lgpo_|-state_|-state_|-set"
                    expected = {
                        "new": {
                            "Computer Configuration": {
                                "Manage preview builds": "Disabled"
                            }
                        },
                        "old": {
                            "Computer Configuration": {
                                "Manage preview builds": "Not Configured"
                            }
                        },
                    }
                    self.assertDictEqual(result[name]["changes"], expected)

    @pytest.mark.destructive_test
    def test_set_computer_policy_ScRemoveOption(self):
        """
        Tests changing ScRemoveOption policy
        """
        self._testRegistryPolicy(
            "ScRemoveOption",
            "No Action",
            "HKEY_LOCAL_MACHINE",
            "Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon",
            "ScRemoveOption",
            "0",
            "REG_SZ",
        )
        self._testRegistryPolicy(
            "Interactive logon: Smart card removal behavior",
            "Lock Workstation",
            "HKEY_LOCAL_MACHINE",
            "Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon",
            "ScRemoveOption",
            "1",
            "REG_SZ",
        )
        self._testRegistryPolicy(
            "Interactive logon: Smart card removal behavior",
            "Not Defined",
            "HKEY_LOCAL_MACHINE",
            "Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon",
            "ScRemoveOption",
            None,
            None,
            False,
        )

    @pytest.mark.destructive_test
    def test_set_sxs_servicing_policy(self):
        """
        Test setting/unsetting/changing sxs-servicing policy
        """

        # Disable sxs-servicing
        log.debug("Attempting to disable sxs-servicing")
        self._testAdmxPolicy(
            "Specify settings for optional component installation and component repair",
            "Disabled",
            [
                r"Computer[\s]*Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Servicing[\s]*LocalSourcePath[\s]*DELETE",
                r"Computer[\s]*Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Servicing[\s]*UseWindowsUpdate[\s]*DELETE",
                r"Computer[\s]*Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Servicing[\s]*RepairContentServerSource[\s]*DELETE",
            ],
        )
        # configure sxs-servicing
        log.debug("Attempting to enable sxs-servicing")
        self._testAdmxPolicy(
            "Specify settings for optional component installation and component repair",
            {
                "Alternate source file path": "",
                "Never attempt to download payload from Windows Update": True,
                "CheckBox_SidestepWSUS": False,
            },
            [
                r"Computer[\s]*Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Servicing[\s]*LocalSourcePath[\s]*EXSZ:",
                r"Computer[\s]*Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Servicing[\s]*UseWindowsUpdate[\s]*DWORD:2",
                r"Computer[\s]*Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Servicing[\s]*RepairContentServerSource[\s]*DELETE",
            ],
        )
        log.debug("Attempting to set different values on sxs-servicing")
        self._testAdmxPolicy(
            "Specify settings for optional component installation and component repair",
            {
                "Alternate source file path": r"\\some\fake\server",
                "Never attempt to download payload from Windows Update": True,
                "CheckBox_SidestepWSUS": False,
            },
            [
                r"Computer[\s]*Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Servicing[\s]*LocalSourcePath[\s]*EXSZ:\\\\\\\\some\\\\fake\\\\server",
                r"Computer[\s]*Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Servicing[\s]*UseWindowsUpdate[\s]*DWORD:2",
                r"Computer[\s]*Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Servicing[\s]*RepairContentServerSource[\s]*DELETE",
            ],
        )
        # Not Configure sxs-servicing
        log.debug("Attempting to set sxs-servicing to Not Configured")
        self._testAdmxPolicy(
            "Specify settings for optional component installation and component repair",
            "Not Configured",
            [
                r"; Source file: "
                r" c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*;"
                r" PARSING COMPLETED."
            ],
        )

    def tearDown(self):
        """
        tearDown method, runs after each test
        """
        self.run_state(
            "file.absent",
            name="c:\\windows\\system32\\grouppolicy\\machine\\registry.pol",
        )
        self.run_state(
            "file.absent", name="c:\\windows\\system32\\grouppolicy\\user\\registry.pol"
        )
