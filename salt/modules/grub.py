'''
Support for GRUB
'''

import os

def __virtual__():
    '''
    Only load the module if grub is installed
    '''
    conf = _detect_conf()
    if os.path.exists(conf):
        return 'boot'
    return False

def _detect_conf():
    '''
    GRUB conf location differs depending on distro
    '''
    conf = ('CentOS', 'Scientific', 'RedHat', 'Fedora')
    menu = ('Ubuntu', 'Debian', 'Arch')
    if __grains__['os'] in conf:
        return '/boot/grub/grub.conf'
    elif __grains__['os'] in menu:
        return '/boot/grub/menu.lst'
    else:
        return '/boot/grub/menu.lst'

def version():
    '''
    Return server version from grub --version

    CLI Example::

        salt '*' grub.version
    '''
    cmd = '/sbin/grub --version'
    out = __salt__['cmd.run'](cmd)
    return out

def conf():
    '''
    Parse GRUB conf file

    CLI Example::

        salt '*' grub.conf
    '''
    stanza = ''
    stanzas = []
    instanza = 0
    ret = {}
    pos = 0
    for line in open(_detect_conf(), 'r'):
        if line.startswith('#'):
            continue
        if line.startswith('\n'):
            instanza = 0
            if 'title' in stanza:
                stanza += 'order {0}'.format(pos)
                pos += 1
                stanzas.append(stanza)
            stanza = ''
            continue
        if line.startswith('title'):
            instanza = 1
        if instanza == 1:
            stanza += line
        if instanza == 0:
            key, value = _parse_line(line)
            ret[key] = value
    if instanza == 1:
        if not line.endswith('\n'):
            line += '\n'
        stanza += line
        stanza += 'order {0}'.format(pos)
        pos += 1
        stanzas.append(stanza)
    ret['stanzas'] = []
    for stanza in stanzas:
        mydict = {}
        for line in stanza.strip().split('\n'):
            key, value = _parse_line(line)
            mydict[key] = value
        ret['stanzas'].append(mydict)
    return ret

def _parse_line(line=''):
    '''
    Used by conf() to break config lines into
    name/value pairs
    '''
    parts = line.split()
    key = parts.pop(0)
    value = ' '.join(parts)
    return key, value

