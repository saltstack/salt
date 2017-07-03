# -*- coding: utf-8 -*-

'''
XenServer Cloud Driver
======================

The XenServer driver is designed to work with a Citrix XenServer.

Requires XenServer SDK

Place a copy of the XenAPI.py in the Python site-packages folder.

:depends: XenAPI

Example provider configuration:

    .. code-block:: yaml

        # /etc/salt/cloud.providers.d/myxen.conf
        myxen:
          driver: xen
          url: http://10.0.0.120
          user: root
          password: p@ssw0rd

Example profile configuration:

    .. code-block:: yaml

        # /etc/salt/cloud.profiles.d/myxen.conf
        suse:
          provider: myxen
          user: root
          password: p@ssw0rd
          image: opensuseleap42_2-template
          storage_repo: 'Local storage'
          resource_pool: default_pool
          clone: True
          minion:
            master: 10.0.0.18
        sles:
          provider: myxen
          user: root
          clone: False
          image: sles12sp2-template
          deploy: False
        w2k12:
          provider: myxen
          image: w2k12svr-template
          clone: True
          userdata_file: /srv/salt/win/files/windows-firewall.ps1
          win_installer: /srv/salt/win/files/Salt-Minion-2016.11.3-AMD64-Setup.exe
          win_username: Administrator
          win_password: p@ssw0rd
          use_winrm: False
          ipv4_cidr: 10.0.0.215/24
          ipv4_gw: 10.0.0.1

'''

# Import python libs
from __future__ import absolute_import
from datetime import datetime
import logging
import time

# Import salt libs
import salt.config as config

# Import Salt-Cloud Libs
import salt.utils.cloud
from salt.exceptions import (
    SaltCloudSystemExit,
    SaltCloudException
)

# Get logging started
log = logging.getLogger(__name__)

try:
    import XenAPI

    HAS_XEN_API = True
except ImportError:
    HAS_XEN_API = False

__virtualname__ = 'xen'
cache = None


def __virtual__():
    '''
    Only load if Xen configuration and XEN SDK is found.
    '''
    if get_configured_provider() is False:
        return False
    if _get_dependencies() is False:
        return False

    global cache  # pylint: disable=global-statement,invalid-name
    cache = salt.cache.Cache(__opts__)

    return __virtualname__


def _get_dependencies():
    '''
    Warn if dependencies aren't met.

    Checks for the XenAPI.py module
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'XenAPI': HAS_XEN_API}
    )


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('url',)
    )


def _get_session():
    '''
    Get a connection to the XenServer host
    '''
    api_version = '1.0'
    originator = 'salt_cloud_{}_driver'.format(__virtualname__)
    url = config.get_cloud_config_value(
        'url',
        get_configured_provider(),
        __opts__,
        search_global=False
    )
    user = config.get_cloud_config_value(
        'user',
        get_configured_provider(),
        __opts__,
        search_global=False
    )
    password = config.get_cloud_config_value(
        'password',
        get_configured_provider(),
        __opts__,
        search_global=False
    )
    session = XenAPI.Session(url)
    log.debug('url: {} user: {} password: {}, originator: {}'.format(
        url,
        user,
        'XXX-pw-redacted-XXX',
        originator))
    session.xenapi.login_with_password(user, password, api_version, originator)
    return session


def list_nodes():
    '''
    List virtual machines

      .. code-block:: bash

          salt-cloud -Q

    '''
    session = _get_session()
    vms = session.xenapi.VM.get_all_records()
    ret = {}
    for vm in vms:
        record = session.xenapi.VM.get_record(vm)
        if not record['is_a_template'] and not record['is_control_domain']:
            ret[record['name_label']] = {
                'id': record['uuid'],
                'image': record['other_config']['base_template_name'],
                'name': record['name_label'],
                'size': record['memory_dynamic_max'],
                'state': record['power_state'],
                'private_ips': get_vm_ip(record['name_label'], session),
                'public_ips': None}
    return ret


def get_vm_ip(name=None, session=None, call=None):
    '''
    Get the IP address of the VM

    .. code-block:: bash

        salt-cloud -a get_vm_ip xenvm01

    .. note:: Requires xen guest tools to be installed in VM

    '''
    if call == 'function':
        raise SaltCloudException(
            'This function must be called with -a or --action.'
        )
    if session is None:
        log.debug('New session being created')
        session = _get_session()
    vm = _get_vm(name, session=session)
    ret = None
    # -- try to get ip from vif
    vifs = session.xenapi.VM.get_VIFs(vm)
    if vifs is not None:
        for vif in vifs:
            if len(session.xenapi.VIF.get_ipv4_addresses(vif)) != 0:
                cidr = session.xenapi.VIF.get_ipv4_addresses(vif).pop()
                ret, subnet = cidr.split('/')
                log.debug(
                    'VM vif returned for instance: {} ip: {}'.format(name, ret))
                return ret
    # -- try to get ip from get tools metrics
    vgm = session.xenapi.VM.get_guest_metrics(vm)
    try:
        net = session.xenapi.VM_guest_metrics.get_networks(vgm)
        if "0/ip" in net.keys():
            log.debug(
                'VM guest metrics returned for instance: {} 0/ip: {}'.format(
                    name,
                    net["0/ip"]))
            ret = net["0/ip"]
    # except Exception as ex:
    except XenAPI.Failure:
        log.info('Could not get vm metrics at this time')
    return ret


def set_vm_ip(name=None,
              ipv4_cidr=None,
              ipv4_gw=None,
              session=None,
              call=None):
    '''
    Set the IP address on a virtual interface (vif)

    '''
    mode = 'static'
    # TODO: Need to add support for IPv6
    if call == 'function':
        raise SaltCloudException(
            'The function must be called with -a or --action.')

    log.debug('Setting name: {} ipv4_cidr: {} ipv4_gw: {} mode: {}'.format(
        name, ipv4_cidr, ipv4_gw, mode))
    if session is None:
        log.debug('New session being created')
        session = _get_session()
    vm = _get_vm(name, session)
    # -- try to get ip from vif
    # TODO: for now will take first interface
    #       addition consideration needed for
    #       multiple interface(vif) VMs
    vifs = session.xenapi.VM.get_VIFs(vm)
    if vifs is not None:
        for vif in vifs:
            log.debug('There are {} vifs.'.format(len(vifs)))
            record = session.xenapi.VIF.get_record(vif)
            log.debug(record)
            try:
                session.xenapi.VIF.configure_ipv4(
                    vif, mode, ipv4_cidr, ipv4_gw)
            except XenAPI.Failure:
                log.info('Static IP assignment could not be performed.')

    return True


def list_nodes_full(session=None):
    '''
    List full virtual machines

      .. code-block:: bash

          salt-cloud -F

    '''
    if session is None:
        session = _get_session()

    ret = {}
    vms = session.xenapi.VM.get_all()
    for vm in vms:
        record = session.xenapi.VM.get_record(vm)
        if not record['is_a_template'] and not record['is_control_domain']:
            vm_cfg = session.xenapi.VM.get_record(vm)
            vm_cfg['id'] = record['uuid']
            vm_cfg['name'] = record['name_label']
            vm_cfg['image'] = record['other_config']['base_template_name']
            vm_cfg['size'] = None
            vm_cfg['state'] = record['power_state']
            vm_cfg['private_ips'] = get_vm_ip(record['name_label'], session)
            vm_cfg['public_ips'] = None
            if 'snapshot_time' in vm_cfg.keys():
                del vm_cfg['snapshot_time']
            ret[record['name_label']] = vm_cfg

    provider = __active_provider_name__ or 'xen'
    if ':' in provider:
        comps = provider.split(':')
        provider = comps[0]
    log.debug('ret: {}'.format(ret))
    log.debug('provider: {}'.format(provider))
    log.debug('__opts__: {}'.format(__opts__))
    __utils__['cloud.cache_node_list'](ret, provider, __opts__)
    return ret


def list_nodes_select(call=None):
    '''
    Perform a select query on Xen VM instances

    .. code-block:: bash

        salt-cloud -S

    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(),
        __opts__['query.selection'],
        call,
    )


def vdi_list(call=None, kwargs=None):
    '''
    Return available Xen VDI images

    If this function is called with the ``-f`` or ``--function`` then
    it can return a list with minimal deatil using the ``terse=True`` keyword
    argument.

    .. code-block:: bash

        salt-cloud -f vdi_list myxen terse=True

    '''
    if call == 'action':
        raise SaltCloudException(
            'This function must be called with -f or --function.')
    log.debug('kwargs is {}'.format(kwargs))
    if kwargs is not None:
        if 'terse' in kwargs:
            if kwargs['terse'] == 'True':
                terse = True
            else:
                terse = False
        else:
            terse = False
    else:
        kwargs = {}
        terse = False
    session = _get_session()
    vdis = session.xenapi.VDI.get_all()
    ret = {}
    for vdi in vdis:
        data = session.xenapi.VDI.get_record(vdi)
        log.debug(type(terse))
        if terse is True:
            ret[data.get('name_label')] = {
                'uuid': data.get('uuid'),
                'OpqueRef': vdi}
        else:
            data.update({'OpaqueRef': vdi})
            ret[data.get('name_label')] = data
    return ret


def avail_locations(session=None, call=None):
    '''
    Return available Xen locations (not implemented)

    .. code-block:: bash

        salt-cloud --list-locations myxen

    '''
    # TODO: need to figure out a good meaning of locations in Xen
    if call == 'action':
        raise SaltCloudException(
            'The avail_locations function must be called with -f or --function.'
        )
    return pool_list()


def avail_sizes(session=None, call=None):
    '''
    Return a list of Xen templat definitions

    .. code-block:: bash

        salt-cloud --list-sizes myxen

    '''
    if call == 'action':
        raise SaltCloudException(
            'The avail_sizes function must be called with -f or --function.')
    return {'STATUS':
            'Sizes are build into templates. Consider running --list-images to see sizes'}


def template_list(call=None):
    '''
    Return available Xen template information.

    This returns the details of
    each template to show number cores, memory sizes, etc..

    .. code-block:: bash

       salt-cloud -f template_list myxen

    '''
    templates = {}
    session = _get_session()
    vms = session.xenapi.VM.get_all()
    for vm in vms:
        record = session.xenapi.VM.get_record(vm)
        if record['is_a_template']:
            templates[record['name_label']] = record
    return templates


def show_instance(name, session=None, call=None):
    '''
    Show information about a specific VM or template

        .. code-block:: bash

            salt-cloud -a show_instance xenvm01

    .. note:: memory is memory_dynamic_max

    '''
    if call == 'function':
        raise SaltCloudException(
            'The show_instnce function must be called with -a or --action.'
        )
    log.debug('show_instance-> name: {} session: {}'.format(name, session))
    if session is None:
        session = _get_session()
    vm = _get_vm(name, session=session)
    record = session.xenapi.VM.get_record(vm)
    if not record['is_a_template'] and not record['is_control_domain']:
        ret = {'id': record['uuid'],
               'image': record['other_config']['base_template_name'],
               'name': record['name_label'],
               'size': record['memory_dynamic_max'],
               'state': record['power_state'],
               'private_ips': get_vm_ip(name, session),
               'public_ips': None}

        __utils__['cloud.cache_node'](
            ret,
            __active_provider_name__,
            __opts__
        )
    return ret


def _determine_resource_pool(session, vm_):
    '''
    Called by create() used to determine resource pool
    '''
    resource_pool = ''
    if 'resource_pool' in vm_.keys():
        resource_pool = _get_pool(vm_['resource_pool'], session)
    else:
        pool = session.xenapi.pool.get_all()
        if len(pool) <= 0:
            resource_pool = None
        else:
            first_pool = session.xenapi.pool.get_all()[0]
            resource_pool = first_pool
    pool_record = session.xenapi.pool.get_record(resource_pool)
    log.debug('resource pool: {}'.format(pool_record['name_label']))
    return resource_pool


def _determine_storage_repo(session, resource_pool, vm_):
    '''
    Called by create() used to determine storage repo for create
    '''
    storage_repo = ''
    if 'storage_repo' in vm_.keys():
        storage_repo = _get_sr(vm_['storage_repo'], session)
    else:
        storage_repo = None
        if resource_pool:
            default_sr = session.xenapi.pool.get_default_SR(resource_pool)
            sr_record = session.xenapi.SR.get_record(default_sr)
            log.debug('storage repository: {}'.format(sr_record['name_label']))
            storage_repo = default_sr
        else:
            storage_repo = None
    log.debug('storage repository: {}'.format(storage_repo))
    return storage_repo


def create(vm_):
    '''
    Create a VM in Xen

    The configuration for this function is read from the profile settings.

    .. code-block:: bash

        salt-cloud -p some_profile xenvm01

    '''
    name = vm_['name']
    record = {}
    ret = {}

    # Since using "provider: <provider-engine>" is deprecated, alias provider
    # to use driver: "driver: <provider-engine>"
    if 'provider' in vm_:
        vm_['driver'] = vm_.pop('provider')

    # fire creating event
    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(name),
        args={
            'name': name,
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )
    log.debug('Adding {} to cloud cache.'.format(name))
    __utils__['cloud.cachedir_index_add'](
        vm_['name'], vm_['profile'], 'xen', vm_['driver']
    )

    # connect to xen
    session = _get_session()

    # determine resource pool
    resource_pool = _determine_resource_pool(session, vm_)

    # determine storage repo
    storage_repo = _determine_storage_repo(session, resource_pool, vm_)

    # build VM
    image = vm_.get('image')
    clone = vm_.get('clone')
    if clone is None:
        clone = True
    log.debug('Clone: {} '.format(clone))

    # fire event to read new vm properties (requesting)
    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(name),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    # create by cloning template
    if clone:
        _clone_vm(image, name, session)
    else:
        _copy_vm(image, name, session, storage_repo)

    # provision template to vm
    _provision_vm(name, session)
    vm = _get_vm(name, session)

    # start vm
    start(name, None, session)

    # get new VM
    vm = _get_vm(name, session)

    # wait for vm to report IP via guest tools
    _wait_for_ip(name, session)

    # set static IP if configured
    _set_static_ip(name, session, vm_)

    # if not deploying salt then exit
    deploy = vm_.get('deploy', True)
    log.debug('delopy is set to {}'.format(deploy))
    if deploy:
        record = session.xenapi.VM.get_record(vm)
        if record is not None:
            _deploy_salt_minion(name, session, vm_)
    else:
        log.debug(
            'The Salt minion will not be installed, deploy: {}'.format(
                vm_['deploy'])
        )
    record = session.xenapi.VM.get_record(vm)
    ret = show_instance(name)
    ret.update({'extra': record})

    __utils__['cloud.fire_event'](
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(name),
        args={
            'name': name,
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )
    return ret


def _deploy_salt_minion(name, session, vm_):
    '''
    Deploy salt minion during create()
    '''
    # Get bootstrap values
    vm_['ssh_host'] = get_vm_ip(name, session)
    vm_['user'] = vm_.get('user', 'root')
    vm_['password'] = vm_.get('password', 'p@ssw0rd!')
    log.debug('{} has IP of {}'.format(name, vm_['ssh_host']))
    # Bootstrap Salt minion!
    if vm_['ssh_host'] is not None:
        log.info('Installing Salt minion  on {0}'.format(name))
        boot_ret = __utils__['cloud.bootstrap'](vm_, __opts__)
        log.debug('boot return: {}'.format(boot_ret))


def _set_static_ip(name, session, vm_):
    '''
    Set static IP during create() if defined
    '''
    ipv4_cidr = ''
    ipv4_gw = ''
    if 'ipv4_gw' in vm_.keys():
        log.debug('ipv4_gw is found in keys')
        ipv4_gw = vm_['ipv4_gw']
    if 'ipv4_cidr' in vm_.keys():
        log.debug('ipv4_cidr is found in keys')
        ipv4_cidr = vm_['ipv4_cidr']
        log.debug('attempting to set IP in instance')
        set_vm_ip(name, ipv4_cidr, ipv4_gw, session, None)


def _wait_for_ip(name, session):
    '''
    Wait for IP  to be available during create()
    '''
    start_time = datetime.now()
    status = None
    while status is None:
        status = get_vm_ip(name, session)
        if status is not None:
            # ignore APIPA address
            if status.startswith('169'):
                status = None
        check_time = datetime.now()
        delta = check_time - start_time
        log.debug('Waited {} seconds for {} to report ip address...'.format(
            delta.seconds, name))
        if delta.seconds > 180:
            log.warn('Timeout getting IP address')
            break
        time.sleep(5)


def _run_async_task(task=None, session=None):
    '''
    Run  XenAPI task in async mode to prevent timeouts
    '''
    if task is None or session is None:
        return None
    task_name = session.xenapi.task.get_name_label(task)
    log.debug('Running {}'.format(task_name))
    while session.xenapi.task.get_status(task) == 'pending':
        progress = round(session.xenapi.task.get_progress(task), 2) * 100
        log.debug('Task progress {}%'.format(str(progress)))
        time.sleep(1)
    log.debug('Cleaning up task {}'.format(task_name))
    session.xenapi.task.destroy(task)


def _clone_vm(image=None, name=None, session=None):
    '''
    Create VM by cloning

    This is faster and should be used if source and target are
    in the same storage repository

    '''
    if session is None:
        session = _get_session()
    log.debug('Creating VM {0} by cloning {1}'.format(name, image))
    source = _get_vm(image, session)
    task = session.xenapi.Async.VM.clone(source, name)
    _run_async_task(task, session)


def _copy_vm(template=None, name=None, session=None, sr=None):
    '''
    Create VM by copy

    This is faster and should be used if source and target are
    NOT in the same storage repository

    template = object reference
    name = string name of new VM
    session = object reference
    sr = object reference
    '''
    if session is None:
        session = _get_session()
    log.debug('Creating VM {0} by copying {1}'.format(name, template))
    source = _get_vm(template, session)
    task = session.xenapi.Async.VM.copy(source, name, sr)
    _run_async_task(task, session)


def _provision_vm(name=None, session=None):
    '''
    Provision vm right after clone/copy
    '''
    if session is None:
        session = _get_session()
    log.info('Provisioning VM {0}'.format(name))
    vm = _get_vm(name, session)
    task = session.xenapi.Async.VM.provision(vm)
    _run_async_task(task, session)


def start(name, call=None, session=None):
    '''
    Start  a vm

    .. code-block:: bash

        salt-cloud -a start xenvm01

    '''
    if call == 'function':
        raise SaltCloudException(
            'The show_instnce function must be called with -a or --action.'
        )
    if session is None:
        session = _get_session()
    log.info('Starting VM {0}'.format(name))
    vm = _get_vm(name, session)
    task = session.xenapi.Async.VM.start(vm, False, True)
    _run_async_task(task, session)
    return show_instance(name)


def pause(name, call=None, session=None):
    '''
    Pause a vm

    .. code-block:: bash

        salt-cloud -a pause xenvm01

    '''
    if call == 'function':
        raise SaltCloudException(
            'The show_instnce function must be called with -a or --action.'
        )
    if session is None:
        session = _get_session()
    log.info('Pausing VM {0}'.format(name))
    vm = _get_vm(name, session)
    task = session.xenapi.Async.VM.pause(vm)
    _run_async_task(task, session)
    return show_instance(name)


def unpause(name, call=None, session=None):
    '''
    UnPause a vm

    .. code-block:: bash

        salt-cloud -a unpause xenvm01

    '''
    if call == 'function':
        raise SaltCloudException(
            'The show_instnce function must be called with -a or --action.'
        )
    if session is None:
        session = _get_session()
    log.info('Unpausing VM {0}'.format(name))
    vm = _get_vm(name, session)
    task = session.xenapi.Async.VM.unpause(vm)
    _run_async_task(task, session)
    return show_instance(name)


def suspend(name, call=None, session=None):
    '''
    Suspend a vm to disk

    .. code-block:: bash

        salt-cloud -a suspend xenvm01

    '''
    if call == 'function':
        raise SaltCloudException(
            'The show_instnce function must be called with -a or --action.'
        )
    if session is None:
        session = _get_session()
    log.info('Suspending VM {0}'.format(name))
    vm = _get_vm(name, session)
    task = session.xenapi.Async.VM.suspend(vm)
    _run_async_task(task, session)
    return show_instance(name)


def resume(name, call=None, session=None):
    '''
    Resume a vm from disk

    .. code-block:: bash

        salt-cloud -a resume xenvm01

    '''
    if call == 'function':
        raise SaltCloudException(
            'The show_instnce function must be called with -a or --action.'
        )
    if session is None:
        session = _get_session()
    log.info('Resuming VM {0}'.format(name))
    vm = _get_vm(name, session)
    task = session.xenapi.Async.VM.resume(vm, False, True)
    _run_async_task(task, session)
    return show_instance(name)


def stop(name, call=None, session=None):
    '''
    Stop a vm

    .. code-block:: bash

        salt-cloud -a stop xenvm01


    '''
    if call == 'function':
        raise SaltCloudException(
            'The show_instnce function must be called with -a or --action.'
        )
    return shutdown(name, call, session)


def shutdown(name, call=None, session=None):
    '''
    Shutdown  a vm

    .. code-block:: bash

        salt-cloud -a shutdown xenvm01

    '''
    if call == 'function':
        raise SaltCloudException(
            'The show_instnce function must be called with -a or --action.'
        )
    if session is None:
        session = _get_session()
    log.info('Starting VM {0}'.format(name))
    vm = _get_vm(name, session)
    task = session.xenapi.Async.VM.shutdown(vm)
    _run_async_task(task, session)
    return show_instance(name)


def reboot(name, call=None, session=None):
    '''
    Reboot a vm

    .. code-block:: bash

        salt-cloud -a reboot xenvm01

    '''
    if call == 'function':
        raise SaltCloudException(
            'The show_instnce function must be called with -a or --action.'
        )
    if session is None:
        session = _get_session()
    log.info('Starting VM {0}'.format(name))
    vm = _get_vm(name, session)
    power_state = session.xenapi.VM.get_power_state(vm)
    if power_state == 'Running':
        task = session.xenapi.Async.VM.clean_reboot(vm)
        _run_async_task(task, session)
        return show_instance(name)
    else:
        return '{} is not running to be rebooted'.format(name)


def _get_vm(name=None, session=None):
    '''
    Get XEN vm instance object reference
    '''
    if session is None:
        session = _get_session()
    vms = session.xenapi.VM.get_by_name_label(name)
    if len(vms) == 1:
        return vms[0]
    return None


def _get_sr(name=None, session=None):
    '''
    Get XEN sr (storage repo) object reference
    '''
    if session is None:
        session = _get_session()
    srs = session.xenapi.SR.get_by_name_label(name)
    if len(srs) == 1:
        return srs[0]
    return None


def _get_pool(name=None, session=None):
    '''
    Get XEN resource pool object reference
    '''
    if session is None:
        session = _get_session()
    pools = session.xenapi.pool.get_all()
    for pool in pools:
        pool_record = session.xenapi.pool.get_record(pool)
        if name in pool_record.get('name_label'):
            return pool
    return None


def destroy(name=None, call=None):
    '''
    Destroy Xen VM or template instance

    .. code-block:: bash

        salt-cloud -d xenvm01

    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )
    ret = {}
    __utils__['cloud.fire_event'](
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )
    session = _get_session()
    vm = _get_vm(name)
    if vm:
        # get vm
        record = session.xenapi.VM.get_record(vm)
        log.debug('power_state: ' + record['power_state'])
        # shut down
        if record['power_state'] != 'Halted':
            task = session.xenapi.Async.VM.hard_shutdown(vm)
            _run_async_task(task, session)

        # destroy disk (vdi) by reading vdb on vm
        ret['vbd'] = destroy_vm_vdis(name, session)
        # destroy vm
        task = session.xenapi.Async.VM.destroy(vm)
        _run_async_task(task, session)
        ret['destroyed'] = True
        __utils__['cloud.fire_event'](
            'event',
            'destroyed instance',
            'salt/cloud/{0}/destroyed'.format(name),
            args={'name': name},
            sock_dir=__opts__['sock_dir'],
            transport=__opts__['transport']
        )
        if __opts__.get('update_cachedir', False) is True:
            __utils__['cloud.delete_minion_cachedir'](
                name,
                __active_provider_name__.split(':')[0],
                __opts__
            )
        __utils__['cloud.cachedir_index_del'](name)
        return ret


def sr_list(call=None):
    '''
    Geta list of storage repositories

    .. code-block:: bash

        salt-cloud -f sr_list myxen

    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'This function must be called with -f, --function argument.'
        )
    ret = {}
    session = _get_session()
    srs = session.xenapi.SR.get_all()
    for sr in srs:
        sr_record = session.xenapi.SR.get_record(sr)
        ret[sr_record['name_label']] = sr_record
    return ret


def host_list(call=None):
    '''
    Get a list of Xen Servers

    .. code-block:: bash

        salt-cloud -f host_list myxen
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'This function must be called with -f, --function argument.'
        )
    ret = {}
    session = _get_session()
    hosts = session.xenapi.host.get_all()
    for host in hosts:
        host_record = session.xenapi.host.get_record(host)
        ret[host_record['name_label']] = host_record
    return ret


def pool_list(call=None):
    '''
    Get a list of Resource Pools

    .. code-block:: bash

        salt-cloud -f pool_list myxen

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'This function must be called with -f, --function argument.'
        )
    ret = {}
    session = _get_session()
    pools = session.xenapi.pool.get_all()
    for pool in pools:
        pool_record = session.xenapi.pool.get_record(pool)
        ret[pool_record['name_label']] = pool_record
    return ret


def pif_list(call=None):
    '''
    Get a list of Resource Pools

    .. code-block:: bash

        salt-cloud -f pool_list myxen
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'This function must be called with -f, --function argument.'
        )
    ret = {}
    session = _get_session()
    pifs = session.xenapi.PIF.get_all()
    for pif in pifs:
        record = session.xenapi.PIF.get_record(pif)
        ret[record['uuid']] = record
    return ret


def vif_list(name, call=None, kwargs=None):
    '''
    Get a list of virtual network interfaces  on a VM

    **requires**: the name of the vm with the vbd definition

    .. code-block:: bash

        salt-cloud -a vif_list xenvm01

    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'This function must be called with -a, --action argument.'
        )
    if name is None:
        return 'A name kwarg is rquired'
    ret = {}
    data = {}
    session = _get_session()
    vm = _get_vm(name)
    vifs = session.xenapi.VM.get_VIFs(vm)
    if vifs is not None:
        x = 0
        for vif in vifs:
            vif_record = session.xenapi.VIF.get_record(vif)
            data['vif-{}'.format(x)] = vif_record
            x += 1
    ret[name] = data
    return ret


def vbd_list(name=None, call=None):
    '''
    Get a list of VBDs on a VM

    **requires**: the name of the vm with the vbd definition

    .. code-block:: bash

        salt-cloud -a vbd_list xenvm01

    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'This function must be called with -a, --action argument.'
        )
    if name is None:
        return 'A name kwarg is rquired'
    ret = {}
    data = {}
    session = _get_session()
    vms = session.xenapi.VM.get_by_name_label(name)
    if len(vms) == 1:
        vm = vms[0]
        vbds = session.xenapi.VM.get_VBDs(vm)
        if vbds is not None:
            x = 0
            for vbd in vbds:
                vbd_record = session.xenapi.VBD.get_record(vbd)
                data['vbd-{}'.format(x)] = vbd_record
                x += 1
    ret = data
    return ret


def avail_images(call=None):
    '''
    Get a list of images from Xen

    If called with the `--list-images` then it returns
    images with all details.

    .. code-block:: bash

        salt-cloud --list-images myxen

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'This function must be called with -f, --function argument.'
        )
    return template_list()


def destroy_vm_vdis(name=None, session=None, call=None):
    '''
    Get virtual block devices on VM

    .. code-block:: bash

        salt-cloud -a destroy_vm_vdis  xenvm01

    '''
    if session is None:
        session = _get_session()
    ret = {}
    # get vm object
    vms = session.xenapi.VM.get_by_name_label(name)
    if len(vms) == 1:
        # read virtual block device (vdb)
        vbds = session.xenapi.VM.get_VBDs(vms[0])
        if vbds is not None:
            x = 0
            for vbd in vbds:
                vbd_record = session.xenapi.VBD.get_record(vbd)
                if vbd_record['VDI'] != 'OpaqueRef:NULL':
                    # read vdi on vdb
                    vdi_record = session.xenapi.VDI.get_record(
                        vbd_record['VDI'])
                    if 'iso' not in vdi_record['name_label']:
                        session.xenapi.VDI.destroy(vbd_record['VDI'])
                        ret['vdi-{}'.format(x)] = vdi_record['name_label']
                x += 1
    return ret


def destroy_template(name=None, call=None, kwargs=None):
    '''
    Destroy Xen VM or template instance

        .. code-block:: bash

            salt-cloud -f destroy_template myxen name=testvm2

    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The destroy_template function must be called with  -f.'
        )
    if kwargs is None:
        kwargs = {}
    name = kwargs.get('name', None)
    session = _get_session()
    vms = session.xenapi.VM.get_all_records()
    ret = {}
    found = False
    for vm in vms:
        record = session.xenapi.VM.get_record(vm)
        if record['is_a_template']:
            if record['name_label'] == name:
                found = True
                # log.debug(record['name_label'])
                session.xenapi.VM.destroy(vm)
                ret[name] = {'status': 'destroyed'}
    if not found:
        ret[name] = {'status': 'not found'}
    return ret
