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
    data = query(hyper)
    if hyper:
        if not hyper in data:
            return
    else:
        hyper = _determine_hyper(data)
    
    client = salt.client.LocalClient(__opts__['conf_file'])

    cmd_ret = client.cmd_iter(
            hyper,
            'virt.init',
            [name, cpu, mem, image],
            timeout=600)

    ret = {}

    for info in cmd_ret:
        print(info)
        ret.update(info)

    return ret

