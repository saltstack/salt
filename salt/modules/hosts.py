# -*- coding: utf-8 -*-
'''
Manage the information in the hosts file
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import os

# Import salt libs
import salt.utils
import salt.utils.odict as odict

# Import 3rd-party libs
from salt.ext import six


# pylint: disable=C0103
def __get_hosts_filename():
    '''
    Return the path to the appropriate hosts file
    '''
    try:
        return __context__['hosts.__get_hosts_filename']
    except KeyError:
        __context__['hosts.__get_hosts_filename'] = \
            __salt__['config.option']('hosts.file')
        return __context__['hosts.__get_hosts_filename']


def _get_or_create_hostfile():
    '''
    Wrapper of __get_hosts_filename but create host file if it
    does not exist.
    '''
    hfn = __get_hosts_filename()
    if hfn is None:
        hfn = ''
    if not os.path.exists(hfn):
        with salt.utils.fopen(hfn, 'w'):
            pass
    return hfn


def _list_hosts():
    '''
    Return the hosts found in the hosts file in as an OrderedDict
    '''
    try:
        return __context__['hosts._list_hosts']
    except KeyError:
        count = 0
        hfn = __get_hosts_filename()
        ret = odict.OrderedDict()
        try:
            with salt.utils.files.fopen(hfn) as ifile:
                for line in ifile:
                    line = salt.utils.stringutils.to_unicode(line).strip()
                    if not line:
                        continue
                    if line.startswith('#'):
                        ret.setdefault('comment-{0}'.format(count), []).append(line)
                        count += 1
                        continue
                    if '#' in line:
                        line = line[:line.index('#')].strip()
                    comps = line.split()
                    ip = comps.pop(0)
                    ret.setdefault(ip, []).extend(comps)
        except (IOError, OSError) as exc:
            salt.utils.files.process_read_exception(exc, hfn, ignore=errno.ENOENT)
            # Don't set __context__ since we weren't able to read from the
            # hosts file.
            return ret

        __context__['hosts._list_hosts'] = ret
        return ret
    with salt.utils.fopen(hfn) as ifile:
        for line in ifile:
            line = salt.utils.to_unicode(line).strip()
            if not line:
                continue
            if line.startswith('#'):
                ret.setdefault('comment-{0}'.format(count), []).append(line)
                count += 1
                continue
            if '#' in line:
                line = line[:line.index('#')].strip()
            comps = line.split()
            ip = comps.pop(0)
            ret.setdefault(ip, []).extend(comps)
    return ret


def _has_pair(ip, alias, hosts_list):
    '''
    Return true if the alias exists in the ip alias list
    '''
    return ip in hosts_list and alias in hosts_list[ip]


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
    return _list_hosts().get(ip, list())


def has_pair(ip, alias):
    '''
    Return true if the alias is set
    CLI Example:
    .. code-block:: bash
        salt '*' hosts.has_pair <ip> <alias>
    '''
    hosts = _list_hosts()
    try:
        return alias in hosts[ip]
    except KeyError:
        return False
    return _has_pair(ip, alias, _list_hosts())


def set_host(ip, alias_list):
    '''
    Set the host entry in the hosts file for the given ip, this will overwrite
    any previous entry for the given ip
    .. versionchanged:: 2018.09.0
        If ``alias`` does not include any host names (it is the empty
        string or contains only whitespace), all entries for the given
        IP address are removed.
    CLI Example:
    .. code-block:: bash
        salt '*' hosts.set_host <ip> <alias_list    >
    '''
    hfn = _get_or_create_hostfile()
    if not os.path.isfile(hfn):
        return False

    # Make sure future calls to _list_hosts() will re-read the file
    __context__.pop('hosts._list_hosts', None)

    line_to_add = salt.utils.stringutils.to_bytes(
        ip + '\t\t' + alias + os.linesep
    )
    # support removing a host entry by providing an empty string
    if not alias.strip():
        line_to_add = b''

    with salt.utils.files.fopen(hfn, 'rb') as fp_:
        lines = fp_.readlines()
    for ind, _ in enumerate(lines):
        tmpline = lines[ind].strip()
        if not tmpline:
            continue
        if tmpline.startswith(b'#'):
            continue
        comps = tmpline.split()
        if comps[0] == salt.utils.stringutils.to_bytes(ip):
            if not ovr:
                lines[ind] = line_to_add
                ovr = True
            else:  # remove other entries
                lines[ind] = b''
    linesep_bytes = salt.utils.stringutils.to_bytes(os.linesep)
    if not ovr:
        # make sure there is a newline
        if lines and not lines[-1].endswith(linesep_bytes):
            lines[-1] += linesep_bytes
        line = line_to_add
        lines.append(line)
    with salt.utils.files.fopen(hfn, 'wb') as ofile:
        ofile.writelines(lines)
    hosts = _list_hosts()

    if not alias_list:
        del hosts[ip]

    hosts[ip] = alias_list

    _write_hosts(hosts)
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
    if not os.path.isfile(hfn):
        return False

    hosts = _list_hosts()

    if not _has_pair(ip, alias, hosts):
        return True

    for i, al in hosts[ip].iteritems:
        if alias == al:
            del hosts[ip][i]

    return _write_hosts(hosts)


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

    hosts = _list_hosts()

    if _has_pair(ip, alias, hosts):
        return True

    hosts[ip].append(alias)

    return _write_hosts(hosts)


def _create_alias_chunks(ip, aliases):
    '''
    Split aliases for a given if in order to fix compatibility issues
        - Max 256 char as per rfc
        - Max 8 alias per line (windows limitation)
    '''
    # https://github.com/saltstack/salt/issues/29592
    simple_alias = sorted(filter(lambda x: '.' not in x, aliases))
    fqdn_alias = sorted(filter(lambda x: '.' in x, aliases))
    sorted_aliases = simple_alias + fqdn_alias
    aliases_chunks = []
    # 256 Chars as per rfc - os line break size - chars len ip - 2 (tabs after ip)
    # https://github.com/saltstack/salt/issues/49889
    max_chars_alias = 256 - len(os.linesep) - len(ip) - 2
    while sorted_aliases:
        # determine max number of alias in a line (max 8)
        alias_per_chunk = 8 if len(sorted_aliases) >= 8 else len(sorted_aliases)
        while len(' '.join(sorted_aliases[:alias_per_chunk])) > max_chars_alias:
            alias_per_chunk = alias_per_chunk - 1

        aliases_chunks.append(sorted_aliases[:alias_per_chunk])
        del sorted_aliases[:alias_per_chunk]
    return aliases_chunks


def _write_hosts(hosts):
    lines = []
    for ip, aliases in hosts.iteritems():
        if len(aliases) > 0:
            chunks = _create_alias_chunks(ip, aliases)
            for c in chunks:
                if ip:
                    if ip.startswith('comment'):
                        line = ''.join(list(c))
                    else:
                        line = '{0}\t\t{1}'.format(ip, ' '.join(list(c)))
                lines.append(line)

    hfn = _get_or_create_hostfile()
    with salt.utils.fopen(hfn, 'w+') as ofile:
        for line in lines:
            if line.strip():
                # /etc/hosts needs to end with a newline so that some utils
                # that read it do not break
                ofile.write(salt.utils.to_str(
                    line.strip() + six.text_type(os.linesep)
                ))
    return True
