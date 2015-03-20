# -*- coding: utf-8 -*-
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
from salt._compat import string_types

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod

__salt__ = {
    'cmd.run': salt.modules.cmdmod._run_quiet,
    'cmd.retcode': salt.modules.cmdmod._retcode_quiet,
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

_INTERFACES = {}


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
    if __opts__.get('enable_gpu_grains', True) is False:
        return {}

    lspci = salt.utils.which('lspci')
    if not lspci:
        log.debug(
            'The `lspci` binary is not available on the system. GPU grains '
            'will not be available.'
        )
        return {}

    # dominant gpu vendors to search for (MUST be lowercase for matching below)
    known_vendors = ['nvidia', 'amd', 'ati', 'intel']
    gpu_classes = ('vga compatible controller', '3d controller')

    devs = []
    try:
        lspci_out = __salt__['cmd.run']('lspci -vmm')

        cur_dev = {}
        error = False
        # Add a blank element to the lspci_out.splitlines() list,
        # otherwise the last device is not evaluated as a cur_dev and ignored.
        lspci_list = lspci_out.splitlines()
        lspci_list.append('')
        for line in lspci_list:
            # check for record-separating empty lines
            if line == '':
                if cur_dev.get('Class', '').lower() in gpu_classes:
                    devs.append(cur_dev)
                cur_dev = {}
                continue
            if re.match(r'^\w+:\s+.*', line):
                key, val = line.split(':', 1)
                cur_dev[key.strip()] = val.strip()
            else:
                error = True
                log.debug('Unexpected lspci output: {0!r}'.format(line))

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


def _osx_gpudata():
    '''
    num_gpus: int
    gpus:
      - vendor: nvidia|amd|ati|...
        model: string
    '''

    gpus = []
    try:
        pcictl_out = __salt__['cmd.run']('system_profiler SPDisplaysDataType')

        for line in pcictl_out.splitlines():
            fieldname, _, fieldval = line.partition(': ')
            if fieldname.strip() == "Chipset Model":
                vendor, _, model = fieldval.partition(' ')
                vendor = vendor.lower()
                gpus.append({'vendor': vendor, 'model': model})

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

    if osdata['kernel'] == 'Darwin':
        cmds['cpu_model'] = '{0} -n machdep.cpu.brand_string'.format(sysctl)
        cmds['cpu_flags'] = '{0} -n machdep.cpu.features'.format(sysctl)

    grains = dict([(k, __salt__['cmd.run'](v)) for k, v in cmds.items()])

    if 'cpu_flags' in grains and isinstance(grains['cpu_flags'], string_types):
        grains['cpu_flags'] = grains['cpu_flags'].split(' ')

    if osdata['kernel'] == 'NetBSD':
        grains['cpu_flags'] = []
        for line in __salt__['cmd.run']('cpuctl identify 0').splitlines():
            m = re.match(r'cpu[0-9]:\ features[0-9]?\ .+<(.+)>', line)
            if m:
                flag = m.group(1).split(',')
                grains['cpu_flags'].extend(flag)

    if osdata['kernel'] == 'FreeBSD' and os.path.isfile('/var/run/dmesg.boot'):
        grains['cpu_flags'] = []
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
    grains['num_cpus'] = len(__salt__['cmd.run'](psrinfo, python_shell=True).splitlines())
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
    elif osdata['kernel'] in ('FreeBSD', 'OpenBSD', 'NetBSD', 'Darwin'):
        sysctl = salt.utils.which('sysctl')
        if sysctl:
            if osdata['kernel'] == 'Darwin':
                mem = __salt__['cmd.run']('{0} -n hw.memsize'.format(sysctl))
            else:
                mem = __salt__['cmd.run']('{0} -n hw.physmem'.format(sysctl))
            if osdata['kernel'] == 'NetBSD' and mem.startswith('-'):
                mem = __salt__['cmd.run']('{0} -n hw.physmem64'.format(sysctl))
            grains['mem_total'] = int(mem) / 1024 / 1024
    elif osdata['kernel'] == 'SunOS':
        prtconf = '/usr/sbin/prtconf 2>/dev/null'
        for line in __salt__['cmd.run'](prtconf, python_shell=True).splitlines():
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

    # Skip the below loop on platforms which have none of the desired cmds
    # This is a temporary measure until we can write proper virtual hardware
    # detection.
    skip_cmds = ('AIX',)

    # Check if enable_lspci is True or False
    if __opts__.get('enable_lspci', True) is False:
        _cmds = ('dmidecode', 'dmesg')
    elif osdata['kernel'] in skip_cmds:
        _cmds = ()
    else:
        # /proc/bus/pci does not exists, lspci will fail
        if not os.path.exists('/proc/bus/pci'):
            _cmds = ('dmidecode', 'dmesg', 'systemd-detect-virt', 'virt-what')
        else:
            _cmds = ('dmidecode', 'lspci', 'dmesg', 'systemd-detect-virt', 'virt-what')

    failed_commands = set()
    for command in _cmds:
        args = []
        if osdata['kernel'] == 'Darwin':
            command = 'system_profiler'
            args = ['SPDisplaysDataType']

        cmd = salt.utils.which(command)

        if not cmd:
            continue

        cmd = '{0} {1}'.format(command, ' '.join(args))

        ret = __salt__['cmd.run_all'](cmd)

        if ret['retcode'] > 0:
            if salt.log.is_logging_configured():
                if salt.utils.is_windows():
                    continue
                failed_commands.add(command)
            continue

        output = ret['stdout']
        if command == "system_profiler":
            macoutput = output.lower()
            if '0x1ab8' in macoutput:
                grains['virtual'] = 'Parallels'
            if 'parallels' in macoutput:
                grains['virtual'] = 'Parallels'
            if 'vmware' in macoutput:
                grains['virtual'] = 'VMware'
            if '0x15ad' in macoutput:
                grains['virtual'] = 'VMware'
            if 'virtualbox' in macoutput:
                grains['virtual'] = 'VirtualBox'
            # Break out of the loop so the next log message is not issued
            break
        elif command == 'systemd-detect-virt':
            if output in ('qemu', 'kvm', 'oracle', 'xen', 'bochs', 'chroot', 'uml', 'systemd-nspawn'):
                grains['virtual'] = output
                break
            elif 'vmware' in output:
                grains['virtual'] = 'VMWare'
                break
            elif 'microsoft' in output:
                grains['virtual'] = 'VirtualPC'
                break
            elif 'lxc' in output:
                grains['virtual'] = 'LXC'
                break
            elif 'systemd-nspawn' in output:
                grains['virtual'] = 'LXC'
                break
        elif command == 'virt-what':
            if output in ('kvm', 'qemu', 'uml', 'xen'):
                grains['virtual'] = output
                break
            elif 'vmware' in output:
                grains['virtual'] = 'VMWare'
                break
            elif 'parallels' in output:
                grains['virtual'] = 'Parallels'
                break
            elif 'hyperv' in output:
                grains['virtual'] = 'HyperV'
                break
        elif command == 'dmidecode' or command == 'dmesg':
            # Product Name: VirtualBox
            if 'Vendor: QEMU' in output:
                # FIXME: Make this detect between kvm or qemu
                grains['virtual'] = 'kvm'
            if 'Vendor: Bochs' in output:
                grains['virtual'] = 'kvm'
            if 'BHYVE  BVXSDT' in output:
                grains['virtual'] = 'bhyve'
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
            elif 'Manufacturer: Google' in output:
                grains['virtual'] = 'kvm'
            # Break out of the loop, lspci parsing is not necessary
            break
        elif command == 'lspci':
            # dmidecode not available or the user does not have the necessary
            # permissions
            model = output.lower()
            if 'vmware' in model:
                grains['virtual'] = 'VMware'
            # 00:04.0 System peripheral: InnoTek Systemberatung GmbH
            #         VirtualBox Guest Service
            elif 'virtualbox' in model:
                grains['virtual'] = 'VirtualBox'
            elif 'qemu' in model:
                grains['virtual'] = 'kvm'
            elif 'virtio' in model:
                grains['virtual'] = 'kvm'
            # Break out of the loop so the next log message is not issued
            break
    else:
        if osdata['kernel'] in skip_cmds:
            log.warn(
                'The tools \'dmidecode\', \'lspci\' and \'dmesg\' failed to '
                'execute because they do not exist on the system of the user '
                'running this instance or the user does not have the '
                'necessary permissions to execute them. Grains output might '
                'not be accurate.'
            )

    choices = ('Linux', 'OpenBSD', 'HP-UX')
    isdir = os.path.isdir
    sysctl = salt.utils.which('sysctl')
    if osdata['kernel'] in choices:
        if os.path.isfile('/proc/1/cgroup'):
            try:
                with salt.utils.fopen('/proc/1/cgroup', 'r') as fhr:
                    if ':/lxc/' in fhr.read():
                        grains['virtual_subtype'] = 'LXC'
                with salt.utils.fopen('/proc/1/cgroup', 'r') as fhr:
                    if ':/docker/' in fhr.read():
                        grains['virtual_subtype'] = 'Docker'
            except IOError:
                pass
        if isdir('/proc/vz'):
            if os.path.isfile('/proc/vz/version'):
                grains['virtual'] = 'openvzhn'
            elif os.path.isfile('/proc/vz/veinfo'):
                grains['virtual'] = 'openvzve'
                # a posteriori, it's expected for these to have failed:
                failed_commands.discard('lspci')
                failed_commands.discard('dmidecode')
        # Provide additional detection for OpenVZ
        if os.path.isfile('/proc/self/status'):
            with salt.utils.fopen('/proc/self/status') as status_file:
                vz_re = re.compile(r'^envID:\s+(\d+)$')
                for line in status_file:
                    vz_match = vz_re.match(line.rstrip('\n'))
                    if vz_match and int(vz_match.groups()[0]) != 0:
                        grains['virtual'] = 'openvzve'
                    elif vz_match and int(vz_match.groups()[0]) == 0:
                        grains['virtual'] = 'openvzhn'
        if isdir('/proc/sys/xen') or \
                isdir('/sys/bus/xen') or isdir('/proc/xen'):
            if os.path.isfile('/proc/xen/xsd_kva'):
                # Tested on CentOS 5.3 / 2.6.18-194.26.1.el5xen
                # Tested on CentOS 5.4 / 2.6.18-164.15.1.el5xen
                grains['virtual_subtype'] = 'Xen Dom0'
            else:
                if grains.get('productname', '') == 'HVM domU':
                    # Requires dmidecode!
                    grains['virtual_subtype'] = 'Xen HVM DomU'
                elif os.path.isfile('/proc/xen/capabilities') and \
                        os.access('/proc/xen/capabilities', os.R_OK):
                    with salt.utils.fopen('/proc/xen/capabilities') as fhr:
                        if 'control_d' not in fhr.read():
                            # Tested on CentOS 5.5 / 2.6.18-194.3.1.el5xen
                            grains['virtual_subtype'] = 'Xen PV DomU'
                        else:
                            # Shouldn't get to this, but just in case
                            grains['virtual_subtype'] = 'Xen Dom0'
                # Tested on Fedora 10 / 2.6.27.30-170.2.82 with xen
                # Tested on Fedora 15 / 2.6.41.4-1 without running xen
                elif isdir('/sys/bus/xen'):
                    if 'xen:' in __salt__['cmd.run']('dmesg').lower():
                        grains['virtual_subtype'] = 'Xen PV DomU'
                    elif os.listdir('/sys/bus/xen/drivers'):
                        # An actual DomU will have several drivers
                        # whereas a paravirt ops kernel will  not.
                        grains['virtual_subtype'] = 'Xen PV DomU'
            # If a Dom0 or DomU was detected, obviously this is xen
            if 'dom' in grains.get('virtual_subtype', '').lower():
                grains['virtual'] = 'xen'
        if os.path.isfile('/proc/cpuinfo'):
            with salt.utils.fopen('/proc/cpuinfo', 'r') as fhr:
                if 'QEMU Virtual CPU' in fhr.read():
                    grains['virtual'] = 'kvm'
    elif osdata['kernel'] == 'FreeBSD':
        kenv = salt.utils.which('kenv')
        if kenv:
            product = __salt__['cmd.run'](
                '{0} smbios.system.product'.format(kenv)
            )
            maker = __salt__['cmd.run']('{0} smbios.system.maker'.format(kenv))
            if product.startswith('VMware'):
                grains['virtual'] = 'VMware'
            if maker.startswith('Xen'):
                grains['virtual_subtype'] = '{0} {1}'.format(maker, product)
                grains['virtual'] = 'xen'
            if maker.startswith('Microsoft') and product.startswith('Virtual'):
                grains['virtual'] = 'VirtualPC'
            if maker.startswith('OpenStack'):
                grains['virtual'] = 'OpenStack'
        if sysctl:
            model = __salt__['cmd.run']('{0} hw.model'.format(sysctl))
            jail = __salt__['cmd.run'](
                '{0} -n security.jail.jailed'.format(sysctl)
            )
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
            elif 'invalid' not in __salt__['cmd.run'](
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

    for command in failed_commands:
        log.warn(
            'Although {0!r} was found in path, the current user '
            'cannot execute it. Grains output might not be '
            'accurate.'.format(command)
        )
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
        grains['ps'] = (
            'ps -fH -p $(grep -l \"^envID:[[:space:]]*0\\$\" '
            '/proc/[0-9]*/status | sed -e \"s=/proc/\\([0-9]*\\)/.*=\\1=\")  '
            '| awk \'{ $7=\"\"; print }\''
        )
    elif osdata['os_family'] == 'Debian':
        grains['ps'] = 'ps -efHww'
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

        # test for virtualized environments
        # I only had VMware available so the rest are unvalidated
        if 'VRTUAL' in biosinfo.Version:  # (not a typo)
            grains['virtual'] = 'HyperV'
        elif 'A M I' in biosinfo.Version:
            grains['virtual'] = 'VirtualPC'
        elif 'VMware' in systeminfo.Model:
            grains['virtual'] = 'VMware'
        elif 'VirtualBox' in systeminfo.Model:
            grains['virtual'] = 'VirtualBox'
        elif 'Xen' in biosinfo.Version:
            grains['virtual'] = 'Xen'
            if 'HVM domU' in systeminfo.Model:
                grains['virtual_subtype'] = 'HVM domU'
        elif 'OpenStack' in systeminfo.Model:
            grains['virtual'] = 'OpenStack'

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
    'raspbiangn': 'Raspbian',
    'fedoraremi': 'Fedora',
    'amazonami': 'Amazon',
    'alt': 'ALT',
    'enterprise': 'OEL',
    'oracleserv': 'OEL',
    'cloudserve': 'CloudLinux',
    'pidora': 'Fedora',
    'scientific': 'ScientificLinux',
    'synology': 'Synology'
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
    'OpenIndiana': 'Solaris',
    'OpenSolaris Development': 'Solaris',
    'OpenSolaris': 'Solaris',
    'Arch ARM': 'Arch',
    'ALT': 'RedHat',
    'Trisquel': 'Debian',
    'GCEL': 'Debian',
    'Linaro': 'Debian',
    'elementary OS': 'Debian',
    'ScientificLinux': 'RedHat',
    'Raspbian': 'Debian'
}


def _linux_bin_exists(binary):
    '''
    Does a binary exist in linux (depends on which)
    '''
    return __salt__['cmd.retcode'](
        'which {0}'.format(binary)
    ) == 0


def _get_interfaces():
    '''
    Provide a dict of the connected interfaces and their ip addresses
    '''

    global _INTERFACES
    if not _INTERFACES:
        _INTERFACES = salt.utils.network.interfaces()
    return _INTERFACES


def os_data():
    '''
    Return grains pertaining to the operating system
    '''
    grains = {
        'num_gpus': 0,
        'gpus': [],
        }

    # Windows Server 2008 64-bit
    # ('Windows', 'MINIONNAME', '2008ServerR2', '6.1.7601', 'AMD64',
    #  'Intel64 Fam ily 6 Model 23 Stepping 6, GenuineIntel')
    # Ubuntu 10.04
    # ('Linux', 'MINIONNAME', '2.6.32-38-server',
    # '#83-Ubuntu SMP Wed Jan 4 11:26:59 UTC 2012', 'x86_64', '')

    # pylint: disable=unpacking-non-sequence
    (grains['kernel'], grains['nodename'],
     grains['kernelrelease'], version, grains['cpuarch'], _) = platform.uname()
    # pylint: enable=unpacking-non-sequence

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
        # Add SELinux grain, if you have it
        if _linux_bin_exists('selinuxenabled'):
            grains['selinux'] = {}
            grains['selinux']['enabled'] = __salt__['cmd.retcode'](
                'selinuxenabled'
            ) == 0
            if _linux_bin_exists('getenforce'):
                grains['selinux']['enforced'] = __salt__['cmd.run'](
                    'getenforce'
                ).strip()

        # Add lsb grains on any distro with lsb-release
        try:
            import lsb_release
            release = lsb_release.get_distro_information()
            for key, value in release.iteritems():
                key = key.lower()
                lsb_param = 'lsb_{0}{1}'.format(
                    '' if key.startswith('distrib_') else 'distrib_',
                    key
                )
                grains[lsb_param] = value
        except ImportError:
            # if the python library isn't available, default to regex
            if os.path.isfile('/etc/lsb-release'):
                # Matches any possible format:
                #     DISTRIB_ID="Ubuntu"
                #     DISTRIB_ID='Mageia'
                #     DISTRIB_ID=Fedora
                #     DISTRIB_RELEASE='10.10'
                #     DISTRIB_CODENAME='squeeze'
                #     DISTRIB_DESCRIPTION='Ubuntu 10.10'
                regex = re.compile((
                    '^(DISTRIB_(?:ID|RELEASE|CODENAME|DESCRIPTION))=(?:\'|")?'
                    '([\\w\\s\\.-_]+)(?:\'|")?'
                ))
                with salt.utils.fopen('/etc/lsb-release') as ifile:
                    for line in ifile:
                        match = regex.match(line.rstrip('\n'))
                        if match:
                            # Adds:
                            #   lsb_distrib_{id,release,codename,description}
                            grains[
                                'lsb_{0}'.format(match.groups()[0].lower())
                            ] = match.groups()[1].rstrip()
            if 'lsb_distrib_id' not in grains:
                if os.path.isfile('/etc/os-release'):
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
                            # BUG_REPORT_URL=
                            #   "https://github.com/archlinuxarm/PKGBUILDs/issues"
                            regex = re.compile(
                                '^([\\w]+)=(?:\'|")?([\\w\\s\\.-_]+)(?:\'|")?'
                            )
                            match = regex.match(line.rstrip('\n'))
                            if match:
                                name, value = match.groups()
                                if name.lower() == 'name':
                                    grains['lsb_distrib_id'] = value.strip()
                elif os.path.isfile('/etc/SuSE-release'):
                    grains['lsb_distrib_id'] = 'SUSE'
                    with salt.utils.fopen('/etc/SuSE-release') as fhr:
                        rel = re.sub("[^0-9]", "", fhr.read().split('\n')[1])
                    with salt.utils.fopen('/etc/SuSE-release') as fhr:
                        patch = re.sub("[^0-9]", "", fhr.read().split('\n')[2])
                    release = rel + " SP" + patch
                    grains['lsb_distrib_release'] = release
                    grains['lsb_distrib_codename'] = "n.a"
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
                elif os.path.isfile('/etc/centos-release'):
                    # CentOS Linux
                    grains['lsb_distrib_id'] = 'CentOS'
                    with salt.utils.fopen('/etc/centos-release') as ifile:
                        for line in ifile:
                            # Need to pull out the version and codename
                            # in the case of custom content in /etc/centos-release
                            find_release = re.compile(r'\d+\.\d+')
                            find_codename = re.compile(r'(?<=\()(.*?)(?=\))')
                            release = find_release.search(line)
                            codename = find_codename.search(line)
                            if release is not None:
                                grains['lsb_distrib_release'] = release.group()
                            if codename is not None:
                                grains['lsb_distrib_codename'] = codename.group()
                elif os.path.isfile('/etc.defaults/VERSION') \
                        and os.path.isfile('/etc.defaults/synoinfo.conf'):
                    grains['osfullname'] = 'Synology'
                    with salt.utils.fopen('/etc.defaults/VERSION', 'r') as fp_:
                        synoinfo = {}
                        for line in fp_:
                            try:
                                key, val = line.rstrip('\n').split('=')
                            except ValueError:
                                continue
                            if key in ('majorversion', 'minorversion',
                                       'buildnumber'):
                                synoinfo[key] = val.strip('"')
                        if len(synoinfo) != 3:
                            log.warning(
                                'Unable to determine Synology version info. '
                                'Please report this, as it is likely a bug.'
                            )
                        else:
                            grains['osrelease'] = (
                                '{majorversion}.{minorversion}-{buildnumber}'
                                .format(**synoinfo)
                            )

        # Use the already intelligent platform module to get distro info
        # (though apparently it's not intelligent enough to strip quotes)
        (osname, osrelease, oscodename) = \
            [x.strip('"').strip("'") for x in
             platform.linux_distribution(supported_dists=_supported_dists)]
        # Try to assign these three names based on the lsb info, they tend to
        # be more accurate than what python gets from /etc/DISTRO-release.
        # It's worth noting that Ubuntu has patched their Python distribution
        # so that platform.linux_distribution() does the /etc/lsb-release
        # parsing, but we do it anyway here for the sake for full portability.
        if 'osfullname' not in grains:
            grains['osfullname'] = \
                grains.get('lsb_distrib_id', osname).strip()
        if 'osrelease' not in grains:
            grains['osrelease'] = \
                grains.get('lsb_distrib_release', osrelease).strip()
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
            grains['os'] = grains['osfullname'] = 'SmartOS'
            grains['osrelease'] = uname_v
        elif os.path.isfile('/etc/release'):
            with salt.utils.fopen('/etc/release', 'r') as fp_:
                rel_data = fp_.read()
                try:
                    release_re = re.compile(
                        r'((?:Open)?Solaris|OpenIndiana) (Development)?'
                        r'\s*(\d+ \d+\/\d+|oi_\S+|snv_\S+)?'
                    )
                    osname, development, osrelease = \
                        release_re.search(rel_data).groups()
                except AttributeError:
                    # Set a blank osrelease grain and fallback to 'Solaris'
                    # as the 'os' grain.
                    grains['os'] = grains['osfullname'] = 'Solaris'
                    grains['osrelease'] = ''
                else:
                    if development is not None:
                        osname = ' '.join((osname, development))
                    grains['os'] = grains['osfullname'] = osname
                    grains['osrelease'] = osrelease

        grains.update(_sunos_cpudata())
    elif grains['kernel'] == 'VMkernel':
        grains['os'] = 'ESXi'
    elif grains['kernel'] == 'Darwin':
        osrelease = __salt__['cmd.run']('sw_vers -productVersion')
        grains['os'] = 'MacOS'
        grains['osrelease'] = osrelease
        grains.update(_bsd_cpudata(grains))
        grains.update(_osx_gpudata())
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

    # Build the osarch grain. This grain will be used for platform-specific
    # considerations such as package management. Fall back to the CPU
    # architecture.
    if grains.get('os_family') == 'Debian':
        osarch = __salt__['cmd.run']('dpkg --print-architecture').strip()
    elif grains.get('os') == 'Fedora':
        osarch = __salt__['cmd.run']('rpm --eval %{_host_cpu}').strip()
    else:
        osarch = grains['cpuarch']
    grains['osarch'] = osarch

    grains.update(_memdata(grains))

    # Get the hardware and bios data
    grains.update(_hw_data(grains))

    # Load the virtual machine info
    grains.update(_virtual(grains))
    grains.update(_ps(grains))

    # Load additional OS family grains
    if grains['os_family'] == "RedHat":
        grains['osmajorrelease'] = grains['osrelease'].split('.', 1)[0]

        grains['osfinger'] = '{os}-{ver}'.format(
            os=grains['osfullname'],
            ver=grains['osrelease'].partition('.')[0])
    elif grains.get('osfullname') == 'Ubuntu':
        grains['osfinger'] = '{os}-{ver}'.format(
            os=grains['osfullname'],
            ver=grains['osrelease'])
    elif grains.get('os') in ('FreeBSD', 'OpenBSD', 'NetBSD'):
        grains['osmajorrelease'] = grains['osrelease'].split('.', 1)[0]

        grains['osfinger'] = '{os}-{ver}'.format(
            os=grains['os'],
            ver=grains['osrelease'])

    if grains.get('osrelease', ''):
        osrelease_info = grains['osrelease'].split('.')
        for idx, value in enumerate(osrelease_info):
            if not value.isdigit():
                continue
            osrelease_info[idx] = int(value)
        grains['osrelease_info'] = tuple(osrelease_info)

    return grains


def locale_info():
    '''
    Provides
        defaultlanguage
        defaultencoding
    '''
    grains = {}
    grains['locale_info'] = {}

    if 'proxyminion' in __opts__:
        return grains

    try:
        (
            grains['locale_info']['defaultlanguage'],
            grains['locale_info']['defaultencoding']
        ) = locale.getdefaultlocale()
    except Exception:
        # locale.getdefaultlocale can ValueError!! Catch anything else it
        # might do, per #2205
        grains['locale_info']['defaultlanguage'] = 'unknown'
        grains['locale_info']['defaultencoding'] = 'unknown'
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

    if 'proxyminion' in __opts__:
        return grains

    grains['localhost'] = socket.gethostname()
    grains['fqdn'] = salt.utils.network.get_fqhostname()
    (grains['host'], grains['domain']) = grains['fqdn'].partition('.')[::2]
    return grains


def append_domain():
    '''
    Return append_domain if set
    '''

    grain = {}

    if 'proxyminion' in __opts__:
        return grain

    if 'append_domain' in __opts__:
        grain['append_domain'] = __opts__['append_domain']
    return grain


def ip4():
    '''
    Return a list of ipv4 addrs
    '''

    if 'proxyminion' in __opts__:
        return {}

    return {'ipv4': salt.utils.network.ip_addrs(include_loopback=True)}


def fqdn_ip4():
    '''
    Return a list of ipv4 addrs of fqdn
    '''

    if 'proxyminion' in __opts__:
        return {}

    try:
        info = socket.getaddrinfo(hostname()['fqdn'], None, socket.AF_INET)
        addrs = list(set(item[4][0] for item in info))
    except socket.error:
        addrs = []
    return {'fqdn_ip4': addrs}


def ip6():
    '''
    Return a list of ipv6 addrs
    '''

    if 'proxyminion' in __opts__:
        return {}

    return {'ipv6': salt.utils.network.ip_addrs6(include_loopback=True)}


def fqdn_ip6():
    '''
    Return a list of ipv6 addrs of fqdn
    '''

    if 'proxyminion' in __opts__:
        return {}

    try:
        info = socket.getaddrinfo(hostname()['fqdn'], None, socket.AF_INET6)
        addrs = list(set(item[4][0] for item in info))
    except socket.error:
        addrs = []
    return {'fqdn_ip6': addrs}


def ip_interfaces():
    '''
    Provide a dict of the connected interfaces and their ip addresses
    '''
    # Provides:
    #   ip_interfaces

    if 'proxyminion' in __opts__:
        return {}

    ret = {}
    ifaces = _get_interfaces()
    for face in ifaces:
        iface_ips = []
        for inet in ifaces[face].get('inet', []):
            if 'address' in inet:
                iface_ips.append(inet['address'])
        for secondary in ifaces[face].get('secondary', []):
            if 'address' in secondary:
                iface_ips.append(secondary['address'])
        ret[face] = iface_ips
    return {'ip_interfaces': ret}


def ip4_interfaces():
    '''
    Provide a dict of the connected interfaces and their ip4 addresses
    '''
    # Provides:
    #   ip_interfaces

    if 'proxyminion' in __opts__:
        return {}

    ret = {}
    ifaces = _get_interfaces()
    for face in ifaces:
        iface_ips = []
        for inet in ifaces[face].get('inet', []):
            if 'address' in inet:
                iface_ips.append(inet['address'])
        for secondary in ifaces[face].get('secondary', []):
            if 'address' in secondary:
                iface_ips.append(secondary['address'])
        ret[face] = iface_ips
    return {'ip4_interfaces': ret}


def ip6_interfaces():
    '''
    Provide a dict of the connected interfaces and their ip6 addresses
    '''
    # Provides:
    #   ip_interfaces

    if 'proxyminion' in __opts__:
        return {}

    ret = {}
    ifaces = _get_interfaces()
    for face in ifaces:
        iface_ips = []
        for inet in ifaces[face].get('inet6', []):
            if 'address' in inet:
                iface_ips.append(inet['address'])
        for secondary in ifaces[face].get('secondary', []):
            if 'address' in secondary:
                iface_ips.append(secondary['address'])
        ret[face] = iface_ips
    return {'ip6_interfaces': ret}


def hwaddr_interfaces():
    '''
    Provide a dict of the connected interfaces and their
    hw addresses (Mac Address)
    '''
    # Provides:
    #   hwaddr_interfaces
    ret = {}
    ifaces = _get_interfaces()
    for face in ifaces:
        if 'hwaddr' in ifaces[face]:
            ret[face] = ifaces[face]['hwaddr']
    return {'hwaddr_interfaces': ret}


def get_machine_id():
    '''
    Provide the machine-id
    '''
    # Provides:
    #   machine-id
    locations = ['/etc/machine-id', '/var/lib/dbus/machine-id']
    existing_locations = [loc for loc in locations if os.path.exists(loc)]
    if not existing_locations:
        return {}
    else:
        with salt.utils.fopen(existing_locations[0]) as machineid:
            return {'machine_id': machineid.read().strip()}


def path():
    '''
    Return the path
    '''
    # Provides:
    #   path
    return {'path': os.environ.get('PATH', '').strip()}


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


def pythonexecutable():
    '''
    Return the python executable in use
    '''
    # Provides:
    #   pythonexecutable
    return {'pythonexecutable': sys.executable}


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
    from salt.version import __version__
    return {'saltversion': __version__}


def zmqversion():
    '''
    Return the zeromq version
    '''
    # Provides:
    #   zmqversion
    try:
        import zmq
        return {'zmqversion': zmq.zmq_version()}
    except ImportError:
        return {}


def saltversioninfo():
    '''
    Return the version_info of salt

     .. versionadded:: 0.17.0
    '''
    # Provides:
    #   saltversioninfo
    from salt.version import __version_info__
    return {'saltversioninfo': __version_info__}


# Relatively complex mini-algorithm to iterate over the various
# sections of dmidecode output and return matches for  specific
# lines containing data we want, but only in the right section.
def _dmidecode_data(regex_dict):
    '''
    Parse the output of dmidecode in a generic fashion that can
    be used for the multiple system types which have dmidecode.
    '''
    ret = {}

    if 'proxyminion' in __opts__:
        return {}

    # No use running if dmidecode/smbios isn't in the path
    if salt.utils.which('dmidecode'):
        out = __salt__['cmd.run']('dmidecode')
    elif salt.utils.which('smbios'):
        out = __salt__['cmd.run']('smbios')
    else:
        log.debug(
            'The `dmidecode` binary is not available on the system. GPU '
            'grains will not be available.'
        )
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

    if 'proxyminion' in __opts__:
        return {}

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
    # On FreeBSD /bin/kenv (already in base system)
    # can be used instead of dmidecode
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
    #   pkgsrcpath
    #   zonename
    #   zoneid
    #   hypervisor_uuid
    #   datacenter

    if 'proxyminion' in __opts__:
        return {}

    grains = {}

    pkgsrcversion = re.compile('^release:\\s(.+)')
    imageversion = re.compile('Image:\\s(.+)')
    pkgsrcpath = re.compile('PKG_PATH=(.+)')
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
    if os.path.isfile('/opt/local/etc/pkg_install.conf'):
        with salt.utils.fopen('/opt/local/etc/pkg_install.conf', 'r') as fp_:
            for line in fp_:
                match = pkgsrcpath.match(line)
                if match:
                    grains['pkgsrcpath'] = match.group(1)
    if 'pkgsrcversion' not in grains:
        grains['pkgsrcversion'] = 'Unknown'
    if 'imageversion' not in grains:
        grains['imageversion'] = 'Unknown'
    if 'pkgsrcpath' not in grains:
        grains['pkgsrcpath'] = 'Unknown'

    grains['zonename'] = __salt__['cmd.run']('zonename')
    grains['zoneid'] = __salt__['cmd.run']('zoneadm list -p | awk -F: \'{ print $1 }\'', python_shell=True)
    grains['hypervisor_uuid'] = __salt__['cmd.run']('mdata-get sdc:server_uuid')
    grains['datacenter'] = __salt__['cmd.run']('mdata-get sdc:datacenter_name')
    if "FAILURE" in grains['datacenter'] or "No metadata" in grains['datacenter']:
        grains['datacenter'] = "Unknown"

    return grains


def get_server_id():
    '''
    Provides an integer based on the FQDN of a machine.
    Useful as server-id in MySQL replication or anywhere else you'll need an ID
    like this.
    '''
    # Provides:
    #   server_id

    if 'proxyminion' in __opts__:
        return {}
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
