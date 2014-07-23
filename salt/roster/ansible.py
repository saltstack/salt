from __future__ import print_function
import os
import re
import fnmatch
import shlex
import pprint
import salt.loader
import salt.utils


CONVERSION = {
    'ansible_ssh_host': 'host',
    'ansible_ssh_port': 'port',
    'ansible_ssh_user': 'user',
    'ansible_ssh_pass': 'passwd',
    'ansible_sudo_pass': 'passwd',
    'ansible_ssh_private_key_file': 'priv'
}

import logging
log = logging.getLogger(__name__)

def targets(tgt, tgt_type='glob', **kwargs):
    if __opts__.get('inventory_file', False) is not False:
        hosts = __opts__.get('inventory_file')
    elif os.path.isfile(__opts__['conf_file']) or not os.path.exists(__opts__['conf_file']):
        hosts = os.path.join(
                os.path.dirname(__opts__['conf_file']),
                'hosts')
    else:
        hosts = os.path.join(__opts__['conf_file'], 'hosts')

    rend = salt.loader.render(__opts__, {})
    imatcher = Inventory(hosts)
    return getattr(imatcher, 'get_{0}'.format(tgt_type))(tgt)


class Inventory(object):
    def __init__(self, hosts='/etc/salt/hosts'):
        self.groups = dict()
        self.hostvars = dict()
        self.parents = dict()
        blocks = re.compile('^\[.*\]$')
        hostvar = re.compile('^\[([^:]+):vars\]$')
        parents = re.compile('^\[([^:]+):children\]$')
        with salt.utils.fopen(hosts) as config:
            for line in config.read().split('\n'):
                if not line or line.startswith('#'):
                    continue
                if blocks.match(line):
                    if hostvar.match(line):
                        proc = '_parse_hostvars_line'
                        varname = hostvar.match(line).groups()[0]
                    elif parents.match(line):
                        proc = '_parse_parents_line'
                        varname = parents.match(line).groups()[0]
                    else:
                        proc = '_parse_group_line'
                        varname = line.strip('[]')
                    continue
                getattr(self, proc)(line, varname)

    def _parse_group_line(self, line, varname):
        line_args = shlex.split(line)
        name = line_args[0]
        host = {line_args[0]: dict()}
        for arg in line_args[1:]:
            key, value = arg.split('=')
            host[name][CONVERSION[key]] = value
        if self.groups.get(varname, ''):
            self.groups[varname].update(host)
        else:
            self.groups[varname] = host

    def _parse_hostvars_line(self, line, varname):
        key, value = line.split('=')
        if varname not in self.hostvars:
            self.hostvars[varname] = dict()
        self.hostvars[varname][key] = value

    def _parse_parents_line(self, line, varname):
        if varname not in self.parents:
            self.parents[varname] = []
        self.parents[varname].append(line)

    def get_glob(self, tgt):
        ret = dict()
        for key, value in self.groups.items():
            for host, info in value.items():
                if fnmatch.fnmatch(host, tgt):
                    ret[host] = info
        return ret

    def _get_parent(self, parent_nodegroup):
        ret = dict()
        for nodegroup in self.parents[parent_nodegroup]:
            if nodegroup in self.parents:
                ret.update(self._get_parent(nodegroup))
            elif nodegroup in self.groups:
                ret.update(self.groups[nodegroup])
        return ret

    def get_nodegroup(self, tgt):
        ret = dict()
        for nodegroup in self.groups:
            if fnmatch.fnmatch(nodegroup, tgt):
                ret.update(self.groups[nodegroup])
        for parent_nodegroup in self.parents:
            if fnmatch.fnmatch(parent_nodegroup, tgt):
              ret.update(self._get_parent(parent_nodegroup))
        return ret
                
    def get_hostvars(self):
        return self.hostvars
