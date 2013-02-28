'''
Load up the libvirt keys into pillar for a given minion if said keys have
been generated using the libvirt key runner.
'''

# Import python libs
import os


def ext_pillar(pillar, command):
    '''
    Read in the generated libvirt keys
    '''
    key_dir = os.path.join(
            __opts__['pki_dir'],
            'libvirt',
            __grains__['id'])
    if not os.path.isdir(key_dir):
        # No keys have been generated
        return {}
    ret = {}
    for key in os.listdir(key_dir):
        if not key.endswith('.pem'):
            continue
        fn_ = os.path.join(key_dir, key)
        with open(fn_, 'r') as fp_:
            ret['libvirt.{0}'.format(key)] = fp_.read()
    return ret
