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
import re
from string import Template

# pylint: disable-msg=C0103
# pylint: disable-msg=R0902
# pylint: disable-msg=W0613
# pylint: disable-msg=C0301


class NXOSPlatform:

    """Cisco Systems Base Platform Unit Test Object"""

    chassis = "Unknown NXOS Chassis"

    upgrade_required = False

    show_install_all_impact_no_module_data = """
Installer will perform impact only check. Please wait. 

Verifying image bootflash:/$IMAGE for boot variable "nxos".
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Preparing "nxos" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Preparing "bios" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Performing module support checks.
[####################] 100% -- SUCCESS

Notifying services about system upgrade.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     1       yes      disruptive         reset  default upgrade is not hitless



Images will be upgraded according to following table:
Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
------  ----------  ----------------------------------------  --------------------  ------------
    """

    internal_server_error_500 = """
    Code: 500
    """

    invalid_command = """
    % Invalid command at '^' marker.
    """

    internal_server_error_500_dict = {
        "code": "500",
        "cli_error": internal_server_error_500,
    }

    bad_request_client_error_400_invalid_command_dict = {
        "code": "400",
        "cli_error": invalid_command,
    }

    backend_processing_error_500 = internal_server_error_500_dict

    show_install_all_impact_in_progress = """
    Installer will perform impact only check. Please wait.
    Another install procedure may be in progress. (0x401E0007)
    """

    bad_request_client_error_400_in_progress_dict = {
        "code": "400",
        "cli_error": show_install_all_impact_in_progress,
    }

    show_install_all_impact = None

    install_all_disruptive_success = None

    show_install_all_impact_non_disruptive = None

    install_all_non_disruptive_success = None

    def __init__(self, *args, **kwargs):

        """
        ckimage - current kickstart image
        cimage - current system image
        nkimage - new kickstart image
        nimage - new system image
        """

        self.ckimage = kwargs.get("ckimage", None)
        self.cimage = kwargs.get("cimage", None)
        self.nkimage = kwargs.get("nkimage", None)
        self.nimage = kwargs.get("nimage", None)
        self.ckversion = self.version_from_image(self.ckimage)
        self.cversion = self.version_from_image(self.cimage)
        self.nkversion = self.version_from_image(self.nkimage)
        self.nversion = self.version_from_image(self.nimage)

        self.upgrade_required = self.cversion != self.nversion

        values = {
            "KIMAGE": self.nkimage,
            "IMAGE": self.nimage,
            "CKVER": self.ckversion,
            "CVER": self.cversion,
            "NKVER": self.nkversion,
            "NVER": self.nversion,
            "REQ": "no" if self.cversion == self.nversion else "yes",
            "KREQ": "no" if self.ckversion == self.nkversion else "yes",
        }

        if self.show_install_all_impact_no_module_data:
            self.show_install_all_impact_no_module_data = self.templatize(
                self.show_install_all_impact_no_module_data, values
            )

        if self.show_install_all_impact:
            self.show_install_all_impact = self.templatize(
                self.show_install_all_impact, values
            )

        if self.show_install_all_impact_non_disruptive:
            self.show_install_all_impact_non_disruptive = self.templatize(
                self.show_install_all_impact_non_disruptive, values
            )

        if self.install_all_non_disruptive_success:
            self.install_all_non_disruptive_success = self.templatize(
                self.install_all_non_disruptive_success, values
            )

        if self.install_all_disruptive_success:
            self.install_all_disruptive_success = self.templatize(
                self.install_all_disruptive_success, values
            )

    @staticmethod
    def templatize(template, values):

        """Substitute variables in template with their corresponding values"""

        return Template(template).substitute(values)

    @staticmethod
    def version_from_image(image):

        """Given a NXOS image named image decompose to appropriate image version"""

        ver = None
        if image:
            match_object = re.search(
                r"^.*\.(\d+)\.(\d+)\.(\d+)\.(\d+|[A-Z][0-9])\.(?:bin)?(\d+)?.*", image
            )
            try:
                ver = match_object.group(1)
                ver += "." + match_object.group(2)
                if match_object.groups()[-1]:
                    ver += "(" + match_object.group(3) + ")"
                    ver += match_object.group(4)
                    ver += "(" + match_object.group(5) + ")"
                else:
                    ver += (
                        "(" + match_object.group(3) + "." + match_object.group(4) + ")"
                    )
            except IndexError:
                return None

        return ver
