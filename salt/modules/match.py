'''
The match module allows for match routines to be run and determine target
specs.
'''

import salt.minion

__func_alias__ = {
    'list_': 'list'
}

def compound(tgt):
    '''
    Return True if the minion matches the given compound target

    CLI Example::

        salt '*' match.compound 'L@cheese,foo and *'
    '''
    matcher = salt.minion.Matcher(__opts__, __salt__)
    try:
        return matcher.compound_match(tgt)
    except Exception:
        return False


def ipcidr(tgt):
    '''
    Return True if the minion matches the given ipcidr target

    CLI Example::

        salt '*' match.ipcidr '192.168.44.0/24'
    '''
    matcher = salt.minion.Matcher(__opts__, __salt__)
    try:
        return matcher.ipcidr_match(tgt)
    except Exception:
        return False


def pillar(tgt):
    '''
    Return True if the minion matches the given pillar target

    CLI Example::

        salt '*' match.pillar 'cheese:foo'
    '''
    matcher = salt.minion.Matcher(__opts__, __salt__)
    try:
        return matcher.pillar_match(tgt)
    except Exception:
        return False


def data(tgt):
    '''
    Return True if the minion matches the given data target

    CLI Example::

        salt '*' match.data 'spam:eggs'
    '''
    matcher = salt.minion.Matcher(__opts__, __salt__)
    try:
        return matcher.data_match(tgt)
    except Exception:
        return False


def grain_pcre(tgt):
    '''
    Return True if the minion matches the given grain_pcre target

    CLI Example::

        salt '*' match.grain_pcre 'os:Fedo.*'
    '''
    matcher = salt.minion.Matcher(__opts__, __salt__)
    try:
        return matcher.grain_pcre_match(tgt)
    except Exception:
        return False


def grain(tgt):
    '''
    Return True if the minion matches the given grain target

    CLI Example::

        salt '*' match.grain 'os:Ubuntu'
    '''
    matcher = salt.minion.Matcher(__opts__, __salt__)
    try:
        return matcher.grain_match(tgt)
    except Exception:
        return False


def list_(tgt):
    '''
    Return True if the minion matches the given list target

    CLI Example::

        salt '*' match.list 'server1,server2'
    '''
    matcher = salt.minion.Matcher(__opts__, __salt__)
    try:
        return matcher.list_match(tgt)
    except Exception:
        return False


def pcre(tgt):
    '''
    Return True if the minion matches the given pcre target

    CLI Example::

        salt '*' match.pcre '.*'
    '''
    matcher = salt.minion.Matcher(__opts__, __salt__)
    try:
        return matcher.pcre_match(tgt)
    except Exception:
        return False


def glob(tgt):
    '''
    Return True if the minion matches the given glob target

    CLI Example::

        salt '*' match.glob '*'
    '''
    matcher = salt.minion.Matcher(__opts__, __salt__)
    try:
        return matcher.glob_match(tgt)
    except Exception:
        return False
