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
    Save the register to <salt cachedir>/thorium/saves/<name>
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    tgt_dir = os.path.join(__opts__['cachedir'], 'thorium', 'saves')
    fn_ = os.path.join(tgt_dir, name)
    if not os.isdir(tgt_dir):
        os.makedirs(tgt_dir)
    with salt.utils.fopen(fn_, 'w+') as fp_:
        fp_.write(json.dump(__reg__))
    return ret
