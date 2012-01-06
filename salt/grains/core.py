'''
The static grains, these are the core, or built in grains.

When grains are loaded they are not loaded in the same way that modules are
loaded, grain functions are detected and executed, the functions MUST
return a dict which will be applied to the main grains dict. This module
will always be executed first, so that any grains loaded here in the core
module can be overwritten just by returning dict keys with the same value
as those returned here
'''

# This needs some refactoring, I made it "as fast as I could" and could be a
# lot clearer, so far it is spaghetti code
# Import python modules

import os
import socket
import sys
import re
import platform
import salt.utils

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmd
__salt__ = {'cmd.run': salt.modules.cmd._run_quiet}


def _kernel():
    '''
    Return the kernel type
    '''
    # Provides:
    # kernel
    grains = {}
    grains['kernel'] = __salt__['cmd.run']('uname -s').strip()

    if grains['kernel'] == 'aix':
        grains['kernelrelease'] = __salt__['cmd.run']('oslevel -s').strip()
    else:
        grains['kernelrelease'] = __salt__['cmd.run']('uname -r').strip()
    if 'kernel' not in grains:
        grains['kernel'] = 'Unknown'
    if not grains['kernel']:
        grains['kernel'] = 'Unknown'
    return grains

def _windows_cpudata():
    '''
    Return the cpu information for Windows systems architecture
    '''
    # Provides:
    #   cpuarch
    #   num_cpus
    #   cpu_model
    grains = {}
    grains['cpuarch'] = platform.machine()
    if 'NUMBER_OF_PROCESSORS' in os.environ:
        grains['num_cpus'] = os.environ['NUMBER_OF_PROCESSORS']
    grains['cpu_model'] = platform.processor()
    return grains

def _linux_cpudata():
    '''
    Return the cpu information for Linux systems architecture
    '''
    # Provides:
    #   cpuarch
    #   num_cpus
    #   cpu_model
    #   cpu_flags
    grains = {}
    cpuinfo = '/proc/cpuinfo'
    # Grab the Arch
    arch = __salt__['cmd.run']('uname -m').strip()
    grains['cpuarch'] = arch
    # Some systems such as Debian don't like uname -m
    # so fallback gracefully to the processor type
    if not grains['cpuarch'] or grains['cpuarch'] == 'unknown':
        arch = __salt__['cmd.run']('uname -p')
        grains['cpuarch'] = arch
    if not grains['cpuarch'] or grains['cpuarch'] == 'unknown':
        arch = __salt__['cmd.run']('uname -i')
        grains['cpuarch'] = arch
    if not grains['cpuarch'] or grains['cpuarch'] == 'unknown':
        grains['cpuarch'] = 'Unknown'
    # Parse over the cpuinfo file
    if os.path.isfile(cpuinfo):
        for line in open(cpuinfo, 'r').readlines():
            comps = line.split(':')
            if not len(comps) > 1:
                continue
            if comps[0].strip() == 'processor':
                grains['num_cpus'] = int(comps[1].strip()) + 1
            elif comps[0].strip() == 'model name':
                grains['cpu_model'] = comps[1].strip()
            elif comps[0].strip() == 'flags':
                grains['cpu_flags'] = comps[1].split()
    if 'num_cpus' not in grains:
        grains['num_cpus'] = 0
    if 'cpu_model' not in grains:
        grains['cpu_model'] = 'Unknown'
    if 'cpu_flags' not in grains:
        grains['cpu_flags'] = []
    return grains


def _freebsd_cpudata():
    '''
    Return cpu information for FreeBSD systems
    '''
    grains = {}
    sysctl = salt.utils.which('sysctl')

    if sysctl:
        machine_cmd = '{0} -n hw.machine'.format(sysctl)
        ncpu_cmd    = '{0} -n hw.ncpu'.format(sysctl)
        model_cpu   = '{0} -n hw.model'.format(sysctl)
        grains['num_cpus'] = __salt__['cmd.run'](ncpu_cmd).strip()
        grains['cpu_model'] = __salt__['cmd.run'](model_cpu).strip()
        grains['cpuarch'] = __salt__['cmd.run'](machine_cmd).strip()
        grains['cpu_flags'] = []
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
            for line in open(meminfo, 'r').readlines():
                comps = line.split(':')
                if not len(comps) > 1:
                    continue
                if comps[0].strip() == 'MemTotal':
                    grains['mem_total'] = int(comps[1].split()[0]) / 1024
    elif osdata['kernel'] in ('FreeBSD','OpenBSD'):
        sysctl = salt.utils.which('sysctl')
        if sysctl:
            mem = __salt__['cmd.run']('{0} -n hw.physmem'.format(sysctl)).strip()
            grains['mem_total'] = str(int(mem) / 1024 / 1024)
    elif osdata['kernel'] == 'Windows':
       for line in __salt__['cmd.run']('SYSTEMINFO /FO LIST').split('\n'):
           comps = line.split(':')
           if not len(comps) > 1:
               continue
           if comps[0].strip() == 'Total Physical Memory':
               grains['mem_total'] = int(comps[1].split()[0].replace(',', ''))
               break

    return grains


def _virtual(osdata):
    '''
    Returns what type of virtual hardware is under the hood, kvm or physical
    '''
    # This is going to be a monster, if you are running a vm you can test this
    # grain with please submit patches!
    # Provides:
    #   virtual
    grains = {'virtual': 'physical'}
    lspci = salt.utils.which('lspci')
    dmidecode = salt.utils.which('dmidecode')

    if dmidecode:
        output = __salt__['cmd.run']('dmidecode')
        # Product Name: VirtualBox
        if 'Vendor: QEMU' in output:
            # FIXME: Make this detect between kvm or qemu
            grains['virtual'] = 'kvm'
        elif 'VirtualBox' in output:
            grains['virtual'] = 'VirtualBox'
        # Product Name: VMware Virtual Platform
        elif 'VMware' in output:
            grains['virtual'] = 'VMware'
        # Manufacturer: Microsoft Corporation
        # Product Name: Virtual Machine
        elif 'Manufacturer: Microsoft' in output and 'Virtual Machine' in output:
            grains['virtual'] = 'VirtualPC'
    # Fall back to lspci if dmidecode isn't available
    elif lspci:
        model = __salt__['cmd.run']('lspci').lower()
        if 'vmware' in model:
            grains['virtual'] = 'VMware'
        # 00:04.0 System peripheral: InnoTek Systemberatung GmbH VirtualBox Guest Service
        elif 'virtualbox' in model:
            grains['virtual'] = 'VirtualBox'
        elif 'qemu' in model:
            grains['virtual'] = 'kvm'
    choices =  ('Linux', 'OpenBSD', 'SunOS', 'HP-UX')
    isdir = os.path.isdir
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
                elif os.path.isfile('/proc/xen/capabilities'):
                    caps = open('/proc/xen/capabilities')
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
        elif isdir('/.SUNWnative'):
            grains['virtual'] = 'zone'
        elif os.path.isfile('/proc/cpuinfo'):
            if 'QEMU Virtual CPU' in open('/proc/cpuinfo', 'r').read():
                grains['virtual'] = 'kvm'
    elif osdata['kernel'] == 'FreeBSD':
        sysctl = salt.utils.which('sysctl')
        if sysctl:
            model = __salt__['cmd.run']('{0} hw.model'.format(sysctl)).strip()
        if 'QEMU Virtual CPU' in model:
            grains['virtual'] = 'kvm'
    return grains


def _ps(osdata):
    '''
    Return the ps grain
    '''
    grains = {}
    bsd_choices = ('FreeBSD', 'NetBSD', 'OpenBSD', 'Darwin')
    if osdata['os'] in bsd_choices:
        grains['ps'] = 'ps auxwww'
    else:
        grains['ps'] = 'ps -efH'
    return grains


def _linux_platform_data(osdata):
    '''
    The platform module is very smart about figuring out linux distro
    information. Instead of re-inventing the wheel, lets use it!
    '''
    # Provides:
    #    osrelease
    #    oscodename
    grains = {}
    (osname, osrelease, oscodename) = platform.dist()
    if 'os' not in osdata and osname:
        grains['os'] = osname
    if osrelease:
        grains['osrelease'] = osrelease
    if oscodename:
        grains['oscodename'] = oscodename
    return grains

def _windows_platform_data(osdata):
    '''
    Use the platform module for as much as we can.
    '''
    # Provides:
    #    osrelease
    #    osversion
    #    osmanufacturer
    #    manufacturer
    #    productname
    #    biosversion
    #    osfullname
    #    inputlocale
    #    timezone
    #    windowsdomain
        
    grains = {}
    (osname, hostname, osrelease, osversion, machine, processor) = platform.uname()
    if 'os' not in osdata and osname:
        grains['os'] = osname
    if osrelease:
        grains['osrelease'] = osrelease
    if osversion:
        grains['osversion'] = osversion
    get_these_grains = {
        'OS Manufacturer': 'osmanufacturer',
        'System Manufacturer': 'manufacturer', 
        'System Model': 'productname',
        'BIOS Version': 'biosversion',
        'OS Name': 'osfullname',
        'Input Locale': 'inputlocale',
        'Time Zone': 'timezone',
        'Domain': 'windowsdomain',
        }
    systeminfo = __salt__['cmd.run']('SYSTEMINFO')
    for line in  systeminfo.split('\n'):
        comps = line.split(':', 1)
        if not len(comps) > 1:
            continue
        item = comps[0].strip()
        value = comps[1].strip()
        if item in get_these_grains:
            grains[get_these_grains[item]] = value
    return grains

def os_data():
    '''
    Return grains pertaining to the operating system
    '''
    grains = {}
    if 'os' in os.environ:
        if os.environ['os'].startswith('Windows'):
            grains['os'] = 'Windows'
            grains['kernel'] = 'Windows'
            grains.update(_memdata(grains))
            grains.update(_windows_platform_data(grains))
            grains.update(_windows_cpudata())
            return grains
    grains.update(_kernel())

    if grains['kernel'] == 'Linux':
        # Add lsb grains on any distro with lsb-release
        if os.path.isfile('/etc/lsb-release'):
            for line in open('/etc/lsb-release').readlines():
                # Matches any possible format:
                #     DISTRIB_ID="Ubuntu"
                #     DISTRIB_ID='Mageia'
                #     DISTRIB_ID=Fedora
                #     DISTRIB_RELEASE='10.10'
                #     DISTRIB_CODENAME='squeeze'
                #     DISTRIB_DESCRIPTION='Ubuntu 10.10'
                regex = re.compile('^(DISTRIB_(?:ID|RELEASE|CODENAME|DESCRIPTION))=(?:\'|")?([\w\s\.-_]+)(?:\'|")?')
                match = regex.match(line)
                if match:
                    # Adds: lsb_distrib_{id,release,codename,description}
                    grains['lsb_{0}'.format(match.groups()[0].lower())] = match.groups()[1].rstrip()
        if os.path.isfile('/etc/arch-release'):
            grains['os'] = 'Arch'
        elif os.path.isfile('/etc/debian_version'):
            grains['os'] = 'Debian'
            if 'lsb_distrib_id' in grains:
                if 'Ubuntu' in grains['lsb_distrib_id']:
                    grains['os'] = 'Ubuntu'
                elif os.path.isfile('/etc/issue.net') and \
                  'Ubuntu' in open('/etc/issue.net').readline():
                    grains['os'] = 'Ubuntu'
        elif os.path.isfile('/etc/gentoo-release'):
            grains['os'] = 'Gentoo'
        elif os.path.isfile('/etc/fedora-release'):
            grains['os'] = 'Fedora'
        elif os.path.isfile('/etc/mandriva-version'):
            grains['os'] = 'Mandriva'
        elif os.path.isfile('/etc/mandrake-version'):
            grains['os'] = 'Mandrake'
        elif os.path.isfile('/etc/mageia-version'):
            grains['os'] = 'Mageia'
        elif os.path.isfile('/etc/meego-version'):
            grains['os'] = 'MeeGo'
        elif os.path.isfile('/etc/vmware-version'):
            grains['os'] = 'VMWareESX'
        elif os.path.isfile('/etc/bluewhite64-version'):
            grains['os'] = 'Bluewhite64'
        elif os.path.isfile('/etc/slamd64-version'):
            grains['os'] = 'Slamd64'
        elif os.path.isfile('/etc/slackware-version'):
            grains['os'] = 'Slackware'
        elif os.path.isfile('/etc/enterprise-release'):
            if os.path.isfile('/etc/ovs-release'):
                grains['os'] = 'OVS'
            else:
                grains['os'] = 'OEL'
        elif os.path.isfile('/etc/redhat-release'):
            data = open('/etc/redhat-release', 'r').read()
            if 'centos' in data.lower():
                grains['os'] = 'CentOS'
            elif 'scientific' in data.lower():
                grains['os'] = 'Scientific'
            else:
                grains['os'] = 'RedHat'
        elif os.path.isfile('/etc/SuSE-release'):
            data = open('/etc/SuSE-release', 'r').read()
            if 'SUSE LINUX Enterprise Server' in data:
                grains['os'] = 'SLES'
            elif 'SUSE LINUX Enterprise Desktop' in data:
                grains['os'] = 'SLED'
            elif 'openSUSE' in data:
                grains['os'] = 'openSUSE'
            else:
                grains['os'] = 'SUSE'
        # Use the already intelligent platform module to get distro info
        grains.update(_linux_platform_data(grains))
        # If the Linux version can not be determined
        if not 'os' in grains:
            grains['os'] = 'Unknown {0}'.format(grains['kernel'])
    elif grains['kernel'] == 'sunos':
        grains['os'] = 'Solaris'
    elif grains['kernel'] == 'VMkernel':
        grains['os'] = 'ESXi'
    elif grains['kernel'] == 'Darwin':
        grains['os'] = 'MacOS'
    else:
        grains['os'] = grains['kernel']
    if grains['kernel'] == 'Linux':
        grains.update(_linux_cpudata())
    elif grains['kernel'] in ('FreeBSD', 'OpenBSD'):
        # _freebsd_cpudata works on OpenBSD as well.
        grains.update(_freebsd_cpudata())

    grains.update(_memdata(grains))

    # Get the hardware and bios data
    grains.update(_hw_data(grains))

    # Load the virtual machine info
    grains.update(_virtual(grains))
    grains.update(_ps(grains))

    return grains


def hostname():
    '''
    Return fqdn, hostname, domainname
    '''
    # This is going to need some work
    # Provides:
    #   fqdn
    #   host
    #   domain
    grains = {}
    grains['fqdn'] = socket.getfqdn()
    comps = grains['fqdn'].split('.')
    grains['host'] = comps[0]
    if len(comps) > 1:
        grains['domain'] = '.'.join(comps[1:])
    else:
        grains['domain'] = ''
    return grains


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
    path = os.path.abspath(os.path.join(__file__, os.path.pardir))
    return {'saltpath': os.path.dirname(path)}


# Relatively complex mini-algorithm to iterate over the various
# sections of dmidecode output and return matches for  specific
# lines containing data we want, but only in the right section.
def _dmidecode_data(regex_dict):
    '''
    Parse the output of dmidecode in a generic fashion that can
    be used for the multiple system types which have dmidecode.
    '''
    # NOTE: This function might gain support for smbios instead
    #       of dmidecode when salt gets working Solaris support
    ret = {}

    # No use running if dmidecode isn't in the path
    if not salt.utils.which('dmidecode'):
        return ret

    out = __salt__['cmd.run']('dmidecode')

    for section in regex_dict:
        section_found = False

        # Look at every line for the right section
        for line in out.split('\n'):
            if not line: continue
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
                regex = re.compile('\s+{0}\s+(.*)$'.format(item))
                grain = regex_dict[section][item]
                # Skip to the next iteration if this grain
                # has been found in the dmidecode output.
                if grain in ret: continue

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
    return grains
