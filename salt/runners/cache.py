'''
Return cached data from minions
'''
# Import salt libs
import salt.utils.master
import salt.output
import salt.payload


def grains(minion=None):
    '''
    Return cached grains for all minions or a specific minion
    '''
    pillar_util = salt.utils.master.MasterPillarUtil('*', 'glob',
                                                use_cached_grains=True,
                                                grains_fallback=False,
                                                opts=__opts__)
    cached_grains = pillar_util.get_minion_grains()

    if minion:
        if minion in cached_grains:
            salt.output.display_output({minion: cached_grains[minion]},
                                       None, __opts__)
            return {minion: cached_grains[minion]}
    for minion_id in cached_grains:
        salt.output.display_output({minion_id: cached_grains[minion_id]},
                                   None, __opts__)
    return cached_grains


def pillar(minion=None):
    '''
    Return cached grains for all minions or a specific minion
    '''
    pillar_util = salt.utils.master.MasterPillarUtil('*', 'glob',
                                                use_cached_grains=True,
                                                grains_fallback=False,
                                                use_cached_pillar=True,
                                                pillar_fallback=False,
                                                opts=__opts__)
    cached_pillar = pillar_util.get_minion_pillar()

    if minion:
        if minion in cached_pillar:
            salt.output.display_output({minion: cached_pillar[minion]},
                                       None, __opts__)
            return {minion: cached_pillar[minion]}
    for minion_id in cached_pillar:
        salt.output.display_output({minion_id: cached_pillar[minion_id]},
                                   None, __opts__)
    return cached_pillar
