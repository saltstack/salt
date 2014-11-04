# -*- coding: utf-8 -*-
'''
Control virtual machines via Salt
'''

# Import python libs
from __future__ import print_function

# Import Salt libs
import salt.client
import salt.output
import salt.utils.virt
import salt.key


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
                salt.output.display_output(
                        ret,
                        'nested',
                        __opts__)
            return ret
    return {}


def query(hyper=None, quiet=False):
    '''
    Query the virtual machines. When called without options all hypervisors
    are detected and a full query is returned. A single hypervisor can be
    passed in to specify an individual hypervisor to query.
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    for info in client.cmd_iter('virtual:physical',
                                'virt.full_info', expr_form='grain'):
        if not info:
            continue
        if not isinstance(info, dict):
            continue
        chunk = {}
        id_ = info.iterkeys().next()
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
            salt.output.display_output(chunk, 'virt_query', __opts__)

    return ret


def list(hyper=None, quiet=False):  # pylint: disable=redefined-builtin
    '''
    List the virtual machines on each hyper, this is a simplified query,
    showing only the virtual machine names belonging to each hypervisor.
    A single hypervisor can be passed in to specify an individual hypervisor
    to list.
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    for info in client.cmd_iter('virtual:physical',
                                'virt.vm_info', expr_form='grain'):
        if not info:
            continue
        if not isinstance(info, dict):
            continue
        chunk = {}
        id_ = info.iterkeys().next()
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
            salt.output.display_output(chunk, 'virt_list', __opts__)

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
    salt.output.display_output(data, 'nested', __opts__)
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
    print('Searching for Hypervisors')
    data = query(hyper, quiet=True)
    # Check if the name is already deployed
    for hyper in data:
        if 'vm_info' in data[hyper]:
            if name in data[hyper]['vm_info']:
                print('Virtual machine {0} is already deployed'.format(name))
                return 'fail'

    if hyper is None:
        hyper = _determine_hyper(data)

    if hyper not in data or not hyper:
        print('Hypervisor {0} was not found'.format(hyper))
        return 'fail'

    if seed:
        print('Minion will be preseeded')
        kv_ = salt.utils.virt.VirtKey(hyper, name, __opts__)
        kv_.authorize()

    client = salt.client.get_local_client(__opts__['conf_file'])

    print('Creating VM {0} on hypervisor {1}'.format(name, hyper))
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

    ret = next(cmd_ret)
    if not ret:
        print('VM {0} was not initialized.'.format(name))
        return 'fail'

    print('VM {0} initialized on hypervisor {1}'.format(name, hyper))
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
        print('Failed to find vm {0} to reset'.format(name))
        return 'fail'
    hyper = data.iterkeys().next()
    cmd_ret = client.cmd_iter(
            hyper,
            'virt.reset',
            [name],
            timeout=600)
    for comp in cmd_ret:
        ret.update(comp)
    print('Reset VM {0}'.format(name))
    return ret


def start(name):
    '''
    Start a named virtual machine
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        print('Failed to find vm {0} to start'.format(name))
        return 'fail'
    hyper = data.iterkeys().next()
    if data[hyper][name]['state'] == 'running':
        print('VM {0} is already running'.format(name))
        return 'bad state'
    cmd_ret = client.cmd_iter(
            hyper,
            'virt.start',
            [name],
            timeout=600)
    for comp in cmd_ret:
        ret.update(comp)
    print('Started VM {0}'.format(name))
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
    hyper = data.iterkeys().next()
    if data[hyper][name]['state'] == 'shutdown':
        print('VM {0} is already shutdown'.format(name))
        return'bad state'
    cmd_ret = client.cmd_iter(
            hyper,
            'virt.destroy',
            [name],
            timeout=600)
    for comp in cmd_ret:
        ret.update(comp)
    print('Powered off VM {0}'.format(name))
    return 'good'


def purge(name, delete_key=True):
    '''
    Destroy the named vm
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        print('Failed to find vm {0} to purge'.format(name))
        return 'fail'
    hyper = data.iterkeys().next()
    cmd_ret = client.cmd_iter(
            hyper,
            'virt.purge',
            [name, True],
            timeout=600)
    for comp in cmd_ret:
        ret.update(comp)

    if delete_key:
        skey = salt.key.Key(__opts__)
        skey.delete_key(name)
    print('Purged VM {0}'.format(name))
    return 'good'


def pause(name):
    '''
    Pause the named vm
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])

    data = vm_info(name, quiet=True)
    if not data:
        print('Failed to find VM {0} to pause'.format(name))
        return 'fail'
    hyper = data.iterkeys().next()
    if data[hyper][name]['state'] == 'paused':
        print('VM {0} is already paused'.format(name))
        return 'bad state'
    cmd_ret = client.cmd_iter(
            hyper,
            'virt.pause',
            [name],
            timeout=600)
    for comp in cmd_ret:
        ret.update(comp)
    print('Paused VM {0}'.format(name))
    return 'good'


def resume(name):
    '''
    Resume a paused vm
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        print('Failed to find VM {0} to pause'.format(name))
        return 'not found'
    hyper = data.iterkeys().next()
    if data[hyper][name]['state'] != 'paused':
        print('VM {0} is not paused'.format(name))
        return 'bad state'
    cmd_ret = client.cmd_iter(
            hyper,
            'virt.resume',
            [name],
            timeout=600)
    for comp in cmd_ret:
        ret.update(comp)
    print('Resumed VM {0}'.format(name))
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
        origin_hyper = origin_data.iterkeys().next()
    except StopIteration:
        print('Named vm {0} was not found to migrate'.format(name))
        return ''
    disks = origin_data[origin_hyper][name]['disks']
    if not origin_data:
        print('Named vm {0} was not found to migrate'.format(name))
        return ''
    if not target:
        target = _determine_hyper(data, origin_hyper)
    if target not in data:
        print('Target hypervisor {0} not found'.format(origin_data))
        return ''
    client.cmd(target, 'virt.seed_non_shared_migrate', [disks, True])
    jid = client.cmd_async(origin_hyper,
                           'virt.migrate_non_shared',
                           [name, target])

    msg = ('The migration of virtual machine {0} to hypervisor {1} has begun, '
           'and can be tracked via jid {2}. The ``salt-run virt.query`` '
           'runner can also be used, the target vm will be shown as paused '
           'until the migration is complete.').format(name, target, jid)
    print(msg)
