from __future__ import print_function
import re
import pprint

CONVERSION = {
    'ansible_ssh_host': 'host',
    'ansible_ssh_port': 'port',
    'ansible_ssh_user': 'user',
    'ansible_ssh_pass': 'passwd',
    'ansible_sudo_pass': 'passwd',
    'ansible_ssh_private_key_file': 'priv'
}

class Inventory(object):
    def __init__(self, hosts='hosts'):
        self.groups = dict()
        self.hostvars = dict()
        blocks = re.compile('^\[.*\]$')
        hostvar = re.compile('^\[.*:vars\]$')
        with open(hosts) as config:
            for line in config.read().split('\n'):
                if not line or line.startswith('#'):
                    continue
                if blocks.match(line):
                    if hostvar.match(line):
                        hostvars = True
                        groups = False
                        varname = line[:-5].strip('[')
                    else:
                        hostvars = False
                        groups = True
                        varname = line.strip('[]')
                    continue
                if hostvars:
                    key, value = self._parse_hostvars_line(line)
                    if varname not in self.hostvars:
                        self.hostvars[varname] = dict()
                    self.hostvars[varname][key] = value
                if groups:
                    if varname in self.groups and self.groups[varname]:
                        self.groups[varname].update(self._parse_host_line(line))
                    else:
                        self.groups[varname] = self._parse_host_line(line)

    def _parse_host_line(self, line):
        line_args = line.split(' ')
        name = line_args[0]
        host = {line_args[0]: dict()}
        for arg in line_args[1:]:
            key, value = arg.split('=')
            host[name][CONVERSION[key]] = value
        return host

    def _parse_hostvars_line(self, line):
        return line.split('=')

    def get_groups(self):
        return self.groups
                
    def get_hostvars(self):
        return self.hostvars


if __name__ == '__main__':
    inventory = Inventory()
    print(pprint.pformat(inventory.get_groups()))
    print(pprint.pformat(inventory.get_hostvars()))
