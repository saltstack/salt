n9k_running_config = """
!Command: show running-config
!Running configuration last done at: Wed Nov 27 18:54:15 2019
!Time: Wed Nov 27 20:21:59 2019

version 9.2(4) Bios:version 07.66
hostname n9k-salt-switch
vdc n9k-salt-switch id 1
  limit-resource vlan minimum 16 maximum 4094
  limit-resource vrf minimum 2 maximum 4096
  limit-resource port-channel minimum 0 maximum 256
  limit-resource u4route-mem minimum 248 maximum 248
  limit-resource u6route-mem minimum 96 maximum 96
  limit-resource m4route-mem minimum 58 maximum 58
  limit-resource m6route-mem minimum 8 maximum 8

feature privilege
feature telnet
feature nxapi
feature bash-shell
cfs eth distribute
feature bgp
feature lldp

username devops password 5 $5$cG3ULyiY$xywJrS7bVTLV2FJy32eA3mVyixfiMqXl5GvnyHMX6Y5  role network-admin
username devops shelltype bash
username devops passphrase  lifetime 99999 warntime 14 gracetime 3
username salt_test password 5 $5$bMOnjQ.w$6ROSiY7Ic7dvfC4jXvQazDrXUH/Cneci371BLC6a.ZD  role network-admin
username salt_test role dev-ops
username salt_test passphrase  lifetime 99999 warntime 14 gracetime 3
username salt_test_2 password 5 $5$jWfBfcJv$LvtViMNcz34fzhD7nfroUa2NPcNbOacLh.WkBXgXocB  role network-operator
username salt_test_2 passphrase  lifetime 99999 warntime 14 gracetime 3
ip domain-lookup
ip name-server 1.1.1.1 2.2.2.2
no system default switchport
system default switchport shutdown
no logging event link-status default
no logging event link-status enable
no logging event trunk-status enable
time-range ans-range
copp profile strict
snmp-server user devops network-admin auth md5 0xbb62c3df89880933539503f7675e8aa8 priv 0xbb62c3df89880933539503f7675e8aa8 localizedkey
snmp-server user salt_test network-admin auth md5 0x3a16a4d0a569be282cc5fbc96138fac8 priv 0x3a16a4d0a569be282cc5fbc96138fac8 localizedkey
rmon event 1 description FATAL(1) owner PMON@FATAL
rmon event 2 description CRITICAL(2) owner PMON@CRITICAL
rmon event 3 description ERROR(3) owner PMON@ERROR
rmon event 4 description WARNING(4) owner PMON@WARNING
rmon event 5 description INFORMATION(5) owner PMON@INFO
no snmp-server enable traps entity entity_mib_change
no snmp-server enable traps entity entity_module_status_change
no snmp-server enable traps entity entity_power_status_change
no snmp-server enable traps entity entity_module_inserted
no snmp-server enable traps entity entity_module_removed
no snmp-server enable traps entity entity_unrecognised_module
no snmp-server enable traps entity entity_fan_status_change
no snmp-server enable traps entity entity_power_out_change
no snmp-server enable traps link linkDown
no snmp-server enable traps link linkUp
no snmp-server enable traps link extended-linkDown
no snmp-server enable traps link extended-linkUp
no snmp-server enable traps link cieLinkDown
no snmp-server enable traps link cieLinkUp
no snmp-server enable traps link delayed-link-state-change
no snmp-server enable traps rf redundancy_framework
no snmp-server enable traps license notify-license-expiry
no snmp-server enable traps license notify-no-license-for-feature
no snmp-server enable traps license notify-licensefile-missing
no snmp-server enable traps license notify-license-expiry-warning
no snmp-server enable traps upgrade UpgradeOpNotifyOnCompletion
no snmp-server enable traps upgrade UpgradeJobStatusNotify
no snmp-server enable traps rmon risingAlarm
no snmp-server enable traps rmon fallingAlarm
no snmp-server enable traps rmon hcRisingAlarm
no snmp-server enable traps rmon hcFallingAlarm
no snmp-server enable traps entity entity_sensor
no snmp-server enable traps entity cefcMIBEnableStatusNotification
no snmp-server enable traps generic coldStart
no snmp-server enable traps generic warmStart
no snmp-server enable traps storm-control cpscEventRev1
no snmp-server enable traps link cErrDisableInterfaceEventRev1
no snmp-server enable traps link cmn-mac-move-notification
ntp server 10.81.254.202 use-vrf management

vlan 1

vrf context management
  ip route 0.0.0.0/0 10.122.197.1
vrf context myvrf
vrf context testing
nxapi http port 80
no nxapi https
nxapi ssl ciphers weak
nxapi ssl protocols TLSv1


interface port-channel10

interface port-channel19

interface Ethernet1/1

interface Ethernet1/2

interface Ethernet1/3

interface Ethernet1/4

interface Ethernet1/5

interface Ethernet1/6

interface Ethernet1/7

interface Ethernet1/8

interface Ethernet1/9

interface Ethernet1/10

interface Ethernet1/11

interface Ethernet1/12

interface Ethernet1/13

interface Ethernet1/14

interface Ethernet1/15

interface Ethernet1/16

interface Ethernet1/17

interface Ethernet1/18

interface Ethernet1/19

interface Ethernet1/20

interface Ethernet1/21

interface Ethernet1/22

interface Ethernet1/23

interface Ethernet1/24

interface Ethernet1/25

interface Ethernet1/26

interface Ethernet1/27

interface Ethernet1/28

interface Ethernet1/29

interface Ethernet1/30

interface Ethernet1/31

interface Ethernet1/32

interface Ethernet1/33

interface Ethernet1/34

interface Ethernet1/35

interface Ethernet1/36

interface Ethernet1/37

interface Ethernet1/38

interface Ethernet1/39

interface Ethernet1/40

interface Ethernet1/41

interface Ethernet1/42

interface Ethernet1/43

interface Ethernet1/44

interface Ethernet1/45

interface Ethernet1/46

interface Ethernet1/47

interface Ethernet1/48

interface Ethernet2/1

interface Ethernet2/2

interface Ethernet2/3

interface Ethernet2/4

interface Ethernet2/5

interface Ethernet2/6

interface Ethernet2/7

interface Ethernet2/8

interface Ethernet2/9

interface Ethernet2/10

interface Ethernet2/11

interface Ethernet2/12

interface mgmt0
  vrf member management
  ip address 192.168.1.5/24
cli alias name wr copy running startup-config
line console
line vty
boot nxos bootflash:/nxos.9.2.4.bin

no logging logfile
no logging monitor
no logging module
no logging console
"""

n9k_show_running_config_list = [
    "\n!Command: show running-config\n!No configuration change since last"
    " restart\n!Time: Tue Dec  3 15:53:49 2019\n\nversion 9.2(4) Bios:version 07.66"
    " \nhostname n9k-device\ninstall feature-set fex\nvdc n9k-device id 1\n  allow"
    " feature-set fex\n  limit-resource vlan minimum 16 maximum 4094\n  limit-resource"
    " vrf minimum 2 maximum 4096\n  limit-resource port-channel minimum 0 maximum 256\n"
    "  limit-resource u4route-mem minimum 248 maximum 248\n  limit-resource u6route-mem"
    " minimum 96 maximum 96\n  limit-resource m4route-mem minimum 58 maximum 58\n "
    " limit-resource m6route-mem minimum 8 maximum 8\nfeature-set fex\n\nfeature"
    " privilege\nfeature tacacs+\ncfs eth distribute\nfeature ngmvpn\nfeature"
    " ospf\nfeature bgp\nfeature pim\nfeature vn-segment-vlan-based\nfeature"
    " lacp\nfeature vpc\nfeature lldp\nfeature bfd\n\nusername admin password 5"
    " $5$mOJsBDrL$lhsuyA8VT/fkWM/5XaZcgHlJIYaaS/J5fh8qdDr6fU3  role"
    " network-admin\nusername devops_user password 5 !  role network-operator\nusername"
    " devops_user passphrase  lifetime 99999 warntime 14 gracetime 3\nusername devops"
    " password 5 $5$.cbtHHuX$IL7tIg97MVeJZcyMhKQ15MsgzVj8w2L1uFufFnaVFv6  role"
    " network-admin\nusername devops passphrase  lifetime 99999 warntime 14 gracetime"
    " 3\nusername salt_test password 5"
    " $5$ALIDDA$epnGyDlACNBu6jqufkSIK26V0zRmO2ANJ6yTXqZwRv8  role"
    " network-operator\nusername salt_test role dev-ops\nusername salt_test role"
    " network-admin\nusername salt_test passphrase  lifetime 99999 warntime 14"
    " gracetime 3\nusername my_test password 5 !  role network-operator\nusername"
    " my_test passphrase  lifetime 99999 warntime 14 gracetime 3\nPassword secure mode"
    " ?? unknown security item\nip domain-lookup\nip name-server 1.1.1.1 2.2.2.2\nno"
    " system default switchport\nsystem default switchport shutdown\nno logging event"
    " link-status default\nno logging event link-status enable\nno logging event"
    " trunk-status enable\ntime-range ans-range\ntime-range my_range\ncopp profile"
    " strict\nsnmp-server user admin network-admin auth md5"
    " 0xbb62c3df89880933539503f7675e8aa8 priv 0xbb62c3df89880933539503f7675e8aa8"
    " localizedkey\nsnmp-server user devops network-admin auth md5"
    " 0xbb62c3df89880933539503f7675e8aa8 priv 0xbb62c3df89880933539503f7675e8aa8"
    " localizedkey\nsnmp-server user devops_user network-operator \nsnmp-server user"
    " my_test network-operator \nsnmp-server user salt_test network-operator auth md5"
    " 0xb3470bc06abb1789337e17e47d048fa2 priv 0xb3470bc06abb1789337e17e47d048fa2"
    " localizedkey\nsnmp-server user salt_test dev-ops\nsnmp-server user salt_test"
    " network-admin\nrmon event 1 description FATAL(1) owner PMON@FATAL\nrmon event 2"
    " description CRITICAL(2) owner PMON@CRITICAL\nrmon event 3 description ERROR(3)"
    " owner PMON@ERROR\nrmon event 4 description WARNING(4) owner PMON@WARNING\nrmon"
    " event 5 description INFORMATION(5) owner PMON@INFO\nntp server 10.81.254.202"
    " use-vrf management\n\nvlan 1\n\nvrf context management\n  ip domain-name cisco\n "
    " ip name-server 192.168.55.247\n  ip route 0.0.0.0/0 192.168.1.84\nvpc domain"
    " 100\n\ninterface port-channel10\n  switchport\n  switchport mode"
    " trunk\n\ninterface port-channel19\n\ninterface port-channel42\n  description"
    " foo\n\ninterface port-channel55\n\ninterface port-channel66\n\ninterface"
    " port-channel100\n  switchport\n  switchport mode trunk\n\ninterface Ethernet1/1\n"
    "  switchport\n  switchport mode trunk\n\ninterface Ethernet1/2\n  switchport\n "
    " switchport mode trunk\n\ninterface Ethernet1/3\n  switchport\n\ninterface"
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
    " mgmt0\n  vrf member management\n  ip address 192.168.1.55/24\n\ninterface"
    " loopback0\n  shutdown\n\ninterface loopback1\ncli alias name wr copy running"
    " startup-config\nline console\nline vty\nboot nxos bootflash:/nxos.9.2.4.bin"
    " \n\nno logging logfile\nno logging module\nno logging console\n\n\n"
]

n9k_show_running_inc_username_list = [
    "username salt_test password 5"
    " $5$ALIDDA$epnGyDlACNBu6jqufkSIK26V0zRmO2ANJ6yTXqZwRv8  role network-operator\n"
]
