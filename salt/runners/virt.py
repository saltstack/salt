# -*- coding: utf-8 -*-
'''
Control virtual machines via Salt
'''

# Import Salt libs
import salt.client
import salt.output
import salt.utils.virt


def _determine_hyper(data, omit=''):
    '''
    Determine what the most resource free hypervisor is based on the given
    data
    '''
    # This is just checking for the hyper with the most free ram, this needs
    # to be much more complicated.
    hyper = ''
    bestmem = 0
    bestcpu = 0
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
    Query the virtual machines
    '''
    ret = {}
    client = salt.client.LocalClient(__opts__['conf_file'])
    for info in client.cmd_iter('virtual:physical',
                                'virt.full_info', expr_form='grain'):
        if not info:
            continue
        if not isinstance(info, dict):
            continue
        chunk = {}
        id_ = info.keys()[0]
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


def list(hyper=None, quiet=False):
    '''
    List the virtual machines on each hyper
    '''
    ret = {}
    client = salt.client.LocalClient(__opts__['conf_file'])
    for info in client.cmd_iter('virtual:physical',
                                'virt.vm_info', expr_form='grain'):
        if not info:
            continue
        if not isinstance(info, dict):
            continue
        chunk = {}
        id_ = info.keys()[0]
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
        for k, v in info[id_]['ret'].items():
            if v['state'] in data:
                data[v['state']].append(k)
            else:
                data[v['state']] = [k]
        chunk[id_] = data
        ret.update(chunk)
        if not quiet:
            salt.output.display_output(chunk, 'virt_list', __opts__)

    return ret


def next_hyper():
    '''
    Return the hypervisor to use for the next autodeployed vm
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
    Initialize a new vm
    '''
    print('Searching for Hypervisors')
    data = query(hyper, quiet=True)
    # Check if the name is already deployed
    for hyper in data:
        if 'vm_info' in data[hyper]:
            if name in data[hyper]['vm_info']:
                print('Virtual machine {0} is already deployed'.format(name))
                return 'fail'
    if hyper:
        if hyper not in data:
            print('Hypervisor {0} was not found'.format(hyper))
            return 'fail'
    else:
        hyper = _determine_hyper(data)

    if seed:
        print('Minion will be preseeded')
        kv = salt.utils.virt.VirtKey(hyper, name, __opts__)
        kv.authorize()

    client = salt.client.LocalClient(__opts__['conf_file'])

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
                'install={0}'.format(install)
            ],
            timeout=600)

    next(cmd_ret)
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
    client = salt.client.LocalClient(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        print('Failed to find vm {0} to reset'.format(name))
        return 'fail'
    hyper = data.keys()[0]
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
    client = salt.client.LocalClient(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        print('Failed to find vm {0} to start'.format(name))
        return 'fail'
    hyper = data.keys()[0]
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
    client = salt.client.LocalClient(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        print('Failed to find vm {0} to destroy'.format(name))
        return 'fail'
    hyper = data.keys()[0]
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


def purge(name):
    '''
    Destroy the named vm
    '''
    ret = {}
    client = salt.client.LocalClient(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        print('Failed to find vm {0} to purge'.format(name))
        return 'fail'
    hyper = data.keys()[0]
    cmd_ret = client.cmd_iter(
            hyper,
            'virt.purge',
            [name, True],
            timeout=600)
    for comp in cmd_ret:
        ret.update(comp)
    print('Purged VM {0}'.format(name))
    return 'good'


def pause(name):
    '''
    Pause the named vm
    '''
    ret = {}
    client = salt.client.LocalClient(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        print('Failed to find VM {0} to pause'.format(name))
        return 'fail'
    hyper = data.keys()[0]
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
    client = salt.client.LocalClient(__opts__['conf_file'])
    data = vm_info(name, quiet=True)
    if not data:
        print('Failed to find VM {0} to pause'.format(name))
        return 'not found'
    hyper = data.keys()[0]
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
    the migration and display information on how to look up the progress
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    data = query(quiet=True)
    origin_data = _find_vm(name, data, quiet=True)
    origin_hyper = origin_data.keys()[0]
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
    print client.cmd_async(origin_hyper,
                           'virt.migrate_non_shared',
                           [name, target])
