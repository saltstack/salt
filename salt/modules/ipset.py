# -*- coding: utf-8 -*-
'''
Support for ipset
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils

# Set up logging
log = logging.getLogger(__name__)

_IPSET_FAMILIES = {
        'ipv4': 'inet',
        'ip4': 'inet',
        'ipv6': 'inet6',
        'ip6': 'inet6',
        }

_IPSET_SET_TYPES = [
        'bitmap:ip',
        'bitmap:ip,mac',
        'bitmap:port',
        'hash:ip',
        'hash:ip,port',
        'hash:ip,port,ip',
        'hash:ip,port,net',
        'hash:net',
        'hash:net,net',
        'hash:net,iface',
        'hash:net,port',
        'hash:net,port,net',
        'list:set'
        ]


_CREATE_OPTIONS = {
    'bitmap:ip': ['range', 'netmask', 'timeout', 'counters', 'comment'],
    'bitmap:ip,mac': ['range', 'timeout', 'counters', 'comment'],
    'bitmap:port': ['range', 'timeout', 'counters', 'comment'],
    'hash:ip': ['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment'],
    'hash:net': ['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment'],
    'hash:net,net': ['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment'],
    'hash:net,port': ['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment'],
    'hash:net,port,net': ['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment'],
    'hash:ip,port,ip': ['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment'],
    'hash:ip,port,net': ['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment'],
    'hash:ip,port': ['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment'],
    'hash:net,iface': ['family', 'hashsize', 'maxelem', 'netmask', 'timeout', 'counters', 'comment'],
    'list:set': ['size', 'timeout', 'counters', 'comment'],
}


_CREATE_OPTIONS_REQUIRED = {
    'bitmap:ip': ['range'],
    'bitmap:ip,mac': ['range'],
    'bitmap:port': ['range'],
    'hash:ip': [],
    'hash:net': [],
    'hash:net,net': [],
    'hash:ip,port': [],
    'hash:net,port': [],
    'hash:ip,port,ip': [],
    'hash:ip,port,net': [],
    'hash:net,port,net': [],
    'hash:net,iface': [],
    'list:set': []
}


_ADD_OPTIONS = {
    'bitmap:ip': ['timeout', 'packets', 'bytes'],
    'bitmap:ip,mac': ['timeout', 'packets', 'bytes'],
    'bitmap:port': ['timeout', 'packets', 'bytes'],
    'hash:ip': ['timeout', 'packets', 'bytes'],
    'hash:net': ['timeout', 'nomatch', 'packets', 'bytes'],
    'hash:net,net': ['timeout', 'nomatch', 'packets', 'bytes'],
    'hash:net,port': ['timeout', 'nomatch', 'packets', 'bytes'],
    'hash:net,port,net': ['timeout', 'nomatch', 'packets', 'bytes'],
    'hash:ip,port,ip': ['timeout', 'packets', 'bytes'],
    'hash:ip,port,net': ['timeout', 'nomatch', 'packets', 'bytes'],
    'hash:ip,port': ['timeout', 'nomatch', 'packets', 'bytes'],
    'hash:net,iface': ['timeout', 'nomatch', 'packets', 'bytes'],
    'list:set': ['timeout', 'packets', 'bytes'],
}


def __virtual__():
    '''
    Only load the module if ipset is installed
    '''
    if salt.utils.which('ipset'):
        return True
    return False


def _ipset_cmd():
    '''
    Return correct command
    '''
    return salt.utils.which('ipset')


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
    .. versionadded:: 2014.7.0

    Check that given ipset set exists.

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


def add(set=None, entry=None, family='ipv4', **kwargs):
    '''
    Append an entry to the specified set.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.add setname 192.168.1.26

        salt '*' ipset.add setname 192.168.0.3,AA:BB:CC:DD:EE:FF

    '''
    if not set:
        return 'Error: Set needs to be specified'
    if not entry:
        return 'Error: Entry needs to be specified'

    setinfo = _find_set_info(set)
    if not setinfo:
        return 'Error: Set {0} does not exist'.format(set)

    settype = setinfo['Type']

    cmd = '{0}'.format(entry)

    if 'timeout' in kwargs:
        if 'timeout' not in setinfo['Header']:
            return 'Error: Set {0} not created with timeout support'.format(set)

    if 'packets' in kwargs or 'bytes' in kwargs:
        if 'counters' not in setinfo['Header']:
            return 'Error: Set {0} not created with counters support'.format(set)

    if 'comment' in kwargs:
        if 'comment' not in setinfo['Header']:
            return 'Error: Set {0} not created with comment support'.format(set)
        cmd = '{0} comment "{1}"'.format(cmd, kwargs['comment'])

    for item in _ADD_OPTIONS[settype]:
        if item in kwargs:
            cmd = '{0} {1} {2}'.format(cmd, item, kwargs[item])

    current_members = _find_set_members(set)
    if cmd in current_members:
        return 'Warn: Entry {0} already exists in set {1}'.format(cmd, set)

    # Using -exist to ensure entries are updated if the comment changes
    cmd = '{0} add -exist {1} {2}'.format(_ipset_cmd(), set, cmd)
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

    current_members = _find_set_members(set)
    if entry in current_members:
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
        #cmd = '{0} flush {1} family {2}'.format(_ipset_cmd(), set, ipset_family)
        cmd = '{0} flush {1}'.format(_ipset_cmd(), set)
    else:
        #cmd = '{0} flush family {1}'.format(_ipset_cmd(), ipset_family)
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
