# -*- coding: utf-8 -*-
'''
Manage the information in the hosts file
'''

# Import python libs
from __future__ import absolute_import
import os

# Import salt libs
import salt.utils
import salt.utils.odict as odict

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,no-name-in-module,redefined-builtin


# pylint: disable=C0103
def __get_hosts_filename():
    '''
    Return the path to the appropriate hosts file
    '''
    # TODO: Investigate using  "%SystemRoot%\system32" for this
    if salt.utils.is_windows():
        return 'C:\\Windows\\System32\\drivers\\etc\\hosts'

    return __salt__['config.option']('hosts.file')


def _get_or_create_hostfile():
    '''
    Wrapper of __get_hosts_filename but create host file if it
    does not exist.
    '''
    hfn = __get_hosts_filename()
    if hfn is None:
        hfn = ''
    if not os.path.exists(hfn):
        salt.utils.fopen(hfn, 'w').close()
    return hfn


def _list_hosts():
    '''
    Return the hosts found in the hosts file in as an OrderedDict
    '''
    count = 0
    hfn = __get_hosts_filename()
    ret = odict.OrderedDict()
    if not os.path.isfile(hfn):
        return ret
    with salt.utils.fopen(hfn) as ifile:
        for line in ifile:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                ret.setdefault('comment-{0}'.format(count), []).extend(line)
                count += 1
                continue
            if '#' in line:
                line = line[:line.index('#')].strip()
            comps = line.split()
            ip = comps.pop(0)
            ret.setdefault(ip, []).extend(comps)
    return ret


def list_hosts():
    '''
    Return the hosts found in the hosts file in this format::

        {'<ip addr>': ['alias1', 'alias2', ...]}

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.list_hosts
    '''
    # msgpack does not like OrderedDict's
    return dict(_list_hosts())


def get_ip(host):
    '''
    Return the ip associated with the named host

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.get_ip <hostname>
    '''
    hosts = _list_hosts()
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

    Aliases (host names) are returned in the order in which they
    appear in the hosts file.  If there are no aliases associated with
    the IP, an empty list is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.get_alias <ip addr>
    '''
    hosts = _list_hosts()
    if ip in hosts:
        return hosts[ip]
    return []


def has_pair(ip, alias):
    '''
    Return true if the alias is set

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.has_pair <ip> <alias>
    '''
    hosts = _list_hosts()
    return ip in hosts and alias in hosts[ip]


def set_host(ip, alias):
    '''
    Set the host entry in the hosts file for the given ip, this will overwrite
    any previous entry for the given ip

    .. versionchanged:: 2016.3.0
        If ``alias`` does not include any host names (it is the empty
        string or contains only whitespace), all entries for the given
        IP address are removed.

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.set_host <ip> <alias>
    '''
    hfn = _get_or_create_hostfile()
    ovr = False
    if not os.path.isfile(hfn):
        return False

    line_to_add = ip + '\t\t' + alias + os.linesep
    # support removing a host entry by providing an empty string
    if not alias.strip():
        line_to_add = ''

    lines = salt.utils.fopen(hfn).readlines()
    for ind, line in enumerate(lines):
        tmpline = line.strip()
        if not tmpline:
            continue
        if tmpline.startswith('#'):
            continue
        comps = tmpline.split()
        if comps[0] == ip:
            if not ovr:
                lines[ind] = line_to_add
                ovr = True
            else:  # remove other entries
                lines[ind] = ''
    if not ovr:
        # make sure there is a newline
        if lines and not lines[-1].endswith(os.linesep):
            lines[-1] += os.linesep
        line = line_to_add
        lines.append(line)
    with salt.utils.fopen(hfn, 'w+') as ofile:
        ofile.writelines(lines)
    return True


def rm_host(ip, alias):
    '''
    Remove a host entry from the hosts file

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.rm_host <ip> <alias>
    '''
    if not has_pair(ip, alias):
        return True
    hfn = _get_or_create_hostfile()
    lines = salt.utils.fopen(hfn).readlines()
    for ind in range(len(lines)):
        tmpline = lines[ind].strip()
        if not tmpline:
            continue
        if tmpline.startswith('#'):
            continue
        comps = tmpline.split()
        if comps[0] == ip:
            newline = '{0}\t\t'.format(comps[0])
            for existing in comps[1:]:
                if existing == alias:
                    continue
                newline += ' {0}'.format(existing)
            if newline.strip() == ip:
                # No aliases exist for the line, make it empty
                lines[ind] = ''
            else:
                # Only an alias was removed
                lines[ind] = newline + os.linesep
    with salt.utils.fopen(hfn, 'w+') as ofile:
        ofile.writelines(lines)
    return True


def add_host(ip, alias):
    '''
    Add a host to an existing entry, if the entry is not in place then create
    it with the given host

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.add_host <ip> <alias>
    '''
    hfn = _get_or_create_hostfile()
    if not os.path.isfile(hfn):
        return False

    if has_pair(ip, alias):
        return True

    hosts = _list_hosts()
    inserted = False
    for i, h in six.iteritems(hosts):
        for j in range(len(h)):
            if h[j].startswith('#') and i == ip:
                h.insert(j, alias)
                inserted = True
    if not inserted:
        hosts.setdefault(ip, []).append(alias)
    _write_hosts(hosts)
    return True


def _write_hosts(hosts):
    lines = []
    for ip, aliases in six.iteritems(hosts):
        if ip:
            if ip.startswith('comment'):
                line = ''.join(aliases)
            else:
                line = '{0}\t\t{1}'.format(
                    ip,
                    ' '.join(aliases)
                    )
        lines.append(line)

    hfn = _get_or_create_hostfile()
    with salt.utils.fopen(hfn, 'w+') as ofile:
        for line in lines:
            if line.strip():
                # /etc/hosts needs to end with EOL so that some utils that read
                # it do not break
                ofile.write(line.strip() + os.linesep)
