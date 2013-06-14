'''
Work with virtual machines managed by libvirt

:depends: libvirt Python module
'''
# Special Thanks to Michael Dehann, many of the concepts, and a few structures
# of his in the virt func module have been used

# Import python libs
import os
import re
import shutil
import subprocess
from xml.dom import minidom

# Import third party libs
try:
    import libvirt
    HAS_LIBVIRT = True
except ImportError:
    HAS_LIBVIRT = False
import yaml

# Import salt libs
import salt.utils
from salt._compat import StringIO as _StringIO
from salt.exceptions import CommandExecutionError


VIRT_STATE_NAME_MAP = {0: 'running',
                       1: 'running',
                       2: 'running',
                       3: 'paused',
                       4: 'shutdown',
                       5: 'shutdown',
                       6: 'crashed'}


def __virtual__():
    if not HAS_LIBVIRT:
        return False
    return 'virt'


def __get_conn():
    '''
    Detects what type of dom this node is and attempts to connect to the
    correct hypervisor via libvirt.
    '''
    # This has only been tested on kvm and xen, it needs to be expanded to
    # support all vm layers supported by libvirt
    try:
        conn = libvirt.open('qemu:///system')
    except Exception:
        raise CommandExecutionError(
            'Sorry, {0} failed to open a connection to the hypervisor '
            'software'.format(
                __grains__['fqdn']
            )
        )
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
    g_cmd = 'grep ^\\s*group /etc/libvirt/qemu.conf'
    u_cmd = 'grep ^\\s*user /etc/libvirt/qemu.conf'
    try:
        group = subprocess.Popen(g_cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('"')[1]
    except IndexError:
        group = 'root'
    try:
        user = subprocess.Popen(u_cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('"')[1]
    except IndexError:
        user = 'root'
    return {'user': user, 'group': group}


def _get_migrate_command():
    '''
    Returns the command shared by the different migration types
    '''
    if __salt__['config.option']('virt.tunnel'):
        return ('virsh migrate --p2p --tunnelled --live --persistent '
                '--undefinesource ')
    return 'virsh migrate --live --persistent --undefinesource '


def _get_target(target, ssh):
    proto = 'qemu'
    if ssh:
        proto += '+ssh'
    return ' %s://%s/%s' % (proto, target, 'system')


def _gen_xml(name, cpu, mem, vda, nicp, emulator, **kwargs):
    '''
    Generate the XML string to define a libvirt vm
    '''
    mem = mem * 1024
    print 'emulator: {}'.format(emulator)
    data = '''
<domain type='%%EMULATOR%%'>
        <name>%%NAME%%</name>
        <vcpu>%%CPU%%</vcpu>
        <memory>%%MEM%%</memory>
        <os>
                <type>hvm</type>
                <boot dev='hd'/>
        </os>
        <devices>
                <disk type='file' device='disk'>
                        <source file='%%VDA%%'/>
                        <target dev='vda' bus='virtio'/>
                        <driver name='qemu' type='%%DISKTYPE%%' cache='none' io='native'/>
                </disk>
                %%NICS%%
                <graphics type='vnc' listen='0.0.0.0' autoport='yes'/>
        </devices>
        <features>
                <acpi/>
        </features>
</domain>
'''
    data = data.replace('%%EMULATOR%%', emulator)
    data = data.replace('%%NAME%%', name)
    data = data.replace('%%CPU%%', str(cpu))
    data = data.replace('%%MEM%%', str(mem))
    data = data.replace('%%VDA%%', vda)
    data = data.replace('%%DISKTYPE%%', _image_type(vda))
    nic_str = ''
    for dev, args in nicp.items():
        nic_t = '''
                <interface type='%%TYPE%%'>
                    <source %%SOURCE%%/>
                    <mac address='%%MAC%%'/>
                    <model type='%%MODEL%%'/>
                </interface>
'''
        if 'bridge' in args:
            nic_t = nic_t.replace('%%SOURCE%%', 'bridge=\'{0}\''.format(args['bridge']))
            nic_t = nic_t.replace('%%TYPE%%', 'bridge')
        elif 'network' in args:
            nic_t = nic_t.replace('%%SOURCE%%', 'network=\'{0}\''.format(args['network']))
            nic_t = nic_t.replace('%%TYPE%%', 'network')
        if 'model' in args:
            nic_t = nic_t.replace('%%MODEL%%', args['model'])
        dmac = '{0}_mac'.format(dev)
        if dmac in kwargs:
            nic_t = nic_t.replace('%%MAC%%', kwargs[dmac])
        else:
            nic_t = nic_t.replace('%%MAC%%', salt.utils.gen_mac())
        nic_str += nic_t
    data = data.replace('%%NICS%%', nic_str)
    return data


def _image_type(vda):
    '''
    Detect what driver needs to be used for the given image
    '''
    out = __salt__['cmd.run']('qemu-img {0}'.format(vda))
    if 'qcow2' in out:
        return 'qcow2'
    else:
        return 'raw'


def _nic_profile(nic):
    '''
    Gather the nic profile from the config or apply the default
    '''
    default = {'eth0': {'bridge': 'br0', 'model': 'virtio'}}
    return __salt__['config.option']('virt.nic', {}).get(nic, default)


def init(name, cpu, mem, image, nic='default', emulator='kvm', **kwargs):
    '''
    Initialize a new vm

    CLI Example::

        salt 'hypervisor' vm_name 4 512 salt://path/to/image.raw
    '''
    img_dir = os.path.join(__salt__['config.option']('virt.images'), name)
    img_dest = os.path.join(
            __salt__['config.option']('virt.images'),
            name,
            'vda')
    sfn = __salt__['cp.cache_file'](image)
    if not os.path.isdir(img_dir):
        os.makedirs(img_dir)
    nicp = _nic_profile(nic)
    salt.utils.copyfile(sfn, img_dest)
    xml = _gen_xml(name, cpu, mem, img_dest, nicp, emulator, **kwargs)
    define_xml_str(xml)
    if kwargs.get('seed'):
        __salt__['img.seed'](img_dest, name, kwargs.get('config'))
    create(name)


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
                'nics': get_nics(vm_),
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


def vm_state(vm_=None):
    '''
    Return list of all the vms and their state.

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example::

        salt '*' virt.vm_state <vm name>
    '''
    def _info(vm_):
        state = ''
        dom = _get_dom(vm_)
        raw = dom.info()
        state = VIRT_STATE_NAME_MAP.get(raw[0], 'unknown')
        return state
    info = {}
    if vm_:
        info[vm_] = _info(vm_)
    else:
        for vm_ in list_vms():
            info[vm_] = _info(vm_)
    return info


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
    doc = minidom.parse(_StringIO(get_xml(vm_)))
    for node in doc.getElementsByTagName('devices'):
        i_nodes = node.getElementsByTagName('interface')
        for i_node in i_nodes:
            nic = {}
            nic['type'] = i_node.getAttribute('type')
            for v_node in i_node.getElementsByTagName('*'):
                if v_node.tagName == 'mac':
                    nic['mac'] = v_node.getAttribute('address')
                if v_node.tagName == 'model':
                    nic['model'] = v_node.getAttribute('type')
                if v_node.tagName == 'target':
                    nic['target'] = v_node.getAttribute('dev')
                # driver, source, and match can all have optional attributes
                if re.match('(driver|source|address)', v_node.tagName):
                    temp = {}
                    for key in v_node.attributes.keys():
                        temp[key] = v_node.getAttribute(key)
                    nic[str(v_node.tagName)] = temp
                # virtualport needs to be handled separately, to pick up the
                # type attribute of the virtualport itself
                if v_node.tagName == 'virtualport':
                    temp = {}
                    temp['type'] = v_node.getAttribute('type')
                    for key in v_node.attributes.keys():
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
    doc = minidom.parse(_StringIO(get_xml(vm_)))
    for node in doc.getElementsByTagName('devices'):
        i_nodes = node.getElementsByTagName('interface')
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
    ssock = _StringIO(xml)
    doc = minidom.parse(ssock)
    for node in doc.getElementsByTagName('domain'):
        g_nodes = node.getElementsByTagName('graphics')
        for g_node in g_nodes:
            for key in g_node.attributes.keys():
                out[key] = g_node.getAttribute(key)
    return out


def get_disks(vm_):
    '''
    Return the disks of a named vm

    CLI Example::

        salt '*' virt.get_disks <vm name>
    '''
    disks = {}
    doc = minidom.parse(_StringIO(get_xml(vm_)))
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
        if target.hasAttribute('dev'):
            qemu_target = ''
            if source.hasAttribute('file'):
                qemu_target = source.getAttribute('file')
            elif source.hasAttribute('dev'):
                qemu_target = source.getAttribute('dev')
            elif source.hasAttribute('protocol') and \
                    source.hasAttribute('name'): # For rbd network
                qemu_target = '%s:%s' % (
                        source.getAttribute('protocol'),
                        source.getAttribute('name'))
            if qemu_target:
                disks[target.getAttribute('dev')] = {
                    'file': qemu_target}
    for dev in disks:
        try:
            output = []
            qemu_output = subprocess.Popen(['qemu-img', 'info',
                disks[dev]['file']],
                shell=False,
                stdout=subprocess.PIPE).communicate()[0]
            snapshots = False
            columns = None
            lines = qemu_output.strip().split('\n')
            for line in lines:
                if line.startswith('Snapshot list:'):
                    snapshots = True
                    continue
                elif snapshots:
                    if line.startswith('ID'):  # Do not parse table headers
                        line = line.replace('VM SIZE', 'VMSIZE')
                        line = line.replace('VM CLOCK', 'TIME VMCLOCK')
                        columns = re.split(r'\s+', line)
                        columns = [c.lower() for c in columns]
                        output.append('snapshots:')
                        continue
                    fields = re.split(r'\s+', line)
                    for i, field in enumerate(fields):
                        sep = ' '
                        if i == 0:
                            sep = '-'
                        output.append(
                            '{0} {1}: "{2}"'.format(
                                sep, columns[i], field
                            )
                        )
                    continue
                output.append(line)
            output = '\n'.join(output)
            disks[dev].update(yaml.safe_load(output))
        except TypeError:
            disks[dev].update(yaml.safe_load('image: Does not exist'))
    return disks


def setmem(vm_, memory, config=False):
    '''
    Changes the amount of memory allocated to VM. The VM must be shutdown
    for this to work.

    memory is to be specified in MB
    If config is True then we ask libvirt to modify the config as well

    CLI Example::

        salt '*' virt.setmem myvm 768
    '''
    if vm_state(vm_) != 'shutdown':
        return False

    dom = _get_dom(vm_)

    # libvirt has a funny bitwise system for the flags in that the flag
    # to affect the "current" setting is 0, which means that to set the
    # current setting we have to call it a second time with just 0 set
    flags = libvirt.VIR_DOMAIN_MEM_MAXIMUM
    if config:
        flags = flags | libvirt.VIR_DOMAIN_AFFECT_CONFIG

    ret1 = dom.setMemoryFlags(memory * 1024, flags)
    ret2 = dom.setMemoryFlags(memory * 1024, libvirt.VIR_DOMAIN_AFFECT_CURRENT)

    # return True if both calls succeeded
    return ret1 == ret2 == 0


def setvcpus(vm_, vcpus, config=False):
    '''
    Changes the amount of vcpus allocated to VM. The VM must be shutdown
    for this to work.

    vcpus is an int representing the number to be assigned
    If config is True then we ask libvirt to modify the config as well

    CLI Example::

        salt '*' virt.setvcpus myvm 2
    '''
    if vm_state(vm_) != 'shutdown':
        return False

    dom = _get_dom(vm_)

    # see notes in setmem
    flags = libvirt.VIR_DOMAIN_VCPU_MAXIMUM
    if config:
        flags = flags | libvirt.VIR_DOMAIN_AFFECT_CONFIG

    ret1 = dom.setVcpusFlags(vcpus, flags)
    ret2 = dom.setVcpusFlags(vcpus, libvirt.VIR_DOMAIN_AFFECT_CURRENT)

    return ret1 == ret2 == 0


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
    Returns the XML for a given vm

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
    return dom.shutdown() == 0


def pause(vm_):
    '''
    Pause the named vm

    CLI Example::

        salt '*' virt.pause <vm name>
    '''
    dom = _get_dom(vm_)
    return dom.suspend() == 0


def resume(vm_):
    '''
    Resume the named vm

    CLI Example::

        salt '*' virt.resume <vm name>
    '''
    dom = _get_dom(vm_)
    return dom.resume() == 0


def create(vm_):
    '''
    Start a defined domain

    CLI Example::

        salt '*' virt.create <vm name>
    '''
    dom = _get_dom(vm_)
    return dom.create() == 0


def start(vm_):
    '''
    Alias for the obscurely named 'create' function

    CLI Example::

        salt '*' virt.start <vm name>
    '''
    return create(vm_)


def reboot(vm_):
    '''
    Reboot a domain via ACPI request

    CLI Example::

        salt '*' virt.reboot <vm name>
    '''
    dom = _get_dom(vm_)

    # reboot has a few modes of operation, passing 0 in means the
    # hypervisor will pick the best method for rebooting
    return dom.reboot(0) == 0


def reset(vm_):
    '''
    Reset a VM by emulating the reset button on a physical machine

    CLI Example::

        salt '*' virt.reset <vm name>
    '''
    dom = _get_dom(vm_)

    # reset takes a flag, like reboot, but it is not yet used
    # so we just pass in 0
    # see: http://libvirt.org/html/libvirt-libvirt.html#virDomainReset
    return dom.reset(0) == 0


def ctrl_alt_del(vm_):
    '''
    Sends CTRL+ALT+DEL to a VM

    CLI Example::

        salt '*' virt.ctrl_alt_del <vm name>
    '''
    dom = _get_dom(vm_)
    return dom.sendKey(0, 0, [29, 56, 111], 3, 0) == 0


def create_xml_str(xml):
    '''
    Start a domain based on the XML passed to the function

    CLI Example::

        salt '*' virt.create_xml_str <XML in string format>
    '''
    conn = __get_conn()
    return conn.createXML(xml, 0) is not None


def create_xml_path(path):
    '''
    Start a defined domain

    CLI Example::

        salt '*' virt.create_xml_path <path to XML file on the node>
    '''
    if not os.path.isfile(path):
        return False
    return create_xml_str(salt.utils.fopen(path, 'r').read())


def define_xml_str(xml):
    '''
    Define a domain based on the XML passed to the function

    CLI Example::

        salt '*' virt.define_xml_str <XML in string format>
    '''
    conn = __get_conn()
    return conn.defineXML(xml) is not None

def migrate_non_shared(vm_, target, ssh=False):
    '''
    Attempt to execute non-shared storage "all" migration

    CLI Example::

        salt '*' virt.migrate_non_shared <vm name> <target hypervisor>
    '''
    cmd = _get_migrate_command() + ' --copy-storage-all ' + vm_\
        + _get_target(target, ssh)

    return subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]


def migrate_non_shared_inc(vm_, target, ssh=False):
    '''
    Attempt to execute non-shared storage "all" migration

    CLI Example::

        salt '*' virt.migrate_non_shared_inc <vm name> <target hypervisor>
    '''
    cmd = _get_migrate_command() + ' --copy-storage-inc ' + vm_\
        + _get_target(target, ssh)

    return subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]


def migrate(vm_, target, ssh=False):
    '''
    Shared storage migration

    CLI Example::

        salt '*' virt.migrate <vm name> <target hypervisor>
    '''
    cmd = _get_migrate_command() + ' ' + vm_\
        + _get_target(target, ssh)

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
    for _, data in disks.items():
        fn_ = data['file']
        form = data['file format']
        size = data['virtual size'].split()[1][1:]
        if os.path.isfile(fn_) and not force:
            # the target exists, check to see if it is compatible
            pre = yaml.safe_load(subprocess.Popen('qemu-img info arch',
                shell=True,
                stdout=subprocess.PIPE).communicate()[0])
            if pre['file format'] != data['file format']\
                    and pre['virtual size'] != data['virtual size']:
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
    dom = _get_dom(vm_)
    return dom.destroy() == 0


def undefine(vm_):
    '''
    Remove a defined vm, this does not purge the virtual machine image, and
    this only works if the vm is powered down

    CLI Example::

        salt '*' virt.undefine <vm name>
    '''
    dom = _get_dom(vm_)
    return dom.undefine() == 0


def purge(vm_, dirs=False):
    '''
    Recursively destroy and delete a virtual machine, pass True for dir's to
    also delete the directories containing the virtual machine disk images -
    USE WITH EXTREME CAUTION!

    CLI Example::

        salt '*' virt.purge <vm name>
    '''
    disks = get_disks(vm_)
    try:
        if not destroy(vm_):
            return False
    except libvirt.libvirtError:
        # This is thrown if the machine is already shut down
        pass
    directories = set()
    for disk in disks:
        os.remove(disks[disk]['file'])
        directories.add(os.path.dirname(disks[disk]['file']))
    if dirs:
        for dir_ in directories:
            shutil.rmtree(dir_)
    undefine(vm_)
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
        if 'kvm_' not in salt.utils.fopen('/proc/modules').read():
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
        if 'xen_' not in salt.utils.fopen('/proc/modules').read():
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

def vm_cputime(vm_=None):
    '''
    Return cputime used by the vms on this hyper in a
    list of dicts::

        [
            'your-vm': {
                'cputime' <int>
                'cputime_percent' <int>
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example::

        salt '*' virt.vm_cputime
    '''
    host_cpus = __get_conn().getInfo()[2]
    def _info(vm_):
        dom = _get_dom(vm_)
        raw = dom.info()
        vcpus = int(raw[3])
        cputime = int(raw[4])
        cputime_percent = 0
        if cputime:
            # Divide by vcpus to always return a number between 0 and 100
            cputime_percent = (1.0e-7 * cputime / host_cpus) / vcpus
        return {
                'cputime': int(raw[4]),
                'cputime_percent': int('%.0f' % cputime_percent)
               }
    info = {}
    if vm_:
        info[vm_] = _info(vm_)
    else:
        for vm_ in list_vms():
            info[vm_] = _info(vm_)
    return info

def vm_netstats(vm_=None):
    '''
    Return combined network counters used by the vms on this hyper in a
    list of dicts::

        [
            'your-vm': {
                'rx_bytes'   : 0,
                'rx_packets' : 0,
                'rx_errs'    : 0,
                'rx_drop'    : 0,
                'tx_bytes'   : 0,
                'tx_packets' : 0,
                'tx_errs'    : 0,
                'tx_drop'    : 0
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example::

        salt '*' virt.vm_netstats
    '''
    def _info(vm_):
        dom = _get_dom(vm_)
        nics = get_nics(vm_)
        ret = {
                'rx_bytes'  : 0,
                'rx_packets': 0,
                'rx_errs'   : 0,
                'rx_drop'   : 0,
                'tx_bytes'  : 0,
                'tx_packets': 0,
                'tx_errs'   : 0,
                'tx_drop'   : 0
               }
        for attrs in nics.values():
            if 'target' in attrs:
                dev = attrs['target']
                stats = dom.interfaceStats(dev)
                ret['rx_bytes'] += stats[0]
                ret['rx_packets'] += stats[1]
                ret['rx_errs'] += stats[2]
                ret['rx_drop'] += stats[3]
                ret['tx_bytes'] += stats[4]
                ret['tx_packets'] += stats[5]
                ret['tx_errs'] += stats[6]
                ret['tx_drop'] += stats[7]

        return ret
    info = {}
    if vm_:
        info[vm_] = _info(vm_)
    else:
        for vm_ in list_vms():
            info[vm_] = _info(vm_)
    return info

def vm_diskstats(vm_=None):
    '''
    Return disk usage counters used by the vms on this hyper in a
    list of dicts::

        [
            'your-vm': {
                'rd_req'   : 0,
                'rd_bytes' : 0,
                'wr_req'   : 0,
                'wr_bytes' : 0,
                'errs'     : 0
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example::

        salt '*' virt.vm_blockstats
    '''
    def get_disk_devs(vm_):
        doc = minidom.parse(_StringIO(get_xml(vm_)))
        disks = []
        for elem in doc.getElementsByTagName('disk'):
            targets = elem.getElementsByTagName('target')
            target = targets[0]
            disks.append(target.getAttribute('dev'))
        return disks

    def _info(vm_):
        dom = _get_dom(vm_)
        # Do not use get_disks, since it uses qemu-img and is very slow
        # and unsuitable for any sort of real time statistics
        disks = get_disk_devs(vm_)
        ret = {
                'rd_req'  : 0,
                'rd_bytes': 0,
                'wr_req'  : 0,
                'wr_bytes': 0,
                'errs'    : 0
               }
        for disk in disks:
            stats = dom.blockStats(disk)
            ret['rd_req']   += stats[0]
            ret['rd_bytes'] += stats[1]
            ret['wr_req']   += stats[2]
            ret['wr_bytes'] += stats[3]
            ret['errs']     += stats[4]

        return ret
    info = {}
    if vm_:
        info[vm_] = _info(vm_)
    else:
        # Can not run function blockStats on inactive VMs
        for vm_ in list_active_vms():
            info[vm_] = _info(vm_)
    return info
