'''
General management functions for salt, tools like seeing what hosts are up
and what hosts are down
'''

import yaml
import distutils.version

# Import salt libs
import salt.key
import salt.client


def status(output=True):
    '''
    Print the status of all known salt minions
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    minions = client.cmd('*', 'test.ping', timeout=__opts__['timeout'])

    key = salt.key.Key(__opts__)
    keys = key.list_keys()

    ret = {}
    ret['up'] = sorted(minions)
    ret['down'] = sorted(set(keys['minions']) - set(minions))
    if output:
        print(yaml.safe_dump(ret, default_flow_style=False))
    return ret


def down():
    '''
    Print a list of all the down or unresponsive salt minions
    '''
    ret = status(output=False).get('down', [])
    for minion in ret:
        print(minion)
    return ret


def up():  # pylint: disable-msg=C0103
    '''
    Print a list of all of the minions that are up
    '''
    ret = status(output=False).get('up', [])
    for minion in ret:
        print(minion)
    return ret


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

    version_status = {}

    master_version = distutils.version.StrictVersion(salt.__version__)
    for minion in minions:
        minion_version = distutils.version.StrictVersion(minions[minion])
        ver_diff = cmp(minion_version, master_version)

        if ver_diff not in version_status:
            version_status[ver_diff] = []
        version_status[ver_diff].append(minion)

    for key in version_status:
        print labels[key]
        for minion in sorted(version_status[key]):
            print '\t', minion
