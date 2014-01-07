# -*- coding: utf-8 -*-
'''
A runner to access data from the salt mine
'''
# Import python libs
import os

# Import salt libs
import salt.payload
import salt.utils.minions
import salt.utils


def get(tgt, fun, tgt_type='glob'):
    '''
    Gathers the data from the specified minions' mine, pass in the target,
    function to look up and the target type

    CLI Example::

        salt-run mine.get '*' network.interfaces
    '''
    ret = {}
    serial = salt.payload.Serial(__opts__)
    checker = salt.utils.minions.CkMinions(__opts__)
    minions = checker.check_minions(
            tgt,
            tgt_type)
    for minion in minions:
        mine = os.path.join(
                __opts__['cachedir'],
                'minions',
                minion,
                'mine.p')
        try:
            with salt.utils.fopen(mine) as fp_:
                fdata = serial.load(fp_).get(fun)
                if fdata:
                    ret[minion] = fdata
        except Exception:
            continue
    return ret
