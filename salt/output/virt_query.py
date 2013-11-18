# -*- coding: utf-8 -*-
'''
virt.query outputter
'''


def output(data):
    '''
    Display output for the salt-run virt.query function
    '''
    out = ''
    for id_ in data:
        out += '{0}\n'.format(id_)
        for vm_ in data[id_]['vm_info']:
            out += '  {0}\n'.format(vm_)
            vm_data = data[id_]['vm_info'][vm_]
            if 'cpu' in vm_data:
                out += '    CPU: {0}\n'.format(vm_data['cpu'])
            if 'mem' in vm_data:
                out += '    Memory: {0}\n'.format(vm_data['mem'])
            if 'state' in vm_data:
                out += '    State: {0}\n'.format(vm_data['state'])
            if 'graphics' in vm_data:
                if vm_data['graphics'].get('type', '') == 'vnc':
                    out += '    Graphics: vnc - {0}:{1}\n'.format(
                            id_,
                            vm_data['graphics']['port'])
            if 'disks' in vm_data:
                for disk, d_data in vm_data['disks'].items():
                    out += '    Disk - {0}:\n'.format(disk)
                    out += '      Size: {0}\n'.format(d_data['disk size'])
                    out += '      File: {0}\n'.format(d_data['file'])
                    out += '      File Format: {0}\n'.format(d_data['file format'])
            if 'nics' in vm_data:
                for mac in vm_data['nics']:
                    out += '    Nic - {0}:\n'.format(mac)
                    out += '      Source: {0}\n'.format(vm_data['nics'][mac]['source'][vm_data['nics'][mac]['source'].keys()[0]])
                    out += '      Type: {0}\n'.format(vm_data['nics'][mac]['type'])
    return out
