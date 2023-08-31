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


class N93KLXCPlatform(NXOSPlatform):

    """Cisco Systems N93K (boot mode lxc) Platform Unit Test Object"""

    chassis = "Nexus9000 C9396PX (LXC) Chassis"

    # Captured output from: show install all nxos <image>

    show_install_all_impact = """
Installer will perform impact only check. Please wait.

Verifying image bootflash:/$IMAGE for boot variable "nxos".
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Preparing "nxos" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Preparing "bios" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Notifying services about system upgrade.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     1       yes      disruptive         reset  Host kernel is not compatible with target image
    27       yes      disruptive         reset  Host kernel is not compatible with target image



Images will be upgraded according to following table:
Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
------  ----------  ----------------------------------------  --------------------  ------------
     1       lcn9k                               $CVER                $NVER           $REQ
    27        nxos                               $CVER                $NVER           $REQ
    27        bios     v07.64(05/16/2018):v07.06(03/02/2014)    v07.64(05/16/2018)            no


Additional info for this installation:
--------------------------------------

"Host kernel is not compatible with target image.
Disruptive ISSU will be performed "
"""

    # Captured output from: show install all nxos <image> non-disruptive

    show_install_all_impact_non_disruptive = """
Installer will perform impact only check. Please wait.

Verifying image bootflash:/$IMAGE for boot variable "nxos".
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Preparing "nxos" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Preparing "bios" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Notifying services about system upgrade.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     1       yes  non-disruptive       rolling
    27       yes  non-disruptive         reset



Images will be upgraded according to following table:
Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
------  ----------  ----------------------------------------  --------------------  ------------
     1       lcn9k                               $CVER           $NVER           $REQ
    27        nxos                               $CVER           $NVER           $REQ
    27        bios     v07.64(05/16/2018):v07.06(03/02/2014)    v07.65(09/04/2018)           yes
"""

    install_all_disruptive_success = """
Installer will perform compatibility check first. Please wait.
Installer is forced disruptive

Verifying image bootflash:/$IMAGE for boot variable "nxos".
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Preparing "nxos" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Preparing "bios" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Notifying services about system upgrade.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     1       yes      disruptive         reset  default upgrade is not hitless
    27       yes      disruptive         reset  default upgrade is not hitless



Images will be upgraded according to following table:
Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
------  ----------  ----------------------------------------  --------------------  ------------
     1       lcn9k                               $CVER           $NVER           $REQ
    27        nxos                               $CVER           $NVER           $REQ
    27        bios     v07.64(05/16/2018):v07.06(03/02/2014)    v07.65(09/04/2018)           yes


Switch will be reloaded for disruptive upgrade.


Install is in progress, please wait.

Setting boot variables.
[####################] 100% -- SUCCESS

Performing configuration copy.
[####################] 100% -- SUCCESS

Module 1: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 27: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS


Finishing the upgrade, switch will reboot in 10 seconds.
"""

    # Captured output from: install all nxos <image> non-disruptive

    install_all_non_disruptive_success = """
Installer will perform compatibility check first. Please wait.

Verifying image bootflash:/$IMAGE for boot variable "nxos".
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Preparing "nxos" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Preparing "bios" version info using image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Notifying services about system upgrade.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     1       yes  non-disruptive       rolling
    27       yes  non-disruptive         reset



Images will be upgraded according to following table:
Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
------  ----------  ----------------------------------------  --------------------  ------------
     1       lcn9k                               $CVER           $NVER           $REQ
    27        nxos                               $CVER           $NVER           $REQ
    27        bios     v07.65(09/04/2018):v07.06(03/02/2014)    v07.64(05/16/2018)            no


Install is in progress, please wait.

Setting boot variables.
[####################] 100% -- SUCCESS

Performing configuration copy.
[####################] 100% -- SUCCESS

Module 1: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Module 27: Refreshing compact flash and upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS


Starting Standby Container, please wait.
 -- SUCCESS

Notifying services about the switchover.
[####################] 100% -- SUCCESS


"Switching over onto standby".

Non-disruptive upgrading.
[#                   ]   0%
Module 1 upgrade completed successfully.
.

Non-disruptive upgrading.
[####################] 100% -- SUCCESS


Install has been successful.
"""
