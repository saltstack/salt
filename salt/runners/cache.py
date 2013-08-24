'''
Return cached data from minions
'''
# Import python libs
import os

# Import salt libs
import salt.utils
import salt.output
import salt.payload


def _cdata():
    '''
    Return the cached data from the minions
    '''
    ret = {}
    serial = salt.payload.Serial(__opts__)
    mdir = os.path.join(__opts__['cachedir'], 'minions')
    try:
        for minion in os.listdir(mdir):
            path = os.path.join(mdir, minion, 'data.p')
            if os.path.isfile(path):
                with salt.utils.fopen(path) as fp_:
                    ret[minion] = serial.loads(fp_.read())
    except (OSError, IOError):
        return ret
    return ret


def grains(minion=None):
    '''
    Return cached grains for all minions or a specific minion
    '''
    data = _cdata()
    if minion:
        if minion in data:
            salt.output.display_output({minion: data[minion]['grains']},
                                       None, __opts__)
            return {minion: data[minion]['grains']}
    ret = {}
    for minion in data:
        ret[minion] = data[minion]['grains']
        salt.output.display_output({minion: data[minion]['grains']},
                                   None, __opts__)
    return ret


def pillar(minion=None):
    '''
    Return cached grains for all minions or a specific minion
    '''
    data = _cdata()
    if minion:
        if minion in data:
            salt.output.display_output({minion: data[minion]['pillar']},
                                       None, __opts__)
            return {minion: data[minion]['pillar']}
    ret = {}
    for minion in data:
        ret[minion] = data[minion]['pillar']
        salt.output.display_output({minion: data[minion]['pillar']},
                                   None, __opts__)
    return ret
