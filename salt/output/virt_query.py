def output(data):
    '''
    '''
    out = ''
    for id_ in data:
        out += '{0}\n'.format(id_)
        for vm_ in data[id_]['vm_info']:
            out += '    {0}\n'.format(vm_)
            vm_data = data[id_]['vm_info'][vm_]
            if 'cpu' in vm_data:
                out += '      CPUS: {0}\n'.format(vm_data['cpu'])
            if 'mem' in vm_data:
                out += '      MEMORY: {0}\n'.format(vm_data['mem'])
            if 'state' in vm_data:
                out += '      STATE: {0}\n'.format(vm_data['state'])
    return out
