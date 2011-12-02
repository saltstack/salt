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
import subprocess
import sys
import re
import platform


def _kernel():
    '''
    Return the kernel type
    '''
    # Provides:
    # kernel
    grains = {}
    grains['kernel'] = subprocess.Popen(['uname', '-s'],
        stdout=subprocess.PIPE).communicate()[0].strip()
    if grains['kernel'] == 'aix':
        grains['kernelrelease'] = subprocess.Popen(['oslevel', '-s'],
            stdout=subprocess.PIPE).communicate()[0].strip()
    else:
        grains['kernelrelease'] = subprocess.Popen(['uname', '-r'],
            stdout=subprocess.PIPE).communicate()[0].strip()
    if 'kernel' not in grains:
        grains['kernel'] = 'Unknown'
    if not grains['kernel']:
        grains['kernel'] = 'Unknown'
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
    arch = subprocess.Popen(['uname', '-m'],
            stdout=subprocess.PIPE).communicate()[0].strip()
    grains['cpuarch'] = arch
    if not grains['cpuarch']:
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
    grains['cpuarch'] = subprocess.Popen(
            '/sbin/sysctl -n hw.machine',
            shell=True,
            stdout=subprocess.PIPE
            ).communicate()[0].strip()
    grains['num_cpus'] = subprocess.Popen(
            '/sbin/sysctl -n hw.ncpu',
            shell=True,
            stdout=subprocess.PIPE
            ).communicate()[0].strip()
    grains['cpu_model'] = subprocess.Popen(
            '/sbin/sysctl -n hw.model',
            shell=True,
            stdout=subprocess.PIPE
            ).communicate()[0].strip()
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
    
        mem = subprocess.Popen(
                '/sbin/sysctl -n hw.physmem',
                shell=True,
                stdout=subprocess.PIPE
                ).communicate()[0].strip()
        
        grains['mem_total'] = str(int(mem) / 1024 / 1024)
    
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
    choices =  ['Linux', 'OpenBSD', 'SunOS', 'HP-UX']
    isdir = os.path.isdir
    if osdata['kernel'] in choices:
        if isdir('/proc/vz'):
            if os.path.isfile('/proc/vz/version'):
                grains['virtual'] = 'openvzhn'
            else:
                grains['virtual'] = 'openvzve'
        elif isdir("/proc/sys/xen") or isdir("/sys/bus/xen") or isdir("/proc/xen"):
            grains['virtual'] = 'xen'
            if os.path.isfile('/proc/xen/xsd_kva'):
                grains['virtual_subtype'] = 'Xen Dom0'
            else:
                if os.path.isfile('/proc/xen/capabilities'):
                    grains['virtual_subtype'] = 'Xen full virt DomU'
                else:
                    grains['virtual_subtype'] = 'Xen paravirt DomU'
        elif isdir('/.SUNWnative'):
            grains['virtual'] = 'zone'
        elif os.path.isfile('/proc/cpuinfo'):
            if 'QEMU Virtual CPU' in open('/proc/cpuinfo', 'r').read():
                grains['virtual'] = 'kvm'
    elif osdata['kernel'] == 'FreeBSD':
        model = subprocess.Popen(
                '/sbin/sysctl hw.model',
                shell=True,
                stdout=subprocess.PIPE
                ).communicate()[0].split(':')[1].strip()
        if 'QEMU Virtual CPU' in model:
            grains['virtual'] = 'kvm'
    return grains


def _ps(osdata):
    '''
    Return the ps grain
    '''
    grains = {}
    grains['ps'] = 'ps auxwww' if \
            'FreeBSD NetBSD OpenBSD Darwin'.count(osdata['os']) else 'ps -efH'
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


def os_data():
    '''
    Return grains pertaining to the operating system
    '''
    grains = {}
    grains.update(_kernel())
    
    if grains['kernel'] == 'Linux':
        # Add lsb grains on any distro with lsb-release
        if os.path.isfile('/etc/lsb-release'):
    
            for line in open('/etc/lsb-release').readlines():
                # Matches any possible format:
                #     DISTRIB_ID=Ubuntu
                #     DISTRIB_ID="Mageia"
                #     DISTRIB_ID='Fedora'
                #     DISTRIB_RELEASE=10.10
                #     DISTRIB_CODENAME=squeeze
                #     DISTRIB_DESCRIPTION="Ubuntu 10.10"
                regex = re.compile('^(DISTRIB_(?:ID|RELEASE|CODENAME|DESCRIPTION))=(?:\'|")?([\w\s\.-_]+)(?:\'|")?')
                match = regex.match(line)
                
                if match:
                    # Adds: lsb_distrib_{id,release,codename,description}
                    grains['lsb_{0}'.format(match.groups()[0].lower())] = match.groups()[1].rstrip()
        
        if os.path.isfile('/etc/arch-release'):
            grains['os'] = 'Arch'
        
        elif os.path.isfile('/etc/debian_version'):
            grains['os'] = 'Debian'
        
            if "lsb_distrib_id" in grains:
            
                if "Ubuntu" in grains['lsb_distrib_id']:
                    grains['os'] = 'Ubuntu'
                
                elif os.path.isfile("/etc/issue.net") and \
                  "Ubuntu" in open("/etc/issue.net").readline():
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
