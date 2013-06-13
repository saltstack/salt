'''
The static grains, these are the core, or built in grains.

When grains are loaded they are not loaded in the same way that modules are
loaded, grain functions are detected and executed, the functions MUST
return a dict which will be applied to the main grains dict. This module
will always be executed first, so that any grains loaded here in the core
module can be overwritten just by returning dict keys with the same value
as those returned here
'''

# Import python libs
import os
import socket
import sys
import re
import platform
import logging
import locale

# Extend the default list of supported distros. This will be used for the
# /etc/DISTRO-release checking that is part of platform.linux_distribution()
from platform import _supported_dists
_supported_dists += ('arch', 'mageia', 'meego', 'vmware', 'bluewhite64',
                     'slamd64', 'ovs', 'system', 'mint', 'oracle')

# Import salt libs
import salt.log
import salt.utils
import salt.utils.network

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod

__salt__ = {
    'cmd.run': salt.modules.cmdmod._run_quiet,
    'cmd.run_all': salt.modules.cmdmod._run_all_quiet
}

log = logging.getLogger(__name__)

HAS_WMI = False
if salt.utils.is_windows():
    # attempt to import the python wmi module
    # the Windows minion uses WMI for some of its grains
    try:
        import wmi
        import salt.utils.winapi
        HAS_WMI = True
    except ImportError:
        log.exception(
            'Unable to import Python wmi module, some core grains '
            'will be missing'
        )


def _windows_cpudata():
    '''
    Return some CPU information on Windows minions
    '''
    # Provides:
    #   num_cpus
    #   cpu_model
    grains = {}
    if 'NUMBER_OF_PROCESSORS' in os.environ:
        # Cast to int so that the logic isn't broken when used as a
        # conditional in templating. Also follows _linux_cpudata()
        try:
            grains['num_cpus'] = int(os.environ['NUMBER_OF_PROCESSORS'])
        except ValueError:
            grains['num_cpus'] = 1
    grains['cpu_model'] = platform.processor()
    return grains


def _linux_cpudata():
    '''
    Return some CPU information for Linux minions
    '''
    # Provides:
    #   num_cpus
    #   cpu_model
    #   cpu_flags
    grains = {}
    cpuinfo = '/proc/cpuinfo'
    # Parse over the cpuinfo file
    if os.path.isfile(cpuinfo):
        with salt.utils.fopen(cpuinfo, 'r') as _fp:
            for line in _fp:
                comps = line.split(':')
                if not len(comps) > 1:
                    continue
                key = comps[0].strip()
                val = comps[1].strip()
                if key == 'processor':
                    grains['num_cpus'] = int(val) + 1
                elif key == 'model name':
                    grains['cpu_model'] = val
                elif key == 'flags':
                    grains['cpu_flags'] = val.split()
                elif key == 'Features':
                    grains['cpu_flags'] = val.split()
                # ARM support - /proc/cpuinfo
                #
                # Processor       : ARMv6-compatible processor rev 7 (v6l)
                # BogoMIPS        : 697.95
                # Features        : swp half thumb fastmult vfp edsp java tls
                # CPU implementer : 0x41
                # CPU architecture: 7
                # CPU variant     : 0x0
                # CPU part        : 0xb76
                # CPU revision    : 7
                #
                # Hardware        : BCM2708
                # Revision        : 0002
                # Serial          : 00000000XXXXXXXX
                elif key == 'Processor':
                    grains['cpu_model'] = val.split('-')[0]
                    grains['num_cpus'] = 1
    if 'num_cpus' not in grains:
        grains['num_cpus'] = 0
    if 'cpu_model' not in grains:
        grains['cpu_model'] = 'Unknown'
    if 'cpu_flags' not in grains:
        grains['cpu_flags'] = []
    return grains


def _linux_gpu_data():
    '''
    num_gpus: int
    gpus:
      - vendor: nvidia|amd|ati|...
        model: string
    '''
    # dominant gpu vendors to search for (MUST be lowercase for matching below)
    known_vendors = ['nvidia', 'amd', 'ati', 'intel']

    devs = []
    try:
        lspci_out = __salt__['cmd.run']('lspci -vmm')

        cur_dev = {}
        error = False
        for line in lspci_out.splitlines():
            # check for record-separating empty lines
            if line == '':
                if cur_dev.get('Class', '') == 'VGA compatible controller':
                    devs.append(cur_dev)
                # XXX; may also need to search for "3D controller"
                cur_dev = {}
                continue
            if re.match(r'^\w+:\s+.*', line):
                key, val = line.split(':', 1)
                cur_dev[key.strip()] = val.strip()
            else:
                error = True
                log.debug('Unexpected lspci output: \'{0}\''.format(line))

        if error:
            log.warn(
                'Error loading grains, unexpected linux_gpu_data output, '
                'check that you have a valid shell configured and '
                'permissions to run lspci command'
            )
    except OSError:
        pass

    gpus = []
    for gpu in devs:
        vendor_strings = gpu['Vendor'].lower().split()
        # default vendor to 'unknown', overwrite if we match a known one
        vendor = 'unknown'
        for name in known_vendors:
            # search for an 'expected' vendor name in the list of strings
            if name in vendor_strings:
                vendor = name
                break
        gpus.append({'vendor': vendor, 'model': gpu['Device']})

    grains = {}
    grains['num_gpus'] = len(gpus)
    grains['gpus'] = gpus
    return grains


def _netbsd_gpu_data():
    '''
    num_gpus: int
    gpus:
      - vendor: nvidia|amd|ati|...
        model: string
    '''
    known_vendors = ['nvidia', 'amd', 'ati', 'intel', 'cirrus logic', 'vmware']

    gpus = []
    try:
        pcictl_out = __salt__['cmd.run']('pcictl pci0 list')

        for line in pcictl_out.splitlines():
            for vendor in known_vendors:
                m = re.match(
                    r'[0-9:]+ ({0}) (.+) \(VGA .+\)'.format(vendor),
                    line,
                    re.IGNORECASE
                )
                if m:
                    gpus.append({'vendor': m.group(1), 'model': m.group(2)})
    except OSError:
        pass

    grains = {}
    grains['num_gpus'] = len(gpus)
    grains['gpus'] = gpus
    return grains


def _bsd_cpudata(osdata):
    '''
    Return CPU information for BSD-like systems
    '''
    # Provides:
    #   cpuarch
    #   num_cpus
    #   cpu_model
    #   cpu_flags
    sysctl = salt.utils.which('sysctl')
    arch = salt.utils.which('arch')
    cmds = {}

    if sysctl:
        cmds.update({
            'num_cpus': '{0} -n hw.ncpu'.format(sysctl),
            'cpuarch': '{0} -n hw.machine'.format(sysctl),
            'cpu_model': '{0} -n hw.model'.format(sysctl),
        })

    if arch and osdata['kernel'] == 'OpenBSD':
        cmds['cpuarch'] = '{0} -s'.format(arch)

    grains = dict([(k, __salt__['cmd.run'](v)) for k, v in cmds.items()])
    grains['cpu_flags'] = []

    if osdata['kernel'] == 'NetBSD':
        for line in __salt__['cmd.run']('cpuctl identify 0').splitlines():
            m = re.match(r'cpu[0-9]:\ features[0-9]?\ .+<(.+)>', line)
            if m:
                flag = m.group(1).split(',')
                grains['cpu_flags'].extend(flag)

    if osdata['kernel'] == 'FreeBSD' and os.path.isfile('/var/run/dmesg.boot'):
        # TODO: at least it needs to be tested for BSD other then FreeBSD
        with salt.utils.fopen('/var/run/dmesg.boot', 'r') as _fp:
            cpu_here = False
            for line in _fp:
                if line.startswith('CPU: '):
                    cpu_here = True  # starts CPU descr
                    continue
                if cpu_here:
                    if not line.startswith(' '):
                        break  # game over
                    if 'Features' in line:
                        start = line.find('<')
                        end = line.find('>')
                        if start > 0 and end > 0:
                            flag = line[start + 1:end].split(',')
                            grains['cpu_flags'].extend(flag)
    try:
        grains['num_cpus'] = int(grains['num_cpus'])
    except ValueError:
        grains['num_cpus'] = 1

    return grains


def _sunos_cpudata():
    '''
    Return the CPU information for Solaris-like systems
    '''
    # Provides:
    #   cpuarch
    #   num_cpus
    #   cpu_model
    #   cpu_flags
    grains = {}
    grains['cpu_flags'] = []

    grains['cpuarch'] = __salt__['cmd.run']('uname -p')
    psrinfo = '/usr/sbin/psrinfo 2>/dev/null'
    grains['num_cpus'] = len(__salt__['cmd.run'](psrinfo).splitlines())
    kstat_info = 'kstat -p cpu_info:0:*:brand'
    for line in __salt__['cmd.run'](kstat_info).splitlines():
        match = re.match(r'(\w+:\d+:\w+\d+:\w+)\s+(.+)', line)
        if match:
            grains['cpu_model'] = match.group(2)
    isainfo = 'isainfo -n -v'
    for line in __salt__['cmd.run'](isainfo).splitlines():
        match = re.match(r'^\s+(.+)', line)
        if match:
            cpu_flags = match.group(1).split()
            grains['cpu_flags'].extend(cpu_flags)

    return grains


def _memdata(osdata):
    '''
    Gather information about the system memory
    '''
    # Provides:
    #   mem_total
    grains = {'mem_total': 0}
    if osdata['kernel'] == 'Linux':
        meminfo = '/proc/meminfo'

        if os.path.isfile(meminfo):
            with salt.utils.fopen(meminfo, 'r') as ifile:
                for line in ifile:
                    comps = line.rstrip('\n').split(':')
                    if not len(comps) > 1:
                        continue
                    if comps[0].strip() == 'MemTotal':
                        grains['mem_total'] = int(comps[1].split()[0]) / 1024
    elif osdata['kernel'] in ('FreeBSD', 'OpenBSD', 'NetBSD'):
        sysctl = salt.utils.which('sysctl')
        if sysctl:
            mem = __salt__['cmd.run']('{0} -n hw.physmem'.format(sysctl))
            if (osdata['kernel'] == 'NetBSD' and mem.startswith('-')):
                mem = __salt__['cmd.run']('{0} -n hw.physmem64'.format(sysctl))
            grains['mem_total'] = str(int(mem) / 1024 / 1024)
    elif osdata['kernel'] == 'SunOS':
        prtconf = '/usr/sbin/prtconf 2>/dev/null'
        for line in __salt__['cmd.run'](prtconf).splitlines():
            comps = line.split(' ')
            if comps[0].strip() == 'Memory' and comps[1].strip() == 'size:':
                grains['mem_total'] = int(comps[2].strip())
    elif osdata['kernel'] == 'Windows' and HAS_WMI:
        with salt.utils.winapi.Com():
            wmi_c = wmi.WMI()
            # this is a list of each stick of ram in a system
            # WMI returns it as the string value of the number of bytes
            tot_bytes = sum(map(lambda x: int(x.Capacity),
                                wmi_c.Win32_PhysicalMemory()), 0)
            # return memory info in gigabytes
            grains['mem_total'] = int(tot_bytes / (1024 ** 2))
    return grains


def _virtual(osdata):
    '''
    Returns what type of virtual hardware is under the hood, kvm or physical
    '''
    # This is going to be a monster, if you are running a vm you can test this
    # grain with please submit patches!
    # Provides:
    #   virtual
    #   virtual_subtype
    grains = {'virtual': 'physical'}
    for command in ('dmidecode', 'lspci', 'dmesg'):
        cmd = salt.utils.which(command)

        if not cmd:
            continue

        ret = __salt__['cmd.run_all'](cmd)

        if ret['retcode'] > 0:
            if salt.log.is_logging_configured():
                if salt.utils.is_windows():
                    continue
                log.warn(
                    'Although \'{0}\' was found in path, the current user '
                    'cannot execute it. Grains output might not be '
                    'accurate.'.format(command)
                )
            continue

        output = ret['stdout']

        if command == 'dmidecode' or command == 'dmesg':
            # Product Name: VirtualBox
            if 'Vendor: QEMU' in output:
                # FIXME: Make this detect between kvm or qemu
                grains['virtual'] = 'kvm'
            if 'Vendor: Bochs' in output:
                grains['virtual'] = 'kvm'
            # Product Name: (oVirt) www.ovirt.org
            # Red Hat Community virtualization Project based on kvm
            elif 'Manufacturer: oVirt' in output:
                grains['virtual'] = 'kvm'
            elif 'VirtualBox' in output:
                grains['virtual'] = 'VirtualBox'
            # Product Name: VMware Virtual Platform
            elif 'VMware' in output:
                grains['virtual'] = 'VMware'
            # Manufacturer: Microsoft Corporation
            # Product Name: Virtual Machine
            elif ': Microsoft' in output and 'Virtual Machine' in output:
                grains['virtual'] = 'VirtualPC'
            # Manufacturer: Parallels Software International Inc.
            elif 'Parallels Software' in output:
                grains['virtual'] = 'Parallels'
            # Break out of the loop, lspci parsing is not necessary
            break
        elif command == 'lspci':
            # dmidecode not available or the user does not have the necessary
            # permissions
            model = output.lower()
            if 'vmware' in model:
                grains['virtual'] = 'VMware'
            # 00:04.0 System peripheral: InnoTek Systemberatung GmbH VirtualBox Guest Service
            elif 'virtualbox' in model:
                grains['virtual'] = 'VirtualBox'
            elif 'qemu' in model:
                grains['virtual'] = 'kvm'
            elif 'virtio' in model:
                grains['virtual'] = 'kvm'
            # Break out of the loop so the next log message is not issued
            break
    else:
        log.warn(
            'The tools \'dmidecode\', \'lspci\' and \'dmesg\' failed to execute '
            'because they do not exist on the system of the user running '
            'this instance or the user does not have the necessary permissions '
            'to execute them. Grains output might not be accurate.'
        )

    choices = ('Linux', 'OpenBSD', 'HP-UX')
    isdir = os.path.isdir
    sysctl = salt.utils.which('sysctl')
    if osdata['kernel'] in choices:
        if isdir('/proc/vz'):
            if os.path.isfile('/proc/vz/version'):
                grains['virtual'] = 'openvzhn'
            else:
                grains['virtual'] = 'openvzve'
        elif isdir('/proc/sys/xen') or isdir('/sys/bus/xen') or isdir('/proc/xen'):
            if os.path.isfile('/proc/xen/xsd_kva'):
                # Tested on CentOS 5.3 / 2.6.18-194.26.1.el5xen
                # Tested on CentOS 5.4 / 2.6.18-164.15.1.el5xen
                grains['virtual_subtype'] = 'Xen Dom0'
            else:
                if grains.get('productname', '') == 'HVM domU':
                    # Requires dmidecode!
                    grains['virtual_subtype'] = 'Xen HVM DomU'
                elif os.path.isfile('/proc/xen/capabilities') and os.access('/proc/xen/capabilities', os.R_OK):
                    caps = salt.utils.fopen('/proc/xen/capabilities')
                    if 'control_d' not in caps.read():
                        # Tested on CentOS 5.5 / 2.6.18-194.3.1.el5xen
                        grains['virtual_subtype'] = 'Xen PV DomU'
                    else:
                        # Shouldn't get to this, but just in case
                        grains['virtual_subtype'] = 'Xen Dom0'
                    caps.close()
                # Tested on Fedora 10 / 2.6.27.30-170.2.82 with xen
                # Tested on Fedora 15 / 2.6.41.4-1 without running xen
                elif isdir('/sys/bus/xen'):
                    if 'xen' in __salt__['cmd.run']('dmesg').lower():
                        grains['virtual_subtype'] = 'Xen PV DomU'
                    elif os.listdir('/sys/bus/xen/drivers'):
                        # An actual DomU will have several drivers
                        # whereas a paravirt ops kernel will  not.
                        grains['virtual_subtype'] = 'Xen PV DomU'
            # If a Dom0 or DomU was detected, obviously this is xen
            if 'dom' in grains.get('virtual_subtype', '').lower():
                grains['virtual'] = 'xen'
        if os.path.isfile('/proc/cpuinfo'):
            if 'QEMU Virtual CPU' in salt.utils.fopen('/proc/cpuinfo', 'r').read():
                grains['virtual'] = 'kvm'
    elif osdata['kernel'] == 'FreeBSD':
        kenv = salt.utils.which('kenv')
        if kenv:
            product = __salt__['cmd.run']('{0} smbios.system.product'.format(kenv))
            maker = __salt__['cmd.run']('{0} smbios.system.maker'.format(kenv))
            if product.startswith('VMware'):
                grains['virtual'] = 'VMware'
            if maker.startswith('Xen'):
                grains['virtual_subtype'] = '{0} {1}'.format(maker, product)
                grains['virtual'] = 'xen'
        if sysctl:
            model = __salt__['cmd.run']('{0} hw.model'.format(sysctl))
            jail = __salt__['cmd.run']('{0} -n security.jail.jailed'.format(sysctl))
            if jail == '1':
                grains['virtual_subtype'] = 'jail'
            if 'QEMU Virtual CPU' in model:
                grains['virtual'] = 'kvm'
    elif osdata['kernel'] == 'SunOS':
        # Check if it's a "regular" zone. (i.e. Solaris 10/11 zone)
        zonename = salt.utils.which('zonename')
        if zonename:
            zone = __salt__['cmd.run']('{0}'.format(zonename))
            if zone != 'global':
                grains['virtual'] = 'zone'
                if osdata['os'] == 'SmartOS':
                    grains.update(_smartos_zone_data())
        # Check if it's a branded zone (i.e. Solaris 8/9 zone)
        if isdir('/.SUNWnative'):
            grains['virtual'] = 'zone'
    elif osdata['kernel'] == 'NetBSD':
        if sysctl:
            if 'QEMU Virtual CPU' in __salt__['cmd.run'](
                    '{0} -n machdep.cpu_brand'.format(sysctl)):
                grains['virtual'] = 'kvm'
            elif not 'invalid' in __salt__['cmd.run'](
                    '{0} -n machdep.xen.suspend'.format(sysctl)):
                grains['virtual'] = 'Xen PV DomU'
            elif 'VMware' in __salt__['cmd.run'](
                    '{0} -n machdep.dmi.system-vendor'.format(sysctl)):
                grains['virtual'] = 'VMware'
            # NetBSD has Xen dom0 support
            elif __salt__['cmd.run'](
                    '{0} -n machdep.idle-mechanism'.format(sysctl)) == 'xen':
                if os.path.isfile('/var/run/xenconsoled.pid'):
                    grains['virtual_subtype'] = 'Xen Dom0'

    return grains


def _ps(osdata):
    '''
    Return the ps grain
    '''
    grains = {}
    bsd_choices = ('FreeBSD', 'NetBSD', 'OpenBSD', 'MacOS')
    if osdata['os'] in bsd_choices:
        grains['ps'] = 'ps auxwww'
    elif osdata['os_family'] == 'Solaris':
        grains['ps'] = '/usr/ucb/ps auxwww'
    elif osdata['os'] == 'Windows':
        grains['ps'] = 'tasklist.exe'
    elif osdata.get('virtual', '') == 'openvzhn':
        grains['ps'] = 'vzps -E 0 -efH|cut -b 6-'
    else:
        grains['ps'] = 'ps -efH'
    return grains


def _windows_platform_data():
    '''
    Use the platform module for as much as we can.
    '''
    # Provides:
    #    osmanufacturer
    #    manufacturer
    #    productname
    #    biosversion
    #    osfullname
    #    timezone
    #    windowsdomain

    if not HAS_WMI:
        return {}

    with salt.utils.winapi.Com():
        wmi_c = wmi.WMI()
        # http://msdn.microsoft.com/en-us/library/windows/desktop/aa394102%28v=vs.85%29.aspx
        systeminfo = wmi_c.Win32_ComputerSystem()[0]
        # http://msdn.microsoft.com/en-us/library/windows/desktop/aa394239%28v=vs.85%29.aspx
        osinfo = wmi_c.Win32_OperatingSystem()[0]
        # http://msdn.microsoft.com/en-us/library/windows/desktop/aa394077(v=vs.85).aspx
        biosinfo = wmi_c.Win32_BIOS()[0]
        # http://msdn.microsoft.com/en-us/library/windows/desktop/aa394498(v=vs.85).aspx
        timeinfo = wmi_c.Win32_TimeZone()[0]

        # the name of the OS comes with a bunch of other data about the install
        # location. For example:
        # 'Microsoft Windows Server 2008 R2 Standard |C:\\Windows|\\Device\\Harddisk0\\Partition2'
        (osfullname, _) = osinfo.Name.split('|', 1)
        osfullname = osfullname.strip()
        grains = {
            'osmanufacturer': osinfo.Manufacturer,
            'manufacturer': systeminfo.Manufacturer,
            'productname': systeminfo.Model,
            # bios name had a bunch of whitespace appended to it in my testing
            # 'PhoenixBIOS 4.0 Release 6.0     '
            'biosversion': biosinfo.Name.strip(),
            'osfullname': osfullname,
            'timezone': timeinfo.Description,
            'windowsdomain': systeminfo.Domain,
        }

    return grains


def id_():
    '''
    Return the id
    '''
    return {'id': __opts__.get('id', '')}

_REPLACE_LINUX_RE = re.compile(r'linux', re.IGNORECASE)

# This maps (at most) the first ten characters (no spaces, lowercased) of
# 'osfullname' to the 'os' grain that Salt traditionally uses.
# Please see os_data() and _supported_dists.
# If your system is not detecting properly it likely needs an entry here.
_OS_NAME_MAP = {
    'redhatente': 'RedHat',
    'gentoobase': 'Gentoo',
    'archarm': 'Arch ARM',
    'arch': 'Arch',
    'debian': 'Debian',
    'debiangnu/': 'Debian',
    'fedoraremi': 'Fedora',
    'amazonami': 'Amazon',
    'alt': 'ALT',
    'oracleserv': 'OEL',
    'cloudserve': 'CloudLinux',
}

# Map the 'os' grain to the 'os_family' grain
# These should always be capitalized entries as the lookup comes
# post-_OS_NAME_MAP. If your system is having trouble with detection, please
# make sure that the 'os' grain is capitalized and working correctly first.
_OS_FAMILY_MAP = {
    'Ubuntu': 'Debian',
    'Fedora': 'RedHat',
    'CentOS': 'RedHat',
    'GoOSe': 'RedHat',
    'Scientific': 'RedHat',
    'Amazon': 'RedHat',
    'CloudLinux': 'RedHat',
    'OVS': 'RedHat',
    'OEL': 'RedHat',
    'XCP': 'RedHat',
    'XenServer': 'RedHat',
    'Mandrake': 'Mandriva',
    'ESXi': 'VMWare',
    'Mint': 'Debian',
    'VMWareESX': 'VMWare',
    'Bluewhite64': 'Bluewhite',
    'Slamd64': 'Slackware',
    'SLES': 'Suse',
    'SUSE Enterprise Server': 'Suse',
    'SUSE  Enterprise Server': 'Suse',
    'SLED': 'Suse',
    'openSUSE': 'Suse',
    'SUSE': 'Suse',
    'Solaris': 'Solaris',
    'SmartOS': 'Solaris',
    'OpenIndiana Development': 'Solaris',
    'Arch ARM': 'Arch',
    'ALT': 'RedHat',
    'Trisquel': 'Debian',
    'GCEL': 'Debian'
}


def os_data():
    '''
    Return grains pertaining to the operating system
    '''
    grains = {
        'num_gpus': 0,
        'gpus': [],
    }

    # Windows Server 2008 64-bit
    # ('Windows', 'MINIONNAME', '2008ServerR2', '6.1.7601', 'AMD64', 'Intel64 Fam ily 6 Model 23 Stepping 6, GenuineIntel')
    # Ubuntu 10.04
    # ('Linux', 'MINIONNAME', '2.6.32-38-server', '#83-Ubuntu SMP Wed Jan 4 11:26:59 UTC 2012', 'x86_64', '')
    (grains['kernel'], grains['nodename'],
     grains['kernelrelease'], version, grains['cpuarch'], _) = platform.uname()
    if salt.utils.is_windows():
        grains['osrelease'] = grains['kernelrelease']
        grains['osversion'] = grains['kernelrelease'] = version
        grains['os'] = 'Windows'
        grains['os_family'] = 'Windows'
        grains.update(_memdata(grains))
        grains.update(_windows_platform_data())
        grains.update(_windows_cpudata())
        grains.update(_ps(grains))
        return grains
    elif salt.utils.is_linux():
        # Add lsb grains on any distro with lsb-release
        try:
            import lsb_release
            release = lsb_release.get_distro_information()
            for key, value in release.iteritems():
                grains['lsb_{0}'.format(key.lower())] = value  # override /etc/lsb-release
        except ImportError:
            # if the python library isn't available, default to regex
            if os.path.isfile('/etc/lsb-release'):
                with salt.utils.fopen('/etc/lsb-release') as ifile:
                    for line in ifile:
                        # Matches any possible format:
                        #     DISTRIB_ID="Ubuntu"
                        #     DISTRIB_ID='Mageia'
                        #     DISTRIB_ID=Fedora
                        #     DISTRIB_RELEASE='10.10'
                        #     DISTRIB_CODENAME='squeeze'
                        #     DISTRIB_DESCRIPTION='Ubuntu 10.10'
                        regex = re.compile('^(DISTRIB_(?:ID|RELEASE|CODENAME|DESCRIPTION))=(?:\'|")?([\\w\\s\\.-_]+)(?:\'|")?')
                        match = regex.match(line.rstrip('\n'))
                        if match:
                            # Adds: lsb_distrib_{id,release,codename,description}
                            grains['lsb_{0}'.format(match.groups()[0].lower())] = match.groups()[1].rstrip()
            elif os.path.isfile('/etc/os-release'):
                # Arch ARM Linux
                with salt.utils.fopen('/etc/os-release') as ifile:
                    # Imitate lsb-release
                    for line in ifile:
                        # NAME="Arch Linux ARM"
                        # ID=archarm
                        # ID_LIKE=arch
                        # PRETTY_NAME="Arch Linux ARM"
                        # ANSI_COLOR="0;36"
                        # HOME_URL="http://archlinuxarm.org/"
                        # SUPPORT_URL="https://archlinuxarm.org/forum"
                        # BUG_REPORT_URL="https://github.com/archlinuxarm/PKGBUILDs/issues"
                        regex = re.compile('^([\\w]+)=(?:\'|")?([\\w\\s\\.-_]+)(?:\'|")?')
                        match = regex.match(line.rstrip('\n'))
                        if match:
                            name, value = match.groups()
                            if name.lower() == 'name':
                                grains['lsb_distrib_id'] = value.strip()
            elif os.path.isfile('/etc/altlinux-release'):
                # ALT Linux
                grains['lsb_distrib_id'] = 'altlinux'
                with salt.utils.fopen('/etc/altlinux-release') as ifile:
                    # This file is symlinked to from:
                    #     /etc/fedora-release
                    #     /etc/redhat-release
                    #     /etc/system-release
                    for line in ifile:
                        # ALT Linux Sisyphus (unstable)
                        comps = line.split()
                        if comps[0] == 'ALT':
                            grains['lsb_distrib_release'] = comps[2]
                            grains['lsb_distrib_codename'] = \
                                comps[3].replace('(', '').replace(')', '')
        # Use the already intelligent platform module to get distro info
        (osname, osrelease, oscodename) = platform.linux_distribution(
            supported_dists=_supported_dists)
        # Try to assign these three names based on the lsb info, they tend to
        # be more accurate than what python gets from /etc/DISTRO-release.
        # It's worth noting that Ubuntu has patched their Python distribution
        # so that platform.linux_distribution() does the /etc/lsb-release
        # parsing, but we do it anyway here for the sake for full portability.
        grains['osfullname'] = grains.get('lsb_distrib_id', osname).strip()
        grains['osrelease'] = grains.get('lsb_distrib_release',
                                         osrelease).strip()
        grains['oscodename'] = grains.get('lsb_distrib_codename',
                                          oscodename).strip()
        distroname = _REPLACE_LINUX_RE.sub('', grains['osfullname']).strip()
        # return the first ten characters with no spaces, lowercased
        shortname = distroname.replace(' ', '').lower()[:10]
        # this maps the long names from the /etc/DISTRO-release files to the
        # traditional short names that Salt has used.
        grains['os'] = _OS_NAME_MAP.get(shortname, distroname)
        grains.update(_linux_cpudata())
        grains.update(_linux_gpu_data())
    elif grains['kernel'] == 'SunOS':
        grains['os_family'] = 'Solaris'
        uname_v = __salt__['cmd.run']('uname -v')
        if 'joyent_' in uname_v:
            # See https://github.com/joyent/smartos-live/issues/224
            grains['os'] = 'SmartOS'
            grains['osrelease'] = uname_v
        elif os.path.isfile('/etc/release'):
            with salt.utils.fopen('/etc/release', 'r') as fp_:
                rel_data = fp_.read()
                try:
                    release_re = r'(Solaris|OpenIndiana(?: Development)?)' \
                                 r'\s+(\d+ \d+\/\d+|oi_\S+)?'
                    osname, osrelease = re.search(release_re,
                                                  rel_data).groups()
                except AttributeError:
                    # Set a blank osrelease grain and fallback to 'Solaris'
                    # as the 'os' grain.
                    grains['os'] = 'Solaris'
                    grains['osrelease'] = ''
                else:
                    grains['os'] = osname
                    grains['osrelease'] = osrelease

        grains.update(_sunos_cpudata())
    elif grains['kernel'] == 'VMkernel':
        grains['os'] = 'ESXi'
    elif grains['kernel'] == 'Darwin':
        grains['os'] = 'MacOS'
        grains.update(_bsd_cpudata(grains))
    else:
        grains['os'] = grains['kernel']
    if grains['kernel'] in ('FreeBSD', 'OpenBSD', 'NetBSD'):
        grains.update(_bsd_cpudata(grains))
        grains['osrelease'] = grains['kernelrelease'].split('-')[0]
        if grains['kernel'] == 'NetBSD':
            grains.update(_netbsd_gpu_data())
    if not grains['os']:
        grains['os'] = 'Unknown {0}'.format(grains['kernel'])
        grains['os_family'] = 'Unknown'
    else:
        # this assigns family names based on the os name
        # family defaults to the os name if not found
        grains['os_family'] = _OS_FAMILY_MAP.get(grains['os'],
                                                 grains['os'])

    grains.update(_memdata(grains))

    # Get the hardware and bios data
    grains.update(_hw_data(grains))

    # Load the virtual machine info
    grains.update(_virtual(grains))
    grains.update(_ps(grains))

    return grains


def locale_info():
    '''
    Provides
        defaultlanguage
        defaultencoding
    '''
    grains = {}
    try:
        (grains['defaultlanguage'], grains['defaultencoding']) = locale.getdefaultlocale()
    except Exception:
        # locale.getdefaultlocale can ValueError!! Catch anything else it
        # might do, per #2205
        grains['defaultlanguage'] = 'unknown'
        grains['defaultencoding'] = 'unknown'
    return grains


def hostname():
    '''
    Return fqdn, hostname, domainname
    '''
    # This is going to need some work
    # Provides:
    #   fqdn
    #   host
    #   localhost
    #   domain
    grains = {}
    grains['localhost'] = socket.gethostname()
    if '.' in socket.getfqdn():
        grains['fqdn'] = socket.getfqdn()
    else:
        grains['fqdn'] = grains['localhost']
    (grains['host'], grains['domain']) = grains['fqdn'].partition('.')[::2]
    return grains


def append_domain():
    '''
    Return append_domain if set
    '''
    grain = {}
    if 'append_domain' in __opts__:
        grain['append_domain'] = __opts__['append_domain']
    return grain


def ip4():
    '''
    Return a list of ipv4 addrs
    '''
    return {'ipv4': salt.utils.network.ip_addrs(include_loopback=True)}


def ip_interfaces():
    '''
    Provide a dict of the connected interfaces and their ip addresses
    '''
    # Provides:
    #   ip_interfaces
    ret = {}
    ifaces = salt.utils.network.interfaces()
    for face in ifaces:
        iface_ips = []
        for inet in ifaces[face].get('inet', []):
            if 'address' in inet:
                iface_ips.append(inet['address'])
        ret[face] = iface_ips
    return {'ip_interfaces': ret}


def path():
    '''
    Return the path
    '''
    # Provides:
    #   path
    return {'path': os.environ['PATH'].strip()}


def pythonversion():
    '''
    Return the Python version
    '''
    # Provides:
    #   pythonversion
    return {'pythonversion': list(sys.version_info)}


def pythonpath():
    '''
    Return the Python path
    '''
    # Provides:
    #   pythonpath
    return {'pythonpath': sys.path}


def saltpath():
    '''
    Return the path of the salt module
    '''
    # Provides:
    #   saltpath
    salt_path = os.path.abspath(os.path.join(__file__, os.path.pardir))
    return {'saltpath': os.path.dirname(salt_path)}


def saltversion():
    '''
    Return the version of salt
    '''
    # Provides:
    #   saltversion
    from salt import __version__
    return {'saltversion': __version__}


# Relatively complex mini-algorithm to iterate over the various
# sections of dmidecode output and return matches for  specific
# lines containing data we want, but only in the right section.
def _dmidecode_data(regex_dict):
    '''
    Parse the output of dmidecode in a generic fashion that can
    be used for the multiple system types which have dmidecode.
    '''
    ret = {}

    # No use running if dmidecode/smbios isn't in the path
    if salt.utils.which('dmidecode'):
        out = __salt__['cmd.run']('dmidecode')
    elif salt.utils.which('smbios'):
        out = __salt__['cmd.run']('smbios')
    else:
        return ret

    for section in regex_dict:
        section_found = False

        # Look at every line for the right section
        for line in out.splitlines():
            if not line:
                continue
            # We've found it, woohoo!
            if re.match(section, line):
                section_found = True
                continue
            if not section_found:
                continue

            # Now that a section has been found, find the data
            for item in regex_dict[section]:
                # Examples:
                #    Product Name: 64639SU
                #    Version: 7LETC1WW (2.21 )
                regex = re.compile(r'\s+{0}\s+(.*)$'.format(item))
                grain = regex_dict[section][item]
                # Skip to the next iteration if this grain
                # has been found in the dmidecode output.
                if grain in ret:
                    continue

                match = regex.match(line)

                # Finally, add the matched data to the grains returned
                if match:
                    ret[grain] = match.group(1).strip()
    return ret


def _hw_data(osdata):
    '''
    Get system specific hardware data from dmidecode

    Provides
        biosversion
        productname
        manufacturer
        serialnumber
        biosreleasedate

    .. versionadded:: 0.9.5
    '''
    grains = {}
    # TODO: *BSD dmidecode output
    if osdata['kernel'] == 'Linux':
        linux_dmi_regex = {
            'BIOS [Ii]nformation': {
                '[Vv]ersion:': 'biosversion',
                '[Rr]elease [Dd]ate:': 'biosreleasedate',
            },
            '[Ss]ystem [Ii]nformation': {
                'Manufacturer:': 'manufacturer',
                'Product(?: Name)?:': 'productname',
                'Serial Number:': 'serialnumber',
            },
        }
        grains.update(_dmidecode_data(linux_dmi_regex))
    elif osdata['kernel'] == 'SunOS':
        sunos_dmi_regex = {
            r'(.+)SMB_TYPE_BIOS\s\(BIOS [Ii]nformation\)': {
                '[Vv]ersion [Ss]tring:': 'biosversion',
                '[Rr]elease [Dd]ate:': 'biosreleasedate',
            },
            r'(.+)SMB_TYPE_SYSTEM\s\([Ss]ystem [Ii]nformation\)': {
                'Manufacturer:': 'manufacturer',
                'Product(?: Name)?:': 'productname',
                'Serial Number:': 'serialnumber',
            },
        }
        grains.update(_dmidecode_data(sunos_dmi_regex))
    # On FreeBSD /bin/kenv (already in base system) can be used instead of dmidecode
    elif osdata['kernel'] == 'FreeBSD':
        kenv = salt.utils.which('kenv')
        if kenv:
            # In theory, it will be easier to add new fields to this later
            fbsd_hwdata = {
                'biosversion': 'smbios.bios.version',
                'manufacturer': 'smbios.system.maker',
                'serialnumber': 'smbios.system.serial',
                'productname': 'smbios.system.product',
                'biosreleasedate': 'smbios.bios.reldate',
            }
            for key, val in fbsd_hwdata.items():
                grains[key] = __salt__['cmd.run']('{0} {1}'.format(kenv, val))
    elif osdata['kernel'] == 'OpenBSD':
        sysctl = salt.utils.which('sysctl')
        hwdata = {'biosversion': 'hw.version',
                  'manufacturer': 'hw.vendor',
                  'productname': 'hw.product',
                  'serialnumber': 'hw.serialno'}
        for key, oid in hwdata.items():
            value = __salt__['cmd.run']('{0} -n {1}'.format(sysctl, oid))
            if not value.endswith(' value is not available'):
                grains[key] = value
    elif osdata['kernel'] == 'NetBSD':
        sysctl = salt.utils.which('sysctl')
        nbsd_hwdata = {
            'biosversion': 'machdep.dmi.board-version',
            'manufacturer': 'machdep.dmi.system-vendor',
            'serialnumber': 'machdep.dmi.system-serial',
            'productname': 'machdep.dmi.system-product',
            'biosreleasedate': 'machdep.dmi.bios-date',
        }
        for key, oid in nbsd_hwdata.items():
            result = __salt__['cmd.run_all']('{0} -n {1}'.format(sysctl, oid))
            if result['retcode'] == 0:
                grains[key] = result['stdout']

    return grains


def _smartos_zone_data():
    '''
    Return useful information from a SmartOS zone
    '''
    # Provides:
    #   pkgsrcversion
    #   imageversion
    grains = {}

    pkgsrcversion = re.compile('^release:\\s(.+)')
    imageversion = re.compile('Image:\\s(.+)')
    if os.path.isfile('/etc/pkgsrc_version'):
        with salt.utils.fopen('/etc/pkgsrc_version', 'r') as fp_:
            for line in fp_:
                match = pkgsrcversion.match(line)
                if match:
                    grains['pkgsrcversion'] = match.group(1)
    if os.path.isfile('/etc/product'):
        with salt.utils.fopen('/etc/product', 'r') as fp_:
            for line in fp_:
                match = imageversion.match(line)
                if match:
                    grains['imageversion'] = match.group(1)
    if 'pkgsrcversion' not in grains:
        grains['pkgsrcversion'] = 'Unknown'
    if 'imageversion' not in grains:
        grains['imageversion'] = 'Unknown'

    return grains


def get_server_id():
    '''
    Provides an integer based on the FQDN of a machine.
    Useful as server-id in MySQL replication or anywhere else you'll need an ID like this.
    '''
    # Provides:
    #   server_id
    return {'server_id': abs(hash(__opts__.get('id', '')) % (2 ** 31))}


def get_master():
    '''
    Provides the minion with the name of its master.
    This is useful in states to target other services running on the master.
    '''
    # Provides:
    #   master
    return {'master': __opts__.get('master', '')}

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
