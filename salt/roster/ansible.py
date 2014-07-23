from __future__ import print_function
import os
import re
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
        blocks = re.compile('^\[.*\]$')
        hostvar = re.compile('^\[.*:vars\]$')
        with salt.utils.fopen(hosts) as config:
            for line in config.read().split('\n'):
                if not line or line.startswith('#'):
                    continue
                if blocks.match(line):
                    if hostvar.match(line):
                        proc = '_parse_hostvars_line'
                        varname = line[:-5].strip('[')
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

    def get_glob(self, tgt):
        ret = dict()
        for key, value in self.groups.items():
            ret.update(value)
        return ret

    def get_nodegroup(self, tgt):
        return self.groups[tgt]
                
    def get_hostvars(self):
        return self.hostvars


if __name__ == '__main__':
    inventory = Inventory()
    print(pprint.pformat(inventory.get_groups()))
    print(pprint.pformat(inventory.get_hostvars()))
