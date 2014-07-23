from __future__ import print_function
import os
import re
import fnmatch
import shlex
import pprint
import json
import salt.loader
import salt.utils
import subprocess


CONVERSION = {
    'ansible_ssh_host': 'host',
    'ansible_ssh_port': 'port',
    'ansible_ssh_user': 'user',
    'ansible_ssh_pass': 'passwd',
    'ansible_sudo_pass': 'sudo',
    'ansible_ssh_private_key_file': 'priv'
}

import logging
log = logging.getLogger(__name__)

def targets(tgt, tgt_type='glob', **kwargs):
    if tgt == 'all':
        tgt = '*':
    if __opts__.get('inventory_file', False) is not False:
        hosts = __opts__.get('inventory_file')
    elif os.path.isfile(__opts__['conf_file']) or not os.path.exists(__opts__['conf_file']):
        hosts = os.path.join(
                os.path.dirname(__opts__['conf_file']),
                'hosts')
    else:
        hosts = os.path.join(__opts__['conf_file'], 'hosts')

    rend = salt.loader.render(__opts__, {})
    if os.path.isfile(hosts) and os.access(hosts, os.X_OK):
        imatcher = Script(tgt, tgt_type='glob', hosts=hosts)
    else:
        imatcher = Inventory(tgt, tgt_type='glob', inventory_file=hosts)
    return imatcher.targets()


class Inventory(object):
    def __init__(self, tgt, tgt_type='glob', inventory_file='/etc/salt/hosts'):
        self.tgt = tgt
        self.tgt_type = tgt_type
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
        if 'sudo' in host[name]:
            host[name]['passwd'], host[name]['sudo'] = host[name]['sudo'], True
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

    def targets(self):
        try:
            return getattr(self, 'get_{0}'.format(self.tgt_type))()
        except AttributeError:
            return {}


    def get_glob(self):
        ret = dict()
        for key, value in self.groups.items():
            for host, info in value.items():
                if fnmatch.fnmatch(host, self.tgt):
                    ret[host] = info
        for nodegroup in self.groups:
            if fnmatch.fnmatch(nodegroup, self.tgt):
                ret.update(self.groups[nodegroup])
        for parent_nodegroup in self.parents:
            if fnmatch.fnmatch(parent_nodegroup, self.tgt):
              ret.update(self._get_parent(parent_nodegroup))
        return ret

    def _get_parent(self, parent_nodegroup):
        ret = dict()
        for nodegroup in self.parents[parent_nodegroup]:
            if nodegroup in self.parents:
                ret.update(self._get_parent(nodegroup))
            elif nodegroup in self.groups:
                ret.update(self.groups[nodegroup])
        return ret
                
    def get_hostvars(self):
        return self.hostvars


class Script(Inventory):
    def __init__(self, inventory_file='/etc/salt/hosts2'):
        self.tgt = tgt
        self.tgt_type = tgt_type
        inventory, error = subprocess.Popen([inventory_file], shell=True, stdout=subprocess.PIPE).communicate()
        self.inventory = json.loads(inventory)
        self.meta = self.inventory.get('_meta', {})
        self.groups = dict()
        self.hostvars = dict()
        self.parents = dict()
        for key, value in self.inventory.items():
            if key == '_meta':
                continue
            if 'hosts' in value:
                self._parse_groups(key, value['hosts'])
            if 'children' in value:
                self._parse_parents(key, value['children'])
            if 'hostvars' in value:
                self._parse_hostvars(key, value['hostvars'])

    def _parse_groups(self, key, value):
        host = dict()
        if key not in self.groups:
            self.groups[key] = dict()
        for server in value:
            tmp = self.meta.get('hostvars', {}).get(server, False)
            if tmp is not False:
                if server not in host:
                    host[server] = dict()
                for tmpkey, tmpval in tmp.items():
                    host[server][CONVERSION[tmpkey]] = tmpval
                if 'sudo' in host[server]:
                    host[server]['passwd'], host[server]['sudo'] = host[server]['sudo'], True

        self.groups[key].update(host)

    def _parse_hostvars(self, key, value):
        if key not in self.hostvars:
            self.hostvars[key] = dict()
        self.hostvars[key] = value

    def _parse_parents(self, key, value):
        if key not in self.parents:
            self.parents[key] = []
        self.parents[key].extend(value)
