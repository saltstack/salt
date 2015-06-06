# -*- coding: utf-8 -*-
'''
Read in an Ansible inventory file or script

Flat inventory files should be in the regular ansible inventory format.

.. code-block:: ini

    [servers]
    salt.gtmanfred.com ansible_ssh_user=gtmanfred ansible_ssh_host=127.0.0.1 ansible_ssh_port=22 ansible_ssh_pass='password'

    [desktop]
    home ansible_ssh_user=gtmanfred ansible_ssh_host=12.34.56.78 ansible_ssh_port=23 ansible_ssh_pass='password'

    [computers:children]
    desktop
    servers

    [names:vars]
    http_port=80

then salt-ssh can be used to hit any of them

.. code-block:: bash

    [~]# salt-ssh all test.ping
    salt.gtmanfred.com:
        True
    home:
        True
    [~]# salt-ssh desktop test.ping
    home:
        True
    [~]# salt-ssh computers test.ping
    salt.gtmanfred.com:
        True
    home:
        True
    [~]# salt-ssh salt.gtmanfred.com test.ping
    salt.gtmanfred.com:
        True

There is also the option of specifying a dynamic inventory, and generating it on the fly

.. code-block:: bash

    #!/bin/bash
    echo '{
      "servers": {
        "hosts": [
          "salt.gtmanfred.com"
        ]
      },
      "desktop": {
        "hosts": [
          "home"
        ]
      },
      "computers": {
        "hosts":{},
        "children": [
          "desktop",
          "servers"
        ]
      },
      "_meta": {
        "hostvars": {
          "salt.gtmanfred.com": {
            "ansible_ssh_user": "gtmanfred",
            "ansible_ssh_host": "127.0.0.1",
            "ansible_sudo_pass": "password",
            "ansible_ssh_port": 22
          },
          "home": {
            "ansible_ssh_user": "gtmanfred",
            "ansible_ssh_host": "12.34.56.78",
            "ansible_sudo_pass": "password",
            "ansible_ssh_port": 23
          }
        }
      }
    }'

This is the format that an inventory script needs to output to work with ansible, and thus here.

.. code-block:: bash

    [~]# salt-ssh --roster-file /etc/salt/hosts salt.gtmanfred.com test.ping
    salt.gtmanfred.com:
            True

Any of the [groups] or direct hostnames will return.  The 'all' is special, and returns everything.
'''
# Import Python libs
from __future__ import absolute_import
import os
import re
import fnmatch
import shlex
import json
import subprocess

# Import Salt libs
import salt.utils
from salt.roster import get_roster_file

# Import 3rd-party libs
import salt.ext.six as six

CONVERSION = {
    'ansible_ssh_host': 'host',
    'ansible_ssh_port': 'port',
    'ansible_ssh_user': 'user',
    'ansible_ssh_pass': 'passwd',
    'ansible_sudo_pass': 'sudo',
    'ansible_ssh_private_key_file': 'priv'
}


def targets(tgt, tgt_type='glob', **kwargs):
    '''
    Return the targets from the ansible inventory_file
    Default: /etc/salt/roster
    '''
    if tgt == 'all':
        tgt = '*'

    inventory_file = get_roster_file(__opts__)

    if os.path.isfile(inventory_file) and os.access(inventory_file, os.X_OK):
        imatcher = Script(tgt, tgt_type='glob', inventory_file=inventory_file)
    else:
        imatcher = Inventory(tgt, tgt_type='glob', inventory_file=inventory_file)
    return imatcher.targets()


class Target(object):
    def targets(self):
        '''
        Execute the correct tgt_type routine and return
        '''
        try:
            return getattr(self, 'get_{0}'.format(self.tgt_type))()
        except AttributeError:
            return {}

    def get_glob(self):
        '''
        Return minions that match via glob
        '''
        ret = dict()
        for key, value in six.iteritems(self.groups):
            for host, info in six.iteritems(value):
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
        '''
        Recursively resolve all [*:children] group blocks
        '''
        ret = dict()
        for nodegroup in self.parents[parent_nodegroup]:
            if nodegroup in self.parents:
                ret.update(self._get_parent(nodegroup))
            elif nodegroup in self.groups:
                ret.update(self.groups[nodegroup])
        return ret


class Inventory(Target):
    '''
    Matcher for static inventory files
    '''
    def __init__(self, tgt, tgt_type='glob', inventory_file='/etc/salt/roster'):
        self.tgt = tgt
        self.tgt_type = tgt_type
        self.groups = dict()
        self.hostvars = dict()
        self.parents = dict()
        blocks = re.compile(r'^\[.*\]$')
        hostvar = re.compile(r'^\[([^:]+):vars\]$')
        parents = re.compile(r'^\[([^:]+):children\]$')
        with salt.utils.fopen(inventory_file) as config:
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

                    getattr(self, proc)(line, varname)

                continue

    def _parse_group_line(self, line, varname):
        '''
        Parse lines in the inventory file that are under the same group block
        '''
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
        '''
        Parse lines in the inventory file that are under the same [*:vars] block
        '''
        key, value = line.split('=')
        if varname not in self.hostvars:
            self.hostvars[varname] = dict()
        self.hostvars[varname][key] = value

    def _parse_parents_line(self, line, varname):
        '''
        Parse lines in the inventory file that are under the same [*:children] block
        '''
        if varname not in self.parents:
            self.parents[varname] = []
        self.parents[varname].append(line)


class Script(Target):
    '''
    Matcher for Inventory scripts
    '''
    def __init__(self, tgt, tgt_type='glob', inventory_file='/etc/salt/roster'):
        self.tgt = tgt
        self.tgt_type = tgt_type
        inventory, error = subprocess.Popen([inventory_file], shell=True, stdout=subprocess.PIPE).communicate()
        self.inventory = json.loads(salt.utils.to_str(inventory))
        self.meta = self.inventory.get('_meta', {})
        self.groups = dict()
        self.hostvars = dict()
        self.parents = dict()
        for key, value in six.iteritems(self.inventory):
            if key == '_meta':
                continue
            if 'hosts' in value:
                self._parse_groups(key, value['hosts'])
            if 'children' in value:
                self._parse_parents(key, value['children'])
            if 'hostvars' in value:
                self._parse_hostvars(key, value['hostvars'])

    def _parse_groups(self, key, value):
        '''
        Parse group data from inventory_file
        '''
        host = dict()
        if key not in self.groups:
            self.groups[key] = dict()
        for server in value:
            tmp = self.meta.get('hostvars', {}).get(server, False)
            if tmp is not False:
                if server not in host:
                    host[server] = dict()
                for tmpkey, tmpval in six.iteritems(tmp):
                    host[server][CONVERSION[tmpkey]] = tmpval
                if 'sudo' in host[server]:
                    host[server]['passwd'], host[server]['sudo'] = host[server]['sudo'], True

        self.groups[key].update(host)

    def _parse_hostvars(self, key, value):
        '''
        Parse hostvars data from inventory_file
        '''
        if key not in self.hostvars:
            self.hostvars[key] = dict()
        self.hostvars[key] = value

    def _parse_parents(self, key, value):
        '''
        Parse children data from inventory_file
        '''
        if key not in self.parents:
            self.parents[key] = []
        self.parents[key].extend(value)
