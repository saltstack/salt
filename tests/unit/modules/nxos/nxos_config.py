template_engine_file_str = "no feature ospf"

config_result = [["no feature ospf"], [{}]]

initial_config = [
    "\n!Command: show running-config\n!Running configuration last done at: Wed Dec  4"
    " 15:33:48 2019\n!Time: Wed Dec  4 15:33:55 2019\n\nversion 9.2(4) Bios:version"
    " 07.66 \nhostname n9k-device\ninstall feature-set fex\nvdc n9k-device id 1\n "
    " allow feature-set fex\n  limit-resource vlan minimum 16 maximum 4094\n "
    " limit-resource vrf minimum 2 maximum 4096\n  limit-resource port-channel minimum"
    " 0 maximum 256\n  limit-resource u4route-mem minimum 248 maximum 248\n "
    " limit-resource u6route-mem minimum 96 maximum 96\n  limit-resource m4route-mem"
    " minimum 58 maximum 58\n  limit-resource m6route-mem minimum 8 maximum"
    " 8\nfeature-set fex\n\nfeature privilege\nfeature telnet\nfeature nxapi\nfeature"
    " bash-shell\ncfs eth distribute\nfeature ngmvpn\nfeature ospf\nfeature"
    " pim\nfeature lldp\n\nusername admin password 5"
    " $5$mOJsBDrL$lhsuyA8VT/fkWM/5XaZcgHlJIYaaS/J5fh8qdDr6fU3  role"
    " network-admin\nusername devops_user password 5 !  role network-operator\nusername"
    " devops_user passphrase  lifetime 99999 warntime 14 gracetime 3\nusername"
    " salt_test password 5 $5$mkXh6O4T$YUVtA89HbXCnue63kgghPlaqPHyaXhdtxPBbPEHhbRC "
    " role network-operator\nusername salt_test passphrase  lifetime 99999 warntime 14"
    " gracetime 3\nip domain-lookup\nip name-server 1.1.1.1 2.2.2.2\nno system default"
    " switchport\nsystem default switchport shutdown\nno logging event link-status"
    " default\nno logging event link-status enable\nno logging event trunk-status"
    " enable\ntime-range ans-range\ntime-range my_range\ncopp profile"
    " strict\nsnmp-server user admin network-admin auth md5"
    " 0xbb62c3df89880933539503f7675e8aa8 priv 0xbb62c3df89880933539503f7675e8aa8"
    " localizedkey\nsnmp-server user devops_user network-operator \nsnmp-server user"
    " salt_test network-operator auth md5 0x3a16a4d0a569be282cc5fbc96138fac8 priv"
    " 0x3a16a4d0a569be282cc5fbc96138fac8 localizedkey\nrmon event 1 description"
    " FATAL(1) owner PMON@FATAL\nrmon event 2 description CRITICAL(2) owner"
    " PMON@CRITICAL\nrmon event 3 description ERROR(3) owner PMON@ERROR\nrmon event 4"
    " description WARNING(4) owner PMON@WARNING\nrmon event 5 description"
    " INFORMATION(5) owner PMON@INFO\nno snmp-server enable traps entity"
    " entity_mib_change\nno snmp-server enable traps entity"
    " entity_module_status_change\nno snmp-server enable traps entity"
    " entity_power_status_change\nno snmp-server enable traps entity"
    " entity_module_inserted\nno snmp-server enable traps entity"
    " entity_module_removed\nno snmp-server enable traps entity"
    " entity_unrecognised_module\nno snmp-server enable traps entity"
    " entity_fan_status_change\nno snmp-server enable traps entity"
    " entity_power_out_change\nno snmp-server enable traps link linkDown\nno"
    " snmp-server enable traps link linkUp\nno snmp-server enable traps link"
    " extended-linkDown\nno snmp-server enable traps link extended-linkUp\nno"
    " snmp-server enable traps link cieLinkDown\nno snmp-server enable traps link"
    " cieLinkUp\nno snmp-server enable traps link delayed-link-state-change\nno"
    " snmp-server enable traps rf redundancy_framework\nno snmp-server enable traps"
    " license notify-license-expiry\nno snmp-server enable traps license"
    " notify-no-license-for-feature\nno snmp-server enable traps license"
    " notify-licensefile-missing\nno snmp-server enable traps license"
    " notify-license-expiry-warning\nno snmp-server enable traps upgrade"
    " UpgradeOpNotifyOnCompletion\nno snmp-server enable traps upgrade"
    " UpgradeJobStatusNotify\nno snmp-server enable traps rmon risingAlarm\nno"
    " snmp-server enable traps rmon fallingAlarm\nno snmp-server enable traps rmon"
    " hcRisingAlarm\nno snmp-server enable traps rmon hcFallingAlarm\nno snmp-server"
    " enable traps entity entity_sensor\nno snmp-server enable traps entity"
    " cefcMIBEnableStatusNotification\nno snmp-server enable traps generic"
    " coldStart\nno snmp-server enable traps generic warmStart\nno snmp-server enable"
    " traps storm-control cpscEventRev1\nno snmp-server enable traps link"
    " cErrDisableInterfaceEventRev1\nno snmp-server enable traps link"
    " cmn-mac-move-notification\nntp server 10.81.254.202 use-vrf management\n\nip pim"
    " ssm range none\nvlan 1\n\nvrf context management\n  ip route 0.0.0.0/0"
    " 192.168.0.1\nvrf context myvrf\nvrf context testing\nnxapi http port 80\nno nxapi"
    " https\nnxapi ssl ciphers weak\nnxapi ssl protocols TLSv1 \n\n\ninterface"
    " port-channel19\n\ninterface port-channel42\n\ninterface"
    " port-channel55\n\ninterface port-channel66\n\ninterface Ethernet1/1\n\ninterface"
    " Ethernet1/2\n\ninterface Ethernet1/3\n  no shutdown\n\ninterface"
    " Ethernet1/4\n\ninterface Ethernet1/5\n\ninterface Ethernet1/6\n\ninterface"
    " Ethernet1/7\n\ninterface Ethernet1/8\n\ninterface Ethernet1/9\n\ninterface"
    " Ethernet1/10\n\ninterface Ethernet1/11\n\ninterface Ethernet1/12\n\ninterface"
    " Ethernet1/13\n\ninterface Ethernet1/14\n\ninterface Ethernet1/15\n\ninterface"
    " Ethernet1/16\n\ninterface Ethernet1/17\n\ninterface Ethernet1/18\n\ninterface"
    " Ethernet1/19\n\ninterface Ethernet1/20\n\ninterface Ethernet1/21\n\ninterface"
    " Ethernet1/22\n\ninterface Ethernet1/23\n\ninterface Ethernet1/24\n\ninterface"
    " Ethernet1/25\n\ninterface Ethernet1/26\n\ninterface Ethernet1/27\n\ninterface"
    " Ethernet1/28\n\ninterface Ethernet1/29\n\ninterface Ethernet1/30\n\ninterface"
    " Ethernet1/31\n\ninterface Ethernet1/32\n\ninterface Ethernet1/33\n\ninterface"
    " Ethernet1/34\n\ninterface Ethernet1/35\n\ninterface Ethernet1/36\n\ninterface"
    " Ethernet1/37\n\ninterface Ethernet1/38\n\ninterface Ethernet1/39\n\ninterface"
    " Ethernet1/40\n\ninterface Ethernet1/41\n\ninterface Ethernet1/42\n\ninterface"
    " Ethernet1/43\n\ninterface Ethernet1/44\n\ninterface Ethernet1/45\n\ninterface"
    " Ethernet1/46\n\ninterface Ethernet1/47\n\ninterface Ethernet1/48\n\ninterface"
    " Ethernet2/1\n\ninterface Ethernet2/2\n\ninterface Ethernet2/3\n\ninterface"
    " Ethernet2/4\n\ninterface Ethernet2/5\n\ninterface Ethernet2/6\n\ninterface"
    " Ethernet2/7\n\ninterface Ethernet2/8\n\ninterface Ethernet2/9\n\ninterface"
    " Ethernet2/10\n\ninterface Ethernet2/11\n\ninterface Ethernet2/12\n\ninterface"
    " mgmt0\n  vrf member management\n  ip address 192.168.0.192/24\n\ninterface"
    " loopback0\n\ninterface loopback1\ncli alias name wr copy running"
    " startup-config\nline console\nline vty\nboot nxos bootflash:/nxos.9.2.4.bin"
    " \n\nno logging logfile\nno logging monitor\nno logging module\nno logging"
    " console\n\n\n"
]

modified_config = [
    "\n!Command: show running-config\n!Running configuration last done at: Wed Dec  4"
    " 15:33:56 2019\n!Time: Wed Dec  4 15:33:56 2019\n\nversion 9.2(4) Bios:version"
    " 07.66 \nhostname n9k-device\ninstall feature-set fex\nvdc n9k-device id 1\n "
    " allow feature-set fex\n  limit-resource vlan minimum 16 maximum 4094\n "
    " limit-resource vrf minimum 2 maximum 4096\n  limit-resource port-channel minimum"
    " 0 maximum 256\n  limit-resource u4route-mem minimum 248 maximum 248\n "
    " limit-resource u6route-mem minimum 96 maximum 96\n  limit-resource m4route-mem"
    " minimum 58 maximum 58\n  limit-resource m6route-mem minimum 8 maximum"
    " 8\nfeature-set fex\n\nfeature privilege\nfeature telnet\nfeature nxapi\nfeature"
    " bash-shell\ncfs eth distribute\nfeature ngmvpn\nfeature pim\nfeature"
    " lldp\n\nusername admin password 5"
    " $5$mOJsBDrL$lhsuyA8VT/fkWM/5XaZcgHlJIYaaS/J5fh8qdDr6fU3  role"
    " network-admin\nusername devops_user password 5 !  role network-operator\nusername"
    " devops_user passphrase  lifetime 99999 warntime 14 gracetime 3\nusername"
    " salt_test password 5 $5$mkXh6O4T$YUVtA89HbXCnue63kgghPlaqPHyaXhdtxPBbPEHhbRC "
    " role network-operator\nusername salt_test passphrase  lifetime 99999 warntime 14"
    " gracetime 3\nip domain-lookup\nip name-server 1.1.1.1 2.2.2.2\nno system default"
    " switchport\nsystem default switchport shutdown\nno logging event link-status"
    " default\nno logging event link-status enable\nno logging event trunk-status"
    " enable\ntime-range ans-range\ntime-range my_range\ncopp profile"
    " strict\nsnmp-server user admin network-admin auth md5"
    " 0xbb62c3df89880933539503f7675e8aa8 priv 0xbb62c3df89880933539503f7675e8aa8"
    " localizedkey\nsnmp-server user devops_user network-operator \nsnmp-server user"
    " salt_test network-operator auth md5 0x3a16a4d0a569be282cc5fbc96138fac8 priv"
    " 0x3a16a4d0a569be282cc5fbc96138fac8 localizedkey\nrmon event 1 description"
    " FATAL(1) owner PMON@FATAL\nrmon event 2 description CRITICAL(2) owner"
    " PMON@CRITICAL\nrmon event 3 description ERROR(3) owner PMON@ERROR\nrmon event 4"
    " description WARNING(4) owner PMON@WARNING\nrmon event 5 description"
    " INFORMATION(5) owner PMON@INFO\nno snmp-server enable traps entity"
    " entity_mib_change\nno snmp-server enable traps entity"
    " entity_module_status_change\nno snmp-server enable traps entity"
    " entity_power_status_change\nno snmp-server enable traps entity"
    " entity_module_inserted\nno snmp-server enable traps entity"
    " entity_module_removed\nno snmp-server enable traps entity"
    " entity_unrecognised_module\nno snmp-server enable traps entity"
    " entity_fan_status_change\nno snmp-server enable traps entity"
    " entity_power_out_change\nno snmp-server enable traps link linkDown\nno"
    " snmp-server enable traps link linkUp\nno snmp-server enable traps link"
    " extended-linkDown\nno snmp-server enable traps link extended-linkUp\nno"
    " snmp-server enable traps link cieLinkDown\nno snmp-server enable traps link"
    " cieLinkUp\nno snmp-server enable traps link delayed-link-state-change\nno"
    " snmp-server enable traps rf redundancy_framework\nno snmp-server enable traps"
    " license notify-license-expiry\nno snmp-server enable traps license"
    " notify-no-license-for-feature\nno snmp-server enable traps license"
    " notify-licensefile-missing\nno snmp-server enable traps license"
    " notify-license-expiry-warning\nno snmp-server enable traps upgrade"
    " UpgradeOpNotifyOnCompletion\nno snmp-server enable traps upgrade"
    " UpgradeJobStatusNotify\nno snmp-server enable traps rmon risingAlarm\nno"
    " snmp-server enable traps rmon fallingAlarm\nno snmp-server enable traps rmon"
    " hcRisingAlarm\nno snmp-server enable traps rmon hcFallingAlarm\nno snmp-server"
    " enable traps entity entity_sensor\nno snmp-server enable traps entity"
    " cefcMIBEnableStatusNotification\nno snmp-server enable traps generic"
    " coldStart\nno snmp-server enable traps generic warmStart\nno snmp-server enable"
    " traps storm-control cpscEventRev1\nno snmp-server enable traps link"
    " cErrDisableInterfaceEventRev1\nno snmp-server enable traps link"
    " cmn-mac-move-notification\nntp server 10.81.254.202 use-vrf management\n\nip pim"
    " ssm range none\nvlan 1\n\nvrf context management\n  ip route 0.0.0.0/0"
    " 192.168.0.1\nvrf context myvrf\nvrf context testing\nnxapi http port 80\nno nxapi"
    " https\nnxapi ssl ciphers weak\nnxapi ssl protocols TLSv1 \n\n\ninterface"
    " port-channel19\n\ninterface port-channel42\n\ninterface"
    " port-channel55\n\ninterface port-channel66\n\ninterface Ethernet1/1\n\ninterface"
    " Ethernet1/2\n\ninterface Ethernet1/3\n  no shutdown\n\ninterface"
    " Ethernet1/4\n\ninterface Ethernet1/5\n\ninterface Ethernet1/6\n\ninterface"
    " Ethernet1/7\n\ninterface Ethernet1/8\n\ninterface Ethernet1/9\n\ninterface"
    " Ethernet1/10\n\ninterface Ethernet1/11\n\ninterface Ethernet1/12\n\ninterface"
    " Ethernet1/13\n\ninterface Ethernet1/14\n\ninterface Ethernet1/15\n\ninterface"
    " Ethernet1/16\n\ninterface Ethernet1/17\n\ninterface Ethernet1/18\n\ninterface"
    " Ethernet1/19\n\ninterface Ethernet1/20\n\ninterface Ethernet1/21\n\ninterface"
    " Ethernet1/22\n\ninterface Ethernet1/23\n\ninterface Ethernet1/24\n\ninterface"
    " Ethernet1/25\n\ninterface Ethernet1/26\n\ninterface Ethernet1/27\n\ninterface"
    " Ethernet1/28\n\ninterface Ethernet1/29\n\ninterface Ethernet1/30\n\ninterface"
    " Ethernet1/31\n\ninterface Ethernet1/32\n\ninterface Ethernet1/33\n\ninterface"
    " Ethernet1/34\n\ninterface Ethernet1/35\n\ninterface Ethernet1/36\n\ninterface"
    " Ethernet1/37\n\ninterface Ethernet1/38\n\ninterface Ethernet1/39\n\ninterface"
    " Ethernet1/40\n\ninterface Ethernet1/41\n\ninterface Ethernet1/42\n\ninterface"
    " Ethernet1/43\n\ninterface Ethernet1/44\n\ninterface Ethernet1/45\n\ninterface"
    " Ethernet1/46\n\ninterface Ethernet1/47\n\ninterface Ethernet1/48\n\ninterface"
    " Ethernet2/1\n\ninterface Ethernet2/2\n\ninterface Ethernet2/3\n\ninterface"
    " Ethernet2/4\n\ninterface Ethernet2/5\n\ninterface Ethernet2/6\n\ninterface"
    " Ethernet2/7\n\ninterface Ethernet2/8\n\ninterface Ethernet2/9\n\ninterface"
    " Ethernet2/10\n\ninterface Ethernet2/11\n\ninterface Ethernet2/12\n\ninterface"
    " mgmt0\n  vrf member management\n  ip address 192.168.0.192/24\n\ninterface"
    " loopback0\n\ninterface loopback1\ncli alias name wr copy running"
    " startup-config\nline console\nline vty\nboot nxos bootflash:/nxos.9.2.4.bin"
    " \n\nno logging logfile\nno logging monitor\nno logging module\nno logging"
    " console\n\n\n"
]

config_input_file = """
feature bgp
!
router bgp 55
  address-family ipv4 unicast
    no client-to-client reflection
    additional-paths send
"""

template_engine_file_str_file = config_input_file

config_result_file = [
    [
        "feature bgp",
        "!",
        "router bgp 55",
        "  address-family ipv4 unicast",
        "    no client-to-client reflection",
        "    additional-paths send",
    ],
    [{}, {}, {}, {}, {}, {}],
]

initial_config_file = [
    "\n!Command: show running-config\n!Running configuration last done at: Wed Dec  4"
    " 15:33:56 2019\n!Time: Wed Dec  4 15:55:51 2019\n\nversion 9.2(4) Bios:version"
    " 07.66 \nhostname dt-n9k5-1\ninstall feature-set fex\nvdc dt-n9k5-1 id 1\n  allow"
    " feature-set fex\n  limit-resource vlan minimum 16 maximum 4094\n  limit-resource"
    " vrf minimum 2 maximum 4096\n  limit-resource port-channel minimum 0 maximum 256\n"
    "  limit-resource u4route-mem minimum 248 maximum 248\n  limit-resource u6route-mem"
    " minimum 96 maximum 96\n  limit-resource m4route-mem minimum 58 maximum 58\n "
    " limit-resource m6route-mem minimum 8 maximum 8\nfeature-set fex\n\nfeature"
    " privilege\nfeature telnet\nfeature nxapi\nfeature bash-shell\ncfs eth"
    " distribute\nfeature ngmvpn\nfeature pim\nfeature lldp\n\nusername admin password"
    " 5 $5$mOJsBDrL$lhsuyA8VT/fkWM/5XaZcgHlJIYaaS/J5fh8qdDr6fU3  role"
    " network-admin\nusername devops_user password 5 !  role network-operator\nusername"
    " devops_user passphrase  lifetime 99999 warntime 14 gracetime 3\nusername"
    " salt_test password 5 $5$mkXh6O4T$YUVtA89HbXCnue63kgghPlaqPHyaXhdtxPBbPEHhbRC "
    " role network-operator\nusername salt_test passphrase  lifetime 99999 warntime 14"
    " gracetime 3\nip domain-lookup\nip name-server 1.1.1.1 2.2.2.2\nno system default"
    " switchport\nsystem default switchport shutdown\nno logging event link-status"
    " default\nno logging event link-status enable\nno logging event trunk-status"
    " enable\ntime-range ans-range\ntime-range my_range\ncopp profile"
    " strict\nsnmp-server user admin network-admin auth md5"
    " 0xbb62c3df89880933539503f7675e8aa8 priv 0xbb62c3df89880933539503f7675e8aa8"
    " localizedkey\nsnmp-server user devops_user network-operator \nsnmp-server user"
    " salt_test network-operator auth md5 0x3a16a4d0a569be282cc5fbc96138fac8 priv"
    " 0x3a16a4d0a569be282cc5fbc96138fac8 localizedkey\nrmon event 1 description"
    " FATAL(1) owner PMON@FATAL\nrmon event 2 description CRITICAL(2) owner"
    " PMON@CRITICAL\nrmon event 3 description ERROR(3) owner PMON@ERROR\nrmon event 4"
    " description WARNING(4) owner PMON@WARNING\nrmon event 5 description"
    " INFORMATION(5) owner PMON@INFO\nno snmp-server enable traps entity"
    " entity_mib_change\nno snmp-server enable traps entity"
    " entity_module_status_change\nno snmp-server enable traps entity"
    " entity_power_status_change\nno snmp-server enable traps entity"
    " entity_module_inserted\nno snmp-server enable traps entity"
    " entity_module_removed\nno snmp-server enable traps entity"
    " entity_unrecognised_module\nno snmp-server enable traps entity"
    " entity_fan_status_change\nno snmp-server enable traps entity"
    " entity_power_out_change\nno snmp-server enable traps link linkDown\nno"
    " snmp-server enable traps link linkUp\nno snmp-server enable traps link"
    " extended-linkDown\nno snmp-server enable traps link extended-linkUp\nno"
    " snmp-server enable traps link cieLinkDown\nno snmp-server enable traps link"
    " cieLinkUp\nno snmp-server enable traps link delayed-link-state-change\nno"
    " snmp-server enable traps rf redundancy_framework\nno snmp-server enable traps"
    " license notify-license-expiry\nno snmp-server enable traps license"
    " notify-no-license-for-feature\nno snmp-server enable traps license"
    " notify-licensefile-missing\nno snmp-server enable traps license"
    " notify-license-expiry-warning\nno snmp-server enable traps upgrade"
    " UpgradeOpNotifyOnCompletion\nno snmp-server enable traps upgrade"
    " UpgradeJobStatusNotify\nno snmp-server enable traps rmon risingAlarm\nno"
    " snmp-server enable traps rmon fallingAlarm\nno snmp-server enable traps rmon"
    " hcRisingAlarm\nno snmp-server enable traps rmon hcFallingAlarm\nno snmp-server"
    " enable traps entity entity_sensor\nno snmp-server enable traps entity"
    " cefcMIBEnableStatusNotification\nno snmp-server enable traps generic"
    " coldStart\nno snmp-server enable traps generic warmStart\nno snmp-server enable"
    " traps storm-control cpscEventRev1\nno snmp-server enable traps link"
    " cErrDisableInterfaceEventRev1\nno snmp-server enable traps link"
    " cmn-mac-move-notification\nntp server 10.81.254.202 use-vrf management\n\nip pim"
    " ssm range none\nvlan 1\n\nvrf context management\n  ip route 0.0.0.0/0"
    " 10.122.197.1\nvrf context myvrf\nvrf context testing\nnxapi http port 80\nno"
    " nxapi https\nnxapi ssl ciphers weak\nnxapi ssl protocols TLSv1 \n\n\ninterface"
    " port-channel19\n\ninterface port-channel42\n\ninterface"
    " port-channel55\n\ninterface port-channel66\n\ninterface Ethernet1/1\n\ninterface"
    " Ethernet1/2\n\ninterface Ethernet1/3\n  no shutdown\n\ninterface"
    " Ethernet1/4\n\ninterface Ethernet1/5\n\ninterface Ethernet1/6\n\ninterface"
    " Ethernet1/7\n\ninterface Ethernet1/8\n\ninterface Ethernet1/9\n\ninterface"
    " Ethernet1/10\n\ninterface Ethernet1/11\n\ninterface Ethernet1/12\n\ninterface"
    " Ethernet1/13\n\ninterface Ethernet1/14\n\ninterface Ethernet1/15\n\ninterface"
    " Ethernet1/16\n\ninterface Ethernet1/17\n\ninterface Ethernet1/18\n\ninterface"
    " Ethernet1/19\n\ninterface Ethernet1/20\n\ninterface Ethernet1/21\n\ninterface"
    " Ethernet1/22\n\ninterface Ethernet1/23\n\ninterface Ethernet1/24\n\ninterface"
    " Ethernet1/25\n\ninterface Ethernet1/26\n\ninterface Ethernet1/27\n\ninterface"
    " Ethernet1/28\n\ninterface Ethernet1/29\n\ninterface Ethernet1/30\n\ninterface"
    " Ethernet1/31\n\ninterface Ethernet1/32\n\ninterface Ethernet1/33\n\ninterface"
    " Ethernet1/34\n\ninterface Ethernet1/35\n\ninterface Ethernet1/36\n\ninterface"
    " Ethernet1/37\n\ninterface Ethernet1/38\n\ninterface Ethernet1/39\n\ninterface"
    " Ethernet1/40\n\ninterface Ethernet1/41\n\ninterface Ethernet1/42\n\ninterface"
    " Ethernet1/43\n\ninterface Ethernet1/44\n\ninterface Ethernet1/45\n\ninterface"
    " Ethernet1/46\n\ninterface Ethernet1/47\n\ninterface Ethernet1/48\n\ninterface"
    " Ethernet2/1\n\ninterface Ethernet2/2\n\ninterface Ethernet2/3\n\ninterface"
    " Ethernet2/4\n\ninterface Ethernet2/5\n\ninterface Ethernet2/6\n\ninterface"
    " Ethernet2/7\n\ninterface Ethernet2/8\n\ninterface Ethernet2/9\n\ninterface"
    " Ethernet2/10\n\ninterface Ethernet2/11\n\ninterface Ethernet2/12\n\ninterface"
    " mgmt0\n  vrf member management\n  ip address 10.122.197.192/24\n\ninterface"
    " loopback0\n\ninterface loopback1\ncli alias name wr copy running"
    " startup-config\nline console\nline vty\nboot nxos bootflash:/nxos.9.2.4.bin"
    " \n\nno logging logfile\nno logging monitor\nno logging module\nno logging"
    " console\n\n\n"
]

modified_config_file = [
    "\n!Command: show running-config\n!Running configuration last done at: Wed Dec  4"
    " 15:55:55 2019\n!Time: Wed Dec  4 15:55:55 2019\n\nversion 9.2(4) Bios:version"
    " 07.66 \nhostname dt-n9k5-1\ninstall feature-set fex\nvdc dt-n9k5-1 id 1\n  allow"
    " feature-set fex\n  limit-resource vlan minimum 16 maximum 4094\n  limit-resource"
    " vrf minimum 2 maximum 4096\n  limit-resource port-channel minimum 0 maximum 256\n"
    "  limit-resource u4route-mem minimum 248 maximum 248\n  limit-resource u6route-mem"
    " minimum 96 maximum 96\n  limit-resource m4route-mem minimum 58 maximum 58\n "
    " limit-resource m6route-mem minimum 8 maximum 8\nfeature-set fex\n\nfeature"
    " privilege\nfeature telnet\nfeature nxapi\nfeature bash-shell\ncfs eth"
    " distribute\nfeature ngmvpn\nfeature bgp\nfeature pim\nfeature lldp\n\nusername"
    " admin password 5 $5$mOJsBDrL$lhsuyA8VT/fkWM/5XaZcgHlJIYaaS/J5fh8qdDr6fU3  role"
    " network-admin\nusername devops_user password 5 !  role network-operator\nusername"
    " devops_user passphrase  lifetime 99999 warntime 14 gracetime 3\nusername"
    " salt_test password 5 $5$mkXh6O4T$YUVtA89HbXCnue63kgghPlaqPHyaXhdtxPBbPEHhbRC "
    " role network-operator\nusername salt_test passphrase  lifetime 99999 warntime 14"
    " gracetime 3\nip domain-lookup\nip name-server 1.1.1.1 2.2.2.2\nno system default"
    " switchport\nsystem default switchport shutdown\nno logging event link-status"
    " default\nno logging event link-status enable\nno logging event trunk-status"
    " enable\ntime-range ans-range\ntime-range my_range\ncopp profile"
    " strict\nsnmp-server user admin network-admin auth md5"
    " 0xbb62c3df89880933539503f7675e8aa8 priv 0xbb62c3df89880933539503f7675e8aa8"
    " localizedkey\nsnmp-server user devops_user network-operator \nsnmp-server user"
    " salt_test network-operator auth md5 0x3a16a4d0a569be282cc5fbc96138fac8 priv"
    " 0x3a16a4d0a569be282cc5fbc96138fac8 localizedkey\nrmon event 1 description"
    " FATAL(1) owner PMON@FATAL\nrmon event 2 description CRITICAL(2) owner"
    " PMON@CRITICAL\nrmon event 3 description ERROR(3) owner PMON@ERROR\nrmon event 4"
    " description WARNING(4) owner PMON@WARNING\nrmon event 5 description"
    " INFORMATION(5) owner PMON@INFO\nno snmp-server enable traps entity"
    " entity_mib_change\nno snmp-server enable traps entity"
    " entity_module_status_change\nno snmp-server enable traps entity"
    " entity_power_status_change\nno snmp-server enable traps entity"
    " entity_module_inserted\nno snmp-server enable traps entity"
    " entity_module_removed\nno snmp-server enable traps entity"
    " entity_unrecognised_module\nno snmp-server enable traps entity"
    " entity_fan_status_change\nno snmp-server enable traps entity"
    " entity_power_out_change\nno snmp-server enable traps link linkDown\nno"
    " snmp-server enable traps link linkUp\nno snmp-server enable traps link"
    " extended-linkDown\nno snmp-server enable traps link extended-linkUp\nno"
    " snmp-server enable traps link cieLinkDown\nno snmp-server enable traps link"
    " cieLinkUp\nno snmp-server enable traps link delayed-link-state-change\nno"
    " snmp-server enable traps rf redundancy_framework\nno snmp-server enable traps"
    " license notify-license-expiry\nno snmp-server enable traps license"
    " notify-no-license-for-feature\nno snmp-server enable traps license"
    " notify-licensefile-missing\nno snmp-server enable traps license"
    " notify-license-expiry-warning\nno snmp-server enable traps upgrade"
    " UpgradeOpNotifyOnCompletion\nno snmp-server enable traps upgrade"
    " UpgradeJobStatusNotify\nno snmp-server enable traps rmon risingAlarm\nno"
    " snmp-server enable traps rmon fallingAlarm\nno snmp-server enable traps rmon"
    " hcRisingAlarm\nno snmp-server enable traps rmon hcFallingAlarm\nno snmp-server"
    " enable traps entity entity_sensor\nno snmp-server enable traps entity"
    " cefcMIBEnableStatusNotification\nno snmp-server enable traps generic"
    " coldStart\nno snmp-server enable traps generic warmStart\nno snmp-server enable"
    " traps storm-control cpscEventRev1\nno snmp-server enable traps link"
    " cErrDisableInterfaceEventRev1\nno snmp-server enable traps link"
    " cmn-mac-move-notification\nntp server 10.81.254.202 use-vrf management\n\nip pim"
    " ssm range none\nvlan 1\n\nvrf context management\n  ip route 0.0.0.0/0"
    " 10.122.197.1\nvrf context myvrf\nvrf context testing\nnxapi http port 80\nno"
    " nxapi https\nnxapi ssl ciphers weak\nnxapi ssl protocols TLSv1 \n\n\ninterface"
    " port-channel19\n\ninterface port-channel42\n\ninterface"
    " port-channel55\n\ninterface port-channel66\n\ninterface Ethernet1/1\n\ninterface"
    " Ethernet1/2\n\ninterface Ethernet1/3\n  no shutdown\n\ninterface"
    " Ethernet1/4\n\ninterface Ethernet1/5\n\ninterface Ethernet1/6\n\ninterface"
    " Ethernet1/7\n\ninterface Ethernet1/8\n\ninterface Ethernet1/9\n\ninterface"
    " Ethernet1/10\n\ninterface Ethernet1/11\n\ninterface Ethernet1/12\n\ninterface"
    " Ethernet1/13\n\ninterface Ethernet1/14\n\ninterface Ethernet1/15\n\ninterface"
    " Ethernet1/16\n\ninterface Ethernet1/17\n\ninterface Ethernet1/18\n\ninterface"
    " Ethernet1/19\n\ninterface Ethernet1/20\n\ninterface Ethernet1/21\n\ninterface"
    " Ethernet1/22\n\ninterface Ethernet1/23\n\ninterface Ethernet1/24\n\ninterface"
    " Ethernet1/25\n\ninterface Ethernet1/26\n\ninterface Ethernet1/27\n\ninterface"
    " Ethernet1/28\n\ninterface Ethernet1/29\n\ninterface Ethernet1/30\n\ninterface"
    " Ethernet1/31\n\ninterface Ethernet1/32\n\ninterface Ethernet1/33\n\ninterface"
    " Ethernet1/34\n\ninterface Ethernet1/35\n\ninterface Ethernet1/36\n\ninterface"
    " Ethernet1/37\n\ninterface Ethernet1/38\n\ninterface Ethernet1/39\n\ninterface"
    " Ethernet1/40\n\ninterface Ethernet1/41\n\ninterface Ethernet1/42\n\ninterface"
    " Ethernet1/43\n\ninterface Ethernet1/44\n\ninterface Ethernet1/45\n\ninterface"
    " Ethernet1/46\n\ninterface Ethernet1/47\n\ninterface Ethernet1/48\n\ninterface"
    " Ethernet2/1\n\ninterface Ethernet2/2\n\ninterface Ethernet2/3\n\ninterface"
    " Ethernet2/4\n\ninterface Ethernet2/5\n\ninterface Ethernet2/6\n\ninterface"
    " Ethernet2/7\n\ninterface Ethernet2/8\n\ninterface Ethernet2/9\n\ninterface"
    " Ethernet2/10\n\ninterface Ethernet2/11\n\ninterface Ethernet2/12\n\ninterface"
    " mgmt0\n  vrf member management\n  ip address 10.122.197.192/24\n\ninterface"
    " loopback0\n\ninterface loopback1\ncli alias name wr copy running"
    " startup-config\nline console\nline vty\nboot nxos bootflash:/nxos.9.2.4.bin"
    " \nrouter bgp 55\n  address-family ipv4 unicast\n    no client-to-client"
    " reflection\n    additional-paths send\n\nno logging logfile\nno logging"
    " monitor\nno logging module\nno logging console\n\n\n"
]

delete_config = """
COMMAND_LIST: no feature bgp

---
+++
@@ -19,7 +19,6 @@
 feature bash-shell
 cfs eth distribute
 feature ngmvpn
-feature bgp
 feature pim
 feature lldp

@@ -234,10 +233,6 @@
 line console
 line vty
 boot nxos bootflash:/nxos.9.2.4.bin
-router bgp 55
-  address-family ipv4 unicast
-    no client-to-client reflection
-    additional-paths send

 no logging logfile
 no logging monitor
 """

remove_user = """
COMMAND_LIST: no username salt_test

---
+++
@@ -25,8 +25,6 @@
 username admin password 5 $5$mOJsBDrL$lhsuyA8VT/fkWM/5XaZcgHlJIYaaS/J5fh8qdDr6fU3  role network-admin
 username devops_user password 5 !  role network-operator
 username devops_user passphrase  lifetime 99999 warntime 14 gracetime 3
-username salt_test password 5 $5$k8DulS4J$GGvG0RPTZdjklgJ4o6X25/AGpEHw1p1Dz8lI0.J77y3  role network-operator
-username salt_test passphrase  lifetime 99999 warntime 14 gracetime 3
 ip domain-lookup
 ip name-server 1.1.1.1 2.2.2.2
 no system default switchport
@@ -39,7 +37,6 @@
 copp profile strict
 snmp-server user admin network-admin auth md5 0xbb62c3df89880933539503f7675e8aa8 priv 0xbb62c3df89880933539503f7675e8aa8 localizedkey
 snmp-server user devops_user network-operator
-snmp-server user salt_test network-operator auth md5 0x6a4237693d3e515b67264a7872476132 priv 0x6a4237693d3e515b67264a7872476132 localizedkey
 rmon event 1 description FATAL(1) owner PMON@FATAL
 rmon event 2 description CRITICAL(2) owner PMON@CRITICAL
 rmon event 3 description ERROR(3) owner PMON@ERROR
 """

save_running_config = """
COMMAND_LIST: copy running-config startup-config

[#                                       ]   1%
[#                                       ]   2%
[##                                      ]   3%
[##                                      ]   4%
[###                                     ]   5%
[###                                     ]   6%
[###                                     ]   7%
[####                                    ]   8%
[####                                    ]   9%
[#####                                   ]  10%
[#####                                   ]  11%
[#####                                   ]  12%
[######                                  ]  13%
[######                                  ]  14%
[#######                                 ]  15%
[#######                                 ]  16%
[#######                                 ]  17%
[########                                ]  18%
[########                                ]  19%
[#########                               ]  20%
[#########                               ]  21%
[#########                               ]  22%
[##########                              ]  23%
[##########                              ]  24%
[###########                             ]  25%
[###########                             ]  26%
[###########                             ]  27%
[############                            ]  28%
[############                            ]  29%
[#############                           ]  30%
[#############                           ]  31%
[#############                           ]  32%
[##############                          ]  33%
[##############                          ]  34%
[###############                         ]  35%
[###############                         ]  36%
[###############                         ]  37%
[################                        ]  38%
[################                        ]  39%
[#################                       ]  40%
[#################                       ]  41%
[#################                       ]  42%
[##################                      ]  43%
[##################                      ]  44%
[###################                     ]  45%
[###################                     ]  46%
[###################                     ]  47%
[####################                    ]  48%
[#####################                   ]  50%
[#####################                   ]  51%
[#####################                   ]  52%
[######################                  ]  53%
[######################                  ]  54%
[#######################                 ]  55%
[#######################                 ]  56%
[#######################                 ]  57%
[########################                ]  58%
[########################                ]  59%
[#########################               ]  60%
[#########################               ]  61%
[#########################               ]  62%
[##########################              ]  63%
[##########################              ]  64%
[###########################             ]  65%
[###########################             ]  66%
[###########################             ]  67%
[############################            ]  68%
[############################            ]  69%
[#############################           ]  70%
[#############################           ]  71%
[#############################           ]  72%
[##############################          ]  73%
[##############################          ]  74%
[###############################         ]  75%
[###############################         ]  76%
[###############################         ]  77%
[################################        ]  78%
[################################        ]  79%
[#################################       ]  80%
[#################################       ]  81%
[#################################       ]  82%
[##################################      ]  83%
[##################################      ]  84%
[###################################     ]  85%
[###################################     ]  86%
[###################################     ]  87%
[####################################    ]  88%
[####################################    ]  89%
[#####################################   ]  90%
[#####################################   ]  91%
[#####################################   ]  92%
[######################################  ]  93%
[######################################  ]  94%
[####################################### ]  95%
[####################################### ]  96%
[####################################### ]  97%
[########################################]  98%
[########################################] 100%
Copy complete, now saving to disk (please wait)...
Copy complete.
"""

set_role = """
COMMAND_LIST: username salt_test role vdc-admin
warning: password for user:salt_test not set. S/he may not be able to login

---
+++
@@ -26,6 +26,8 @@
 username admin password 5 $5$mOJsBDrL$lhsuyA8VT/fkWM/5XaZcgHlJIYaaS/J5fh8qdDr6fU3  role network-admin
 username devops_user password 5 !  role network-operator
 username devops_user passphrase  lifetime 99999 warntime 14 gracetime 3
+username salt_test password 5 !  role vdc-admin
+username salt_test passphrase  lifetime 99999 warntime 14 gracetime 3
 ip domain-lookup
 ip name-server 1.1.1.1 2.2.2.2
 no system default switchport
@@ -38,6 +40,7 @@
 copp profile strict
 snmp-server user admin network-admin auth md5 0xbb62c3df89880933539503f7675e8aa8 priv 0xbb62c3df89880933539503f7675e8aa8 localizedkey
 snmp-server user devops_user network-operator
+snmp-server user salt_test vdc-admin
 rmon event 1 description FATAL(1) owner PMON@FATAL
 rmon event 2 description CRITICAL(2) owner PMON@CRITICAL
 rmon event 3 description ERROR(3) owner PMON@ERROR
"""

unset_role = """
COMMAND_LIST: no username salt_test role vdc-admin

---
+++
@@ -26,8 +26,7 @@
 username admin password 5 $5$mOJsBDrL$lhsuyA8VT/fkWM/5XaZcgHlJIYaaS/J5fh8qdDr6fU3  role network-admin
 username ansible password 5 !  role network-operator
 username ansible passphrase  lifetime 99999 warntime 14 gracetime 3
-username salt_test password 5 !  role vdc-admin
-username salt_test role network-operator
+username salt_test password 5 !  role network-operator
 username salt_test passphrase  lifetime 99999 warntime 14 gracetime 3
 ip domain-lookup
 ip name-server 1.1.1.1 2.2.2.2
@@ -41,8 +40,7 @@
 copp profile strict
 snmp-server user admin network-admin auth md5 0xbb62c3df89880933539503f7675e8aa8 priv 0xbb62c3df89880933539503f7675e8aa8 localizedkey
 snmp-server user ansible network-operator
-snmp-server user salt_test vdc-admin
-snmp-server user salt_test network-operator
+snmp-server user salt_test network-operator
 rmon event 1 description FATAL(1) owner PMON@FATAL
 rmon event 2 description CRITICAL(2) owner PMON@CRITICAL
 rmon event 3 description ERROR(3) owner PMON@ERROR
"""
