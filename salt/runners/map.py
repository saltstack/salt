# -*- coding: utf-8 -*-
'''

General map/reduce style salt-runner for aggregating identical results returned by several different minions.
Aggregated results are sorted by the size of the minion pools returning identical results.

Useful for playing the game: " some of these things are not like the others... " when identifying discrepancies
in a large infrastructure managed by salt.

'''

import salt.client


def hash(*args, **kwargs):
    '''
    Return the aggregated and sorted results from a salt command submitted by a
    salt runner...

    CLI Example #1: ( functionally equivalent to "salt-run manage.up" )

        salt-run map.hash "*" test.ping

    CLI Example #2: ( find an "outlier" minion config file )

        salt-run map.hash "*" file.get_hash /etc/salt/minion

    '''
    import hashlib

    tgt = args[0]
    cmd = args[1]

    client = salt.client.LocalClient(__opts__['conf_file'])
    minions = client.cmd(tgt, cmd, args[2:], timeout=__opts__['timeout'])
    ret = {}
    # hash minion return values as a string
    for minion in minions:
        h = hashlib.sha256(str(minions[minion])).hexdigest()
        if not h in ret:
            ret[h] = []

        ret[h].append(minion)

    for k in sorted(ret, key=lambda k: len(ret[k]), reverse=True):
        # return aggregated results, sorted by size of the hash pool
        # TODO:  use a custom outputter for better display results

        print 'minion pool:\n--------'
        print ret[k]
        print 'size:\n-----'
        print '    ' + str(len(ret[k]))
        print 'result:\n-------'
        print '    ' + str(minions[ret[k][0]])
        print '\n'

    return ret
