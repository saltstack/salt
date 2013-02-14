'''
Control virtual machines via Salt
'''

# Import Salt libs
import salt.client
import salt.output


def _determine_hyper(data):
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
        if not isinstance(comps, dict):
            continue
        if comps.get('freemem', 0) > bestmem:
            bestmem = comps['freemem']
            hyper = hv_
    return hyper


def query(hyper=None, quiet=False):
    '''
    Query the virtual machines
    '''
    ret = {}
    client = salt.client.LocalClient(__opts__['conf_file'])
    for info in client.cmd_iter('virtual:physical', 'virt.full_info', expr_form='grain'):
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
        if not 'ret' in info[id_]:
            continue
        chunk[id_] = info[id_]['ret']
        ret.update(chunk)
        if not quiet:
            salt.output.display_output(chunk, 'virt_query', __opts__)

    return ret


def next_hyper():
    '''
    Return the hypervisor to use for the next autodeployed vm
    '''
    hyper = _determine_hyper(query(quiet=True))
    print(hyper)
    return hyper


def init(name, cpu, mem, image, hyper=None):
    '''
    Initialize a new vm
    '''
    data = query(hyper, quiet=True)
    if hyper:
        if not hyper in data:
            print('Hypervisor {0} was not found'.format(hyper))
            return 'fail'
    else:
        hyper = _determine_hyper(data)
    
    client = salt.client.LocalClient(__opts__['conf_file'])

    cmd_ret = client.cmd_iter(
            hyper,
            'virt.init',
            [name, cpu, mem, image],
            timeout=600)

    for info in cmd_ret:
        print('VM {0} initialized on hypervisor {1}'.format(name, hyper))

    return 'good'


def vm_info(name, quiet=False):
    '''
    Return the information on the named vm
    '''
    data = query(quiet=True)
    for hv_ in data:
        if name in data[hv_].get('vm_info', {}):
            ret = {hv_: {name: data[hv_]['vm_info'][name]}}
            if not quiet:
                salt.output.display_output(
                        ret,
                        'nested',
                        __opts__)
            return ret
    return {}


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
    if data[hyper][name]['state'] == 'running':
        print('VM {0} is already running'.format(name))
        return 'bad state'
    hyper = data.keys()[0]
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
    if data[hyper][name]['state'] == 'shutdown':
        print('VM {0} is already shutdown'.format(name))
        return'bad state'
    hyper = data.keys()[0]
    cmd_ret = client.cmd_iter(
            hyper,
            'virt.destroy',
            [name],
            timeout=600)
    for comp in cmd_ret:
        ret.update(comp)
    print('Powered off VM {0}'.format())
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
