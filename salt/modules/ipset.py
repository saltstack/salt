# -*- coding: utf-8 -*-
'''
Support for ipset
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt libs
from salt.ext import six
from salt.ext.six.moves import map, range
import salt.utils.path

# Import third-party libs
if six.PY3:
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress

# Set up logging
log = logging.getLogger(__name__)


# Fix included in py2-ipaddress for 32bit architectures
# Except that xrange only supports machine integers, not longs, so...
def long_range(start, end):
    while start < end:
        yield start
        start += 1

_IPSET_FAMILIES = {
        'ipv4': 'inet',
        'ip4': 'inet',
        'ipv6': 'inet6',
        'ip6': 'inet6',
        }

_IPSET_SET_TYPES = set([
        'bitmap:ip',
        'bitmap:ip,mac',
        'bitmap:port',
        'hash:ip',
        'hash:mac',
        'hash:ip,port',
        'hash:ip,port,ip',
        'hash:ip,port,net',
        'hash:net',
        'hash:net,net',
        'hash:net,iface',
        'hash:net,port',
        'hash:net,port,net',
        'hash:ip,mark',
        'list:set'
        ])


_CREATE_OPTIONS = {
    'bitmap:ip': set(['range', 'netmask', 'timeout', 'counters', 'comment', 'skbinfo']),
    'bitmap:ip,mac': set(['range', 'timeout', 'counters', 'comment', 'skbinfo']),
    'bitmap:port': set(['range', 'timeout', 'counters', 'comment', 'skbinfo']),
    'hash:ip': set(['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment', 'skbinfo']),
    'hash:mac': set(['hashsize', 'maxelem', 'timeout', 'counters', 'comment', 'skbinfo']),
    'hash:net': set(['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment', 'skbinfo']),
    'hash:net,net': set(['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment', 'skbinfo']),
    'hash:net,port': set(['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment', 'skbinfo']),
    'hash:net,port,net': set(['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment', 'skbinfo']),
    'hash:ip,port,ip': set(['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment', 'skbinfo']),
    'hash:ip,port,net': set(['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment', 'skbinfo']),
    'hash:ip,port': set(['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment', 'skbinfo']),
    'hash:ip,mark': set(['family', 'markmask', 'hashsize', 'maxelem', 'timeout', 'counters', 'comment', 'skbinfo']),
    'hash:net,iface': set(['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment', 'skbinfo']),
    'list:set': set(['size', 'timeout', 'counters', 'comment']),
}

_CREATE_OPTIONS_WITHOUT_VALUE = set(['comment', 'counters', 'skbinfo'])

_CREATE_OPTIONS_REQUIRED = {
    'bitmap:ip': ['range'],
    'bitmap:ip,mac': ['range'],
    'bitmap:port': ['range'],
    'hash:ip': [],
    'hash:mac': [],
    'hash:net': [],
    'hash:net,net': [],
    'hash:ip,port': [],
    'hash:net,port': [],
    'hash:ip,port,ip': [],
    'hash:ip,port,net': [],
    'hash:net,port,net': [],
    'hash:net,iface': [],
    'hash:ip,mark': [],
    'list:set': []
}


_ADD_OPTIONS = {
    'bitmap:ip': set(['timeout', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'bitmap:ip,mac': set(['timeout', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'bitmap:port': set(['timeout', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbprio']),
    'hash:ip': set(['timeout', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'hash:mac': set(['timeout', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'hash:net': set(['timeout', 'nomatch', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'hash:net,net': set(['timeout', 'nomatch', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'hash:net,port': set(['timeout', 'nomatch', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'hash:net,port,net': set(['timeout', 'nomatch', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'hash:ip,port,ip': set(['timeout', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'hash:ip,port,net': set(['timeout', 'nomatch', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'hash:ip,port': set(['timeout', 'nomatch', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'hash:net,iface': set(['timeout', 'nomatch', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'hash:ip,mark': set(['timeout', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
    'list:set': set(['timeout', 'packets', 'bytes', 'skbmark', 'skbprio', 'skbqueue']),
}


def __virtual__():
    '''
    Only load the module if ipset is installed
    '''
    if salt.utils.path.which('ipset'):
        return True
    return (False, 'The ipset execution modules cannot be loaded: ipset binary not in path.')


def _ipset_cmd():
    '''
    Return correct command
    '''
    return salt.utils.path.which('ipset')


def version():
    '''
    Return version from ipset --version

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.version

    '''
    cmd = '{0} --version' . format(_ipset_cmd())
    out = __salt__['cmd.run'](cmd).split()
    return out[1]


def new_set(set=None, set_type=None, family='ipv4', comment=False, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Create new custom set

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.new_set custom_set list:set

        salt '*' ipset.new_set custom_set list:set comment=True

        IPv6:
        salt '*' ipset.new_set custom_set list:set family=ipv6
    '''

    ipset_family = _IPSET_FAMILIES[family]
    if not set:
        return 'Error: Set needs to be specified'

    if not set_type:
        return 'Error: Set Type needs to be specified'

    if set_type not in _IPSET_SET_TYPES:
        return 'Error: Set Type is invalid'

    # Check for required arguments
    for item in _CREATE_OPTIONS_REQUIRED[set_type]:
        if item not in kwargs:
            return 'Error: {0} is a required argument'.format(item)

    cmd = '{0} create {1} {2}'.format(_ipset_cmd(), set, set_type)

    for item in _CREATE_OPTIONS[set_type]:
        if item in kwargs:
            if item in _CREATE_OPTIONS_WITHOUT_VALUE:
                cmd = '{0} {1} '.format(cmd, item)
            else:
                cmd = '{0} {1} {2} '.format(cmd, item, kwargs[item])

    # Family only valid for certain set types
    if 'family' in _CREATE_OPTIONS[set_type]:
        cmd = '{0} family {1}'.format(cmd, ipset_family)

    if comment:
        cmd = '{0} comment'.format(cmd)

    out = __salt__['cmd.run'](cmd, python_shell=False)

    if not out:
        out = True
    return out


def delete_set(set=None, family='ipv4'):
    '''
    .. versionadded:: 2014.7.0

    Delete ipset set.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.delete_set custom_set

        IPv6:
        salt '*' ipset.delete_set custom_set family=ipv6
    '''

    if not set:
        return 'Error: Set needs to be specified'

    cmd = '{0} destroy {1}'.format(_ipset_cmd(), set)
    out = __salt__['cmd.run'](cmd, python_shell=False)

    if not out:
        out = True
    return out


def rename_set(set=None, new_set=None, family='ipv4'):
    '''
    .. versionadded:: 2014.7.0

    Delete ipset set.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.rename_set custom_set new_set=new_set_name

        IPv6:
        salt '*' ipset.rename_set custom_set new_set=new_set_name family=ipv6
    '''

    if not set:
        return 'Error: Set needs to be specified'

    if not new_set:
        return 'Error: New name for set needs to be specified'

    settype = _find_set_type(set)
    if not settype:
        return 'Error: Set does not exist'

    settype = _find_set_type(new_set)
    if settype:
        return 'Error: New Set already exists'

    cmd = '{0} rename {1} {2}'.format(_ipset_cmd(), set, new_set)
    out = __salt__['cmd.run'](cmd, python_shell=False)

    if not out:
        out = True
    return out


def list_sets(family='ipv4'):
    '''
    .. versionadded:: 2014.7.0

    List all ipset sets.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.list_sets

    '''
    cmd = '{0} list -t'.format(_ipset_cmd())
    out = __salt__['cmd.run'](cmd, python_shell=False)

    _tmp = out.split('\n')

    count = 0
    sets = []
    sets.append({})
    for item in _tmp:
        if len(item) == 0:
            count = count + 1
            sets.append({})
            continue
        key, value = item.split(':', 1)
        sets[count][key] = value[1:]
    return sets


def check_set(set=None, family='ipv4'):
    '''
    Check that given ipset set exists.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.check_set setname

    '''
    if not set:
        return 'Error: Set needs to be specified'

    setinfo = _find_set_info(set)
    if not setinfo:
        return False
    return True


def add(setname=None, entry=None, family='ipv4', **kwargs):
    '''
    Append an entry to the specified set.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.add setname 192.168.1.26

        salt '*' ipset.add setname 192.168.0.3,AA:BB:CC:DD:EE:FF

    '''
    if not setname:
        return 'Error: Set needs to be specified'
    if not entry:
        return 'Error: Entry needs to be specified'

    setinfo = _find_set_info(setname)
    if not setinfo:
        return 'Error: Set {0} does not exist'.format(setname)

    settype = setinfo['Type']

    cmd = '{0}'.format(entry)

    if 'timeout' in kwargs:
        if 'timeout' not in setinfo['Header']:
            return 'Error: Set {0} not created with timeout support'.format(setname)

    if 'packets' in kwargs or 'bytes' in kwargs:
        if 'counters' not in setinfo['Header']:
            return 'Error: Set {0} not created with counters support'.format(setname)

    if 'comment' in kwargs:
        if 'comment' not in setinfo['Header']:
            return 'Error: Set {0} not created with comment support'.format(setname)
        if 'comment' not in entry:
            cmd = '{0} comment "{1}"'.format(cmd, kwargs['comment'])

    if len(set(['skbmark', 'skbprio', 'skbqueue']) & set(kwargs.keys())) > 0:
        if 'skbinfo' not in setinfo['Header']:
            return 'Error: Set {0} not created with skbinfo support'.format(setname)

    for item in _ADD_OPTIONS[settype]:
        if item in kwargs:
            cmd = '{0} {1} {2}'.format(cmd, item, kwargs[item])

    current_members = _find_set_members(setname)
    if cmd in current_members:
        return 'Warn: Entry {0} already exists in set {1}'.format(cmd, setname)

    # Using -exist to ensure entries are updated if the comment changes
    cmd = '{0} add -exist {1} {2}'.format(_ipset_cmd(), setname, cmd)
    out = __salt__['cmd.run'](cmd, python_shell=False)

    if len(out) == 0:
        return 'Success'
    return 'Error: {0}'.format(out)


def delete(set=None, entry=None, family='ipv4', **kwargs):
    '''
    Delete an entry from the specified set.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.delete setname 192.168.0.3,AA:BB:CC:DD:EE:FF

    '''
    if not set:
        return 'Error: Set needs to be specified'
    if not entry:
        return 'Error: Entry needs to be specified'

    settype = _find_set_type(set)

    if not settype:
        return 'Error: Set {0} does not exist'.format(set)

    cmd = '{0} del {1} {2}'.format(_ipset_cmd(), set, entry)
    out = __salt__['cmd.run'](cmd, python_shell=False)

    if len(out) == 0:
        return 'Success'
    return 'Error: {0}'.format(out)


def check(set=None, entry=None, family='ipv4'):
    '''
    Check that an entry exists in the specified set.

    set
        The ipset name

    entry
        An entry in the ipset.  This parameter can be a single IP address, a
        range of IP addresses, or a subnet block.  Example:

        .. code-block:: cfg

            192.168.0.1
            192.168.0.2-192.168.0.19
            192.168.0.0/25

    family
        IP protocol version: ipv4 or ipv6

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.check setname '192.168.0.1 comment "Hello"'

    '''
    if not set:
        return 'Error: Set needs to be specified'
    if not entry:
        return 'Error: Entry needs to be specified'

    settype = _find_set_type(set)
    if not settype:
        return 'Error: Set {0} does not exist'.format(set)

    current_members = _parse_members(settype, _find_set_members(set))

    if not len(current_members):
        return False

    if isinstance(entry, list):
        entries = _parse_members(settype, entry)
    else:
        entries = [_parse_member(settype, entry)]

    for current_member in current_members:
        for entry in entries:
            if _member_contains(current_member, entry):
                return True

    return False


def test(set=None, entry=None, family='ipv4', **kwargs):
    '''
    Test if an entry is in the specified set.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.test setname 192.168.0.2

        IPv6:
        salt '*' ipset.test setname fd81:fc56:9ac7::/48
    '''
    if not set:
        return 'Error: Set needs to be specified'
    if not entry:
        return 'Error: Entry needs to be specified'

    settype = _find_set_type(set)
    if not settype:
        return 'Error: Set {0} does not exist'.format(set)

    cmd = '{0} test {1} {2}'.format(_ipset_cmd(), set, entry)
    out = __salt__['cmd.run_all'](cmd, python_shell=False)

    if out['retcode'] > 0:
        # Entry doesn't exist in set return false
        return False

    return True


def flush(set=None, family='ipv4'):
    '''
    Flush entries in the specified set,
    Flush all sets if set is not specified.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.flush

        salt '*' ipset.flush set

        IPv6:
        salt '*' ipset.flush

        salt '*' ipset.flush set
    '''

    settype = _find_set_type(set)
    if not settype:
        return 'Error: Set {0} does not exist'.format(set)

    ipset_family = _IPSET_FAMILIES[family]
    if set:
        cmd = '{0} flush {1}'.format(_ipset_cmd(), set)
    else:
        cmd = '{0} flush'.format(_ipset_cmd())
    out = __salt__['cmd.run'](cmd, python_shell=False)

    if len(out) == 0:
        return True
    else:
        return False


def _find_set_members(set):
    '''
    Return list of members for a set
    '''

    cmd = '{0} list {1}'.format(_ipset_cmd(), set)
    out = __salt__['cmd.run_all'](cmd, python_shell=False)

    if out['retcode'] > 0:
        # Set doesn't exist return false
        return False

    _tmp = out['stdout'].split('\n')
    members = []
    startMembers = False
    for i in _tmp:
        if startMembers:
            members.append(i)
        if 'Members:' in i:
            startMembers = True
    return members


def _find_set_info(set):
    '''
    Return information about the set
    '''

    cmd = '{0} list -t {1}'.format(_ipset_cmd(), set)
    out = __salt__['cmd.run_all'](cmd, python_shell=False)

    if out['retcode'] > 0:
        # Set doesn't exist return false
        return False

    setinfo = {}
    _tmp = out['stdout'].split('\n')
    for item in _tmp:
        # Only split if item has a colon
        if ':' in item:
            key, value = item.split(':', 1)
            setinfo[key] = value[1:]
    return setinfo


def _find_set_type(set):
    '''
    Find the type of the set
    '''
    setinfo = _find_set_info(set)

    if setinfo:
        return setinfo['Type']
    else:
        return False


def _parse_members(settype, members):
    if isinstance(members, six.string_types):

        return [_parse_member(settype, members)]

    return [_parse_member(settype, member) for member in members]


def _parse_member(settype, member, strict=False):
    subtypes = settype.split(':')[1].split(',')

    all_parts = member.split(' ', 1)
    parts = all_parts[0].split(',')

    parsed_member = []
    for i in range(len(subtypes)):
        subtype = subtypes[i]
        part = parts[i]

        if subtype in ['ip', 'net']:
            try:
                if '/' in part:
                    part = ipaddress.ip_network(part, strict=strict)
                elif '-' in part:
                    start, end = list(map(ipaddress.ip_address, part.split('-')))

                    part = list(ipaddress.summarize_address_range(start, end))
                else:
                    part = ipaddress.ip_address(part)
            except ValueError:
                pass

        elif subtype == 'port':
            part = int(part)

        parsed_member.append(part)

    if len(all_parts) > 1:
        parsed_member.append(all_parts[1])

    return parsed_member


def _members_contain(members, entry):
    pass


def _member_contains(member, entry):
    if len(member) < len(entry):
        return False

    for i in range(len(entry)):
        if not _compare_member_parts(member[i], entry[i]):
            return False

    return True


def _compare_member_parts(member_part, entry_part):
    if member_part == entry_part:
        # this covers int, string, and equal ip and net
        return True

    # for ip ranges parsed with summarize_address_range
    if isinstance(entry_part, list):
        for entry_part_item in entry_part:
            if not _compare_member_parts(member_part, entry_part_item):
                return False

        return True

    # below we only deal with ip and net objects
    if _is_address(member_part):
        if _is_network(entry_part):
            return member_part in entry_part

    elif _is_network(member_part):
        if _is_address(entry_part):
            return entry_part in member_part

        # both are networks, and == was false
        return False

        # This could be changed to support things like
        # 192.168.0.4/30 contains 192.168.0.4/31
        #
        # return entry_part.network_address in member_part \
        #    and entry_part.broadcast_address in member_part

    return False


def _is_network(o):
    return isinstance(o, ipaddress.IPv4Network) \
        or isinstance(o, ipaddress.IPv6Network)


def _is_address(o):
    return isinstance(o, ipaddress.IPv4Address) \
        or isinstance(o, ipaddress.IPv6Address)
