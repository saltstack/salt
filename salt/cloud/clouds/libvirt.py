# -*- coding: utf-8 -*-
'''
Libvirt Cloud Module
====================

Example provider:

.. code-block:: yaml

    # Provider maps to libvirt instance
    my-libvirt-config:
      driver: libvirt
      # url: "qemu+ssh://user@remotekvm/system?socket=/var/run/libvirt/libvirt-sock"
      url: qemu:///system

Example profile:

.. code-block:: yaml

    base-itest:
      # points back at provider config, which is the libvirt daemon to talk to
      provider: my-libvirt-config
      base_domain: base-image
      ssh_username: vagrant
      # has_ssh_agent: True
      password: vagrant
      # if /tmp is mounted noexec do workaround
      deploy_command: sh /tmp/.saltcloud/deploy.sh
      # -F makes the bootstrap script overwrite existing config
      # which make reprovisioning a box work
      script_args: -F
      grains:
        sushi: more tasty
      # point at the another master at another port
      minion:
        master: 192.168.16.1
        master_port: 5506

TODO: look at event descriptions here:
  https://docs.saltstack.com/en/latest/topics/cloud/reactor.html
'''

# Import python libs
from __future__ import absolute_import
import sys
import traceback
import logging
import uuid
import time

from xml.etree import ElementTree

# Import salt libs
import salt.utils

# Import salt cloud libs
import salt.utils.cloud
import salt.config as config

import salt.ext.six as six

try:
    import libvirt  # pylint: disable=import-error
    HAS_LIBVIRT = True
except ImportError:
    HAS_LIBVIRT = False

# Get logging started
log = logging.getLogger(__name__)

VIRT_STATE_NAME_MAP = {0: 'running',
                       1: 'running',
                       2: 'running',
                       3: 'paused',
                       4: 'shutdown',
                       5: 'shutdown',
                       6: 'crashed'}

IP_LEARNING_XML = """<filterref filter='clean-traffic'>
        <parameter name='CTRL_IP_LEARNING' value='any'/>
      </filterref>"""


def __virtual__():
    '''
    Needs no special configuration
    '''
    if not HAS_LIBVIRT:
        return (False, 'Unable to locate or import python libvirt library.')
    return True

def __get_conn(url):
    # This has only been tested on kvm and xen, it needs to be expanded to
    # support all vm layers supported by libvirt

    try:
        conn = libvirt.open(url)
    except Exception:
        raise CommandExecutionError(
            'Sorry, {0} failed to open a connection to the hypervisor '
            'software at {1}'.format(
                __grains__['fqdn'], url
            )
        )
    return conn


def list_nodes(kwargs=None, call=None):
    '''
    Return a list of the VMs

    id (str)
    image (str)
    size (str)
    state (str)
    private_ips (list)
    public_ips (list)

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called '
            'with -f or --function.'
        )

    providers = __opts__.get('providers', {})

    ret = {}
    providers_to_check = filter(None, [cfg.get('libvirt') for cfg in providers.itervalues()])
    for p in providers_to_check:
        conn = __get_conn(p['url'])
        domains = conn.listAllDomains()
        # TODO: filter on the domains we actually manage
        for d in domains:
            data = {
                'id': d.UUIDString(),
                'image': '',
                'size': '',
                'state': VIRT_STATE_NAME_MAP[d.state()[0]],
                'private_ips': [],
                'public_ips': getDomainIps(d) }
            # TODO: Annoyingly name is not guaranteed to be unique, but the id will not work in other places
            ret[d.name()] = data

    return ret

def list_nodes_full(kwargs=None, call=None):
    '''
    Because this module is not specific to any cloud providers, there will be
    no nodes to list.
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called '
            'with -f or --function.'
        )

    return list_nodes(call)

def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_select function must be called '
            'with -f or --function.'
        )

    selection = __opts__.get('query.selection')

    if not selection:
        raise SaltCloudSystemExit(
            'query.selection not found in /etc/salt/cloud'
        )

    # TODO: somewhat doubt the implementation of cloud.list_nodes_select
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(), selection, call,
    )

def toIPAddrType(addrType):
    if addrType == libvirt.VIR_IP_ADDR_TYPE_IPV4:
        return "ipv4"
    elif addrType == libvirt.VIR_IP_ADDR_TYPE_IPV6:
        return "ipv6"

def getDomainIps(domain):
    ips = []
    state = domain.state(0)
    if state[0] != libvirt.VIR_DOMAIN_RUNNING:
        return ips
    addresses = domain.interfaceAddresses(0,0)
    for (name, val) in addresses.iteritems():
        if val['addrs']:
            for addr in val['addrs']:
                tp = toIPAddrType(addr['type'])
                if tp == "ipv4":
                    ips.append(addr['addr'])
    return ips

def getDomainIp(domain, idx=0):
    ips = getDomainIps(domain)
    if not ips or len(ips) <= idx:
        return None
    return ips[idx]

def create(vm_):
    '''
    Provision a single machine
    '''
    log.info('Cloning machine {0}'.format(vm_['name']))

    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'libvirt',
                                                           vm_['profile']) is False:
            return False
    except AttributeError:
        pass

    # RK: no clue if we need this?
    # Since using "provider: <provider-engine>" is deprecated, alias provider
    # to use driver: "driver: <provider-engine>"
    if 'provider' in vm_:
        vm_['driver'] = vm_.pop('provider')

    # TODO: check name ?
    name = vm_['name']

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(name),
        {
            'name': name,
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        transport = __opts__['transport']
    )

    key_filename = config.get_cloud_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined key_filename \'{0}\' does not exist'.format(
                key_filename
            )
        )
    vm_['key_filename'] = key_filename
    # wait_for_instance requires private_key
    vm_['private_key'] = key_filename

    cleanup = []
    try:
        # clone the vm
        base = vm_['base_domain']
        conn = __get_conn(vm_['url'])

        cloneXml = None
        try:
            # for idempotency the salt-bootstrap needs -F argument
            #  script_args: -F
            cloneDomain = conn.lookupByName(name)
        except:
            domain = conn.lookupByName(base)
            # TODO: ensure base is shut down before cloning
            xml = domain.XMLDesc(0)

            # TODO: does this have some predescribed format?
            kwargs = {
                'name': name,
                'base_domain': base,
            }

            salt.utils.cloud.fire_event(
                'event',
                'requesting instance',
                'salt/cloud/{0}/requesting'.format(name),
                {'kwargs': kwargs},
                transport=__opts__['transport']
            )

            domainXml = ElementTree.fromstring(xml)
            domainXml.find('./name').text = name
            domainXml.find('./description').text = "Cloned from {0}".format(base)
            domainXml.remove(domainXml.find('./uuid'))
            for ifaceXml in domainXml.findall('./devices/interface'):
                ifaceXml.remove(ifaceXml.find('./mac'))
                # enable IP learning
                if ifaceXml.find("./filterref/parameter[@name='CTRL_IP_LEARNING']") is None:
                    ifaceXml.append(ElementTree.fromstring(IP_LEARNING_XML))
            for disk in domainXml.findall("""./devices/disk[@device='disk'][@type='file']"""):
                # print "Disk: ", ElementTree.tostring(disk)
                # check if we can clone
                if disk.find("./driver[@name='qemu'][@type='qcow2']") is not None:
                    source = disk.find("./source").attrib['file']
                    pool, volume = findPoolAndVolume(conn, source)
                    newVolume = pool.createXML(createVolumeWithBackingStoreXml(volume), 0)
                    cleanup.append({ 'what': 'volume', 'item': newVolume })

                    # apply new volume to
                    disk.find("./source").attrib['file'] = newVolume.path()
                else:
                    # TODO: duplicate disk
                    raise CommandExecutionError('Cloning a disk is not supported yet.')

            cloneXml = ElementTree.tostring(domainXml)

            cloneDomain = conn.defineXMLFlags(cloneXml, libvirt.VIR_DOMAIN_DEFINE_VALIDATE)
            cleanup.append({ 'what': 'domain', 'item': cloneDomain })
            cloneDomain.createWithFlags(libvirt.VIR_DOMAIN_START_FORCE_BOOT)

        address = salt.utils.cloud.wait_for_ip(
            getDomainIp,
            update_args=(cloneDomain, 0),
            timeout=config.get_cloud_config_value('wait_for_ip_timeout', vm_, __opts__, default=10 * 60),
            interval=config.get_cloud_config_value('wait_for_ip_interval', vm_, __opts__, default=10),
            interval_multiplier=config.get_cloud_config_value('wait_for_ip_interval_multiplier', vm_, __opts__, default=1),
        )

        log.info('Address = {0}'.format(address))

        vm_['ssh_host'] = address

        # the bootstrap script needs to be installed first in /etc/salt/cloud.deploy.d/
        # salt-cloud -u is your friend
        ret = salt.utils.cloud.bootstrap(vm_, __opts__)

        salt.utils.cloud.fire_event(
            'event',
            'created instance',
            'salt/cloud/{0}/created'.format(name),
            {
                'name': name,
                'profile': vm_['profile'],
                'provider': vm_['driver'],
            },
            transport=__opts__['transport']
        )

        return ret
    except:
        log.info('cleanup = {0}'.format(cleanup))
        for leftover in cleanup:
            what = leftover['what']
            item = leftover['item']
            if what == 'domain':
                destroyDomain(conn, item)
            if what == 'volume':
                item.delete()

        info = sys.exc_info()
        print 'crashed {0}'.format(info)
        traceback.print_tb(info[2])

def destroy(name, call=None):
    """
    This function irreversibly destroys a virtual machine on the cloud provider.
    Before doing so, it should fire an event on the Salt event bus.

    The tag for this event is `salt/cloud/<vm name>/destroying`.
    Once the virtual machine has been destroyed, another event is fired.
    The tag for that event is `salt/cloud/<vm name>/destroyed`.

    Dependencies:
        list_nodes

    @param name:
    @type name: str
    @param call:
    @type call:
    @return: True if all went well, otherwise an error message
    @rtype: bool|str
    """
    log.info("Attempting to delete instance {0}".format(name))

    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    found = []

    providers = __opts__.get('providers', {})
    providers_to_check = filter(None, [cfg.get('libvirt') for cfg in providers.itervalues()])
    for p in providers_to_check:
        conn = __get_conn(p['url'])
        log.info("looking at {0}".format(p['url']))
        try:
            domain = conn.lookupByName(name)
            found.append({ 'domain': domain, 'conn': conn })
        except:
            pass

    if not found:
        return "{0} doesn't exist and can't be deleted".format(name)

    if len(found) > 1:
        return "{0} doesn't identify a unique machine leaving things".format(name)

    try:
        salt.utils.cloud.fire_event(
            'event',
            'destroying instance',
            'salt/cloud/{0}/destroying'.format(name),
            {'name': name},
            transport=__opts__['transport']
        )

        destroyDomain(found[0]['conn'], found[0]['domain'])

        salt.utils.cloud.fire_event(
            'event',
            'destroyed instance',
            'salt/cloud/{0}/destroyed'.format(name),
            {'name': name},
            transport=__opts__['transport']
        )
    except:
        info = sys.exc_info()
        print 'crashed {0}'.format(info)
        traceback.print_tb(info[2])

def destroyDomain(conn, domain):
    log.info('Destroying domain {0}'.format(domain.name()))
    try:
        domain.destroy()
    except:
        pass
    volumes = getDomainVolumes(conn, domain)
    for v in volumes:
        log.debug('Removing volume {0}'.format(v.name()))
        v.delete()

    log.debug('Undefining domain {0}'.format(domain.name()))
    domain.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE+libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA+libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)

def createVolumeWithBackingStoreXml(volume):
    template = """<volume>
                    <name>n</name>
                    <capacity>c</capacity>
                    <allocation>0</allocation>
                    <target>
                        <format type='qcow2'/>
                        <compat>1.1</compat>
                    </target>
                    <backingStore>
                        <format type='qcow2'/>
                        <path>p</path>
                    </backingStore>
                </volume>
                """
    volumeXml = ElementTree.fromstring(template)
    # TODO: generate name
    volumeXml.find('name').text = generate_new_name(volume.name())
    log.debug("volume: {0}".format(dir(volume)))
    volumeXml.find('capacity').text = str(volume.info()[1])
    volumeXml.find('./backingStore/path').text = volume.path()
    r = ElementTree.tostring(volumeXml)
    log.debug("Creating {0}".format(r))
    return r

def findPoolAndVolume(conn, path):
    # active and persistent storage pools
    # TODO: should we filter on type?
    for sp in conn.listAllStoragePools(2+4):
        for v in sp.listAllVolumes():
            if v.path() == path:
                return (sp, v)
    raise CommandExecutionError('Could not clone disk no storage pool with volume found')

def generate_new_name(orig_name):
    name, ext = orig_name.rsplit('.', 1)
    return '{0}-{1}.{2}'.format(name, uuid.uuid1(), ext)

def getDomainVolumes(conn, domain):
    volumes = []
    xml = ElementTree.fromstring(domain.XMLDesc(0))
    for disk in xml.findall("""./devices/disk[@device='disk'][@type='file']"""):
        if disk.find("./driver[@name='qemu'][@type='qcow2']") is not None:
            source = disk.find("./source").attrib['file']
            pool, volume = findPoolAndVolume(conn, source)
            volumes.append(volume)
    return volumes

def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'libvirt',
        ()
    )
