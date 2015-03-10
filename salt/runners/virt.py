# -*- coding: utf-8 -*-
'''
Control virtual machines via Salt
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import
import logging

# Import Salt libs
import salt.client
import salt.utils.virt
import salt.key
from salt.exceptions import SaltClientError

log = logging.getLogger(__name__)


def _determine_hyper(data, omit=''):
    '''
    Determine what the most resource free hypervisor is based on the given
    data
    '''
    # This is just checking for the hyper with the most free ram, this needs
    # to be much more complicated.
    hyper = ''
    bestmem = 0
    for hv_, comps in data.items():
        if hv_ == omit:
            continue
        if not isinstance(comps, dict):
            continue
        if comps.get('freemem', 0) > bestmem:
            bestmem = comps['freemem']
            hyper = hv_
    return hyper


def _find_vm(name, data, quiet=False):
    '''
    Scan the query data for the named vm
    '''
    for hv_ in data:
        # Check if data is a dict, and not '"virt.full_info" is not available.'
        if not isinstance(data[hv_], dict):
            continue
        if name in data[hv_].get('vm_info', {}):
            ret = {hv_: {name: data[hv_]['vm_info'][name]}}
            if not quiet:
                __jid_event__.fire_event({'data': ret, 'outputter': 'nested'}, 'progress')
            return ret
    return {}


def query(hyper=None, quiet=False):
    '''
    Query the virtual machines. When called without options all hypervisors
    are detected and a full query is returned. A single hypervisor can be
    passed in to specify an individual hypervisor to query.
    '''
    if quiet:
        log.warn('\'quiet\' is deprecated. Please migrate to --quiet')
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    try:
        for info in client.cmd_iter('virtual:physical',
                                    'virt.full_info', expr_form='grain'):
            if not info:
                continue
            if not isinstance(info, dict):
                continue
            chunk = {}
            id_ = next(info.iterkeys())
            if hyper:
                if hyper != id_:
                    continue
            if not isinstance(info[id_], dict):
                continue
            if 'ret' not in info[id_]:
                continue
            if not isinstance(info[id_]['ret'], dict):
                continue
            chunk[id_] = info[id_]['ret']
            ret.update(chunk)
            if not quiet:
                __jid_event__.fire_event({'data': chunk, 'outputter': 'virt_query'}, 'progress')
    except SaltClientError as client_error:
        print(client_error)
    return ret


def list(hyper=None, quiet=False):  # pylint: disable=redefined-builtin
    '''
    List the virtual machines on each hyper, this is a simplified query,
    showing only the virtual machine names belonging to each hypervisor.
    A single hypervisor can be passed in to specify an individual hypervisor
    to list.
    '''
    if quiet:
        log.warn('\'quiet\' is deprecated. Please migrate to --quiet')
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    for info in client.cmd_iter('virtual:physical',
                                'virt.vm_info', expr_form='grain'):
        if not info:
            continue
        if not isinstance(info, dict):
            continue
        chunk = {}
        id_ = next(info.iterkeys())
        if hyper:
            if hyper != id_:
                continue
        if not isinstance(info[id_], dict):
            continue
        if 'ret' not in info[id_]:
            continue
        if not isinstance(info[id_]['ret'], dict):
            continue
        data = {}
        for key, val in info[id_]['ret'].items():
            if val['state'] in data:
                data[val['state']].append(key)
            else:
                data[val['state']] = [key]
        chunk[id_] = data
        ret.update(chunk)
        if not quiet:
            __jid_event__.fire_event({'data': chunk, 'outputter': 'virt_list'}, 'progress')

    return ret


def next_hyper():
    '''
    Return the hypervisor to use for the next autodeployed vm. This queries
    the available hypervisors and executes some math the determine the most
    "available" next hypervisor.
    '''
    hyper = _determine_hyper(query(quiet=True))
    print(hyper)
    return hyper


def hyper_info(hyper=None):
    '''
    Return information about the hypervisors connected to this master
    '''
    data = query(hyper, quiet=True)
    for id_ in data:
        if 'vm_info' in data[id_]:
            data[id_].pop('vm_info')
    __jid_event__.fire_event({'data': data, 'outputter': 'nested'}, 'progress')
    return data


def init(
        name,
        cpu,
        mem,
        image,
        hyper=None,
        seed=True,
        nic='default',
        install=True):
    '''
    This routine is used to create a new virtual machine. This routines takes
    a number of options to determine what the newly created virtual machine
    will look like.

    name
        The mandatory name of the new virtual machine. The name option is
        also the minion id, all minions must have an id.

    cpu
        The number of cpus to allocate to this new virtual machine.

    mem
        The amount of memory to allocate tot his virtual machine. The number
        is interpreted in megabytes.

    image
        The network location of the virtual machine image, commonly a location
        on the salt fileserver, but http, https and ftp can also be used.

    hyper
        The hypervisor to use for the new virtual machine, if this is omitted
        Salt will automatically detect what hypervisor to use.

    seed
        Set to False to prevent Salt from seeding the new virtual machine.

    nic
        The nic profile to use, defaults to the "default" nic profile which
        assumes a single network interface per vm associated with the "br0"
        bridge on the master.

    install
        Set to False to prevent Salt from installing a minion on the new vm
        before it spins up.
    '''
    __jid_event__.fire_event({'message': 'Searching for Hypervisors'}, 'progress')
    data = query(hyper, quiet=True)
    # Check if the name is already deployed
    for hyper in data:
        if 'vm_info' in data[hyper]:
            if name in data[hyper]['vm_info']:
                __jid_event__.fire_event({'message': 'Virtual machine {0} is already deployed'.format(name)}, 'progress')
                return 'fail'

    if hyper is None:
        hyper = _determine_hyper(data)

    if hyper not in data or not hyper:
        __jid_event__.fire_event({'message': 'Hypervisor {0} was not found'.format(hyper)}, 'progress')
        return 'fail'

    if seed:
        __jid_event__.fire_event({'message': 'Minion will be preseeded'}, 'progress')
        kv_ = salt.utils.virt.VirtKey(hyper, name, __opts__)
        kv_.authorize()

    client = salt.client.get_local_client(__opts__['conf_file'])

    __jid_event__.fire_event({'message': 'Creating VM {0} on hypervisor {1}'.format(name, hyper)}, 'progress')
    try:
        cmd_ret = client.cmd_iter(
                hyper,
                'virt.init',
                [
                    name,
                    cpu,
                    mem,
                    image,
                    'seed={0}'.format(seed),
                    'nic={0}'.format(nic),
                    'install={0}'.format(install),
                ],
                timeout=600)
    except SaltClientError as client_error:
        # Fall through to ret error handling below
        print(client_error)

    ret = next(cmd_ret)
    if not ret:
        __jid_event__.fire_event({'message': 'VM {0} was not initialized.'.format(name)}, 'progress')
        return 'fail'

    __jid_event__.fire_event({'message': 'VM {0} initialized on hypervisor {1}'.format(name, hyper)}, 'progress')
    return 'good'


def vm_info(name, quiet=False):
    '''
    Return the information on the named vm
    '''
    data = query(quiet=True)
    return _find_vm(name, data, quiet)


def reset(name):
    '''
    Force power down and restart an existing vm
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        __jid_event__.fire_event({'message': 'Failed to find vm {0} to reset'.format(name)}, 'progress')
        return 'fail'
    hyper = next(data.iterkeys())
    try:
        cmd_ret = client.cmd_iter(
                hyper,
                'virt.reset',
                [name],
                timeout=600)
        for comp in cmd_ret:
            ret.update(comp)
        __jid_event__.fire_event({'message': 'Reset VM {0}'.format(name)}, 'progress')
    except SaltClientError as client_error:
        print(client_error)
    return ret


def start(name):
    '''
    Start a named virtual machine
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        __jid_event__.fire_event({'message': 'Failed to find vm {0} to start'.format(name)}, 'progress')
        return 'fail'
    hyper = next(data.iterkeys())
    if data[hyper][name]['state'] == 'running':
        print('VM {0} is already running'.format(name))
        return 'bad state'
    try:
        cmd_ret = client.cmd_iter(
                hyper,
                'virt.start',
                [name],
                timeout=600)
    except SaltClientError as client_error:
        return 'Virtual machine {0} not started: {1}'. format(name, client_error)
    for comp in cmd_ret:
        ret.update(comp)
    __jid_event__.fire_event({'message': 'Started VM {0}'.format(name)}, 'progress')
    return 'good'


def force_off(name):
    '''
    Force power down the named virtual machine
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        print('Failed to find vm {0} to destroy'.format(name))
        return 'fail'
    hyper = next(data.iterkeys())
    if data[hyper][name]['state'] == 'shutdown':
        print('VM {0} is already shutdown'.format(name))
        return'bad state'
    try:
        cmd_ret = client.cmd_iter(
                hyper,
                'virt.destroy',
                [name],
                timeout=600)
    except SaltClientError as client_error:
        return 'Virtual machine {0} could not be forced off: {1}'.format(name, client_error)
    for comp in cmd_ret:
        ret.update(comp)
    __jid_event__.fire_event({'message': 'Powered off VM {0}'.format(name)}, 'progress')
    return 'good'


def purge(name, delete_key=True):
    '''
    Destroy the named vm
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        __jid_event__.fire_event({'error': 'Failed to find vm {0} to purge'.format(name)}, 'progress')
        return 'fail'
    hyper = next(data.iterkeys())
    try:
        cmd_ret = client.cmd_iter(
                hyper,
                'virt.purge',
                [name, True],
                timeout=600)
    except SaltClientError as client_error:
        return 'Virtual machine {0} could not be purged: {1}'.format(name, client_error)

    for comp in cmd_ret:
        ret.update(comp)

    if delete_key:
        skey = salt.key.Key(__opts__)
        skey.delete_key(name)
    __jid_event__.fire_event({'message': 'Purged VM {0}'.format(name)}, 'progress')
    return 'good'


def pause(name):
    '''
    Pause the named vm
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])

    data = vm_info(name, quiet=True)
    if not data:
        __jid_event__.fire_event({'error': 'Failed to find VM {0} to pause'.format(name)}, 'progress')
        return 'fail'
    hyper = next(data.iterkeys())
    if data[hyper][name]['state'] == 'paused':
        __jid_event__.fire_event({'error': 'VM {0} is already paused'.format(name)}, 'progress')
        return 'bad state'
    try:
        cmd_ret = client.cmd_iter(
                hyper,
                'virt.pause',
                [name],
                timeout=600)
    except SaltClientError as client_error:
        return 'Virtual machine {0} could not be pasued: {1}'.format(name, client_error)
    for comp in cmd_ret:
        ret.update(comp)
    __jid_event__.fire_event({'message': 'Paused VM {0}'.format(name)}, 'progress')
    return 'good'


def resume(name):
    '''
    Resume a paused vm
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        __jid_event__.fire_event({'error': 'Failed to find VM {0} to pause'.format(name)}, 'progress')
        return 'not found'
    hyper = next(data.iterkeys())
    if data[hyper][name]['state'] != 'paused':
        __jid_event__.fire_event({'error': 'VM {0} is not paused'.format(name)}, 'progress')
        return 'bad state'
    try:
        cmd_ret = client.cmd_iter(
                hyper,
                'virt.resume',
                [name],
                timeout=600)
    except SaltClientError as client_error:
        return 'Virtual machine {0} could not be resumed: {1}'.format(name, client_error)
    for comp in cmd_ret:
        ret.update(comp)
    __jid_event__.fire_event({'message': 'Resumed VM {0}'.format(name)}, 'progress')
    return 'good'


def migrate(name, target=''):
    '''
    Migrate a vm from one hypervisor to another. This routine will just start
    the migration and display information on how to look up the progress.
    '''
    client = salt.client.get_local_client(__opts__['conf_file'])
    data = query(quiet=True)
    origin_data = _find_vm(name, data, quiet=True)
    try:
        origin_hyper = list(origin_data.keys())[0]
    except IndexError:
        __jid_event__.fire_event({'error': 'Named vm {0} was not found to migrate'.format(name)}, 'progress')
        return ''
    disks = origin_data[origin_hyper][name]['disks']
    if not origin_data:
        __jid_event__.fire_event({'error': 'Named vm {0} was not found to migrate'.format(name)}, 'progress')
        return ''
    if not target:
        target = _determine_hyper(data, origin_hyper)
    if target not in data:
        __jid_event__.fire_event({'error': 'Target hypervisor {0} not found'.format(origin_data)}, 'progress')
        return ''
    try:
        client.cmd(target, 'virt.seed_non_shared_migrate', [disks, True])
        jid = client.cmd_async(origin_hyper,
                               'virt.migrate_non_shared',
                               [name, target])
    except SaltClientError as client_error:
        return 'Virtual machine {0} could not be migrated: {1}'.format(name, client_error)

    msg = ('The migration of virtual machine {0} to hypervisor {1} has begun, '
           'and can be tracked via jid {2}. The ``salt-run virt.query`` '
           'runner can also be used, the target vm will be shown as paused '
           'until the migration is complete.').format(name, target, jid)
    __jid_event__.fire_event({'message': msg}, 'progress')
