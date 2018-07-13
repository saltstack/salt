# -*- coding: utf-8 -*-
'''
This is the default set of matcher functions.

NOTE: These functions are converted to methods on the Matcher module during master and minion startup.
This is why they all take `self` but are not defined inside a `class:` declaration.
'''
from __future__ import absolute_import, print_function, unicode_literals

import re
import fnmatch
import logging
from salt.ext import six

from salt.defaults import DEFAULT_TARGET_DELIM

import salt.utils.data
import salt.utils.minions
import salt.utils.network
import salt.loader
if six.PY3:
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddres

HAS_RANGE = False
try:
    import seco.range
    HAS_RANGE = True
except ImportError:
    pass

log = logging.getLogger(__name__)

def confirm_top(self, match, data, nodegroups=None):
    '''
    Takes the data passed to a top file environment and determines if the
    data matches this minion
    '''
    matcher = 'compound'
    if not data:
        log.error('Received bad data when setting the match from the top '
                    'file')
        return False
    for item in data:
        if isinstance(item, dict):
            if 'match' in item:
                matcher = item['match']
    if hasattr(self, matcher + '_match'):
        funcname = '{0}_match'.format(matcher)
        if matcher == 'nodegroup':
            return getattr(self, funcname)(match, nodegroups)
        return getattr(self, funcname)(match)
    else:
        log.error('Attempting to match with unknown matcher: %s', matcher)
        return False

def glob_match(self, tgt):
    '''
    Returns true if the passed glob matches the id
    '''
    if not isinstance(tgt, six.string_types):
        return False

    return fnmatch.fnmatch(self.opts['id'], tgt)

def pcre_match(self, tgt):
    '''
    Returns true if the passed pcre regex matches
    '''
    return bool(re.match(tgt, self.opts['id']))

def list_match(self, tgt):
    '''
    Determines if this host is on the list
    '''
    if isinstance(tgt, six.string_types):
        tgt = tgt.split(',')
    return bool(self.opts['id'] in tgt)

def grain_match(self, tgt, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Reads in the grains glob match
    '''
    log.debug('grains target: %s', tgt)
    if delimiter not in tgt:
        log.error('Got insufficient arguments for grains match '
                    'statement from master')
        return False
    return salt.utils.data.subdict_match(
        self.opts['grains'], tgt, delimiter=delimiter
    )

def grain_pcre_match(self, tgt, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Matches a grain based on regex
    '''
    log.debug('grains pcre target: %s', tgt)
    if delimiter not in tgt:
        log.error('Got insufficient arguments for grains pcre match '
                    'statement from master')
        return False
    return salt.utils.data.subdict_match(
        self.opts['grains'], tgt, delimiter=delimiter, regex_match=True)

def data_match(self, tgt):
    '''
    Match based on the local data store on the minion
    '''
    if self.functions is None:
        utils = salt.loader.utils(self.opts)
        self.functions = salt.loader.minion_mods(self.opts, utils=utils)
    comps = tgt.split(':')
    if len(comps) < 2:
        return False
    val = self.functions['data.getval'](comps[0])
    if val is None:
        # The value is not defined
        return False
    if isinstance(val, list):
        # We are matching a single component to a single list member
        for member in val:
            if fnmatch.fnmatch(six.text_type(member).lower(), comps[1].lower()):
                return True
        return False
    if isinstance(val, dict):
        if comps[1] in val:
            return True
        return False
    return bool(fnmatch.fnmatch(
        val,
        comps[1],
    ))

def pillar_match(self, tgt, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Reads in the pillar glob match
    '''
    log.debug('pillar target: %s', tgt)
    if delimiter not in tgt:
        log.error('Got insufficient arguments for pillar match '
                    'statement from master')
        return False
    return salt.utils.data.subdict_match(
        self.opts['pillar'], tgt, delimiter=delimiter
    )

def pillar_pcre_match(self, tgt, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Reads in the pillar pcre match
    '''
    log.debug('pillar PCRE target: %s', tgt)
    if delimiter not in tgt:
        log.error('Got insufficient arguments for pillar PCRE match '
                    'statement from master')
        return False
    return salt.utils.data.subdict_match(
        self.opts['pillar'], tgt, delimiter=delimiter, regex_match=True
    )

def pillar_exact_match(self, tgt, delimiter=':'):
    '''
    Reads in the pillar match, no globbing, no PCRE
    '''
    log.debug('pillar target: %s', tgt)
    if delimiter not in tgt:
        log.error('Got insufficient arguments for pillar match '
                    'statement from master')
        return False
    return salt.utils.data.subdict_match(self.opts['pillar'],
                                    tgt,
                                    delimiter=delimiter,
                                    exact_match=True)

def ipcidr_match(self, tgt):
    '''
    Matches based on IP address or CIDR notation
    '''
    try:
        # Target is an address?
        tgt = ipaddress.ip_address(tgt)
    except:  # pylint: disable=bare-except
        try:
            # Target is a network?
            tgt = ipaddress.ip_network(tgt)
        except:  # pylint: disable=bare-except
            log.error('Invalid IP/CIDR target: %s', tgt)
            return []
    proto = 'ipv{0}'.format(tgt.version)

    grains = self.opts['grains']

    if proto not in grains:
        match = False
    elif isinstance(tgt, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
        match = six.text_type(tgt) in grains[proto]
    else:
        match = salt.utils.network.in_subnet(tgt, grains[proto])

    return match

def range_match(self, tgt):
    '''
    Matches based on range cluster
    '''
    if HAS_RANGE:
        range_ = seco.range.Range(self.opts['range_server'])
        try:
            return self.opts['grains']['fqdn'] in range_.expand(tgt)
        except seco.range.RangeException as exc:
            log.debug('Range exception in compound match: %s', exc)
            return False
    return False

def compound_match(self, tgt):
    '''
    Runs the compound target check
    '''
    nodegroups = self.opts.get('nodegroups', {})

    if not isinstance(tgt, six.string_types) and not isinstance(tgt, (list, tuple)):
        log.error('Compound target received that is neither string, list nor tuple')
        return False
    log.debug('compound_match: %s ? %s', self.opts['id'], tgt)
    ref = {'G': 'grain',
            'P': 'grain_pcre',
            'I': 'pillar',
            'J': 'pillar_pcre',
            'L': 'list',
            'N': None,      # Nodegroups should already be expanded
            'S': 'ipcidr',
            'E': 'pcre'}
    if HAS_RANGE:
        ref['R'] = 'range'

    results = []
    opers = ['and', 'or', 'not', '(', ')']

    if isinstance(tgt, six.string_types):
        words = tgt.split()
    else:
        # we make a shallow copy in order to not affect the passed in arg
        words = tgt[:]

    while words:
        word = words.pop(0)
        target_info = salt.utils.minions.parse_target(word)

        # Easy check first
        if word in opers:
            if results:
                if results[-1] == '(' and word in ('and', 'or'):
                    log.error('Invalid beginning operator after "(": %s', word)
                    return False
                if word == 'not':
                    if not results[-1] in ('and', 'or', '('):
                        results.append('and')
                results.append(word)
            else:
                # seq start with binary oper, fail
                if word not in ['(', 'not']:
                    log.error('Invalid beginning operator: %s', word)
                    return False
                results.append(word)

        elif target_info and target_info['engine']:
            if 'N' == target_info['engine']:
                # if we encounter a node group, just evaluate it in-place
                decomposed = salt.utils.minions.nodegroup_comp(target_info['pattern'], nodegroups)
                if decomposed:
                    words = decomposed + words
                continue

            engine = ref.get(target_info['engine'])
            if not engine:
                # If an unknown engine is called at any time, fail out
                log.error(
                    'Unrecognized target engine "%s" for target '
                    'expression "%s"', target_info['engine'], word
                )
                return False

            engine_args = [target_info['pattern']]
            engine_kwargs = {}
            if target_info['delimiter']:
                engine_kwargs['delimiter'] = target_info['delimiter']

            results.append(
                six.text_type(getattr(self, '{0}_match'.format(engine))(*engine_args, **engine_kwargs))
            )

        else:
            # The match is not explicitly defined, evaluate it as a glob
            results.append(six.text_type(self.glob_match(word)))

    results = ' '.join(results)
    log.debug('compound_match %s ? "%s" => "%s"', self.opts['id'], tgt, results)
    try:
        return eval(results)  # pylint: disable=W0123
    except Exception:
        log.error(
            'Invalid compound target: %s for results: %s', tgt, results)
        return False
    return False

def nodegroup_match(self, tgt, nodegroups):
    '''
    This is a compatibility matcher and is NOT called when using
    nodegroups for remote execution, but is called when the nodegroups
    matcher is used in states
    '''
    if tgt in nodegroups:
        return self.compound_match(
            salt.utils.minions.nodegroup_comp(tgt, nodegroups)
        )
    return False
