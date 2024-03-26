"""
    :codeauthor: Thomas Stoner <tmstoner@cisco.com>
"""

# Copyright (c) 2018 Cisco and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import salt.modules.nxos_upgrade as nxos_upgrade
from salt.exceptions import CommandExecutionError, NxosError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase
from tests.unit.modules.nxos.nxos_n3k import N3KPlatform
from tests.unit.modules.nxos.nxos_n5k import N5KPlatform
from tests.unit.modules.nxos.nxos_n7k import N7KPlatform
from tests.unit.modules.nxos.nxos_n36k import N36KPlatform
from tests.unit.modules.nxos.nxos_n93k import N93KPlatform
from tests.unit.modules.nxos.nxos_n93klxc import N93KLXCPlatform
from tests.unit.modules.nxos.nxos_n95k import N95KPlatform

# pylint: disable-msg=C0103
# pylint: disable-msg=C0301
# pylint: disable-msg=E1101
# pylint: disable-msg=R0904


class NxosUpgradeTestCase(TestCase, LoaderModuleMockMixin):
    """Test cases for salt.modules.nxos_upgrade"""

    platform_list = None

    @staticmethod
    def assert_platform_upgrade(condition, platform):
        """Assert platform upgrade condition and display appropriate chassis & images upon assertion failure"""

        assert bool(condition), "{}: Upgrade {} -> {}".format(
            platform.chassis, platform.cimage, platform.nimage
        )

    def setup_loader_modules(self):
        """Define list of platforms for Unit Test"""

        self.platform_list = [
            N3KPlatform(cimage="nxos.7.0.3.F3.3.bin", nimage="nxos.9.2.1.255.bin"),
            N36KPlatform(cimage="nxos.9.1.2.50.bin", nimage="nxos.9.2.2.50.bin"),
            N5KPlatform(
                ckimage="n6000-uk9-kickstart.7.3.0.N1.1.bin",
                cimage="n6000-uk9.7.3.0.N1.1.bin",
                nkimage="n6000-uk9-kickstart.7.3.3.N2.1.bin",
                nimage="n6000-uk9.7.3.3.N2.1.bin",
            ),
            N7KPlatform(
                ckimage="n7000-s2-kickstart.7.3.0.D1.1.bin",
                cimage="n7000-s2-dk9.7.3.0.D1.1.bin",
                nkimage="n7000-s2-kickstart.8.3.1.112.gbin",
                nimage="n7000-s2-dk9.8.3.1.112.gbin",
            ),
            N93KPlatform(cimage="nxos.7.0.3.I7.4.bin", nimage="nxos.7.0.3.I7.5.bin"),
            N93KPlatform(cimage="nxos.7.0.3.I7.5.bin", nimage="nxos.7.0.3.I7.5.bin"),
            N93KLXCPlatform(cimage="nxos.7.0.3.I7.4.bin", nimage="nxos.7.0.3.I7.5.bin"),
            N95KPlatform(cimage="nxos.7.0.3.I7.4.bin", nimage="nxos.9.2.2.14.bin"),
        ]

        return {nxos_upgrade: {}}

    def tearDown(self):
        del self.platform_list

    @staticmethod
    def test_check_upgrade_impact_input_validation():
        """UT: nxos_upgrade module:check_upgrade_impact method - input validation"""

        result = nxos_upgrade.check_upgrade_impact("dummy-platform-image.bin", issu=1)
        assert "Input Error" in result

    @staticmethod
    def test_upgrade_input_validation():
        """UT: nxos_upgrade module:upgrade method - input validation"""

        result = nxos_upgrade.upgrade("dummy-platform-image.bin", issu=1)
        assert "Input Error" in result

    def test_check_upgrade_impact_backend_processing_error_500(self):
        """UT: nxos_upgrade module:check_upgrade_impact method - error HTTP code 500"""

        for platform in self.platform_list:
            if platform.backend_processing_error_500:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            return_value=platform.backend_processing_error_500
                        )
                    },
                ):
                    result = nxos_upgrade.check_upgrade_impact(platform.nimage)
                    self.assert_platform_upgrade(
                        result["backend_processing_error"], platform
                    )
                    self.assert_platform_upgrade(not result["succeeded"], platform)

    def test_check_upgrade_impact_internal_server_error_400_invalid_command(self):
        """UT: nxos_upgrade module:check_upgrade_impact method - invalid command error HTTP code 400"""

        for platform in self.platform_list:
            if platform.bad_request_client_error_400_invalid_command_dict:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            return_value=platform.bad_request_client_error_400_invalid_command_dict
                        )
                    },
                ):
                    result = nxos_upgrade.check_upgrade_impact(platform.nimage)
                    self.assert_platform_upgrade(result["invalid_command"], platform)
                    self.assert_platform_upgrade(not result["succeeded"], platform)

    def test_check_upgrade_impact_internal_server_error_400_in_progress(self):
        """UT: nxos_upgrade module:check_upgrade_impact method - in-progress error HTTP code 400"""

        for platform in self.platform_list:
            if platform.bad_request_client_error_400_in_progress_dict:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            return_value=platform.bad_request_client_error_400_in_progress_dict
                        )
                    },
                ):
                    result = nxos_upgrade.check_upgrade_impact(platform.nimage)
                    self.assert_platform_upgrade(result["installing"], platform)
                    self.assert_platform_upgrade(not result["succeeded"], platform)

    def test_check_upgrade_impact_internal_server_error_500(self):
        """UT: nxos_upgrade module:check_upgrade_impact method - internal server error HTTP code 500"""

        for platform in self.platform_list:
            if platform.internal_server_error_500:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            return_value=platform.internal_server_error_500
                        )
                    },
                ):
                    result = nxos_upgrade.check_upgrade_impact(platform.nimage)
                    self.assert_platform_upgrade(
                        platform.internal_server_error_500 in result["error_data"],
                        platform,
                    )
                    self.assert_platform_upgrade(
                        result["backend_processing_error"], platform
                    )
                    self.assert_platform_upgrade(not result["succeeded"], platform)

    def test_check_upgrade_impact_non_disruptive_success(self):
        """UT: nxos_upgrade module:check_upgrade_impact method - non-disruptive success"""

        for platform in self.platform_list:
            if platform.install_all_non_disruptive_success:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            return_value=platform.install_all_non_disruptive_success
                        )
                    },
                ):
                    result = nxos_upgrade.check_upgrade_impact(platform.nimage)
                    self.assert_platform_upgrade(
                        result["upgrade_non_disruptive"], platform
                    )
                    self.assert_platform_upgrade(result["succeeded"], platform)
                    self.assert_platform_upgrade(result["module_data"], platform)

    def test_check_upgrade_impact_disruptive_success(self):
        """UT: nxos_upgrade module:check_upgrade_impact method - disruptive success"""

        for platform in self.platform_list:
            if platform.install_all_disruptive_success:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            return_value=platform.install_all_disruptive_success
                        )
                    },
                ):
                    result = nxos_upgrade.check_upgrade_impact(platform.nimage)
                    self.assert_platform_upgrade(
                        result["upgrade_required"] == platform.upgrade_required,
                        platform,
                    )
                    self.assert_platform_upgrade(
                        not result["upgrade_non_disruptive"], platform
                    )
                    self.assert_platform_upgrade(not result["succeeded"], platform)
                    self.assert_platform_upgrade(
                        result["upgrade_in_progress"], platform
                    )
                    self.assert_platform_upgrade(result["module_data"], platform)

    def test_upgrade_show_install_all_impact_no_module_data(self):
        """UT: nxos_upgrade module: upgrade method - no module data"""

        for platform in self.platform_list:
            if platform.show_install_all_impact_no_module_data:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            return_value=platform.show_install_all_impact_no_module_data
                        )
                    },
                ):
                    result = nxos_upgrade.upgrade(platform.nimage, issu=False)
                    self.assert_platform_upgrade(not result["succeeded"], platform)
                    self.assert_platform_upgrade(
                        result["error_data"] == result["upgrade_data"], platform
                    )

    def test_upgrade_invalid_command(self):
        """UT: nxos_upgrade module:upgrade method - invalid command"""

        for platform in self.platform_list:
            if platform.invalid_command:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {"nxos.sendline": MagicMock(return_value=platform.invalid_command)},
                ):
                    result = nxos_upgrade.upgrade(platform.nimage, platform.nkimage)
                    self.assert_platform_upgrade(result["error_data"], platform)
                    self.assert_platform_upgrade(not result["succeeded"], platform)

    def test_upgrade_install_in_progress(self):
        """UT: nxos_upgrade module:upgrade method - in-progress"""

        for platform in self.platform_list:
            if platform.show_install_all_impact_in_progress:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            return_value=platform.show_install_all_impact_in_progress
                        )
                    },
                ):
                    result = nxos_upgrade.upgrade(platform.nimage, platform.nkimage)
                    self.assert_platform_upgrade(result["error_data"], platform)
                    self.assert_platform_upgrade(not result["succeeded"], platform)

    def test_upgrade_install_in_progress_terminal_dont_ask(self):
        """UT: nxos_upgrade module:upgrade method - in-progress (terminal don't-ask)"""

        for platform in self.platform_list:
            if platform.invalid_command:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            return_value=[
                                {},
                                platform.show_install_all_impact_in_progress,
                            ]
                        )
                    },
                ):
                    result = nxos_upgrade.upgrade(platform.nimage, platform.nkimage)
                    self.assert_platform_upgrade(result["error_data"], platform)
                    self.assert_platform_upgrade(not result["succeeded"], platform)

    def test_upgrade_install_in_progress_sans_terminal_dont_ask(self):
        """UT: nxos_upgrade module:upgrade method - in-progress (sans terminal don't-ask)"""

        for platform in self.platform_list:
            if platform.invalid_command:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            return_value=[platform.show_install_all_impact_in_progress]
                        )
                    },
                ):
                    result = nxos_upgrade.upgrade(platform.nimage, platform.nkimage)
                    self.assert_platform_upgrade(result["error_data"], platform)
                    self.assert_platform_upgrade(not result["succeeded"], platform)

    def test_upgrade_internal_server_error_500(self):
        """UT: nxos_upgrade module:upgrade method - internal server error 500"""

        for platform in self.platform_list:
            if platform.backend_processing_error_500:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            return_value=platform.internal_server_error_500
                        )
                    },
                ):
                    result = nxos_upgrade.upgrade(platform.nimage)
                    self.assert_platform_upgrade(result["error_data"], platform)
                    self.assert_platform_upgrade(
                        result["backend_processing_error"], platform
                    )
                    self.assert_platform_upgrade(not result["succeeded"], platform)

    def test_upgrade_install_all_disruptive(self):
        """UT: nxos_upgrade module:upgrade method - install all disruptive"""

        for platform in self.platform_list:
            if platform.show_install_all_impact:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            side_effect=[
                                platform.show_install_all_impact,
                                platform.install_all_disruptive_success,
                            ]
                        )
                    },
                ):
                    result = nxos_upgrade.upgrade(
                        platform.nimage, platform.nkimage, issu=False
                    )
                    self.assert_platform_upgrade(not result["error_data"], platform)
                    if platform.upgrade_required:
                        self.assert_platform_upgrade(
                            result["upgrade_in_progress"], platform
                        )
                    else:
                        self.assert_platform_upgrade(
                            not result["upgrade_in_progress"], platform
                        )

    def test_upgrade_install_all_non_disruptive(self):
        """UT: nxos_upgrade module:upgrade method - install all non-disruptive"""

        for platform in self.platform_list:
            if platform.show_install_all_impact_non_disruptive:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            side_effect=[
                                platform.show_install_all_impact_non_disruptive,
                                platform.install_all_non_disruptive_success,
                            ]
                        )
                    },
                ):
                    result = nxos_upgrade.upgrade(
                        platform.nimage, platform.nkimage, issu=True
                    )
                    self.assert_platform_upgrade(not result["error_data"], platform)
                    self.assert_platform_upgrade(result["succeeded"], platform)

    def test_upgrade_CommandExecutionError_Exception(self):
        """UT: nxos_upgrade module:upgrade method - raise CommandExecutionError exception #1"""

        for platform in self.platform_list:
            if platform.invalid_command:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            side_effect=CommandExecutionError(
                                {
                                    "rejected_input": "invalid CLI command",
                                    "message": "CLI excution error",
                                    "code": "400",
                                    "cli_error": platform.invalid_command,
                                }
                            )
                        )
                    },
                ):
                    result = nxos_upgrade.upgrade(
                        platform.nimage, platform.nkimage, issu=False
                    )
                    self.assert_platform_upgrade(result["error_data"], platform)
                    self.assert_platform_upgrade(result["invalid_command"], platform)
                    self.assert_platform_upgrade(not result["succeeded"], platform)

    def test_upgrade_CommandExecutionError_Exception2(self):
        """UT: nxos_upgrade module:upgrade method - raise CommandExecutionError exception #2"""

        for platform in self.platform_list:
            if platform.invalid_command:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            side_effect=[
                                platform.show_install_all_impact,
                                CommandExecutionError(
                                    {
                                        "rejected_input": "invalid CLI command",
                                        "message": "CLI excution error",
                                        "code": "400",
                                        "cli_error": platform.invalid_command,
                                    }
                                ),
                            ]
                        )
                    },
                ):
                    result = nxos_upgrade.upgrade(
                        platform.nimage, platform.nkimage, issu=False
                    )
                    if platform.upgrade_required:
                        self.assert_platform_upgrade(result["error_data"], platform)
                        self.assert_platform_upgrade(
                            result["invalid_command"], platform
                        )
                        self.assert_platform_upgrade(not result["succeeded"], platform)
                    else:
                        self.assert_platform_upgrade(result["succeeded"], platform)

    def test_upgrade_NxosError_Exception(self):
        """UT: nxos_upgrade module:upgrade method - raise NxosError exception"""

        for platform in self.platform_list:
            if platform.internal_server_error_500:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            side_effect=[
                                platform.show_install_all_impact,
                                NxosError(platform.internal_server_error_500),
                            ]
                        )
                    },
                ):
                    result = nxos_upgrade.upgrade(
                        platform.nimage, platform.nkimage, issu=False
                    )
                    if platform.upgrade_required:
                        self.assert_platform_upgrade(
                            result["upgrade_in_progress"], platform
                        )
                        self.assert_platform_upgrade(not result["succeeded"], platform)
                    else:
                        self.assert_platform_upgrade(
                            not result["upgrade_in_progress"], platform
                        )
                        self.assert_platform_upgrade(result["succeeded"], platform)

    def test_upgrade_NxosError_Exception2(self):
        """UT: nxos_upgrade module:upgrade method - raise NxosError exception #2"""

        for platform in self.platform_list:
            if platform.internal_server_error_500:
                with patch.dict(
                    nxos_upgrade.__salt__,
                    {
                        "nxos.sendline": MagicMock(
                            side_effect=[
                                platform.show_install_all_impact,
                                NxosError(
                                    "{'Error Message': 'Not Found', 'Code': 404}"
                                ),
                            ]
                        )
                    },
                ):
                    result = nxos_upgrade.upgrade(
                        platform.nimage, platform.nkimage, issu=False
                    )
                    if platform.upgrade_required:
                        self.assert_platform_upgrade(
                            result["upgrade_in_progress"], platform
                        )
                        self.assert_platform_upgrade(not result["succeeded"], platform)
                    else:
                        self.assert_platform_upgrade(
                            not result["upgrade_in_progress"], platform
                        )
                        self.assert_platform_upgrade(result["succeeded"], platform)
