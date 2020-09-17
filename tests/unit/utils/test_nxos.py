# -*- coding: utf-8 -*-
"""
    :codeauthor: Praveen Ramoorthy<@praveenramoorthy>
"""

# Copyright (c) 2019 Cisco and/or its affiliates.
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


# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.exceptions
import salt.utils.nxos as nxos_utils
import salt.utils.pycrypto
from salt.exceptions import (
    CommandExecutionError, 
    NxosError, 
    NxosRequestNotSupported,
)

# Import Salt Testing Libs
from tests.support.mock import MagicMock, create_autospec, patch
from tests.support.unit import TestCase

RESPONSE_NO_DICT = {
   "ins_api":{
      "sid":"eoc",
      "type":"cli_show_ascii",
      "version":"1.0",
      "outputs":{
         "output":{
            "body":"Cisco Nexus Operating System (NX-OS) Software\nTAC support: http://www.cisco.com/tac\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\nAll rights reserved.\nThe copyrights to certain works contained in this software are\nowned by other third parties and used and distributed under their own\nlicenses, such as open source.  This software is provided \"as is,\" and unless\notherwise stated, there is no warranty, express or implied, including but not\nlimited to warranties of merchantability and fitness for a particular purpose.\nCertain components of this software are licensed under\nthe GNU General Public License (GPL) version 2.0 or \nGNU General Public License (GPL) version 3.0  or the GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser General Public License (LGPL) Version 2.0. \nA copy of each such license is available at\nhttp://www.opensource.org/licenses/gpl-2.0.php and\nhttp://opensource.org/licenses/gpl-3.0.html and\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n\nSoftware\n  BIOS: version 07.67\n NXOS: version 9.3(5)\n  BIOS compile time:  01/29/2020\n  NXOS image file is: bootflash:///nxos.9.3.5.bin\n  NXOS compile time:  7/20/2020 20:00:00 [07/21/2020 06:30:11]\n\n\nHardware\n  cisco Nexus9000 93180YC-EX chassis \n  Intel(R) Xeon(R) CPU  @ 1.80GHz with 24631956 kB of memory.\n  Processor Board ID FDO21392QKM\n\n  Device name: n9k-140\n  bootflash:   53298520 kB\nKernel uptime is 32 day(s), 4 hour(s), 10 minute(s), 27 second(s)\n\nLast reset at 294975 usecs after Mon Aug 10 07:33:01 2020\n  Reason: Reset Requested by CLI command reload\n  System version: 7.0(3)I7(9)\n  Service: \n\nplugin\n  Core Plugin, Ethernet Plugin\n\nActive Package(s):\n        nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\n        \n",
            "code":"200",
            "msg":"Success",
            "input":"show version"
         }
      }
   }
}


RESULT_NO_DICT = ['Cisco Nexus Operating System (NX-OS) Software\nTAC support: http://www.cisco.com/tac\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\nAll rights reserved.\nThe copyrights to certain works contained in this software are\nowned by other third parties and used and distributed under their own\nlicenses, such as open source.  This software is provided "as is," and unless\notherwise stated, there is no warranty, express or implied, including but not\nlimited to warranties of merchantability and fitness for a particular purpose.\nCertain components of this software are licensed under\nthe GNU General Public License (GPL) version 2.0 or \nGNU General Public License (GPL) version 3.0  or the GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser General Public License (LGPL) Version 2.0. \nA copy of each such license is available at\nhttp://www.opensource.org/licenses/gpl-2.0.php and\nhttp://opensource.org/licenses/gpl-3.0.html and\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n\nSoftware\n  BIOS: version 07.67\n NXOS: version 9.3(5)\n  BIOS compile time:  01/29/2020\n  NXOS image file is: bootflash:///nxos.9.3.5.bin\n  NXOS compile time:  7/20/2020 20:00:00 [07/21/2020 06:30:11]\n\n\nHardware\n  cisco Nexus9000 93180YC-EX chassis \n  Intel(R) Xeon(R) CPU  @ 1.80GHz with 24631956 kB of memory.\n  Processor Board ID FDO21392QKM\n\n  Device name: n9k-140\n  bootflash:   53298520 kB\nKernel uptime is 32 day(s), 4 hour(s), 10 minute(s), 27 second(s)\n\nLast reset at 294975 usecs after Mon Aug 10 07:33:01 2020\n  Reason: Reset Requested by CLI command reload\n  System version: 7.0(3)I7(9)\n  Service: \n\nplugin\n  Core Plugin, Ethernet Plugin\n\nActive Package(s):\n        nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\n        \n']


RESPONSE_DICT = {
   "body":"{\n\t\"ins_api\":\t{\n\t\t\"sid\":\t\"eoc\",\n\t\t\"type\":\t\"cli_show_ascii\",\n\t\t\"version\":\t\"1.0\",\n\t\t\"outputs\":\t{\n\t\t\t\"output\":\t{\n\t\t\t\t\"body\":\t\"Cisco Nexus Operating System (NX-OS) Software\\nTAC support: http://www.cisco.com/tac\\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\\nAll rights reserved.\\nThe copyrights to certain works contained in this software are\\nowned by other third parties and used and distributed under their own\\nlicenses, such as open source.  This software is provided \\\"as is,\\\" and unless\\notherwise stated, there is no warranty, express or implied, including but not\\nlimited to warranties of merchantability and fitness for a particular purpose.\\nCertain components of this software are licensed under\\nthe GNU General Public License (GPL) version 2.0 or \\nGNU General Public License (GPL) version 3.0  or the GNU\\nLesser General Public License (LGPL) Version 2.1 or \\nLesser General Public License (LGPL) Version 2.0. \\nA copy of each such license is available at\\nhttp://www.opensource.org/licenses/gpl-2.0.php and\\nhttp://opensource.org/licenses/gpl-3.0.html and\\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\\n\\nSoftware\\n  BIOS: version 07.67\\n NXOS: version 9.3(5)\\n  BIOS compile time:  01/29/2020\\n  NXOS image file is: bootflash:///nxos.9.3.5.bin\\n  NXOS compile time:  7/20/2020 20:00:00 [07/21/2020 06:30:11]\\n\\n\\nHardware\\n  cisco Nexus9000 93180YC-EX chassis \\n  Intel(R) Xeon(R) CPU  @ 1.80GHz with 24631956 kB of memory.\\n  Processor Board ID FDO21392QKM\\n\\n  Device name: n9k-140\\n  bootflash:   53298520 kB\\nKernel uptime is 37 day(s), 0 hour(s), 4 minute(s), 11 second(s)\\n\\nLast reset at 294975 usecs after Mon Aug 10 07:33:01 2020\\n  Reason: Reset Requested by CLI command reload\\n  System version: 7.0(3)I7(9)\\n  Service: \\n\\nplugin\\n  Core Plugin, Ethernet Plugin\\n\\nActive Package(s):\\n        nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\\n        \\n\",\n\t\t\t\t\"code\":\t\"200\",\n\t\t\t\t\"msg\":\t\"Success\",\n\t\t\t\t\"input\":\t\"show version\"\n\t\t\t}\n\t\t}\n\t}\n}",
   "dict":{
      "ins_api":{
         "sid":"eoc",
         "type":"cli_show_ascii",
         "version":"1.0",
         "outputs":{
            "output":{
               "body":"Cisco Nexus Operating System (NX-OS) Software\nTAC support: http://www.cisco.com/tac\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\nAll rights reserved.\nThe copyrights to certain works contained in this software are\nowned by other third parties and used and distributed under their own\nlicenses, such as open source.  This software is provided \"as is,\" and unless\notherwise stated, there is no warranty, express or implied, including but not\nlimited to warranties of merchantability and fitness for a particular purpose.\nCertain components of this software are licensed under\nthe GNU General Public License (GPL) version 2.0 or \nGNU General Public License (GPL) version 3.0  or the GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser General Public License (LGPL) Version 2.0. \nA copy of each such license is available at\nhttp://www.opensource.org/licenses/gpl-2.0.php and\nhttp://opensource.org/licenses/gpl-3.0.html and\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n\nSoftware\n  BIOS: version 07.67\n NXOS: version 9.3(5)\n  BIOS compile time:  01/29/2020\n  NXOS image file is: bootflash:///nxos.9.3.5.bin\n  NXOS compile time:  7/20/2020 20:00:00 [07/21/2020 06:30:11]\n\n\nHardware\n  cisco Nexus9000 93180YC-EX chassis \n  Intel(R) Xeon(R) CPU  @ 1.80GHz with 24631956 kB of memory.\n  Processor Board ID FDO21392QKM\n\n  Device name: n9k-140\n  bootflash:   53298520 kB\nKernel uptime is 37 day(s), 0 hour(s), 4 minute(s), 11 second(s)\n\nLast reset at 294975 usecs after Mon Aug 10 07:33:01 2020\n  Reason: Reset Requested by CLI command reload\n  System version: 7.0(3)I7(9)\n  Service: \n\nplugin\n  Core Plugin, Ethernet Plugin\n\nActive Package(s):\n        nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\n        \n",
               "code":"200",
               "msg":"Success",
               "input":"show version"
            }
         }
      }
   }
}


RESULT_DICT = ['Cisco Nexus Operating System (NX-OS) Software\nTAC support: http://www.cisco.com/tac\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\nAll rights reserved.\nThe copyrights to certain works contained in this software are\nowned by other third parties and used and distributed under their own\nlicenses, such as open source.  This software is provided "as is," and unless\notherwise stated, there is no warranty, express or implied, including but not\nlimited to warranties of merchantability and fitness for a particular purpose.\nCertain components of this software are licensed under\nthe GNU General Public License (GPL) version 2.0 or \nGNU General Public License (GPL) version 3.0  or the GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser General Public License (LGPL) Version 2.0. \nA copy of each such license is available at\nhttp://www.opensource.org/licenses/gpl-2.0.php and\nhttp://opensource.org/licenses/gpl-3.0.html and\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n\nSoftware\n  BIOS: version 07.67\n NXOS: version 9.3(5)\n  BIOS compile time:  01/29/2020\n  NXOS image file is: bootflash:///nxos.9.3.5.bin\n  NXOS compile time:  7/20/2020 20:00:00 [07/21/2020 06:30:11]\n\n\nHardware\n  cisco Nexus9000 93180YC-EX chassis \n  Intel(R) Xeon(R) CPU  @ 1.80GHz with 24631956 kB of memory.\n  Processor Board ID FDO21392QKM\n\n  Device name: n9k-140\n  bootflash:   53298520 kB\nKernel uptime is 37 day(s), 0 hour(s), 4 minute(s), 11 second(s)\n\nLast reset at 294975 usecs after Mon Aug 10 07:33:01 2020\n  Reason: Reset Requested by CLI command reload\n  System version: 7.0(3)I7(9)\n  Service: \n\nplugin\n  Core Plugin, Ethernet Plugin\n\nActive Package(s):\n        nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\n        \n']


RESPONSE_DICT_1 = {
   "body":"{\n\t\"ins_api\":\t{\n\t\t\"type\":\t\"cli_show\",\n\t\t\"version\":\t\"1.0\",\n\t\t\"sid\":\t\"eoc\",\n\t\t\"outputs\":\t{\n\t\t\t\"output\":\t{\n\t\t\t\t\"input\":\t\"show ver\",\n\t\t\t\t\"msg\":\t\"Success\",\n\t\t\t\t\"code\":\t\"200\",\n\t\t\t\t\"body\":\t{\n\t\t\t\t\t\"header_str\":\t\"Cisco Nexus Operating System (NX-OS) Software\\nTAC support: http://www.cisco.com/tac\\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\\nAll rights reserved.\\nThe copyrights to certain works contained in this software are\\nowned by other third parties and used and distributed under their own\\nlicenses, such as open source.  This software is provided \\\"as is,\\\" and unless\\notherwise stated, there is no warranty, express or implied, including but not\\nlimited to warranties of merchantability and fitness for a particular purpose.\\nCertain components of this software are licensed under\\nthe GNU General Public License (GPL) version 2.0 or \\nGNU General Public License (GPL) version 3.0  or the GNU\\nLesser General Public License (LGPL) Version 2.1 or \\nLesser General Public License (LGPL) Version 2.0. \\nA copy of each such license is available at\\nhttp://www.opensource.org/licenses/gpl-2.0.php and\\nhttp://opensource.org/licenses/gpl-3.0.html and\\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\\n\",\n\t\t\t\t\t\"bios_ver_str\":\t\"07.67\",\n\t\t\t\t\t\"kickstart_ver_str\":\t\"9.3(5)\",\n\t\t\t\t\t\"nxos_ver_str\":\t\"9.3(5)\",\n\t\t\t\t\t\"bios_cmpl_time\":\t\"01/29/2020\",\n\t\t\t\t\t\"kick_file_name\":\t\"bootflash:///nxos.9.3.5.bin\",\n\t\t\t\t\t\"nxos_file_name\":\t\"bootflash:///nxos.9.3.5.bin\",\n\t\t\t\t\t\"kick_cmpl_time\":\t\"7/20/2020 20:00:00\",\n\t\t\t\t\t\"nxos_cmpl_time\":\t\"7/20/2020 20:00:00\",\n\t\t\t\t\t\"kick_tmstmp\":\t\"07/21/2020 06:30:11\",\n\t\t\t\t\t\"nxos_tmstmp\":\t\"07/21/2020 06:30:11\",\n\t\t\t\t\t\"chassis_id\":\t\"Nexus9000 93180YC-EX chassis\",\n\t\t\t\t\t\"cpu_name\":\t\"Intel(R) Xeon(R) CPU  @ 1.80GHz\",\n\t\t\t\t\t\"memory\":\t24631956,\n\t\t\t\t\t\"mem_type\":\t\"kB\",\n\t\t\t\t\t\"proc_board_id\":\t\"FDO21392QKM\",\n\t\t\t\t\t\"host_name\":\t\"n9k-140\",\n\t\t\t\t\t\"bootflash_size\":\t53298520,\n\t\t\t\t\t\"kern_uptm_days\":\t37,\n\t\t\t\t\t\"kern_uptm_hrs\":\t0,\n\t\t\t\t\t\"kern_uptm_mins\":\t21,\n\t\t\t\t\t\"kern_uptm_secs\":\t46,\n\t\t\t\t\t\"rr_usecs\":\t294975,\n\t\t\t\t\t\"rr_ctime\":\t\"Mon Aug 10 07:33:01 2020\",\n\t\t\t\t\t\"rr_reason\":\t\"Reset Requested by CLI command reload\",\n\t\t\t\t\t\"rr_sys_ver\":\t\"7.0(3)I7(9)\",\n\t\t\t\t\t\"rr_service\":\t\"\",\n\t\t\t\t\t\"plugins\":\t\"Core Plugin, Ethernet Plugin\",\n\t\t\t\t\t\"manufacturer\":\t\"Cisco Systems, Inc.\",\n\t\t\t\t\t\"TABLE_package_list\":\t{\n\t\t\t\t\t\t\"ROW_package_list\":\t{\n\t\t\t\t\t\t\t\"package_id\":\t\"\"\n\t\t\t\t\t\t}\n\t\t\t\t\t},\n\t\t\t\t\t\"TABLE_smu_list\":\t{\n\t\t\t\t\t\t\"ROW_smu_list\":\t{\n\t\t\t\t\t\t\t\"install_smu_id\":\t\"nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\\n\"\n\t\t\t\t\t\t}\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}",
   "dict":{
      "ins_api":{
         "type":"cli_show",
         "version":"1.0",
         "sid":"eoc",
         "outputs":{
            "output":{
               "input":"show ver",
               "msg":"Success",
               "code":"200",
               "body":{
                  "header_str":"Cisco Nexus Operating System (NX-OS) Software\nTAC support: http://www.cisco.com/tac\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\nAll rights reserved.\nThe copyrights to certain works contained in this software are\nowned by other third parties and used and distributed under their own\nlicenses, such as open source.  This software is provided \"as is,\" and unless\notherwise stated, there is no warranty, express or implied, including but not\nlimited to warranties of merchantability and fitness for a particular purpose.\nCertain components of this software are licensed under\nthe GNU General Public License (GPL) version 2.0 or \nGNU General Public License (GPL) version 3.0  or the GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser General Public License (LGPL) Version 2.0. \nA copy of each such license is available at\nhttp://www.opensource.org/licenses/gpl-2.0.php and\nhttp://opensource.org/licenses/gpl-3.0.html and\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n",
                  "bios_ver_str":"07.67",
                  "kickstart_ver_str":"9.3(5)",
                  "nxos_ver_str":"9.3(5)",
                  "bios_cmpl_time":"01/29/2020",
                  "kick_file_name":"bootflash:///nxos.9.3.5.bin",
                  "nxos_file_name":"bootflash:///nxos.9.3.5.bin",
                  "kick_cmpl_time":"7/20/2020 20:00:00",
                  "nxos_cmpl_time":"7/20/2020 20:00:00",
                  "kick_tmstmp":"07/21/2020 06:30:11",
                  "nxos_tmstmp":"07/21/2020 06:30:11",
                  "chassis_id":"Nexus9000 93180YC-EX chassis",
                  "cpu_name":"Intel(R) Xeon(R) CPU  @ 1.80GHz",
                  "memory":24631956,
                  "mem_type":"kB",
                  "proc_board_id":"FDO21392QKM",
                  "host_name":"n9k-140",
                  "bootflash_size":53298520,
                  "kern_uptm_days":37,
                  "kern_uptm_hrs":0,
                  "kern_uptm_mins":21,
                  "kern_uptm_secs":46,
                  "rr_usecs":294975,
                  "rr_ctime":"Mon Aug 10 07:33:01 2020",
                  "rr_reason":"Reset Requested by CLI command reload",
                  "rr_sys_ver":"7.0(3)I7(9)",
                  "rr_service":"",
                  "plugins":"Core Plugin, Ethernet Plugin",
                  "manufacturer":"Cisco Systems, Inc.",
                  "TABLE_package_list":{
                     "ROW_package_list":{
                        "package_id":""
                     }
                  },
                  "TABLE_smu_list":{
                     "ROW_smu_list":{
                        "install_smu_id":"nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\n"
                     }
                  }
               }
            }
         }
      }
   }
}


RESULT_DICT_1 = [{'header_str': 'Cisco Nexus Operating System (NX-OS) Software\nTAC support: http://www.cisco.com/tac\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\nAll rights reserved.\nThe copyrights to certain works contained in this software are\nowned by other third parties and used and distributed under their own\nlicenses, such as open source.  This software is provided "as is," and unless\notherwise stated, there is no warranty, express or implied, including but not\nlimited to warranties of merchantability and fitness for a particular purpose.\nCertain components of this software are licensed under\nthe GNU General Public License (GPL) version 2.0 or \nGNU General Public License (GPL) version 3.0  or the GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser General Public License (LGPL) Version 2.0. \nA copy of each such license is available at\nhttp://www.opensource.org/licenses/gpl-2.0.php and\nhttp://opensource.org/licenses/gpl-3.0.html and\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n', 'bios_ver_str': '07.67', 'kickstart_ver_str': '9.3(5)', 'nxos_ver_str': '9.3(5)', 'bios_cmpl_time': '01/29/2020', 'kick_file_name': 'bootflash:///nxos.9.3.5.bin', 'nxos_file_name': 'bootflash:///nxos.9.3.5.bin', 'kick_cmpl_time': '7/20/2020 20:00:00', 'nxos_cmpl_time': '7/20/2020 20:00:00', 'kick_tmstmp': '07/21/2020 06:30:11', 'nxos_tmstmp': '07/21/2020 06:30:11', 'chassis_id': 'Nexus9000 93180YC-EX chassis', 'cpu_name': 'Intel(R) Xeon(R) CPU  @ 1.80GHz', 'memory': 24631956, 'mem_type': 'kB', 'proc_board_id': 'FDO21392QKM', 'host_name': 'n9k-140', 'bootflash_size': 53298520, 'kern_uptm_days': 37, 'kern_uptm_hrs': 0, 'kern_uptm_mins': 21, 'kern_uptm_secs': 46, 'rr_usecs': 294975, 'rr_ctime': 'Mon Aug 10 07:33:01 2020', 'rr_reason': 'Reset Requested by CLI command reload', 'rr_sys_ver': '7.0(3)I7(9)', 'rr_service': '', 'plugins': 'Core Plugin, Ethernet Plugin', 'manufacturer': 'Cisco Systems, Inc.', 'TABLE_package_list': {'ROW_package_list': {'package_id': ''}}, 'TABLE_smu_list': {'ROW_smu_list': {'install_smu_id': 'nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\n'}}}]


RESPONSE_400 = {
   "body":"{\n\t\"ins_api\":\t{\n\t\t\"sid\":\t\"eoc\",\n\t\t\"type\":\t\"cli_show_ascii\",\n\t\t\"version\":\t\"1.0\",\n\t\t\"outputs\":\t{\n\t\t\t\"output\":\t{\n\t\t\t\t\"code\":\t\"400\",\n\t\t\t\t\"msg\":\t\"Input CLI command error\",\n\t\t\t\t\"clierror\":\t\"% Invalid command\\n\",\n\t\t\t\t\"input\":\t\"show version | show module\"\n\t\t\t}\n\t\t}\n\t}\n}",
   "dict":{
      "ins_api":{
         "sid":"eoc",
         "type":"cli_show_ascii",
         "version":"1.0",
         "outputs":{
            "output":{
               "code":"400",
               "msg":"Input CLI command error",
               "clierror":"% Invalid command\n",
               "input":"show version | show module"
            }
         }
      }
   }
}

RESPONSE_413 = {
   "body":"{\n\t\"ins_api\":\t{\n\t\t\"type\":\t\"cli_show\",\n\t\t\"version\":\t\"1.0\",\n\t\t\"sid\":\t\"eoc\",\n\t\t\"outputs\":\t{\n\t\t\t\"output\":\t{\n\t\t\t\t\"clierror\":\t\"\",\n\t\t\t\t\"input\":\t\"show version | show module\",\n\t\t\t\t\"msg\":\t\"Pipe is not allowed for this message type\",\n\t\t\t\t\"code\":\t\"501\"\n\t\t\t}\n\t\t}\n\t}\n}",
   "dict":{
      "ins_api":{
         "type":"cli_show",
         "version":"1.0",
         "sid":"eoc",
         "outputs":{
            "output":{
               "clierror":"",
               "input":"show version | show module",
               "msg":"Response size too big",
               "code":"413"
            }
         }
      }
   }
}


RESPONSE_501 = {
   "body":"{\n\t\"ins_api\":\t{\n\t\t\"type\":\t\"cli_show\",\n\t\t\"version\":\t\"1.0\",\n\t\t\"sid\":\t\"eoc\",\n\t\t\"outputs\":\t{\n\t\t\t\"output\":\t{\n\t\t\t\t\"clierror\":\t\"\",\n\t\t\t\t\"input\":\t\"show version | show module\",\n\t\t\t\t\"msg\":\t\"Pipe is not allowed for this message type\",\n\t\t\t\t\"code\":\t\"501\"\n\t\t\t}\n\t\t}\n\t}\n}",
   "dict":{
      "ins_api":{
         "type":"cli_show",
         "version":"1.0",
         "sid":"eoc",
         "outputs":{
            "output":{
               "clierror":"",
               "input":"show version | show module",
               "msg":"Pipe is not allowed for this message type",
               "code":"501"
            }
         }
      }
   }
}


RESPONSE_ERROR = {
   "inst_api":{
      "sid":"eoc",
      "type":"cli_show_ascii",
      "version":"1.0",
      "outputs":{
         "output":{
            "body":"Cisco Nexus Operating System (NX-OS) Software\nTAC support: http://www.cisco.com/tac\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\nAll rights reserved.\nThe copyrights to certain works contained in this software are\nowned by other third parties and used and distributed under their own\nlicenses, such as open source.  This software is provided \"as is,\" and unless\notherwise stated, there is no warranty, express or implied, including but not\nlimited to warranties of merchantability and fitness for a particular purpose.\nCertain components of this software are licensed under\nthe GNU General Public License (GPL) version 2.0 or \nGNU General Public License (GPL) version 3.0  or the GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser General Public License (LGPL) Version 2.0. \nA copy of each such license is available at\nhttp://www.opensource.org/licenses/gpl-2.0.php and\nhttp://opensource.org/licenses/gpl-3.0.html and\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n\nSoftware\n  BIOS: version 07.67\n NXOS: version 9.3(5)\n  BIOS compile time:  01/29/2020\n  NXOS image file is: bootflash:///nxos.9.3.5.bin\n  NXOS compile time:  7/20/2020 20:00:00 [07/21/2020 06:30:11]\n\n\nHardware\n  cisco Nexus9000 93180YC-EX chassis \n  Intel(R) Xeon(R) CPU  @ 1.80GHz with 24631956 kB of memory.\n  Processor Board ID FDO21392QKM\n\n  Device name: n9k-140\n  bootflash:   53298520 kB\nKernel uptime is 32 day(s), 2 hour(s), 15 minute(s), 46 second(s)\n\nLast reset at 294975 usecs after Mon Aug 10 07:33:01 2020\n  Reason: Reset Requested by CLI command reload\n  System version: 7.0(3)I7(9)\n  Service: \n\nplugin\n  Core Plugin, Ethernet Plugin\n\nActive Package(s):\n        nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\n        \n",
            "code":"200",
            "msg":"Success",
            "input":"show version"
         }
      }
   }
} 


RESPONSE_MULTI = {
   "body":"{\n\t\"ins_api\":\t{\n\t\t\"sid\":\t\"eoc\",\n\t\t\"type\":\t\"cli_show_ascii\",\n\t\t\"version\":\t\"1.0\",\n\t\t\"outputs\":\t{\n\t\t\t\"output\":\t[{\n\t\t\t\t\t\"body\":\t\"Cisco Nexus Operating System (NX-OS) Software\\nTAC support: http://www.cisco.com/tac\\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\\nAll rights reserved.\\nThe copyrights to certain works contained in this software are\\nowned by other third parties and used and distributed under their own\\nlicenses, such as open source.  This software is provided \\\"as is,\\\" and unless\\notherwise stated, there is no warranty, express or implied, including but not\\nlimited to warranties of merchantability and fitness for a particular purpose.\\nCertain components of this software are licensed under\\nthe GNU General Public License (GPL) version 2.0 or \\nGNU General Public License (GPL) version 3.0  or the GNU\\nLesser General Public License (LGPL) Version 2.1 or \\nLesser General Public License (LGPL) Version 2.0. \\nA copy of each such license is available at\\nhttp://www.opensource.org/licenses/gpl-2.0.php and\\nhttp://opensource.org/licenses/gpl-3.0.html and\\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\\n\\nSoftware\\n  BIOS: version 07.67\\n NXOS: version 9.3(5)\\n  BIOS compile time:  01/29/2020\\n  NXOS image file is: bootflash:///nxos.9.3.5.bin\\n  NXOS compile time:  7/20/2020 20:00:00 [07/21/2020 06:30:11]\\n\\n\\nHardware\\n  cisco Nexus9000 93180YC-EX chassis \\n  Intel(R) Xeon(R) CPU  @ 1.80GHz with 24631956 kB of memory.\\n  Processor Board ID FDO21392QKM\\n\\n  Device name: n9k-140\\n  bootflash:   53298520 kB\\nKernel uptime is 38 day(s), 6 hour(s), 57 minute(s), 22 second(s)\\n\\nLast reset at 294975 usecs after Mon Aug 10 07:33:01 2020\\n  Reason: Reset Requested by CLI command reload\\n  System version: 7.0(3)I7(9)\\n  Service: \\n\\nplugin\\n  Core Plugin, Ethernet Plugin\\n\\nActive Package(s):\\n nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\\n \\n\",\n\t\t\t\t\t\"code\":\t\"200\",\n\t\t\t\t\t\"msg\":\t\"Success\",\n\t\t\t\t\t\"input\":\t\"show version\"\n\t\t\t\t}, {\n\t\t\t\t\t\"body\":\t\"Mod Ports             Module-Type                      Model           Status\\n--- ----- ------------------------------------- --------------------- ---------\\n1    54   48x10/25G + 6x40/100G Ethernet Module N9K-C93180YC-EX       active *  \\n\\nMod  Sw                       Hw    Slot\\n---  ----------------------- ------ ----\\n1    9.3(5)                   3.0    NA  \\n\\n\\nMod  MAC-Address(es)                         Serial-Num\\n---  --------------------------------------  ----------\\n1    6c-b2-ae-84-b6-70 to 6c-b2-ae-84-b6-bf  FDO21392QKM\\n\\nMod  Online Diag Status\\n---  ------------------\\n1    Pass\\n\\n* this terminal session \\n\",\n\t\t\t\t\t\"code\":\t\"200\",\n\t\t\t\t\t\"msg\":\t\"Success\",\n\t\t\t\t\t\"input\":\t\" show module\"\n\t\t\t\t}]\n\t\t}\n\t}\n}",
   "dict":{
      "ins_api":{
         "sid":"eoc",
         "type":"cli_show_ascii",
         "version":"1.0",
         "outputs":{
            "output":[
               {
                  "body":"Cisco Nexus Operating System (NX-OS) Software\nTAC support: http://www.cisco.com/tac\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\nAll rights reserved.\nThe copyrights to certain works contained in this software are\nowned by other third parties and used and distributed under their own\nlicenses, such as open source.  This software is provided \"as is,\" and unless\notherwise stated, there is no warranty, express or implied, including but not\nlimited to warranties of merchantability and fitness for a particular purpose.\nCertain components of this software are licensed under\nthe GNU General Public License (GPL) version 2.0 or \nGNU General Public License (GPL) version 3.0  or the GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser General Public License (LGPL) Version 2.0. \nA copy of each such license is available at\nhttp://www.opensource.org/licenses/gpl-2.0.php and\nhttp://opensource.org/licenses/gpl-3.0.html and\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n\nSoftware\n  BIOS: version 07.67\n NXOS: version 9.3(5)\n  BIOS compile time:  01/29/2020\n  NXOS image file is: bootflash:///nxos.9.3.5.bin\n  NXOS compile time:  7/20/2020 20:00:00 [07/21/2020 06:30:11]\n\n\nHardware\n  cisco Nexus9000 93180YC-EX chassis \n  Intel(R) Xeon(R) CPU  @ 1.80GHz with 24631956 kB of memory.\n  Processor Board ID FDO21392QKM\n\n  Device name: n9k-140\n  bootflash:   53298520 kB\nKernel uptime is 38 day(s), 6 hour(s), 57 minute(s), 22 second(s)\n\nLast reset at 294975 usecs after Mon Aug 10 07:33:01 2020\n  Reason: Reset Requested by CLI command reload\n  System version: 7.0(3)I7(9)\n  Service: \n\nplugin\n  Core Plugin, Ethernet Plugin\n\nActive Package(s):\n nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\n \n",
                  "code":"200",
                  "msg":"Success",
                  "input":"show version"
               },
               {
                  "body":"Mod Ports             Module-Type                      Model           Status\n--- ----- ------------------------------------- --------------------- ---------\n1    54   48x10/25G + 6x40/100G Ethernet Module N9K-C93180YC-EX       active *  \n\nMod  Sw                       Hw    Slot\n---  ----------------------- ------ ----\n1    9.3(5)                   3.0    NA  \n\n\nMod  MAC-Address(es)                         Serial-Num\n---  --------------------------------------  ----------\n1    6c-b2-ae-84-b6-70 to 6c-b2-ae-84-b6-bf  FDO21392QKM\n\nMod  Online Diag Status\n---  ------------------\n1    Pass\n\n* this terminal session \n",
                  "code":"200",
                  "msg":"Success",
                  "input":" show module"
               }
            ]
         }
      }
   }
}


RESULT_MULTI = ['Cisco Nexus Operating System (NX-OS) Software\nTAC support: http://www.cisco.com/tac\nCopyright (C) 2002-2020, Cisco and/or its affiliates.\nAll rights reserved.\nThe copyrights to certain works contained in this software are\nowned by other third parties and used and distributed under their own\nlicenses, such as open source.  This software is provided "as is," and unless\notherwise stated, there is no warranty, express or implied, including but not\nlimited to warranties of merchantability and fitness for a particular purpose.\nCertain components of this software are licensed under\nthe GNU General Public License (GPL) version 2.0 or \nGNU General Public License (GPL) version 3.0  or the GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser General Public License (LGPL) Version 2.0. \nA copy of each such license is available at\nhttp://www.opensource.org/licenses/gpl-2.0.php and\nhttp://opensource.org/licenses/gpl-3.0.html and\nhttp://www.opensource.org/licenses/lgpl-2.1.php and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n\nSoftware\n  BIOS: version 07.67\n NXOS: version 9.3(5)\n  BIOS compile time:  01/29/2020\n  NXOS image file is: bootflash:///nxos.9.3.5.bin\n  NXOS compile time:  7/20/2020 20:00:00 [07/21/2020 06:30:11]\n\n\nHardware\n  cisco Nexus9000 93180YC-EX chassis \n  Intel(R) Xeon(R) CPU  @ 1.80GHz with 24631956 kB of memory.\n  Processor Board ID FDO21392QKM\n\n  Device name: n9k-140\n  bootflash:   53298520 kB\nKernel uptime is 38 day(s), 6 hour(s), 57 minute(s), 22 second(s)\n\nLast reset at 294975 usecs after Mon Aug 10 07:33:01 2020\n  Reason: Reset Requested by CLI command reload\n  System version: 7.0(3)I7(9)\n  Service: \n\nplugin\n  Core Plugin, Ethernet Plugin\n\nActive Package(s):\n nxos.CSCvv25573-n9k_ALL-1.0.0-9.3.5.lib32_n9000\n \n', 'Mod Ports             Module-Type                      Model           Status\n--- ----- ------------------------------------- --------------------- ---------\n1    54   48x10/25G + 6x40/100G Ethernet Module N9K-C93180YC-EX       active *  \n\nMod  Sw                       Hw    Slot\n---  ----------------------- ------ ----\n1    9.3(5)                   3.0    NA  \n\n\nMod  MAC-Address(es)                         Serial-Num\n---  --------------------------------------  ----------\n1    6c-b2-ae-84-b6-70 to 6c-b2-ae-84-b6-bf  FDO21392QKM\n\nMod  Online Diag Status\n---  ------------------\n1    Pass\n\n* this terminal session \n']


class NxosTestCase(TestCase):
    def test_show_nxapi_response_no_dict(self):
        command_list = "show version"

        #with patch.object(nxos_utils.NxapiClient, "__init__", lambda a='b': None):
        with patch.object(nxos_utils.NxapiClient, "__init__", lambda a: None):
           result = nxos_utils.NxapiClient().parse_response(RESPONSE_NO_DICT,  command_list)
        self.assertEqual(result, RESULT_NO_DICT)

    def test_show_nxapi_response_dict(self):
        command_list = "show version"

        with patch.object(nxos_utils.NxapiClient, "__init__", lambda a: None):
           result = nxos_utils.NxapiClient().parse_response(RESPONSE_DICT,  command_list)
        self.assertEqual(result, RESULT_DICT)

    def test_show_nxapi_response_dict_1(self):
        command_list = "show version"

        with patch.object(nxos_utils.NxapiClient, "__init__", lambda a: None):
           result = nxos_utils.NxapiClient().parse_response(RESPONSE_DICT_1,  command_list)
        self.assertEqual(result, RESULT_DICT_1)

    def test_show_nxapi_response_dict_multi(self):
        command_list = ['show version', 'show module']

        with patch.object(nxos_utils.NxapiClient, "__init__", lambda a: None):
           result = nxos_utils.NxapiClient().parse_response(RESPONSE_MULTI,  command_list)
        self.assertEqual(result, RESULT_MULTI)

    def test_show_nxapi_response_error_400(self):
        command_list = "show version | show module"

        with patch.object(nxos_utils.NxapiClient, "__init__", lambda a: None):
            with self.assertRaises(CommandExecutionError):
                result = nxos_utils.NxapiClient().parse_response(RESPONSE_400,  command_list)

    def test_show_nxapi_response_error_413(self):
        command_list = "show version | show module"

        with patch.object(nxos_utils.NxapiClient, "__init__", lambda a: None):
            with self.assertRaises(NxosRequestNotSupported):
                result = nxos_utils.NxapiClient().parse_response(RESPONSE_413,  command_list)

    def test_show_nxapi_response_error_501(self):
        command_list = "show version | show module"

        with patch.object(nxos_utils.NxapiClient, "__init__", lambda a: None):
            with self.assertRaises(NxosError):
                result = nxos_utils.NxapiClient().parse_response(RESPONSE_501,  command_list)

    def test_show_nxapi_response_error(self):
        command_list = "show version"

        with patch.object(nxos_utils.NxapiClient, "__init__", lambda a: None):
            with self.assertRaises(NxosError):
                result = nxos_utils.NxapiClient().parse_response(RESPONSE_ERROR,  command_list)
