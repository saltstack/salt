"""
Manage the information in the hosts file
"""


import errno
import logging
import os

import salt.utils.files
import salt.utils.odict as odict
import salt.utils.stringutils

log = logging.getLogger(__name__)


# pylint: disable=C0103
def __get_hosts_filename():
    """
    Return the path to the appropriate hosts file
    """
    try:
        return __context__["hosts.__get_hosts_filename"]
    except KeyError:
        __context__["hosts.__get_hosts_filename"] = __salt__["config.option"](
            "hosts.file"
        )
        return __context__["hosts.__get_hosts_filename"]


def _get_or_create_hostfile():
    """
    Wrapper of __get_hosts_filename but create host file if it
    does not exist.
    """
    hfn = __get_hosts_filename()
    if hfn is None:
        hfn = ""
    if not os.path.exists(hfn):
        with salt.utils.files.fopen(hfn, "w"):
            pass
    return hfn


def _list_hosts():
    """
    Return the hosts found in the hosts file in as an OrderedDict
    """
    try:
        return __context__["hosts._list_hosts"]
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
                    if line.startswith("#"):
                        ret.setdefault("comment-{}".format(count), []).append(line)
                        count += 1
                        continue
                    comment = None
                    if "#" in line:
                        comment = line[line.index("#") + 1 :].lstrip()
                        line = line[: line.index("#")].strip()
                    comps = line.split()
                    ip = comps.pop(0)
                    if comment:
                        ret.setdefault(ip, {}).setdefault("aliases", []).extend(comps)
                        ret.setdefault(ip, {}).update({"comment": comment})
                    else:
                        ret.setdefault(ip, {}).setdefault("aliases", []).extend(comps)
        except OSError as exc:
            salt.utils.files.process_read_exception(exc, hfn, ignore=errno.ENOENT)
            # Don't set __context__ since we weren't able to read from the
            # hosts file.
            return ret

        __context__["hosts._list_hosts"] = ret
        return ret


def list_hosts():
    """
    Return the hosts found in the hosts file in this format::

        {'<ip addr>': ['alias1', 'alias2', ...]}

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.list_hosts
    """
    # msgpack does not like OrderedDict's
    return dict(_list_hosts())


def get_ip(host):
    """
    Return the ip associated with the named host

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.get_ip <hostname>
    """
    hosts = _list_hosts()
    if not hosts:
        return ""
    # Look for the op
    for addr in hosts:
        if isinstance(hosts[addr], dict) and "aliases" in hosts[addr]:
            _hosts = hosts[addr]["aliases"]
            if host in _hosts:
                return addr
    # ip not found
    return ""


def get_alias(ip):
    """
    Return the list of aliases associated with an ip

    Aliases (host names) are returned in the order in which they
    appear in the hosts file.  If there are no aliases associated with
    the IP, an empty list is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.get_alias <ip addr>
    """
    hosts = _list_hosts()
    if ip in list(hosts):
        return hosts[ip]["aliases"]
    return []


def has_pair(ip, alias):
    """
    Return true if the alias is set

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.has_pair <ip> <alias>
    """
    hosts = _list_hosts()
    try:
        if isinstance(alias, list):
            return set(alias).issubset(hosts[ip]["aliases"])
        else:
            return alias in hosts[ip]["aliases"]
    except KeyError:
        return False


def set_host(ip, alias, comment=None):
    """
    Set the host entry in the hosts file for the given ip, this will overwrite
    any previous entry for the given ip

    .. versionchanged:: 2016.3.0
        If ``alias`` does not include any host names (it is the empty
        string or contains only whitespace), all entries for the given
        IP address are removed.

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.set_host <ip> <alias>
    """
    hfn = _get_or_create_hostfile()
    ovr = False
    if not os.path.isfile(hfn):
        return False

    # Make sure future calls to _list_hosts() will re-read the file
    __context__.pop("hosts._list_hosts", None)

    if comment:
        line_to_add = salt.utils.stringutils.to_bytes(
            ip + "\t\t" + alias + "\t\t# " + comment + os.linesep
        )
    else:
        line_to_add = salt.utils.stringutils.to_bytes(ip + "\t\t" + alias + os.linesep)
    # support removing a host entry by providing an empty string
    if not alias.strip():
        line_to_add = b""

    with salt.utils.files.fopen(hfn, "rb") as fp_:
        lines = fp_.readlines()
    for ind, _ in enumerate(lines):
        tmpline = lines[ind].strip()
        if not tmpline:
            continue
        if tmpline.startswith(b"#"):
            continue
        comps = tmpline.split()
        if comps[0] == salt.utils.stringutils.to_bytes(ip):
            if not ovr:
                lines[ind] = line_to_add
                ovr = True
            else:  # remove other entries
                lines[ind] = b""
    linesep_bytes = salt.utils.stringutils.to_bytes(os.linesep)
    if not ovr:
        # make sure there is a newline
        if lines and not lines[-1].endswith(linesep_bytes):
            lines[-1] += linesep_bytes
        line = line_to_add
        lines.append(line)
    with salt.utils.files.fopen(hfn, "wb") as ofile:
        ofile.writelines(lines)
    return True


def rm_host(ip, alias):
    """
    Remove a host entry from the hosts file

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.rm_host <ip> <alias>
    """
    if not has_pair(ip, alias):
        return True
    # Make sure future calls to _list_hosts() will re-read the file
    __context__.pop("hosts._list_hosts", None)
    hfn = _get_or_create_hostfile()
    with salt.utils.files.fopen(hfn, "rb") as fp_:
        lines = fp_.readlines()
    for ind, _ in enumerate(lines):
        tmpline = lines[ind].strip()
        if not tmpline:
            continue
        if tmpline.startswith(b"#"):
            continue
        comps = tmpline.split()
        comment = None
        if b"#" in tmpline:
            host_info, comment = tmpline.split(b"#")
            comment = salt.utils.stringutils.to_bytes(comment).lstrip()
        else:
            host_info = tmpline
        host_info = salt.utils.stringutils.to_bytes(host_info)
        comps = host_info.split()
        b_ip = salt.utils.stringutils.to_bytes(ip)
        b_alias = salt.utils.stringutils.to_bytes(alias)
        if comps[0] == b_ip:
            newline = comps[0] + b"\t\t"
            for existing in comps[1:]:
                if existing == b_alias:
                    continue
                newline += existing + b" "
            if newline.strip() == b_ip:
                # No aliases exist for the line, make it empty
                lines[ind] = b""
            else:
                # Only an alias was removed
                if comment:
                    lines[ind] = (
                        newline
                        + b"# "
                        + comment
                        + salt.utils.stringutils.to_bytes(os.linesep)
                    )
                else:
                    lines[ind] = newline + salt.utils.stringutils.to_bytes(os.linesep)
    with salt.utils.files.fopen(hfn, "wb") as ofile:
        ofile.writelines(lines)
    return True


def add_host(ip, alias):
    """
    Add a host to an existing entry, if the entry is not in place then create
    it with the given host

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.add_host <ip> <alias>
    """
    hfn = _get_or_create_hostfile()
    if not os.path.isfile(hfn):
        return False

    if has_pair(ip, alias):
        return True

    hosts = _list_hosts()

    # Make sure future calls to _list_hosts() will re-read the file
    __context__.pop("hosts._list_hosts", None)

    inserted = False
    for i, h in hosts.items():
        for num, host in enumerate(h):
            if isinstance(h, list):
                if host.startswith("#") and i == ip:
                    h.insert(num, alias)
                    inserted = True
    if not inserted:
        hosts.setdefault(ip, {}).setdefault("aliases", []).append(alias)
    _write_hosts(hosts)
    return True


def set_comment(ip, comment):
    """
    Set the comment for a host to an existing entry,
    if the entry is not in place then return False

    CLI Example:

    .. code-block:: bash

        salt '*' hosts.set_comment <ip> <comment>
    """
    hfn = _get_or_create_hostfile()
    if not os.path.isfile(hfn):
        return False

    hosts = _list_hosts()

    # Make sure future calls to _list_hosts() will re-read the file
    __context__.pop("hosts._list_hosts", None)

    if ip not in hosts:
        return False

    if "comment" in hosts[ip]:
        if comment != hosts[ip]["comment"]:
            hosts[ip]["comment"] = comment
            _write_hosts(hosts)
        else:
            return True
    else:
        hosts[ip]["comment"] = comment
        _write_hosts(hosts)
    return True


def _write_hosts(hosts):
    lines = []
    for ip, host_info in hosts.items():
        if ip:
            if ip.startswith("comment"):
                line = "".join(host_info)
            else:
                if "comment" in host_info:
                    line = "{}\t\t{}\t\t# {}".format(
                        ip, " ".join(host_info["aliases"]), host_info["comment"]
                    )
                else:
                    line = "{}\t\t{}".format(ip, " ".join(host_info["aliases"]))
        lines.append(line)

    hfn = _get_or_create_hostfile()
    with salt.utils.files.fopen(hfn, "w+") as ofile:
        for line in lines:
            if line.strip():
                # /etc/hosts needs to end with a newline so that some utils
                # that read it do not break
                ofile.write(
                    salt.utils.stringutils.to_str(line.strip() + str(os.linesep))
                )
