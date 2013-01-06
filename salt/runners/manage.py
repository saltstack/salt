'''
General management functions for salt, tools like seeing what hosts are up
and what hosts are down
'''

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
