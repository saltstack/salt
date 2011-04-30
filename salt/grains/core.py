'''
The static grains, these are the core, or built in grains.

When grains are loaded they are not loaded in the same way that modules are
loaded, grain functions are detected and executed, the functions MUST
return a dict which will be applied to the main grains dict. This module
will always be executed first, so that any grains loaded here in the core
module can be overwritten just by returning dict keys with the same value
as those returned here
'''
# Import python modules
import os
import subprocess

def _kernel():
    '''
    Return the kernel type
    '''
    grains = {}
    grains['kernel'] = subprocess.Popen(['uname', '-s'],
        stdout=subprocess.PIPE).communicate()[0].strip()
    if grains['kernel'] == 'aix':
        grains['kernelrelease'] = subprocess.Popen(['oslevel', '-s'],
            stdout=subprocess.PIPE).communicate()[0].strip()
    else:
        grains['kernelrelease'] = subprocess.Popen(['uname', '-r'],
            stdout=subprocess.PIPE).communicate()[0].strip()
    return grains

def _cpuarch():
    '''
    Return the cpu architecture
    '''
    arch = subprocess.Popen(['uname', '-m'],
        stdout=subprocess.PIPE).communicate()[0].strip()
    return {'cpuarch': arch}

def _virtual(os_data):
    '''
    Returns what type of virtual hardware is under the hood, kvm or physical
    '''
    # This is going to be a monster, if you are running a vm you can test this
    # grain with please submit patches!
    grains = {'virtual': 'physical'}
    if 'Linux FreeBSD OpenBSD SunOS HP-UX GNU/kFreeBSD'.count(os_data['kernel']):
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
    return grains

def os_data():
    '''
    Return grins pertaining to the operating system
    '''
    grains = {}
    grains.update(_kernel())
    grains.update(_cpuarch())
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
    else:
        grains['os'] = kernel

    # Load the virtual machine info
    
    grains.update(_virtual(grains))
    return grains

def hostname():
    '''
    Return fqdn, hostname, domainname
    '''
    # This is going to need some work
    host = subprocess.Popen(['hostname'],
        stdout=subprocess.PIPE).communicate()[0].strip()
    domain = subprocess.Popen(['dnsdomainname'],
        stdout=subprocess.PIPE).communicate()[0].strip()
    grains =  {'host': host}
    if domain:
        grains['domain'] = domain
        grains['fqdn'] = host + '.' + domain
    return grains

def path():
    '''
    Return the path
    '''
    return {'path': os.environ['PATH'].strip()}


