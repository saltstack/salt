'''
The static grains, these grains only need to be executed once!

We use some "python tricks" here to make sure that the static grains are only
executed once, but are available to each other in a logical sequence. To do
this some naming semantics are im place, the grains are functions that return
values that are generated when the module is loaded.
Local grain values are preceeded with __ while functions which acctually
generate the values are preceeded with a single _ so that the loader module
ignores them. Really, the only public stuff are the functions that return the
previously generated grain values
'''
# Import python modules
import os
import subprocess


__kernel = _kernel()
kernel = lambda: __kernel

__cpuarch = _cpuarch()
cpuarch = lambda: __cpuarch

__operatingsystem = _operatingsystem()
operatingsystem = labmda: __operatingsystem

__fqdn, __host, __domain = _hostname()
fqdn = lambda: __fqdn
host = lambda: __host
domain = lambda: __domain

__path = _path()
path = lambda: __path

def _kernel():
    '''
    Return the kernel type
    '''
    return subprocess.Popen(['uname', '-s'],
        stdout=subprocess.PIPE).communicate()[0].strip()

def _cpuarch():
    '''
    Return the cpu architecture
    '''
    return subprocess.Popen(['uname', '-m'],
        stdout=subprocess.PIPE).communicate()[0].strip()

def _operatingsystem():
    '''
    Return a string defining the operating system
    '''
    if __kernel == 'Linux':
        if os.path.isfile('/etc/arch-release'):
            return 'Arch'
        elif os.path.isfile('/etc/debian_version'):
            return 'Debian'
        elif os.path.isfile('/etc/gentoo-version'):
            return 'Gentoo'
        elif os.path.isfile('/etc/fedora-version'):
            return 'Fedora'
        elif os.path.isfile('/etc/mandriva-version'):
            return 'Mandriva'
        elif os.path.isfile('/etc/mandrake-version'):
            return 'Mandrake'
        elif os.path.isfile('/etc/meego-version'):
            return 'MeeGo'
        elif os.path.isfile('/etc/vmware-version'):
            return 'VMWareESX'
        elif os.path.isfile('/etc/bluewhite64-version'):
            return 'Bluewhite64'
        elif os.path.isfile('/etc/slamd64-version'):
            return 'Slamd64'
        elif os.path.isfile('/etc/slackware-version'):
            return 'Slackware'
        elif os.path.isfile('/etc/enterprise-release'):
            if os.path.isfile('/etc/ovs-release'):
                return 'OVS'
            else:
                return 'OEL'
        elif os.path.isfile('/etc/redhat-release'):
            data = open('/etc/redhat-release', 'r').read()
            if data.count('centos'):
                return 'CentOS'
            elif data.count('scientific'):
                return 'Scientific'
            else:
                return RedHat
        elif os.path.isfile('/etc/SuSE-release'):
            data = open('/etc/SuSE-release', 'r').read()
            if data.count('SUSE LINUX Enterprise Server'):
                return 'SLES'
            elif data.count('SUSE LINUX Enterprise Desktop'):
                return 'SLED'
            elif data.count('openSUSE'):
                return 'openSUSE'
            else:
                return 'SUSE'
    elif __kernel == 'sunos':
        return 'Solaris'
    elif __kernel == 'VMkernel':
        return 'ESXi'
    else:
        return __kernel

def _hostname():
    '''
    Return a tuple, (fqdn, hostname, domainname)
    '''
    # This is going to need some work
    host = subprocess.Popen(['hostname'],
        stdout=subprocess.PIPE).communicate()[0].strip()
    domain = subprocess.Popen(['dnsdomainname'],
        stdout=subprocess.PIPE).communicate()[0].strip()
    return (host + '.' + domain, host, domain)

def _path():
    '''
    Return the path
    '''
    return os.environ['PATH'].strip()
