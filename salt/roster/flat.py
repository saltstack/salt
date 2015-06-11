# -*- coding: utf-8 -*-
'''
Read in the roster from a flat file using the renderer system
'''
from __future__ import absolute_import

# Import python libs
import fnmatch
import re

# Import Salt libs
import salt.loader
from salt.template import compile_template
from salt.ext.six import string_types
from salt.roster import get_roster_file

import logging
log = logging.getLogger(__name__)


def targets(tgt, tgt_type='glob', **kwargs):
    '''
    Return the targets from the flat yaml file, checks opts for location but
    defaults to /etc/salt/roster
    '''
    template = get_roster_file(__opts__)

    rend = salt.loader.render(__opts__, {})
    raw = compile_template(template, rend, __opts__['renderer'], **kwargs)
    conditioned_raw = {}
    for minion in raw:
        conditioned_raw[str(minion)] = raw[minion]
    rmatcher = RosterMatcher(conditioned_raw, tgt, tgt_type, 'ipv4')
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
        log.info('minions list: {0}'.format(minions))
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

    def ret_list_minions(self):
        '''
        Return minions that match via list
        '''
        minions = {}
        for minion in self.raw:
            if minion in self.tgt:
                data = self.get_data(minion)
                if data:
                    minions[minion] = data
        return minions

    def get_data(self, minion):
        '''
        Return the configured ip
        '''
        if isinstance(self.raw[minion], string_types):
            return {'host': self.raw[minion]}
        if isinstance(self.raw[minion], dict):
            return self.raw[minion]
        return False
