'''
Work with vitual machines managed by libvirt
'''
# Special Thanks to Michael Dehann, many of the concepts, and a few structures
# of his in the virt func module have been used


# Import Python Libs
import os
import StringIO
from xml.dom import minidom
import subprocess
import shutil

# Import libvirt
import libvirt

# Import Third Party Libs
import yaml

VIRT_STATE_NAME_MAP = {
   0 : "running",
   1 : "running",
   2 : "running",
   3 : "paused",
   4 : "shutdown",
   5 : "shutdown",
   6 : "crashed"
}

def __get_conn():
    '''
    Detects what type of dom this node is and attempts to connect to the
    correct hypervisor via libvirt.
    '''
    # This only supports kvm right now, it needs to be expanded to support
    # all vm layers supported by libvirt
    return libvirt.open("qemu:///system")

def _get_dom(vm_):
    '''
    Return a domain object for the named vm 
    '''
    conn = __get_conn()
    if not list_vms().count(vm_):
        raise Exception('The specified vm is not present')
    return conn.lookupByName(vm_)

def _libvirt_creds():
    '''
    Returns the user and group that the disk images should be owned by
    '''
    g_cmd = 'grep group /etc/libvirt/qemu.conf'
    u_cmd = 'grep user /etc/libvirt/qemu.conf'
    group = subprocess.Popen(g_cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('"')[1]
    user = subprocess.Popen(u_cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('"')[1]
    return {'user': user, 'group': group}

def list_vms():
    '''
    Return a list of virtual machine names on the minion
    
    CLI Example:
    salt '*' virt.list_vms
    '''
    conn = __get_conn()
    vms = []
    for id_ in conn.listDomainsID():
        vms.append(conn.lookupByID(id_).name())
    return vms

def vm_info():
    '''
    Return detailed information about the vms on this hyper in a dict:

    {'cpu': <int>,
     'maxMem': <int>,
     'mem': <int>,
     'state': '<state>',
     'cputime' <int>}

    CLI Example:
    salt '*' virt.vm_info
    '''
    info = {}
    for vm_ in list_vms():
        dom = _get_dom(vm_)
        raw = dom.info()
        info[vm_] = {
                'state': VIRT_STATE_NAME_MAP.get(raw[0], 'unknown'),
                'maxMem': int(raw[1]),
                'mem': int(raw[2]),
                'cpu': raw[3],
                'cputime': int(raw[4]),
                'graphics': get_graphics(vm_),
                'disks': get_disks(vm_),
                }
    return info

def node_info():
    '''
    Return a dict with information about this node

    CLI Example:
    salt '*' virt.node_info
    '''
    conn = __get_conn()
    info = {}
    raw = conn.getInfo()
    info = {
            'cpumodel'     : str(raw[0]),
            'phymemory'    : raw[1],
            'cpus'         : raw[2],
            'cpumhz'       : raw[3],
            'numanodes'    : raw[4],
            'sockets'      : raw[5],
            'cpucores'     : raw[6],
            'cputhreads'   : raw[7]
            }
    return info

def get_graphics(vm_):
    '''
    Returns the information on vnc for a given vm
    '''
    out = {'autoport': 'None',
           'keymap': 'None',
           'type': 'vnc',
           'port': 'None',
           'listen': 'None'}
    xml = get_xml(vm_)
    ssock = StringIO.StringIO(xml)
    doc = minidom.parse(ssock)
    for node in doc.getElementsByTagName("domain"):
        g_nodes = node.getElementsByTagName("graphics")
        for g_node in g_nodes:
            for key in g_node.attributes.keys():
                out[key] = g_node.getAttribute(key)
    return out

def get_disks(vm_):
    '''
    Return the disks of a named vm
    '''
    disks = {}
    doc = minidom.parse(StringIO.StringIO(get_xml(vm_)))
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
        if target.attributes.keys().count('dev')\
                and source.attributes.keys().count('file'):
            disks[target.getAttribute('dev')] =\
                    {'file': source.getAttribute('file')}
    for dev in disks:
        disks[dev].update(yaml.load(subprocess.Popen('qemu-img info arch',
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]))
    return disks

def freemem():
    '''
    Return an int representing the amount of memory that has not been given
    to virtual machines on this node

    CLI Example:
    salt '*' virt.freemem
    '''
    conn = __get_conn()
    mem = conn.getInfo()[1]
    # Take off just enough to sustain the hypervisor
    mem -= 256
    for vm_ in list_vms():
        dom = _get_dom(vm_)
        if dom.ID() > 0:
            mem -= dom.info()[2]/1024
    return mem

def freecpu():
    '''
    Return an int representing the number of unallocated cpus on this
    hypervisor

    CLI Example:
    salt '*' virt.freemem
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

    CLI Example:
    salt '*' virt.full_info
    '''
    return {'freemem': freemem(),
            'node_info': node_info(),
            'vm_info': vm_info(),
            'freecpu': freecpu()}

def get_xml(vm_):
    '''
    Returns the xml for a given vm
    '''
    dom = _get_dom(vm_)
    return dom.XMLDesc(0)

def shutdown(vm_):
    '''
    Send a soft shutdown signal to the named vm

    CLI Example:
    salt '*' virt.shutdown <vm name>
    '''
    dom = _get_dom(vm_)
    dom.shutdown()
    return True

def pause(vm_):
    '''
    Pause the named vm

    CLI Example:
    salt '*' virt.pause <vm name>
    '''
    dom = _get_dom(vm_)
    dom.suspend()
    return True

def resume(vm_):
    '''
    Resume the named vm

    CLI Example:
    salt '*' virt.resume <vm name>
    '''
    dom = _get_dom(vm_)
    dom.resume()
    return True

def create(vm_):
    '''
    Start a defined domain

    CLI Example:
    salt '*' virt.create <vm name>
    '''
    dom = _get_dom(vm_)
    dom.create()
    return True

def create_xml_str(xml):
    '''
    Start a domain based on the xml passed to the function

    CLI Example:
    salt '*' virt.create_xml_str <xml in string format>
    '''
    conn = __get_conn()
    conn.createXML(xml, 0)
    return True

def create_xml_path(path):
    '''
    Start a defined domain

    CLI Example:
    salt '*' virt.create_xml_path <path to xml file on the node>
    '''
    if not os.path.isfile(path):
        return False
    return create_xml_str(open(path, 'r').read())

def migrate_non_shared(vm_, target):
    '''
    Attempt to execute non-shared storage "all" migration
    '''
    dom = _get_dom(vm_)
    try:
        dconn = libvirt.open('qemu://' + target  + '/system')
    except:
        return 'Failed to connect to the destination server'
    return dom.migrate(dconn, 
        libvirt.VIR_MIGRATE_LIVE | libvirt.VIR_MIGRATE_NON_SHARED_DISK)

def migrate_non_shared_inc(vm_, target):
    '''
    Attempt to execute non-shared storage "all" migration
    '''
    dom = _get_dom(vm_)
    try:
        dconn = libvirt.open('qemu://' + target  + '/system')
    except:
        return 'Failed to connect to the destination server'
    return dom.migrate(dconn, 
        libvirt.VIR_MIGRATE_LIVE | libvirt.VIR_MIGRATE_NON_SHARED_INC)

def migrate(vm_, target):
    '''
    Shared storage migration
    '''
    dom = _get_dom(vm_)
    try:
        dconn = libvirt.open('qemu://' + target  + '/system')
    except:
        return 'Failed to connect to the destination server'
    return dom.migrate(dconn, 
        libvirt.VIR_MIGRATE_LIVE)

def seed_non_shared_migrate(disks, force=False):
    '''
    Non shared migration reqiuires that the disks be present on the migration
    destination, pass the disks information via this function, to the
    migration destination before executing the migration.
    '''
    {'file': path}
    for dev, data in disks:
        fn_ = data['file']
        form = data['file format']
        size = data['virtual size'].split()[1][1:]
        if os.path.isfile(fn_) and not force:
            # the target exists, check to see if is is compatable
            pre = yaml.load(subprocess.Popen('qemu-img info arch',
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

def destroy(vm_):
    '''
    Hard power down the virtual machine, this is equivelent to pulling the
    power

    CLI Example:
    salt '*' virt.destroy <vm name>
    '''
    try:
        dom = _get_dom(vm_)
        dom.destroy()
    except:
        return False
    return True

def undefine(vm_):
    '''
    Remove a defined vm, this does not purge the virtual machine image, and
    this only works if the vm is powered down

    CLI Example:
    salt '*' virt.undefine <vm name>
    '''
    try:
        dom = _get_dom(vm_)
        dom.undefine()
    except:
        return False
    return True

def purge(vm_, dirs=False):
    '''
    Recursively destroy and delete a virtual machine, pass True for dirs to
    also delete the directories containing the virtual machine disk images -
    USE WITH EXTREAME CAUTION!
    '''
    disks = get_disks(vm_)
    destroy(vm_)
    directories = set()
    for disk in disks:
        os.remove(disks[disk])
        directories.add(os.path.dirname(disks[disk]))
    if dirs:
        for dir_ in directories:
            shutil.rmtree(dir_)
    return True

def virt_type():
    '''
    Returns the virtual machine type as a string
    
    CLI Example:
    salt '*' virt.virt_type
    '''
    return __facter__['virtual']

def is_kvm_hyper():
    '''
    Returns a bool whether or not this node is a hypervisor
    '''
    if __facter__['virtual'] != 'physical':
        return False
    if not open('/proc/modules').read().count('kvm_'):
        return False
    libvirt_ret = subprocess.Popen('ps aux',
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].count('libvirtd')
    if not libvirt_ret:
        return False
    return True
