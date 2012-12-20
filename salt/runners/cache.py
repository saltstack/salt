'''
Return cached data from minions
'''
# Import python libs
import os

# Import salt libs
import salt.output
import salt.payload


def _cdata():
    '''
    Return the cached data from the minions
    '''
    ret = {}
    serial = salt.payload.Serial(__opts__)
    mdir = os.path.join(__opts__['cachedir'], 'minions')
    for minion in os.listdir(mdir):
        path = os.path.join(mdir, minion, 'data.p')
        if os.path.isfile(path):
            with open(path) as fp_:
                ret[minion] = serial.loads(fp_.read())
    return ret


def grains(minion=None):
    '''
    Return cached grains for all minions or a specific minion
    '''
    data = _cdata()
    if minion:
        if minion in data:
            salt.output({minion: data[minion]['grains']}, 'grains')
            return {minion: data[minion]['grains']}
    ret = {}
    for minion in data:
        ret[minion] = data[minion]['grains']
        salt.output({minion: data[minion]['grains']}, 'grains')
    return ret


def pillar(minion=None):
    '''
    Return cached grains for all minions or a specific minion
    '''
    data = _cdata()
    if minion:
        if minion in data:
            salt.output({minion: data[minion]['pillar']})
            return {minion: data[minion]['pillar']}
    ret = {}
    for minion in data:
        ret[minion] = data[minion]['pillar']
        salt.output({minion: data[minion]['pillar']})
    return ret
