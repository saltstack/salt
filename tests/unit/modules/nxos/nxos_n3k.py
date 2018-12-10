# -*- coding: utf-8 -*-
'''
    :codeauthor: Thomas Stoner <tmstoner@cisco.com>
'''

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


from __future__ import absolute_import
from tests.unit.modules.nxos.nxos_platform import NXOSPlatform


class N3KPlatform(NXOSPlatform):

    """ Cisco Systems N3K Platform Unit Test Object """

    chassis = "Nexus 3172 Chassis"

    # Captured output from: show install all impact nxos <image>

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
     1        nxos                                    $CVER                $NVER           $REQ
     1        bios     v01.11(03/06/2018):v01.08(08/22/2017)    v01.13(09/27/2018)           yes
    """

    # Captured output from: show install impact nxos <image>

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
     1        nxos                                    $CVER                $NVER           $REQ
     1        bios     v01.11(03/06/2018):v01.08(08/22/2017)    v01.13(09/27/2018)           yes



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


Finishing the upgrade, switch will reboot in 10 seconds.
    """
