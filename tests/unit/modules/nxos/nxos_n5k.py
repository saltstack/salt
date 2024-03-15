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


class N5KPlatform(NXOSPlatform):
    """Cisco Systems N5K Platform Unit Test Object"""

    chassis = "cisco Nexus 5672UP 16G-FC Chassis"

    # Captured output from: show install all impact kickstart <kimage> system <image>

    show_install_all_impact = """
Verifying image bootflash:/$KIMAGE for boot variable "kickstart".
[####################] 100% -- SUCCESS

Verifying image bootflash:/$IMAGE for boot variable "system".
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Extracting "system" version from image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Extracting "kickstart" version from image bootflash:/$KIMAGE.
[####################] 100% -- SUCCESS

Extracting "bios" version from image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Performing module support checks.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     0       yes      disruptive         reset  ISSD is not supported and switch will reset with ascii configuration
     1       yes      disruptive         reset  ISSD is not supported and switch will reset with ascii configuration
     2       yes      disruptive         reset  ISSD is not supported and switch will reset with ascii configuration



Images will be upgraded according to following table:
Module             Image         Running-Version             New-Version  Upg-Required
------  ----------------  ----------------------  ----------------------  ------------
     0            system            $CVER             $NVER           $REQ
     0         kickstart            $CVER             $NVER           $REQ
     0              bios      v0.1.9(03/09/2016)      v0.1.6(12/03/2015)            no
     0         power-seq    SF-uC:37, SF-FPGA:35    SF-uC:37, SF-FPGA:35            no
     0            iofpga               v0.0.0.39               v0.0.0.39            no
     1            iofpga               v0.0.0.18               v0.0.0.18            no
     2            iofpga               v0.0.0.18               v0.0.0.18            no

Warning : ISSD is not supported and switch will reset with ASCII configuration.
All incompatible configuration will be lost in the target release.
Please also refer the downgrade procedure documentation of the release for more details.
    """

    # Captured output from: install all kickstart <kimage> system <image> '''

    install_all_disruptive_success = """
Verifying image bootflash:/$KIMAGE for boot variable "kickstart".
[####################] 100% -- SUCCESS

Verifying image bootflash:/$IMAGE for boot variable "system".
[####################] 100% -- SUCCESS

Verifying image type.
[####################] 100% -- SUCCESS

Extracting "system" version from image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Extracting "kickstart" version from image bootflash:/$KIMAGE.
[####################] 100% -- SUCCESS

Extracting "bios" version from image bootflash:/$IMAGE.
[####################] 100% -- SUCCESS

Performing module support checks.
[####################] 100% -- SUCCESS



Compatibility check is done:
Module  bootable          Impact  Install-type  Reason
------  --------  --------------  ------------  ------
     0       yes      disruptive         reset  ISSD is not supported and switch will reset with ascii configuration
     1       yes      disruptive         reset  ISSD is not supported and switch will reset with ascii configuration
     2       yes      disruptive         reset  ISSD is not supported and switch will reset with ascii configuration



Images will be upgraded according to following table:
Module             Image         Running-Version             New-Version  Upg-Required
------  ----------------  ----------------------  ----------------------  ------------
     0            system            $CVER             $NVER           $REQ
     0         kickstart            $CKVER            $NKVER          $KREQ
     0              bios      v0.1.9(03/09/2016)      v0.1.6(12/03/2015)            no
     0         power-seq    SF-uC:37, SF-FPGA:35    SF-uC:37, SF-FPGA:35            no
     0            iofpga               v0.0.0.39               v0.0.0.39            no
     1            iofpga               v0.0.0.18               v0.0.0.18            no
     2            iofpga               v0.0.0.18               v0.0.0.18            no

Warning : ISSD is not supported and switch will reset with ASCII configuration.
All incompatible configuration will be lost in the target release.
Please also refer the downgrade procedure documentation of the release for more details.

Install is in progress, please wait.

Performing runtime checks.
[####################] 100% -- SUCCESS

Setting boot variables.
[####################] 100% -- SUCCESS

Performing configuration copy.
[####################] 100% -- SUCCESS

Converting startup config.
[####################] 100% -- SUCCESS

Finishing the upgrade, switch will reboot in 10 seconds.
    """
