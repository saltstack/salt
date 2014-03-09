# -*- coding: utf-8 -*-
'''
Support for nftables
'''

# Import python libs
import logging
import re

# Import salt libs
import salt.utils
from salt.exceptions import (
    CommandExecutionError
)


# Set up logging
log = logging.getLogger(__name__)

_NFTABLES_FAMILIES = {
        'ipv4': 'ip',
        'ip4': 'ip',
        'ip': 'ip',
        'ipv6': 'ip6',
        'ip6': 'ip6',
        'arp': 'arp',
        'bridge': 'bridge'
        }


def __virtual__():
    '''
    Only load the module if nftables is installed
    '''
    if salt.utils.which('nft'):
        return 'nftables'
    return False


def _nftables_cmd():
    '''
    Return correct command
    '''
    return 'nft'


def _conf(family='ip'):
    '''
    Use the same file for rules for now.
    '''
    if __grains__['os_family'] == 'RedHat':
        return '/etc/nftables'
    elif __grains__['os_family'] == 'Arch':
        return '/etc/nftables'
    elif __grains__['os_family'] == 'Debian':
        return '/etc/nftables'
    elif __grains__['os'] == 'Gentoo':
        return '/etc/nftables'
    else:
        return False


def version():
    '''
    Return version from nftables --version

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.version

    '''
    cmd = '{0} --version' . format(_nftables_cmd())
    out = __salt__['cmd.run'](cmd).split()
    return out[1]


def get_saved_rules(conf_file=None, family='ipv4'):
    '''
    Return a data structure of the rules in the conf file

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.get_saved_rules

    '''
    if _conf() and not conf_file:
        conf_file = _conf()

    lines = salt.utils.fopen(conf_file).readlines()
    rules = []
    for line in lines:
        tmpline = line.strip()
        if not tmpline:
            continue
        if tmpline.startswith('#'):
            continue
        rules.append(line)
    return rules


def get_rules(family='ipv4'):
    '''
    Return a data structure of the current, in-memory rules

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.get_rules

        salt '*' nftables.get_rules family=ipv6

    '''
    nft_family = _NFTABLES_FAMILIES[family]
    rules = []
    cmd = '{0} list tables {1}'.format(_nftables_cmd(), nft_family)
    out = __salt__['cmd.run'](cmd)
    if not out:
        return rules

    tables = re.split('\n+', out)
    for table in tables:
        table_name = table.split(' ')[1]
        cmd = '{0} list table {1} {2}'.format(_nftables_cmd(), nft_family, table_name)
        out = __salt__['cmd.run'](cmd)
        rules.append(out)
    return rules


def save(filename=None, family='ipv4'):
    '''
    Save the current in-memory rules to disk

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.save /etc/nftables
    '''
    if _conf() and not filename:
        filename = _conf()

    nft_families = ['ip', 'ip6', 'arp', 'bridge']
    rules = "#! nft -f\n"
    for family in nft_families:
        out = get_rules(family)
        if out:
            rules += '\n'
        rules = rules + '\n'.join(out)
    rules = rules + '\n'

    try:
        with salt.utils.fopen(filename, 'w+') as _fh:
            # Write out any changes
            _fh.writelines(rules)
    except (IOError, OSError) as exc:
        raise CommandExecutionError(
            'Problem writing to configuration file: {0}'.format(exc)
        )
    return rules


def get_rule_handle(table='filter', chain=None, rule=None, family='ipv4'):
    '''
    Get the handle for a particular rule

    This function accepts a rule in a standard nftables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.get_rule_handle filter input \\
            rule='input tcp dport 22 log accept'

        IPv6:
        salt '*' nftables.get_rule_handle filter input \\
            rule='input tcp dport 22 log accept' \\
            family=ipv6
    '''
    if not chain:
        return 'Error: Chain needs to be specified'
    if not rule:
        return 'Error: Rule needs to be specified'

    if not check_table(table, family=family):
        return 'Error: table {0} in family {1} does not exist' . format(table, family)

    if not check_chain(table, chain, family=family):
        return 'Error: chain {0} in table {1} in family {1} does not exist' . format(chain, table, family)

    if not check(table, chain, rule, family=family):
        return 'Error: rule {0} chain {1} in table {2} in family {3} does not exist' . format(rule, chain, table, family)

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = '{0} --numeric --handle list chain {1} {2} {3}' . format(_nftables_cmd(), nft_family, table, chain)
    out = __salt__['cmd.run'](cmd)
    rules = re.split('\n+', out)

    pat = re.compile(r'{0} # handle (?P<handle>\d+)' . format(rule))
    for rule in rules:
        match = pat.search(rule)
        if match:
            handle = match.group('handle')
    return handle


def check(table='filter', chain=None, rule=None, family='ipv4'):
    '''
    Check for the existence of a rule in the table and chain

    This function accepts a rule in a standard nftables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.check filter input \\
            rule='input tcp dport 22 log accept'

        IPv6:
        salt '*' nftables.check filter input \\
            rule='input tcp dport 22 log accept' \\
            family=ipv6
    '''
    if not chain:
        return 'Error: Chain needs to be specified'
    if not rule:
        return 'Error: Rule needs to be specified'

    if not check_table(table, family=family):
        return 'Error: table {0} in family {1} does not exist' . format(table, family)

    if not check_chain(table, chain, family=family):
        return 'Error: chain {0} in table {1} in family {1} does not exist' . format(chain, table, family)

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = '{0} --handle --numeric list chain {1} {2} {3}' . format(_nftables_cmd(), nft_family, table, chain)
    out = __salt__['cmd.run'](cmd).find('{0} #'.format(rule))

    if out != -1:
        out = ''
    else:
        return False

    if not out:
        return True
    return out


def check_chain(table='filter', chain=None, family='ipv4'):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Check for the existence of a chain in the table

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.check_chain filter input

        IPv6:
        salt '*' nftables.check_chain filter input family=ipv6
    '''

    if not chain:
        return 'Error: Chain needs to be specified'

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = '{0} list table {1} {2}' . format(_nftables_cmd(), nft_family, table)
    out = __salt__['cmd.run'](cmd).find('chain {0} {{'.format(chain))

    if out != -1:
        out = ''
    else:
        return False

    if not out:
        return True
    return out


def check_table(table=None, family='ipv4'):
    '''
    Check for the existence of a table
    '''
    if not table:
        return 'Error: table needs to be specified'

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = '{0} list tables {1}' . format(_nftables_cmd(), nft_family)
    out = __salt__['cmd.run'](cmd).find('table {0}'.format(table))

    if out != -1:
        out = ''
    else:
        return False

    if not out:
        return True
    return out


def new_table(table, family='ipv4'):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Create new custom table.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.new_table filter

        IPv6:
        salt '*' nftables.new_table filter family=ipv6
    '''

    if not table:
        return 'Error: table needs to be specified'

    if check_table(table, family=family):
        return 'Error: table {0} in family {1} already exists' . format(table, family)

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = '{0} add table {1} {2}'.format(_nftables_cmd(), nft_family, table)
    out = __salt__['cmd.run'](cmd)

    if not out:
        out = True
    return out


def delete_table(table, family='ipv4'):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Create new custom table.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.delete_table filter

        IPv6:
        salt '*' nftables.delete_table filter family=ipv6
    '''

    if not table:
        return 'Error: table needs to be specified'

    if not check_table(table, family=family):
        return 'Error: table {0} in family {1} does not exist' . format(table, family)

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = '{0} delete table {1} {2}'.format(_nftables_cmd(), nft_family, table)
    out = __salt__['cmd.run'](cmd)

    if not out:
        out = True
    return out


def new_chain(table='filter', chain=None, table_type=None, hook=None, priority=None, family='ipv4'):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Create new chain to the specified table.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.new_chain filter input

        salt '*' nftables.new_chain filter input table_type=filter hook=input priority=0

        salt '*' nftables.new_chain filter foo

        IPv6:
        salt '*' nftables.new_chain filter input family=ipv6

        salt '*' nftables.new_chain filter input table_type=filter hook=input priority=0 family=ipv6

        salt '*' nftables.new_chain filter foo family=ipv6
    '''

    if not chain:
        return 'Error: Chain needs to be specified'

    if not check_table(table, family=family):
        return 'Error: table {0} in family {1} does not exist' . format(table, family)

    if check_chain(table, chain, family=family):
        return 'Error: chain {0} in table {1} in family {1} already exists' . format(chain, table, family)

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = '{0} add chain {1} {2} {3}'.format(_nftables_cmd(), nft_family, table, chain)
    features = ''
    if table_type or hook or priority:
        if table_type:
            features += ' type {0}'.format(table_type)
        if hook:
            features += ' hook {0}'.format(hook)
        if priority:
            features += ' priority {0}'.format(priority)
        cmd = '{0} \\{{ {1}\\; \\}}'.format(cmd, features)

    out = __salt__['cmd.run'](cmd)

    if not out:
        out = True
    return out


def delete_chain(table='filter', chain=None, family='ipv4'):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Delete the chain from the specified table.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.delete_chain filter input

        salt '*' nftables.delete_chain filter foo

        IPv6:
        salt '*' nftables.delete_chain filter input family=ipv6

        salt '*' nftables.delete_chain filter foo family=ipv6
    '''

    if not chain:
        return 'Error: Chain needs to be specified'

    if not check_table(table, family=family):
        return 'Error: table {0} in family {1} does not exist' . format(table, family)

    if not check_chain(table, chain, family=family):
        return 'Error: chain {0} in table {1} in family {1} does not exist' . format(chain, table, family)

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = '{0} delete chain {1} {2} {3}'.format(_nftables_cmd(), nft_family, table, chain)
    out = __salt__['cmd.run'](cmd)

    if not out:
        out = True
    return out


def append(table='filter', chain=None, rule=None, family='ipv4'):
    '''
    Append a rule to the specified table & chain.

    This function accepts a rule in a standard nftables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.append filter input \\
            rule='input tcp dport 22 log accept'

        IPv6:
        salt '*' nftables.append filter input \\
            rule='input tcp dport 22 log accept' \\
            family=ipv6
    '''
    if not chain:
        return 'Error: Chain needs to be specified'
    if not rule:
        return 'Error: Rule needs to be specified'

    if not check_table(table, family=family):
        return 'Error: table {0} in family {1} does not exist' . format(table, family)

    if not check_chain(table, chain, family=family):
        return 'Error: chain {0} in table {1} in family {1} does not exist' . format(chain, table, family)

    if check(table, chain, rule, family=family):
        return 'Error: rule {0} chain {1} in table {2} in family {3} already exists' . format(rule, chain, table, family)

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = '{0} add rule {1} {2} {3} {4}'.format(_nftables_cmd(), nft_family, table, chain, rule)
    out = __salt__['cmd.run'](cmd)
    if len(out) == 0:
        return True
    else:
        return False


def insert(table='filter', chain=None, position=None, rule=None, family='ipv4'):
    '''
    Insert a rule into the specified table & chain, at the specified position.

    If position is not specified, rule will be inserted in first position.

    This function accepts a rule in a standard nftables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Examples:

    .. code-block:: bash

        salt '*' nftables.insert filter input \\
            rule='input tcp dport 22 log accept'

        salt '*' nftables.insert filter input position=3 \\
            rule='input tcp dport 22 log accept'

        IPv6:
        salt '*' nftables.insert filter input \\
            rule='input tcp dport 22 log accept' \\
            family=ipv6

        salt '*' nftables.insert filter input position=3 \\
            rule='input tcp dport 22 log accept' \\
            family=ipv6
    '''
    if not chain:
        return 'Error: Chain needs to be specified'
    if not rule:
        return 'Error: Rule needs to be specified'

    if not check_table(table, family=family):
        return 'Error: table {0} in family {1} does not exist' . format(table, family)

    if not check_chain(table, chain, family=family):
        return 'Error: chain {0} in table {1} in family {1} does not exist' . format(chain, table, family)

    if check(table, chain, rule, family=family):
        return 'Error: rule {0} chain {1} in table {2} in family {3} already exists' . format(rule, chain, table, family)

    nft_family = _NFTABLES_FAMILIES[family]
    if position:
        cmd = '{0} insert rule {1} {2} {3} position {4} {5}'.format(_nftables_cmd(), nft_family, table, chain, position, rule)
    else:
        cmd = '{0} insert rule {1} {2} {3} {4}'.format(_nftables_cmd(), nft_family, table, chain, rule)
    out = __salt__['cmd.run'](cmd)

    if len(out) == 0:
        return True
    else:
        return False


def delete(table, chain=None, position=None, rule=None, family='ipv4'):
    '''
    Delete a rule from the specified table & chain, specifying either the rule
        in its entirety, or the rule's position in the chain.

    This function accepts a rule in a standard nftables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Examples:

    .. code-block:: bash

        salt '*' nftables.delete filter input position=3

        salt '*' nftables.delete filter input \\
            rule='input tcp dport 22 log accept'

        IPv6:
        salt '*' nftables.delete filter input position=3 family=ipv6

        salt '*' nftables.delete filter input \\
            rule='input tcp dport 22 log accept' \\
            family=ipv6
    '''

    if position and rule:
        return 'Error: Only specify a position or a rule, not both'

    if not check_table(table, family=family):
        return 'Error: table {0} in family {1} does not exist' . format(table, family)

    if not check_chain(table, chain, family=family):
        return 'Error: chain {0} in table {1} in family {1} does not exist' . format(chain, table, family)

    if not check(table, chain, rule, family=family):
        return 'Error: rule {0} chain {1} in table {2} in family {3} does not exists' . format(chain, table, family)

    # nftables rules can only be deleted using the handle
    # if we don't have it, find it.
    if not position:
        position = get_rule_handle(table, chain, rule, family)

    nft_family = _NFTABLES_FAMILIES[family]
    cmd = '{0} delete rule {1} {2} {3} handle {4}'.format(_nftables_cmd(), nft_family, table, chain, position)
    out = __salt__['cmd.run'](cmd)

    if len(out) == 0:
        return True
    else:
        return False


def flush(table='filter', chain='', family='ipv4'):
    '''
    Flush the chain in the specified table, flush all chains in the specified
    table if chain is not specified.

    CLI Example:

    .. code-block:: bash

        salt '*' nftables.flush filter

        salt '*' nftables.flush filter input

        IPv6:
        salt '*' nftables.flush filter input family=ipv6
    '''
    if not check_table(table, family=family):
        return 'Error: table {0} in family {1} does not exist' . format(table, family)

    if chain:
        if not check_chain(table, chain, family=family):
            return 'Error: chain {0} in table {1} in family {1} does not exist' . format(chain, table, family)
        cmd = '{0} flush chain {1} {2}'.format(_nftables_cmd(), table, chain)
    else:
        cmd = '{0} flush table {1}'.format(_nftables_cmd(), table)
    out = __salt__['cmd.run'](cmd)

    if len(out) == 0:
        return True
    else:
        return False
