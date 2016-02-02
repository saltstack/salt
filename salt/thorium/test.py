'''
A simple test module, writes matches to disk to verify activity
'''

# Import python libs
import os
import json

# Import salt libs
import salt.utils


def save(name):
    '''
    Save the register to /tmp/<name>
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    fn_ = os.path.join('/tmp', name)
    with salt.utils.fopen(fn_, 'w+') as fp_:
        fp_.write(json.dump(__reg__))
    return ret
