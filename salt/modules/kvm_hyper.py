'''
Provide the hyper module for kvm hypervisors. This is the interface used to
interact with kvm on behalf of the salt-virt interface

Required python modules: libvirt
'''

# This is a test interface for the salt-virt system. The api in this file is
# VERY likely to change.


# Import Python Libs
import os
import shutil
import string
import subprocess
from xml.dom import minidom

# Import libvirt
try:
    import libvirt
    has_libvirt = True
except ImportError:
    has_libvirt = False

# Import Third party modules
import yaml

# Import Salt Modules
import salt.utils
from salt._compat import StringIO

VIRT_STATE_NAME_MAP = {0: "running",
                       1: "running",
                       2: "running",
                       3: "paused",
                       4: "shutdown",
                       5: "shutdown",
                       6: "crashed"}


def __virtual__():
    '''
    Apply this module as the hyper module if the minion is a kvm hypervisor
    '''
    if 'virtual' not in __grains__:
        return False
    if __grains__['virtual'] != 'physical':
        return False
    if __grains__['kernel'] != 'Linux':
        return False
    if not os.path.exists('/proc/modules'):
        return False
    if 'kvm_' not in open('/proc/modules').read():
        return False
    if not has_libvirt:
        return False
    try:
        libvirt_conn = libvirt.open('qemu:///system')
        libvirt_conn.close()
        return 'hyper'
    except Exception:
        return False


def __get_conn():
    '''
    Connects to the libvirt daemon for qemu/kvm
    '''
    return libvirt.open("qemu:///system")


def _get_dom(vm_):
    '''
    Return a domain object for the named vm
    '''
    conn = __get_conn()
    if vm_ not in list_virts():
        raise Exception('The specified vm is not present')
    return conn.lookupByName(vm_)

# Define tier 1 Virt functions, all hyper interfaces have these:
# hyper_type
# list_virts
# hyper_info
# get_conf


def hyper_type():
    '''
    Return that type of hypervisor this is

    CLI Example::

        salt '*' hyper.hyper_type
    '''
    return 'kvm'


def freemem():
    '''
    Return an int representing the amount of memory that has not been given
    to virtual machines on this node

    CLI Example::

        salt '*' hyper.freemem
    '''
    conn = __get_conn()
    mem = conn.getInfo()[1]
    # Take off just enough to sustain the hypervisor
    mem -= 256
    for vm_ in list_virts():
        dom = _get_dom(vm_)
        if dom.ID() > 0:
            mem -= dom.info()[2] / 1024
    return mem


def freecpu():
    '''
    Return an int representing the number of unallocated cpus on this
    hypervisor

    CLI Example::

        salt '*' hyper.freecpu
    '''
    conn = __get_conn()
    cpus = conn.getInfo()[2]
    for vm_ in list_virts():
        dom = _get_dom(vm_)
        if dom.ID() > 0:
            cpus -= dom.info()[3]
    return cpus


def list_virts():
    '''
    Return a list of virtual machine names on the minion

    CLI Example::

        salt '*' hyper.list_virts
    '''
    # Expand to include down vms
    conn = __get_conn()
    vms = []
    for id_ in conn.listDomainsID():
        vms.append(conn.lookupByID(id_).name())
    return vms


def virt_info():
    '''
    Return detailed information about the vms on this hyper in a dict::

        {'cpu': <int>,
        'maxMem': <int>,
        'mem': <int>,
        'state': '<state>',
        'cputime' <int>}

    CLI Example::

        salt '*' hyper.virt_info
    '''
    info = {}
    for vm_ in list_virts():
        dom = _get_dom(vm_)
        raw = dom.info()
        info[vm_] = {
                     'state': VIRT_STATE_NAME_MAP.get(raw[0], 'unknown'),
                     'maxMem': int(raw[1]),
                     'mem': int(raw[2]),
                     'cpu': raw[3],
                     'cputime': int(raw[4]),
                     'disks': get_disks(vm_),
                     }
    return info


def hyper_info():
    '''
    Return a dict with information about this hypervisor

    CLI Example::

        salt '*' hyper.hyper_info
    '''
    conn = __get_conn()
    raw = conn.getInfo()
    info = {
            'phymemory': raw[1],
            'cpus': raw[2],
            'cpumhz': raw[3],
            'cpucores': raw[6],
            'cputhreads': raw[7],
            'type': hyper_type(),
            'freecpu': freecpu(),
            'freemem': freemem(),
            'virt_info': virt_info(),
            }
    return info

# Level 2 - vm class specific
# init - Create a vm from options
# start - Start a down vm
# halt
# purge
# pause
# resume
# set_autostart
# get_disks
# get_conf

def _get_image(image, vda):
    '''
    Copy the image into place
    '''
    if ':' in image:
        if not os.path.isabs(image) or not image.startswith('file://'):
            # The image is on a network resource
            env = 'base'
            if not image.rindex(':') == 4:
                env = image.split(':')[-1]
                image = image[:image.rindex(':')]
            __salt__['cp.get_url'](image, vda, env)
    if os.path.isabs(image) or image.startswith('file://'):
        # This is a local file, copy it into place
        if image.startswith('file://'):
            # Condition this into a standard path
            for ind in range(6, len(image)):
                if image[ind].isalpha():
                    image = os.path.join('/', image[ind:])
                    break
        shutil.copy2(image, vda)


def _gen_xml(name,
        cpus,
        mem,
        vmdir,
        disks,
        network,
        desc,
        opts):
    '''
    Generate the xml used for the libvirt configuration
    '''
    # Don't generate the libvirt config if it already exists
    vda = os.path.join(vmdir, 'vda')
    data = '''
<domain type='kvm'>
        <name>%%NAME%%</name>
        <vcpu>%%CPU%%</vcpu>
        <memory>%%MEM%%</memory>
        <os>
                <type>hvm</type>
                <boot dev='hd'/>
        </os>
        <devices>
                <emulator>/usr/bin/kvm</emulator>
                <disk type='file' device='disk'>
                        <source file='%%VDA%%'/>
                        <target dev='vda' bus='virtio'/>
                        <driver name='qemu' cache='writeback' io='native'/>
                </disk>
                %%DISK%%
                %%NICS%%
                <graphics type='vnc' listen='0.0.0.0' autoport='yes'/>
        </devices>
        <features>
                <acpi/>
        </features>
</domain>
        '''
    data = data.replace('%%NAME%%', name)
    data = data.replace('%%CPU%%', str(cpus))
    data = data.replace('%%MEM%%', str(int(mem) * 1024))
    data = data.replace('%%VDA%%', vda)
    nics = ''
    for interface, data in network.items():
        for bridge, mac in data.items():
            if not mac:
                # Generate this interface's mac addr, use the qemu default
                # prefix, 52:54
                mac = salt.utils.gen_mac('52:54:')
            nic = '''
                <interface type='bridge'>
                        <source bridge='%%BRIDGE%%'/>
                        <mac address='%%MAC%%'/>
                        <model type='virtio'/>
                </interface>\n'''
            nic = nic.replace('%%BRIDGE%%', bridge)
            nic = nic.replace('%%MAC%%', mac)
            nics += nic
    data = data.replace('%%NICS%%', nics)

    if disks:
        letters = string.ascii_lowercase
        disk_str = ''
        for ind in range(0, len(disks)):
            disk = disks[ind]
            disk_d = '''
            <disk type='file' device='disk'>
                    <source file='%%DISK_PATH%%'/>
                    <target dev='%%VD%%' bus='virtio'/>
                    <driver name='qemu' type='%%TYPE%%' cache='writeback' io='native'/>
            </disk>
            '''

            disk_d = disk_d.replace('%%DISK_PATH%%', disk['path'])
            disk_d = disk_d.replace('%%TYPE%%', disk['format'])
            disk_d = disk_d.replace('%%VD%%', 'vd' + letters[ind + 1])

            disk_str += disk_d
        data = data.replace('%%DISK%%', disk_str)
    else:
        data = data.replace('%%DISK%%', '')
    return data


def init(
        name,
        cpus,
        mem,
        image,
        storage_dir,
        network={'eth0': {'bridge': 'br0', 'mac': ''}},
        desc='',
        opts={}):
    '''
    Create a KVM virtual machine based on these passed options, the virtual
    machine will be started upon creation

    CLI Example:

        salt '*' hyper.init webserver 2 2048 salt://fedora/f16.img:virt /srv/vm/images
    '''
    vmdir = os.path.join(storage_dir, name)
    if not os.path.exists(vmdir):
        os.makedirs(vmdir)
    vda = os.path.join(vmdir, 'vda')
    _get_image(image, vda)
    # The image is in place
    xml = _gen_xml(name, cpus, mem, vmdir, network, desc, opts)
    config = os.path.join(vmdir, 'config.xml')
    open(config, 'w+').write(xml)
    return start(config)


def start(config):
    '''
    Start an already defined virtual machine that has been shut down

    CLI Example::

        salt '*' hyper.start webserver
    '''
    # change this to use the libvirt api and add more logging and a verbose
    # return
    cmd = 'virsh create {0}'.format(config)
    return not __salt__['cmd.retcode'](cmd)

def halt(name):
    '''
    Hard power down a virtual machine

    CLI Example::

        salt '*' hyper.halt webserver
    '''
    try:
        dom = _get_dom(name)
        dom.destroy()
    except Exception:
        return False
    return True


def purge(name):
    '''
    Hard power down and purge a virtual machine, this will destroy a vm and
    all associated vm data

    CLI Example::

        salt '*' hyper.purge webserver
    '''
    disks = get_disks(name)
    halt(name)
    directories = set()
    for disk in disks:
        os.remove(disks[disk]['file'])
        directories.add(os.path.dirname(disks[disk]['file']))
    if directories:
        for dir_ in directories:
            shutil.rmtree(dir_)
    return True


def pause(name):
    '''
    Pause the named virtual machine

    CLI Example::

        salt '*' hyper.pause webserver
    '''
    dom = _get_dom(name)
    dom.suspend()
    return True


def resume(name):
    '''
    Resume the named virtual machine

    CLI Example::

        salt '*' hyper.resume webserver
    '''
    dom = _get_dom(name)
    dom.resume()
    return True


def set_autostart(name):
    '''
    Set the named virtual machine to autostart when the hypervisor boots

    CLI Example::

        salt '*' hyper.set_autostart webserver
    '''
    dom = _get_dom(name)

    if state == 'on':
        return dom.setAutostart(1) == 0

    elif state == 'off':
        return dom.setAutostart(0) == 0

    else:
        # return False if state is set to something other then on or off
        return False


def get_disks(name):
    '''
    Return the disks of a named virt

    CLI Example::

        salt '*' hyper.get_disks <vm name>
    '''
    disks = {}
    doc = minidom.parse(StringIO(get_conf(name)))
    for elem in doc.getElementsByTagName('disk'):
        sources = elem.getElementsByTagName('source')
        targets = elem.getElementsByTagName('target')
        if len(sources) > 0:
            source = sources[0]
        else:
            continue
        if len(targets) > 0:
            target = targets[0]
        else:
            continue
        if 'dev' in list(target.attributes) and 'file' in list(source.attributes):
            disks[target.getAttribute('dev')] = {'file': source.getAttribute('file')}
    for dev in disks:
        disks[dev].update(yaml.safe_load(subprocess.Popen('qemu-img info ' \
            + disks[dev]['file'],
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]))
    return disks


def get_conf(name):
    '''
    Returns the xml for a given vm

    CLI Example::

        salt '*' hyper.get_conf <vm name>
    '''
    dom = _get_dom(name)
    return dom.XMLDesc(0)
