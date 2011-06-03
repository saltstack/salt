'''
General management functions for salt, tools like seeing what hosts are up
and what hosts are down
'''

# Import salt modules
import salt.client
import salt.cli.key

def down():
    '''
    Print a list of all the down or unresponsive salt minions
    '''
    client = salt.client.LocalClient(__opts__['config'])
    key = salt.cli.key(__opts__)
    minions = client.cmd('*', 'test.ping', timeout=1)
    keys = key._keys('acc')
    for minion in minions:
        keys.remove(minion)
    for minion in sorted(keys):
        print minion
