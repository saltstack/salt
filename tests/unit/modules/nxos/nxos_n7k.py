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


class N7KPlatform(NXOSPlatform):
    """Cisco Systems N7K Platform Unit Test Object"""

    chassis = "Nexus7000 C7010 (10 Slot) Chassis"

    # Captured output from: show install all impact kickstart <kimage> system <image>

    show_install_all_impact = """
Installer will perform impact only check. Please wait.

Verifying image bootflash:/$KIMAGE for boot variable "kickstart".
[####################] 100% -- SUCCESS

Verifying image bootflash:/$IMAGE for boot variable "system".
[####################] 100% -- SUCCESS

Performing module support checks.
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Extracting "system" version from image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Extracting "kickstart" version from image bootflash:/$KIMAGE.
[####################] 100% -- SUCCESS

Extracting "bios" version from image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Extracting "lc1n7k" version from image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Notifying services about system upgrade.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     2       yes      disruptive         reset  Incompatible image
     3       yes      disruptive         reset  Incompatible image



Images will be upgraded according to following table:
Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
------  ----------  ----------------------------------------  --------------------  ------------
     2      system                               $CVER                $NVER           $REQ
     2   kickstart                               $CKVER               $NKVER          $KREQ
     2        bios   v2.12.0(05/29/2013):v2.12.0(05/29/2013)   v2.13.0(10/23/2018)           yes
     3      lc1n7k                               8.3(0)SK(1)                8.3(2)           yes
     3        bios     v1.10.21(11/26/12):v1.10.21(11/26/12)    v1.10.21(11/26/12)            no
"""

    # Captured output from: install all kickstart <kimage> system <image>

    install_all_disruptive_success = """
Installer will perform compatibility check first. Please wait.

Verifying image bootflash:/$KIMAGE for boot variable "kickstart".
[####################] 100% -- SUCCESS

Verifying image bootflash:/$IMAGE for boot variable "system".
[####################] 100% -- SUCCESS

Performing module support checks.
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Extracting "system" version from image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Extracting "kickstart" version from image bootflash:/$KIMAGE.
[####################] 100% -- SUCCESS

Extracting "bios" version from image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Notifying services about system upgrade.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     5       yes      disruptive         reset  Reset due to single supervisor



Images will be upgraded according to following table:
Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
------  ----------  ----------------------------------------  --------------------  ------------
     5      system                               $CVER                 $NVER           $REQ
     5   kickstart                               $CKVER                $NKVER          $KREQ
     5        bios   v2.12.0(05/29/2013):v2.12.0(05/29/2013)   v2.13.0(10/23/2018)           yes


Install is in progress, please wait.

Performing runtime checks.
[####################] 100% -- SUCCESS

Setting boot variables.
[####################] 100% -- SUCCESS

Performing configuration copy.
[####################] 100% -- SUCCESS

Module 5:  Upgrading bios/loader/bootrom.
Warning: please do not remove or power off the module at this time.
[####################] 100% -- SUCCESS

Finishing the upgrade, switch will reboot in 10 seconds.
"""
