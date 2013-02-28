'''
Control virtual machines via Salt
'''

# Import python libs
import os
import subprocess

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


def gen_hyper_keys(
        country='US',
        state='Utah',
        locality='Salt Lake City',
        organization = 'Salted'):
    '''
    Generate the keys to be used by libvirt hypervisors, this routine gens
    the keys and applies them to the pillar for the hypervisor minions
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    key_dir = os.path.join(
            __opts__['pki_dir'],
            'libvirt')
    if not os.path.isdir(key_dir):
        os.makedirs(key_dir)
    cakey = os.path.join(key_dir, 'cakey.pem')
    cacert = os.path.join(key_dir, 'cacert.pem')
    cainfo = os.path.join(key_dir, 'ca.info')
    if not os.path.isfile(cainfo):
        with open(cainfo, 'w+') as fp_:
            fp_.write('cn = salted\nca\ncert_signing_key')
    if not os.path.isfile(cakey):
        subprocess.call(
                'certtool --generate-privkey > {0}'.format(cakey),
                shell=True)
    if not os.path.isfile(cacert):
        cmd = ('certtool --generate-self-signed --load-privkey {0} '
               '--template {1} --outfile {2}').format(cakey, cainfo, cacert)
        subprocess.call(cmd, shell=True)
    hypers = set()
    for info in client.cmd_iter(
            'virtual:physical',
            'virt.freecpu',
            expr_form='grain'):
        if not info:
            continue
        if not isinstance(info, dict):
            continue
        hypers.add(info.keys()[0])
    for info in client.cmd_iter(
            list(hypers),
            'grains.items',
            expr_form='list'):
        grains = info[info.keys()[0]]['ret']
        sub_dir = os.path.join(key_dir, grains['id'])
        if not os.path.isdir(sub_dir):
            os.makedirs(sub_dir)
        priv = os.path.join(sub_dir, 'serverkey.pem')
        cert = os.path.join(sub_dir, 'servercert.pem')
        srvinfo = os.path.join(sub_dir, 'server.info')
        cpriv = os.path.join(sub_dir, 'clientkey.pem')
        ccert = os.path.join(sub_dir, 'clientcert.pem')
        clientinfo = os.path.join(sub_dir, 'client.info')
        if not os.path.isfile(srvinfo):
            with open(srvinfo, 'w+') as fp_:
                infodat = ('organization = salted\ncn = {0}\ntls_www_server'
                           '\nencryption_key\nsigning_key').format(
                                   grains['fqdn'])
                fp_.write(infodat)
        if not os.path.isfile(priv):
            subprocess.call(
                    'certtool --generate-privkey > {0}'.format(priv),
                    shell=True)
        if not os.path.isfile(cert):
            cmd = ('certtool --generate-certificate --load-privkey {0} '
                   '--load-ca-certificate {1} --load-ca-privkey {2} '
                   '--template {3} --outfile {4}'
                   ).format(priv, cacert, cakey, srvinfo, cert)
            subprocess.call(cmd, shell=True)
        if not os.path.isfile(clientinfo):
            with open(clientinfo, 'w+') as fp_:
                infodat = ('country = {0}\nstate = {1}\nlocality = '
                           '{2}\norganization = {3}\ncn = {4}\n'
                           'tls_www_client\nencryption_key\nsigning_key'
                           ).format(
                                   country,
                                   state,
                                   locality,
                                   organization,
                                   grains['fqdn'])
                fp_.write(infodat)
        if not os.path.isfile(cpriv):
            subprocess.call(
                    'certtool --generate-privkey > {0}'.format(cpriv),
                    shell=True)
        if not os.path.isfile(ccert):
            cmd = ('certtool --generate-certificate --load-privkey {0} '
                   '--load-ca-certificate {1} --load-ca-privkey {2} '
                   '--template {3} --outfile {4}'
                   ).format(cpriv, cacert, cakey, clientinfo, ccert)
            subprocess.call(cmd, shell=True)


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


def init(name, cpu, mem, image, hyper=None, seed=True):
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
        if not hyper in data:
            print('Hypervisor {0} was not found'.format(hyper))
            return 'fail'
    else:
        hyper = _determine_hyper(data)
    
    client = salt.client.LocalClient(__opts__['conf_file'])

    print('Creating VM {0} on hypervisor {1}'.format(name, hyper))
    cmd_ret = client.cmd_iter(
            hyper,
            'virt.init',
            [name, cpu, mem, image, 'seed={0}'.format(seed)],
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
