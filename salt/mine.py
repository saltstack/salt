# -*- coding: utf-8 -*-
'''
Salt-Mine module to interact with salt-mine cache
'''
# Import python libs
import os

# Import salt libs
import salt.payload
import salt.utils.minions
import salt.utils


def get(tgt, fun, tgt_type='glob', opts=None):
    '''
    Gathers the data from the specified minions' mine, pass in the target,
    function to look up and the target type
    '''
    ret = {}
    serial = salt.payload.Serial(opts)
    checker = salt.utils.minions.CkMinions(opts)
    minions = checker.check_minions(
            tgt,
            tgt_type)
    for minion in minions:
        mine = os.path.join(
                opts['cachedir'],
                'minions',
                minion,
                'mine.p')
        try:
            with salt.utils.fopen(mine, 'rb') as fp_:
                fdata = serial.load(fp_).get(fun)
                if fdata:
                    ret[minion] = fdata
        except Exception:
            continue
    return ret
