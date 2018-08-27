# -*- coding: utf-8 -*-
'''
Roster matching by various criteria (glob, pcre, etc)
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import fnmatch
import logging
import re
import copy

# Try to import range from https://github.com/ytoolshed/range
HAS_RANGE = False
try:
    import seco.range
    HAS_RANGE = True
except ImportError:
    pass
# pylint: enable=import-error

# Import Salt libs
from salt.ext import six


log = logging.getLogger(__name__)


def targets(conditioned_raw, tgt, tgt_type, ipv='ipv4'):
    rmatcher = RosterMatcher(conditioned_raw, tgt, tgt_type, ipv)
    return rmatcher.targets()


class RosterMatcher(object):
    '''
    Matcher for the roster data structure
    '''
    def __init__(self, raw, tgt, tgt_type, ipv='ipv4'):
        self.tgt = tgt
        self.tgt_type = tgt_type
        self.raw = raw
        self.ipv = ipv

    def targets(self):
        '''
        Execute the correct tgt_type routine and return
        '''
        try:
            return getattr(self, 'ret_{0}_minions'.format(self.tgt_type))()
        except AttributeError:
            return {}

    def ret_glob_minions(self):
        '''
        Return minions that match via glob
        '''
        minions = {}
        for minion in self.raw:
            if fnmatch.fnmatch(minion, self.tgt):
                data = self.get_data(minion)
                if data:
                    minions[minion] = data.copy()
        return minions

    def ret_pcre_minions(self):
        '''
        Return minions that match via pcre
        '''
        minions = {}
        for minion in self.raw:
            if re.match(self.tgt, minion):
                data = self.get_data(minion)
                if data:
                    minions[minion] = data.copy()
        return minions

    def ret_list_minions(self):
        '''
        Return minions that match via list
        '''
        minions = {}
        if not isinstance(self.tgt, list):
            self.tgt = self.tgt.split(',')
        for minion in self.raw:
            if minion in self.tgt:
                data = self.get_data(minion)
                if data:
                    minions[minion] = data.copy()
        return minions

    def ret_nodegroup_minions(self):
        '''
        Return minions which match the special list-only groups defined by
        ssh_list_nodegroups
        '''
        minions = {}
        nodegroup = __opts__.get('ssh_list_nodegroups', {}).get(self.tgt, [])
        if not isinstance(nodegroup, list):
            nodegroup = nodegroup.split(',')
        for minion in self.raw:
            if minion in nodegroup:
                data = self.get_data(minion)
                if data:
                    minions[minion] = data.copy()
        return minions

    def ret_range_minions(self):
        '''
        Return minions that are returned by a range query
        '''
        if HAS_RANGE is False:
            raise RuntimeError("Python lib 'seco.range' is not available")

        minions = {}
        range_hosts = _convert_range_to_list(self.tgt, __opts__['range_server'])

        for minion in self.raw:
            if minion in range_hosts:
                data = self.get_data(minion)
                if data:
                    minions[minion] = data.copy()
        return minions

    def get_data(self, minion):
        '''
        Return the configured ip
        '''
        ret = copy.deepcopy(__opts__.get('roster_defaults', {}))
        if isinstance(self.raw[minion], six.string_types):
            ret.update({'host': self.raw[minion]})
            return ret
        elif isinstance(self.raw[minion], dict):
            ret.update(self.raw[minion])
            return ret
        return False


def _convert_range_to_list(tgt, range_server):
    '''
    convert a seco.range range into a list target
    '''
    r = seco.range.Range(range_server)
    try:
        return r.expand(tgt)
    except seco.range.RangeException as err:
        log.error('Range server exception: %s', err)
        return []
