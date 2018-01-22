# -*- coding: utf-8 -*-
'''
Work with virtual machines managed by libvirt

:depends: libvirt Python module
'''
# Special Thanks to Michael Dehann, many of the concepts, and a few structures
# of his in the virt func module have been used

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import os
import re
import sys
import shutil
import subprocess
import string  # pylint: disable=deprecated-module
import logging
import time
import datetime
from xml.etree import ElementTree

# Import third party libs
import jinja2
import jinja2.exceptions
from salt.ext import six
from salt.ext.six.moves import StringIO as _StringIO  # pylint: disable=import-error
from xml.dom import minidom
try:
    import libvirt  # pylint: disable=import-error
    from libvirt import libvirtError
    HAS_LIBVIRT = True
except ImportError:
    HAS_LIBVIRT = False

# Import salt libs
import salt.utils.files
import salt.utils.network
import salt.utils.path
import salt.utils.stringutils
import salt.utils.templates
import salt.utils.validate.net
import salt.utils.yaml
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

# Set up template environment
JINJA = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(salt.utils.templates.TEMPLATE_DIRNAME, 'virt')
    )
)

VIRT_STATE_NAME_MAP = {0: 'running',
                       1: 'running',
                       2: 'running',
                       3: 'paused',
                       4: 'shutdown',
                       5: 'shutdown',
                       6: 'crashed'}

VIRT_DEFAULT_HYPER = 'kvm'


def __virtual__():
    if not HAS_LIBVIRT:
        return (False, 'Unable to locate or import python libvirt library.')
    return 'virt'


def __get_conn():
    '''
    Detects what type of dom this node is and attempts to connect to the
    correct hypervisor via libvirt.
    '''
    # This has only been tested on kvm and xen, it needs to be expanded to
    # support all vm layers supported by libvirt

    def __esxi_uri():
        '''
        Connect to an ESXi host with a configuration like so:

        .. code-block:: yaml

            libvirt:
              hypervisor: esxi
              connection: esx01

        The connection setting can either be an explicit libvirt URI,
        or a libvirt URI alias as in this example. No, it cannot be
        just a hostname.


        Example libvirt `/etc/libvirt/libvirt.conf`:

        .. code-block::

            uri_aliases = [
              "esx01=esx://10.1.1.101/?no_verify=1&auto_answer=1",
              "esx02=esx://10.1.1.102/?no_verify=1&auto_answer=1",
            ]

        Reference:

         - http://libvirt.org/drvesx.html#uriformat
         - http://libvirt.org/uri.html#URI_config
        '''
        connection = __salt__['config.get']('libvirt:connection', 'esx')
        return connection

    def __esxi_auth():
        '''
        We rely on that the credentials is provided to libvirt through
        its built in mechanisms.

        Example libvirt `/etc/libvirt/auth.conf`:

        .. code-block::

            [credentials-myvirt]
            username=user
            password=secret

            [auth-esx-10.1.1.101]
            credentials=myvirt

            [auth-esx-10.1.1.102]
            credentials=myvirt

        Reference:

          - http://libvirt.org/auth.html#Auth_client_config
        '''
        return [[libvirt.VIR_CRED_EXTERNAL], lambda: 0, None]

    if 'virt.connect' in __opts__:
        conn_str = __opts__['virt.connect']
    else:
        conn_str = 'qemu:///system'

    conn_func = {
        'esxi': [libvirt.openAuth, [__esxi_uri(),
                                    __esxi_auth(),
                                    0]],
        'qemu': [libvirt.open, [conn_str]],
    }

    hypervisor = __salt__['config.get']('libvirt:hypervisor', 'qemu')

    try:
        conn = conn_func[hypervisor][0](*conn_func[hypervisor][1])
    except Exception:
        raise CommandExecutionError(
            'Sorry, {0} failed to open a connection to the hypervisor '
            'software at {1}'.format(
                __grains__['fqdn'],
                conn_func[hypervisor][1][0]
            )
        )
    return conn


def _get_domain(*vms, **kwargs):
    '''
    Return a domain object for the named VM or return domain object for all VMs.
    '''
    ret = list()
    lookup_vms = list()
    conn = __get_conn()

    all_vms = list_domains()
    if not all_vms:
        raise CommandExecutionError('No virtual machines found.')

    if vms:
        for vm in vms:
            if vm not in all_vms:
                raise CommandExecutionError('The VM "{name}" is not present'.format(name=vm))
            else:
                lookup_vms.append(vm)
    else:
        lookup_vms = list(all_vms)

    for vm in lookup_vms:
        ret.append(conn.lookupByName(vm))

    return len(ret) == 1 and not kwargs.get('iterable') and ret[0] or ret


def _libvirt_creds():
    '''
    Returns the user and group that the disk images should be owned by
    '''
    g_cmd = 'grep ^\\s*group /etc/libvirt/qemu.conf'
    u_cmd = 'grep ^\\s*user /etc/libvirt/qemu.conf'
    try:
        stdout = subprocess.Popen(g_cmd,
                    shell=True,
                    stdout=subprocess.PIPE).communicate()[0]
        group = salt.utils.stringutils.to_str(stdout).split('"')[1]
    except IndexError:
        group = 'root'
    try:
        stdout = subprocess.Popen(u_cmd,
                    shell=True,
                    stdout=subprocess.PIPE).communicate()[0]
        user = salt.utils.stringutils.to_str(stdout).split('"')[1]
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
    return ' {0}://{1}/{2}'.format(proto, target, 'system')


def _gen_xml(name,
             cpu,
             mem,
             diskp,
             nicp,
             hypervisor,
             **kwargs):
    '''
    Generate the XML string to define a libvirt VM
    '''
    hypervisor = 'vmware' if hypervisor == 'esxi' else hypervisor
    mem = int(mem) * 1024  # MB
    context = {
        'hypervisor': hypervisor,
        'name': name,
        'cpu': six.text_type(cpu),
        'mem': six.text_type(mem),
    }
    if hypervisor in ['qemu', 'kvm']:
        context['controller_model'] = False
    elif hypervisor in ['esxi', 'vmware']:
        # TODO: make bus and model parameterized, this works for 64-bit Linux
        context['controller_model'] = 'lsilogic'

    if kwargs.get('enable_vnc', True):
        context['enable_vnc'] = True
    else:
        context['enable_vnc'] = False

    if 'boot_dev' in kwargs:
        context['boot_dev'] = []
        for dev in kwargs['boot_dev'].split():
            context['boot_dev'].append(dev)
    else:
        context['boot_dev'] = ['hd']

    if 'serial_type' in kwargs:
        context['serial_type'] = kwargs['serial_type']
    if 'serial_type' in context and context['serial_type'] == 'tcp':
        if 'telnet_port' in kwargs:
            context['telnet_port'] = kwargs['telnet_port']
        else:
            context['telnet_port'] = 23023  # FIXME: use random unused port
    if 'serial_type' in context:
        if 'console' in kwargs:
            context['console'] = kwargs['console']
        else:
            context['console'] = True

    context['disks'] = {}
    for i, disk in enumerate(diskp):
        for disk_name, args in six.iteritems(disk):
            context['disks'][disk_name] = {}
            fn_ = '{0}.{1}'.format(disk_name, args['format'])
            context['disks'][disk_name]['file_name'] = fn_
            context['disks'][disk_name]['source_file'] = os.path.join(args['pool'],
                                                                      name,
                                                                      fn_)
            if hypervisor in ['qemu', 'kvm']:
                context['disks'][disk_name]['target_dev'] = 'vd{0}'.format(string.ascii_lowercase[i])
                context['disks'][disk_name]['address'] = False
                context['disks'][disk_name]['driver'] = True
            elif hypervisor in ['esxi', 'vmware']:
                context['disks'][disk_name]['target_dev'] = 'sd{0}'.format(string.ascii_lowercase[i])
                context['disks'][disk_name]['address'] = True
                context['disks'][disk_name]['driver'] = False
            context['disks'][disk_name]['disk_bus'] = args['model']
            context['disks'][disk_name]['type'] = args['format']
            context['disks'][disk_name]['index'] = six.text_type(i)

    context['nics'] = nicp

    fn_ = 'libvirt_domain.jinja'
    try:
        template = JINJA.get_template(fn_)
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template %s', fn_)
        return ''

    return template.render(**context)


def _gen_vol_xml(vmname,
                 diskname,
                 size,
                 hypervisor,
                 **kwargs):
    '''
    Generate the XML string to define a libvirt storage volume
    '''
    size = int(size) * 1024  # MB
    disk_info = _get_image_info(hypervisor, vmname, **kwargs)
    context = {
        'name': vmname,
        'filename': '{0}.{1}'.format(diskname, disk_info['disktype']),
        'volname': diskname,
        'disktype': disk_info['disktype'],
        'size': six.text_type(size),
        'pool': disk_info['pool'],
    }
    fn_ = 'libvirt_volume.jinja'
    try:
        template = JINJA.get_template(fn_)
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template %s', fn_)
        return ''
    return template.render(**context)


def _qemu_image_info(path):
    '''
    Detect information for the image at path
    '''
    ret = {}
    out = __salt__['cmd.run']('qemu-img info {0}'.format(path))

    match_map = {'size': r'virtual size: \w+ \((\d+) byte[s]?\)',
                 'format': r'file format: (\w+)'}

    for info, search in six.iteritems(match_map):
        try:
            ret[info] = re.search(search, out).group(1)
        except AttributeError:
            continue
    return ret


def _qemu_image_create(vm_name,
                       disk_file_name,
                       disk_image=None,
                       disk_size=None,
                       disk_type='qcow2',
                       enable_qcow=False,
                       saltenv='base'):
    '''
    Create the image file using specified disk_size or/and disk_image

    Return path to the created image file
    '''
    if not disk_size and not disk_image:
        raise CommandExecutionError(
            'Unable to create new disk {0}, please specify'
            ' disk size and/or disk image argument'
            .format(disk_file_name)
        )

    img_dir = __salt__['config.option']('virt.images')
    log.debug('Image directory from config option `virt.images`'
              ' is %s', img_dir)
    img_dest = os.path.join(
        img_dir,
        vm_name,
        disk_file_name
    )
    log.debug('Image destination will be %s', img_dest)
    img_dir = os.path.dirname(img_dest)
    log.debug('Image destination directory is %s', img_dir)
    try:
        os.makedirs(img_dir)
    except OSError:
        pass

    if disk_image:
        log.debug('Create disk from specified image %s', disk_image)
        sfn = __salt__['cp.cache_file'](disk_image, saltenv)

        qcow2 = False
        if salt.utils.path.which('qemu-img'):
            res = __salt__['cmd.run']('qemu-img info {}'.format(sfn))
            imageinfo = salt.utils.yaml.safe_load(res)
            qcow2 = imageinfo['file format'] == 'qcow2'
        try:
            if enable_qcow and qcow2:
                log.info('Cloning qcow2 image %s using copy on write', sfn)
                __salt__['cmd.run'](
                    'qemu-img create -f qcow2 -o backing_file={0} {1}'
                    .format(sfn, img_dest).split())
            else:
                log.debug('Copying %s to %s', sfn, img_dest)
                salt.utils.files.copyfile(sfn, img_dest)

            mask = os.umask(0)
            os.umask(mask)

            if disk_size and qcow2:
                log.debug('Resize qcow2 image to %sM', disk_size)
                __salt__['cmd.run'](
                    'qemu-img resize {0} {1}M'
                    .format(img_dest, disk_size)
                )

            log.debug('Apply umask and remove exec bit')
            mode = (0o0777 ^ mask) & 0o0666
            os.chmod(img_dest, mode)

        except (IOError, OSError) as e:
            raise CommandExecutionError(
                'Problem while copying image. {0} - {1}'
                .format(disk_image, e)
            )

    else:
        # Create empty disk
        try:
            mask = os.umask(0)
            os.umask(mask)

            if disk_size:
                log.debug('Create empty image with size %sM', disk_size)
                __salt__['cmd.run'](
                    'qemu-img create -f {0} {1} {2}M'
                    .format(disk_type, img_dest, disk_size)
                )
            else:
                raise CommandExecutionError(
                    'Unable to create new disk {0},'
                    ' please specify <size> argument'
                    .format(img_dest)
                )

            log.debug('Apply umask and remove exec bit')
            mode = (0o0777 ^ mask) & 0o0666
            os.chmod(img_dest, mode)

        except (IOError, OSError) as e:
            raise CommandExecutionError(
                'Problem while creating volume {0} - {1}'
                .format(img_dest, e)
            )

    return img_dest


# TODO: this function is deprecated, should be replaced with
# _qemu_image_info()
def _image_type(vda):
    '''
    Detect what driver needs to be used for the given image
    '''
    out = __salt__['cmd.run']('qemu-img info {0}'.format(vda))
    if 'file format: qcow2' in out:
        return 'qcow2'
    else:
        return 'raw'


# TODO: this function is deprecated, should be merged and replaced
# with _disk_profile()
def _get_image_info(hypervisor, name, **kwargs):
    '''
    Determine disk image info, such as filename, image format and
    storage pool, based on which hypervisor is used
    '''
    ret = {}
    if hypervisor in ['esxi', 'vmware']:
        ret['disktype'] = 'vmdk'
        ret['filename'] = '{0}{1}'.format(name, '.vmdk')
        ret['pool'] = '[{0}] '.format(kwargs.get('pool', '0'))
    elif hypervisor in ['kvm', 'qemu']:
        ret['disktype'] = 'qcow2'
        ret['filename'] = '{0}{1}'.format(name, '.qcow2')
        ret['pool'] = __salt__['config.option']('virt.images')
    return ret


def _disk_profile(profile, hypervisor, **kwargs):
    '''
    Gather the disk profile from the config or apply the default based
    on the active hypervisor

    This is the ``default`` profile for KVM/QEMU, which can be
    overridden in the configuration:

    .. code-block:: yaml

        virt:
          disk:
            default:
              - system:
                  size: 8192
                  format: qcow2
                  model: virtio

    Example profile for KVM/QEMU with two disks, first is created
    from specified image, the second is empty:

    .. code-block:: yaml

        virt:
          disk:
            two_disks:
              - system:
                  size: 8192
                  format: qcow2
                  model: virtio
                  image: http://path/to/image.qcow2
              - lvm:
                  size: 32768
                  format: qcow2
                  model: virtio

    The ``format`` and ``model`` parameters are optional, and will
    default to whatever is best suitable for the active hypervisor.
    '''
    default = [
          {'system':
             {'size': '8192'}
          }
    ]
    if hypervisor in ['esxi', 'vmware']:
        overlay = {'format': 'vmdk',
                   'model': 'scsi',
                   'pool': '[{0}] '.format(kwargs.get('pool', '0'))
                  }
    elif hypervisor in ['qemu', 'kvm']:
        overlay = {'format': 'qcow2',
                   'model': 'virtio',
                   'pool': __salt__['config.option']('virt.images')
                  }
    else:
        overlay = {}

    disklist = copy.deepcopy(
        __salt__['config.get']('virt:disk', {}).get(profile, default))
    for key, val in six.iteritems(overlay):
        for i, disks in enumerate(disklist):
            for disk in disks:
                if key not in disks[disk]:
                    disklist[i][disk][key] = val
    return disklist


def _nic_profile(profile_name, hypervisor, **kwargs):

    default = [{'eth0': {}}]
    vmware_overlay = {'type': 'bridge', 'source': 'DEFAULT', 'model': 'e1000'}
    kvm_overlay = {'type': 'bridge', 'source': 'br0', 'model': 'virtio'}
    overlays = {
            'kvm': kvm_overlay,
            'qemu': kvm_overlay,
            'esxi': vmware_overlay,
            'vmware': vmware_overlay,
            }

    # support old location
    config_data = __salt__['config.option']('virt.nic', {}).get(
        profile_name, None
    )

    if config_data is None:
        config_data = __salt__['config.get']('virt:nic', {}).get(
            profile_name, default
        )

    interfaces = []

    def append_dict_profile_to_interface_list(profile_dict):
        for interface_name, attributes in six.iteritems(profile_dict):
            attributes['name'] = interface_name
            interfaces.append(attributes)

    # old style dicts (top-level dicts)
    #
    # virt:
    #    nic:
    #        eth0:
    #            bridge: br0
    #        eth1:
    #            network: test_net
    if isinstance(config_data, dict):
        append_dict_profile_to_interface_list(config_data)

    # new style lists (may contain dicts)
    #
    # virt:
    #   nic:
    #     - eth0:
    #         bridge: br0
    #     - eth1:
    #         network: test_net
    #
    # virt:
    #   nic:
    #     - name: eth0
    #       bridge: br0
    #     - name: eth1
    #       network: test_net
    elif isinstance(config_data, list):
        for interface in config_data:
            if isinstance(interface, dict):
                if len(interface) == 1:
                    append_dict_profile_to_interface_list(interface)
                else:
                    interfaces.append(interface)

    def _normalize_net_types(attributes):
        '''
        Guess which style of definition:

            bridge: br0

             or

            network: net0

             or

            type: network
            source: net0
        '''
        for type_ in ['bridge', 'network']:
            if type_ in attributes:
                attributes['type'] = type_
                # we want to discard the original key
                attributes['source'] = attributes.pop(type_)

        attributes['type'] = attributes.get('type', None)
        attributes['source'] = attributes.get('source', None)

    def _apply_default_overlay(attributes):
        for key, value in six.iteritems(overlays[hypervisor]):
            if key not in attributes or not attributes[key]:
                attributes[key] = value

    def _assign_mac(attributes, hypervisor):
        dmac = kwargs.get('dmac', None)
        if dmac is not None:
            log.debug('DMAC address is %s', dmac)
            if salt.utils.validate.net.mac(dmac):
                attributes['mac'] = dmac
            else:
                msg = 'Malformed MAC address: {0}'.format(dmac)
                raise CommandExecutionError(msg)
        else:
            if hypervisor in ['qemu', 'kvm']:
                attributes['mac'] = salt.utils.network.gen_mac(
                    prefix='52:54:00')
            else:
                attributes['mac'] = salt.utils.network.gen_mac()

    for interface in interfaces:
        _normalize_net_types(interface)
        _assign_mac(interface, hypervisor)
        if hypervisor in overlays:
            _apply_default_overlay(interface)

    return interfaces


def init(name,
         cpu,
         mem,
         image=None,
         nic='default',
         hypervisor=VIRT_DEFAULT_HYPER,
         start=True,  # pylint: disable=redefined-outer-name
         disk='default',
         saltenv='base',
         seed=True,
         install=True,
         pub_key=None,
         priv_key=None,
         seed_cmd='seed.apply',
         enable_vnc=False,
         enable_qcow=False,
         **kwargs):
    '''
    Initialize a new vm

    CLI Example:

    .. code-block:: bash

        salt 'hypervisor' virt.init vm_name 4 512 salt://path/to/image.raw
        salt 'hypervisor' virt.init vm_name 4 512 /var/lib/libvirt/images/img.raw
        salt 'hypervisor' virt.init vm_name 4 512 nic=profile disk=profile
    '''
    hypervisor = __salt__['config.get']('libvirt:hypervisor', hypervisor)
    log.debug('Using hyperisor %s', hypervisor)

    nicp = _nic_profile(nic, hypervisor, **kwargs)
    log.debug('NIC profile is %s', nicp)

    diskp = _disk_profile(disk, hypervisor, **kwargs)

    if image:
        # If image is specified in module arguments, then it will be used
        # for the first disk instead of the image from the disk profile
        disk_name = next(six.iterkeys(diskp[0]))
        log.debug('%s image from module arguments will be used for disk "%s"'
                  ' instead of %s', image, disk_name, diskp[0][disk_name].get('image'))
        diskp[0][disk_name]['image'] = image

    # Create multiple disks, empty or from specified images.
    for disk in diskp:
        log.debug("Creating disk for VM [ %s ]: %s", name, disk)

        for disk_name, args in six.iteritems(disk):

            if hypervisor in ['esxi', 'vmware']:
                if 'image' in args:
                    # TODO: we should be copying the image file onto the ESX host
                    raise SaltInvocationError(
                        'virt.init does not support image '
                        'template in conjunction with esxi hypervisor'
                    )
                else:
                    # assume libvirt manages disks for us
                    log.debug('Generating libvirt XML for %s', disk)
                    xml = _gen_vol_xml(
                        name,
                        disk_name,
                        args['size'],
                        hypervisor,
                    )
                    define_vol_xml_str(xml)

            elif hypervisor in ['qemu', 'kvm']:

                disk_type = args.get('format', 'qcow2')
                disk_image = args.get('image', None)
                disk_size = args.get('size', None)
                disk_file_name = '{0}.{1}'.format(disk_name, disk_type)

                img_dest = _qemu_image_create(
                    vm_name=name,
                    disk_file_name=disk_file_name,
                    disk_image=disk_image,
                    disk_size=disk_size,
                    disk_type=disk_type,
                    enable_qcow=enable_qcow,
                    saltenv=saltenv,
                )

                # Seed only if there is an image specified
                if seed and disk_image:
                    log.debug('Seed command is %s', seed_cmd)
                    __salt__[seed_cmd](
                        img_dest,
                        id_=name,
                        config=kwargs.get('config'),
                        install=install,
                        pub_key=pub_key,
                        priv_key=priv_key,
                    )

            else:
                # Unknown hypervisor
                raise SaltInvocationError(
                    'Unsupported hypervisor when handling disk image: {0}'
                    .format(hypervisor)
                )

    log.debug('Generating VM XML')
    kwargs['enable_vnc'] = enable_vnc
    xml = _gen_xml(name, cpu, mem, diskp, nicp, hypervisor, **kwargs)
    try:
        define_xml_str(xml)
    except libvirtError as err:
        # check if failure is due to this domain already existing
        if "domain '{}' already exists".format(name) in six.text_type(err):
            # continue on to seeding
            log.warning(err)
        else:
            raise err  # a real error we should report upwards

    if start:
        log.debug('Starting VM %s', name)
        _get_domain(name).create()

    return True


def list_domains():
    '''
    Return a list of available domains.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_domains
    '''
    vms = []
    vms.extend(list_active_vms())
    vms.extend(list_inactive_vms())
    return vms


def list_active_vms():
    '''
    Return a list of names for active virtual machine on the minion

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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
    list of dicts:

    .. code-block:: python

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

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_info
    '''
    def _info(vm_):
        dom = _get_domain(vm_)
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
        for vm_ in list_domains():
            info[vm_] = _info(vm_)
    return info


def vm_state(vm_=None):
    '''
    Return list of all the vms and their state.

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_state <domain>
    '''
    def _info(vm_):
        state = ''
        dom = _get_domain(vm_)
        raw = dom.info()
        state = VIRT_STATE_NAME_MAP.get(raw[0], 'unknown')
        return state
    info = {}
    if vm_:
        info[vm_] = _info(vm_)
    else:
        for vm_ in list_domains():
            info[vm_] = _info(vm_)
    return info


def node_info():
    '''
    Return a dict with information about this node

    CLI Example:

    .. code-block:: bash

        salt '*' virt.node_info
    '''
    conn = __get_conn()
    raw = conn.getInfo()
    info = {'cpucores': raw[6],
            'cpumhz': raw[3],
            'cpumodel': six.text_type(raw[0]),
            'cpus': raw[2],
            'cputhreads': raw[7],
            'numanodes': raw[4],
            'phymemory': raw[1],
            'sockets': raw[5]}
    return info


def get_nics(vm_):
    '''
    Return info about the network interfaces of a named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_nics <domain>
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
                    for key, value in v_node.attributes.items():
                        temp[key] = value
                    nic[six.text_type(v_node.tagName)] = temp
                # virtualport needs to be handled separately, to pick up the
                # type attribute of the virtualport itself
                if v_node.tagName == 'virtualport':
                    temp = {}
                    temp['type'] = v_node.getAttribute('type')
                    for key, value in v_node.attributes.items():
                        temp[key] = value
                    nic['virtualport'] = temp
            if 'mac' not in nic:
                continue
            nics[nic['mac']] = nic
    return nics


def get_macs(vm_):
    '''
    Return a list off MAC addresses from the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_macs <domain>
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

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_graphics <domain>
    '''
    out = {'autoport': 'None',
           'keymap': 'None',
           'listen': 'None',
           'port': 'None',
           'type': 'None'}
    xml = get_xml(vm_)
    ssock = _StringIO(xml)
    doc = minidom.parse(ssock)
    for node in doc.getElementsByTagName('domain'):
        g_nodes = node.getElementsByTagName('graphics')
        for g_node in g_nodes:
            for key, value in g_node.attributes.items():
                out[key] = value
    return out


def get_disks(vm_):
    '''
    Return the disks of a named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_disks <domain>
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
                    source.hasAttribute('name'):  # For rbd network
                qemu_target = '{0}:{1}'.format(
                        source.getAttribute('protocol'),
                        source.getAttribute('name'))
            if qemu_target:
                disks[target.getAttribute('dev')] = {
                    'file': qemu_target}
    for dev in disks:
        try:
            hypervisor = __salt__['config.get']('libvirt:hypervisor', 'kvm')
            if hypervisor not in ['qemu', 'kvm']:
                break

            output = []
            stdout = subprocess.Popen(
                        ['qemu-img', 'info', disks[dev]['file']],
                        shell=False,
                        stdout=subprocess.PIPE).communicate()[0]
            qemu_output = salt.utils.stringutils.to_str(stdout)
            snapshots = False
            columns = None
            lines = qemu_output.strip().split('\n')
            for line in lines:
                if line.startswith('Snapshot list:'):
                    snapshots = True
                    continue

                # If this is a copy-on-write image, then the backing file
                # represents the base image
                #
                # backing file: base.qcow2 (actual path: /var/shared/base.qcow2)
                elif line.startswith('backing file'):
                    matches = re.match(r'.*\(actual path: (.*?)\)', line)
                    if matches:
                        output.append('backing file: {0}'.format(matches.group(1)))
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
            disks[dev].update(salt.utils.yaml.safe_load(output))
        except TypeError:
            disks[dev].update({'image': 'Does not exist'})
    return disks


def setmem(vm_, memory, config=False):
    '''
    Changes the amount of memory allocated to VM. The VM must be shutdown
    for this to work.

    memory is to be specified in MB
    If config is True then we ask libvirt to modify the config as well

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setmem <domain> <size>
        salt '*' virt.setmem my_domain 768
    '''
    if vm_state(vm_)[vm_] != 'shutdown':
        return False

    dom = _get_domain(vm_)

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

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setvcpus <domain> <amount>
        salt '*' virt.setvcpus my_domain 4
    '''
    if vm_state(vm_)[vm_] != 'shutdown':
        return False

    dom = _get_domain(vm_)

    # see notes in setmem
    flags = libvirt.VIR_DOMAIN_VCPU_MAXIMUM
    if config:
        flags = flags | libvirt.VIR_DOMAIN_AFFECT_CONFIG

    ret1 = dom.setVcpusFlags(vcpus, flags)
    ret2 = dom.setVcpusFlags(vcpus, libvirt.VIR_DOMAIN_AFFECT_CURRENT)

    return ret1 == ret2 == 0


def freemem():
    '''
    Return an int representing the amount of memory (in MB) that has not
    been given to virtual machines on this node

    CLI Example:

    .. code-block:: bash

        salt '*' virt.freemem
    '''
    conn = __get_conn()
    mem = conn.getInfo()[1]
    # Take off just enough to sustain the hypervisor
    mem -= 256
    for vm_ in list_domains():
        dom = _get_domain(vm_)
        if dom.ID() > 0:
            mem -= dom.info()[2] / 1024
    return mem


def freecpu():
    '''
    Return an int representing the number of unallocated cpus on this
    hypervisor

    CLI Example:

    .. code-block:: bash

        salt '*' virt.freecpu
    '''
    conn = __get_conn()
    cpus = conn.getInfo()[2]
    for vm_ in list_domains():
        dom = _get_domain(vm_)
        if dom.ID() > 0:
            cpus -= dom.info()[3]
    return cpus


def full_info():
    '''
    Return the node_info, vm_info and freemem

    CLI Example:

    .. code-block:: bash

        salt '*' virt.full_info
    '''
    return {'freecpu': freecpu(),
            'freemem': freemem(),
            'node_info': node_info(),
            'vm_info': vm_info()}


def get_xml(vm_):
    '''
    Returns the XML for a given vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_xml <domain>
    '''
    dom = _get_domain(vm_)
    return dom.XMLDesc(0)


def get_profiles(hypervisor=None):
    '''
    Return the virt profiles for hypervisor.

    Currently there are profiles for:

     - nic
     - disk

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_profiles
        salt '*' virt.get_profiles hypervisor=esxi
    '''
    ret = {}
    if hypervisor:
        hypervisor = hypervisor
    else:
        hypervisor = __salt__['config.get']('libvirt:hypervisor', VIRT_DEFAULT_HYPER)
    virtconf = __salt__['config.get']('virt', {})
    for typ in ['disk', 'nic']:
        _func = getattr(sys.modules[__name__], '_{0}_profile'.format(typ))
        ret[typ] = {'default': _func('default', hypervisor)}
        if typ in virtconf:
            ret.setdefault(typ, {})
            for prf in virtconf[typ]:
                ret[typ][prf] = _func(prf, hypervisor)
    return ret


def shutdown(vm_):
    '''
    Send a soft shutdown signal to the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.shutdown <domain>
    '''
    dom = _get_domain(vm_)
    return dom.shutdown() == 0


def pause(vm_):
    '''
    Pause the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pause <domain>
    '''
    dom = _get_domain(vm_)
    return dom.suspend() == 0


def resume(vm_):
    '''
    Resume the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.resume <domain>
    '''
    dom = _get_domain(vm_)
    return dom.resume() == 0


def start(name):
    '''
    Start a defined domain

    CLI Example:

    .. code-block:: bash

        salt '*' virt.start <domain>
    '''
    return _get_domain(name).create() == 0


def stop(name):
    '''
    Hard power down the virtual machine, this is equivalent to pulling the power.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.stop <domain>
    '''
    return _get_domain(name).destroy() == 0


def reboot(name):
    '''
    Reboot a domain via ACPI request

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reboot <domain>
    '''
    return _get_domain(name).reboot(libvirt.VIR_DOMAIN_REBOOT_DEFAULT) == 0


def reset(vm_):
    '''
    Reset a VM by emulating the reset button on a physical machine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reset <domain>
    '''
    dom = _get_domain(vm_)

    # reset takes a flag, like reboot, but it is not yet used
    # so we just pass in 0
    # see: http://libvirt.org/html/libvirt-libvirt.html#virDomainReset
    return dom.reset(0) == 0


def ctrl_alt_del(vm_):
    '''
    Sends CTRL+ALT+DEL to a VM

    CLI Example:

    .. code-block:: bash

        salt '*' virt.ctrl_alt_del <domain>
    '''
    dom = _get_domain(vm_)
    return dom.sendKey(0, 0, [29, 56, 111], 3, 0) == 0


def create_xml_str(xml):
    '''
    Start a domain based on the XML passed to the function

    CLI Example:

    .. code-block:: bash

        salt '*' virt.create_xml_str <XML in string format>
    '''
    conn = __get_conn()
    return conn.createXML(xml, 0) is not None


def create_xml_path(path):
    '''
    Start a domain based on the XML-file path passed to the function

    CLI Example:

    .. code-block:: bash

        salt '*' virt.create_xml_path <path to XML file on the node>
    '''
    try:
        with salt.utils.files.fopen(path, 'r') as fp_:
            return create_xml_str(
                salt.utils.stringutils.to_unicode(fp_.read())
            )
    except (OSError, IOError):
        return False


def define_xml_str(xml):
    '''
    Define a domain based on the XML passed to the function

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_xml_str <XML in string format>
    '''
    conn = __get_conn()
    return conn.defineXML(xml) is not None


def define_xml_path(path):
    '''
    Define a domain based on the XML-file path passed to the function

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_xml_path <path to XML file on the node>

    '''
    try:
        with salt.utils.files.fopen(path, 'r') as fp_:
            return define_xml_str(
                salt.utils.stringutils.to_unicode(fp_.read())
            )
    except (OSError, IOError):
        return False


def define_vol_xml_str(xml):
    '''
    Define a volume based on the XML passed to the function

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_vol_xml_str <XML in string format>
    '''
    poolname = __salt__['config.get']('libvirt:storagepool', 'default')
    conn = __get_conn()
    pool = conn.storagePoolLookupByName(six.text_type(poolname))
    return pool.createXML(xml, 0) is not None


def define_vol_xml_path(path):
    '''
    Define a volume based on the XML-file path passed to the function

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_vol_xml_path <path to XML file on the node>

    '''
    try:
        with salt.utils.files.fopen(path, 'r') as fp_:
            return define_vol_xml_str(
                salt.utils.stringutils.to_unicode(fp_.read())
            )
    except (OSError, IOError):
        return False


def migrate_non_shared(vm_, target, ssh=False):
    '''
    Attempt to execute non-shared storage "all" migration

    CLI Example:

    .. code-block:: bash

        salt '*' virt.migrate_non_shared <vm name> <target hypervisor>
    '''
    cmd = _get_migrate_command() + ' --copy-storage-all ' + vm_\
        + _get_target(target, ssh)

    stdout = subprocess.Popen(cmd,
                shell=True,
                stdout=subprocess.PIPE).communicate()[0]
    return salt.utils.stringutils.to_str(stdout)


def migrate_non_shared_inc(vm_, target, ssh=False):
    '''
    Attempt to execute non-shared storage "all" migration

    CLI Example:

    .. code-block:: bash

        salt '*' virt.migrate_non_shared_inc <vm name> <target hypervisor>
    '''
    cmd = _get_migrate_command() + ' --copy-storage-inc ' + vm_\
        + _get_target(target, ssh)

    stdout = subprocess.Popen(cmd,
                shell=True,
                stdout=subprocess.PIPE).communicate()[0]
    return salt.utils.stringutils.to_str(stdout)


def migrate(vm_, target, ssh=False):
    '''
    Shared storage migration

    CLI Example:

    .. code-block:: bash

        salt '*' virt.migrate <domain> <target hypervisor>
    '''
    cmd = _get_migrate_command() + ' ' + vm_\
        + _get_target(target, ssh)

    stdout = subprocess.Popen(cmd,
                shell=True,
                stdout=subprocess.PIPE).communicate()[0]
    return salt.utils.stringutils.to_str(stdout)


def seed_non_shared_migrate(disks, force=False):
    '''
    Non shared migration requires that the disks be present on the migration
    destination, pass the disks information via this function, to the
    migration destination before executing the migration.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.seed_non_shared_migrate <disks>
    '''
    for _, data in six.iteritems(disks):
        fn_ = data['file']
        form = data['file format']
        size = data['virtual size'].split()[1][1:]
        if os.path.isfile(fn_) and not force:
            # the target exists, check to see if it is compatible
            pre = salt.utils.yaml.safe_load(subprocess.Popen('qemu-img info arch',
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

    CLI Example:

    .. code-block:: bash

        salt "*" virt.set_autostart <domain> <on | off>
    '''

    dom = _get_domain(vm_)

    if state == 'on':
        return dom.setAutostart(1) == 0

    elif state == 'off':
        return dom.setAutostart(0) == 0

    else:
        # return False if state is set to something other then on or off
        return False


def undefine(vm_):
    '''
    Remove a defined vm, this does not purge the virtual machine image, and
    this only works if the vm is powered down

    CLI Example:

    .. code-block:: bash

        salt '*' virt.undefine <domain>
    '''
    dom = _get_domain(vm_)
    return dom.undefine() == 0


def purge(vm_, dirs=False):
    '''
    Recursively destroy and delete a virtual machine, pass True for dir's to
    also delete the directories containing the virtual machine disk images -
    USE WITH EXTREME CAUTION!

    CLI Example:

    .. code-block:: bash

        salt '*' virt.purge <domain>
    '''
    disks = get_disks(vm_)
    try:
        if not stop(vm_):
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

    CLI Example:

    .. code-block:: bash

        salt '*' virt.virt_type
    '''
    return __grains__['virtual']


def is_kvm_hyper():
    '''
    Returns a bool whether or not this node is a KVM hypervisor

    CLI Example:

    .. code-block:: bash

        salt '*' virt.is_kvm_hyper
    '''
    try:
        with salt.utils.files.fopen('/proc/modules') as fp_:
            if 'kvm_' not in salt.utils.stringutils.to_unicode(fp_.read()):
                return False
    except IOError:
        # No /proc/modules? Are we on Windows? Or Solaris?
        return False
    return 'libvirtd' in __salt__['cmd.run'](__grains__['ps'])


def is_xen_hyper():
    '''
    Returns a bool whether or not this node is a XEN hypervisor

    CLI Example:

    .. code-block:: bash

        salt '*' virt.is_xen_hyper
    '''
    try:
        if __grains__['virtual_subtype'] != 'Xen Dom0':
            return False
    except KeyError:
        # virtual_subtype isn't set everywhere.
        return False
    try:
        with salt.utils.files.fopen('/proc/modules') as fp_:
            if 'xen_' not in salt.utils.stringutils.to_unicode(fp_.read()):
                return False
    except (OSError, IOError):
        # No /proc/modules? Are we on Windows? Or Solaris?
        return False
    return 'libvirtd' in __salt__['cmd.run'](__grains__['ps'])


def is_hyper():
    '''
    Returns a bool whether or not this node is a hypervisor of any kind

    CLI Example:

    .. code-block:: bash

        salt '*' virt.is_hyper
    '''
    if HAS_LIBVIRT:
        return is_xen_hyper() or is_kvm_hyper()
    return False


def vm_cputime(vm_=None):
    '''
    Return cputime used by the vms on this hyper in a
    list of dicts:

    .. code-block:: python

        [
            'your-vm': {
                'cputime' <int>
                'cputime_percent' <int>
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_cputime
    '''
    host_cpus = __get_conn().getInfo()[2]

    def _info(vm_):
        dom = _get_domain(vm_)
        raw = dom.info()
        vcpus = int(raw[3])
        cputime = int(raw[4])
        cputime_percent = 0
        if cputime:
            # Divide by vcpus to always return a number between 0 and 100
            cputime_percent = (1.0e-7 * cputime / host_cpus) / vcpus
        return {
                'cputime': int(raw[4]),
                'cputime_percent': int('{0:.0f}'.format(cputime_percent))
               }
    info = {}
    if vm_:
        info[vm_] = _info(vm_)
    else:
        for vm_ in list_domains():
            info[vm_] = _info(vm_)
    return info


def vm_netstats(vm_=None):
    '''
    Return combined network counters used by the vms on this hyper in a
    list of dicts:

    .. code-block:: python

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

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_netstats
    '''
    def _info(vm_):
        dom = _get_domain(vm_)
        nics = get_nics(vm_)
        ret = {
                'rx_bytes': 0,
                'rx_packets': 0,
                'rx_errs': 0,
                'rx_drop': 0,
                'tx_bytes': 0,
                'tx_packets': 0,
                'tx_errs': 0,
                'tx_drop': 0
               }
        for attrs in six.itervalues(nics):
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
        for vm_ in list_domains():
            info[vm_] = _info(vm_)
    return info


def vm_diskstats(vm_=None):
    '''
    Return disk usage counters used by the vms on this hyper in a
    list of dicts:

    .. code-block:: python

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

    CLI Example:

    .. code-block:: bash

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
        dom = _get_domain(vm_)
        # Do not use get_disks, since it uses qemu-img and is very slow
        # and unsuitable for any sort of real time statistics
        disks = get_disk_devs(vm_)
        ret = {'rd_req': 0,
               'rd_bytes': 0,
               'wr_req': 0,
               'wr_bytes': 0,
               'errs': 0
               }
        for disk in disks:
            stats = dom.blockStats(disk)
            ret['rd_req'] += stats[0]
            ret['rd_bytes'] += stats[1]
            ret['wr_req'] += stats[2]
            ret['wr_bytes'] += stats[3]
            ret['errs'] += stats[4]

        return ret
    info = {}
    if vm_:
        info[vm_] = _info(vm_)
    else:
        # Can not run function blockStats on inactive VMs
        for vm_ in list_active_vms():
            info[vm_] = _info(vm_)
    return info


def _parse_snapshot_description(snapshot, unix_time=False):
    '''
    Parse XML doc and return a dict with the status values.

    :param xmldoc:
    :return:
    '''
    ret = dict()
    tree = ElementTree.fromstring(snapshot.getXMLDesc())
    for node in tree:
        if node.tag == 'name':
            ret['name'] = node.text
        elif node.tag == 'creationTime':
            ret['created'] = not unix_time and datetime.datetime.fromtimestamp(
                float(node.text)).isoformat(' ') or float(node.text)
        elif node.tag == 'state':
            ret['running'] = node.text == 'running'

    ret['current'] = snapshot.isCurrent() == 1

    return ret


def list_snapshots(domain=None):
    '''
    List available snapshots for certain vm or for all.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_snapshots
        salt '*' virt.list_snapshots <domain>
    '''
    ret = dict()
    for vm_domain in _get_domain(*(domain and [domain] or list()), iterable=True):
        ret[vm_domain.name()] = [_parse_snapshot_description(snap) for snap in vm_domain.listAllSnapshots()] or 'N/A'

    return ret


def snapshot(domain, name=None, suffix=None):
    '''
    Create a snapshot of a VM.

    Options:

    * **name**: Name of the snapshot. If the name is omitted, then will be used original domain name with
                ISO 8601 time as a suffix.

    * **suffix**: Add suffix for the new name. Useful in states, where such snapshots
                  can be distinguished from manually created.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.snapshot <domain>
    '''
    if name and name.lower() == domain.lower():
        raise CommandExecutionError('Virtual Machine {name} is already defined. '
                                    'Please choose another name for the snapshot'.format(name=name))
    if not name:
        name = "{domain}-{tsnap}".format(domain=domain, tsnap=time.strftime('%Y%m%d-%H%M%S', time.localtime()))

    if suffix:
        name = "{name}-{suffix}".format(name=name, suffix=suffix)

    doc = ElementTree.Element('domainsnapshot')
    n_name = ElementTree.SubElement(doc, 'name')
    n_name.text = name

    _get_domain(domain).snapshotCreateXML(ElementTree.tostring(doc))

    return {'name': name}


def delete_snapshots(name, *names, **kwargs):
    '''
    Delete one or more snapshots of the given VM.

    Options:

    * **all**: Remove all snapshots. Values: True or False (default False).

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.delete_snapshots <domain> all=True
        salt '*' virt.delete_snapshots <domain> <snapshot>
        salt '*' virt.delete_snapshots <domain> <snapshot1> <snapshot2> ...
    '''
    deleted = dict()
    for snap in _get_domain(name).listAllSnapshots():
        if snap.getName() in names or not names:
            deleted[snap.getName()] = _parse_snapshot_description(snap)
            snap.delete()

    return {'available': list_snapshots(name), 'deleted': deleted}


def revert_snapshot(name, snapshot=None, cleanup=False):
    '''
    Revert snapshot to the previous from current (if available) or to the specific.

    Options:

    * **cleanup**: Remove all newer than reverted snapshots. Values: True or False (default False).

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.revert <domain>
        salt '*' virt.revert <domain> <snapshot>
    '''
    ret = dict()
    domain = _get_domain(name)
    snapshots = domain.listAllSnapshots()

    _snapshots = list()
    for snap_obj in snapshots:
        _snapshots.append({'idx': _parse_snapshot_description(snap_obj, unix_time=True)['created'], 'ptr': snap_obj})
    snapshots = [w_ptr['ptr'] for w_ptr in sorted(_snapshots, key=lambda item: item['idx'], reverse=True)]
    del _snapshots

    if not snapshots:
        raise CommandExecutionError('No snapshots found')
    elif len(snapshots) == 1:
        raise CommandExecutionError('Cannot revert to itself: only one snapshot is available.')

    snap = None
    for p_snap in snapshots:
        if not snapshot:
            if p_snap.isCurrent() and snapshots[snapshots.index(p_snap) + 1:]:
                snap = snapshots[snapshots.index(p_snap) + 1:][0]
                break
        elif p_snap.getName() == snapshot:
            snap = p_snap
            break

    if not snap:
        raise CommandExecutionError(
            snapshot and 'Snapshot "{0}" not found'.format(snapshot) or 'No more previous snapshots available')
    elif snap.isCurrent():
        raise CommandExecutionError('Cannot revert to the currently running snapshot.')

    domain.revertToSnapshot(snap)
    ret['reverted'] = snap.getName()

    if cleanup:
        delete = list()
        for p_snap in snapshots:
            if p_snap.getName() != snap.getName():
                delete.append(p_snap.getName())
                p_snap.delete()
            else:
                break
        ret['deleted'] = delete
    else:
        ret['deleted'] = 'N/A'

    return ret


def _capabilities():
    '''
    Return connection capabilities
    It's a huge klutz to parse right,
    so hide func for now and pass on the XML instead
    '''
    conn = __get_conn()
    caps = conn.getCapabilities()
    caps = minidom.parseString(caps)

    return caps


def cpu_baseline(full=False, migratable=False, out='libvirt'):
    '''
    Return the optimal 'custom' CPU baseline config for VM's on this minion

    .. versionadded:: 2016.3.0

    :param full: Return all CPU features rather than the ones on top of the closest CPU model
    :param migratable: Exclude CPU features that are unmigratable (libvirt 2.13+)
    :param out: 'libvirt' (default) for usable libvirt XML definition, 'salt' for nice dict

    CLI Example:

    .. code-block:: bash

        salt '*' virt.cpu_baseline

    '''
    conn = __get_conn()
    caps = _capabilities()

    cpu = caps.getElementsByTagName('host')[0].getElementsByTagName('cpu')[0]

    log.debug('Host CPU model definition: %s', cpu.toxml())

    flags = 0
    if migratable:
        # This one is only in 1.2.14+
        if getattr(libvirt, 'VIR_CONNECT_BASELINE_CPU_MIGRATABLE', False):
            flags += libvirt.VIR_CONNECT_BASELINE_CPU_MIGRATABLE
        else:
            raise ValueError

    if full and getattr(libvirt, 'VIR_CONNECT_BASELINE_CPU_EXPAND_FEATURES', False):
        # This one is only in 1.1.3+
        flags += libvirt.VIR_CONNECT_BASELINE_CPU_EXPAND_FEATURES

    cpu = conn.baselineCPU([cpu.toxml()], flags)
    cpu = minidom.parseString(cpu).getElementsByTagName('cpu')
    cpu = cpu[0]

    if full and not getattr(libvirt, 'VIR_CONNECT_BASELINE_CPU_EXPAND_FEATURES', False):
        # Try do it by ourselves
        # Find the models in cpu_map.xml and iterate over them for as long as entries have submodels
        with salt.utils.files.fopen('/usr/share/libvirt/cpu_map.xml', 'r') as cpu_map:
            cpu_map = minidom.parse(cpu_map)

        cpu_model = cpu.getElementsByTagName('model')[0].childNodes[0].nodeValue
        while cpu_model:
            cpu_specs = [el for el in cpu_map.getElementsByTagName('model') if el.getAttribute('name') == cpu_model and el.hasChildNodes()]

            if not len(cpu_specs):
                raise ValueError('Model {0} not found in CPU map'.format(cpu_model))
            elif len(cpu_specs) > 1:
                raise ValueError('Multiple models {0} found in CPU map'.format(cpu_model))

            cpu_specs = cpu_specs[0]

            cpu_model = cpu_specs.getElementsByTagName('model')
            if not len(cpu_model):
                cpu_model = None
            else:
                cpu_model = cpu_model[0].getAttribute('name')

            for feature in cpu_specs.getElementsByTagName('feature'):
                cpu.appendChild(feature)

    if out == 'libvirt':
        return cpu.toxml()
    elif out == 'salt':
        return {
            'model': cpu.getElementsByTagName('model')[0].childNodes[0].nodeValue,
            'vendor': cpu.getElementsByTagName('vendor')[0].childNodes[0].nodeValue,
            'features': [feature.getAttribute('name') for feature in cpu.getElementsByTagName('feature')]
        }
