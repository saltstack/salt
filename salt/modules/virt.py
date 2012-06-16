'''
Work with virtual machines managed by libvirt

Required python modules: libvirt
'''
# Special Thanks to Michael Dehann, many of the concepts, and a few structures
# of his in the virt func module have been used

import os
import re
import shutil
import subprocess
from xml.dom import minidom

# Import Third Party Libs
try:
    import libvirt
    has_libvirt = True
except ImportError:
    has_libvirt = False
import yaml

from salt._compat import StringIO
from salt.exceptions import CommandExecutionError

VIRT_STATE_NAME_MAP = {0: "running",
                       1: "running",
                       2: "running",
                       3: "paused",
                       4: "shutdown",
                       5: "shutdown",
                       6: "crashed"}


def __virtual__():
    if not has_libvirt:
        return False
    return 'virt'


def __get_conn():
    '''
    Detects what type of dom this node is and attempts to connect to the
    correct hypervisor via libvirt.
    '''
    # This has only been tested on kvm and xen, it needs to be expanded to support
    # all vm layers supported by libvirt
    try:
        conn = libvirt.open("qemu:///system")
    except Exception:
        msg = 'Sorry, {0} failed to open a connection to the hypervisor software'
        raise CommandExecutionError(msg.format(__grains__['fqdn']))
    return conn


def _get_dom(vm_):
    '''
    Return a domain object for the named vm
    '''
    conn = __get_conn()
    if vm_ not in list_vms():
        raise CommandExecutionError('The specified vm is not present')
    return conn.lookupByName(vm_)


def _libvirt_creds():
    '''
    Returns the user and group that the disk images should be owned by
    '''
    g_cmd = 'grep ^\s*group /etc/libvirt/qemu.conf'
    u_cmd = 'grep ^\s*user /etc/libvirt/qemu.conf'
    try:
        group = subprocess.Popen(g_cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('"')[1]
    except IndexError:
        group = "root"
    try:
        user = subprocess.Popen(u_cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('"')[1]
    except IndexError:
        user = "root"
    return {'user': user, 'group': group}


def list_vms():
    '''
    Return a list of virtual machine names on the minion

    CLI Example::

        salt '*' virt.list_vms
    '''
    vms = []
    vms.extend(list_active_vms())
    vms.extend(list_inactive_vms())
    return vms

def list_active_vms():
    '''
    Return a list of names for active virtual machine on the minion

    CLI Example::

        salt '*' virt.list_active_vms
    '''
    conn = __get_conn()
    vms = []
    for id_ in conn.listDomainsID():
        vms.append(conn.lookupByID(id_).name())
    return vms

def list_inactive_vms():
    '''
    Return a list of names for inactive virtual machine on the minion

    CLI Example::

        salt '*' virt.list_inactive_vms
    '''
    conn = __get_conn()
    vms = []
    for id_ in conn.listDefinedDomains():
        vms.append(id_)
    return vms

def vm_info(vm_=None):
    '''
    Return detailed information about the vms on this hyper in a
    list of dicts::

        [
            'your-vm': {
                'cpu': <int>,
                'maxMem': <int>,
                'mem': <int>,
                'state': '<state>',
                'cputime' <int>
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example::

        salt '*' virt.vm_info
    '''
    def _info(vm_):
        dom = _get_dom(vm_)
        raw = dom.info()
        return {'cpu': raw[3],
                'cputime': int(raw[4]),
                'disks': get_disks(vm_),
                'graphics': get_graphics(vm_),
                'maxMem': int(raw[1]),
                'mem': int(raw[2]),
                'state': VIRT_STATE_NAME_MAP.get(raw[0], 'unknown')}
    info = {}
    if vm_:
        info[vm_] = _info(vm_)
    else:
        for vm_ in list_vms():
            info[vm_] = _info(vm_)
    return info

def vm_state(vm_):
    '''
    Return the status of the named VM.

    CLI Example::

        salt '*' virt.vm_state <vm name>
    '''
    state = ''
    dom = _get_dom(vm_)
    raw = dom.info()
    state = VIRT_STATE_NAME_MAP.get(raw[0], 'unknown')
    return state

def node_info():
    '''
    Return a dict with information about this node

    CLI Example::

        salt '*' virt.node_info
    '''
    conn = __get_conn()
    raw = conn.getInfo()
    info = {'cpucores': raw[6],
            'cpumhz': raw[3],
            'cpumodel': str(raw[0]),
            'cpus': raw[2],
            'cputhreads': raw[7],
            'numanodes': raw[4],
            'phymemory': raw[1],
            'sockets': raw[5]}
    return info

def get_nics(vm_):
    '''
    Return info about the network interfaces of a named vm

    CLI Example::

        salt '*' virt.get_nics <vm name>
    '''
    nics = {}
    doc = minidom.parse(StringIO(get_xml(vm_)))
    for node in doc.getElementsByTagName("devices"):
        i_nodes = node.getElementsByTagName("interface")
        for i_node in i_nodes:
            nic = {}
            nic['type'] = i_node.getAttribute('type')
            for v_node in i_node.getElementsByTagName('*'):
                if v_node.tagName == "mac":
                    nic['mac'] = v_node.getAttribute('address')
                if v_node.tagName == "model":
                    nic['model'] = v_node.getAttribute('type')
                # driver, source, and match can all have optional attributes
                if re.match('(driver|source|address)', v_node.tagName):
                    temp = {}
                    for key in v_node.attributes:
                        temp[key] = v_node.getAttribute(key)
                    nic[str(v_node.tagName)] = temp
                # virtualport needs to be handled separately, to pick up the
                # type attribute of the virtualport itself
                if v_node.tagName == "virtualport":
                    temp = {}
                    temp['type'] = v_node.getAttribute('type')
                    for key in v_node.attributes:
                        temp[key] = v_node.getAttribute(key)
                    nic['virtualport'] = temp
            if 'mac' not in nic:
                continue
            nics[nic['mac']] = nic
    return nics

def get_macs(vm_):
    '''
    Return a list off MAC addresses from the named vm

    CLI Example::

        salt '*' virt.get_macs <vm name>
    '''
    macs = []
    doc = minidom.parse(StringIO(get_xml(vm_)))
    for node in doc.getElementsByTagName("devices"):
        i_nodes = node.getElementsByTagName("interface")
        for i_node in i_nodes:
            for v_node in i_node.getElementsByTagName('mac'):
                macs.append(v_node.getAttribute('address'))
    return macs

def get_graphics(vm_):
    '''
    Returns the information on vnc for a given vm

    CLI Example::

        salt '*' virt.get_graphics <vm name>
    '''
    out = {'autoport': 'None',
           'keymap': 'None',
           'listen': 'None',
           'port': 'None',
           'type': 'vnc'}
    xml = get_xml(vm_)
    ssock = StringIO(xml)
    doc = minidom.parse(ssock)
    for node in doc.getElementsByTagName("domain"):
        g_nodes = node.getElementsByTagName("graphics")
        for g_node in g_nodes:
            for key in g_node.attributes:
                out[key] = g_node.getAttribute(key)
    return out


def get_disks(vm_):
    '''
    Return the disks of a named vm

    CLI Example::

        salt '*' virt.get_disks <vm name>
    '''
    disks = {}
    doc = minidom.parse(StringIO(get_xml(vm_)))
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
            disks[target.getAttribute('dev')] = {
                'file': source.getAttribute('file')}
    for dev in disks:
        try:
            disks[dev].update(yaml.safe_load(subprocess.Popen('qemu-img info '
                + disks[dev]['file'],
                shell=True,
                stdout=subprocess.PIPE).communicate()[0]))
        except TypeError:
            disks[dev].update(yaml.safe_load('image: Does not exist'))
    return disks


def freemem():
    '''
    Return an int representing the amount of memory that has not been given
    to virtual machines on this node

    CLI Example::

        salt '*' virt.freemem
    '''
    conn = __get_conn()
    mem = conn.getInfo()[1]
    # Take off just enough to sustain the hypervisor
    mem -= 256
    for vm_ in list_vms():
        dom = _get_dom(vm_)
        if dom.ID() > 0:
            mem -= dom.info()[2] / 1024
    return mem


def freecpu():
    '''
    Return an int representing the number of unallocated cpus on this
    hypervisor

    CLI Example::

        salt '*' virt.freecpu
    '''
    conn = __get_conn()
    cpus = conn.getInfo()[2]
    for vm_ in list_vms():
        dom = _get_dom(vm_)
        if dom.ID() > 0:
            cpus -= dom.info()[3]
    return cpus


def full_info():
    '''
    Return the node_info, vm_info and freemem

    CLI Example::

        salt '*' virt.full_info
    '''
    return {'freecpu': freecpu(),
            'freemem': freemem(),
            'node_info': node_info(),
            'vm_info': vm_info()}


def get_xml(vm_):
    '''
    Returns the xml for a given vm

    CLI Example::

        salt '*' virt.get_xml <vm name>
    '''
    dom = _get_dom(vm_)
    return dom.XMLDesc(0)


def shutdown(vm_):
    '''
    Send a soft shutdown signal to the named vm

    CLI Example::

        salt '*' virt.shutdown <vm name>
    '''
    dom = _get_dom(vm_)
    dom.shutdown()
    return True


def pause(vm_):
    '''
    Pause the named vm

    CLI Example::

        salt '*' virt.pause <vm name>
    '''
    dom = _get_dom(vm_)
    dom.suspend()
    return True


def resume(vm_):
    '''
    Resume the named vm

    CLI Example::

        salt '*' virt.resume <vm name>
    '''
    dom = _get_dom(vm_)
    dom.resume()
    return True


def create(vm_):
    '''
    Start a defined domain

    CLI Example::

        salt '*' virt.create <vm name>
    '''
    dom = _get_dom(vm_)
    dom.create()
    return True


def start(vm_):
    '''
    Alias for the obscurely named 'create' function

    CLI Example::

        salt '*' virt.start <vm name>
    '''
    return create(vm_)


def create_xml_str(xml):
    '''
    Start a domain based on the xml passed to the function

    CLI Example::

        salt '*' virt.create_xml_str <xml in string format>
    '''
    conn = __get_conn()
    conn.createXML(xml, 0)
    return True


def create_xml_path(path):
    '''
    Start a defined domain

    CLI Example::

        salt '*' virt.create_xml_path <path to xml file on the node>
    '''
    if not os.path.isfile(path):
        return False
    return create_xml_str(open(path, 'r').read())


def migrate_non_shared(vm_, target):
    '''
    Attempt to execute non-shared storage "all" migration

    CLI Example::

        salt '*' virt.migrate_non_shared <vm name> <target hypervisor>
    '''
    cmd = 'virsh migrate --live --copy-storage-all ' + vm_\
        + ' qemu://' + target + '/system'

    return subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]


def migrate_non_shared_inc(vm_, target):
    '''
    Attempt to execute non-shared storage "all" migration

    CLI Example::

        salt '*' virt.migrate_non_shared_inc <vm name> <target hypervisor>
    '''
    cmd = 'virsh migrate --live --copy-storage-inc ' + vm_\
        + ' qemu://' + target + '/system'

    return subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]


def migrate(vm_, target):
    '''
    Shared storage migration

    CLI Example::

        salt '*' virt.migrate <vm name> <target hypervisor>
    '''
    cmd = 'virsh migrate --live ' + vm_\
        + ' qemu://' + target + '/system'

    return subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]


def seed_non_shared_migrate(disks, force=False):
    '''
    Non shared migration requires that the disks be present on the migration
    destination, pass the disks information via this function, to the
    migration destination before executing the migration.

    CLI Example::

        salt '*' virt.seed_non_shared_migrate <disks>
    '''
    for dev, data in disks.items():
        fn_ = data['file']
        form = data['file format']
        size = data['virtual size'].split()[1][1:]
        if os.path.isfile(fn_) and not force:
            # the target exists, check to see if is is compatible
            pre = yaml.safe_load(subprocess.Popen('qemu-img info arch',
                shell=True,
                stdout=subprocess.PIPE).communicate()[0])
            if not pre['file format'] == data['file format']\
                    and not pre['virtual size'] == data['virtual size']:
                return False
        if not os.path.isdir(os.path.dirname(fn_)):
            os.makedirs(os.path.dirname(fn_))
        if os.path.isfile(fn_):
            os.remove(fn_)
        cmd = 'qemu-img create -f ' + form + ' ' + fn_ + ' ' + size
        subprocess.call(cmd, shell=True)
        creds = _libvirt_creds()
        cmd = 'chown ' + creds['user'] + ':' + creds['group'] + ' ' + fn_
        subprocess.call(cmd, shell=True)
    return True


def set_autostart(vm_, state='on'):
    '''
    Set the autostart flag on a VM so that the VM will start with the host
    system on reboot.

    CLI Example::

        salt "*" virt.set_autostart <vm name> <on | off>
    '''

    dom = _get_dom(vm_)

    if state == 'on':
        return dom.setAutostart(1) == 0

    elif state == 'off':
        return dom.setAutostart(0) == 0

    else:
        # return False if state is set to something other then on or off
        return False

def destroy(vm_):
    '''
    Hard power down the virtual machine, this is equivalent to pulling the
    power

    CLI Example::

        salt '*' virt.destroy <vm name>
    '''
    try:
        dom = _get_dom(vm_)
        dom.destroy()
    except Exception:
        return False
    return True


def undefine(vm_):
    '''
    Remove a defined vm, this does not purge the virtual machine image, and
    this only works if the vm is powered down

    CLI Example::

        salt '*' virt.undefine <vm name>
    '''
    try:
        dom = _get_dom(vm_)
        dom.undefine()
    except Exception:
        return False
    return True


def purge(vm_, dirs=False):
    '''
    Recursively destroy and delete a virtual machine, pass True for dir's to
    also delete the directories containing the virtual machine disk images -
    USE WITH EXTREME CAUTION!

    CLI Example::

        salt '*' virt.purge <vm name>
    '''
    disks = get_disks(vm_)
    destroy(vm_)
    directories = set()
    for disk in disks:
        os.remove(disks[disk]['file'])
        directories.add(os.path.dirname(disks[disk]['file']))
    if dirs:
        for dir_ in directories:
            shutil.rmtree(dir_)
    return True


def virt_type():
    '''
    Returns the virtual machine type as a string

    CLI Example::

        salt '*' virt.virt_type
    '''
    return __grains__['virtual']


def is_kvm_hyper():
    '''
    Returns a bool whether or not this node is a KVM hypervisor

    CLI Example::

        salt '*' virt.is_kvm_hyper
    '''
    if __grains__['virtual'] != 'physical':
        return False
    try:
        if 'kvm_' not in open('/proc/modules').read():
            return False
    except IOError:
            # No /proc/modules? Are we on Windows? Or Solaris?
            return False
    return 'libvirtd' in __salt__['cmd.run'](__grains__['ps'])

def is_xen_hyper():
    '''
    Returns a bool whether or not this node is a XEN hypervisor

    CLI Example::

        salt '*' virt.is_xen_hyper
    '''
    try:
        if __grains__['virtual_subtype'] != 'Xen Dom0':
            return False
    except KeyError:
            # virtual_subtype isn't set everywhere.
            return False
    try:
        if 'xen_' not in open('/proc/modules').read():
            return False
    except IOError:
            # No /proc/modules? Are we on Windows? Or Solaris?
            return False
    return 'libvirtd' in __salt__['cmd.run'](__grains__['ps'])

def is_hyper():
    '''
    Returns a bool whether or not this node is a hypervisor of any kind

    CLI Example::

        salt '*' virt.is_hyper
    '''
    return is_xen_hyper() or is_kvm_hyper()
