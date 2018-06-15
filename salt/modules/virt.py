# -*- coding: utf-8 -*-
'''
Work with virtual machines managed by libvirt

Connection
==========

The connection to the virtualization host can be either setup in the minion configuration,
pillar data or overridden for each individual call.

By default, the libvirt connection URL will be guessed: the first available libvirt
hypervisor driver will be used. This can be overridden like this:

.. code-block:: yaml

    virt:
        connection:
            uri: lxc:///

If the connection requires an authentication like for ESXi, this can be defined in the
minion pillar data like this:

.. code-block:: yaml

    virt:
        connection:
            uri: esx://10.1.1.101/?no_verify=1&auto_answer=1
            auth:
                username: user
                password: secret

Connecting with SSH protocol
----------------------------

Libvirt can connect to remote hosts using SSH using one of the ``ssh``, ``libssh`` and
``libssh2`` transports. Note that ``libssh2`` is likely to fail as it doesn't read the
``known_hosts`` file. Libvirt may also have been built without ``libssh`` or ``libssh2``
support.

To use the SSH transport, on the minion setup an SSH agent with a key authorized on
the remote libvirt machine.

Per call connection setup
-------------------------

.. versionadded:: Fluorine

All the calls requiring the libvirt connection configuration as mentioned above can
override this configuration using ``connection``, ``username`` and ``password`` parameters.

This means that the following will list the domains on the local LXC libvirt driver,
whatever the ``virt:connection`` is.

.. code-block:: bash

    salt 'hypervisor' virt.list_domains connection=lxc:///

The calls not using the libvirt connection setup are:

- ``seed_non_shared_migrate``
- ``virt_type``
- ``is_*hyper``
- all migration functions

Reference:

- `libvirt ESX URI format <http://libvirt.org/drvesx.html#uriformat>`_
- `libvirt URI format <http://libvirt.org/uri.html#URI_config>`_
- `libvirt authentication configuration <http://libvirt.org/auth.html#Auth_client_config>`_

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
import xml.dom
from xml.dom import minidom
import jinja2
import jinja2.exceptions
try:
    import libvirt  # pylint: disable=import-error
    from libvirt import libvirtError
    HAS_LIBVIRT = True
except ImportError:
    HAS_LIBVIRT = False

# Import salt libs
import salt.utils.files
import salt.utils.json
import salt.utils.network
import salt.utils.path
import salt.utils.stringutils
import salt.utils.templates
import salt.utils.validate.net
import salt.utils.versions
import salt.utils.yaml
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext import six
from salt.ext.six.moves import StringIO as _StringIO  # pylint: disable=import-error

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


def __virtual__():
    if not HAS_LIBVIRT:
        return (False, 'Unable to locate or import python libvirt library.')
    return 'virt'


def __get_request_auth(username, password):
    '''
    Get libvirt.openAuth callback with username, password values overriding
    the configuration ones.
    '''

    # pylint: disable=unused-argument
    def __request_auth(credentials, user_data):
        '''Callback method passed to libvirt.openAuth().

        The credentials argument is a list of credentials that libvirt
        would like to request. An element of this list is a list containing
        5 items (4 inputs, 1 output):
          - the credential type, e.g. libvirt.VIR_CRED_AUTHNAME
          - a prompt to be displayed to the user
          - a challenge
          - a default result for the request
          - a place to store the actual result for the request

        The user_data argument is currently not set in the openAuth call.
        '''
        for credential in credentials:
            if credential[0] == libvirt.VIR_CRED_AUTHNAME:
                credential[4] = username if username else \
                                __salt__['config.get']('virt:connection:auth:username', credential[3])
            elif credential[0] == libvirt.VIR_CRED_NOECHOPROMPT:
                credential[4] = password if password else \
                                __salt__['config.get']('virt:connection:auth:password', credential[3])
            else:
                log.info('Unhandled credential type: %s', credential[0])
        return 0


def __get_conn(**kwargs):
    '''
    Detects what type of dom this node is and attempts to connect to the
    correct hypervisor via libvirt.

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    '''
    # This has only been tested on kvm and xen, it needs to be expanded to
    # support all vm layers supported by libvirt

    username = kwargs.get('username', None)
    password = kwargs.get('password', None)
    conn_str = kwargs.get('connection', None)
    if not conn_str:
        conn_str = __salt__['config.get']('virt.connect', None)
        if conn_str is not None:
            salt.utils.versions.warn_until(
                'Sodium',
                '\'virt.connect\' configuration property has been deprecated in favor '
                'of \'virt:connection:uri\'. \'virt.connect\' will stop being used in '
                '{version}.'
            )
        else:
            conn_str = __salt__['config.get']('libvirt:connection', None)
            if conn_str is not None:
                salt.utils.versions.warn_until(
                    'Sodium',
                    '\'libvirt.connection\' configuration property has been deprecated in favor '
                    'of \'virt:connection:uri\'. \'libvirt.connection\' will stop being used in '
                    '{version}.'
                )

        conn_str = __salt__['config.get']('virt:connection:uri', conn_str)

    hypervisor = __salt__['config.get']('libvirt:hypervisor', None)
    if hypervisor is not None:
        salt.utils.versions.warn_until(
            'Sodium',
            '\'libvirt.hypervisor\' configuration property has been deprecated. '
            'Rather use the \'virt:connection:uri\' to properly define the libvirt '
            'URI or alias of the host to connect to. \'libvirt:hypervisor\' will '
            'stop being used in {version}.'
        )

    if hypervisor == 'esxi' and conn_str is None:
        salt.utils.versions.warn_until(
            'Sodium',
            'esxi hypervisor default with no default connection URI detected, '
            'please set \'virt:connection:uri\' to \'esx\' for keep the legacy '
            'behavior. Will default to libvirt guess once \'libvirt:hypervisor\' '
            'configuration is removed in {version}.'
        )
        conn_str = 'esx'

    try:
        auth_types = [libvirt.VIR_CRED_AUTHNAME,
                      libvirt.VIR_CRED_NOECHOPROMPT,
                      libvirt.VIR_CRED_ECHOPROMPT,
                      libvirt.VIR_CRED_PASSPHRASE,
                      libvirt.VIR_CRED_EXTERNAL]
        conn = libvirt.openAuth(conn_str, [auth_types, __get_request_auth(username, password), None], 0)
    except Exception:
        raise CommandExecutionError(
            'Sorry, {0} failed to open a connection to the hypervisor '
            'software at {1}'.format(
                __grains__['fqdn'],
                conn_str
            )
        )
    return conn


def _get_domain_types(**kwargs):
    '''
    Return the list of possible values for the <domain> type attribute.
    '''
    caps = capabilities(**kwargs)
    return sorted(set([x for y in [guest['arch']['domains'].keys() for guest in caps['guests']] for x in y]))


def _get_domain(conn, *vms, **kwargs):
    '''
    Return a domain object for the named VM or return domain object for all VMs.

    :params conn: libvirt connection object
    :param vms: list of domain names to look for
    :param iterable: True to return an array in all cases
    '''
    ret = list()
    lookup_vms = list()

    all_vms = []
    if kwargs.get('active', True):
        for id_ in conn.listDomainsID():
            all_vms.append(conn.lookupByID(id_).name())

    if kwargs.get('inactive', True):
        for id_ in conn.listDefinedDomains():
            all_vms.append(id_)

    if not all_vms:
        raise CommandExecutionError('No virtual machines found.')

    if vms:
        for name in vms:
            if name not in all_vms:
                raise CommandExecutionError('The VM "{name}" is not present'.format(name=name))
            else:
                lookup_vms.append(name)
    else:
        lookup_vms = list(all_vms)

    for name in lookup_vms:
        ret.append(conn.lookupByName(name))

    return len(ret) == 1 and not kwargs.get('iterable') and ret[0] or ret


def _parse_qemu_img_info(info):
    '''
    Parse qemu-img info JSON output into disk infos dictionary
    '''
    raw_infos = salt.utils.json.loads(info)
    disks = []
    for disk_infos in raw_infos:
        disk = {
                   'file': disk_infos['filename'],
                   'file format': disk_infos['format'],
                   'disk size': disk_infos['actual-size'],
                   'virtual size': disk_infos['virtual-size'],
                   'cluster size': disk_infos['cluster-size']
               }

        if 'full-backing-filename' in disk_infos.keys():
            disk['backing file'] = format(disk_infos['full-backing-filename'])

        if 'snapshots' in disk_infos.keys():
            disk['snapshots'] = [
                    {
                        'id': snapshot['id'],
                        'tag': snapshot['name'],
                        'vmsize': snapshot['vm-state-size'],
                        'date': datetime.datetime.fromtimestamp(
                            float('{}.{}'.format(snapshot['date-sec'], snapshot['date-nsec']))).isoformat(),
                        'vmclock': datetime.datetime.utcfromtimestamp(
                            float('{}.{}'.format(snapshot['vm-clock-sec'],
                                                 snapshot['vm-clock-nsec']))).time().isoformat()
                    } for snapshot in disk_infos['snapshots']]
        disks.append(disk)

    for disk in disks:
        if 'backing file' in disk.keys():
            candidates = [info for info in disks if 'file' in info.keys() and info['file'] == disk['backing file']]
            if candidates:
                disk['backing file'] = candidates[0]

    return disks[0]


def _get_uuid(dom):
    '''
    Return a uuid from the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_uuid <domain>
    '''
    uuid = ''
    doc = minidom.parse(_StringIO(get_xml(dom)))
    for node in doc.getElementsByTagName('uuid'):
        uuid = node.firstChild.nodeValue
    return uuid


def _get_on_poweroff(dom):
    '''
    Return `on_poweroff` setting from the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_on_restart <domain>
    '''
    on_poweroff = ''
    doc = minidom.parse(_StringIO(get_xml(dom)))
    for node in doc.getElementsByTagName('on_poweroff'):
        on_poweroff = node.firstChild.nodeValue
    return on_poweroff


def _get_on_reboot(dom):
    '''
    Return `on_reboot` setting from the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_on_reboot <domain>
    '''
    on_restart = ''
    doc = minidom.parse(_StringIO(get_xml(dom)))
    for node in doc.getElementsByTagName('on_reboot'):
        on_restart = node.firstChild.nodeValue
    return on_restart


def _get_on_crash(dom):
    '''
    Return `on_crash` setting from the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_on_crash <domain>
    '''
    on_crash = ''
    doc = minidom.parse(_StringIO(get_xml(dom)))
    for node in doc.getElementsByTagName('on_crash'):
        on_crash = node.firstChild.nodeValue
    return on_crash


def _get_nics(dom):
    '''
    Get domain network interfaces from a libvirt domain object.
    '''
    nics = {}
    doc = minidom.parse(_StringIO(dom.XMLDesc(0)))
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


def _get_graphics(dom):
    '''
    Get domain graphics from a libvirt domain object.
    '''
    out = {'autoport': 'None',
           'keymap': 'None',
           'listen': 'None',
           'port': 'None',
           'type': 'None'}
    desc = dom.XMLDesc(0)
    ssock = _StringIO(desc)
    doc = minidom.parse(ssock)
    for node in doc.getElementsByTagName('domain'):
        g_nodes = node.getElementsByTagName('graphics')
        for g_node in g_nodes:
            for key, value in g_node.attributes.items():
                out[key] = value
    return out


def _get_disks(dom):
    '''
    Get domain disks from a libvirt domain object.
    '''
    disks = {}
    doc = minidom.parse(_StringIO(dom.XMLDesc(0)))
    for elem in doc.getElementsByTagName('disk'):
        sources = elem.getElementsByTagName('source')
        targets = elem.getElementsByTagName('target')
        if sources:
            source = sources[0]
        else:
            continue
        if targets:
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
            if not qemu_target:
                continue

            disk = {'file': qemu_target,
                    'type': elem.getAttribute('device')}

            driver = _get_xml_first_element_by_tag_name(elem, 'driver')
            if driver and driver.getAttribute('type') == 'qcow2':
                try:
                    stdout = subprocess.Popen(
                                ['qemu-img', 'info', '--output', 'json', '--backing-chain', disk['file']],
                                shell=False,
                                stdout=subprocess.PIPE).communicate()[0]
                    qemu_output = salt.utils.stringutils.to_str(stdout)
                    output = _parse_qemu_img_info(qemu_output)
                    disk.update(output)
                except TypeError:
                    disk.update({'file': 'Does not exist'})

            disks[target.getAttribute('dev')] = disk
    return disks


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
    tunnel = __salt__['config.option']('virt.tunnel')
    if tunnel:
        salt.utils.versions.warn_until(
            'Sodium',
            '\'virt.tunnel\' has been deprecated in favor of '
            '\'virt:tunnel\'. \'virt.tunnel\' will stop '
            'being used in {version}.')
    else:
        tunnel = __salt__['config.get']('virt:tunnel')
    if tunnel:
        return ('virsh migrate --p2p --tunnelled --live --persistent '
                '--undefinesource ')
    return 'virsh migrate --live --persistent --undefinesource '


def _get_target(target, ssh):
    '''
    Compute libvirt URL for target migration host.
    '''
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
             graphics=None,
             **kwargs):
    '''
    Generate the XML string to define a libvirt VM
    '''
    mem = int(mem) * 1024  # MB
    context = {
        'hypervisor': hypervisor,
        'name': name,
        'cpu': six.text_type(cpu),
        'mem': six.text_type(mem),
    }
    if hypervisor in ['qemu', 'kvm']:
        context['controller_model'] = False
    elif hypervisor == 'vmware':
        # TODO: make bus and model parameterized, this works for 64-bit Linux
        context['controller_model'] = 'lsilogic'

    # By default, set the graphics to listen to all addresses
    if graphics:
        if 'listen' not in graphics:
            graphics['listen'] = {'type': 'address', 'address': '0.0.0.0'}
        elif 'address' not in graphics['listen'] and graphics['listen']['type'] == 'address':
            graphics['listen']['address'] = '0.0.0.0'
    context['graphics'] = graphics

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
                 disktype,
                 size,
                 pool):
    '''
    Generate the XML string to define a libvirt storage volume
    '''
    size = int(size) * 1024  # MB
    context = {
        'name': vmname,
        'filename': '{0}.{1}'.format(diskname, disktype),
        'volname': diskname,
        'disktype': disktype,
        'size': six.text_type(size),
        'pool': pool,
    }
    fn_ = 'libvirt_volume.jinja'
    try:
        template = JINJA.get_template(fn_)
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template %s', fn_)
        return ''
    return template.render(**context)


def _gen_net_xml(name,
                 bridge,
                 forward,
                 vport,
                 tag=None):
    '''
    Generate the XML string to define a libvirt network
    '''
    context = {
        'name': name,
        'bridge': bridge,
        'forward': forward,
        'vport': vport,
        'tag': tag,
    }
    fn_ = 'libvirt_network.jinja'
    try:
        template = JINJA.get_template(fn_)
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template %s', fn_)
        return ''
    return template.render(**context)


def _gen_pool_xml(name,
                  ptype,
                  target,
                  source=None):
    '''
    Generate the XML string to define a libvirt storage pool
    '''
    context = {
        'name': name,
        'ptype': ptype,
        'target': target,
        'source': source,
    }
    fn_ = 'libvirt_pool.jinja'
    try:
        template = JINJA.get_template(fn_)
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template %s', fn_)
        return ''
    return template.render(**context)


def _get_images_dir():
    '''
    Extract the images dir from the configuration. First attempts to
    find legacy virt.images, then tries virt:images.
    '''
    img_dir = __salt__['config.option']('virt.images')
    if img_dir:
        salt.utils.versions.warn_until(
            'Sodium',
            '\'virt.images\' has been deprecated in favor of '
            '\'virt:images\'. \'virt.images\' will stop '
            'being used in {version}.')
    else:
        img_dir = __salt__['config.get']('virt:images')

    log.debug('Image directory from config option `virt:images`'
              ' is %s', img_dir)
    return img_dir


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

    img_dir = _get_images_dir()

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

            mask = salt.utils.files.get_umask()

            if disk_size and qcow2:
                log.debug('Resize qcow2 image to %sM', disk_size)
                __salt__['cmd.run'](
                    'qemu-img resize {0} {1}M'
                    .format(img_dest, disk_size)
                )

            log.debug('Apply umask and remove exec bit')
            mode = (0o0777 ^ mask) & 0o0666
            os.chmod(img_dest, mode)

        except (IOError, OSError) as err:
            raise CommandExecutionError(
                'Problem while copying image. {0} - {1}'
                .format(disk_image, err)
            )

    else:
        # Create empty disk
        try:
            mask = salt.utils.files.get_umask()

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

        except (IOError, OSError) as err:
            raise CommandExecutionError(
                'Problem while creating volume {0} - {1}'
                .format(img_dest, err)
            )

    return img_dest


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
    default = [{'system':
                {'size': '8192'}}]
    if hypervisor == 'vmware':
        overlay = {'format': 'vmdk',
                   'model': 'scsi',
                   'pool': '[{0}] '.format(kwargs.get('pool', '0'))}
    elif hypervisor in ['qemu', 'kvm']:
        overlay = {'format': 'qcow2',
                   'model': 'virtio',
                   'pool': _get_images_dir()}
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
    '''
    Compute NIC data based on profile
    '''

    default = [{'eth0': {}}]
    vmware_overlay = {'type': 'bridge', 'source': 'DEFAULT', 'model': 'e1000'}
    kvm_overlay = {'type': 'bridge', 'source': 'br0', 'model': 'virtio'}
    overlays = {
            'kvm': kvm_overlay,
            'qemu': kvm_overlay,
            'vmware': vmware_overlay,
            }

    # support old location
    config_data = __salt__['config.option']('virt.nic', {}).get(
        profile_name, None
    )

    if config_data is not None:
        salt.utils.versions.warn_until(
            'Sodium',
            '\'virt.nic\' has been deprecated in favor of \'virt:nic\'. '
            '\'virt.nic\' will stop being used in {version}.'
        )
    else:
        config_data = __salt__['config.get']('virt:nic', {}).get(
            profile_name, default
        )

    interfaces = []

    # pylint: disable=invalid-name
    def append_dict_profile_to_interface_list(profile_dict):
        '''
        Append dictionary profile data to interfaces list
        '''
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
        '''
        Apply the default overlay to attributes
        '''
        for key, value in six.iteritems(overlays[hypervisor]):
            if key not in attributes or not attributes[key]:
                attributes[key] = value

    def _assign_mac(attributes, hypervisor):
        '''
        Compute mac address for NIC depending on hypervisor
        '''
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
         hypervisor=None,
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
         graphics=None,
         **kwargs):
    '''
    Initialize a new vm

    :param name: name of the virtual machine to create
    :param cpu: Number of virtual CPUs to assign to the virtual machine
    :param mem: Amount of memory to allocate to the virtual machine in MiB.
    :param image: Path to a disk image to use as the first disk (Default: ``None``).
    :param nic: NIC profile to use (Default: ``'default'``).
    :param hypervisor: the virtual machine type. By default the value will be computed according
                       to the virtual host capabilities.
    :param start: ``True`` to start the virtual machine after having defined it (Default: ``True``)
    :param disk: Disk profile to use (Default: ``'default'``).
    :param saltenv: Fileserver environment (Default: ``'base'``).
                    See :mod:`cp module for more details <salt.modules.cp>`
    :param seed: ``True`` to seed the disk image. Only used when the ``image`` parameter is provided.
                 (Default: ``True``)
    :param install: install salt minion if absent (Default: ``True``)
    :param pub_key: public key to seed with (Default: ``None``)
    :param priv_key: public key to seed with (Default: ``None``)
    :param seed_cmd: Salt command to execute to seed the image. (Default: ``'seed.apply'``)
    :param enable_vnc:
        ``True`` to setup a vnc display for the VM (Default: ``False``)

        Deprecated in favor of the ``graphics`` parameter. Could be replaced with
        the following:

        .. code-block:: python

            graphics={'type': 'vnc'}

        .. deprecated:: Fluorine
    :param graphics:
        Dictionary providing details on the graphics device to create. (Default: ``None``)
        See :ref:`init-graphics-def` for more details on the possible values.

        .. versionadded:: Fluorine
    :param enable_qcow:
        ``True`` to create a QCOW2 overlay image, rather than copying the image
        (Default: ``False``).
    :param pool: Path of the folder where the image files are located for vmware/esx hypervisors.
    :param dmac:
        Default MAC address to use for the network interfaces. By default MAC addresses are
        automatically generated.
    :param config: minion configuration to use when seeding.
                   See :mod:`seed module for more details <salt.modules.seed>`
    :param boot_dev: String of space-separated devices to boot from (Default: ``'hd'``)
    :param serial_type: Serial device type. One of ``'pty'``, ``'tcp'`` (Default: ``None``)
    :param telnet_port: Telnet port to use for serial device of type ``tcp``.
    :param console: ``True`` to add a console device along with serial one (Default: ``True``)
    :param connection: libvirt connection URI, overriding defaults

                       .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

                     .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

                     .. versionadded:: Fluorine

    .. _init-graphics-def:

    .. rubric:: Graphics Definition

    The graphics dictionnary can have the following properties:

    type
        Graphics type. The possible values are ``'spice'``, ``'vnc'`` and other values
        allowed as a libvirt graphics type (Default: ``None``)

        See `the libvirt documentation <https://libvirt.org/formatdomain.html#elementsGraphics>`_
        for more details on the possible types

    port
        Port to export the graphics on for ``vnc``, ``spice`` and ``rdp`` types.

    tls_port
        Port to export the graphics over a secured connection for ``spice`` type.

    listen
        Dictionary defining on what address to listen on for ``vnc``, ``spice`` and ``rdp``.
        It has a ``type`` property with ``address`` and ``None`` as possible values, and an
        ``address`` property holding the IP or hostname to listen on.

        By default, not setting the ``listen`` part of the dictionary will default to
        listen on all addresses.

    .. rubric:: CLI Example

    .. code-block:: bash

        salt 'hypervisor' virt.init vm_name 4 512 salt://path/to/image.raw
        salt 'hypervisor' virt.init vm_name 4 512 /var/lib/libvirt/images/img.raw
        salt 'hypervisor' virt.init vm_name 4 512 nic=profile disk=profile

    The disk images will be created in an image folder within the directory
    defined by the ``virt:images`` option. Its default value is
    ``/srv/salt/salt-images/`` but this can changed with such a configuration:

    .. code-block:: yaml

        virt:
            images: /data/my/vm/images/
    '''
    hypervisors = _get_domain_types(**kwargs)
    hypervisor = __salt__['config.get']('libvirt:hypervisor', hypervisor)
    if hypervisor is not None:
        salt.utils.versions.warn_until(
            'Sodium',
            '\'libvirt:hypervisor\' configuration property has been deprecated. '
            'Rather use the \'virt:connection:uri\' to properly define the libvirt '
            'URI or alias of the host to connect to. \'libvirt:hypervisor\' will '
            'stop being used in {version}.'
        )
    else:
        # Use the machine types as possible values
        # Prefer 'kvm' over the others if available
        hypervisor = 'kvm' if 'kvm' in hypervisors else hypervisors[0]

    # esxi used to be a possible value for the hypervisor: map it to vmware since it's the same
    hypervisor = 'vmware' if hypervisor == 'esxi' else hypervisor

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
    for _disk in diskp:
        log.debug("Creating disk for VM [ %s ]: %s", name, _disk)

        for disk_name, args in six.iteritems(_disk):

            if hypervisor == 'vmware':
                if 'image' in args:
                    # TODO: we should be copying the image file onto the ESX host
                    raise SaltInvocationError(
                        'virt.init does not support image '
                        'template in conjunction with esxi hypervisor'
                    )
                else:
                    # assume libvirt manages disks for us
                    log.debug('Generating libvirt XML for %s', _disk)
                    vol_xml = _gen_vol_xml(
                        name,
                        disk_name,
                        args['format'],
                        args['size'],
                        args['pool']
                    )
                    define_vol_xml_str(vol_xml)

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

    if enable_vnc:
        salt.utils.versions.warn_until(
            'Sodium',
            '\'enable_vnc\' parameter has been deprecated in favor of '
            '\'graphics\'. Use graphics={\'type\': \'vnc\'} for the same behavior. '
            '\'enable_vnc\' will be removed in {version}. ')
        graphics = {'type': 'vnc'}

    vm_xml = _gen_xml(name, cpu, mem, diskp, nicp, hypervisor, graphics, **kwargs)
    conn = __get_conn(**kwargs)
    try:
        conn.defineXML(vm_xml)
    except libvirtError as err:
        # check if failure is due to this domain already existing
        if "domain '{}' already exists".format(name) in six.text_type(err):
            # continue on to seeding
            log.warning(err)
        else:
            conn.close()
            raise err  # a real error we should report upwards

    if start:
        log.debug('Starting VM %s', name)
        _get_domain(conn, name).create()
    conn.close()

    return True


def list_domains(**kwargs):
    '''
    Return a list of available domains.

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_domains
    '''
    vms = []
    conn = __get_conn(**kwargs)
    for dom in _get_domain(conn, iterable=True):
        vms.append(dom.name())
    conn.close()
    return vms


def list_active_vms(**kwargs):
    '''
    Return a list of names for active virtual machine on the minion

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_active_vms
    '''
    vms = []
    conn = __get_conn(**kwargs)
    for dom in _get_domain(conn, iterable=True, inactive=False):
        vms.append(dom.name())
    conn.close()
    return vms


def list_inactive_vms(**kwargs):
    '''
    Return a list of names for inactive virtual machine on the minion

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_inactive_vms
    '''
    vms = []
    conn = __get_conn(**kwargs)
    for dom in _get_domain(conn, iterable=True, active=False):
        vms.append(dom.name())
    conn.close()
    return vms


def vm_info(vm_=None, **kwargs):
    '''
    Return detailed information about the vms on this hyper in a
    list of dicts:

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

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
    def _info(dom):
        '''
        Compute the infos of a domain
        '''
        raw = dom.info()
        return {'cpu': raw[3],
                'cputime': int(raw[4]),
                'disks': _get_disks(dom),
                'graphics': _get_graphics(dom),
                'nics': _get_nics(dom),
                'uuid': _get_uuid(dom),
                'on_crash': _get_on_crash(dom),
                'on_reboot': _get_on_reboot(dom),
                'on_poweroff': _get_on_poweroff(dom),
                'maxMem': int(raw[1]),
                'mem': int(raw[2]),
                'state': VIRT_STATE_NAME_MAP.get(raw[0], 'unknown')}
    info = {}
    conn = __get_conn(**kwargs)
    if vm_:
        info[vm_] = _info(_get_domain(conn, vm_))
    else:
        for domain in _get_domain(conn, iterable=True):
            info[domain.name()] = _info(domain)
    conn.close()
    return info


def vm_state(vm_=None, **kwargs):
    '''
    Return list of all the vms and their state.

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_state <domain>
    '''
    def _info(dom):
        '''
        Compute domain state
        '''
        state = ''
        raw = dom.info()
        state = VIRT_STATE_NAME_MAP.get(raw[0], 'unknown')
        return state
    info = {}
    conn = __get_conn(**kwargs)
    if vm_:
        info[vm_] = _info(_get_domain(conn, vm_))
    else:
        for domain in _get_domain(conn, iterable=True):
            info[domain.name()] = _info(domain)
    conn.close()
    return info


def _node_info(conn):
    '''
    Internal variant of node_info taking a libvirt connection as parameter
    '''
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


def node_info(**kwargs):
    '''
    Return a dict with information about this node

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.node_info
    '''
    conn = __get_conn(**kwargs)
    info = _node_info(conn)
    conn.close()
    return info


def get_nics(vm_, **kwargs):
    '''
    Return info about the network interfaces of a named vm

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_nics <domain>
    '''
    conn = __get_conn(**kwargs)
    nics = _get_nics(_get_domain(conn, vm_))
    conn.close()
    return nics


def get_macs(vm_, **kwargs):
    '''
    Return a list off MAC addresses from the named vm

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_macs <domain>
    '''
    macs = []
    doc = minidom.parse(_StringIO(get_xml(vm_, **kwargs)))
    for node in doc.getElementsByTagName('devices'):
        i_nodes = node.getElementsByTagName('interface')
        for i_node in i_nodes:
            for v_node in i_node.getElementsByTagName('mac'):
                macs.append(v_node.getAttribute('address'))
    return macs


def get_graphics(vm_, **kwargs):
    '''
    Returns the information on vnc for a given vm

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_graphics <domain>
    '''
    conn = __get_conn(**kwargs)
    graphics = _get_graphics(_get_domain(conn, vm_))
    conn.close()
    return graphics


def get_disks(vm_, **kwargs):
    '''
    Return the disks of a named vm

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_disks <domain>
    '''
    conn = __get_conn(**kwargs)
    disks = _get_disks(_get_domain(conn, vm_))
    conn.close()
    return disks


def setmem(vm_, memory, config=False, **kwargs):
    '''
    Changes the amount of memory allocated to VM. The VM must be shutdown
    for this to work.

    :param vm_: name of the domain
    :param memory: memory amount to set in MB
    :param config: if True then libvirt will be asked to modify the config as well
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setmem <domain> <size>
        salt '*' virt.setmem my_domain 768
    '''
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)

    if VIRT_STATE_NAME_MAP.get(dom.info()[0], 'unknown') != 'shutdown':
        return False

    # libvirt has a funny bitwise system for the flags in that the flag
    # to affect the "current" setting is 0, which means that to set the
    # current setting we have to call it a second time with just 0 set
    flags = libvirt.VIR_DOMAIN_MEM_MAXIMUM
    if config:
        flags = flags | libvirt.VIR_DOMAIN_AFFECT_CONFIG

    ret1 = dom.setMemoryFlags(memory * 1024, flags)
    ret2 = dom.setMemoryFlags(memory * 1024, libvirt.VIR_DOMAIN_AFFECT_CURRENT)

    conn.close()

    # return True if both calls succeeded
    return ret1 == ret2 == 0


def setvcpus(vm_, vcpus, config=False, **kwargs):
    '''
    Changes the amount of vcpus allocated to VM. The VM must be shutdown
    for this to work.

    If config is True then we ask libvirt to modify the config as well

    :param vm_: name of the domain
    :param vcpus: integer representing the number of CPUs to be assigned
    :param config: if True then libvirt will be asked to modify the config as well
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setvcpus <domain> <amount>
        salt '*' virt.setvcpus my_domain 4
    '''
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)

    if VIRT_STATE_NAME_MAP.get(dom.info()[0], 'unknown') != 'shutdown':
        return False

    # see notes in setmem
    flags = libvirt.VIR_DOMAIN_VCPU_MAXIMUM
    if config:
        flags = flags | libvirt.VIR_DOMAIN_AFFECT_CONFIG

    ret1 = dom.setVcpusFlags(vcpus, flags)
    ret2 = dom.setVcpusFlags(vcpus, libvirt.VIR_DOMAIN_AFFECT_CURRENT)

    conn.close()

    return ret1 == ret2 == 0


def _freemem(conn):
    '''
    Internal variant of freemem taking a libvirt connection as parameter
    '''
    mem = conn.getInfo()[1]
    # Take off just enough to sustain the hypervisor
    mem -= 256
    for dom in _get_domain(conn, iterable=True):
        if dom.ID() > 0:
            mem -= dom.info()[2] / 1024
    return mem


def freemem(**kwargs):
    '''
    Return an int representing the amount of memory (in MB) that has not
    been given to virtual machines on this node

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.freemem
    '''
    conn = __get_conn(**kwargs)
    mem = _freemem(conn)
    conn.close()
    return mem


def _freecpu(conn):
    '''
    Internal variant of freecpu taking a libvirt connection as parameter
    '''
    cpus = conn.getInfo()[2]
    for dom in _get_domain(conn, iterable=True):
        if dom.ID() > 0:
            cpus -= dom.info()[3]
    return cpus


def freecpu(**kwargs):
    '''
    Return an int representing the number of unallocated cpus on this
    hypervisor

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.freecpu
    '''
    conn = __get_conn(**kwargs)
    cpus = _freecpu(conn)
    conn.close()
    return cpus


def full_info(**kwargs):
    '''
    Return the node_info, vm_info and freemem

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.full_info
    '''
    conn = __get_conn(**kwargs)
    info = {'freecpu': _freecpu(conn),
            'freemem': _freemem(conn),
            'node_info': _node_info(conn),
            'vm_info': vm_info()}
    conn.close()
    return info


def get_xml(vm_, **kwargs):
    '''
    Returns the XML for a given vm

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_xml <domain>
    '''
    conn = __get_conn(**kwargs)
    xml_desc = _get_domain(conn, vm_).XMLDesc(0)
    conn.close()
    return xml_desc


def get_profiles(hypervisor=None, **kwargs):
    '''
    Return the virt profiles for hypervisor.

    Currently there are profiles for:

    - nic
    - disk

    :param hypervisor: override the default machine type.
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_profiles
        salt '*' virt.get_profiles hypervisor=esxi
    '''
    ret = {}

    hypervisors = _get_domain_types(**kwargs)
    default_hypervisor = 'kvm' if 'kvm' in hypervisors else hypervisors[0]

    if not hypervisor:
        hypervisor = __salt__['config.get']('libvirt:hypervisor')
        if hypervisor is not None:
            salt.utils.versions.warn_until(
                'Sodium',
                '\'libvirt:hypervisor\' configuration property has been deprecated. '
                'Rather use the \'virt:connection:uri\' to properly define the libvirt '
                'URI or alias of the host to connect to. \'libvirt:hypervisor\' will '
                'stop being used in {version}.'
            )
        else:
            # Use the machine types as possible values
            # Prefer 'kvm' over the others if available
            hypervisor = default_hypervisor
    virtconf = __salt__['config.get']('virt', {})
    for typ in ['disk', 'nic']:
        _func = getattr(sys.modules[__name__], '_{0}_profile'.format(typ))
        ret[typ] = {'default': _func('default', hypervisor)}
        if typ in virtconf:
            ret.setdefault(typ, {})
            for prf in virtconf[typ]:
                ret[typ][prf] = _func(prf, hypervisor)
    return ret


def shutdown(vm_, **kwargs):
    '''
    Send a soft shutdown signal to the named vm

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.shutdown <domain>
    '''
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    ret = dom.shutdown() == 0
    conn.close()
    return ret


def pause(vm_, **kwargs):
    '''
    Pause the named vm

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pause <domain>
    '''
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    ret = dom.suspend() == 0
    conn.close()
    return ret


def resume(vm_, **kwargs):
    '''
    Resume the named vm

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.resume <domain>
    '''
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    ret = dom.resume() == 0
    conn.close()
    return ret


def start(name, **kwargs):
    '''
    Start a defined domain

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.start <domain>
    '''
    conn = __get_conn(**kwargs)
    ret = _get_domain(conn, name).create() == 0
    conn.close()
    return ret


def stop(name, **kwargs):
    '''
    Hard power down the virtual machine, this is equivalent to pulling the power.

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.stop <domain>
    '''
    conn = __get_conn(**kwargs)
    ret = _get_domain(conn, name).destroy() == 0
    conn.close()
    return ret


def reboot(name, **kwargs):
    '''
    Reboot a domain via ACPI request

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reboot <domain>
    '''
    conn = __get_conn(**kwargs)
    ret = _get_domain(conn, name).reboot(libvirt.VIR_DOMAIN_REBOOT_DEFAULT) == 0
    conn.close()
    return ret


def reset(vm_, **kwargs):
    '''
    Reset a VM by emulating the reset button on a physical machine

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reset <domain>
    '''
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)

    # reset takes a flag, like reboot, but it is not yet used
    # so we just pass in 0
    # see: http://libvirt.org/html/libvirt-libvirt.html#virDomainReset
    ret = dom.reset(0) == 0
    conn.close()
    return ret


def ctrl_alt_del(vm_, **kwargs):
    '''
    Sends CTRL+ALT+DEL to a VM

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.ctrl_alt_del <domain>
    '''
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    ret = dom.sendKey(0, 0, [29, 56, 111], 3, 0) == 0
    conn.close()
    return ret


def create_xml_str(xml, **kwargs):  # pylint: disable=redefined-outer-name
    '''
    Start a domain based on the XML passed to the function

    :param xml: libvirt XML definition of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.create_xml_str <XML in string format>
    '''
    conn = __get_conn(**kwargs)
    ret = conn.createXML(xml, 0) is not None
    conn.close()
    return ret


def create_xml_path(path, **kwargs):
    '''
    Start a domain based on the XML-file path passed to the function

    :param path: path to a file containing the libvirt XML definition of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.create_xml_path <path to XML file on the node>
    '''
    try:
        with salt.utils.files.fopen(path, 'r') as fp_:
            return create_xml_str(
                salt.utils.stringutils.to_unicode(fp_.read()),
                **kwargs
            )
    except (OSError, IOError):
        return False


def define_xml_str(xml, **kwargs):  # pylint: disable=redefined-outer-name
    '''
    Define a domain based on the XML passed to the function

    :param xml: libvirt XML definition of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_xml_str <XML in string format>
    '''
    conn = __get_conn(**kwargs)
    ret = conn.defineXML(xml) is not None
    conn.close()
    return ret


def define_xml_path(path, **kwargs):
    '''
    Define a domain based on the XML-file path passed to the function

    :param path: path to a file containing the libvirt XML definition of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_xml_path <path to XML file on the node>

    '''
    try:
        with salt.utils.files.fopen(path, 'r') as fp_:
            return define_xml_str(
                salt.utils.stringutils.to_unicode(fp_.read()),
                **kwargs
            )
    except (OSError, IOError):
        return False


def define_vol_xml_str(xml, **kwargs):  # pylint: disable=redefined-outer-name
    '''
    Define a volume based on the XML passed to the function

    :param xml: libvirt XML definition of the storage volume
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_vol_xml_str <XML in string format>

    The storage pool where the disk image will be defined is ``default``
    unless changed with a configuration like this:

    .. code-block:: yaml

        virt:
            storagepool: mine
    '''
    poolname = __salt__['config.get']('libvirt:storagepool', None)
    if poolname is not None:
        salt.utils.versions.warn_until(
            'Sodium',
            '\'libvirt:storagepool\' has been deprecated in favor of '
            '\'virt:storagepool\'. \'libvirt:storagepool\' will stop '
            'being used in {version}.'
        )
    else:
        poolname = __salt__['config.get']('virt:storagepool', 'default')

    conn = __get_conn(**kwargs)
    pool = conn.storagePoolLookupByName(six.text_type(poolname))
    ret = pool.createXML(xml, 0) is not None
    conn.close()
    return ret


def define_vol_xml_path(path, **kwargs):
    '''
    Define a volume based on the XML-file path passed to the function

    :param path: path to a file containing the libvirt XML definition of the volume
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_vol_xml_path <path to XML file on the node>

    '''
    try:
        with salt.utils.files.fopen(path, 'r') as fp_:
            return define_vol_xml_str(
                salt.utils.stringutils.to_unicode(fp_.read()),
                **kwargs
            )
    except (OSError, IOError):
        return False


def migrate_non_shared(vm_, target, ssh=False):
    '''
    Attempt to execute non-shared storage "all" migration

    :param vm_: domain name
    :param target: target libvirt host name
    :param ssh: True to connect over ssh

    CLI Example:

    .. code-block:: bash

        salt '*' virt.migrate_non_shared <vm name> <target hypervisor>

    A tunnel data migration can be performed by setting this in the
    configuration:

    .. code-block:: yaml

        virt:
            tunnel: True

    For more details on tunnelled data migrations, report to
    https://libvirt.org/migration.html#transporttunnel
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

    :param vm_: domain name
    :param target: target libvirt host name
    :param ssh: True to connect over ssh

    CLI Example:

    .. code-block:: bash

        salt '*' virt.migrate_non_shared_inc <vm name> <target hypervisor>

    A tunnel data migration can be performed by setting this in the
    configuration:

    .. code-block:: yaml

        virt:
            tunnel: True

    For more details on tunnelled data migrations, report to
    https://libvirt.org/migration.html#transporttunnel
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

    :param vm_: domain name
    :param target: target libvirt host name
    :param ssh: True to connect over ssh

    CLI Example:

    .. code-block:: bash

        salt '*' virt.migrate <domain> <target hypervisor>

    A tunnel data migration can be performed by setting this in the
    configuration:

    .. code-block:: yaml

        virt:
            tunnel: True

    For more details on tunnelled data migrations, report to
    https://libvirt.org/migration.html#transporttunnel
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

    :param disks: the list of disk data as provided by virt.get_disks
    :param force: skip checking the compatibility of source and target disk
                  images if True. (default: False)

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


def set_autostart(vm_, state='on', **kwargs):
    '''
    Set the autostart flag on a VM so that the VM will start with the host
    system on reboot.

    :param vm_: domain name
    :param state: 'on' to auto start the pool, anything else to mark the
                  pool not to be started when the host boots
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt "*" virt.set_autostart <domain> <on | off>
    '''
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)

    # return False if state is set to something other then on or off
    ret = False

    if state == 'on':
        ret = dom.setAutostart(1) == 0

    elif state == 'off':
        ret = dom.setAutostart(0) == 0

    conn.close()
    return ret


def undefine(vm_, **kwargs):
    '''
    Remove a defined vm, this does not purge the virtual machine image, and
    this only works if the vm is powered down

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.undefine <domain>
    '''
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    if getattr(libvirt, 'VIR_DOMAIN_UNDEFINE_NVRAM', False):
        # This one is only in 1.2.8+
        ret = dom.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_NVRAM) == 0
    else:
        ret = dom.undefine() == 0
    conn.close()
    return ret


def purge(vm_, dirs=False, removables=None, **kwargs):
    '''
    Recursively destroy and delete a virtual machine, pass True for dir's to
    also delete the directories containing the virtual machine disk images -
    USE WITH EXTREME CAUTION!

    Pass removables=False to avoid deleting cdrom and floppy images. To avoid
    disruption, the default but dangerous value is True. This will be changed
    to the safer False default value in Sodium.

    :param vm_: domain name
    :param dirs: pass True to remove containing directories
    :param removables: pass True to remove removable devices

        .. versionadded:: Fluorine
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.purge <domain> removables=False
    '''
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    disks = _get_disks(dom)
    if removables is None:
        salt.utils.versions.warn_until(
            'Sodium',
            'removables argument default value is True, but will be changed '
            'to False by default in {version}. Please set to True to maintain '
            'the current behavior in the future.'
        )
        removables = True
    if VIRT_STATE_NAME_MAP.get(dom.info()[0], 'unknown') != 'shutdown' and dom.destroy() != 0:
        return False
    directories = set()
    for disk in disks:
        if not removables and disks[disk]['type'] in ['cdrom', 'floppy']:
            continue
        os.remove(disks[disk]['file'])
        directories.add(os.path.dirname(disks[disk]['file']))
    if dirs:
        for dir_ in directories:
            shutil.rmtree(dir_)
    if getattr(libvirt, 'VIR_DOMAIN_UNDEFINE_NVRAM', False):
        # This one is only in 1.2.8+
        dom.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)
    else:
        dom.undefine()
    conn.close()
    return True


def virt_type():
    '''
    Returns the virtual machine type as a string

    CLI Example:

    .. code-block:: bash

        salt '*' virt.virt_type
    '''
    return __grains__['virtual']


def _is_kvm_hyper():
    '''
    Returns a bool whether or not this node is a KVM hypervisor
    '''
    try:
        with salt.utils.files.fopen('/proc/modules') as fp_:
            if 'kvm_' not in salt.utils.stringutils.to_unicode(fp_.read()):
                return False
    except IOError:
        # No /proc/modules? Are we on Windows? Or Solaris?
        return False
    return 'libvirtd' in __salt__['cmd.run'](__grains__['ps'])


def is_kvm_hyper():
    '''
    Returns a bool whether or not this node is a KVM hypervisor

    CLI Example:

    .. code-block:: bash

        salt '*' virt.is_kvm_hyper

    .. deprecated:: Fluorine
    '''
    salt.utils.versions.warn_until(
        'Sodium',
        '\'is_kvm_hyper\' function has been deprecated. Use the \'get_hypervisor\' == "kvm" instead. '
        '\'is_kvm_hyper\' will be removed in {version}.'
    )
    return _is_kvm_hyper()


def _is_xen_hyper():
    '''
    Returns a bool whether or not this node is a XEN hypervisor
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


def is_xen_hyper():
    '''
    Returns a bool whether or not this node is a XEN hypervisor

    CLI Example:

    .. code-block:: bash

        salt '*' virt.is_xen_hyper

    .. deprecated:: Fluorine
    '''
    salt.utils.versions.warn_until(
        'Sodium',
        '\'is_xen_hyper\' function has been deprecated. Use the \'get_hypervisor\' == "xen" instead. '
        '\'is_xen_hyper\' will be removed in {version}.'
    )
    return _is_xen_hyper()


def get_hypervisor():
    '''
    Returns the name of the hypervisor running on this node or ``None``.

    Detected hypervisors:

    - kvm
    - xen

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_hypervisor

    .. versionadded:: Fluorine
        the function and the ``kvm`` and ``xen`` hypervisors support
    '''
    # To add a new 'foo' hypervisor, add the _is_foo_hyper function,
    # add 'foo' to the list below and add it to the docstring with a .. versionadded::
    hypervisors = ['kvm', 'xen']
    result = [hyper for hyper in hypervisors if getattr(sys.modules[__name__], '_is_{}_hyper').format(hyper)()]
    return result[0] if result else None


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


def vm_cputime(vm_=None, **kwargs):
    '''
    Return cputime used by the vms on this hyper in a
    list of dicts:

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

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
    conn = __get_conn(**kwargs)
    host_cpus = conn.getInfo()[2]

    def _info(dom):
        '''
        Compute cputime info of a domain
        '''
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
        info[vm_] = _info(_get_domain(conn, vm_))
    else:
        for domain in _get_domain(conn, iterable=True):
            info[domain.name()] = _info(domain)
    conn.close()
    return info


def vm_netstats(vm_=None, **kwargs):
    '''
    Return combined network counters used by the vms on this hyper in a
    list of dicts:

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

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
    def _info(dom):
        '''
        Compute network stats of a domain
        '''
        nics = _get_nics(dom)
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
    conn = __get_conn(**kwargs)
    if vm_:
        info[vm_] = _info(_get_domain(conn, vm_))
    else:
        for domain in _get_domain(conn, iterable=True):
            info[domain.name()] = _info(domain)
    conn.close()
    return info


def vm_diskstats(vm_=None, **kwargs):
    '''
    Return disk usage counters used by the vms on this hyper in a
    list of dicts:

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

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
    def get_disk_devs(dom):
        '''
        Extract the disk devices names from the domain XML definition
        '''
        doc = minidom.parse(_StringIO(dom.XMLDesc(0)))
        disks = []
        for elem in doc.getElementsByTagName('disk'):
            targets = elem.getElementsByTagName('target')
            target = targets[0]
            disks.append(target.getAttribute('dev'))
        return disks

    def _info(dom):
        '''
        Compute the disk stats of a domain
        '''
        # Do not use get_disks, since it uses qemu-img and is very slow
        # and unsuitable for any sort of real time statistics
        disks = get_disk_devs(dom)
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
    conn = __get_conn(**kwargs)
    if vm_:
        info[vm_] = _info(_get_domain(conn, vm_))
    else:
        # Can not run function blockStats on inactive VMs
        for domain in _get_domain(conn, iterable=True, inactive=False):
            info[domain.name()] = _info(domain)
    conn.close()
    return info


def _parse_snapshot_description(vm_snapshot, unix_time=False):
    '''
    Parse XML doc and return a dict with the status values.

    :param xmldoc:
    :return:
    '''
    ret = dict()
    tree = ElementTree.fromstring(vm_snapshot.getXMLDesc())
    for node in tree:
        if node.tag == 'name':
            ret['name'] = node.text
        elif node.tag == 'creationTime':
            ret['created'] = datetime.datetime.fromtimestamp(float(node.text)).isoformat(' ') \
                                if not unix_time else float(node.text)
        elif node.tag == 'state':
            ret['running'] = node.text == 'running'

    ret['current'] = vm_snapshot.isCurrent() == 1

    return ret


def list_snapshots(domain=None, **kwargs):
    '''
    List available snapshots for certain vm or for all.

    :param domain: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_snapshots
        salt '*' virt.list_snapshots <domain>
    '''
    ret = dict()
    conn = __get_conn(**kwargs)
    for vm_domain in _get_domain(conn, *(domain and [domain] or list()), iterable=True):
        ret[vm_domain.name()] = [_parse_snapshot_description(snap) for snap in vm_domain.listAllSnapshots()] or 'N/A'

    conn.close()
    return ret


def snapshot(domain, name=None, suffix=None, **kwargs):
    '''
    Create a snapshot of a VM.

    :param domain: domain name
    :param name: Name of the snapshot. If the name is omitted, then will be used original domain
                 name with ISO 8601 time as a suffix.

    :param suffix: Add suffix for the new name. Useful in states, where such snapshots
                   can be distinguished from manually created.
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

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

    conn = __get_conn(**kwargs)
    _get_domain(conn, domain).snapshotCreateXML(ElementTree.tostring(doc))
    conn.close()

    return {'name': name}


def delete_snapshots(name, *names, **kwargs):
    '''
    Delete one or more snapshots of the given VM.

    :param name: domain name
    :param names: names of the snapshots to remove
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.delete_snapshots <domain> all=True
        salt '*' virt.delete_snapshots <domain> <snapshot>
        salt '*' virt.delete_snapshots <domain> <snapshot1> <snapshot2> ...
    '''
    deleted = dict()
    conn = __get_conn(**kwargs)
    domain = _get_domain(conn, name)
    for snap in domain.listAllSnapshots():
        if snap.getName() in names or not names:
            deleted[snap.getName()] = _parse_snapshot_description(snap)
            snap.delete()
    conn.close()

    available = {name: [_parse_snapshot_description(snap) for snap in domain.listAllSnapshots()] or 'N/A'}

    return {'available': available, 'deleted': deleted}


def revert_snapshot(name, vm_snapshot=None, cleanup=False, **kwargs):
    '''
    Revert snapshot to the previous from current (if available) or to the specific.

    :param name: domain name
    :param vm_snapshot: name of the snapshot to revert
    :param cleanup: Remove all newer than reverted snapshots. Values: True or False (default False).
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.revert <domain>
        salt '*' virt.revert <domain> <snapshot>
    '''
    ret = dict()
    conn = __get_conn(**kwargs)
    domain = _get_domain(conn, name)
    snapshots = domain.listAllSnapshots()

    _snapshots = list()
    for snap_obj in snapshots:
        _snapshots.append({'idx': _parse_snapshot_description(snap_obj, unix_time=True)['created'], 'ptr': snap_obj})
    snapshots = [w_ptr['ptr'] for w_ptr in sorted(_snapshots, key=lambda item: item['idx'], reverse=True)]
    del _snapshots

    if not snapshots:
        conn.close()
        raise CommandExecutionError('No snapshots found')
    elif len(snapshots) == 1:
        conn.close()
        raise CommandExecutionError('Cannot revert to itself: only one snapshot is available.')

    snap = None
    for p_snap in snapshots:
        if not vm_snapshot:
            if p_snap.isCurrent() and snapshots[snapshots.index(p_snap) + 1:]:
                snap = snapshots[snapshots.index(p_snap) + 1:][0]
                break
        elif p_snap.getName() == vm_snapshot:
            snap = p_snap
            break

    if not snap:
        conn.close()
        raise CommandExecutionError(
            snapshot and 'Snapshot "{0}" not found'.format(vm_snapshot) or 'No more previous snapshots available')
    elif snap.isCurrent():
        conn.close()
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

    conn.close()

    return ret


def _capabilities(conn):
    '''
    Return connection capabilities as XML.
    '''
    caps = conn.getCapabilities()
    caps = minidom.parseString(caps)

    return caps


def _get_xml_first_element_by_tag_name(node, name):  # pylint: disable=invalid-name
    '''
    Convenience function getting the first result of getElementsByTagName() or None.
    '''
    nodes = node.getElementsByTagName(name)
    return nodes[0] if nodes else None


def _get_xml_element_text(node):
    '''
    Get the text value of an XML element.
    '''
    return "".join([child.data for child in node.childNodes if child.nodeType == xml.dom.Node.TEXT_NODE])


def _get_xml_child_text(node, name, default):
    '''
    Get the text value of the child named name of XML element node
    '''
    result = "".join([_get_xml_element_text(child) for child in node.childNodes
                      if child.nodeType == xml.dom.Node.ELEMENT_NODE and child.tagName == name])
    return result if result else default


def _caps_add_machine(machines, node):
    '''
    Parse the <machine> element of the host capabilities and add it
    to the machines list.
    '''
    maxcpus = node.getAttribute('maxCpus')
    canonical = node.getAttribute('canonical')
    name = _get_xml_element_text(node)

    alternate_name = ""
    if canonical:
        alternate_name = name
        name = canonical

    machine = machines.get(name)
    if not machine:
        machine = {'alternate_names': []}
        if maxcpus:
            machine['maxcpus'] = int(maxcpus)
        machines[name] = machine
    if alternate_name:
        machine['alternate_names'].append(alternate_name)


def _parse_caps_guest(guest):
    '''
    Parse the <guest> element of the connection capabilities XML
    '''
    arch_node = _get_xml_first_element_by_tag_name(guest, 'arch')
    result = {
        'os_type': _get_xml_element_text(guest.getElementsByTagName('os_type')[0]),
        'arch': {
            'name': arch_node.getAttribute('name'),
            'machines': {},
            'domains': {}
        },
    }

    for child in arch_node.childNodes:
        if child.nodeType != xml.dom.Node.ELEMENT_NODE:
            continue
        if child.tagName == 'wordsize':
            result['arch']['wordsize'] = int(_get_xml_element_text(child))
        elif child.tagName == 'emulator':
            result['arch']['emulator'] = _get_xml_element_text(child)
        elif child.tagName == 'machine':
            _caps_add_machine(result['arch']['machines'], child)
        elif child.tagName == 'domain':
            domain_type = child.getAttribute('type')
            domain = {
                'emulator': None,
                'machines': {}
            }
            emulator_node = _get_xml_first_element_by_tag_name(child, 'emulator')
            if emulator_node:
                domain['emulator'] = _get_xml_element_text(emulator_node)
            for machine in child.getElementsByTagName('machine'):
                _caps_add_machine(domain['machines'], machine)
            result['arch']['domains'][domain_type] = domain

    # Note that some features have no default and toggle attributes.
    # This may not be a perfect match, but represent them as enabled by default
    # without possibility to toggle them.
    features_node = _get_xml_first_element_by_tag_name(guest, 'features')
    result['features'] = {child.tagName: {'toggle': True if child.getAttribute('toggle') == 'yes' else False,
                                          'default': True if child.getAttribute('default') == 'no' else True}
                          for child in features_node.childNodes if child.nodeType == xml.dom.Node.ELEMENT_NODE}

    return result


def _parse_caps_cell(cell):
    '''
    Parse the <cell> nodes of the connection capabilities XML output.
    '''
    result = {
        'id': int(cell.getAttribute('id'))
    }

    mem_node = _get_xml_first_element_by_tag_name(cell, 'memory')
    if mem_node:
        unit = mem_node.getAttribute('unit') if mem_node.hasAttribute('unit') else 'KiB'
        memory = _get_xml_element_text(mem_node)
        result['memory'] = "{} {}".format(memory, unit)

    pages = [{'size': "{} {}".format(page.getAttribute('size'),
                                     page.getAttribute('unit') if page.getAttribute('unit') else 'KiB'),
              'available': int(_get_xml_element_text(page))}
             for page in cell.getElementsByTagName('pages')]
    if pages:
        result['pages'] = pages

    distances = {int(distance.getAttribute('id')): int(distance.getAttribute('value'))
                 for distance in cell.getElementsByTagName('sibling')}
    if distances:
        result['distances'] = distances

    cpus = []
    for cpu_node in cell.getElementsByTagName('cpu'):
        cpu = {
            'id': int(cpu_node.getAttribute('id'))
        }
        socket_id = cpu_node.getAttribute('socket_id')
        if socket_id:
            cpu['socket_id'] = int(socket_id)

        core_id = cpu_node.getAttribute('core_id')
        if core_id:
            cpu['core_id'] = int(core_id)
        siblings = cpu_node.getAttribute('siblings')
        if siblings:
            cpu['siblings'] = siblings
        cpus.append(cpu)
    if cpus:
        result['cpus'] = cpus

    return result


def _parse_caps_bank(bank):
    '''
    Parse the <bank> element of the connection capabilities XML.
    '''
    result = {
        'id': int(bank.getAttribute('id')),
        'level': int(bank.getAttribute('level')),
        'type': bank.getAttribute('type'),
        'size': "{} {}".format(bank.getAttribute('size'), bank.getAttribute('unit')),
        'cpus': bank.getAttribute('cpus')
    }

    controls = []
    for control in bank.getElementsByTagName('control'):
        unit = control.getAttribute('unit')
        result_control = {
            'granularity': "{} {}".format(control.getAttribute('granularity'), unit),
            'type': control.getAttribute('type'),
            'maxAllocs': int(control.getAttribute('maxAllocs'))
        }

        minimum = control.getAttribute('min')
        if minimum:
            result_control['min'] = "{} {}".format(minimum, unit)
        controls.append(result_control)
    if controls:
        result['controls'] = controls

    return result


def _parse_caps_host(host):
    '''
    Parse the <host> element of the connection capabilities XML.
    '''
    result = {}
    for child in host.childNodes:
        if child.nodeType != xml.dom.Node.ELEMENT_NODE:
            continue

        if child.tagName == 'uuid':
            result['uuid'] = _get_xml_element_text(child)

        elif child.tagName == 'cpu':
            cpu = {
                'arch': _get_xml_child_text(child, 'arch', None),
                'model': _get_xml_child_text(child, 'model', None),
                'vendor': _get_xml_child_text(child, 'vendor', None),
                'features': [feature.getAttribute('name') for feature in child.getElementsByTagName('feature')],
                'pages': [{'size': '{} {}'.format(page.getAttribute('size'),
                                                  page.getAttribute('unit') if page.hasAttribute('unit') else 'KiB')}
                          for page in child.getElementsByTagName('pages')]
            }
            # Parse the cpu tag
            microcode = _get_xml_first_element_by_tag_name(child, 'microcode')
            if microcode:
                cpu['microcode'] = microcode.getAttribute('version')

            topology = _get_xml_first_element_by_tag_name(child, 'topology')
            if topology:
                cpu['sockets'] = int(topology.getAttribute('sockets'))
                cpu['cores'] = int(topology.getAttribute('cores'))
                cpu['threads'] = int(topology.getAttribute('threads'))
            result['cpu'] = cpu

        elif child.tagName == "power_management":
            result['power_management'] = [node.tagName for node in child.childNodes
                                          if node.nodeType == xml.dom.Node.ELEMENT_NODE]

        elif child.tagName == "migration_features":
            result['migration'] = {
                'live': bool(child.getElementsByTagName('live')),
                'transports': [_get_xml_element_text(node) for node in child.getElementsByTagName('uri_transport')]
            }

        elif child.tagName == "topology":
            result['topology'] = {
                'cells': [_parse_caps_cell(cell) for cell in child.getElementsByTagName('cell')]
            }

        elif child.tagName == 'cache':
            result['cache'] = {
                'banks': [_parse_caps_bank(bank) for bank in child.getElementsByTagName('bank')]
            }

    result['security'] = [{
            'model': _get_xml_child_text(secmodel, 'model', None),
            'doi': _get_xml_child_text(secmodel, 'doi', None),
            'baselabels': [{'type': label.getAttribute('type'), 'label': _get_xml_element_text(label)}
                           for label in secmodel.getElementsByTagName('baselabel')]
        }
        for secmodel in host.getElementsByTagName('secmodel')]

    return result


def capabilities(**kwargs):
    '''
    Return the hypervisor connection capabilities.

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.capabilities
    '''
    conn = __get_conn(**kwargs)
    caps = _capabilities(conn)
    conn.close()

    return {
        'host': _parse_caps_host(caps.getElementsByTagName('host')[0]),
        'guests': [_parse_caps_guest(guest) for guest in caps.getElementsByTagName('guest')]
    }


def _parse_caps_enum(node):
    '''
    Return a tuple containing the name of the enum and the possible values
    '''
    return (node.getAttribute('name') or None,
            [_get_xml_element_text(value) for value in node.getElementsByTagName('value')])


def _parse_caps_cpu(node):
    '''
    Parse the <cpu> element of the domain capabilities
    '''
    result = {}
    for mode in node.getElementsByTagName('mode'):
        if not mode.getAttribute('supported') == 'yes':
            continue

        name = mode.getAttribute('name')
        if name == 'host-passthrough':
            result[name] = True

        elif name == 'host-model':
            host_model = {}
            model_node = _get_xml_first_element_by_tag_name(mode, 'model')
            if model_node:
                model = {
                    'name': _get_xml_element_text(model_node)
                }

                vendor_id = model_node.getAttribute('vendor_id')
                if vendor_id:
                    model['vendor_id'] = vendor_id

                fallback = model_node.getAttribute('fallback')
                if fallback:
                    model['fallback'] = fallback
                host_model['model'] = model

            vendor = _get_xml_child_text(mode, 'vendor', None)
            if vendor:
                host_model['vendor'] = vendor

            features = {feature.getAttribute('name'): feature.getAttribute('policy')
                        for feature in mode.getElementsByTagName('feature')}
            if features:
                host_model['features'] = features

            result[name] = host_model

        elif name == 'custom':
            custom_model = {}
            models = {_get_xml_element_text(model): model.getAttribute('usable')
                      for model in mode.getElementsByTagName('model')}
            if models:
                custom_model['models'] = models
            result[name] = custom_model

    return result


def _parse_caps_devices_features(node):
    '''
    Parse the devices or features list of the domain capatilities
    '''
    result = {}
    for child in node.childNodes:
        if child.nodeType != xml.dom.Node.ELEMENT_NODE or not child.getAttribute('supported') == 'yes':
            continue
        enums = [_parse_caps_enum(node) for node in child.getElementsByTagName('enum')]
        result[child.tagName] = {item[0]: item[1] for item in enums if item[0]}
    return result


def _parse_caps_loader(node):
    '''
    Parse the <loader> element of the domain capabilities.
    '''
    enums = [_parse_caps_enum(enum) for enum in node.getElementsByTagName('enum')]
    result = {item[0]: item[1] for item in enums if item[0]}

    values = [_get_xml_element_text(child) for child in node.childNodes
              if child.nodeType == xml.dom.Node.ELEMENT_NODE and child.tagName == 'value']

    if values:
        result['values'] = values

    return result


def domain_capabilities(emulator=None, arch=None, machine=None, domain=None, **kwargs):
    '''
    Return the domain capabilities given an emulator, architecture, machine or virtualization type.

    .. versionadded:: Fluorine

    :param emulator: return the capabilities for the given emulator binary
    :param arch: return the capabilities for the given CPU architecture
    :param machine: return the capabilities for the given emulated machine type
    :param domain: return the capabilities for the given virtualization type.
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    The list of the possible emulator, arch, machine and domain can be found in
    the host capabilities output.

    If none of the parameters is provided the libvirt default domain capabilities
    will be returned.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.domain_capabilities arch='x86_64' domain='kvm'

    '''
    conn = __get_conn(**kwargs)
    caps = conn.getDomainCapabilities(emulator, arch, machine, domain, 0)
    caps = minidom.parseString(caps)
    conn.close()

    root_node = caps.getElementsByTagName('domainCapabilities')[0]

    result = {
        'emulator': _get_xml_child_text(root_node, 'path', None),
        'domain': _get_xml_child_text(root_node, 'domain', None),
        'machine': _get_xml_child_text(root_node, 'machine', None),
        'arch': _get_xml_child_text(root_node, 'arch', None)
    }

    for child in root_node.childNodes:
        if child.nodeType != xml.dom.Node.ELEMENT_NODE:
            continue

        if child.tagName == 'vcpu' and child.getAttribute('max'):
            result['max_vcpus'] = int(child.getAttribute('max'))

        elif child.tagName == 'iothreads':
            iothreads = child.getAttribute('supported') == 'yes'
            if iothreads is not None:
                result['iothreads'] = iothreads

        elif child.tagName == 'os':
            result['os'] = {}
            loader_node = _get_xml_first_element_by_tag_name(child, 'loader')
            if loader_node and loader_node.getAttribute('supported') == 'yes':
                loader = _parse_caps_loader(loader_node)
                result['os']['loader'] = loader

        elif child.tagName == 'cpu':
            cpu = _parse_caps_cpu(child)
            if cpu:
                result['cpu'] = cpu

        elif child.tagName == 'devices':
            devices = _parse_caps_devices_features(child)
            if devices:
                result['devices'] = devices

        elif child.tagName == 'features':
            features = _parse_caps_devices_features(child)
            if features:
                result['features'] = features

    return result


def cpu_baseline(full=False, migratable=False, out='libvirt', **kwargs):
    '''
    Return the optimal 'custom' CPU baseline config for VM's on this minion

    .. versionadded:: 2016.3.0

    :param full: Return all CPU features rather than the ones on top of the closest CPU model
    :param migratable: Exclude CPU features that are unmigratable (libvirt 2.13+)
    :param out: 'libvirt' (default) for usable libvirt XML definition, 'salt' for nice dict
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: Fluorine
    :param username: username to connect with, overriding defaults

        .. versionadded:: Fluorine
    :param password: password to connect with, overriding defaults

        .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.cpu_baseline

    '''
    conn = __get_conn(**kwargs)
    caps = _capabilities(conn)

    cpu = caps.getElementsByTagName('host')[0].getElementsByTagName('cpu')[0]

    log.debug('Host CPU model definition: %s', cpu.toxml())

    flags = 0
    if migratable:
        # This one is only in 1.2.14+
        if getattr(libvirt, 'VIR_CONNECT_BASELINE_CPU_MIGRATABLE', False):
            flags += libvirt.VIR_CONNECT_BASELINE_CPU_MIGRATABLE
        else:
            conn.close()
            raise ValueError

    if full and getattr(libvirt, 'VIR_CONNECT_BASELINE_CPU_EXPAND_FEATURES', False):
        # This one is only in 1.1.3+
        flags += libvirt.VIR_CONNECT_BASELINE_CPU_EXPAND_FEATURES

    cpu = conn.baselineCPU([cpu.toxml()], flags)
    cpu = minidom.parseString(cpu).getElementsByTagName('cpu')
    cpu = cpu[0]
    conn.close()

    if full and not getattr(libvirt, 'VIR_CONNECT_BASELINE_CPU_EXPAND_FEATURES', False):
        # Try do it by ourselves
        # Find the models in cpu_map.xml and iterate over them for as long as entries have submodels
        with salt.utils.files.fopen('/usr/share/libvirt/cpu_map.xml', 'r') as cpu_map:
            cpu_map = minidom.parse(cpu_map)

        cpu_model = cpu.getElementsByTagName('model')[0].childNodes[0].nodeValue
        while cpu_model:
            cpu_map_models = cpu_map.getElementsByTagName('model')
            cpu_specs = [el for el in cpu_map_models if el.getAttribute('name') == cpu_model and el.hasChildNodes()]

            if not cpu_specs:
                raise ValueError('Model {0} not found in CPU map'.format(cpu_model))
            elif len(cpu_specs) > 1:
                raise ValueError('Multiple models {0} found in CPU map'.format(cpu_model))

            cpu_specs = cpu_specs[0]

            cpu_model = cpu_specs.getElementsByTagName('model')
            if not cpu_model:
                cpu_model = None
            else:
                cpu_model = cpu_model[0].getAttribute('name')

            for feature in cpu_specs.getElementsByTagName('feature'):
                cpu.appendChild(feature)

    if out == 'salt':
        return {
            'model': cpu.getElementsByTagName('model')[0].childNodes[0].nodeValue,
            'vendor': cpu.getElementsByTagName('vendor')[0].childNodes[0].nodeValue,
            'features': [feature.getAttribute('name') for feature in cpu.getElementsByTagName('feature')]
        }
    return cpu.toxml()


def net_define(name, bridge, forward, **kwargs):
    '''
    Create libvirt network.

    :param name: Network name
    :param bridge: Bridge name
    :param forward: Forward mode(bridge, router, nat)
    :param vport: Virtualport type
    :param tag: Vlan tag
    :param autostart: Network autostart (default True)
    :param start: Network start (default True)
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    CLI Example:

    .. code-block:: bash

        salt '*' virt.net_define network main bridge openvswitch

    .. versionadded:: Fluorine
    '''
    conn = __get_conn(**kwargs)
    vport = kwargs.get('vport', None)
    tag = kwargs.get('tag', None)
    autostart = kwargs.get('autostart', True)
    starting = kwargs.get('start', True)
    net_xml = _gen_net_xml(
        name,
        bridge,
        forward,
        vport,
        tag,
    )
    try:
        conn.networkDefineXML(net_xml)
    except libvirtError as err:
        log.warning(err)
        conn.close()
        raise err  # a real error we should report upwards

    try:
        network = conn.networkLookupByName(name)
    except libvirtError as err:
        log.warning(err)
        conn.close()
        raise err  # a real error we should report upwards

    if network is None:
        conn.close()
        return False

    if (starting is True or autostart is True) and network.isActive() != 1:
        network.create()

    if autostart is True and network.autostart() != 1:
        network.setAutostart(int(autostart))
    elif autostart is False and network.autostart() == 1:
        network.setAutostart(int(autostart))

    conn.close()

    return True


def list_networks(**kwargs):
    '''
    List all virtual networks.

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

       salt '*' virt.list_networks
    '''
    conn = __get_conn(**kwargs)
    try:
        return [net.name() for net in conn.listAllNetworks()]
    finally:
        conn.close()


def network_info(name, **kwargs):
    '''
    Return informations on a virtual network provided its name.

    :param name: virtual network name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.network_info default
    '''
    result = {}
    conn = __get_conn(**kwargs)
    try:
        net = conn.networkLookupByName(name)
        leases = net.DHCPLeases()
        for lease in leases:
            if lease['type'] == libvirt.VIR_IP_ADDR_TYPE_IPV4:
                lease['type'] = 'ipv4'
            elif lease['type'] == libvirt.VIR_IP_ADDR_TYPE_IPV6:
                lease['type'] = 'ipv6'
            else:
                lease['type'] = 'unknown'

        result = {
            'uuid': net.UUIDString(),
            'bridge': net.bridgeName(),
            'autostart': net.autostart(),
            'active': net.isActive(),
            'persistent': net.isPersistent(),
            'leases': leases
        }
    except libvirt.libvirtError as err:
        log.debug('Silenced libvirt error: %s', str(err))
    finally:
        conn.close()
    return result


def network_start(name, **kwargs):
    '''
    Start a defined virtual network.

    :param name: virtual network name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.network_start default
    '''
    conn = __get_conn(**kwargs)
    try:
        net = conn.networkLookupByName(name)
        return not bool(net.create())
    finally:
        conn.close()


def network_stop(name, **kwargs):
    '''
    Stop a defined virtual network.

    :param name: virtual network name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.network_stop default
    '''
    conn = __get_conn(**kwargs)
    try:
        net = conn.networkLookupByName(name)
        return not bool(net.destroy())
    finally:
        conn.close()


def network_undefine(name, **kwargs):
    '''
    Remove a defined virtual network. This does not stop the virtual network.

    :param name: virtual network name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.network_undefine default
    '''
    conn = __get_conn(**kwargs)
    try:
        net = conn.networkLookupByName(name)
        return not bool(net.undefine())
    finally:
        conn.close()


def network_set_autostart(name, state='on', **kwargs):
    '''
    Set the autostart flag on a virtual network so that the network
    will start with the host system on reboot.

    :param name: virtual network name
    :param state: 'on' to auto start the network, anything else to mark the
                  virtual network not to be started when the host boots
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt "*" virt.network_set_autostart <pool> <on | off>
    '''
    conn = __get_conn(**kwargs)
    try:
        net = conn.networkLookupByName(name)
        return not bool(net.setAutostart(1 if state == 'on' else 0))
    finally:
        conn.close()


def pool_define_build(name, **kwargs):
    '''
    Create libvirt pool.

    :param name: Pool name
    :param ptype: Pool type
    :param target: Pool path target
    :param source: Pool dev source
    :param autostart: Pool autostart (default True)
    :param start: Pool start (default True)
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_define base logical base

    .. versionadded:: Fluorine
    '''
    exist = False
    update = False
    conn = __get_conn(**kwargs)
    ptype = kwargs.pop('ptype', None)
    target = kwargs.pop('target', None)
    source = kwargs.pop('source', None)
    autostart = kwargs.pop('autostart', True)
    starting = kwargs.pop('start', True)
    pool_xml = _gen_pool_xml(
        name,
        ptype,
        target,
        source,
    )
    try:
        conn.storagePoolDefineXML(pool_xml)
    except libvirtError as err:
        log.warning(err)
        if err.get_error_code() == libvirt.VIR_ERR_STORAGE_POOL_BUILT or libvirt.VIR_ERR_OPERATION_FAILED:
            exist = True
        else:
            conn.close()
            raise err  # a real error we should report upwards
    try:
        pool = conn.storagePoolLookupByName(name)
    except libvirtError as err:
        log.warning(err)
        conn.close()
        raise err  # a real error we should report upwards

    if pool is None:
        conn.close()
        return False

    if (starting is True or autostart is True) and pool.isActive() != 1:
        if exist is True:
            update = True
            pool.create()
        else:
            pool.create(libvirt.VIR_STORAGE_POOL_CREATE_WITH_BUILD)

    if autostart is True and pool.autostart() != 1:
        if exist is True:
            update = True
        pool.setAutostart(int(autostart))
    elif autostart is False and pool.autostart() == 1:
        if exist is True:
            update = True
        pool.setAutostart(int(autostart))

    conn.close()

    if exist is True:
        if update is True:
            return (True, 'Pool exist', 'Pool update')
        return (True, 'Pool exist')

    return True


def list_pools(**kwargs):
    '''
    List all storage pools.

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_pools
    '''
    conn = __get_conn(**kwargs)
    try:
        return [pool.name() for pool in conn.listAllStoragePools()]
    finally:
        conn.close()


def pool_info(name, **kwargs):
    '''
    Return informations on a storage pool provided its name.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_info default
    '''
    result = {}
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        infos = pool.info()
        states = ['inactive', 'building', 'running', 'degraded', 'inaccessible']
        state = states[infos[0]] if infos[0] < len(states) else 'unknown'
        result = {
            'uuid': pool.UUIDString(),
            'state': state,
            'capacity': infos[1],
            'allocation': infos[2],
            'free': infos[3],
            'autostart': pool.autostart(),
            'persistent': pool.isPersistent()
        }
    except libvirt.libvirtError as err:
        log.debug('Silenced libvirt error: %s', str(err))
    finally:
        conn.close()
    return result


def pool_start(name, **kwargs):
    '''
    Start a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_start default
    '''
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.create())
    finally:
        conn.close()


def pool_build(name, **kwargs):
    '''
    Build a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_build default
    '''
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.build())
    finally:
        conn.close()


def pool_stop(name, **kwargs):
    '''
    Stop a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_stop default
    '''
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.destroy())
    finally:
        conn.close()


def pool_undefine(name, **kwargs):
    '''
    Remove a defined libvirt storage pool. The pool needs to be stopped before calling.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_undefine default
    '''
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.undefine())
    finally:
        conn.close()


def pool_delete(name, fast=True, **kwargs):
    '''
    Delete the resources of a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param fast: if set to False, zeroes out all the data.
                 Default value is True.
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_delete default
    '''
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        flags = libvirt.VIR_STORAGE_POOL_DELETE_NORMAL
        if fast:
            flags = libvirt.VIR_STORAGE_POOL_DELETE_ZEROED
        return not bool(pool.delete(flags))
    finally:
        conn.close()


def pool_refresh(name, **kwargs):
    '''
    Refresh a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_refresh default
    '''
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.refresh())
    finally:
        conn.close()


def pool_set_autostart(name, state='on', **kwargs):
    '''
    Set the autostart flag on a libvirt storage pool so that the storage pool
    will start with the host system on reboot.

    :param name: libvirt storage pool name
    :param state: 'on' to auto start the pool, anything else to mark the
                  pool not to be started when the host boots
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt "*" virt.pool_set_autostart <pool> <on | off>
    '''
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.setAutostart(1 if state == 'on' else 0))
    finally:
        conn.close()


def pool_list_volumes(name, **kwargs):
    '''
    List the volumes contained in a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt "*" virt.pool_list_volumes <pool>
    '''
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return pool.listVolumes()
    finally:
        conn.close()
