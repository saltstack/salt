n9k_show_ver = """
Cisco Nexus Operating System (NX-OS) Software
TAC support: http://www.cisco.com/tac
Copyright (C) 2002-2018, Cisco and/or its affiliates.
All rights reserved.
The copyrights to certain works contained in this software are
owned by other third parties and used and distributed under their own
licenses, such as open source.  This software is provided "as is," and unless
otherwise stated, there is no warranty, express or implied, including but not
limited to warranties of merchantability and fitness for a particular purpose.
Certain components of this software are licensed under
the GNU General Public License (GPL) version 2.0 or
GNU General Public License (GPL) version 3.0  or the GNU
Lesser General Public License (LGPL) Version 2.1 or
Lesser General Public License (LGPL) Version 2.0.
A copy of each such license is available at
http://www.opensource.org/licenses/gpl-2.0.php and
http://opensource.org/licenses/gpl-3.0.html and
http://www.opensource.org/licenses/lgpl-2.1.php and
http://www.gnu.org/licenses/old-licenses/library.txt.

Software
  BIOS: version 08.36
  NXOS: version 9.2(1)
  BIOS compile time:  06/07/2019
  NXOS image file is: bootflash:///nxos.9.2.1.bin
  NXOS compile time:  7/17/2018 16:00:00 [07/18/2018 00:21:19]


Hardware
  cisco Nexus9000 C9504 (4 Slot) Chassis ("Supervisor Module")
  Intel(R) Xeon(R) CPU E5-2403 0 @ 1.80GHz with 16400084 kB of memory.
  Processor Board ID SAL1909A7VC

  Device name: n9k-device
  bootflash:   53298520 kB
Kernel uptime is 0 day(s), 18 hour(s), 26 minute(s), 18 second(s)

Last reset at 931765 usecs after Mon Dec  2 01:21:36 2019
  Reason: Reset Requested by CLI command reload
  System version: 9.2(4)
  Service:

plugin
  Core Plugin, Ethernet Plugin

Active Package(s):
"""

n9k_show_ver_structured = [
    {
        "header_str": (
            "Cisco Nexus Operating System (NX-OS) Software\nTAC support:"
            " http://www.cisco.com/tac\nCopyright (C) 2002-2019, Cisco and/or its"
            " affiliates.\nAll rights reserved.\nThe copyrights to certain works"
            " contained in this software are\nowned by other third parties and used and"
            " distributed under their own\nlicenses, such as open source.  This"
            ' software is provided "as is," and unless\notherwise stated, there is no'
            " warranty, express or implied, including but not\nlimited to warranties of"
            " merchantability and fitness for a particular purpose.\nCertain components"
            " of this software are licensed under\nthe GNU General Public License (GPL)"
            " version 2.0 or \nGNU General Public License (GPL) version 3.0  or the"
            " GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser General"
            " Public License (LGPL) Version 2.0. \nA copy of each such license is"
            " available at\nhttp://www.opensource.org/licenses/gpl-2.0.php"
            " and\nhttp://opensource.org/licenses/gpl-3.0.html"
            " and\nhttp://www.opensource.org/licenses/lgpl-2.1.php"
            " and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n"
        ),
        "bios_ver_str": "07.66",
        "kickstart_ver_str": "7.0(3)I7(8) [build 7.0(3)I7(7.16)]",
        "bios_cmpl_time": "06/12/2019",
        "kick_file_name": "bootflash:///nxos.7.0.3.I7.7.16.bin",
        "kick_cmpl_time": " 11/29/2019 13:00:00",
        "kick_tmstmp": "11/29/2019 21:52:12",
        "chassis_id": "Nexus9000 C9396PX Chassis",
        "cpu_name": "Intel(R) Core(TM) i3- CPU @ 2.50GHz",
        "memory": 16401088,
        "mem_type": "kB",
        "proc_board_id": "SAL1821T9EF",
        "host_name": "dt-n9k5-1",
        "bootflash_size": 21693714,
        "kern_uptm_days": 1,
        "kern_uptm_hrs": 23,
        "kern_uptm_mins": 32,
        "kern_uptm_secs": 47,
        "rr_usecs": 915186,
        "rr_ctime": "Sun Dec  1 15:47:17 2019",
        "rr_reason": "Reset Requested by CLI command reload",
        "rr_sys_ver": "9.2(4)",
        "rr_service": "",
        "manufacturer": "Cisco Systems, Inc.",
        "TABLE_package_list": {"ROW_package_list": {"package_id": {}}},
    }
]

# Data returned from nxapi for raw text is in list form.
n9k_show_ver_list = [
    "Cisco Nexus Operating System (NX-OS) Software\nTAC support:"
    " http://www.cisco.com/tac\nCopyright (C) 2002-2019, Cisco and/or its"
    " affiliates.\nAll rights reserved.\nThe copyrights to certain works contained in"
    " this software are\nowned by other third parties and used and distributed under"
    ' their own\nlicenses, such as open source.  This software is provided "as is," and'
    " unless\notherwise stated, there is no warranty, express or implied, including but"
    " not\nlimited to warranties of merchantability and fitness for a particular"
    " purpose.\nCertain components of this software are licensed under\nthe GNU General"
    " Public License (GPL) version 2.0 or \nGNU General Public License (GPL) version"
    " 3.0  or the GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser"
    " General Public License (LGPL) Version 2.0. \nA copy of each such license is"
    " available at\nhttp://www.opensource.org/licenses/gpl-2.0.php"
    " and\nhttp://opensource.org/licenses/gpl-3.0.html"
    " and\nhttp://www.opensource.org/licenses/lgpl-2.1.php"
    " and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n\nSoftware\n  BIOS:"
    " version 07.66\n  NXOS: version 7.0(3)I7(8) [build 7.0(3)I7(7.16)]\n  BIOS compile"
    " time:  06/12/2019\n  NXOS image file is: bootflash:///nxos.7.0.3.I7.7.16.bin\n "
    " NXOS compile time:  11/29/2019 13:00:00 [11/29/2019 21:52:12]\n\n\nHardware\n "
    " cisco Nexus9000 C9396PX Chassis \n  Intel(R) Core(TM) i3- CPU @ 2.50GHz with"
    " 16401088 kB of memory.\n  Processor Board ID SAL1821T9EF\n\n  Device name:"
    " n9k-device\n  bootflash:   21693714 kB\nKernel uptime is 1 day(s), 22 hour(s), 54"
    " minute(s), 13 second(s)\n\nLast reset at 915186 usecs after Sun Dec  1 15:47:17"
    " 2019\n  Reason: Reset Requested by CLI command reload\n  System version: 9.2(4)\n"
    "  Service: \n\nplugin\n  Core Plugin, Ethernet Plugin\n\nActive Package(s):\n \n"
]

n9k_show_user_account = """
user:salt_test
        this user account has no expiry date
        roles:network-operator network-admin dev-ops
"""

n9k_show_user_account_list = [
    "user:salt_test\n        this user account has no expiry date\n       "
    " roles:network-operator dev-ops network-admin \n"
]

n9k_show_ver_int_list = [
    "Cisco Nexus Operating System (NX-OS) Software\nTAC support:"
    " http://www.cisco.com/tac\nCopyright (C) 2002-2019, Cisco and/or its"
    " affiliates.\nAll rights reserved.\nThe copyrights to certain works contained in"
    " this software are\nowned by other third parties and used and distributed under"
    ' their own\nlicenses, such as open source.  This software is provided "as is," and'
    " unless\notherwise stated, there is no warranty, express or implied, including but"
    " not\nlimited to warranties of merchantability and fitness for a particular"
    " purpose.\nCertain components of this software are licensed under\nthe GNU General"
    " Public License (GPL) version 2.0 or \nGNU General Public License (GPL) version"
    " 3.0  or the GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser"
    " General Public License (LGPL) Version 2.0. \nA copy of each such license is"
    " available at\nhttp://www.opensource.org/licenses/gpl-2.0.php"
    " and\nhttp://opensource.org/licenses/gpl-3.0.html"
    " and\nhttp://www.opensource.org/licenses/lgpl-2.1.php"
    " and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n\nSoftware\n  BIOS:"
    " version 07.66\n  NXOS: version 7.0(3)I7(8) [build 7.0(3)I7(7.16)]\n  BIOS compile"
    " time:  06/12/2019\n  NXOS image file is: bootflash:///nxos.7.0.3.I7.7.16.bin\n "
    " NXOS compile time:  11/29/2019 13:00:00 [11/29/2019 21:52:12]\n\n\nHardware\n "
    " cisco Nexus9000 C9396PX Chassis \n  Intel(R) Core(TM) i3- CPU @ 2.50GHz with"
    " 16401088 kB of memory.\n  Processor Board ID SAL1821T9EF\n\n  Device name:"
    " n9k-device\n  bootflash:   21693714 kB\nKernel uptime is 1 day(s), 23 hour(s), 24"
    " minute(s), 35 second(s)\n\nLast reset at 915186 usecs after Sun Dec  1 15:47:17"
    " 2019\n  Reason: Reset Requested by CLI command reload\n  System version: 9.2(4)\n"
    "  Service: \n\nplugin\n  Core Plugin, Ethernet Plugin\n\nActive Package(s):\n \n",
    "Ethernet1/1 is down (XCVR not inserted)\nadmin state is down, Dedicated"
    " Interface\n  Hardware: 1000/10000 Ethernet, address: 88f0.31dc.7de6 (bia"
    " 88f0.31dc.7de6)\n  MTU 1500 bytes, BW 10000000 Kbit, DLY 10 usec\n  reliability"
    " 255/255, txload 1/255, rxload 1/255\n  Encapsulation ARPA, medium is broadcast\n "
    " Port mode is trunk\n  auto-duplex, auto-speed\n  Beacon is turned off\n "
    " Auto-Negotiation is turned on  FEC mode is Auto\n  Input flow-control is off,"
    " output flow-control is off\n  Auto-mdix is turned off\n  Switchport monitor is"
    " off \n  EtherType is 0x8100 \n  EEE (efficient-ethernet) : n/a\n    admin fec"
    " state is auto, oper fec state is off\n  Last link flapped never\n  Last clearing"
    ' of "show interface" counters 1d21h\n  0 interface resets\n  Load-Interval #1: 30'
    " seconds\n    30 seconds input rate 0 bits/sec, 0 packets/sec\n    30 seconds"
    " output rate 0 bits/sec, 0 packets/sec\n    input rate 0 bps, 0 pps; output rate 0"
    " bps, 0 pps\n  Load-Interval #2: 5 minute (300 seconds)\n    300 seconds input"
    " rate 0 bits/sec, 0 packets/sec\n    300 seconds output rate 0 bits/sec, 0"
    " packets/sec\n    input rate 0 bps, 0 pps; output rate 0 bps, 0 pps\n  RX\n    0"
    " unicast packets  0 multicast packets  0 broadcast packets\n    0 input packets  0"
    " bytes\n    0 jumbo packets  0 storm suppression packets\n    0 runts  0 giants  0"
    " CRC  0 no buffer\n    0 input error  0 short frame  0 overrun   0 underrun  0"
    " ignored\n    0 watchdog  0 bad etype drop  0 bad proto drop  0 if down drop\n   "
    " 0 input with dribble  0 input discard\n    0 Rx pause\n  TX\n    0 unicast"
    " packets  0 multicast packets  0 broadcast packets\n    0 output packets  0"
    " bytes\n    0 jumbo packets\n    0 output error  0 collision  0 deferred  0 late"
    " collision\n    0 lost carrier  0 no carrier  0 babble  0 output discard\n    0 Tx"
    " pause\n\n",
]

n9k_show_ver_int_list_structured = [
    {
        "header_str": (
            "Cisco Nexus Operating System (NX-OS) Software\nTAC support:"
            " http://www.cisco.com/tac\nCopyright (C) 2002-2019, Cisco and/or its"
            " affiliates.\nAll rights reserved.\nThe copyrights to certain works"
            " contained in this software are\nowned by other third parties and used and"
            " distributed under their own\nlicenses, such as open source.  This"
            ' software is provided "as is," and unless\notherwise stated, there is no'
            " warranty, express or implied, including but not\nlimited to warranties of"
            " merchantability and fitness for a particular purpose.\nCertain components"
            " of this software are licensed under\nthe GNU General Public License (GPL)"
            " version 2.0 or \nGNU General Public License (GPL) version 3.0  or the"
            " GNU\nLesser General Public License (LGPL) Version 2.1 or \nLesser General"
            " Public License (LGPL) Version 2.0. \nA copy of each such license is"
            " available at\nhttp://www.opensource.org/licenses/gpl-2.0.php"
            " and\nhttp://opensource.org/licenses/gpl-3.0.html"
            " and\nhttp://www.opensource.org/licenses/lgpl-2.1.php"
            " and\nhttp://www.gnu.org/licenses/old-licenses/library.txt.\n"
        ),
        "bios_ver_str": "07.66",
        "kickstart_ver_str": "7.0(3)I7(8) [build 7.0(3)I7(7.16)]",
        "bios_cmpl_time": "06/12/2019",
        "kick_file_name": "bootflash:///nxos.7.0.3.I7.7.16.bin",
        "kick_cmpl_time": " 11/29/2019 13:00:00",
        "kick_tmstmp": "11/29/2019 21:52:12",
        "chassis_id": "Nexus9000 C9396PX Chassis",
        "cpu_name": "Intel(R) Core(TM) i3- CPU @ 2.50GHz",
        "memory": 16401088,
        "mem_type": "kB",
        "proc_board_id": "SAL1821T9EF",
        "host_name": "n9k-device",
        "bootflash_size": 21693714,
        "kern_uptm_days": 1,
        "kern_uptm_hrs": 23,
        "kern_uptm_mins": 31,
        "kern_uptm_secs": 18,
        "rr_usecs": 915186,
        "rr_ctime": "Sun Dec  1 15:47:17 2019",
        "rr_reason": "Reset Requested by CLI command reload",
        "rr_sys_ver": "9.2(4)",
        "rr_service": "",
        "manufacturer": "Cisco Systems, Inc.",
        "TABLE_package_list": {"ROW_package_list": {"package_id": {}}},
    },
    {
        "TABLE_interface": {
            "ROW_interface": {
                "interface": "Ethernet1/1",
                "state": "down",
                "state_rsn_desc": "XCVR not inserted",
                "admin_state": "down",
                "share_state": "Dedicated",
                "eth_hw_desc": "1000/10000 Ethernet",
                "eth_hw_addr": "88f0.31dc.7de6",
                "eth_bia_addr": "88f0.31dc.7de6",
                "eth_mtu": "1500",
                "eth_bw": 10000000,
                "eth_dly": 10,
                "eth_reliability": "255",
                "eth_txload": "1",
                "eth_rxload": "1",
                "medium": "broadcast",
                "eth_mode": "trunk",
                "eth_duplex": "auto",
                "eth_speed": "auto-speed",
                "eth_beacon": "off",
                "eth_autoneg": "on",
                "eth_in_flowctrl": "off",
                "eth_out_flowctrl": "off",
                "eth_mdix": "off",
                "eth_swt_monitor": "off",
                "eth_ethertype": "0x8100",
                "eth_eee_state": "n/a",
                "eth_admin_fec_state": "auto",
                "eth_oper_fec_state": "off",
                "eth_link_flapped": "never",
                "eth_clear_counters": "1d21h",
                "eth_reset_cntr": 0,
                "eth_load_interval1_rx": 30,
                "eth_inrate1_bits": "0",
                "eth_inrate1_pkts": "0",
                "eth_load_interval1_tx": "30",
                "eth_outrate1_bits": "0",
                "eth_outrate1_pkts": "0",
                "eth_inrate1_summary_bits": "0 bps",
                "eth_inrate1_summary_pkts": "0 pps",
                "eth_outrate1_summary_bits": "0 bps",
                "eth_outrate1_summary_pkts": "0 pps",
                "eth_load_interval2_rx": "300",
                "eth_inrate2_bits": "0",
                "eth_inrate2_pkts": "0",
                "eth_load_interval2_tx": "300",
                "eth_outrate2_bits": "0",
                "eth_outrate2_pkts": "0",
                "eth_inrate2_summary_bits": "0 bps",
                "eth_inrate2_summary_pkts": "0 pps",
                "eth_outrate2_summary_bits": "0 bps",
                "eth_outrate2_summary_pkts": "0 pps",
                "eth_inucast": 0,
                "eth_inmcast": 0,
                "eth_inbcast": 0,
                "eth_inpkts": 0,
                "eth_inbytes": 0,
                "eth_jumbo_inpkts": "0",
                "eth_storm_supp": "0",
                "eth_runts": 0,
                "eth_giants": 0,
                "eth_crc": "0",
                "eth_nobuf": 0,
                "eth_inerr": "0",
                "eth_frame": "0",
                "eth_overrun": "0",
                "eth_underrun": "0",
                "eth_ignored": "0",
                "eth_watchdog": "0",
                "eth_bad_eth": "0",
                "eth_bad_proto": "0",
                "eth_in_ifdown_drops": "0",
                "eth_dribble": "0",
                "eth_indiscard": "0",
                "eth_inpause": "0",
                "eth_outucast": 0,
                "eth_outmcast": 0,
                "eth_outbcast": 0,
                "eth_outpkts": 0,
                "eth_outbytes": 0,
                "eth_jumbo_outpkts": "0",
                "eth_outerr": "0",
                "eth_coll": "0",
                "eth_deferred": "0",
                "eth_latecoll": "0",
                "eth_lostcarrier": "0",
                "eth_nocarrier": "0",
                "eth_babbles": "0",
                "eth_outdiscard": "0",
                "eth_outpause": "0",
            }
        }
    },
]

n9k_get_user_output = (
    "username salt_test password 5"
    " $5$mkXh6O4T$YUVtA89HbXCnue63kgghPlaqPHyaXhdtxPBbPEHhbRC  role network-operator"
)
