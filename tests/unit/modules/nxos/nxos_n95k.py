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
from tests.unit.modules.nxos.nxos_platform import NXOSPlatform

# pylint: disable-msg=C0103


class N95KPlatform(NXOSPlatform):

    """Cisco Systems N9K Platform Unit Test Object"""

    chassis = "Nexus9000 C9508 (8 Slot) Chassis"

    # Captured output from: show install all impact nxos <image>

    show_install_all_impact = """
Installer will perform impact only check. Please wait.

Verifying image bootflash:/$IMAGE for boot variable "nxos".
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Preparing "bios" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Preparing "nxos" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Performing module support checks.
[####################] 100% -- SUCCESS

Notifying services about system upgrade.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     1       yes  non-disruptive          none
    22       yes  non-disruptive          none
    24       yes  non-disruptive          none
    26       yes  non-disruptive          none
    28       yes  non-disruptive          none
    29       yes  non-disruptive          none
    30       yes  non-disruptive          none



Images will be upgraded according to following table:
Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
------  ----------  ----------------------------------------  --------------------  ------------
     1       lcn9k                               $CVER           $NVER            $REQ
     1        bios                       v01.48(00:v01.42(00             v01.48(00            no
    22       lcn9k                               $CVER           $NVER            $REQ
    22        bios                       v01.48(00:v01.42(00             v01.48(00            no
    24       lcn9k                               $CVER           $NVER            $REQ
    24        bios                       v01.48(00:v01.42(00             v01.48(00            no
    26       lcn9k                               $CVER           $NVER            $REQ
    26        bios                       v01.48(00:v01.42(00             v01.48(00            no
    28        nxos                               $CVER           $NVER            $REQ
    28        bios     v08.32(10/18/2016):v08.06(09/10/2014)    v08.32(10/18/2016)            no
    29       lcn9k                               $CVER           $NVER            $REQ
    29        bios                       v01.48(00:v01.42(00             v01.48(00            no
    30       lcn9k                               $CVER           $NVER            $REQ
    30        bios                       v01.48(00:v01.42(00             v01.48(00            no
"""

    # Captured output from: show install all impact nxos <image> non-disruptive

    show_install_all_impact_non_disruptive = """
Installer will perform impact only check. Please wait.

Verifying image bootflash:/$IMAGE for boot variable "nxos".
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Preparing "bios" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Preparing "nxos" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Performing module support checks.
[####################] 100% -- SUCCESS

Notifying services about system upgrade.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     1       yes  non-disruptive          none
    22       yes  non-disruptive          none
    24       yes  non-disruptive          none
    26       yes  non-disruptive          none
    28       yes  non-disruptive          none
    29       yes  non-disruptive          none
    30       yes  non-disruptive          none



Images will be upgraded according to following table:
Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
------  ----------  ----------------------------------------  --------------------  ------------
     1       lcn9k                                    $CVER                $NVER            $REQ
     1        bios                       v01.48(00:v01.42(00             v01.48(00            no
    22       lcn9k                                    $CVER                $NVER            $REQ
    22        bios                       v01.48(00:v01.42(00             v01.48(00            no
    24       lcn9k                                    $CVER                $NVER            $REQ
    24        bios                       v01.48(00:v01.42(00             v01.48(00            no
    26       lcn9k                                    $CVER                $NVER            $REQ
    26        bios                       v01.48(00:v01.42(00             v01.48(00            no
    28        nxos                                    $CVER                $NVER            $REQ
    28        bios     v08.35(08/31/2018):v08.06(09/10/2014)    v08.35(08/31/2018)            no
    29       lcn9k                                    $CVER                $NVER            $REQ
    29        bios                       v01.48(00:v01.42(00             v01.48(00            no
    30       lcn9k                                    $CVER                $NVER            $REQ
    30        bios                       v01.48(00:v01.42(00             v01.48(00            no
"""

    # Captured output from: install all nxos <image> non-disruptive

    install_all_non_disruptive_success = """
Installer will perform compatibility check first. Please wait.

Verifying image bootflash:/$IMAGE for boot variable "nxos".
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Preparing "bios" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Preparing "nxos" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Performing module support checks.
[####################] 100% -- SUCCESS

Notifying services about system upgrade.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     1       yes  non-disruptive          none
    22       yes  non-disruptive          none
    24       yes  non-disruptive          none
    26       yes  non-disruptive          none
    28       yes  non-disruptive          none
    29       yes  non-disruptive          none
    30       yes  non-disruptive          none



Images will be upgraded according to following table:
Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
------  ----------  ----------------------------------------  --------------------  ------------
     1       lcn9k                               $CVER           $NVER            $REQ
     1        bios                       v01.48(00:v01.42(00             v01.48(00            no
    22       lcn9k                               $CVER           $NVER            $REQ
    22        bios                       v01.48(00:v01.42(00             v01.48(00            no
    24       lcn9k                               $CVER           $NVER            $REQ
    24        bios                       v01.48(00:v01.42(00             v01.48(00            no
    26       lcn9k                               $CVER           $NVER            $REQ
    26        bios                       v01.48(00:v01.42(00             v01.48(00            no
    28        nxos                               $CVER           $NVER            $REQ
    28        bios     v08.32(10/18/2016):v08.06(09/10/2014)    v08.32(10/18/2016)            no
    29       lcn9k                               $CVER           $NVER            $REQ
    29        bios                       v01.48(00:v01.42(00             v01.48(00            no
    30       lcn9k                               $CVER           $NVER            $REQ
    30        bios                       v01.48(00:v01.42(00             v01.48(00            no


Install is in progress, please wait.

Performing runtime checks.
[####################] 100% -- SUCCESS

Setting boot variables.
[####################] 100% -- SUCCESS

Performing configuration copy.
[####################] 100% -- SUCCESS

Module 1: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 22: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 24: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 26: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 28: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 29: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 30: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS


Install has been successful.
"""

    # Captured output from: install all nxos <image>

    install_all_disruptive_success = """
Installer will perform compatibility check first. Please wait.
Installer is forced disruptive

Verifying image bootflash:/$IMAGE for boot variable "nxos".
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Preparing "bios" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Preparing "nxos" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Performing module support checks.
[####################] 100% -- SUCCESS

Notifying services about system upgrade.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     1       yes      disruptive         reset  default upgrade is not hitless
    22       yes      disruptive         reset  default upgrade is not hitless
    24       yes      disruptive         reset  default upgrade is not hitless
    26       yes      disruptive         reset  default upgrade is not hitless
    28       yes      disruptive         reset  default upgrade is not hitless
    29       yes      disruptive         reset  default upgrade is not hitless
    30       yes      disruptive         reset  default upgrade is not hitless



Images will be upgraded according to following table:
Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
------  ----------  ----------------------------------------  --------------------  ------------
     1       lcn9k                               $CVER                $NVER           $REQ
     1        bios                       v01.48(00:v01.42(00             v01.48(00            no
    22       lcn9k                               $CVER                $NVER           $REQ
    22        bios                       v01.48(00:v01.42(00             v01.48(00            no
    24       lcn9k                               $CVER                $NVER           $REQ
    24        bios                       v01.48(00:v01.42(00             v01.48(00            no
    26       lcn9k                               $CVER                $NVER           $REQ
    26        bios                       v01.48(00:v01.42(00             v01.48(00            no
    28        nxos                               $CVER                $NVER           $REQ
    28        bios     v08.32(10/18/2016):v08.06(09/10/2014)    v08.35(08/31/2018)           yes
    29       lcn9k                               $CVER                $NVER           $REQ
    29        bios                       v01.48(00:v01.42(00             v01.48(00            no
    30       lcn9k                               $CVER                $NVER           $REQ
    30        bios                       v01.48(00:v01.42(00             v01.48(00            no


Switch will be reloaded for disruptive upgrade.

Install is in progress, please wait.

Performing runtime checks.
[####################] 100% -- SUCCESS

Setting boot variables.
[####################] 100% -- SUCCESS

Performing configuration copy.
[####################] 100% -- SUCCESS

Module 1: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 22: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 24: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 26: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 28: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 29: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 30: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS


Finishing the upgrade, switch will reboot in 10 seconds.
"""
