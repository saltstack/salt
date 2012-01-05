'''
Manage the information in the hosts file
'''

import os

def __get_hosts_filename():
    if __grains__['kernel'].startswith('Windows'):
        return 'C:\Windows\System32\drivers\etc\hosts'
    else:
        return '/etc/hosts'

def list_hosts():
    '''
    Return the hosts found in the hosts file in this format::

        {'<ip addr>': ['alias1', 'alias2', ...]}

    CLI Example::

        salt '*' hosts.list_hosts
    '''
    hfn = __get_hosts_filename()
    ret = {}
    if not os.path.isfile(hfn):
        return ret
    for line in open(hfn).readlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            continue
        comps = line.split()
        if comps[0] in ret:
            # maybe log a warning ?
            ret[comps[0]].extend(comps[1:])
        else:
            ret[comps[0]] = comps[1:]
    return ret


def get_ip(host):
    '''
    Return the ip associated with the named host

    CLI Example::
        salt '*' hosts.get_ip <hostname>
    '''
    hosts = list_hosts()
    if not hosts:
        return ''
    # Look for the op
    for addr in hosts:
        if host in hosts[addr]:
            return addr
    # ip not found
    return ''


def get_alias(ip):
    '''
    Return the list of aliases associated with an ip

    CLI Example::
        salt '*' hosts.get_alias <ip addr>
    '''
    hosts = list_hosts()
    if ip in hosts:
        return hosts[ip]
    return []


def has_pair(ip, alias):
    '''
    Return true if the alias is set

    CLI Example::
        salt '*' hosts.has_pair <ip> <alias>
    '''
    hosts = list_hosts()
    if ip not in hosts:
        return False
    if alias in hosts[ip]:
        return True
    return False


def set_host(ip, alias):
    '''
    Set the host entry in the hosts file for the given ip, this will overwrite
    any previous entry for the given ip

    CLI Example::
        salt '*' hosts.set_host <ip> <alias>
    '''
    hfn = __get_hosts_filename()
    ovr = False
    if not os.path.isfile(hfn):
        return False
    lines = open(hfn).readlines()
    for ind in range(len(lines)):
        tmpline = lines[ind].strip()
        if not tmpline:
            continue
        if tmpline.startswith('#'):
            continue
        comps = tmpline.split()
        if comps[0] == ip:
            if not ovr:
                lines[ind] = ip + '\t\t' + alias + '\n'
                ovr = True
            else: # remove other entries
                lines[ind] = ''
    if not ovr:
        # make sure there is a newline
        if lines and not lines[-1].endswith(('\n', '\r')):
            lines[-1] = '%s\n' % lines[-1]
        line = ip + '\t\t' + alias + '\n'
        lines.append(line)
    open(hfn, 'w+').writelines(lines)
    return True


def rm_host(ip, alias):
    '''
    Remove a host entry from the hosts file

    CLI Example::
        salt '*' hosts.rm_host <ip> <alias>
    '''
    if not has_pair(ip, alias):
        return True
    hfn = __get_hosts_filename()
    lines = open(hfn).readlines()
    for ind in range(len(lines)):
        tmpline = lines[ind].strip()
        if not tmpline:
            continue
        if tmpline.startswith('#'):
            continue
        comps = tmpline.split()
        if comps[0] == ip:
            newline = comps[0] + '\t'
            for existing in comps[1:]:
                if existing == alias:
                    continue
                newline += '\t' + existing
            if newline.strip() == ip:
                lines[ind] = ''
            else:
                lines[ind] = newline
    open(hfn, 'w+').writelines(lines)
    return True


def add_host(ip, alias):
    '''
    Add a host to an existing entry, if the entry is not in place then create
    it with the given host

    CLI Example::
        salt '*' hosts.add_host <ip> <alias>
    '''
    hfn = __get_hosts_filename()
    ovr = False
    if not os.path.isfile(hfn):
        return False
    lines = open(hfn).readlines()
    for ind in range(len(lines)):
        tmpline = lines[ind].strip()
        if not tmpline:
            continue
        if tmpline.startswith('#'):
            continue
        comps = tmpline.split()
        if comps[0] == ip:
            newline = comps[0] + '\t'
            for existing in comps[1:]:
                newline += '\t' + existing
            newline += '\t' + alias
            lines.append(newline)
            ovr = True
            # leave any other matching entries alone
            break
    if not ovr:
        # make sure there is a newline
        if lines and not lines[-1].endswith(('\n', '\r')):
            lines[-1] = '%s\n' % lines[-1]
        line = ip + '\t\t' + alias + '\n'
        lines.append(line)
    open(hfn, 'w+').writelines(lines)
    return True
