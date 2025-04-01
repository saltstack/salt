import logging
import os

import pytest

import salt.modules.aixpkg as aixpkg
import salt.modules.pkg_resource as pkg_resource
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def lslpp_out():
    # Output from lslpp -Lc which contains Filesets and RPMs installed on system
    # Package Name:Fileset:Level:State:PTF Id:Fix State:Type:Description:Destination Dir.:Uninstaller:Message Catalog:Message Set:Message Number:Parent:Automatic:EFIX Locked:Install Path:Build Date

    return [
        "GSKit8:GSKit8.gskcrypt32.ppc.rte:8.0.50.88: : :C: :IBM GSKit Cryptography Runtime: : : : : : :0:0:/:",
        "GSKit8:GSKit8.gskcrypt64.ppc.rte:8.0.50.88: : :C: :IBM GSKit Cryptography Runtime: : : : : : :0:0:/:",
        "GSKit8:GSKit8.gskssl32.ppc.rte:8.0.50.88: : :C: :IBM GSKit SSL Runtime With Acme Toolkit: : : : : : :0:0:/:",
        "GSKit8:GSKit8.gskssl64.ppc.rte:8.0.50.88: : :C: :IBM GSKit SSL Runtime With Acme Toolkit: : : : : : :0:0:/:",
        "ICU4C.rte:ICU4C.rte:7.2.4.0: : :C: :International Components for Unicode : : : : : : :1:0:/:1937",
        "adde.v2.common:adde.v2.common.rte:7.2.0.0: : :C: :ADDE Common Device Runtime Environment : : : : : : :1:0:/:1543",
        "adde.v2.ethernet:adde.v2.ethernet.rte:7.2.4.0: : :C: :ADDE Ethernet Device Runtime Environment : : : : : : :1:0:/:1937",
        "adde.v2.rdma:adde.v2.rdma.rte:7.2.2.0: : :C: :ADDE RDMA Device Runtime Environment : : : : : : :1:0:/:1731",
        "bos.64bit:bos.64bit:7.2.4.1: : :C:F:Base Operating System 64 bit Runtime: : : : : : :0:0:/:2015",
        "bos.acct:bos.acct:7.2.4.0: : :C: :Accounting Services : : : : : : :1:0:/:1937",
        "bos.adt:bos.adt.base:7.2.4.1: : :C:F:Base Application Development Toolkit: : : : : : :0:0:/:2015",
        "bos.adt:bos.adt.debug:7.2.4.0: : :C: :Base Application Development Debuggers : : : : : : :1:0:/:1937",
        "bos.adt:bos.adt.include:7.2.4.1: : :C:F:Base Application Development Include Files: : : : : : :0:0:/:2015",
        "bos.adt:bos.adt.lib:7.2.4.0: : :C: :Base Application Development Libraries : : : : : : :1:0:/:1937",
        "bos.adt:bos.adt.libm:7.2.3.0: : :C: :Base Application Development Math Library : : : : : : :1:0:/:1837",
        "bos.ae:bos.ae:7.2.0.0: : :C: :Activation Engine : : : : : : :1:0:/:1543",
        "bos.aixpert.cmds:bos.aixpert.cmds:7.2.4.1: : :C:F:AIX Security Hardening: : : : : : :0:0:/:2015",
        "bos.aso:bos.aso:7.2.4.0: : :C: :Active System Optimizer : : : : : : :1:0:/:1937",
        "bos.cdmount:bos.cdmount:7.2.0.0: : :C: :CD/DVD Automount Facility : : : : : : :1:0:/:1543",
        "bos.diag:bos.diag.com:7.2.4.1: : :C:F:Common Hardware Diagnostics: : : : : : :0:0:/:2015",
        "bos.diag:bos.diag.rte:7.2.4.1: : :C:F:Hardware Diagnostics: : : : : : :0:0:/:2015",
        "bos.diag:bos.diag.util:7.2.4.1: : :C:F:Hardware Diagnostics Utilities: : : : : : :0:0:/:2015",
        "bos.help.msg.en_US:bos.help.msg.en_US.com:7.2.3.0: : :C: :WebSM/SMIT Context Helps - U.S. English: : : : : : :1:0:/:",
        "bos.help.msg.en_US:bos.help.msg.en_US.smit:7.2.3.0: : :C: :SMIT Context Helps - U.S. English: : : : : : :1:0:/:",
        "bos.iconv:bos.iconv.com:7.2.4.0: : :C: :Common Language to Language Converters : : : : : : :1:0:/:1937",
        "bos.iconv:bos.iconv.ucs.com:7.2.4.0: : :C: :Unicode Base Converters for AIX Code Sets/Fonts : : : : : : :1:0:/:1937",
        "bos.iocp:bos.iocp.rte:7.2.4.0: : :C: :I/O Completion Ports API : : : : : : :1:0:/:1937",
        "bos.loc.iso:bos.loc.iso.en_US:7.2.4.0: : :C: :Base System Locale ISO Code Set - U.S. English : : : : : : :1:0:/:1937",
        "bos.mh:bos.mh:7.2.0.0: : :C: :Mail Handler : : : : : : :1:0:/:1543",
        "bos.mls:bos.mls.lib:7.2.0.0: : :C: :Trusted AIX Libraries : : : : : : :1:0:/:1543",
        "bos.mp64:bos.mp64:7.2.4.4: : :C:F:Base Operating System 64-bit Multiprocessor Runtime: : : : : : :0:0:/:2015",
        "bos.net:bos.net.ipsec.keymgt:7.2.4.1: : :C:F:IP Security Key Management: : : : : : :0:0:/:2015",
        "bos.net:bos.net.ipsec.rte:7.2.4.1: : :C:F:IP Security: : : : : : :0:0:/:2015",
        "bos.net:bos.net.nfs.client:7.2.4.1: : :C:F:Network File System Client: : : : : : :0:0:/:2015",
        "bos.net:bos.net.nis.client:7.2.4.0: : :C: :Network Information Service Client : : : : : : :1:0:/:1937",
        "bos.net:bos.net.snapp:7.2.4.0: : :C: :System Networking Analysis and Performance Pilot : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.adt:7.2.4.1: : :C:F:TCP/IP Application Toolkit: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.bind:7.2.4.0: : :C: :TCP/IP BIND Server Applications : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.bind_utils:7.2.4.1: : :C:F:TCP/IP BIND Utility Applications: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.bootp:7.2.4.0: : :C: :TCP/IP bootpd Application : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.client:7.2.0.0: : :C: :TCP/IP Client Support : : : : : : :1:0:/:1543",
        "bos.net:bos.net.tcp.client_core:7.2.4.1: : :C:F:TCP/IP Client Core Support: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.dfpd:7.2.4.0: : :C: :TCP/IP Dynamic Feedback Protocol Application : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.dhcp:7.2.4.0: : :C: :TCP/IP DHCP Client Application : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.dhcpd:7.2.4.1: : :C:F:TCP/IP DHCP Server Applications: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.ftp:7.2.4.0: : :C: :TCP/IP ftp Client Application : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.ftpd:7.2.4.1: : :C:F:TCP/IP ftp Server Application: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.gated:7.2.4.1: : :C:F:TCP/IP gated Applications: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.imapd:7.2.4.1: : :C:F:TCP/IP imapd Applications: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.mail_utils:7.2.4.0: : :C: :TCP/IP Mail Utility Applications : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.ntp:7.2.4.0: : :C: :TCP/IP ntp Applications : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.ntpd:7.2.4.0: : :C: :TCP/IP ntpd Applications : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.pop3d:7.2.4.1: : :C:F:TCP/IP pop3d Applications: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.pxed:7.2.4.1: : :C:F:TCP/IP PXE Server Applications: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.rcmd:7.2.4.0: : :C: :TCP/IP Remote Command Client Applications : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.rcmd_server:7.2.4.0: : :C: :TCP/IP Remote Command Server Applications : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.sendmail:7.2.4.1: : :C:F:TCP/IP sendmail Applications: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.server:7.2.4.0: : :C: :TCP/IP Server Support : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.server_core:7.2.4.1: : :C:F:TCP/IP Server Core: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.slip:7.2.4.0: : :C: :TCP/IP SLIP Applications : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.slp:7.2.4.1: : :C:F:TCP/IP SLP Applications: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.smit:7.2.4.0: : :C: :TCP/IP SMIT Support : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.snmp:7.2.4.1: : :C:F:TCP/IP SNMP Client Application: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.snmpd:7.2.4.1: : :C:F:TCP/IP SNMP Server Application: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.syslogd:7.2.4.0: : :C: :TCP/IP syslogd Application : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.tcpdump:7.2.4.1: : :C:F:TCP/IP Trace Applications: : : : : : :0:0:/:2015",
        "bos.net:bos.net.tcp.telnet:7.2.4.0: : :C: :TCP/IP telnet Application : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.telnetd:7.2.4.0: : :C: :TCP/IP telnetd Application : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.tftp:7.2.4.0: : :C: :TCP/IP tftp Client Applications : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.tftpd:7.2.4.0: : :C: :TCP/IP tftpd Server Application : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.timed:7.2.4.0: : :C: :TCP/IP timed Application : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.traceroute:7.2.4.0: : :C: :TCP/IP BIND traceroute Applications : : : : : : :1:0:/:1937",
        "bos.net:bos.net.tcp.x500:7.2.4.0: : :C: :TCP/IP x500 Related Support : : : : : : :1:0:/:1937",
        "bos.net:bos.net.uucode:7.2.4.0: : :C: :Unix to Unix Copy Utilities : : : : : : :1:0:/:1937",
        "bos.net:bos.net.uucp:7.2.4.0: : :C: :Unix to Unix Copy Program : : : : : : :1:0:/:1937",
        "bos.perf:bos.perf.diag_tool:7.2.2.0: : :C: :Performance Diagnostic Tool : : : : : : :1:0:/:1731",
        "bos.perf:bos.perf.libperfstat:7.2.4.1: : :C:F:Performance Statistics Library Interface: : : : : : :0:0:/:2015",
        "bos.perf:bos.perf.perfstat:7.2.4.0: : :C: :Performance Statistics Interface : : : : : : :1:0:/:1937",
        "bos.perf.pmaix:bos.perf.pmaix:7.2.3.15: : :C: :Performance Management : : : : : : :1:0:/:1845",
        "bos.perf:bos.perf.proctools:7.2.4.1: : :C:F:Proc Filesystem Tools: : : : : : :0:0:/:2015",
        "bos.perf:bos.perf.tools:7.2.4.1: : :C:F:Base Performance Tools: : : : : : :0:0:/:2015",
        "bos.perf:bos.perf.tune:7.2.4.0: : :C: :Performance Tuning Support : : : : : : :1:0:/:1937",
        "bos.pmapi:bos.pmapi.events:7.2.3.0: : :C: :Performance Monitor API Event Codes : : : : : : :1:0:/:1837",
        "bos.pmapi:bos.pmapi.lib:7.2.4.1: : :C:F:Performance Monitor API Library: : : : : : :0:0:/:2015",
        "bos.pmapi:bos.pmapi.pmsvcs:7.2.4.1: : :C:F:Performance Monitor API Kernel Extension: : : : : : :0:0:/:2015",
        "bos.pmapi:bos.pmapi.samples:7.2.3.0: : :C: :Performance Monitor API Samples : : : : : : :1:0:/:1837",
        "bos.pmapi:bos.pmapi.tools:7.2.4.0: : :C: :Performance Monitor API Tools : : : : : : :1:0:/:1937",
        "bos:bos.rte:7.2.4.1: : :C:F:Base Operating System Runtime: : : : : : :0:0:/:2015",
        "bos:bos.rte.Dt:7.2.0.0: : :C: :Desktop Integrator: : : : : : :1:0:/:",
        "bos:bos.rte.ILS:7.2.4.0: : :C: :International Language Support: : : : : : :1:0:/:",
        "bos:bos.rte.SRC:7.2.4.0: : :C: :System Resource Controller: : : : : : :1:0:/:",
        "bos:bos.rte.X11:7.2.0.0: : :C: :AIXwindows Device Support: : : : : : :1:0:/:",
        "bos:bos.rte.aio:7.2.4.2: : :C:F:Asynchronous I/O Extension: : : : : : :0:0:/:2015",
        "bos:bos.rte.archive:7.2.4.0: : :C: :Archive Commands: : : : : : :1:0:/:",
        "bos:bos.rte.bind_cmds:7.2.4.1: : :C:F:Binder and Loader Commands: : : : : : :0:0:/:2015",
        "bos:bos.rte.boot:7.2.4.1: : :C:F:Boot Commands: : : : : : :0:0:/:2015",
        "bos:bos.rte.bosinst:7.2.4.0: : :C: :Base OS Install Commands: : : : : : :1:0:/:",
        "bos:bos.rte.commands:7.2.4.1: : :C:F:Commands: : : : : : :0:0:/:2015",
        "bos:bos.rte.compare:7.2.4.1: : :C:F:File Compare Commands: : : : : : :0:0:/:2015",
        "bos:bos.rte.console:7.2.1.0: : :C: :Console: : : : : : :1:0:/:",
        "bos:bos.rte.control:7.2.4.1: : :C:F:System Control Commands: : : : : : :0:0:/:2015",
        "bos:bos.rte.cron:7.2.4.0: : :C: :Batch Operations: : : : : : :1:0:/:",
        "bos:bos.rte.date:7.2.4.1: : :C:F:Date Control Commands: : : : : : :0:0:/:2015",
        "bos:bos.rte.devices:7.2.4.0: : :C: :Base Device Drivers: : : : : : :1:0:/:",
        "bos:bos.rte.devices_msg:7.2.4.0: : :C: :Device Driver Messages: : : : : : :1:0:/:",
        "bos:bos.rte.diag:7.2.4.0: : :C: :Diagnostics: : : : : : :1:0:/:",
        "bos:bos.rte.edit:7.2.4.1: : :C:F:Editors: : : : : : :0:0:/:2015",
        "bos:bos.rte.filesystem:7.2.4.0: : :C: :Filesystem Administration: : : : : : :1:0:/:",
        "bos:bos.rte.iconv:7.2.4.0: : :C: :Language Converters: : : : : : :1:0:/:",
        "bos:bos.rte.ifor_ls:7.2.2.0: : :C: :iFOR/LS Libraries: : : : : : :1:0:/:",
        "bos:bos.rte.im:7.2.3.0: : :C: :Input Methods: : : : : : :1:0:/:",
        "bos:bos.rte.install:7.2.4.4: : :C:F:LPP Install Commands: : : : : : :0:0:/:2015",
        "bos:bos.rte.jfscomp:7.2.3.0: : :C: :JFS Compression: : : : : : :1:0:/:",
        "bos:bos.rte.libc:7.2.4.1: : :C:F:libc Library: : : : : : :0:0:/:2015",
        "bos:bos.rte.libcfg:7.2.4.0: : :C: :libcfg Library: : : : : : :1:0:/:",
        "bos:bos.rte.libcur:7.2.2.0: : :C: :libcurses Library: : : : : : :1:0:/:",
        "bos:bos.rte.libdbm:7.2.0.0: : :C: :libdbm Library: : : : : : :1:0:/:",
        "bos:bos.rte.libnetsvc:7.2.0.0: : :C: :Network Services Libraries: : : : : : :1:0:/:",
        "bos:bos.rte.libpthreads:7.2.4.1: : :C:F:libpthreads Library: : : : : : :0:0:/:2015",
        "bos:bos.rte.libqb:7.2.4.0: : :C: :libqb Library: : : : : : :1:0:/:",
        "bos:bos.rte.libs:7.2.0.0: : :C: :libs Library: : : : : : :1:0:/:",
        "bos:bos.rte.loc:7.2.1.0: : :C: :Base Locale Support: : : : : : :1:0:/:",
        "bos:bos.rte.lvm:7.2.4.1: : :C:F:Logical Volume Manager: : : : : : :0:0:/:2015",
        "bos:bos.rte.man:7.2.0.0: : :C: :Man Commands: : : : : : :1:0:/:",
        "bos:bos.rte.methods:7.2.4.0: : :C: :Device Config Methods: : : : : : :1:0:/:",
        "bos:bos.rte.misc_cmds:7.2.4.0: : :C: :Miscellaneous Commands: : : : : : :1:0:/:",
        "bos:bos.rte.mlslib:7.2.0.0: : :C: :Trusted AIX Libraries: : : : : : :1:0:/:",
        "bos:bos.rte.net:7.2.4.1: : :C:F:Network: : : : : : :0:0:/:2015",
        "bos:bos.rte.odm:7.2.4.0: : :C: :Object Data Manager: : : : : : :1:0:/:",
        "bos:bos.rte.printers:7.2.4.0: : :C: :Front End Printer Support: : : : : : :1:0:/:",
        "bos:bos.rte.security:7.2.4.1: : :C:F:Base Security Function: : : : : : :0:0:/:2015",
        "bos:bos.rte.serv_aid:7.2.4.0: : :C: :Error Log Service Aids: : : : : : :1:0:/:",
        "bos:bos.rte.shell:7.2.4.1: : :C:F:Shells (bsh, ksh, csh): : : : : : :0:0:/:2015",
        "bos:bos.rte.streams:7.2.4.0: : :C: :Streams Libraries: : : : : : :1:0:/:",
        "bos:bos.rte.tty:7.2.4.1: : :C:F:Base TTY Support and Commands: : : : : : :0:0:/:2015",
        "bos.swma:bos.swma:7.2.0.0: : :C: :Software Maintenance Agreement : : : : : : :1:0:/:1543",
        "bos.sysmgt:bos.sysmgt.loginlic:7.2.4.0: : :C: :License Management : : : : : : :1:0:/:1937",
        "bos.sysmgt:bos.sysmgt.nim.client:7.2.4.1: : :C:F:Network Install Manager - Client Tools: : : : : : :0:0:/:2015",
        "bos.sysmgt:bos.sysmgt.quota:7.2.2.0: : :C: :Filesystem Quota Commands : : : : : : :1:0:/:1731",
        "bos.sysmgt:bos.sysmgt.serv_aid:7.2.4.0: : :C: :Software Error Logging and Dump Service Aids : : : : : : :1:0:/:1937",
        "bos.sysmgt:bos.sysmgt.smit:7.2.4.1: : :C:F:System Management Interface Tool (SMIT): : : : : : :0:0:/:2015",
        "bos.sysmgt:bos.sysmgt.sysbr:7.2.4.1: : :C:F:System Backup and BOS Install Utilities: : : : : : :0:0:/:2015",
        "bos.sysmgt:bos.sysmgt.trace:7.2.4.1: : :C:F:Software Trace Service Aids: : : : : : :0:0:/:2015",
        "bos.terminfo:bos.terminfo.ansi.data:7.2.0.0: : :C: :Amer National Stds Institute Terminal Defs : : : : : : :1:0:/:1543",
        "bos.terminfo:bos.terminfo.com.data:7.2.0.0: : :C: :Common Terminal Definitions : : : : : : :1:0:/:1543",
        "bos.terminfo:bos.terminfo.dec.data:7.2.0.0: : :C: :Digital Equipment Corp. Terminal Definitions : : : : : : :1:0:/:1543",
        "bos.terminfo:bos.terminfo.ibm.data:7.2.0.0: : :C: :IBM Terminal Definitions : : : : : : :1:0:/:1543",
        "bos.terminfo:bos.terminfo.pc.data:7.2.0.0: : :C: :Personal Computer Terminal Definitions : : : : : : :1:0:/:1543",
        "bos.terminfo:bos.terminfo.print.data:7.2.0.0: : :C: :Generic Line Printer Terminal Definitions : : : : : : :1:0:/:1543",
        "bos.terminfo:bos.terminfo.rte:7.2.0.0: : :C: :Run-time Environment for AIX Terminals : : : : : : :1:0:/:1543",
        "bos.terminfo:bos.terminfo.televideo.data:7.2.0.0: : :C: :Televideo Terminal Definitions : : : : : : :1:0:/:1543",
        "bos.terminfo:bos.terminfo.wyse.data:7.2.0.0: : :C: :Wyse Terminal Definitions : : : : : : :1:0:/:1543",
        "bos.txt:bos.txt.spell:7.2.0.0: : :C: :Writer's Tools Commands : : : : : : :1:0:/:1543",
        "bos.txt:bos.txt.spell.data:7.2.0.0: : :C: :Writer's Tools Data : : : : : : :1:0:/:1543",
        "bos.txt:bos.txt.tfs:7.2.1.0: : :C: :Text Formatting Services Commands : : : : : : :1:0:/:1642",
        "bos.txt:bos.txt.tfs.data:7.2.0.0: : :C: :Text Formatting Services Data : : : : : : :1:0:/:1543",
        "bos.wpars:bos.wpars:7.2.4.1: : :C:F:AIX Workload Partitions: : : : : : :0:0:/:2015",
        "bos.xerces:bos.xerces.lib:3.2.2.0: : :C: :APACHE Xerces-C++ XML parsing library: : : : : : :1:0:/:",
        "cdrtools.base:cdrtools.base:1.9.0.9: : :C: :CD/DVD recorder: : : : : : :1:0:/:",
        "cdrtools.man.en_US:cdrtools.man.en_US:1.9.0.9: : :C: :CD/DVD recorder man page documentation: : : : : : :1:0:/:",
        "clic.rte:clic.rte.kernext:4.10.0.2: : :C: :CryptoLite for C Kernel: : : : : : :1:0:/:",
        "clic.rte:clic.rte.lib:4.10.0.2: : :C: :CryptoLite for C Library: : : : : : :1:0:/:",
        "devices.artic960:devices.artic960.diag:7.2.0.0: : :C: :IBM ARTIC960 Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.artic960:devices.artic960.rte:7.2.4.0: : :C: :IBM ARTIC960 Runtime Support : : : : : : :1:0:/:1937",
        "devices.artic960:devices.artic960.ucode:7.2.0.0: : :C: :IBM ARTIC960 Adapter Software : : : : : : :1:0:/:1543",
        "devices.capi.14105043:devices.capi.14105043.rte:7.2.4.0: : :C: :CAPI Memory Copy Accelerator Software : : : : : : :1:0:/:1937",
        "devices.capi.1410f0041410f004:devices.capi.1410f0041410f004.com:7.2.4.0: : :C: :Common CAPI Flash Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.capi.1410f0041410f004:devices.capi.1410f0041410f004.diag:7.2.4.0: : :C: :CAPI Flash Adapter Diagnostics : : : : : : :1:0:/:1937",
        "devices.capi.1410f0041410f004:devices.capi.1410f0041410f004.rte:7.2.0.0: : :C: :CAPI Flash Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.chrp.AT97SC3201_r:devices.chrp.AT97SC3201_r.rte:7.2.0.0: : :C: :Trusted Platform Module Device Software : : : : : : :1:0:/:1543",
        "devices.chrp.IBM.lhca:devices.chrp.IBM.lhca.rte:7.2.4.0: : :C: :Infiniband Logical HCA Runtime Environment : : : : : : :1:0:/:1937",
        "devices.chrp.IBM.lhea:devices.chrp.IBM.lhea.diag:7.2.0.0: : :C: :Host Ethernet Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.chrp.IBM.lhea:devices.chrp.IBM.lhea.rte:7.2.4.0: : :C: :Host Ethernet Adapter (HEA) Runtime Environment : : : : : : :1:0:/:1937",
        "devices.chrp.base:devices.chrp.base.ServiceRM:2.5.1.3: : :C:F:RSCT Service Resource Manager: : : : : : :1:0:/:",
        "devices.chrp.base:devices.chrp.base.diag:7.2.4.1: : :C:F:RISC CHRP Base System Device Diagnostics: : : : : : :0:0:/:2015",
        "devices.chrp.base:devices.chrp.base.rte:7.2.4.2: : :C:F:RISC PC Base System Device Software (CHRP): : : : : : :0:0:/:2015",
        "devices.chrp.capi:devices.chrp.capi.rte:7.2.4.0: : :C: :CAPI Bus Software (CHRP) : : : : : : :1:0:/:1937",
        "devices.chrp.pci:devices.chrp.pci.rte:7.2.4.0: : :C: :PCI Bus Software (CHRP) : : : : : : :1:0:/:1937",
        "devices.chrp.pciex:devices.chrp.pciex.rte:7.2.0.0: : :C: :PCI Express Bus Software (CHRP) : : : : : : :1:0:/:1543",
        "devices.chrp.vdevice:devices.chrp.vdevice.rte:7.2.4.0: : :C: :Virtual I/O Bus Support : : : : : : :1:0:/:1937",
        "devices.chrp_lpar.base:devices.chrp_lpar.base.ras:7.2.4.0: : :C: :CHRP LPAR RAS Support : : : : : : :1:0:/:1937",
        "devices.common.IBM.async:devices.common.IBM.async.diag:7.2.0.0: : :C: :Common Serial Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.common.IBM.cflash:devices.common.IBM.cflash.rte:7.2.4.0: : :C: :Common CAPI Flash Device Software : : : : : : :1:0:/:1937",
        "devices.common.IBM.crypt:devices.common.IBM.crypt.rte:7.2.0.0: : :C: :Cryptographic Common Runtime Environment : : : : : : :1:0:/:1543",
        "devices.common.IBM.cx:devices.common.IBM.cx.rte:7.2.3.15: : :C: :CX Common Adapter Software : : : : : : :1:0:/:1845",
        "devices.common.IBM.disk:devices.common.IBM.disk.rte:7.2.4.0: : :C: :Common IBM Disk Software : : : : : : :1:0:/:1937",
        "devices.common.IBM.ethernet:devices.common.IBM.ethernet.rte:7.2.4.2: : :C:F:Common Ethernet Software: : : : : : :0:0:/:2015",
        "devices.common.IBM.fc:devices.common.IBM.fc.hba-api:7.2.4.0: : :C: :Common HBA API Library : : : : : : :1:0:/:1937",
        "devices.common.IBM.fc:devices.common.IBM.fc.rte:7.2.4.1: : :C:F:Common IBM FC Software: : : : : : :0:0:/:2015",
        "devices.common.IBM.fda:devices.common.IBM.fda.diag:7.2.0.0: : :C: :Common Diskette Adapter and Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.common.IBM.fda:devices.common.IBM.fda.rte:7.2.0.0: : :C: :Common Diskette Device Software : : : : : : :1:0:/:1543",
        "devices.common.IBM.hdlc:devices.common.IBM.hdlc.rte:7.2.4.1: : :C:F:Common HDLC Software: : : : : : :0:0:/:2015",
        "devices.common.IBM.hdlc:devices.common.IBM.hdlc.sdlc:7.2.4.0: : :C: :SDLC COMIO Device Driver Emulation : : : : : : :1:0:/:1937",
        "devices.common.IBM.ib:devices.common.IBM.ib.rte:7.2.4.1: : :C:F:Infiniband Common Runtime Environment: : : : : : :0:0:/:2015",
        "devices.common.IBM.ide:devices.common.IBM.ide.rte:7.2.0.0: : :C: :Common IDE I/O Controller Software : : : : : : :1:0:/:1543",
        "devices.common.IBM.iscsi:devices.common.IBM.iscsi.rte:7.2.4.1: : :C:F:Common iSCSI Files: : : : : : :0:0:/:2015",
        "devices.common.IBM.ktm_std:devices.common.IBM.ktm_std.diag:7.2.0.0: : :C: :Common Keyboard, Mouse, and Tablet Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.common.IBM.ktm_std:devices.common.IBM.ktm_std.rte:7.2.0.0: : :C: :Common Keyboard, Tablet, and Mouse Software : : : : : : :1:0:/:1543",
        "devices.common.IBM.modemcfg:devices.common.IBM.modemcfg.data:7.2.0.0: : :C: :Sample Service Processor Modem Configuration Files : : : : : : :1:0:/:1543",
        "devices.common.IBM.mpio:devices.common.IBM.mpio.rte:7.2.4.1: : :C:F:MPIO Disk Path Control Module: : : : : : :0:0:/:2015",
        "devices.common.IBM.mpt2:devices.common.IBM.mpt2.diag:7.2.4.0: : :C: :MPT SAS Device Diagnostics : : : : : : :1:0:/:1937",
        "devices.common.IBM.mpt2:devices.common.IBM.mpt2.rte:7.2.4.0: : :C: :MPT SAS Device Software : : : : : : :1:0:/:1937",
        "devices.common.IBM.scsi:devices.common.IBM.scsi.rte:7.2.4.1: : :C:F:Common SCSI I/O Controller Software: : : : : : :0:0:/:2015",
        "devices.common.IBM.sissas:devices.common.IBM.sissas.rte:7.2.4.0: : :C: :Common IBM SAS RAID Software : : : : : : :1:0:/:1937",
        "devices.common.IBM.soe:devices.common.IBM.soe.rte:7.2.4.1: : :C: :Serial over Ethernet client driver : : : : : : :0:0:/:2015",
        "devices.common.IBM.storfwork:devices.common.IBM.storfwork.rte:7.2.4.1: : :C:F:Storage Framework Module: : : : : : :0:0:/:2015",
        "devices.common.IBM.usb:devices.common.IBM.usb.diag:7.2.4.0: : :C: :Common USB Adapter Diagnostics : : : : : : :1:0:/:1937",
        "devices.common.IBM.usb:devices.common.IBM.usb.rte:7.2.4.0: : :C: :USB System Software : : : : : : :1:0:/:1937",
        "devices.common.IBM.xhci:devices.common.IBM.xhci.rte:7.2.4.0: : :C: :Common xHCI Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.common.base:devices.common.base.diag:7.2.0.0: : :C: :Common Base System Diagnostics : : : : : : :1:0:/:1543",
        "devices.common.rspcbase:devices.common.rspcbase.rte:7.2.4.0: : :C: :RISC PC Common Base System Device Software : : : : : : :1:0:/:1937",
        "devices.ethernet.ct3:devices.ethernet.ct3.cdli:7.2.4.0: : :C: :10 Gigabit Ethernet Adapter Software : : : : : : :1:0:/:1937",
        "devices.ethernet.ct3:devices.ethernet.ct3.rte:7.2.4.0: : :C: :10 Gigabit Ethernet PCI-Express Host Bus Adapter Software : : : : : : :1:0:/:1937",
        "devices.ethernet.lnc2:devices.ethernet.lnc2.rte:7.2.4.2: : :C:F:10 Gigabit Ethernet PCI-Express Adapter Software (lnc2): : : : : : :0:0:/:2015",
        "devices.ethernet.mlx:devices.ethernet.mlx.diag:7.2.0.0: : :C: :RoCE Converged Network Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.ethernet.mlx:devices.ethernet.mlx.rte:7.2.4.2: : :C:F:RoCE Converged Network Adapter: : : : : : :0:0:/:2015",
        "devices.ethernet.mlxc:devices.ethernet.mlxc.rte:7.2.4.2: : :C:F:MLXC RoCE Adapter Software: : : : : : :0:0:/:2015",
        "devices.ethernet.shi:devices.ethernet.shi.rte:7.2.4.2: : :C:F:10 Gigabit Ethernet PCI-Express Adapter Software (shi): : : : : : :0:0:/:2015",
        "devices.fcp.disk:devices.fcp.disk.rte:7.2.4.1: : :C:F:FC SCSI CD-ROM, Disk, Read/Write Optical Device Software: : : : : : :0:0:/:2015",
        "devices.fcp.tape:devices.fcp.tape.rte:7.2.4.0: : :C: :FC SCSI Tape Device Software : : : : : : :1:0:/:1937",
        "devices.graphics:devices.graphics.com:7.2.3.0: : :C: :Graphics Adapter Common Software : : : : : : :1:0:/:1837",
        "devices.graphics:devices.graphics.voo:7.2.0.0: : :C: :Graphics Adapter VOO and Stereo Software : : : : : : :1:0:/:1543",
        "devices.ide.cdrom:devices.ide.cdrom.diag:7.2.4.0: : :C: :IDE CDROM, Cdrom Device Diagnostics : : : : : : :1:0:/:1937",
        "devices.ide.cdrom:devices.ide.cdrom.rte:7.2.4.0: : :C: :IDE CDROM Device Software : : : : : : :1:0:/:1937",
        "devices.iscsi.disk:devices.iscsi.disk.rte:7.2.3.15: : :C: :iSCSI Disk Software : : : : : : :1:0:/:1845",
        "devices.iscsi.tape:devices.iscsi.tape.rte:7.2.0.0: : :C: :iSCSI Tape Software : : : : : : :1:0:/:1543",
        "devices.iscsi_sw:devices.iscsi_sw.rte:7.2.4.1: : :C:F:iSCSI Software Device Driver: : : : : : :0:0:/:2015",
        "devices.loopback:devices.loopback.rte:7.2.4.0: : :C: :Loopback Device Driver : : : : : : :1:0:/:1937",
        "devices.pci.00100b00:devices.pci.00100b00.diag:7.2.0.0: : :C: :SYM53C896 Dual Channel PCI-2 Ultra2 SCSI Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.00100b00:devices.pci.00100b00.rte:7.2.0.0: : :C: :SYM53C896 Dual Channel PCI SCSI I/O Controller : : : : : : :1:0:/:1543",
        "devices.pci.00100c00:devices.pci.00100c00.diag:7.2.0.0: : :C: :SYM53C895 LVD PCI SCSI I/O Controller Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.00100c00:devices.pci.00100c00.rte:7.2.0.0: : :C: :SYM53C895 PCI SCSI I/O Controller Software : : : : : : :1:0:/:1543",
        "devices.pci.00100f00:devices.pci.00100f00.diag:7.2.3.0: : :C: :SYM53C8xxA PCI SCSI I/O Controller Diagnostics : : : : : : :1:0:/:1837",
        "devices.pci.00100f00:devices.pci.00100f00.rte:7.2.4.0: : :C: :SYM53C8xxA PCI SCSI I/O Controller Software : : : : : : :1:0:/:1937",
        "devices.pci.00102100:devices.pci.00102100.diag:7.2.0.0: : :C: :SYM53C1010 Dual Channel PCI Ultra3 SCSI Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.00102100:devices.pci.00102100.rte:7.2.0.0: : :C: :SYM53C1010 PCI Ultra-3 SCSI I/O Controller Software : : : : : : :1:0:/:1543",
        "devices.pci.00105000:devices.pci.00105000.com:7.2.4.0: : :C: :Common SAS Expansion Card Device Software : : : : : : :1:0:/:1937",
        "devices.pci.00105000:devices.pci.00105000.diag:7.2.4.0: : :C: :LSI SAS Adapter Diagnostics : : : : : : :1:0:/:1937",
        "devices.pci.00105000:devices.pci.00105000.rte:7.2.0.0: : :C: :SAS Expansion Card Device Software (00105000) : : : : : : :1:0:/:1543",
        "devices.pci.02105e51:devices.pci.02105e51.X11:7.2.0.0: : :C: :AIXwindows Native Display Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.02105e51:devices.pci.02105e51.diag:7.2.0.0: : :C: :Native Display Graphics Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.02105e51:devices.pci.02105e51.rte:7.2.3.0: : :C: :Native Display Adapter Software : : : : : : :1:0:/:1837",
        "devices.pci.14100c03:devices.pci.14100c03.diag:7.2.0.0: : :C: :PCI-XDDR Auxiliary Cache Adapter Diagnostics (14100c03) : : : : : : :1:0:/:1543",
        "devices.pci.14100c03:devices.pci.14100c03.rte:7.2.0.0: : :C: :PCI-XDDR Auxiliary Cache Adapter Software (14100c03) : : : : : : :1:0:/:1543",
        "devices.pci.14100d03:devices.pci.14100d03.diag:7.2.0.0: : :C: :PCI-XDDR Auxiliary Cache Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.14100d03:devices.pci.14100d03.rte:7.2.0.0: : :C: :PCI-XDDR Auxiliary Cache Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.14101103:devices.pci.14101103.diag:7.2.0.0: : :C: :4-Port 10/100/1000 Base-TX PCI-X Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.14101103:devices.pci.14101103.rte:7.2.0.0: : :C: :4-Port 10/100/1000 Base-TX PCI-X Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.14102203:devices.pci.14102203.diag:7.2.0.0: : :C: :IBM 1 Gigabit-TX iSCSI TOE PCI-X Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.14102203:devices.pci.14102203.rte:7.2.0.0: : :C: :IBM 1 Gigabit-TX iSCSI TOE PCI-X Adapter : : : : : : :1:0:/:1543",
        "devices.pci.14102e00:devices.pci.14102e00.diag:7.2.4.0: : :C: :IBM PCI SCSI RAID Adapter Diagnostics Support : : : : : : :1:0:/:1937",
        "devices.pci.14102e00:devices.pci.14102e00.rte:7.2.4.0: : :C: :IBM PCI SCSI RAID Adapter Device Software Support : : : : : : :1:0:/:1937",
        "devices.pci.14103302:devices.pci.14103302.X11:7.2.0.0: : :C: :AIXwindows GXT135P Graphics Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.14103302:devices.pci.14103302.diag:7.2.0.0: : :C: :GXT135P Graphics Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.14103302:devices.pci.14103302.rte:7.2.3.0: : :C: :GXT135P Graphics Adapter Software : : : : : : :1:0:/:1837",
        "devices.pci.14106402:devices.pci.14106402.diag:7.2.0.0: : :C: :PCI-X Quad Channel U320 SCSI RAID Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.14106402:devices.pci.14106402.rte:7.2.0.0: : :C: :PCI-X Quad Channel U320 SCSI RAID Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.14106402:devices.pci.14106402.ucode:7.2.0.0: : :C: :PCI-X Quad Channel U320 SCSI RAID Adapter Microcode : : : : : : :1:0:/:1543",
        "devices.pci.14106602:devices.pci.14106602.diag:7.2.4.0: : :C: :PCI-X Dual Channel SCSI Adapter Diagnostics : : : : : : :1:0:/:1937",
        "devices.pci.14106602:devices.pci.14106602.rte:7.2.4.0: : :C: :PCI-X Dual Channel SCSI Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pci.14106602:devices.pci.14106602.ucode:7.2.0.0: : :C: :PCI-X Dual Channel SCSI Adapter Microcode : : : : : : :1:0:/:1543",
        "devices.pci.14106802:devices.pci.14106802.diag:7.2.0.0: : :C: :Gigabit Ethernet-SX PCI-X Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.14106802:devices.pci.14106802.rte:7.2.0.0: : :C: :Gigabit Ethernet-SX PCI-X Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.14106902:devices.pci.14106902.diag:7.2.3.15: : :C: :10/100/1000 Base-TX PCI-X Adapter Diagnostics : : : : : : :1:0:/:1845",
        "devices.pci.14106902:devices.pci.14106902.rte:7.2.4.0: : :C: :10/100/1000 Base-TX PCI-X Adapter Software : : : : : : :1:0:/:1937",
        "devices.pci.14107802:devices.pci.14107802.diag:7.2.0.0: : :C: :PCI-X Dual Channel Ultra320 SCSI RAID Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.14107802:devices.pci.14107802.rte:7.2.4.0: : :C: :PCI-X Dual Channel Ultra320 SCSI RAID Adapter Software : : : : : : :1:0:/:1937",
        "devices.pci.14107802:devices.pci.14107802.ucode:7.2.0.0: : :C: :PCI-X Dual Channel Ultra320 SCSI RAID Adapter Microcode : : : : : : :1:0:/:1543",
        "devices.pci.14108902:devices.pci.14108902.diag:7.2.0.0: : :C: :10/100/1000 Base-TX PCI-X Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.14108902:devices.pci.14108902.rte:7.2.0.0: : :C: :2-Port 10/100/1000 Base-TX PCI-X Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.14108c00:devices.pci.14108c00.rte:7.2.3.0: : :C: :ARTIC960Hx 4-Port Selectable PCI Adapter Runtime Software : : : : : : :1:0:/:1837",
        "devices.pci.14108d02:devices.pci.14108d02.diag:7.2.0.0: : :C: :PCI-X DDR Dual Channel SAS RAID Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.14108d02:devices.pci.14108d02.rte:7.2.0.0: : :C: :PCI-XDDR Dual Channel SAS RAID Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410a803:devices.pci.1410a803.diag:7.2.0.0: : :C: :4-port Asynchronous EIA-232 PCI-E Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.1410a803:devices.pci.1410a803.rte:7.2.0.0: : :C: :4 Port Async EIA-232 PCIe Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410bd02:devices.pci.1410bd02.diag:7.2.3.15: : :C: :PCI-X266 3GB SAS RAID Adapter Diagnostics : : : : : : :1:0:/:1845",
        "devices.pci.1410bd02:devices.pci.1410bd02.rte:7.2.0.0: : :C: :PCI-X266 Dual-x4 3Gb SAS RAID Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410be02:devices.pci.1410be02.diag:7.2.0.0: : :C: :PCI-X DDR Dual Channel U320 SCSI RAID Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.1410be02:devices.pci.1410be02.rte:7.2.0.0: : :C: :PCI-XDDR Dual Channel U320 SCSI RAID Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410bf02:devices.pci.1410bf02.diag:7.2.0.0: : :C: :PCI-X DDR Quad Channel U320 SCSI RAID Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.1410bf02:devices.pci.1410bf02.rte:7.2.0.0: : :C: :PCI-XDDR Quad Channel U320 SCSI RAID Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410c002:devices.pci.1410c002.diag:7.2.0.0: : :C: :PCI-X DDR Dual Channel U320 SCSI Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.1410c002:devices.pci.1410c002.rte:7.2.0.0: : :C: :PCI-XDDR Dual Channel U320 SCSI Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410c302:devices.pci.1410c302.diag:7.2.0.0: : :C: :PCI-X266 Ext Tri-x4 3Gb SAS RAID Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.1410c302:devices.pci.1410c302.rte:7.2.0.0: : :C: :PCI-X266 Ext Tri-x4 3Gb SAS RAID Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410cf02:devices.pci.1410cf02.diag:7.2.0.0: : :C: :1000 Base-SX PCI-X iSCSI TOE Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.1410cf02:devices.pci.1410cf02.rte:7.2.0.0: : :C: :1000 Base-SX PCI-X iSCSI TOE Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pci.1410d002:devices.pci.1410d002.com:7.2.4.0: : :C: :Common PCI iSCSI TOE Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pci.1410d002:devices.pci.1410d002.diag:7.2.4.0: : :C: :1000 Base-TX PCI-X iSCSI TOE Adapter Device Diagnostics : : : : : : :1:0:/:1937",
        "devices.pci.1410d002:devices.pci.1410d002.rte:7.2.0.0: : :C: :1000 Base-TX PCI-X iSCSI TOE Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pci.1410d302:devices.pci.1410d302.diag:7.2.0.0: : :C: :PCI-X Dual Channel Ultra320 SCSI Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.1410d302:devices.pci.1410d302.rte:7.2.0.0: : :C: :PCI-X Dual Channel U320 SCSI Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410d402:devices.pci.1410d402.diag:7.2.0.0: : :C: :PCI-X Dual Channel U320 SCSI RAID Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.1410d402:devices.pci.1410d402.rte:7.2.0.0: : :C: :PCI-X Dual Channel U320 SCSI RAID Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410d403:devices.pci.1410d403.rte:7.2.0.0: : :C: :Native 1-Port Asynchronous EIA-232 PCI Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410d502:devices.pci.1410d502.diag:7.2.0.0: : :C: :PCI-X DDR Quad Channel U320 SCSI RAID Adapter Diagnostics : : : : : : :1:0:/:154",
        "devices.pci.1410d502:devices.pci.1410d502.rte:7.2.0.0: : :C: :PCI-XDDR Quad Channel U320 SCSI RAID Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410e202:devices.pci.1410e202.diag:7.2.0.0: : :C: :IBM 1 Gigabit-SX iSCSI TOE PCI-X Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.1410e202:devices.pci.1410e202.rte:7.2.0.0: : :C: :IBM 1 Gigabit-SX iSCSI TOE PCI-X Adapter : : : : : : :1:0:/:1543",
        "devices.pci.1410e601:devices.pci.1410e601.diag:7.2.0.0: : :C: :IBM Cryptographic Accelerator Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.1410e601:devices.pci.1410e601.rte:7.2.3.0: : :C: :IBM Crypto Accelerator Adapter Software : : : : : : :1:0:/:1837",
        "devices.pci.1410eb02:devices.pci.1410eb02.diag:7.2.3.15: : :C: :10 Gigabit Ethernet-SR PCI-X 2.0 DDR Adapter Diagnostics : : : : : : :1:0:/:1845",
        "devices.pci.1410eb02:devices.pci.1410eb02.rte:7.2.0.0: : :C: :10 Gigabit Ethernet-SR PCI-X 2.0 DDR Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.1410ec02:devices.pci.1410ec02.diag:7.2.0.0: : :C: :10 Gigabit Ethernet-LR PCI-X 2.0 DDR Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.1410ec02:devices.pci.1410ec02.rte:7.2.3.0: : :C: :10 Gigabit Ethernet-LR PCI-X 2.0 DDR Adapter Software : : : : : : :1:0:/:1837",
        "devices.pci.22106474:devices.pci.22106474.diag:7.2.0.0: : :C: :USB Host Controller (22106474) Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.22106474:devices.pci.22106474.rte:7.2.3.0: : :C: :USB Host Controller (22106474) Software : : : : : : :1:0:/:1837",
        "devices.pci.2b102725:devices.pci.2b102725.X11:7.2.0.0: : :C: :AIXwindows GXT145 Graphics Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.2b102725:devices.pci.2b102725.diag:7.2.0.0: : :C: :GXT145 2D Graphics Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.2b102725:devices.pci.2b102725.rte:7.2.3.0: : :C: :GXT145 Graphics Adapter Software : : : : : : :1:0:/:1837",
        "devices.pci.33103500:devices.pci.33103500.diag:7.2.0.0: : :C: :USB Host Controller (33103500) Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.33103500:devices.pci.33103500.rte:7.2.3.0: : :C: :USB Host Controller (33103500) Software : : : : : : :1:0:/:1837",
        "devices.pci.3310e000:devices.pci.3310e000.diag:7.2.0.0: : :C: :USB Enhanced Host Controller (3310e000) Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.3310e000:devices.pci.3310e000.rte:7.2.4.0: : :C: :USB Enhanced Host Controller Adapter (3310e000) Software : : : : : : :1:0:/:1937",
        "devices.pci.331121b9:devices.pci.331121b9.com:7.2.0.0: : :C: :IBM PCI 2-Port Multiprotocol Common Software : : : : : : :1:0:/:1543",
        "devices.pci.331121b9:devices.pci.331121b9.diag:7.2.3.0: : :C: :PCI 2-Port Multiprotocol Adapter (331121b9) Diagnostics : : : : : : :1:0:/:1837",
        "devices.pci.331121b9:devices.pci.331121b9.rte:7.2.3.0: : :C: :IBM PCI 2-Port Multiprotocol Device Driver : : : : : : :1:0:/:1837",
        "devices.pci.4f111100:devices.pci.4f111100.asw:7.2.0.0: : :C: :PCI 8-Port Asynchronous Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.4f111100:devices.pci.4f111100.com:7.2.3.0: : :C: :Common PCI Asynchronous Adapter Software : : : : : : :1:0:/:1837",
        "devices.pci.4f111100:devices.pci.4f111100.diag:7.2.3.0: : :C: :RISC PC PCI Async 8 Port Adapter Diagnostics : : : : : : :1:0:/:1837",
        "devices.pci.4f111100:devices.pci.4f111100.rte:7.2.0.0: : :C: :PCI 8-Port Asynchronous Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.4f111b00:devices.pci.4f111b00.asw:7.2.0.0: : :C: :PCI 128-Port Asynchronous Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.4f111b00:devices.pci.4f111b00.diag:7.2.0.0: : :C: :RISC PC PCI Async 128 Port Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.4f111b00:devices.pci.4f111b00.rte:7.2.0.0: : :C: :PCI 128-Port Asynchronous Adapter Software : : : : : : :1:0:/:1543",
        "devices.pci.4f11c800:devices.pci.4f11c800.diag:7.2.3.0: : :C: :2-port Asynchronous EIA-232 PCI Adapter Diagnostics : : : : : : :1:0:/:1837",
        "devices.pci.4f11c800:devices.pci.4f11c800.rte:7.2.4.1: : :C: :2-Port Asynchronous EIA-232 PCI Adapter Software : : : : : : :1:0:/:1937",
        "devices.pci.77101223:devices.pci.77101223.com:7.2.4.0: : :C: :PCI FC Adapter (77101223) Common Software : : : : : : :1:0:/:1937",
        "devices.pci.77101223:devices.pci.77101223.diag:7.2.4.1: : :C:F:PCI FC Adapter (77101223) Diagnostics: : : : : : :0:0:/:2015",
        "devices.pci.77101223:devices.pci.77101223.rte:7.2.0.0: : :C: :PCI FC Adapter (77101223) Runtime Software : : : : : : :1:0:/:1543",
        "devices.pci.77102224:devices.pci.77102224.com:7.2.4.0: : :C: :PCI-X FC Adapter (77102224) Common Software : : : : : : :1:0:/:1937",
        "devices.pci.77102224:devices.pci.77102224.diag:7.2.0.0: : :C: :PCI-X FC Adapter (77102224) Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.77102224:devices.pci.77102224.rte:7.2.0.0: : :C: :PCI-X FC Adapter (77102224) Runtime Software : : : : : : :1:0:/:1543",
        "devices.pci.77102e01:devices.pci.77102e01.diag:7.2.0.0: : :C: :1000 Base-TX PCI-X iSCSI TOE Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.77102e01:devices.pci.77102e01.rte:7.2.0.0: : :C: :PCI-X 1000 Base-TX iSCSI TOE Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pci.99172604:devices.pci.99172604.diag:7.2.0.0: : :C: :USB Enhanced Host Controller (99172604) Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.99172604:devices.pci.99172604.rte:7.2.3.0: : :C: :USB Enhanced Host Controller Adapter (99172604) Software : : : : : : :1:0:/:1837",
        "devices.pci.99172704:devices.pci.99172704.diag:7.2.0.0: : :C: :USB Host Controller (99172704) Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.99172704:devices.pci.99172704.rte:7.2.3.0: : :C: :USB Host Controller (99172704) Software : : : : : : :1:0:/:1837",
        "devices.pci.a8135201:devices.pci.a8135201.diag:7.2.0.0: : :C: :2-port Asynchronous EIA-232 PCI Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.a8135201:devices.pci.a8135201.rte:7.2.0.0: : :C: :Native 2-Port Asynchronous EIA-232 PCI Adapter Software : : : : : : :1:0:/:154",
        "devices.pci.c1110358:devices.pci.c1110358.diag:7.2.0.0: : :C: :USB Open Host Controller Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.c1110358:devices.pci.c1110358.rte:7.2.3.0: : :C: :USB Host Controller (c1110358) Software : : : : : : :1:0:/:1837",
        "devices.pci.df1000f7:devices.pci.df1000f7.com:7.2.4.1: : :C:F:Common PCI FC Adapter Device Software: : : : : : :0:0:/:2015",
        "devices.pci.df1000f7:devices.pci.df1000f7.diag:7.2.3.15: : :C: :PCI FC Adapter Device Diagnostics : : : : : : :1:0:/:1845",
        "devices.pci.df1000f7:devices.pci.df1000f7.rte:7.2.0.0: : :C: :PCI FC Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pci.df1000f9:devices.pci.df1000f9.diag:7.2.0.0: : :C: :64-bit PCI FC Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.df1000f9:devices.pci.df1000f9.rte:7.2.0.0: : :C: :64-bit PCI FC Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pci.df1000fa:devices.pci.df1000fa.diag:7.2.0.0: : :C: :FC PCI-X Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.df1000fa:devices.pci.df1000fa.rte:7.2.0.0: : :C: :FC PCI-X Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pci.df1000fd:devices.pci.df1000fd.diag:7.2.0.0: : :C: :FC PCI-X Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.df1000fd:devices.pci.df1000fd.rte:7.2.0.0: : :C: :4Gb PCI-X FC Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pci.df1023fd:devices.pci.df1023fd.diag:7.2.0.0: : :C: :4Gb PCI-X FC Adapter (df1023fd) Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.df1023fd:devices.pci.df1023fd.rte:7.2.0.0: : :C: :4Gb PCI-X FC Adapter (df1023fd) Device Software : : : : : : :1:0:/:1543",
        "devices.pci.df1080f9:devices.pci.df1080f9.diag:7.2.0.0: : :C: :PCI-X FC Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pci.df1080f9:devices.pci.df1080f9.rte:7.2.0.0: : :C: :PCI-X FC Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pci.e414a816:devices.pci.e414a816.diag:7.2.3.15: : :C: :Gigabit Ethernet Adapter Diagnostics : : : : : : :1:0:/:1845",
        "devices.pci.e414a816:devices.pci.e414a816.rte:7.2.3.0: : :C: :Gigabit Ethernet-SX Adapter Software : : : : : : :1:0:/:1837",
        "devices.pci.f41a0100:devices.pci.f41a0100.rte:7.2.4.0: : :C: :Virtio NIC Adapter (f41a0100) : : : : : : :1:0:/:1937",
        "devices.pci.f41a0800:devices.pci.f41a0800.rte:7.2.2.15: : :C: :Virtio SCSI Adapter (f41a0800) : : : : : : :1:0:/:1806",
        "devices.pci.pci:devices.pci.pci.rte:7.2.0.0: : :C: :PCI Bus Bridge Software (CHRP) : : : : : : :1:0:/:1543",
        "devices.pciex.001072001410ea03:devices.pciex.001072001410ea03.diag:7.2.0.0: : :C: :PCIe2 SAS Adapter Dual-port 6Gb Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.001072001410ea03:devices.pciex.001072001410ea03.rte:7.2.0.0: : :C: :PCIe2 SAS Adapter Dual-port 6Gb Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.001072001410f603:devices.pciex.001072001410f603.diag:7.2.0.0: : :C: :PCIe2 SAS Adapter Quad-port 6Gb Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.001072001410f603:devices.pciex.001072001410f603.rte:7.2.0.0: : :C: :PCIe2 SAS Adapter Quad-port 6Gb Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.14103903:devices.pciex.14103903.diag:7.2.0.0: : :C: :PCI Express 3Gb SAS RAID Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.14103903:devices.pciex.14103903.rte:7.2.0.0: : :C: :PCI Express 3GB SAS RAID Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.14103d03:devices.pciex.14103d03.diag:7.2.3.15: : :C: :PCI Express 6GB SAS RAID Adapter Diagnostics : : : : : : :1:0:/:1845",
        "devices.pciex.14103d03:devices.pciex.14103d03.rte:7.2.0.0: : :C: :PCI Express 6GB SAS RAID Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.14103f03:devices.pciex.14103f03.diag:7.2.3.15: : :C: :2-Port Gigabit Ethernet-SX PCI-Express Adapter Diagnostics : : : : : : :1:0:/:1845",
        "devices.pciex.14103f03:devices.pciex.14103f03.rte:7.2.0.0: : :C: :2-Port Gigabit Ethernet-SX PCI-Express Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.14104003:devices.pciex.14104003.diag:7.2.0.0: : :C: :2-Port 10/100/1000 Base-TX PCI-Express Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.14104003:devices.pciex.14104003.rte:7.2.0.0: : :C: :2-Port 10/100/1000 Base-TX PCI-Express Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.14104a03:devices.pciex.14104a03.diag:7.2.0.0: : :C: :PCIe3 6GB SAS RAID Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.14104a03:devices.pciex.14104a03.rte:7.2.0.0: : :C: :PCIe3 6GB SAS RAID Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.14104b0414104b04:devices.pciex.14104b0414104b04.com:7.2.4.0: : :C: :Common PCIe FPGA Accelerator Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.14104b0414104b04:devices.pciex.14104b0414104b04.diag:7.2.3.15: : :C: :PCIe FPGA Accelrator Adapter Diagnostics : : : : : : :1:0:/:1913",
        "devices.pciex.14104b0414104b04:devices.pciex.14104b0414104b04.rte:7.2.0.0: : :C: :PCIe FPGA Accelrator Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.1410660414100000:devices.pciex.1410660414100000.diag:7.2.3.0: : :C: :IBM 4767 PCIe3 Cryptographic Coprocessor (1410660414100000) Diagnostics Software : : : : : : :1:0:/:1837",
        "devices.pciex.1410660414100000:devices.pciex.1410660414100000.rte:7.2.4.1: : :C:F:IBM 4767 PCIe3 Cryptographic Coprocessor (1410660414100000) Device Software: : : : : : :0:0:/:2015",
        "devices.pciex.14106803:devices.pciex.14106803.diag:7.2.0.0: : :C: :4-Port 10/100/1000 Base-TX PCI Express Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.14106803:devices.pciex.14106803.rte:7.2.0.0: : :C: :4-Port 10/100/1000 Base-TX PCI-Express Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.14107a0314107b03:devices.pciex.14107a0314107b03.diag:7.2.4.0: : :C: :IBM Y4 PCI-E Cryptographic CoProcessor Model 4765 (14107a0314107b03) Diagnostics : : : : : : :1:0:/:1937",
        "devices.pciex.14107a0314107b03:devices.pciex.14107a0314107b03.rte:7.2.4.0: : :C: :IBM Y4 PCI-E Cryptographic Coprocessor (14107a0314107b03) Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.151438c1:devices.pciex.151438c1.diag:7.2.3.0: : :C: :PCIe Async EIA-232 Controller Diagnostics : : : : : : :1:0:/:1837",
        "devices.pciex.151438c1:devices.pciex.151438c1.rte:7.2.0.0: : :C: :PCIe Async EIA-232 Controller : : : : : : :1:0:/:1543",
        "devices.pciex.2514300014108c03:devices.pciex.2514300014108c03.diag:7.2.3.15: : :C: :10 Gigabit Ethernet-SR PCI Express Adapter Diagnostics Software (2514300014108c03) : : : : : : :1:0:/:1845",
        "devices.pciex.2514300014108c03:devices.pciex.2514300014108c03.rte:7.2.0.0: : :C: :10 Gigabit Ethernet-SR PCI-Express Host Bus Adapter : : : : : : :1:0:/:1543",
        "devices.pciex.251430001410a303:devices.pciex.251430001410a303.diag:7.2.0.0: : :C: :10 Gigabit Ethernet-CX4 PCI Express Adapter Diagnostics Software (251430001410a303) : : : : : : :1:0:/:1543",
        "devices.pciex.251430001410a303:devices.pciex.251430001410a303.rte:7.2.0.0: : :C: :10 Gigabit Ethernet-CX4 PCI-Express Host Bus Adapter : : : : : : :1:0:/:1543",
        "devices.pciex.2514310025140100:devices.pciex.2514310025140100.diag:7.2.0.0: : :C: :10 Gigabit Ethernet PCI-Express Host Bus Adapter Diagnostics Software (2514310025140100) : : : : : : :1:0:/:1543",
        "devices.pciex.2514310025140100:devices.pciex.2514310025140100.rte:7.2.0.0: : :C: :10 Gigabit Ethernet PCI-Express Host Bus Adapter : : : : : : :1:0:/:1543",
        "devices.pciex.4c10418214109e04:devices.pciex.4c10418214109e04.diag:7.2.4.0: : :C: :PCIe2 USB 3.0 xHCI 4-Port Adapter Device Diagnostics : : : : : : :1:0:/:1937",
        "devices.pciex.4c10418214109e04:devices.pciex.4c10418214109e04.rte:7.2.0.0: : :C: :PCIe2 USB 3.0 xHCI 4-Port Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.4c1041821410b204:devices.pciex.4c1041821410b204.diag:7.2.0.0: : :C: :Integrated PCIe2 USB 3.0 xHCI Controller Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.4c1041821410b204:devices.pciex.4c1041821410b204.rte:7.2.0.0: : :C: :Integrated PCIe2 USB 3.0 xHCI Controller Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.4f11f60014102204:devices.pciex.4f11f60014102204.diag:7.2.0.0: : :C: :PCIe 2-port Async EIA-232 Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.4f11f60014102204:devices.pciex.4f11f60014102204.rte:7.2.0.0: : :C: :PCIe 2-port Async EIA-232 Adapter : : : : : : :1:0:/:1543",
        "devices.pciex.771000801410b003:devices.pciex.771000801410b003.diag:7.2.0.0: : :C: :10 Gb FCoE PCI Express Dual Port Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.771000801410b003:devices.pciex.771000801410b003.rte:7.2.4.0: : :C: :10 Gb Ethernet-SR PCI Express Dual Port Adapter Software : : : : : : :1:0:/:1937",
        "devices.pciex.7710008077108001:devices.pciex.7710008077108001.diag:7.2.0.0: : :C: :10 Gb FCoE PCI Express Dual Port Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.7710008077108001:devices.pciex.7710008077108001.rte:7.2.0.0: : :C: :10 Gb Ethernet PCI Express Dual Port Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.771001801410af03:devices.pciex.771001801410af03.diag:7.2.4.0: : :C: :10 Gb FCoE PCI Express Dual Port Adapter (771001801410af03) Diagnostics : : : : : : :1:0:/:1937",
        "devices.pciex.771001801410af03:devices.pciex.771001801410af03.rte:7.2.4.0: : :C: :10 Gb FCoE PCI Express Dual Port Adapter (771001801410af03) Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.7710018077107f01:devices.pciex.7710018077107f01.diag:7.2.0.0: : :C: :10 Gb FCoE PCIe Blade Expansion Card (7710018077107f01) Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.7710018077107f01:devices.pciex.7710018077107f01.rte:7.2.0.0: : :C: :10 Gb FCoE PCIe Blade Expansion Card (7710018077107f01) Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.77103224:devices.pciex.77103224.diag:7.2.0.0: : :C: :PCI Express FC Adapter Diagnostics (77103224) : : : : : : :1:0:/:1543",
        "devices.pciex.77103224:devices.pciex.77103224.rte:7.2.0.0: : :C: :PCI Express 4Gb FC Adapter (77103224) Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.77103225141004f3:devices.pciex.77103225141004f3.diag:7.2.0.0: : :C: :8Gb 2-Port PCIe2 FC (77103225141004f3) Diagnostics Software : : : : : : :1:0:/:1614",
        "devices.pciex.77103225141004f3:devices.pciex.77103225141004f3.rte:7.2.0.0: : :C: :8Gb 2-Port PCIe2 FC (77103225141004f3) Runtime Software : : : : : : :1:0:/:1614",
        "devices.pciex.7710322514101e04:devices.pciex.7710322514101e04.diag:7.2.0.0: : :C: :Low Profile 8Gb 4-Port PCIe2 FC (7710322514101e04) Diagnostic Software : : : : : : :1:0:/:1543",
        "devices.pciex.7710322514101e04:devices.pciex.7710322514101e04.rte:7.2.4.0: : :C: :Low Profile 8Gb 4-Port PCIe2 FC (7710322514101e04) Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.7710322577106501:devices.pciex.7710322577106501.diag:7.2.0.0: : :C: :4Gb PCIe FC Blade Expansion Card (7710322577106501) Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.7710322577106501:devices.pciex.7710322577106501.rte:7.2.0.0: : :C: :4Gb PCIe FC Blade Expansion Card (7710322577106501) Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.7710322577106601:devices.pciex.7710322577106601.diag:7.2.0.0: : :C: :8Gb PCIe FC Blade Expansion Card (7710322577106601) Diagnostic Software : : : : : : :1:0:/:1543",
        "devices.pciex.7710322577106601:devices.pciex.7710322577106601.rte:7.2.0.0: : :C: :8Gb PCIe FC Blade Expansion Card (7710322577106601) Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.7710322577106801:devices.pciex.7710322577106801.diag:7.2.0.0: : :C: :8Gb PCIe FC Blade Expansion Card (7710322577106801) Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.7710322577106801:devices.pciex.7710322577106801.rte:7.2.0.0: : :C: :8Gb PCIe FC Blade Expansion Card (7710322577106801) Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.7710322577107501:devices.pciex.7710322577107501.diag:7.2.0.0: : :C: :Dual Port 8Gb FC Mezzanine Card (7710322577107501) Diagnostic Software : : : : : : :1:0:/:1543",
        "devices.pciex.7710322577107501:devices.pciex.7710322577107501.rte:7.2.0.0: : :C: :Dual Port 8Gb FC Mezzanine Card (7710322577107501) Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.7710322577107601:devices.pciex.7710322577107601.diag:7.2.0.0: : :C: :8Gb PCIe FC Blade Expansion Card (7710322577107601) Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.7710322577107601:devices.pciex.7710322577107601.rte:7.2.0.0: : :C: :8Gb PCIe FC Blade Expansion Card (7710322577107601) Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.7710612214105006:devices.pciex.7710612214105006.com:7.2.4.0: : :C: :Common PCIe3 FC Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.7710612214105006:devices.pciex.7710612214105006.diag:7.2.4.1: : :C:F:16Gb FC PCIe3 2 Ports (7710612214105006) Diagnostic Software: : : : : : :0:0:/:2015",
        "devices.pciex.7710612214105006:devices.pciex.7710612214105006.rte:7.2.4.0: : :C: :16Gb FC PCIe3 2 Port Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.8680c71014108003:devices.pciex.8680c71014108003.diag:7.2.3.15: : :C: :10 Gigabit Ethernet-LR PCI-Express Adapter Diagnostics : : : : : : :1:0:/:1845",
        "devices.pciex.8680c71014108003:devices.pciex.8680c71014108003.rte:7.2.3.16: : :C: :10 Gigabit Ethernet-LR PCI-Express Adapter Software : : : : : : :1:0:/:1913",
        "devices.pciex.a219100714100904:devices.pciex.a219100714100904.diag:7.2.0.0: : :C: :Int Multifunction Card w/ SR Optical 10GbE Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.a219100714100904:devices.pciex.a219100714100904.rte:7.2.0.0: : :C: :Int Multifunction Card w/ SR Optical 10GbE Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.a219100714100a04:devices.pciex.a219100714100a04.diag:7.2.0.0: : :C: :Int Multifunction Card w/ Copper SFP+ 10GbE Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.a219100714100a04:devices.pciex.a219100714100a04.rte:7.2.0.0: : :C: :Int Multifunction Card w/ Copper SFP+ 10GbE Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.a21910071410d003:devices.pciex.a21910071410d003.diag:7.2.3.15: : :C: :PCIe2 2-port 10GbE SR Adapter Diagnostics : : : : : : :1:0:/:1845",
        "devices.pciex.a21910071410d003:devices.pciex.a21910071410d003.rte:7.2.3.0: : :C: :PCIe2 2-port 10GbE SR Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.a21910071410d103:devices.pciex.a21910071410d103.diag:7.2.0.0: : :C: :PCIe2 2-port 10GbE SFP Copper Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.a21910071410d103:devices.pciex.a21910071410d103.rte:7.2.0.0: : :C: :PCIe2 2-port 10GbE SFP+Copper Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.a21910071410d203:devices.pciex.a21910071410d203.diag:7.2.0.0: : :C: :Int Multifunction Card w/ Base-TX Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.a21910071410d203:devices.pciex.a21910071410d203.rte:7.2.0.0: : :C: :Int Multifunction Card w/ Base-TX 10/100/1000 1GbE Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.a2191007df1033e7:devices.pciex.a2191007df1033e7.diag:7.2.0.0: : :C: :10GbE 4 port PCIe2 Mezz Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.a2191007df1033e7:devices.pciex.a2191007df1033e7.rte:7.2.0.0: : :C: :10GbE 4-port PCIe2 Mezz Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.b31503101410b504:devices.pciex.b31503101410b504.diag:7.2.0.0: : :C: :RoCE Host Bus Adapter Diagnostics (b31503101410b504) : : : : : : :1:0:/:1543",
        "devices.pciex.b31503101410b504:devices.pciex.b31503101410b504.rte:7.2.1.0: : :C: :RoCE Host Bus Adapter (b31503101410b504) : : : : : : :1:0:/:1642",
        "devices.pciex.b31507101410e704:devices.pciex.b31507101410e704.diag:7.2.0.0: : :C: :RoCE Host Bus Adapter Diagnostics (b31507101410e704) : : : : : : :1:0:/:1543",
        "devices.pciex.b31507101410e704:devices.pciex.b31507101410e704.rte:7.2.3.0: : :C: :RoCE Host Bus Adapter (b31507101410e704) : : : : : : :1:0:/:1837",
        "devices.pciex.b31507101410eb04:devices.pciex.b31507101410eb04.diag:7.2.0.0: : :C: :RoCE Host Bus Adapter Diagnostics (b31507101410eb04) : : : : : : :1:0:/:1543",
        "devices.pciex.b31507101410eb04:devices.pciex.b31507101410eb04.rte:7.2.3.0: : :C: :RoCE Host Bus Adapter (b31507101410eb04) : : : : : : :1:0:/:1837",
        "devices.pciex.b31513101410f704:devices.pciex.b31513101410f704.diag:7.2.4.0: : :C: :100Gbit RoCE PCIe3 Adapter Diagnostics (b31513101410f704) : : : : : : :1:0:/:1937",
        "devices.pciex.b31513101410f704:devices.pciex.b31513101410f704.rte:7.2.4.0: : :C: :PCIe3 100Gbit 2-port RoCE Adapter Software : : : : : : :1:0:/:1937",
        "devices.pciex.b31514101410f704:devices.pciex.b31514101410f704.diag:7.2.2.15: : :C: :PCIe3 100Gbit 2-port RoCE Adapter Diagnostics : : : : : : :1:0:/:1806",
        "devices.pciex.b31514101410f704:devices.pciex.b31514101410f704.rte:7.2.4.0: : :C: :PCIe3 100Gbit 2-port RoCE Adapter Software : : : : : : :1:0:/:1937",
        "devices.pciex.b315151014101e06:devices.pciex.b315151014101e06.diag:7.2.4.0: : :C: :PCIe3 25Gbit 2-port RoCE Adapter Diagnostics : : : : : : :1:0:/:1937",
        "devices.pciex.b315151014101e06:devices.pciex.b315151014101e06.rte:7.2.4.0: : :C: :PCIe3 25Gbit 2-port RoCE Adapter Software : : : : : : :1:0:/:1937",
        "devices.pciex.b315151014101f06:devices.pciex.b315151014101f06.diag:7.2.4.0: : :C: :PCIe3 10Gbit 2-port RoCE Adapter Diagnostics : : : : : : :1:0:/:1937",
        "devices.pciex.b315151014101f06:devices.pciex.b315151014101f06.rte:7.2.4.0: : :C: :PCIe3 10Gbit 2-port RoCE Adapter Software : : : : : : :1:0:/:1937",
        "devices.pciex.b315161014101e06:devices.pciex.b315161014101e06.diag:7.2.2.15: : :C: :PCIe3 25Gbit 2-port RoCE Adapter VF Diagnostics : : : : : : :1:0:/:1806",
        "devices.pciex.b315161014101e06:devices.pciex.b315161014101e06.rte:7.2.4.0: : :C: :PCIe3 25Gbit 2-port RoCE Adapter VF Software : : : : : : :1:0:/:1937",
        "devices.pciex.b315161014101f06:devices.pciex.b315161014101f06.diag:7.2.2.15: : :C: :PCIe3 10Gbit 2-port RoCE Adapter VF Diagnostics : : : : : : :1:0:/:1806",
        "devices.pciex.b315161014101f06:devices.pciex.b315161014101f06.rte:7.2.4.0: : :C: :PCIe3 10Gbit 2-port RoCE Adapter VF Software : : : : : : :1:0:/:1937",
        "devices.pciex.b315191014103506:devices.pciex.b315191014103506.diag:7.2.4.0: : :C: :2-port 100Gbit RoCE PCIe4 Adapter Diagnostics Software : : : : : : :1:0:/:1937",
        "devices.pciex.b315191014103506:devices.pciex.b315191014103506.rte:7.2.4.0: : :C: :PCIe4 100Gbit 2-port RoCE Adapter Software : : : : : : :1:0:/:1937",
        "devices.pciex.b3151a1014103506:devices.pciex.b3151a1014103506.diag:7.2.3.15: : :C: :2-port 100Gbit RoCE PCIe4 Adapter Diagnostics Software : : : : : : :1:0:/:1913",
        "devices.pciex.b3151a1014103506:devices.pciex.b3151a1014103506.rte:7.2.3.15: : :C: :PCIe4 100Gbit 2-port RoCE Adapter Software : : : : : : :1:0:/:1913",
        "devices.pciex.b3153c67:devices.pciex.b3153c67.diag:7.2.0.0: : :C: :PCIe Dual Port HCA QDR Infiniband Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.b3153c67:devices.pciex.b3153c67.rte:7.2.0.0: : :C: :4X PCI-E QDR Infiniband Device Driver : : : : : : :1:0:/:1543",
        "devices.pciex.b3154a63:devices.pciex.b3154a63.diag:7.2.4.1: : :C:F:PCI-E 4X DDR Infiniband Device Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.b3154a63:devices.pciex.b3154a63.rte:7.2.4.0: : :C: :4X PCI-E DDR Infiniband Device Driver : : : : : : :1:0:/:1937",
        "devices.pciex.b315506714101604:devices.pciex.b315506714101604.diag:7.2.0.0: : :C: :RoCE Host Bus Adapter Diagnostics (b315506714101604) : : : : : : :1:0:/:1543",
        "devices.pciex.b315506714101604:devices.pciex.b315506714101604.rte:7.2.1.0: : :C: :RoCE Host Bus Adapter (b315506714101604) : : : : : : :1:0:/:1642",
        "devices.pciex.b315506714106104:devices.pciex.b315506714106104.diag:7.2.0.0: : :C: :RoCE Host Bus Adapter Diagnostics (b315506714106104) : : : : : : :1:0:/:1543",
        "devices.pciex.b315506714106104:devices.pciex.b315506714106104.rte:7.2.1.0: : :C: :RoCE Host Bus Adapter (b315506714106104) : : : : : : :1:0:/:1642",
        "devices.pciex.b3155067b3157265:devices.pciex.b3155067b3157265.diag:7.2.0.0: : :C: :RoCE Host Bus Adapter Diagnostics (b3155067b3157265) : : : : : : :1:0:/:1543",
        "devices.pciex.b3155067b3157265:devices.pciex.b3155067b3157265.rte:7.2.1.0: : :C: :RoCE Host Bus Adapter (b3155067b3157265) : : : : : : :1:0:/:1642",
        "devices.pciex.b3155067b3157365:devices.pciex.b3155067b3157365.diag:7.2.0.0: : :C: :RoCE Host Bus Adapter Diagnostics (b3155067b3157365) : : : : : : :1:0:/:1543",
        "devices.pciex.b3155067b3157365:devices.pciex.b3155067b3157365.rte:7.2.1.0: : :C: :RoCE Host Bus Adapter (b3155067b3157365) : : : : : : :1:0:/:1642",
        "devices.pciex.df1000e214105e04:devices.pciex.df1000e214105e04.diag:7.2.0.0: : :C: :GX++ 16Gb FC 2 Port Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1000e214105e04:devices.pciex.df1000e214105e04.rte:7.2.0.0: : :C: :GX++ 16Gb FC 2 Port Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.df1000e21410f103:devices.pciex.df1000e21410f103.diag:7.2.0.0: : :C: :16Gb FC PCIe2 2 Port Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1000e21410f103:devices.pciex.df1000e21410f103.rte:7.2.4.0: : :C: :16Gb FC PCIe2 2 Port Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.df1000e2df1002e2:devices.pciex.df1000e2df1002e2.diag:7.2.0.0: : :C: :PCIe2 2-Port 16Gb FC Mezzanine Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1000e2df1002e2:devices.pciex.df1000e2df1002e2.rte:7.2.0.0: : :C: :PCIe2 2-Port 16Gb FC Mezzanine Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.df1000e2df1082e2:devices.pciex.df1000e2df1082e2.diag:7.2.0.0: : :C: :4-Port 16Gb FC Mezzanine Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1000e2df1082e2:devices.pciex.df1000e2df1082e2.rte:7.2.0.0: : :C: :4-Port 16Gb FC Mezzanine Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.df1000e314101406:devices.pciex.df1000e314101406.diag:7.2.3.15: : :C: :16Gb FC PCIe3 4 Port Adapter Diagnostics : : : : : : :1:0:/:1913",
        "devices.pciex.df1000e314101406:devices.pciex.df1000e314101406.rte:7.2.4.0: : :C: :16Gb FC PCIe3 4 Port Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.df1000e314101506:devices.pciex.df1000e314101506.diag:7.2.3.15: : :C: :32Gb FC PCIe3 2 Port Adapter Diagnostics : : : : : : :1:0:/:1913",
        "devices.pciex.df1000e314101506:devices.pciex.df1000e314101506.rte:7.2.4.1: : :C:F:32Gb FC PCIe3 2 Port Adapter Device Software: : : : : : :0:0:/:2015",
        "devices.pciex.df1000f114100104:devices.pciex.df1000f114100104.diag:7.2.0.0: : :C: :8Gb FC PCI Express Quad Port Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1000f114100104:devices.pciex.df1000f114100104.rte:7.2.4.0: : :C: :8Gb FC PCI Express Quad Port Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.df1000f114108a03:devices.pciex.df1000f114108a03.diag:7.2.0.0: : :C: :8Gb PCI-E FC Adapter (df1000f114108a03) Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1000f114108a03:devices.pciex.df1000f114108a03.rte:7.2.4.0: : :C: :8Gb FC PCI Express Dual Port Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.df1000f1df1024f1:devices.pciex.df1000f1df1024f1.diag:7.2.0.0: : :C: :8Gb PCI-E FC Adapter (df1000f1df1024f1) Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1000f1df1024f1:devices.pciex.df1000f1df1024f1.rte:7.2.0.0: : :C: :8Gb PCIe FC Blade Expansion Card (df1000f1df1024f1) Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.df1000fe:devices.pciex.df1000fe.diag:7.2.0.0: : :C: :4Gb FC PCI Express Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1000fe:devices.pciex.df1000fe.rte:7.2.0.0: : :C: :4Gb FC PCI Express Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.df1020e214100f04:devices.pciex.df1020e214100f04.diag:7.2.4.1: : :C:F:PCIe2 10GbE SFP+ SR Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1020e214100f04:devices.pciex.df1020e214100f04.rte:7.2.3.15: : :C: :PCIe3 10GbE SFP+ SR Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e214103604:devices.pciex.df1020e214103604.diag:7.2.4.1: : :C:F:PCIe2 10GbE SFP+ SR 4-port Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1020e214103604:devices.pciex.df1020e214103604.rte:7.2.3.15: : :C: :PCIe2 10GbE SFP+ SR 4-port Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e214103804:devices.pciex.df1020e214103804.diag:7.2.0.0: : :C: :PCIe2 10GBaseT 4-port Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1020e214103804:devices.pciex.df1020e214103804.rte:7.2.3.15: : :C: :PCIe2 10GBaseT 4-port Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e214103904:devices.pciex.df1020e214103904.diag:7.2.0.0: : :C: :PCIe2 10GbE SFP+ Cu 4-port Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1020e214103904:devices.pciex.df1020e214103904.rte:7.2.3.15: : :C: :PCIe2 10GbE SFP+ Cu 4-port Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e214103b04:devices.pciex.df1020e214103b04.diag:7.2.0.0: : :C: :PCIe2 10GBaseT 4-port Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1020e214103b04:devices.pciex.df1020e214103b04.rte:7.2.3.15: : :C: :PCIe2 10GBaseT 4-port Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e214103c04:devices.pciex.df1020e214103c04.diag:7.2.4.1: : :C:F:PCIe2 10/100/1000 Base-TX Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1020e214103c04:devices.pciex.df1020e214103c04.rte:7.2.3.15: : :C: :PCIe3 10/100/1000 Base-TX Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e214103d04:devices.pciex.df1020e214103d04.diag:7.2.4.1: : :C:F:PCIe2 10GbE SFP+ Cu 4-port Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1020e214103d04:devices.pciex.df1020e214103d04.rte:7.2.3.15: : :C: :PCIe3 10GbE SFP+ Cu Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e214103f04:devices.pciex.df1020e214103f04.diag:7.2.4.1: : :C:F:PCIe2 1GbaseT SFP+ Cu 4-port Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1020e214103f04:devices.pciex.df1020e214103f04.rte:7.2.3.15: : :C: :PCIe3 100/1000 Base-TX Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e214104004:devices.pciex.df1020e214104004.diag:7.2.4.1: : :C:F:PCIe2 10GbE SFP+ LR 4-port Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1020e214104004:devices.pciex.df1020e214104004.rte:7.2.3.15: : :C: :PCIe3 10GbE SFP+ LR Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e214104204:devices.pciex.df1020e214104204.diag:7.2.4.1: : :C:F:PCIe2 100/1000 Base-TX Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1020e214104204:devices.pciex.df1020e214104204.rte:7.2.3.15: : :C: :PCIe3 100/1000 Base-TX Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e214105104:devices.pciex.df1020e214105104.diag:7.2.0.0: : :C: :PCIe2 10GbE Mezz Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1020e214105104:devices.pciex.df1020e214105104.rte:7.2.3.15: : :C: :PCIe2 10GbE Mezz Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e214105d04:devices.pciex.df1020e214105d04.diag:7.2.0.0: : :C: :PCIe2 10GbE 2-port GX++ Gen2 Converged Network Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1020e214105d04:devices.pciex.df1020e214105d04.rte:7.2.3.15: : :C: :PCIe2 10GbE 2-port GX++ Gen2 Converged Network Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e21410e304:devices.pciex.df1020e21410e304.diag:7.2.4.1: : :C:F:PCIe3 4-Port 10GbE SR Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1020e21410e304:devices.pciex.df1020e21410e304.rte:7.2.3.15: : :C: :PCIe3 4-Port 10GbE SR Adapter : : : : : : :1:0:/:1845",
        "devices.pciex.df1020e21410e404:devices.pciex.df1020e21410e404.diag:7.2.4.1: : :C:F:PCIe3 4-Port 10GbE CU Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1020e21410e404:devices.pciex.df1020e21410e404.rte:7.2.3.15: : :C: :PCIe3 4-Port 10GbE CU Adapter : : : : : : :1:0:/:1845",
        "devices.pciex.df1028e214100f04:devices.pciex.df1028e214100f04.diag:7.2.0.0: : :C: :PCIe2 10GbE SFP+ SR VF Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1028e214100f04:devices.pciex.df1028e214100f04.rte:7.2.3.0: : :C: :PCIe2 10GbE SFP+ SR VF Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.df1028e214103604:devices.pciex.df1028e214103604.diag:7.2.0.0: : :C: :PCIe2 10GbE SFP+ SR 4-port VF Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1028e214103604:devices.pciex.df1028e214103604.rte:7.2.3.0: : :C: :PCIe2 10GbE SFP+ SR 4-port VF Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.df1028e214103804:devices.pciex.df1028e214103804.diag:7.2.0.0: : :C: :PCIe2 10GBaseT 4-port VF Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1028e214103804:devices.pciex.df1028e214103804.rte:7.2.3.0: : :C: :PCIe2 10GBaseT 4-port VF Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.df1028e214103904:devices.pciex.df1028e214103904.diag:7.2.0.0: : :C: :PCIe2 10GbE SFP+ Cu 4-port VF Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1028e214103904:devices.pciex.df1028e214103904.rte:7.2.3.0: : :C: :PCIe2 10GbE SFP+ Cu 4-port VF Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.df1028e214103b04:devices.pciex.df1028e214103b04.diag:7.2.0.0: : :C: :PCIe2 10GBaseT 4-port VF Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1028e214103b04:devices.pciex.df1028e214103b04.rte:7.2.3.0: : :C: :PCIe2 10GBaseT 4-port VF Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.df1028e214103c04:devices.pciex.df1028e214103c04.diag:7.2.0.0: : :C: :PCIe2 10/100/1000 Base-TX VF Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1028e214103c04:devices.pciex.df1028e214103c04.rte:7.2.3.0: : :C: :PCIe2 10/100/1000 Base-TX VF Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.df1028e214103d04:devices.pciex.df1028e214103d04.diag:7.2.4.1: : :C:F:PCIe2 10GbE SFP+ Cu 4-port VF Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1028e214103d04:devices.pciex.df1028e214103d04.rte:7.2.3.0: : :C: :PCIe2 10GbE SFP+ Cu VF Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.df1028e214103f04:devices.pciex.df1028e214103f04.diag:7.2.0.0: : :C: :PCIe2 1GbaseT SFP+ Cu 4-port VF Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1028e214103f04:devices.pciex.df1028e214103f04.rte:7.2.3.0: : :C: :PCIe2 100/1000 Base-TX VF Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.df1028e214104004:devices.pciex.df1028e214104004.diag:7.2.4.1: : :C:F:PCIe2 10GbE SFP+ LR VF Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1028e214104004:devices.pciex.df1028e214104004.rte:7.2.3.0: : :C: :PCIe2 10GbE SFP+ LR VF Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.df1028e214104204:devices.pciex.df1028e214104204.diag:7.2.0.0: : :C: :PCIe2 100/1000 Base-TX VF Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1028e214104204:devices.pciex.df1028e214104204.rte:7.2.3.0: : :C: :PCIe2 100/1000 Base-TX VF Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.df1028e21410e304:devices.pciex.df1028e21410e304.diag:7.2.4.1: : :C:F:PCIe3 4-Port 10GbE SR VF Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1028e21410e304:devices.pciex.df1028e21410e304.rte:7.2.3.15: : :C: :PCIe3 4-Port 10GbE SR VF Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1028e21410e404:devices.pciex.df1028e21410e404.diag:7.2.4.1: : :C:F:PCIe3 4-Port 10GbE CU VF Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1028e21410e404:devices.pciex.df1028e21410e404.rte:7.2.3.15: : :C: :PCIe3 4-Port 10GbE CU VF Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.df1060e214101004:devices.pciex.df1060e214101004.diag:7.2.0.0: : :C: :PCIe2 10GbE FCoE 4 Port Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1060e214101004:devices.pciex.df1060e214101004.rte:7.2.4.0: : :C: :10Gb FCoE PCIe2 4 Port Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.df1060e214103404:devices.pciex.df1060e214103404.com:7.2.4.1: : :C:F:Common PCIe3 FC Adapter Device Software: : : : : : :0:0:/:2015",
        "devices.pciex.df1060e214103404:devices.pciex.df1060e214103404.diag:7.2.4.2: : :C:F:PCIe2 10Gb 4-Port FCoE Mezzanine Adapter Device Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.df1060e214103404:devices.pciex.df1060e214103404.rte:7.2.0.0: : :C: :PCIe3 10Gb 4-Port FCoE Mezzanine Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.df1060e214103704:devices.pciex.df1060e214103704.diag:7.2.0.0: : :C: :Integrated 10Gb 4-Port FCoE Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1060e214103704:devices.pciex.df1060e214103704.rte:7.2.4.0: : :C: :Integrated 10Gb 4-Port FCoE Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.df1060e214103a04:devices.pciex.df1060e214103a04.diag:7.2.0.0: : :C: :Integrated 10Gb Cu 4-Port FCoE Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1060e214103a04:devices.pciex.df1060e214103a04.rte:7.2.4.0: : :C: :Integrated 10Gb Cu 4-Port FCoE Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.df1060e214103e04:devices.pciex.df1060e214103e04.diag:7.2.0.0: : :C: :PCIe2 10GbE Cu 4-port FCoE Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1060e214103e04:devices.pciex.df1060e214103e04.rte:7.2.4.0: : :C: :PCIe2 10Gb Cu 4-Port FCoE Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.df1060e214104104:devices.pciex.df1060e214104104.diag:7.2.0.0: : :C: :PCIe2 10Gb LR 4-Port FCoE Adapter Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1060e214104104:devices.pciex.df1060e214104104.rte:7.2.4.0: : :C: :PCIe2 10Gb LR 4-Port FCoE Adapter Device Software : : : : : : :1:0:/:1937",
        "devices.pciex.df1060e214105204:devices.pciex.df1060e214105204.diag:7.2.0.0: : :C: :PCIe2 10GbE FCoE Mezz Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1060e214105204:devices.pciex.df1060e214105204.rte:7.2.0.0: : :C: :PCIe2 10Gb FCoE Mezzanine Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.df1060e214105f04:devices.pciex.df1060e214105f04.diag:7.2.0.0: : :C: :GX++ 10Gb FCoE Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.df1060e214105f04:devices.pciex.df1060e214105f04.rte:7.2.0.0: : :C: :GX++ 10Gb FCoE Adapter Device Software : : : : : : :1:0:/:1543",
        "devices.pciex.e4143a161410a003:devices.pciex.e4143a161410a003.diag:7.2.0.0: : :C: :2-Port Gigabit Ethernet Combo PCI-Express Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.e4143a161410a003:devices.pciex.e4143a161410a003.rte:7.2.0.0: : :C: :2-Port Gigabit Ethernet Combo PCI-Express Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.e4143a161410ed03:devices.pciex.e4143a161410ed03.diag:7.2.0.0: : :C: :2-Port Integrated Gigabit Ethernet PCI-Express Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.e4143a161410ed03:devices.pciex.e4143a161410ed03.rte:7.2.0.0: : :C: :2-Port Integrated Gigabit Ethernet PCI-Express Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.e4143a16e4140909:devices.pciex.e4143a16e4140909.diag:7.2.0.0: : :C: :2-Port Gigabit Ethernet PCI-Express Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.e4143a16e4140909:devices.pciex.e4143a16e4140909.rte:7.2.0.0: : :C: :2-Port Gigabit Ethernet PCI-Express Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.e4143a16e4143009:devices.pciex.e4143a16e4143009.diag:7.2.3.15: : :C: :4-Port Gigabit Ethernet PCI-Express Adapter Diagnostics : : : : : : :1:0:/:1845",
        "devices.pciex.e4143a16e4143009:devices.pciex.e4143a16e4143009.rte:7.2.3.0: : :C: :4-Port Gigabit Ethernet PCI-Express Adapter Software : : : : : : :1:0:/:1837",
        "devices.pciex.e4145616e4140518:devices.pciex.e4145616e4140518.diag:7.2.3.15: : :C: :2-Port Gigabit Ethernet PCI-Express Adapter Diagnostics : : : : : : :1:0:/:1845",
        "devices.pciex.e4145616e4140518:devices.pciex.e4145616e4140518.rte:7.2.4.0: : :C: :2-Port Gigabit Ethernet PCI-Express Adapter Software : : : : : : :1:0:/:1937",
        "devices.pciex.e4145616e4140528:devices.pciex.e4145616e4140528.diag:7.2.0.0: : :C: :2-Port Gigabit Ethernet PCI-Express Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.e4145616e4140528:devices.pciex.e4145616e4140528.rte:7.2.3.15: : :C: :2-Port Gigabit Ethernet PCI-Express Adapter Software : : : : : : :1:0:/:1845",
        "devices.pciex.e414571614102004:devices.pciex.e414571614102004.diag:7.2.0.0: : :C: :4-Port Gigabit Ethernet PCI-Express Adapter Diagnostics : : : : : : :1:0:/:1543",
        "devices.pciex.e414571614102004:devices.pciex.e414571614102004.rte:7.2.0.0: : :C: :4-Port Gigabit Ethernet PCI-Express Adapter Software : : : : : : :1:0:/:1543",
        "devices.pciex.e4148a1614109304:devices.pciex.e4148a1614109304.diag:7.2.4.1: : :C:F:PCIe2 4-Port (10GbE SFP+ & 1GbE RJ45) Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.e4148a1614109304:devices.pciex.e4148a1614109304.rte:7.2.3.15: : :C: :PCIe2 4-Port (10GbE SFP+ & 1GbE RJ45) Adapter : : : : : : :1:0:/:1845",
        "devices.pciex.e4148a1614109404:devices.pciex.e4148a1614109404.diag:7.2.4.1: : :C:F:PCIe2 4-Port (10GbE SFP+ & 1GbE RJ45) Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.e4148a1614109404:devices.pciex.e4148a1614109404.rte:7.2.3.15: : :C: :PCIe2 4-Port (10GbE SFP+ & 1GbE RJ45) Adapter : : : : : : :1:0:/:1845",
        "devices.pciex.e4148e1614109204:devices.pciex.e4148e1614109204.diag:7.2.4.1: : :C:F:PCIe2 2-Port 10GbE Base-T Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.e4148e1614109204:devices.pciex.e4148e1614109204.rte:7.2.3.15: : :C: :PCIe2 2-Port 10GbE Base-T Adapter : : : : : : :1:0:/:1845",
        "devices.pciex.pciexclass.010802:devices.pciex.pciexclass.010802.diag:7.2.4.1: : :C:F:PCIe NVMe Adapter Diagnostics: : : : : : :0:0:/:2015",
        "devices.pciex.pciexclass.010802:devices.pciex.pciexclass.010802.rte:7.2.4.1: : :C:F:PCIe NVMe Adapter Software: : : : : : :0:0:/:2015",
        "devices.sas:devices.sas.diag:7.2.3.15: : :C: :Serial Attached SCSI Device Diagnostics : : : : : : :1:0:/:1845",
        "devices.sas:devices.sas.rte:7.2.4.0: : :C: :Serial Attached SCSI Device Software : : : : : : :1:0:/:1937",
        "devices.sata:devices.sata.diag:7.2.0.0: : :C: :Serial ATA Device Diagnostics : : : : : : :1:0:/:1543",
        "devices.sata:devices.sata.rte:7.2.0.0: : :C: :Serial ATA Device Software : : : : : : :1:0:/:1543",
        "devices.scsi.disk:devices.scsi.disk.diag.com:7.2.4.1: : :C:F:Common Disk Diagnostic Service Aid: : : : : : :0:0:/:2015",
        "devices.scsi.disk:devices.scsi.disk.diag.rte:7.2.2.0: : :C: :SCSI CD_ROM, Disk Device Diagnostics : : : : : : :1:0:/:1731",
        "devices.scsi.disk:devices.scsi.disk.rspc:7.2.0.0: : :C: :RISC PC SCSI CD-ROM, Disk, Read/Write Optical Software : : : : : : :1:0:/:1543",
        "devices.scsi.disk:devices.scsi.disk.rte:7.2.4.0: : :C: :SCSI CD-ROM, Disk, Read/Write Optical Device Software : : : : : : :1:0:/:1937",
        "devices.scsi.ses:devices.scsi.ses.diag:7.2.4.0: : :C: :SCSI Enclosure Services Device Diagnostics : : : : : : :1:0:/:1937",
        "devices.scsi.ses:devices.scsi.ses.rte:7.2.4.0: : :C: :SCSI Enclosure Device Software : : : : : : :1:0:/:1937",
        "devices.scsi.tape:devices.scsi.tape.diag:7.2.4.0: : :C: :SCSI Tape Device Diagnostics : : : : : : :1:0:/:1937",
        "devices.scsi.tape:devices.scsi.tape.rspc:7.2.0.0: : :C: :RISC PC SCSI Tape Device Software : : : : : : :1:0:/:1543",
        "devices.scsi.tape:devices.scsi.tape.rte:7.2.4.0: : :C: :SCSI Tape Device Software : : : : : : :1:0:/:1937",
        "devices.scsi.tm:devices.scsi.tm.rte:7.2.4.0: : :C: :SCSI Target Mode Software : : : : : : :1:0:/:1937",
        "devices.serial.sb1:devices.serial.sb1.X11:7.2.0.0: : :C: :AIXwindows 6094-030 Spaceball 3-D Input Device Software : : : : : : :1:0:/:1543",
        "devices.serial.tablet1:devices.serial.tablet1.X11:7.2.0.0: : :C: :AIXwindows Serial Tablet Input Device Software : : : : : : :1:0:/:1543",
        "devices.tty:devices.tty.rte:7.2.4.1: : :C:F:TTY Device Driver Support Software: : : : : : :0:0:/:2015",
        "devices.usbif.010100:devices.usbif.010100.rte:7.2.4.0: : :C: :USB Audio Device Driver : : : : : : :1:0:/:1937",
        "devices.usbif.03000008:devices.usbif.03000008.rte:7.2.4.0: : :C: :USB 3D Mouse Client Driver : : : : : : :1:0:/:1937",
        "devices.usbif.030101:devices.usbif.030101.rte:7.2.4.0: : :C: :USB Keyboard Client Driver : : : : : : :1:0:/:1937",
        "devices.usbif.030102:devices.usbif.030102.rte:7.2.4.0: : :C: :USB Mouse Client Driver : : : : : : :1:0:/:1937",
        "devices.usbif.08025002:devices.usbif.08025002.diag:7.2.3.15: : :C: :USB Mass Storage Diagnostics : : : : : : :1:0:/:1845",
        "devices.usbif.08025002:devices.usbif.08025002.rte:7.2.4.0: : :C: :USB Mass Storage Device Software : : : : : : :1:0:/:1937",
        "devices.usbif.080400:devices.usbif.080400.diag:7.2.0.0: : :C: :USB Diskette Diagnostics : : : : : : :1:0:/:1543",
        "devices.usbif.080400:devices.usbif.080400.rte:7.2.4.0: : :C: :USB Diskette Client Driver : : : : : : :1:0:/:1937",
        "devices.usbif.usblibke:devices.usbif.usblibke.rte:7.2.4.0: : :C: :LIBUSB Device Support Software : : : : : : :1:0:/:1937",
        "devices.vdevice.IBM.l-lan:devices.vdevice.IBM.l-lan.rte:7.2.4.2: : :C:F:Virtual I/O Ethernet Software: : : : : : :0:0:/:2015",
        "devices.vdevice.IBM.v-scsi:devices.vdevice.IBM.v-scsi.rte:7.2.4.1: : :C: :Virtual SCSI Client Support : : : : : : :1:0:/:1937",
        "devices.vdevice.IBM.vfc-client:devices.vdevice.IBM.vfc-client.rte:7.2.4.3: : :C:F:Virtual Fibre Channel Client Support: : : : : : :0:0:/:2015",
        "devices.vdevice.IBM.vnic:devices.vdevice.IBM.vnic.rte:7.2.4.2: : :C:F:Virtual NIC Client Software: : : : : : :0:0:/:2015",
        "devices.vdevice.hvterm-protocol:devices.vdevice.hvterm-protocol.rte:7.2.0.0: : :C: :Virtual Terminal Physical Support : : : : : : :1:0:/:1543",
        "devices.vdevice.hvterm1:devices.vdevice.hvterm1.rte:7.2.3.0: : :C: :Virtual Terminal Devices : : : : : : :1:0:/:1837",
        "devices.vdevice.vty-server:devices.vdevice.vty-server.rte:7.2.4.0: : :C: :Virtual Terminal Devices : : : : : : :1:0:/:1937",
        "devices.virtio:devices.virtio.core.rte:7.2.4.0: : :C: :Virtio Core Device Software : : : : : : :1:0:/:1937",
        "devices.virtio:devices.virtio.ethernet.rte:7.2.4.0: : :C: :Virtio Ethernet Device Software : : : : : : :1:0:/:1937",
        "devices.virtio:devices.virtio.scsi.rte:7.2.4.0: : :C: :virtio SCSI Adapter Device Software : : : : : : :1:0:/:1937",
        "expect.base:expect.base:5.42.1.1: : :C: :Binary executable files of Expect: : : : : : :0:0:/:",
        "idsldap.clt32bit64:idsldap.clt32bit64.rte:6.4.0.15: : :C: :Directory Server - 32 bit Client: : : : : : :0:0:/:",
        "idsldap.clt_max_crypto32bit64:idsldap.clt_max_crypto32bit64.rte:6.4.0.15: : :C: :Directory Server - 32 bit Client (SSL): : : : : : :0:0:/:",
        "idsldap.cltbase64:idsldap.cltbase64.adt:6.4.0.15: : :C: :Directory Server - Base Client: : : : : : :0:0:/:",
        "idsldap.cltbase64:idsldap.cltbase64.rte:6.4.0.15: : :C: :Directory Server - Base Client: : : : : : :0:0:/:",
        "idsldap.license64:idsldap.license64.rte:6.4.0.15: : :C: :Directory Server - License: : : : : : :0:0:/:",
        "invscout.com:invscout.com:2.2.0.1: : :C: :Inventory Scout Microcode Catalog: : : : : : :1:0:/:",
        "invscout.ldb:invscout.ldb:2.2.0.2: : :C: :Inventory Scout Logic Database: : : : : : :1:0:/:",
        "invscout.rte:invscout.rte:2.2.0.20: : :C: :Inventory Scout Runtime: : : : : : :1:0:/:",
        "krb5.client:krb5.client.rte:1.16.1.2: : :C: :Network Authentication Service Client: : : : : : :0:0:/:",
        "krb5.client:krb5.client.samples:1.16.1.2: : :C: :Network Authentication Service Samples: : : : : : :0:0:/:",
        "krb5.lic:krb5.lic:1.16.1.2: : :C: :Network Authentication Service License: : : : : : :0:0:/:",
        "krb5.toolkit:krb5.toolkit.adt:1.16.1.2: : :C: :Network Authentication Service App. Dev. Toolkit: : : : : : :0:0:/:",
        "libc++.rte:libc++.rte:16.1.0.3: : :C: :IBM XL C++ Runtime for AIX 7.1 and later : : : : : : :0:0:/:",
        "mcr.rte:mcr.rte:7.2.4.1: : :C:F:Metacluster Checkpoint and Restart: : : : : : :0:0:/:2015",
        "memdbg.adt:memdbg.adt:5.5.0.1: : :C: :User Heap/Memory Debug Toolkit : : : : : : :0:0:/:",
        "memdbg.aix53:memdbg.aix53.adt:5.5.0.1: : :C: :User Heap/Memory Debug Toolkit for AIX 5.3 : : : : : : :0:0:/:",
        "memdbg.msg.en_US:memdbg.msg.en_US:5.5.0.1: : :C: :User Heap/Memory Debug Messages--U.S. English : : : : : : :0:0:/:",
        "openssh.base:openssh.base.client:8.1.102.2102: : :C: :Open Secure Shell Commands: : : : : : :0:0:/:",
        "openssh.base:openssh.base.server:8.1.102.2102: : :C: :Open Secure Shell Server: : : : : : :0:0:/:",
        "openssh.man.en_US:openssh.man.en_US:8.1.102.2102: : :C: :Open Secure Shell Documentation - U.S. English: : : : : : :0:0:/:",
        "openssl.base:openssl.base:1.0.2.2100: : :C: :Open Secure Socket Layer: : : : : : :0:0:/:",
        "openssl.license:openssl.license:1.0.2.2100: : :C: :Open Secure Socket License: : : : : : :0:0:/:",
        "openssl.man.en_US:openssl.man.en_US:1.0.2.2100: : :C: :Open Secure Socket Layer: : : : : : :0:0:/:",
        "perfagent.tools:perfagent.tools:7.2.4.1: : :C:F:Local Performance Analysis & Control Commands: : : : : : :0:0:/:2015",
        "perl.libext:perl.libext:2.4.4.1: : :C:F:Perl Library Extensions: : : : : : :0:0:/:2015",
        "perl.rte:perl.rte:5.28.1.2: : :C: :Perl Version 5 Runtime Environment: : : : : : :0:0:/:1241",
        "printers.rte:printers.rte:7.2.4.0: : :C: :Printer Backend : : : : : : :1:0:/:1937",
        "rpm.rte:rpm.rte:4.15.1.3: : :C: :RPM Package Manager: : : : : : :0:0:/:",
        "rsct.core:rsct.core.auditrm:3.2.5.0: : :C: :RSCT Audit Log Resource Manager: : : : : : :1:0:/:",
        "rsct.core:rsct.core.errm:3.2.5.0: : :C: :RSCT Event Response Resource Manager: : : : : : :1:0:/:",
        "rsct.core:rsct.core.fsrm:3.2.5.0: : :C: :RSCT File System Resource Manager: : : : : : :1:0:/:",
        "rsct.core:rsct.core.gui:3.2.5.0: : :C: :RSCT Graphical User Interface: : : : : : :1:0:/:",
        "rsct.core:rsct.core.hostrm:3.2.5.2: : :C:F:RSCT Host Resource Manager: : : : : : :0:0:/:",
        "rsct.core:rsct.core.lprm:3.2.5.0: : :C: :RSCT Least Privilege Resource Manager: : : : : : :1:0:/:",
        "rsct.core:rsct.core.microsensor:3.2.5.0: : :C: :RSCT MicroSensor Resource Manager: : : : : : :1:0:/:",
        "rsct.core:rsct.core.rmc:3.2.5.2: : :C:F:RSCT Resource Monitoring and Control: : : : : : :0:0:/:",
        "rsct.core:rsct.core.sec:3.2.5.0: : :C: :RSCT Security: : : : : : :1:0:/:",
        "rsct.core:rsct.core.sensorrm:3.2.5.0: : :C: :RSCT Sensor Resource Manager: : : : : : :1:0:/:",
        "rsct.core:rsct.core.sr:3.2.5.0: : :C: :RSCT Registry: : : : : : :1:0:/:",
        "rsct.core:rsct.core.utils:3.2.5.2: : :C:F:RSCT Utilities: : : : : : :0:0:/:",
        "salt:salt.rte:30.0.4.0: : :C: :SaltProject for AIX: : : : : : :0:0:/:",
        "security.acf:security.acf:7.2.4.1: : :C:F:ACF/PKCS11 Device Driver: : : : : : :0:0:/:2015",
        "tcl.base:tcl.base:8.4.7.1: : :C: :Binary executable files of Tcl: : : : : : :0:0:/:",
        "tk.base:tk.base:8.4.7.1: : :C: :Binary executable files of Tk: : : : : : :0:0:/:",
        "wio.common:wio.common:7.2.0.0: : :C: :Common I/O Support for Workload Partitions : : : : : : :1:0:/:1543",
        "wio.fcp:wio.fcp:7.2.4.0: : :C: :FC I/O Support for Workload Partitions : : : : : : :1:0:/:1937",
        "wio.vscsi:wio.vscsi:7.2.0.0: : :C: :VSCSI I/O Support for Workload Partitions : : : : : : :1:0:/:1543",
        "xlC.adt:xlC.adt.include:16.1.0.0: : :C: :C Set ++ Application Development Toolkit: : : : : : :0:0:/:",
        "xlC.aix61:xlC.aix61.rte:16.1.0.3: : :C: :IBM XL C++ Runtime for AIX 6.1 and later : : : : : : :0:0:/:",
        "xlC.cpp:xlC.cpp:9.0.0.0: : :C: :C for AIX Preprocessor: : : : : : :1:0:/:",
        "xlC.msg.en_US:xlC.msg.en_US.rte:16.1.0.0: : :C: :IBM XL C++ Runtime Messages--U.S. English: : : : : : :0:0:/:",
        "xlC.rte:xlC.rte:16.1.0.3: : :C: :IBM XL C++ Runtime for AIX : : : : : : :0:0:/:",
        "xlC.sup.aix50.rte:xlC.sup.aix50.rte:9.0.0.1: : :C: :XL C/C++ Runtime for AIX 5.2: : : : : : :1:0:/:",
        "xlCcmp.16.1.0:xlCcmp.16.1.0:16.1.0.1: : :C: :XL C++ compiler: : : : : : :0:0:/:",
        "xlCcmp.16.1.0.beta:xlCcmp.16.1.0.beta:16.1.0.1: : :C: :XL C++ beta license files: : : : : : :0:0:/:",
        "xlCcmp.16.1.0.bundle:xlCcmp.16.1.0.bundle:16.1.0.1: : :C: :XL C++ media defined bundles: : : : : : :0:0:/:",
        "xlCcmp.16.1.0.evaluation:xlCcmp.16.1.0.evaluation:16.1.0.1: : :C: :XL C++ license files for the evaluation copy: : : : : : :0:0:/:",
        "xlCcmp.16.1.0.lib:xlCcmp.16.1.0.lib:16.1.0.1: : :C: :XL C++ libraries: : : : : : :0:0:/:",
        "xlCcmp.16.1.0.ndi:xlCcmp.16.1.0.ndi:16.1.0.1: : :C: :XL C++ non-default installation script: : : : : : :0:0:/:",
        "xlCcmp.16.1.0.tools:xlCcmp.16.1.0.tools:16.1.0.1: : :C: :XL C++ tools: : : : : : :0:0:/:",
        "xlccmp.16.1.0:xlccmp.16.1.0:16.1.0.1: : :C: :XL C compiler: : : : : : :0:0:/:",
        "xlccmp.16.1.0.bundle:xlccmp.16.1.0.bundle:16.1.0.1: : :C: :XL C media defined bundles: : : : : : :0:0:/:",
        "xlccmp.16.1.0.lib:xlccmp.16.1.0.lib:16.1.0.1: : :C: :XL C libraries: : : : : : :0:0:/:",
        "xlccmp.16.1.0.ndi:xlccmp.16.1.0.ndi:16.1.0.1: : :C: :XL C non-default installation script: : : : : : :0:0:/:",
        "xlmass.9.1.0:xlmass.9.1.0:9.1.0.1: : :C: :IBM Mathematical Acceleration Subsystem (MASS): : : : : : :0:0:/:",
        "xlsmp.aix61.rte:xlsmp.aix61.rte:5.1.0.0: : :C: :SMP Runtime Libraries: : : : : : :0:0:/:",
        "xlsmp.msg.En_US.rte:xlsmp.msg.En_US.rte:5.1.0.0: : :C: :XL SMP Runtime Messages - U.S. English IBM-850: : : : : : :0:0:/:",
        "xlsmp.msg.en_US.rte:xlsmp.msg.en_US.rte:5.1.0.0: : :C: :XL SMP Runtime Messages - U.S. English: : : : : : :0:0:/:",
        "xlsmp.rte:xlsmp.rte:5.1.0.0: : :C: :SMP Runtime Library: : : : : : :0:0:/:",
        "AIX-rpm:AIX-rpm-7.2.4.1-5:7.2.4.1-5: : :C:R:Virtual Package for libraries and shells installed on system: :/bin/rpm -e AIX-rpm: : : : :1: :(none):Thu Dec  2 18:09:40 EST 2021",
        "bash:bash-5.1.4-2:5.1.4-2: : :C:R:The GNU Bourne Again shell (bash) version 5.1.4: :/bin/rpm -e bash: : : : :0: :(none):Fri Aug 13 04:33:12 EDT 2021",
        "bzip2:bzip2-1.0.8-2:1.0.8-2: : :C:R:A file compression utility: :/bin/rpm -e bzip2: : : : :0: :(none):Thu Nov 28 23:57:13 EST 2019",
        "ca-certificates:ca-certificates-2020.06.01-1:2020.06.01-1: : :C:R:The Mozilla CA root certificate bundle: :/bin/rpm -e ca-certificates: : : : :0: :(none):Mon Aug  3 01:34:12 EDT 2020",
        "cloud-init:cloud-init-0.7.5-4.3:0.7.5-4.3: : :C:R:Cloud node initialization tool: :/bin/rpm -e cloud-init: : : : :0: :(none):Thu Jun  8 12:24:46 EDT 2017",
        "curl:curl-7.79.1-1:7.79.1-1: : :C:R:get a file from a FTP or HTTP server.: :/bin/rpm -e curl: : : : :0: :/opt/freeware:Wed Oct  6 09:48:02 EDT 2021",
        "cyrus-sasl:cyrus-sasl-2.1.26-3:2.1.26-3: : :C:R:Simple Authentication and Security Layer (SASL).: :/bin/rpm -e cyrus-sasl: : : : :0: :/opt/freeware:Wed Aug  1 02:41:24 EDT 2018",
        "db:db-5.3.28-1:5.3.28-1: : :C:R:The Berkeley Database, the Open Source embedded database system: :/bin/rpm -e db: : : : :1: :/opt/freeware:Fri Dec 11 05:11:17 EST 2020",
        "dnf:dnf-4.2.17-32_1:4.2.17-32_1: : :C:R:Package manager: :/bin/rpm -e dnf: : : : :0: :(none):Wed Jul 21 04:42:32 EDT 2021",
        "dnf-automatic:dnf-automatic-4.2.17-32_1:4.2.17-32_1: : :C:R:Package manager - automated upgrades: :/bin/rpm -e dnf-automatic: : : : :0: :(none):Wed Jul 21 04:42:32 EDT 2021",
        "dnf-data:dnf-data-4.2.17-32_1:4.2.17-32_1: : :C:R:Common data and configuration files for DNF: :/bin/rpm -e dnf-data: : : : :0: :(none):Wed Jul 21 04:42:32 EDT 2021",
        "expat:expat-2.2.9-2:2.2.9-2: : :C:R:An XML parser library: :/bin/rpm -e expat: : : : :0: :(none):Wed Jun 24 07:45:26 EDT 2020",
        "gcc:gcc-8-1:8-1: : :C:R:GNU Compiler Collection: :/bin/rpm -e gcc: : : : :0: :(none):Tue Dec 15 04:20:31 EST 2020",
        "gcc-c++:gcc-c++-8-1:8-1: : :C:R:C++ support for GCC: :/bin/rpm -e gcc-c++: : : : :0: :(none):Tue Dec 15 04:20:31 EST 2020",
        "gcc-cpp:gcc-cpp-8-1:8-1: : :C:R:The C Preprocessor: :/bin/rpm -e gcc-cpp: : : : :0: :(none):Tue Dec 15 04:20:31 EST 2020",
        "gcc8:gcc8-8.3.0-6:8.3.0-6: : :C:R:GNU Compiler Collection: :/bin/rpm -e gcc8: : : : :0: :(none):Mon Aug 16 13:46:25 EDT 2021",
        "gcc8-c++:gcc8-c++-8.3.0-6:8.3.0-6: : :C:R:C++ support for GCC: :/bin/rpm -e gcc8-c++: : : : :0: :(none):Mon Aug 16 13:46:25 EDT 2021",
        "gcc8-cpp:gcc8-cpp-8.3.0-6:8.3.0-6: : :C:R:The C Preprocessor: :/bin/rpm -e gcc8-cpp: : : : :0: :(none):Mon Aug 16 13:46:25 EDT 2021",
        "gdbm:gdbm-1.18.1-1:1.18.1-1: : :C:R:A GNU set of database routines which use extensible hashing.: :/bin/rpm -e gdbm: : : : :0: :(none):Thu Apr 25 02:41:30 EDT 2019",
        "gettext:gettext-0.20.2-1:0.20.2-1: : :C:R:GNU libraries and utilities for producing multi-lingual messages.: :/bin/rpm -e gettext: : : : :0: :(none):Fri Oct 30 07:50:43 EDT 2020",
        "git:git-2.31.1-1:2.31.1-1: : :C:R:Core git tools: :/bin/rpm -e git: : : : :0: :(none):Tue Aug  3 11:46:26 EDT 2021",
        "git-core:git-core-2.31.1-1:2.31.1-1: : :C:R:Core package of git with minimal functionality: :/bin/rpm -e git-core: : : : :0: :(none):Tue Aug  3 11:46:26 EDT 2021",
        "git-core-doc:git-core-doc-2.31.1-1:2.31.1-1: : :C:R:Documentation files for git-core: :/bin/rpm -e git-core-doc: : : : :0: :(none):Tue Aug  3 11:46:26 EDT 2021",
        "git-daemon:git-daemon-2.31.1-1:2.31.1-1: : :C:R:Git protocol dæmon: :/bin/rpm -e git-daemon: : : : :0: :(none):Tue Aug  3 11:46:26 EDT 2021",
        "git-email:git-email-2.31.1-1:2.31.1-1: : :C:R:Git tools for sending email: :/bin/rpm -e git-email: : : : :0: :(none):Tue Aug  3 11:46:26 EDT 2021",
        "git-gui:git-gui-2.31.1-1:2.31.1-1: : :C:R:Git GUI tool: :/bin/rpm -e git-gui: : : : :0: :(none):Tue Aug  3 11:46:26 EDT 2021",
        "git-lfs:git-lfs-2.9.0-1:2.9.0-1: : :C:R:Git extension for versioning large files: :/bin/rpm -e git-lfs: : : : :0: :(none):Thu Nov 14 04:22:09 EST 2019",
        "glib2:glib2-2.56.1-2:2.56.1-2: : :C:R:A library of handy utility functions: :/bin/rpm -e glib2: : : : :0: :(none):Tue Aug  7 02:58:07 EDT 2018",
        "gmp:gmp-6.1.2-1:6.1.2-1: : :C:R:A GNU arbitrary precision library: :/bin/rpm -e gmp: : : : :0: :(none):Wed Aug  9 06:08:10 EDT 2017",
        "info:info-6.6-2:6.6-2: : :C:R:A stand-alone TTY-based reader for GNU texinfo documentation.: :/bin/rpm -e info: : : : :1: :(none):Tue Nov 19 08:36:49 EST 2019",
        "krb5-libs:krb5-libs-1.18.3-1:1.18.3-1: : :C:R:The shared libraries used by Kerberos 5: :/bin/rpm -e krb5-libs: : : : :0: :(none):Tue Feb  9 10:57:13 EST 2021",
        "less:less-557-1:557-1: : :C:R:A text file browser similar to more, but better: :/bin/rpm -e less: : : : :0: :/opt/freeware:Wed Apr 15 15:10:14 EDT 2020",
        "libcomps:libcomps-0.1.11-32_1:0.1.11-32_1: : :C:R:Comps XML file manipulation library: :/bin/rpm -e libcomps: : : : :0: :(none):Sun Jul 11 05:22:48 EDT 2021",
        "libdnf:libdnf-0.39.1-32_1:0.39.1-32_1: : :C:R:Library providing simplified C and Python API to libsolv: :/bin/rpm -e libdnf: : : : :0: :(none):Sun Jul 11 23:26:48 EDT 2021",
        "libffi:libffi-3.2.1-3:3.2.1-3: : :C:R:A portable foreign function interface library: :/bin/rpm -e libffi: : : : :0: :(none):Thu Feb 28 00:27:09 EST 2019",
        "libgcc:libgcc-8-1:8-1: : :C:R:GCC version 8 shared support library: :/bin/rpm -e libgcc: : : : :0: :(none):Tue Dec 15 04:20:31 EST 2020",
        "libgcc8:libgcc8-8.3.0-6:8.3.0-6: : :C:R:GCC version 8.3.0 shared support library: :/bin/rpm -e libgcc8: : : : :0: :(none):Mon Aug 16 13:46:25 EDT 2021",
        "libgomp:libgomp-8-1:8-1: : :C:R:GCC OpenMP 2.5 shared support library: :/bin/rpm -e libgomp: : : : :0: :(none):Tue Dec 15 04:20:31 EST 2020",
        "libgomp8:libgomp8-8.3.0-6:8.3.0-6: : :C:R:GCC OpenMP 2.5 shared support library: :/bin/rpm -e libgomp8: : : : :0: :(none):Mon Aug 16 13:46:25 EDT 2021",
        "libiconv:libiconv-1.16-1:1.16-1: : :C:R:Character set conversion library, portable iconv implementation: :/bin/rpm -e libiconv: : : : :0: :(none):Thu May 21 05:05:00 EDT 2020",
        "libmodulemd:libmodulemd-1.5.2-32_1:1.5.2-32_1: : :C:R:Module metadata manipulation library: :/bin/rpm -e libmodulemd: : : : :0: :(none):Sun Jul 11 05:18:07 EDT 2021",
        "libmpc:libmpc-1.1.0-1:1.1.0-1: : :C:R:C library for multiple precision complex arithmetic: :/bin/rpm -e libmpc: : : : :0: :(none):Thu Sep 26 07:33:20 EDT 2019",
        "libnghttp2:libnghttp2-1.41.0-1:1.41.0-1: : :C:R:A library implementing the HTTP/2 protocol: :/bin/rpm -e libnghttp2: : : : :0: :(none):Fri Jul 24 05:59:01 EDT 2020",
        "librepo:librepo-1.11.0-32_1:1.11.0-32_1: : :C:R:Repodata downloading library: :/bin/rpm -e librepo: : : : :0: :(none):Sun Jul 11 05:22:18 EDT 2021",
        "libsmartcols:libsmartcols-2.34-32_1:2.34-32_1: : :C:R:Prints table or tree: :/bin/rpm -e libsmartcols: : : : :0: :(none):Sun Jul 11 05:22:01 EDT 2021",
        "libsolv:libsolv-0.7.9-32_1:0.7.9-32_1: : :C:R:Package dependency solver: :/bin/rpm -e libsolv: : : : :0: :(none):Sun Jul 11 05:18:40 EDT 2021",
        "libssh2:libssh2-1.9.0-1:1.9.0-1: : :C:R:A library implementing the SSH2 protocol: :/bin/rpm -e libssh2: : : : :0: :(none):Fri May  8 00:48:29 EDT 2020",
        "libstdc++:libstdc++-8-1:8-1: : :C:R:GNU Standard C++ Library: :/bin/rpm -e libstdc++: : : : :0: :(none):Tue Dec 15 04:20:31 EST 2020",
        "libstdc++8:libstdc++8-8.3.0-6:8.3.0-6: : :C:R:GNU Standard C++ Library: :/bin/rpm -e libstdc++8: : : : :0: :(none):Mon Aug 16 13:46:25 EDT 2021",
        "libstdc++8-devel:libstdc++8-devel-8.3.0-6:8.3.0-6: : :C:R:Header files and libraries for C++ development: :/bin/rpm -e libstdc++8-devel: : : : :0: :(none):Mon Aug 16 13:46:25 EDT 2021",
        "libtextstyle:libtextstyle-0.20.2-1:0.20.2-1: : :C:R:Text styling library: :/bin/rpm -e libtextstyle: : : : :0: :(none):Fri Oct 30 07:50:43 EDT 2020",
        "libunistring:libunistring-0.9.10-1:0.9.10-1: : :C:R:GNU Unicode string library: :/bin/rpm -e libunistring: : : : :0: :(none):Fri Oct 30 08:45:38 EDT 2020",
        "libxml2:libxml2-2.9.11-1:2.9.11-1: : :C:R:Library providing XML and HTML support: :/bin/rpm -e libxml2: : : : :0: :(none):Tue Aug 24 01:44:36 EDT 2021",
        "libyaml:libyaml-0.2.2-1:0.2.2-1: : :C:R:YAML 1.1 parser and emitter written in C: :/bin/rpm -e libyaml: : : : :0: :(none):Wed Apr 29 02:20:05 EDT 2020",
        "libzstd:libzstd-1.4.4-32_1:1.4.4-32_1: : :C:R:Zstd shared library: :/bin/rpm -e libzstd: : : : :0: :(none):Sun Jul 11 05:17:04 EDT 2021",
        "lz4:lz4-1.9.2-1:1.9.2-1: : :C:R:Extremely fast compression algorithm: :/bin/rpm -e lz4: : : : :0: :(none):Thu Oct 24 10:39:53 EDT 2019",
        "mpfr:mpfr-4.0.2-2:4.0.2-2: : :C:R:A C library for multiple-precision floating-point computations: :/bin/rpm -e mpfr: : : : :0: :(none):Wed Mar  4 07:55:58 EST 2020",
        "ncurses:ncurses-6.2-2:6.2-2: : :C:R:A terminal handling library: :/bin/rpm -e ncurses: : : : :0: :(none):Wed Sep 16 07:02:18 EDT 2020",
        "openldap:openldap-2.4.58-1:2.4.58-1: : :C:R:The configuration files, libraries, and documentation for OpenLDAP: :/bin/rpm -e openldap: : : : :0: :(none):Mon Apr 12 06:25:19 EDT 2021",
        "p11-kit:p11-kit-0.23.16-1:0.23.16-1: : :C:R:Library to work with PKCS#11 modules: :/bin/rpm -e p11-kit: : : : :0: :(none):Thu Aug  1 04:33:16 EDT 2019",
        "p11-kit-tools:p11-kit-tools-0.23.16-1:0.23.16-1: : :C:R:Library to work with PKCS#11 modules -- Tools: :/bin/rpm -e p11-kit-tools: : : : :0: :(none):Thu Aug  1 04:33:16 EDT 2019",
        "perl:perl-5.30.3-2:5.30.3-2: : :C:R:The Perl programming language.: :/bin/rpm -e perl: : : : :1: :/opt/freeware:Tue Jan  5 06:11:45 EST 2021",
        "perl-Authen-SASL:perl-Authen-SASL-2.16-7:2.16-7: : :C:R:SASL Authentication framework for Perl: :/bin/rpm -e perl-Authen-SASL: : : : :0: :(none):Sat Aug 20 01:46:33 EDT 2016",
        "perl-Net-SMTP-SSL:perl-Net-SMTP-SSL-1.04-1:1.04-1: : :C:R:SSL support for Net::SMTP: :/bin/rpm -e perl-Net-SMTP-SSL: : : : :0: :(none):Tue Mar 20 00:40:38 EDT 2018",
        "pysqlite:pysqlite-2.8.3-2:2.8.3-2: : :C:R:A DB API v2.0 compatible interface to SQLite 3.0: :/bin/rpm -e pysqlite: : : : :0: :(none):Fri Sep 27 04:26:24 EDT 2019",
        "python:python-2.7.18-3:2.7.18-3: : :C:R:An interpreted, interactive, object-oriented programming language.: :/bin/rpm -e python: : : : :0: :/opt/freeware:Mon May 31 11:41:15 EDT 2021",
        "python-PyYAML:python-PyYAML-3.11-1:3.11-1: : :C:R:YAML parser and emitter for Python: :/bin/rpm -e python-PyYAML: : : : :0: :/opt/freeware:Tue Jun 14 08:45:08 EDT 2016",
        "python-boto:python-boto-2.34.0-1:2.34.0-1: : :C:R:A simple, lightweight interface to Amazon Web Services: :/bin/rpm -e python-boto: : : : :0: :/opt/freeware:Wed May 25 07:15:11 EDT 2016",
        "python-cheetah:python-cheetah-2.4.4-2:2.4.4-2: : :C:R:Template engine and code generator: :/bin/rpm -e python-cheetah: : : : :0: :/opt/freeware:Wed May 25 07:18:22 EDT 2016",
        "python-configobj:python-configobj-5.0.5-1:5.0.5-1: : :C:R:Config file reading, writing and validation.: :/bin/rpm -e python-configobj: : : : :0: :/opt/freeware:Wed May 25 07:19:20 EDT 2016",
        "python-devel:python-devel-2.7.18-3:2.7.18-3: : :C:R:The libraries and header files needed for Python development.: :/bin/rpm -e python-devel: : : : :0: :/opt/freeware:Mon May 31 11:41:15 EDT 2021",
        "python-iniparse:python-iniparse-0.4-1:0.4-1: : :C:R:Python Module for Accessing and Modifying Configuration Data in INI files: :/bin/rpm -e python-iniparse: : : : :0: :(none):Mon Jun 13 08:41:09 EDT 2016",
        "python-jsonpatch:python-jsonpatch-1.8-1:1.8-1: : :C:R:Applying JSON Patches in Python: :/bin/rpm -e python-jsonpatch: : : : :0: :/opt/freeware:Wed May 25 07:20:25 EDT 2016",
        "python-jsonpointer:python-jsonpointer-1.0-1:1.0-1: : :C:R:Identify specific nodes in a JSON document (RFC 6901): :/bin/rpm -e python-jsonpointer: : : : :0: :/opt/freeware:Wed May 25 07:22:51 EDT 2016",
        "python-oauth:python-oauth-1.0.1-1:1.0.1-1: : :C:R:Library for OAuth version 1.0a: :/bin/rpm -e python-oauth: : : : :0: :/opt/freeware:Thu Jun 16 02:41:11 EDT 2016",
        "python-prettytable:python-prettytable-0.7.2-1:0.7.2-1: : :C:R:A simple Python library for easily displaying tabular data in a visually appealing ASCII table format: :/bin/rpm -e python-prettytable: : : : :0: :/opt/freeware:Thu Jun 16 02:46:16 EDT 2016",
        "python-pycurl:python-pycurl-7.43.0-1:7.43.0-1: : :C:R:A Python interface to libcurl: :/bin/rpm -e python-pycurl: : : : :0: :(none):Tue Jan  2 05:42:35 EST 2018",
        "python-pyserial:python-pyserial-2.7-1:2.7-1: : :C:R:Python serial port access library: :/bin/rpm -e python-pyserial: : : : :0: :/opt/freeware:Thu Jun 16 02:43:21 EDT 2016",
        "python-requests:python-requests-2.4.3-1:2.4.3-1: : :C:R:HTTP library, written in Python, for human beings: :/bin/rpm -e python-requests: : : : :0: :/opt/freeware:Thu Jun 16 02:48:27 EDT 2016",
        "python-setuptools:python-setuptools-0.9.8-2:0.9.8-2: : :C:R:Easily download, build, install, upgrade, and uninstall Python packages: :/bin/rpm -e python-setuptools: : : : :0: :/opt/freeware:Mon Jun 13 08:34:58 EDT 2016",
        "python-six:python-six-1.10.0-1:1.10.0-1: : :C:R:Python 2 and 3 compatibility utilities: :/bin/rpm -e python-six: : : : :0: :/opt/freeware:Wed Aug 24 14:36:21 EDT 2016",
        "python-tools:python-tools-2.7.18-3:2.7.18-3: : :C:R:A collection of development tools included with Python.: :/bin/rpm -e python-tools: : : : :0: :/opt/freeware:Mon May 31 11:41:15 EDT 2021",
        "python-urlgrabber:python-urlgrabber-3.10.1-1:3.10.1-1: : :C:R:A high-level cross-protocol url-grabber: :/bin/rpm -e python-urlgrabber: : : : :0: :(none):Mon Jun 13 07:29:37 EDT 2016",
        "python-xml:python-xml-0.8.4-1:0.8.4-1: : :C:R:XML libraries for python: :/bin/rpm -e python-xml: : : : :0: :/opt/freeware:Wed Jun 29 05:30:07 EDT 2016",
        "python3:python3-3.7.11-1:3.7.11-1: : :C:R:An interpreted, interactive, object-oriented programming language.: :/bin/rpm -e python3: : : : :0: :/opt/freeware:Mon Sep  6 11:23:58 EDT 2021",
        "python3-dateutil:python3-dateutil-2.8.0-1:2.8.0-1: : :C:R:Extensions to the standard Python datetime module: :/bin/rpm -e python3-dateutil: : : : :0: :(none):Tue Dec 31 00:41:37 EST 2019",
        "python3-dnf:python3-dnf-4.2.17-32_1:4.2.17-32_1: : :C:R:Python 3 interface to DNF: :/bin/rpm -e python3-dnf: : : : :0: :(none):Wed Jul 21 04:42:32 EDT 2021",
        "python3-dnf-plugin-migrate:python3-dnf-plugin-migrate-4.0.16-32_1:4.0.16-32_1: : :C:R:Migrate Plugin for DNF: :/bin/rpm -e python3-dnf-plugin-migrate: : : : :0: :(none):Wed Jul 21 10:06:41 EDT 2021",
        "python3-dnf-plugins-core:python3-dnf-plugins-core-4.0.16-32_1:4.0.16-32_1: : :C:R:Core Plugins for DNF: :/bin/rpm -e python3-dnf-plugins-core: : : : :0: :(none):Wed Jul 21 10:06:41 EDT 2021",
        "python3-gpgme:python3-gpgme-1.13.1-32_1:1.13.1-32_1: : :C:R:Python 3 bindings for the gpgme library.: :/bin/rpm -e python3-gpgme: : : : :0: :(none):Sun Jul 11 05:10:59 EDT 2021",
        "python3-hawkey:python3-hawkey-0.39.1-32_1:0.39.1-32_1: : :C:R:Python 3 bindings for the hawkey library: :/bin/rpm -e python3-hawkey: : : : :0: :(none):Sun Jul 11 23:26:48 EDT 2021",
        "python3-libcomps:python3-libcomps-0.1.11-32_1:0.1.11-32_1: : :C:R:Python 3 bindings for libcomps library: :/bin/rpm -e python3-libcomps: : : : :0: :(none):Sun Jul 11 05:22:48 EDT 2021",
        "python3-libdnf:python3-libdnf-0.39.1-32_1:0.39.1-32_1: : :C:R:Python 3 bindings for the libdnf library.: :/bin/rpm -e python3-libdnf: : : : :0: :(none):Sun Jul 11 23:26:48 EDT 2021",
        "python3-librepo:python3-librepo-1.11.0-32_1:1.11.0-32_1: : :C:R:Python 3 bindings for the librepo library: :/bin/rpm -e python3-librepo: : : : :0: :(none):Sun Jul 11 05:22:18 EDT 2021",
        "python3-six:python3-six-1.13.0-1:1.13.0-1: : :C:R:Python 2 and 3 compatibility utilities: :/bin/rpm -e python3-six: : : : :0: :/opt/freeware:Mon Dec 16 23:41:48 EST 2019",
        "readline:readline-8.0-2:8.0-2: : :C:R:A library for editing typed command lines: :/bin/rpm -e readline: : : : :0: :(none):Mon Aug 12 05:18:07 EDT 2019",
        "rpm-python3:rpm-python3-4.15.1-32_1:4.15.1-32_1: : :C:R:This package contains files to be added on top of rpm-devel for python developements.: :/bin/rpm -e rpm-python3: : : : :0: :/usr/opt/rpm:Sat Jul 10 13:12:03 EDT 2021",
        "rsync:rsync-3.2.3-1:3.2.3-1: : :C:R:A program for synchronizing files over a network.: :/bin/rpm -e rsync: : : : :0: :(none):Wed Aug 26 01:37:51 EDT 2020",
        "sed:sed-4.8-1:4.8-1: : :C:R:A GNU stream text editor.: :/bin/rpm -e sed: : : : :1: :/opt/freeware:Tue Nov 17 03:13:15 EST 2020",
        "sqlite:sqlite-3.32.3-1:3.32.3-1: : :C:R:Library that implements an embeddable SQL database engine: :/bin/rpm -e sqlite: : : : :0: :(none):Thu Aug 20 10:39:58 EDT 2020",
        "sudo:sudo-1.9.5p2-1:1.9.5p2-1: : :C:R:Allows restricted root access for specified users.: :/bin/rpm -e sudo: : : : :0: :/opt/freeware:Wed Jan 27 12:29:50 EST 2021",
        "vim-common:vim-common-8.1.2424-2:8.1.2424-2: : :C:R:The common files needed by any version of the VIM editor: :/bin/rpm -e vim-common: : : : :0: :(none):Wed Sep  1 13:11:24 EDT 2021",
        "vim-enhanced:vim-enhanced-8.1.2424-2:8.1.2424-2: : :C:R:A version of the VIM editor which includes recent enhancements: :/bin/rpm -e vim-enhanced: : : : :0: :(none):Wed Sep  1 13:11:24 EDT 2021",
        "vim-minimal:vim-minimal-8.1.2424-2:8.1.2424-2: : :C:R:A minimal version of the VIM editor: :/bin/rpm -e vim-minimal: : : : :0: :(none):Wed Sep  1 13:11:24 EDT 2021",
        "wget:wget-1.21.1-1:1.21.1-1: : :C:R:A utility for retrieving files using the HTTP or FTP protocols: :/bin/rpm -e wget: : : : :0: :(none):Wed Mar  3 23:43:47 EST 2021",
        "xz-libs:xz-libs-5.2.5-1:5.2.5-1: : :C:R:Libraries for decoding LZMA compression: :/bin/rpm -e xz-libs: : : : :0: :(none):Mon Apr 20 23:33:27 EDT 2020",
        "yum:yum-4.2.17-32_1:4.2.17-32_1: : :C:R:Package manager: :/bin/rpm -e yum: : : : :0: :(none):Wed Jul 21 04:42:32 EDT 2021",
        "yum-metadata-parser:yum-metadata-parser-1.1.4-2:1.1.4-2: : :C:R:A fast metadata parser for yum: :/bin/rpm -e yum-metadata-parser: : : : :0: :(none):Fri Feb 24 13:51:50 EST 2017",
        "yum-utils:yum-utils-1.1.31-2:1.1.31-2: : :C:R:Utilities based around the yum package manager: :/bin/rpm -e yum-utils: : : : :0: :(none):Mon Mar  4 07:43:01 EST 2019",
        "zchunk-libs:zchunk-libs-1.1.4-32_1:1.1.4-32_1: : :C:R:Zchunk library: :/bin/rpm -e zchunk-libs: : : : :0: :(none):Sun Jul 11 05:21:41 EDT 2021",
        "zlib:zlib-1.2.11-2:1.2.11-2: : :C:R:The zlib compression and decompression library.: :/bin/rpm -e zlib: : : : :0: :/opt/freeware:Thu Dec 17 10:29:03 EST 2020",
    ]


@pytest.fixture
def configure_loader_modules():

    return {
        aixpkg: {
            "__context__": {"yum_bin": "yum"},
            "__grains__": {
                "osarch": "PowerPC_POWER8",
                "os": "AIX",
                "os_family": "AIX",
                "osmajorrelease": 7,
            },
        },
        pkg_resource: {},
    }


def test_list_pkgs(lslpp_out):
    """
    Test packages listing.

    :return:
    """

    def _add_data(data, key, value):
        data.setdefault(key, []).append(value)

    with patch.dict(aixpkg.__grains__, {"osarch": "PowerPC_POWER8"}), patch.dict(
        aixpkg.__salt__,
        {"cmd.run": MagicMock(return_value=os.linesep.join(lslpp_out))},
    ), patch.dict(aixpkg.__salt__, {"pkg_resource.add_pkg": _add_data}), patch.dict(
        aixpkg.__salt__,
        {"pkg_resource.format_pkg_list": pkg_resource.format_pkg_list},
    ), patch.dict(
        aixpkg.__salt__,
        {"pkg_resource.sort_pkglist": pkg_resource.sort_pkglist},
    ), patch.dict(
        aixpkg.__salt__, {"pkg_resource.stringify": MagicMock()}
    ):
        pkgs = aixpkg.list_pkgs(versions_as_list=True)
        for pkg_name, pkg_version in {
            "python-urlgrabber": "3.10.1-1",
            "rpm-python3": "4.15.1-32_1",
            "yum": "4.2.17-32_1",
            "openssh.base.client": "8.1.102.2102",
            "GSKit8.gskcrypt32.ppc.rte": "8.0.50.88",
            "bos.adt.base": "7.2.4.1",
            "perfagent.tools": "7.2.4.1",
        }.items():
            assert pkgs.get(pkg_name) is not None
            assert pkgs[pkg_name] == [pkg_version]


def test_list_pkgs_no_context(lslpp_out):
    """
    Test packages listing.

    :return:
    """

    def _add_data(data, key, value):
        data.setdefault(key, []).append(value)

    with patch.dict(aixpkg.__grains__, {"osarch": "PowerPC_POWER8"}), patch.dict(
        aixpkg.__salt__,
        {"cmd.run": MagicMock(return_value=os.linesep.join(lslpp_out))},
    ), patch.dict(aixpkg.__salt__, {"pkg_resource.add_pkg": _add_data}), patch.dict(
        aixpkg.__salt__,
        {"pkg_resource.format_pkg_list": pkg_resource.format_pkg_list},
    ), patch.dict(
        aixpkg.__salt__,
        {"pkg_resource.sort_pkglist": pkg_resource.sort_pkglist},
    ), patch.dict(
        aixpkg.__salt__, {"pkg_resource.stringify": MagicMock()}
    ), patch.object(
        aixpkg, "_list_pkgs_from_context"
    ) as list_pkgs_context_mock:
        pkgs = aixpkg.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()

        pkgs = aixpkg.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()


def test_version_with_valid_names():
    """
    test version of packages
    """

    lslpp_info_out = """  info                         6.6-2    C     R    A stand-alone TTY-based reader
                                                   for GNU texinfo documentation.
                                                   (/bin/rpm)


State codes:
 A -- Applied.
 B -- Broken.
 C -- Committed.
 E -- EFIX Locked.
 O -- Obsolete.  (partially migrated to newer version)
 ? -- Inconsistent State...Run lppchk -v.

Type codes:
 F -- Installp Fileset
 P -- Product
 C -- Component
 T -- Feature
 R -- RPM Package
 E -- Interim Fix
"""

    lslpp_bash_out = """  bash                       5.1.4-2    C     R    The GNU Bourne Again shell
                                                   (bash) version 5.1.4
                                                   (/bin/rpm)


State codes:
 A -- Applied.
 B -- Broken.
 C -- Committed.
 E -- EFIX Locked.
 O -- Obsolete.  (partially migrated to newer version)
 ? -- Inconsistent State...Run lppchk -v.

Type codes:
 F -- Installp Fileset
 P -- Product
 C -- Component
 T -- Feature
 R -- RPM Package
 E -- Interim Fix
"""

    ver_chk = MagicMock(
        side_effect=[
            {"retcode": 0, "stdout": lslpp_info_out},
            {"retcode": 0, "stdout": lslpp_bash_out},
        ]
    )
    with patch.dict(aixpkg.__grains__, {"osarch": "PowerPC_POWER8"}), patch.dict(
        aixpkg.__salt__,
        {"cmd.run_all": ver_chk},
    ):
        versions_checked = aixpkg.version(
            "info", "bash", versions_as_list=True, use_context=False
        )
        assert ver_chk.call_count == 2
        ver_chk.assert_any_call("lslpp -Lq info", python_shell=False)
        ver_chk.assert_called_with("lslpp -Lq bash", python_shell=False)
        expected = {"info": "6.6-2", "bash": "5.1.4-2"}
        assert versions_checked == expected


def test_version_with_invalid_names():
    """
    test version of packages
    """

    lslpp_mydog_out = """lslpp: Fileset mydog not installed.


State codes:
 A -- Applied.
 B -- Broken.
 C -- Committed.
 E -- EFIX Locked.
 O -- Obsolete.  (partially migrated to newer version)
 ? -- Inconsistent State...Run lppchk -v.

Type codes:
 F -- Installp Fileset
 P -- Product
 C -- Component
 T -- Feature
 R -- RPM Package
 E -- Interim Fix
"""

    ver_chk = MagicMock(return_value={"retcode": 1, "stdout": lslpp_mydog_out})
    with patch.dict(aixpkg.__grains__, {"osarch": "PowerPC_POWER8"}), patch.dict(
        aixpkg.__salt__,
        {"cmd.run_all": ver_chk},
    ):
        versions_checked = aixpkg.version(
            "mydog", versions_as_list=True, use_context=False
        )
        assert ver_chk.call_count == 1
        ver_chk.assert_called_with("lslpp -Lq mydog", python_shell=False)
        assert versions_checked == ""


def test_upgrade_available_valid():
    """
    test upgrade available where a valid upgrade is available
    """

    chk_upgrade_out = """
Last metadata expiration check: 22:5:48 ago on Mon Dec  6 19:26:36 EST 2021.

info.ppc                                                                                                                          6.7-1                                                                                                                          AIX_Toolbox
"""
    dnf_call = MagicMock(return_value={"retcode": 100, "stdout": chk_upgrade_out})
    version_mock = MagicMock(return_value="6.6-2")
    with patch("pathlib.Path.is_file", return_value=True):
        with patch.dict(
            aixpkg.__salt__,
            {"cmd.run_all": dnf_call, "config.get": MagicMock(return_value=False)},
        ), patch.object(aixpkg, "version", version_mock):
            result = aixpkg.upgrade_available("info")
            assert dnf_call.call_count == 1
            libpath_env = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
            dnf_call.assert_any_call(
                "/opt/freeware/bin/dnf check-update info",
                env=libpath_env,
                ignore_retcode=True,
                python_shell=False,
            )
            assert result


def test_upgrade_available_none():
    """
    test upgrade available where a valid upgrade is not available
    """

    chk_upgrade_out = (
        "Last metadata expiration check: 22:5:48 ago on Mon Dec  6 19:26:36 EST 2021."
    )

    dnf_call = MagicMock(return_value={"retcode": 100, "stdout": chk_upgrade_out})
    version_mock = MagicMock(return_value="6.6-2")
    with patch("pathlib.Path.is_file", return_value=True):
        with patch.dict(
            aixpkg.__salt__,
            {"cmd.run_all": dnf_call, "config.get": MagicMock(return_value=False)},
        ), patch.object(aixpkg, "version", version_mock):
            result = aixpkg.upgrade_available("info")
            assert dnf_call.call_count == 1
            libpath_env = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
            dnf_call.assert_any_call(
                "/opt/freeware/bin/dnf check-update info",
                env=libpath_env,
                ignore_retcode=True,
                python_shell=False,
            )
            assert not result


def test_install_rpm_using_dnf():
    """
    Test install of rpm using dnf
    """
    dnf_call = MagicMock(return_value={"retcode": 100, "stdout": ""})
    list_pkgs_mock = MagicMock(side_effect=[{"info": "6.6-2"}, {"info": "6.7-1"}])
    with patch("pathlib.Path.is_file", return_value=True):
        with patch.dict(
            aixpkg.__salt__,
            {"cmd.run_all": dnf_call, "config.get": MagicMock(return_value=False)},
        ), patch.object(aixpkg, "list_pkgs", list_pkgs_mock):
            result = aixpkg.install("info")
            libpath_env = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
            dnf_call.assert_any_call(
                "/opt/freeware/bin/dnf install --allowerasing --assumeyes  info",
                env=libpath_env,
                ignore_retcode=True,
                python_shell=False,
            )
            expected = {"info": {"old": "6.6-2", "new": "6.7-1"}}
            assert result == expected


def test_install_non_rpm_using_dnf_gen_error():
    """
    Test install of non rpm using dnf which should generate an error
    """
    info_fake_error = """Last metadata expiration check: 1 day, 23:40:22 ago on Mon Dec  6 19:26:36 EST 2021.
No match for argument: info_fake
Error: Unable to find a match: info_fake
"""
    dnf_call = MagicMock(
        return_value={"retcode": 1, "stdout": "", "stderr": info_fake_error}
    )
    list_pkgs_mock = MagicMock(side_effect=[{"info": "6.6-2"}, {"info": "6.6-2"}])
    with patch("pathlib.Path.is_file", return_value=True):
        with patch.dict(
            aixpkg.__salt__,
            {"cmd.run_all": dnf_call, "config.get": MagicMock(return_value=False)},
        ), patch.object(aixpkg, "list_pkgs", list_pkgs_mock):
            expected = {
                "changes": {},
                "errors": [info_fake_error],
            }
            with pytest.raises(CommandExecutionError) as exc_info:
                aixpkg.install("info_fake.rpm")
            assert exc_info.value.info == expected, exc_info.value.info
            assert dnf_call.call_count == 1
            libpath_env = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
            dnf_call.assert_any_call(
                "/opt/freeware/bin/dnf install --allowerasing --assumeyes  info_fake.rpm",
                env=libpath_env,
                ignore_retcode=True,
                python_shell=False,
            )


def test_install_fileset_with_rte_extension():
    """
    Test install of fileset with rte extension
    """
    installp_call = MagicMock(return_value={"retcode": 0, "stdout": ""})
    fileset_pkg_name = "/stage/middleware/AIX/Xlc/usr/sys/inst.images/xlC.rte"
    list_pkgs_mock = MagicMock(
        side_effect=[{"xlC.rte": "15.3.0.6"}, {"xlC.rte": "16.1.0.3"}]
    )
    with patch("pathlib.Path.is_file", return_value=True):
        with patch.dict(
            aixpkg.__salt__,
            {"cmd.run_all": installp_call, "config.get": MagicMock(return_value=False)},
        ), patch.object(aixpkg, "list_pkgs", list_pkgs_mock):
            result = aixpkg.install(fileset_pkg_name)
            assert installp_call.call_count == 1
            installp_call.assert_any_call(
                "/usr/sbin/installp -acYXg -d /stage/middleware/AIX/Xlc/usr/sys/inst.images xlC.rte",
                python_shell=False,
            )
            expected = {"xlC.rte": {"old": "15.3.0.6", "new": "16.1.0.3"}}
            assert result == expected


def test_install_fileset_with_bff_extension():
    """
    Test install of fileset with bff extension
    """
    installp_call = MagicMock(return_value={"retcode": 0, "stdout": ""})
    fileset_pkg_name = (
        "/cecc/repos/aix72/TL3/BASE/installp/ppc/bos.rte.printers_7.2.2.0.bff"
    )
    list_pkgs_mock = MagicMock(
        side_effect=[{"bos.rte.printers": "7.1.6.0"}, {"bos.rte.printers": "7.2.4.0"}]
    )
    with patch("pathlib.Path.is_file", return_value=True):
        with patch.dict(
            aixpkg.__salt__,
            {"cmd.run_all": installp_call, "config.get": MagicMock(return_value=False)},
        ), patch.object(aixpkg, "list_pkgs", list_pkgs_mock):
            result = aixpkg.install(fileset_pkg_name)
            assert installp_call.call_count == 1
            installp_call.assert_any_call(
                "/usr/sbin/installp -acYXg -d /cecc/repos/aix72/TL3/BASE/installp/ppc bos.rte.printers_7.2.2.0.bff",
                python_shell=False,
            )
            expected = {"bos.rte.printers": {"old": "7.1.6.0", "new": "7.2.4.0"}}
            assert result == expected


def test_install_fail_dnf_try_fileset():
    """
    Test install of non-recognized extension, first dnf then fileset
    """

    bos_net_fake_error = """AIX generic repository                                                                                                                                                                                                                       12 kB/s | 2.6 kB     00:00
AIX noarch repository                                                                                                                                                                                                                        12 kB/s | 2.5 kB     00:00
AIX 7.2 specific repository                                                                                                                                                                                                                  12 kB/s | 2.5 kB     00:00
No match for argument: bos.net
Error: Unable to find a match: bos.net
"""

    fileset_pkg_name = "/cecc/repos/aix72/TL3/BASE/installp/ppc/bos.net"
    dnf_installp_call = MagicMock(
        side_effect=[
            {"retcode": 1, "stdout": "", "stderr": bos_net_fake_error},
            {"retcode": 0, "stdout": ""},
        ]
    )
    list_pkgs_mock = MagicMock(
        side_effect=[
            {"bos.net.tcp.tcpdump": "7.1.6.3"},
            {"bos.net.tcp.tcpdump": "7.2.4.1"},
        ]
    )
    with patch("pathlib.Path.is_file", return_value=True):
        with patch.dict(
            aixpkg.__salt__,
            {
                "cmd.run_all": dnf_installp_call,
                "config.get": MagicMock(return_value=False),
            },
        ), patch.object(aixpkg, "list_pkgs", list_pkgs_mock):
            result = aixpkg.install(fileset_pkg_name)
            assert dnf_installp_call.call_count == 2
            libpath_env = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
            dnf_installp_call.assert_any_call(
                "/opt/freeware/bin/dnf install --allowerasing --assumeyes  {}".format(
                    fileset_pkg_name
                ),
                env=libpath_env,
                ignore_retcode=True,
                python_shell=False,
            )
            dnf_installp_call.assert_called_with(
                "/usr/sbin/installp -acYXg -d /cecc/repos/aix72/TL3/BASE/installp/ppc bos.net",
                python_shell=False,
            )
            expected = {"bos.net.tcp.tcpdump": {"old": "7.1.6.3", "new": "7.2.4.1"}}
            assert result == expected


def test_install_fail_dnf_try_fileset_with_error():
    """
    Test install of non-recognized extension, first dnf then fileset, but error
    """

    info_fake_dnf_error = """Last metadata expiration check: 1 day, 23:40:22 ago on Mon Dec  6 19:26:36 EST 2021.
No match for argument: info_fake
Error: Unable to find a match: info_fake
"""

    info_fake_fileset_error = """+-----------------------------------------------------------------------------+
                    Pre-installation Verification...
+-----------------------------------------------------------------------------+
Verifying selections...done
Verifying requisites...done
Results...

FAILURES
--------
  Filesets listed in this section failed pre-installation verification
  and will not be installed.

  Missing Filesets
  ----------------
  The following filesets could not be found on the installation media.
  If you feel these filesets really are on the media, check for typographical
  errors in the name specified or, if installing from directory, check for
  discrepancies between the Table of Contents file (.toc) and the images that
  reside in the directory.

    fake_info

  << End of Failure Section >>

+-----------------------------------------------------------------------------+
                   BUILDDATE Verification ...
+-----------------------------------------------------------------------------+
Verifying build dates...done
FILESET STATISTICS
------------------
    1  Selected to be installed, of which:
        1  FAILED pre-installation verification
  ----
    0  Total to be installed


Pre-installation Failure/Warning Summary
----------------------------------------
Name                      Level           Pre-installation Failure/Warning
-------------------------------------------------------------------------------
fake_info                                 Not found on the installation media

"""
    fileset_pkg_name = "/cecc/repos/aix72/TL3/BASE/installp/ppc/info_fake"
    fileset_pkg_base_name = os.path.basename(f"{fileset_pkg_name}")
    dnf_installp_call = MagicMock(
        side_effect=[
            {"retcode": 1, "stdout": "", "stderr": info_fake_dnf_error},
            {"retcode": 1, "stdout": "", "stderr": info_fake_fileset_error},
        ]
    )
    list_pkgs_mock = MagicMock(
        side_effect=[
            {"bos.net.tcp.tcpdump": "7.2.4.1"},
            {"bos.net.tcp.tcpdump": "7.2.4.1"},
        ]
    )
    with patch("pathlib.Path.is_file", return_value=True):
        with patch.dict(
            aixpkg.__salt__,
            {
                "cmd.run_all": dnf_installp_call,
                "config.get": MagicMock(return_value=False),
            },
        ), patch.object(aixpkg, "list_pkgs", list_pkgs_mock):
            expected = {
                "changes": {},
                "errors": [info_fake_fileset_error],
            }
            with pytest.raises(CommandExecutionError) as exc_info:
                result = aixpkg.install(fileset_pkg_name)
            assert exc_info.value.info == expected, exc_info.value.info
            assert dnf_installp_call.call_count == 2
            libpath_env = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
            dnf_installp_call.assert_any_call(
                "/opt/freeware/bin/dnf install --allowerasing --assumeyes  {}".format(
                    fileset_pkg_name
                ),
                env=libpath_env,
                ignore_retcode=True,
                python_shell=False,
            )
            dnf_installp_call.assert_called_with(
                "/usr/sbin/installp -acYXg -d /cecc/repos/aix72/TL3/BASE/installp/ppc {}".format(
                    fileset_pkg_base_name
                ),
                python_shell=False,
            )


def test_remove_dnf():
    """
    Test remove rpm file using dnf
    """
    pkg_name = "info"
    pkg_name_version = "6.7-1"
    pkg_name_lslpp_out = """#Package Name:Fileset:Level:State:PTF Id:Fix State:Type:Description:Destination Dir.:Uninstaller:Message Catalog:Message Set:Message Number:Parent:Automatic:EFIX Locked:Install Path:Build Date\ninfo:info-6.7-1:6.7-1: : :C:R:A stand-alone TTY-based reader for GNU texinfo documentation.: :/bin/rpm -e info: : : : :1: :(none):Mon Feb  8 08:04:43 2021"""
    pkg_name_lslpp_out_dict = {
        "pid": 5439838,
        "retcode": 0,
        "stdout": pkg_name_lslpp_out,
        "stderr": "",
    }
    dnf_call = MagicMock(
        side_effect=[pkg_name_lslpp_out_dict, {"retcode": 0, "stdout": ""}]
    )
    list_pkgs_mock = MagicMock(
        side_effect=[
            {f"{pkg_name}": f"{pkg_name_version}"},
            {f"{pkg_name}": ""},
        ]
    )

    with patch("pathlib.Path.is_file", return_value=True):
        with patch.dict(
            aixpkg.__salt__,
            {"cmd.run_all": dnf_call, "config.get": MagicMock(return_value=False)},
        ), patch.object(aixpkg, "list_pkgs", list_pkgs_mock):
            result = aixpkg.remove(f"{pkg_name}")
            dnf_call.assert_any_call(
                ["/usr/bin/lslpp", "-Lc", f"{pkg_name}"],
                python_shell=False,
            )
            libpath_env = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
            dnf_call.assert_any_call(
                f"/opt/freeware/bin/dnf -y remove {pkg_name}",
                env=libpath_env,
                ignore_retcode=True,
                python_shell=False,
            )
            expected = {f"{pkg_name}": {"old": f"{pkg_name_version}", "new": ""}}
            assert result == expected


def test_remove_fileset():
    """
    Test remove fileset using installp

    Note: need to have the fileset available, compound filesets are not handled
        for example:  /usr/bin/installp -acXYg  /cecc/repos/aix72/TL4/BASE/installp/ppc/bos.adt.other bos.adt.insttools"
            is not supported
    """
    fileset_pkg_name = "/cecc/repos/aix72/TL4/BASE/installp/ppc/bos.adt.insttools"  # fake fileset (as part of compound bos.adt.other)
    fileset_base_name = os.path.basename(fileset_pkg_name)
    fileset_pkg_name_version = "7.2.2.0"
    fileset_pkg_name_lslpp_out = """#Package Name:Fileset:Level:State:PTF Id:Fix State:Type:Description:Destination Dir.:Uninstaller:Message Catalog:Message Set:Message Number:Parent:Automatic:EFIX Locked:Install Path:Build Date
bos.adt:bos.adt.insttools:7.2.2.0: : :C: :Tool to Create installp Packages : : : : : : :0:0:/:1731
"""
    fileset_pkg_name_lslpp_out_dict = {
        "pid": 5439838,
        "retcode": 0,
        "stdout": fileset_pkg_name_lslpp_out,
        "stderr": "",
    }
    fileset_pkg_name_installp_out = """+-----------------------------------------------------------------------------+
                    Pre-installation Verification...
+-----------------------------------------------------------------------------+
Verifying selections...done
Verifying requisites...done
Results...

SUCCESSES
---------
  Filesets listed in this section passed pre-installation verification
  and will be installed.

  Selected Filesets
  -----------------
  bos.adt.insttools 7.2.2.0                   # Tool to Create installp Pack...

  << End of Success Section >>

+-----------------------------------------------------------------------------+
                   BUILDDATE Verification ...
+-----------------------------------------------------------------------------+
Verifying build dates...done
FILESET STATISTICS
------------------
    1  Selected to be installed, of which:
        1  Passed pre-installation verification
  ----
    1  Total to be installed

+-----------------------------------------------------------------------------+
                         Installing Software...
+-----------------------------------------------------------------------------+

installp: APPLYING software for:
        bos.adt.insttools 7.2.2.0


. . . . . << Copyright notice for bos.adt >> . . . . . . .
 Licensed Materials - Property of IBM

 5765CD200
   Copyright International Business Machines Corp. 2002, 2019.

 All rights reserved.
 US Government Users Restricted Rights - Use, duplication or disclosure
 restricted by GSA ADP Schedule Contract with IBM Corp.
. . . . . << End of copyright notice for bos.adt >>. . . .

Successfully updated the Kernel Authorization Table.
Successfully updated the Kernel Role Table.
Successfully updated the Kernel Command Table.
Successfully updated the Kernel Device Table.
Successfully updated the Kernel Object Domain Table.
Successfully updated the Kernel  Domains Table.
Successfully updated the Kernel RBAC log level.
Finished processing all filesets.  (Total time:  1 secs).

+-----------------------------------------------------------------------------+
                                Summaries:
+-----------------------------------------------------------------------------+

Installation Summary
--------------------
Name                        Level           Part        Event       Result
-------------------------------------------------------------------------------
bos.adt.insttools           7.2.2.0         USR         APPLY       SUCCESS
bos.adt.insttools           7.2.2.0         ROOT        APPLY       SUCCESS
"""
    dnf_call = MagicMock(
        side_effect=[fileset_pkg_name_lslpp_out_dict, {"retcode": 0, "stdout": ""}]
    )
    list_pkgs_mock = MagicMock(
        side_effect=[
            {f"{fileset_base_name}": f"{fileset_pkg_name_version}"},
            {f"{fileset_base_name}": ""},
        ]
    )

    with patch("pathlib.Path.is_file", return_value=True):
        with patch.dict(
            aixpkg.__salt__,
            {"cmd.run_all": dnf_call, "config.get": MagicMock(return_value=False)},
        ), patch.object(aixpkg, "list_pkgs", list_pkgs_mock):
            result = aixpkg.remove(f"{fileset_pkg_name}")
            dnf_call.assert_any_call(
                ["/usr/bin/lslpp", "-Lc", f"{fileset_pkg_name}"],
                python_shell=False,
            )
            libpath_env = {"LIBPATH": "/opt/freeware/lib:/usr/lib"}
            test_name = os.path.basename(fileset_pkg_name)
            dnf_call.assert_any_call(
                ["/usr/sbin/installp", "-u", f"{fileset_base_name}"],
                python_shell=False,
            )
            expected = {
                f"{fileset_base_name}": {
                    "old": f"{fileset_pkg_name_version}",
                    "new": "",
                }
            }
            assert result == expected


def test_remove_failure():
    """
    Test remove package / fileset and experience failure
    """

    fileset_pkg_name = "info_fake"
    fileset_lslpp_error_stdout = """#Package Name:Fileset:Level:State:PTF Id:Fix State:Type:Description:Destination Dir.:Uninstaller:Message Catalog:Message Set:Message Number:Parent:Automatic:EFIX Locked:Install Path:Build Date
lslpp: Fileset info_fake not installed.
"""
    fileset_lslpp_error_dict = {
        "pid": 5374414,
        "retcode": 1,
        "stdout": fileset_lslpp_error_stdout,
        "stderr": "/usr/bin/lslpp: Fileset info_fake not installed.",
    }

    lslpp_call = MagicMock(return_value=fileset_lslpp_error_dict)
    list_pkgs_mock = MagicMock(
        side_effect=[
            {"bos.net.tcp.tcpdump": "7.2.4.1"},
            {"bos.net.tcp.tcpdump": "7.2.4.1"},
        ]
    )
    with patch.dict(
        aixpkg.__salt__,
        {
            "cmd.run_all": lslpp_call,
            "config.get": MagicMock(return_value=False),
        },
    ), patch.object(aixpkg, "list_pkgs", list_pkgs_mock):
        expected = {
            "changes": {},
            "errors": [f"/usr/bin/lslpp: Fileset {fileset_pkg_name} not installed."],
        }
        with pytest.raises(CommandExecutionError) as exc_info:
            result = aixpkg.remove(fileset_pkg_name)
        assert exc_info.value.info == expected, exc_info.value.info
        assert lslpp_call.call_count == 1
        lslpp_call.assert_any_call(
            ["/usr/bin/lslpp", "-Lc", f"{fileset_pkg_name}"],
            python_shell=False,
        )
