# -*- coding: utf-8 -*-
'''
A Mysql-Keystore that manages salt-keys in a mysql-database
'''
import re

minions = [ 'minion' + str(x)  for x in xrange(5) ]
minions_pre = [ 'minion' + str(x)  for x in xrange(6,10) ]
minions_rej = [ 'minion' + str(x)  for x in xrange(11,15) ]

def name_match(match, full=False):
    '''
    Accept a glob which to match the of a key and return the key's location
    '''

    matches = list_keys()
    ret = {}
    for status, keys in matches.items():
        for key in sorted(keys):
            yes = re.match(match + '$', key)
            if yes:
                if status not in ret:
                    ret[status] = []
                ret[status].append(yes.group(0))
    return ret


def dict_match(match_dict):
    '''
    Accept a dictionary of keys and return the current state of the
    specified keys
    '''
    print("dict_match")

def local_keys():
    minions = [ 'minion' + str(x)  for x in xrange(10) ]
    return {'local': minions }

def list_keys():
    '''
    Return a dict of managed keys and what the key status are
    '''
    return {'minions' : minions,
            'minions_pre' : minions_pre,
            'minions_rejected' : minions_rej}


def all_keys():
    '''
    Merge managed keys with local keys
    '''
    return list_keys()

def list_status(match):
    '''
    Return a dict of managed keys under a named status
    '''

    if match.startswith('acc'):
        return minions
    elif match.startswith('pre') or match.startswith('un'):
        return minions_pre
    elif match.startswith('rej'):
        return minions_rej
    elif match.startswith('all'):
        return self.all_keys()

def key_str(match):
    '''
    Return the specified public key or keys based on a glob
    '''
    ret = {}
    minions = name_match(match)

    for status, minion_list in minions.items():
        ret[status] = {}
        for minion in minion_list:
            ret[status][minion] = 'ABCSAMPLE_PUBKEY'
    return ret


def key_str_all(self):
    '''
    Return all managed key strings
    '''
    print("key_str_all")

def accept(match=None, match_dict=None, include_rejected=False):
    '''
    Accept public keys. If "match" is passed, it is evaluated as a glob.
    Pre-gathered matches can also be passed via "match_dict".
    '''
    print("accept")

def accept_all():
    '''
    Accept all keys in pre
    '''
    print("accept_all")

def delete_key(match=None, match_dict=None):
    '''
    Delete public keys. If "match" is passed, it is evaluated as a glob.
    Pre-gathered matches can also be passed via "match_dict".
    '''
    print("delete_key")

def delete_all(self):
    '''
    Delete all keys
    '''
    print("delete_all")

def reject(match=None, match_dict=None, include_accepted=False):
    '''
    Reject public keys. If "match" is passed, it is evaluated as a glob.
    Pre-gathered matches can also be passed via "match_dict".
    '''
    print("reject")

def reject_all(self):
    '''
    Reject all keys in pre
    '''
    print("reject_all")

def finger(match):
    '''
    Return the fingerprint for a specified key
    '''
    print("finger")


def finger_all(self):
    '''
    Return fingerprins for all keys
    '''
    print("finger_all")

if __name__ == '__main__':
    name_match('minion1')
