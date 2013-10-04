# -*- coding: utf-8 -*-
'''
Read in the roster from a flat file using the renderer system
'''

# Import python libs
import os
import fnmatch
import re

# Import Salt libs
import salt.loader
from salt.template import compile_template


def targets(tgt, tgt_type='glob', **kwargs):
    '''
    Return the targets from the flat yaml file, checks opts for location but
    defaults to /etc/salt/roster
    '''
    if __opts__.get('roster_file'):
        template = __opts__.get('roster_file')
    elif os.path.isfile(__opts__['conf_file']) or not os.path.exists(__opts__['conf_file']):
        template = os.path.join(
                os.path.dirname(__opts__['conf_file']),
                'roster')
    else:
        template = os.path.join(__opts__['conf_file'], 'roster')
    rend = salt.loader.render(__opts__, {})
    raw = compile_template(template, rend, __opts__['renderer'], **kwargs)
    rmatcher = RosterMatcher(raw, tgt, tgt_type, 'ipv4')
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
                    minions[minion] = data
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
                    minions[minion] = data
        return minions

    def get_data(self, minion):
        '''
        Return the configured ip
        '''
        if isinstance(self.raw[minion], basestring):
            return {'host': self.raw[minion]}
        if isinstance(self.raw[minion], dict):
            return self.raw[minion]
        return False
