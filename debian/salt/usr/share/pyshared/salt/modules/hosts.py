'''
Manage the information in the hosts file
'''
import os

def list_hosts():
    '''
    Return the hosts found in the hosts file in this format:

    {'<ip addr>': ['alias1', 'alias2', ...]}

    CLI Example:
    salt '*' hosts.list_hosts
    '''
    hfn = '/etc/hosts'
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
        ret[comps[0]] = comps[1:]
    return ret

def get_ip(host):
    '''
    Return the ip associated with the named host

    CLI Example:
    salt '*' hosts.get_ip <hostname>
    '''
    hosts = list_hosts()
    if not hosts:
        return ''
    # Look for the op
    for addr in hosts:
        if hosts[addr].count(host):
            return addr
    # ip not found
    return ''

def get_alias(ip):
    '''
    Return the list of aliases associated with an ip

    CLI Example:
    salt '*' hosts.get_alias <ip addr>
    '''
    hosts = list_hosts()
    if hosts.has_key(ip):
        return hosts[ip]
    return []

def has_pair(ip, alias):
    '''
    Return true if the alias is set

    CLI Example:
    salt '*' hosts.has_pair <ip> <alias>
    '''
    hosts = list_hosts()
    if not hosts.has_key(ip):
        return False
    if hosts[ip].count(alias):
        return True
    return False

def set_host(ip, alias):
    '''
    Set the host entry in th hosts file for the given ip, this will overwrite
    any previous entry for the given ip

    CLI Example:
    salt '*' hosts.set_host <ip> <alias>
    '''
    hfn = '/etc/hosts'
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
            lines[ind] = ip + '\t\t' + alias + '\n'
            ovr = True
    if not ovr:
        line = ip + '\t\t' + alias + '\n'
        lines.append(line)
    open(hfn, 'w+').writelines(lines)
    return True

def rm_host(ip, alias):
    '''
    Remove a host entry from the hosts file

    CLI Example:
    salt '*' hosts.rm_host <ip> <alias>
    '''
    if not has_pair(ip, alias):
        return True
    hfn = '/etc/hosts'
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

    CLI Example:
    salt '*' hosts.add_host <ip> <alias>
    '''
    hfn = '/etc/hosts'
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
    if not ovr:
        line = ip + '\t\t' + alias + '\n'
        lines.append(line)
    open(hfn, 'w+').writelines(lines)
    return True
