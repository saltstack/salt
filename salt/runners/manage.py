'''
General management functions for salt, tools like seeing what hosts are up
and what hosts are down
'''

import distutils.version

# Import salt libs
import salt.key
import salt.client


def down():
    '''
    Print a list of all the down or unresponsive salt minions
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    minions = client.cmd('*', 'test.ping', timeout=__opts__['timeout'])

    key = salt.key.Key(__opts__)
    keys = key.list_keys()

    ret = sorted(set(keys['minions']) - set(minions))
    for minion in ret:
        print(minion)
    return ret


def up():  # pylint: disable-msg=C0103
    '''
    Print a list of all of the minions that are up
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    minions = client.cmd('*', 'test.ping', timeout=__opts__['timeout'])

    for minion in sorted(minions):
        print(minion)

    return sorted(minions)


def versions():
    '''
    Check the version of active minions
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    minions = client.cmd('*', 'test.version', timeout=__opts__['timeout'])

    labels = {
        -1: 'Minion requires update',
        0: 'Up to date',
        1: 'Minion newer than master',
    }

    sorted_minions = {}

    master_version = distutils.version.StrictVersion(salt.__version__)
    for minion in minions:
        minion_version = distutils.version.StrictVersion(minions[minion])
        ver_diff = cmp(minion_version, master_version)

        if ver_diff not in sorted_minions:
            sorted_minions[ver_diff] = []
        sorted_minions[ver_diff].append(minion)

    for key in sorted_minions:
        print labels[key]
        for minion in sorted(sorted_minions[key]):
            print '\t', minion
