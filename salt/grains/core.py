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
    if not grains.has_key('kernel'):
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
    if not grains.has_key('num_cpus'):
        grains['num_cpus'] = 0
    if not grains.has_key('cpu_model'):
        grains['cpu_model'] = 'Unknown'
    if not grains.has_key('cpu_flags'):
        grains['cpu_flags'] = []
    return grains

def _freebsd_cpudata():
    '''
    Return cpu information for FreeBSD systems
    '''
    grains = {}
    grains['cpuarch'] = subprocess.Popen(
            '/sbin/sysctl hw.machine',
            shell=True,
            stdout=subprocess.PIPE
            ).communicate()[0].split(':')[1].strip()
    grains['num_cpus'] = subprocess.Popen(
            '/sbin/sysctl hw.ncpu',
            shell=True,
            stdout=subprocess.PIPE
            ).communicate()[0].split(':')[1].strip()
    grains['cpu_model'] = subprocess.Popen(
            '/sbin/sysctl hw.model',
            shell=True,
            stdout=subprocess.PIPE
            ).communicate()[0].split(':')[1].strip()
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
                    grains['mem_total'] = int(comps[1].split()[0])/1024
    elif osdata['kernel'] == 'FreeBSD':
        mem = subprocess.Popen(
                '/sbin/sysctl hw.physmem',
                shell=True,
                stdout=subprocess.PIPE
                ).communicate()[0].split(':')[1].strip()
        grains['mem_total'] = str(int(mem)/1024/1024)
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
    if 'Linux OpenBSD SunOS HP-UX'.count(osdata['kernel']):
        if os.path.isdir('/proc/vz'):
            if os.path.isfile('/proc/vz/version'):
                grains['virtual'] = 'openvzhn'
            else:
                grains['virtual'] = 'openvzve'
        if os.path.isdir('/.SUNWnative'):
            grains['virtual'] = 'zone'
        if os.path.isfile('/proc/cpuinfo'):
            if open('/proc/cpuinfo', 'r').read().count('QEMU Virtual CPU'):
                grains['virtual'] = 'kvm'
    elif osdata['kernel'] == 'FreeBSD':
        model = subprocess.Popen(
                '/sbin/sysctl hw.model',
                shell=True,
                stdout=subprocess.PIPE
                ).communicate()[0].split(':')[1].strip()
        if model.count('QEMU Virtual CPU'):
            grains['virtual'] = 'kvm'
    return grains

def _ps(osdata):
    '''
    Return the ps grain
    '''
    grains = {}
    grains['ps'] = 'ps auxwww' if\
            'FreeBSD NetBSD OpenBSD Darwin'.count(osdata['os']) else 'ps -ef'
    return grains

def os_data():
    '''
    Return grains pertaining to the operating system
    '''
    grains = {}
    grains.update(_kernel())
    if grains['kernel'] == 'Linux':
        if os.path.isfile('/etc/arch-release'):
            grains['os'] = 'Arch'
        elif os.path.isfile('/etc/debian_version'):
            grains['os'] = 'Debian'
        elif os.path.isfile('/etc/gentoo-version'):
            grains['os'] = 'Gentoo'
        elif os.path.isfile('/etc/fedora-version'):
            grains['os'] = 'Fedora'
        elif os.path.isfile('/etc/mandriva-version'):
            grains['os'] =  'Mandriva'
        elif os.path.isfile('/etc/mandrake-version'):
            grains['os'] = 'Mandrake'
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
            if data.count('centos'):
                grains['os'] = 'CentOS'
            elif data.count('scientific'):
                grains['os'] = 'Scientific'
            else:
                grains['os'] = 'RedHat'
        elif os.path.isfile('/etc/SuSE-release'):
            data = open('/etc/SuSE-release', 'r').read()
            if data.count('SUSE LINUX Enterprise Server'):
                grains['os'] = 'SLES'
            elif data.count('SUSE LINUX Enterprise Desktop'):
                grains['os'] = 'SLED'
            elif data.count('openSUSE'):
                grains['os'] = 'openSUSE'
            else:
                grains['os'] = 'SUSE'
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
    elif grains['kernel'] == 'FreeBSD':
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


