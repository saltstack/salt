# -*- coding: utf-8 -*-
'''
Parses roster entries out of Host directives from SSH known_hosts

.. code-block:: bash

    salt-ssh --roster sshknownhosts '*' -r "echo hi"
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import os
import fnmatch
import re
import copy
import logging

# Import Salt libs
import salt.utils.files
import salt.utils.stringutils
from salt.ext import six

log = logging.getLogger(__name__)


def _get_ssh_known_hosts_file(opts):
    '''
    :return: Path to the .ssh/known_hosts file - usually <home>/.ssh/known_hosts
    '''
    ssh_known_hosts_file = opts.get('ssh_known_hosts_file')
    if not os.path.isfile(ssh_known_hosts_file):
        log.error('Cannot find SSH known_hosts file')
        raise IOError('Cannot find SSH known_hosts file')
    if not os.access(ssh_known_hosts_file, os.R_OK):
        log.error('Cannot access SSH known_hosts file: %s', ssh_known_hosts_file)
        raise IOError('Cannot access SSH known_hosts file: {}'.format(ssh_known_hosts_file))
    return ssh_known_hosts_file


def _parse_ssh_known_hosts_line(line):
    '''
    :return: Dict that contain the three fields from a known_hosts line
    '''
    line_unicode = salt.utils.stringutils.to_unicode(line)
    fields = line_unicode.split(" ")

    if len(fields) < 3:
        log.warn("Not enough fields found in known_hosts in line : %s", line)
        return None

    fields = fields[:3]

    names, keytype, key = fields
    names = names.split(",")

    return {'names': names, 'keytype': keytype, 'key': key}


def parse_ssh_known_hosts(lines):
    '''
    Parses lines from the SSH known_hosts to create roster targets.

    :param lines: Individual lines from the ssh known_hosts file
    :return: Dictionary of targets in similar style to the flat roster
    '''

    targets_ = {}
    for line in lines:
        host_key = _parse_ssh_known_hosts_line(line)

        for host in host_key['names']:
            targets_.update({host: {'host': host}})

    return targets_


def targets(tgt, tgt_type='glob'):
    '''
    Return the targets from the flat yaml file, checks opts for location but
    defaults to /etc/salt/roster
    '''
    ssh_known_hosts_file = _get_ssh_known_hosts_file(__opts__)
    with salt.utils.files.fopen(ssh_known_hosts_file, 'r') as hostfile:
        all_minions = parse_ssh_known_hosts([line.rstrip() for line in hostfile])
    rmatcher = RosterMatcher(all_minions, tgt, tgt_type)
    return rmatcher.targets()


class RosterMatcher(object):
    '''
    Matcher for the roster data structure
    '''
    def __init__(self, raw, tgt, tgt_type):
        self.tgt = tgt
        self.tgt_type = tgt_type
        self.raw = raw

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
