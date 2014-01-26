# -*- coding: utf-8 -*-
'''
Support for iptables
'''

# Import python libs
import os
import sys
import shlex

# Import salt libs
import salt.utils
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS
from salt.exceptions import SaltException


def __virtual__():
    '''
    Only load the module if iptables is installed
    '''
    if salt.utils.which('iptables'):
        return 'iptables'
    return False


def _iptables_cmd(family='ipv4'):
    '''
    Return correct command based on the family, eg. ipv4 or ipv6
    '''
    if family == 'ipv6':
        return 'ip6tables'
    else:
        return 'iptables'


def _conf(family='ipv4'):
    '''
    Some distros have a specific location for config files
    '''
    if __grains__['os_family'] == 'RedHat':
        if family == 'ipv6':
            return '/etc/sysconfig/ip6tables'
        else:
            return '/etc/sysconfig/iptables'
    elif __grains__['os_family'] == 'Arch':
        if family == 'ipv6':
            return '/etc/iptables/ip6tables.rules'
        else:
            return '/etc/iptables/iptables.rules'
    elif __grains__['os_family'] == 'Debian':
        if family == 'ipv6':
            return '/etc/iptables/rules.v4'
        else:
            return '/etc/iptables/rules.v6'
    elif __grains__['os'] == 'Gentoo':
        if family == 'ipv6':
            return '/var/lib/ip6tables/rules-save'
        else:
            return '/var/lib/iptables/rules-save'
    else:
        return False


def version(family='ipv4'):
    '''
    Return version from iptables --version

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.version

        IPv6:
        salt '*' iptables.version family=ipv6
    '''
    cmd = '{0} --version' . format(_iptables_cmd(family))
    out = __salt__['cmd.run'](cmd).split()
    return out[1]


def build_rule(table=None, chain=None, command=None, position='', full=None, family='ipv4',
               **kwargs):
    '''
    Build a well-formatted iptables rule based on kwargs. Long options must be
    used (`--jump` instead of `-j`) because they will have the `--` added to
    them. A `table` and `chain` are not required, unless `full` is True.

    If `full` is `True`, then `table`, `chain` and `command` are required.
    `command` may be specified as either a short option ('I') or a long option
    (`--insert`). This will return the iptables command, exactly as it would
    be used from the command line.

    If a position is required (as with `-I` or `-D`), it may be specified as
    `position`. This will only be useful if `full` is True.

    If `connstate` is passed in, it will automatically be changed to `state`.

    CLI Examples:

    .. code-block:: bash

        salt '*' iptables.build_rule match=state \\
            connstate=RELATED,ESTABLISHED jump=ACCEPT
        salt '*' iptables.build_rule filter INPUT command=I position=3 \\
            full=True match=state state=RELATED,ESTABLISHED jump=ACCEPT

        IPv6:
        salt '*' iptables.build_rule match=state \\
            connstate=RELATED,ESTABLISHED jump=ACCEPT \\
            family=ipv6
        salt '*' iptables.build_rule filter INPUT command=I position=3 \\
            full=True match=state state=RELATED,ESTABLISHED jump=ACCEPT \\
            family=ipv6

    '''
    if 'target' in kwargs:
        kwargs['jump'] = kwargs['target']
        del kwargs['target']

    for ignore in list(_STATE_INTERNAL_KEYWORDS) + ['chain', 'save', 'table']:
        if ignore in kwargs:
            del kwargs[ignore]

    rule = ''

    if 'if' in kwargs:
        rule += '-i {0} '.format(kwargs['if'])
        del kwargs['if']

    if 'proto' in kwargs:
        rule += '-p {0} '.format(kwargs['proto'])

    if 'match' in kwargs:
        rule += '-m {0} '.format(kwargs['match'])
        del kwargs['match']

    if 'state' in kwargs:
        del kwargs['state']

    if 'connstate' in kwargs:
        rule += '--state {0} '.format(kwargs['connstate'])
        del kwargs['connstate']

    if 'proto' in kwargs:
        rule += '-m {0} '.format(kwargs['proto'])
        del kwargs['proto']

    if 'dport' in kwargs:
        rule += '--dport {0} '.format(kwargs['dport'])
        del kwargs['dport']

    if 'sport' in kwargs:
        rule += '--sport {0} '.format(kwargs['sport'])
        del kwargs['sport']

    # Jumps should appear last, except for any arguments that are passed to
    # jumps, which of course need to follow.
    after_jump = []

    if 'jump' in kwargs:
        after_jump.append('--jump {0} '.format(kwargs['jump']))
        del kwargs['jump']

    if 'j' in kwargs:
        after_jump.append('-j {0} '.format(kwargs['j']))
        del kwargs['j']

    if 'to-port' in kwargs:
        after_jump.append('--to-port {0} '.format(kwargs['to-port']))
        del kwargs['to-port']

    if 'to-ports' in kwargs:
        after_jump.append('--to-ports {0} '.format(kwargs['to-ports']))
        del kwargs['to-ports']

    for item in kwargs:
        if len(item) == 1:
            rule += '-{0} {1} '.format(item, kwargs[item])
        else:
            rule += '--{0} {1} '.format(item, kwargs[item])

    for item in after_jump:
        rule += item

    if full is True:
        if not table:
            return 'Error: Table needs to be specified'
        if not chain:
            return 'Error: Chain needs to be specified'
        if not command:
            return 'Error: Command needs to be specified'

        if command in 'ACDIRLSFZNXPE':
            flag = '-'
        else:
            flag = '--'

        return '{0} -t {1} {2}{3} {4} {5} {6}'.format(_iptables_cmd(family),
            table, flag, command, chain, position, rule)

    return rule


def get_saved_rules(conf_file=None, family='ipv4'):
    '''
    Return a data structure of the rules in the conf file

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.get_saved_rules

        IPv6:
        salt '*' iptables.get_saved_rules family=ipv6
    '''
    return _parse_conf(conf_file, family)


def get_rules(family='ipv4'):
    '''
    Return a data structure of the current, in-memory rules

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.get_rules

        IPv6:
        salt '*' iptables.get_rules family=ipv6

    '''
    return _parse_conf(in_mem=True, family=family)


def get_saved_policy(table='filter', chain=None, conf_file=None, family='ipv4'):
    '''
    Return the current policy for the specified table/chain

    CLI Examples:

    .. code-block:: bash

        salt '*' iptables.get_saved_policy filter INPUT
        salt '*' iptables.get_saved_policy filter INPUT \\
            conf_file=/etc/iptables.saved

        IPv6:
        salt '*' iptables.get_saved_policy filter INPUT family=ipv6
        salt '*' iptables.get_saved_policy filter INPUT \\
            conf_file=/etc/iptables.saved family=ipv6

    '''
    if not chain:
        return 'Error: Chain needs to be specified'

    rules = _parse_conf(conf_file, family=family)
    return rules[table][chain]['policy']


def get_policy(table='filter', chain=None, family='ipv4'):
    '''
    Return the current policy for the specified table/chain

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.get_policy filter INPUT

        IPv6:
        salt '*' iptables.get_policy filter INPUT family=ipv6
    '''
    if not chain:
        return 'Error: Chain needs to be specified'

    rules = _parse_conf(in_mem=True, family=family)
    return rules[table][chain]['policy']


def set_policy(table='filter', chain=None, policy=None, family='ipv4'):
    '''
    Set the current policy for the specified table/chain

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.set_policy filter INPUT ACCEPT

        IPv6:
        salt '*' iptables.set_policy filter INPUT ACCEPT family=ipv6
    '''
    if not chain:
        return 'Error: Chain needs to be specified'
    if not policy:
        return 'Error: Policy needs to be specified'

    cmd = '{0} -t {1} -P {2} {3}'.format(_iptables_cmd(family), table, chain, policy)
    out = __salt__['cmd.run'](cmd)
    return out


def save(filename=None, family='ipv4'):
    '''
    Save the current in-memory rules to disk

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.save /etc/sysconfig/iptables

        IPv6:
        salt '*' iptables.save /etc/sysconfig/iptables family=ipv6
    '''
    if _conf() and not filename:
        filename = _conf()

    parent_dir = os.path.dirname(filename)
    if not os.path.isdir(parent_dir):
        os.makedirs(parent_dir)
    cmd = '{0}-save > {1}'.format(_iptables_cmd(family), filename)
    out = __salt__['cmd.run'](cmd)
    return out


def check(table='filter', chain=None, rule=None, family='ipv4'):
    '''
    Check for the existance of a rule in the table and chain

    This function accepts a rule in a standard iptables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.check filter INPUT \\
            rule='-m state --state RELATED,ESTABLISHED -j ACCEPT'

        IPv6:
        salt '*' iptables.check filter INPUT \\
            rule='-m state --state RELATED,ESTABLISHED -j ACCEPT' \\
            family=ipv6
    '''
    if not chain:
        return 'Error: Chain needs to be specified'
    if not rule:
        return 'Error: Rule needs to be specified'

    if __grains__['os_family'] == 'RedHat':
        cmd = '{0}-save' . format(_iptables_cmd(family))
        out = __salt__['cmd.run'](cmd).find('-A {1} {2}'.format(
            table,
            chain,
            rule,
        ))
        if out != -1:
            out = ''
        else:
            return False
    else:
        cmd = '{0} -t {1} -C {2} {3}'.format(_iptables_cmd(family), table, chain, rule)
        out = __salt__['cmd.run'](cmd)

    if not out:
        return True
    return out


def check_chain(table='filter', chain=None, family='ipv4'):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Check for the existance of a chain in the table

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.check_chain filter INPUT

        IPv6:
        salt '*' iptables.check_chain filter INPUT family=ipv6
    '''

    if not chain:
        return 'Error: Chain needs to be specified'

    cmd = '{0}-save -t {1}'.format(_iptables_cmd(family), table)
    out = __salt__['cmd.run'](cmd).find(':{1} '.format(table, chain))

    if out != -1:
        out = True
    else:
        out = False

    return out


def new_chain(table='filter', chain=None, family='ipv4'):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Create new custom chain to the specified table.

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.new_chain filter CUSTOM_CHAIN

        IPv6:
        salt '*' iptables.new_chain filter CUSTOM_CHAIN family=ipv6
    '''

    if not chain:
        return 'Error: Chain needs to be specified'

    cmd = '{0} -t {1} -N {2}'.format(_iptables_cmd(family), table, chain)
    out = __salt__['cmd.run'](cmd)

    if not out:
        out = True
    return out


def delete_chain(table='filter', chain=None, family='ipv4'):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Delete custom chain to the specified table.

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.delete_chain filter CUSTOM_CHAIN

        IPv6:
        salt '*' iptables.delete_chain filter CUSTOM_CHAIN family=ipv6
    '''

    if not chain:
        return 'Error: Chain needs to be specified'

    cmd = '{0} -t {1} -X {2}'.format(_iptables_cmd(family), table, chain)
    out = __salt__['cmd.run'](cmd)

    if not out:
        out = True
    return out


def append(table='filter', chain=None, rule=None, family='ipv4'):
    '''
    Append a rule to the specified table/chain.

    This function accepts a rule in a standard iptables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.append filter INPUT \\
            rule='-m state --state RELATED,ESTABLISHED -j ACCEPT'

        IPv6:
        salt '*' iptables.append filter INPUT \\
            rule='-m state --state RELATED,ESTABLISHED -j ACCEPT' \\
            family=ipv6
    '''
    if not chain:
        return 'Error: Chain needs to be specified'
    if not rule:
        return 'Error: Rule needs to be specified'

    cmd = '{0} -t {1} -A {2} {3}'.format(_iptables_cmd(family), table, chain, rule)
    out = __salt__['cmd.run'](cmd)
    if len(out) == 0:
        return True
    else:
        return False


def insert(table='filter', chain=None, position=None, rule=None, family='ipv4'):
    '''
    Insert a rule into the specified table/chain, at the specified position.

    This function accepts a rule in a standard iptables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Examples:

    .. code-block:: bash

        salt '*' iptables.insert filter INPUT position=3 \\
            rule='-m state --state RELATED,ESTABLISHED -j ACCEPT'

        IPv6:
        salt '*' iptables.insert filter INPUT position=3 \\
            rule='-m state --state RELATED,ESTABLISHED -j ACCEPT' \\
            family=ipv6
    '''
    if not chain:
        return 'Error: Chain needs to be specified'
    if not position:
        return 'Error: Position needs to be specified or use append (-A)'
    if not rule:
        return 'Error: Rule needs to be specified'

    cmd = '{0} -t {1} -I {2} {3} {4}'.format(_iptables_cmd(family), table, chain, position, rule)
    out = __salt__['cmd.run'](cmd)
    return out


def delete(table, chain=None, position=None, rule=None, family='ipv4'):
    '''
    Delete a rule from the specified table/chain, specifying either the rule
        in its entirety, or the rule's position in the chain.

    This function accepts a rule in a standard iptables command format,
        starting with the chain. Trying to force users to adapt to a new
        method of creating rules would be irritating at best, and we
        already have a parser that can handle it.

    CLI Examples:

    .. code-block:: bash

        salt '*' iptables.delete filter INPUT position=3
        salt '*' iptables.delete filter INPUT \\
            rule='-m state --state RELATED,ESTABLISHED -j ACCEPT'

        IPv6:
        salt '*' iptables.delete filter INPUT position=3 family=ipv6
        salt '*' iptables.delete filter INPUT \\
            rule='-m state --state RELATED,ESTABLISHED -j ACCEPT' \\
            family=ipv6
    '''

    if position and rule:
        return 'Error: Only specify a position or a rule, not both'

    if position:
        rule = position

    cmd = '{0} -t {1} -D {2} {3}'.format(_iptables_cmd(family), table, chain, rule)
    out = __salt__['cmd.run'](cmd)
    return out


def flush(table='filter', chain='', family='ipv4'):
    '''
    Flush the chain in the specified table, flush all chains in the specified
    table if not specified chain.

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.flush filter INPUT

        IPv6:
        salt '*' iptables.flush filter INPUT family=ipv6
    '''

    if chain:
        cmd = '{0} -t {1} -F {2}'.format(_iptables_cmd(family), table, chain)
    else:
        cmd = '{0} -t {1} -F'.format(_iptables_cmd(family), table)
    out = __salt__['cmd.run'](cmd)
    return out


def _parse_conf(conf_file=None, in_mem=False, family='ipv4'):
    '''
    If a file is not passed in, and the correct one for this OS is not
    detected, return False
    '''
    if _conf() and not conf_file and not in_mem:
        conf_file = _conf(family)

    rules = ''
    if conf_file:
        with salt.utils.fopen(conf_file, 'r') as ifile:
            rules = ifile.read()
    elif in_mem:
        cmd = '{0}-save' . format(_iptables_cmd(family))
        rules = __salt__['cmd.run'](cmd)
    else:
        raise SaltException('A file was not found to parse')

    ret = {}
    table = ''
    for line in rules.splitlines():
        if line.startswith('*'):
            table = line.replace('*', '')
            ret[table] = {}
        elif line.startswith(':'):
            comps = line.split()
            chain = comps[0].replace(':', '')
            ret[table][chain] = {}
            ret[table][chain]['policy'] = comps[1]
            counters = comps[2].replace('[', '').replace(']', '')
            (pcount, bcount) = counters.split(':')
            ret[table][chain]['packet count'] = pcount
            ret[table][chain]['byte count'] = bcount
            ret[table][chain]['rules'] = []
            ret[table][chain]['rules_comment'] = {}
        elif line.startswith('-A'):
            parser = _parser()
            parsed_args = []
            if sys.version.startswith('2.6'):
                (opts, args) = parser.parse_args(shlex.split(line))
                parsed_args = vars(opts)
            else:
                parsed_args = vars(parser.parse_args(shlex.split(line)))
            ret_args = {}
            chain = parsed_args['append']
            if not sys.version.startswith('2.6'):
                if isinstance(chain, list):
                    chain = chain[0]
            for arg in parsed_args:
                if parsed_args[arg] and arg is not 'append':
                    ret_args[arg] = parsed_args[arg]
            if parsed_args['comment'] is not None:
                comment = parsed_args['comment'][0].strip('"')
                ret[table][chain[0]]['rules_comment'][comment] = ret_args
            ret[table][chain[0]]['rules'].append(ret_args)
    return ret


def _parser():
    '''
    This function contains _all_ the options I could find in man 8 iptables,
    listed in the first section that I found them in. They will not all be used
    by all parts of the module; use them intelligently and appropriately.
    '''
    add_arg = None
    if sys.version.startswith('2.6'):
        import optparse
        parser = optparse.OptionParser()
        add_arg = parser.add_option
    else:
        import argparse
        parser = argparse.ArgumentParser()
        add_arg = parser.add_argument

    # COMMANDS
    if sys.version.startswith('2.6'):
        add_arg('-A', '--append', dest='append', action='append')
    else:
        add_arg('-A', '--append', dest='append', action='append', nargs='*')
    add_arg('-D', '--delete', dest='delete', action='append')
    add_arg('-I', '--insert', dest='insert', action='append')
    add_arg('-R', '--replace', dest='replace', action='append')
    add_arg('-L', '--list', dest='list', action='append')
    add_arg('-F', '--flush', dest='flush', action='append')
    add_arg('-Z', '--zero', dest='zero', action='append')
    add_arg('-N', '--new-chain', dest='new-chain', action='append')
    add_arg('-X', '--delete-chain', dest='delete-chain', action='append')
    add_arg('-P', '--policy', dest='policy', action='append')
    add_arg('-E', '--rename-chain', dest='rename-chain', action='append')

    # PARAMETERS
    add_arg('-p', '--protocol', dest='protocol', action='append')
    if sys.version.startswith('2.6'):
        add_arg('-s', '--source', dest='source', action='append')
        add_arg('-d', '--destination', dest='destination', action='append')
    else:
        add_arg('-s', '--source', dest='source', action='append', nargs='*')
        add_arg('-d', '--destination', dest='destination', action='append',
                nargs='*')
    add_arg('-j', '--jump', dest='jump', action='append')
    add_arg('-g', '--goto', dest='goto', action='append')
    add_arg('-i', '--in-interface', dest='in-interface', action='append')
    add_arg('-o', '--out-interface', dest='out-interface', action='append')
    add_arg('-f', '--fragment', dest='fragment', action='append')
    add_arg('-c', '--set-counters', dest='set-counters', action='append')

    # MATCH EXTENSIONS
    add_arg('-m', '--match', dest='match', action='append')
    ## addrtype
    add_arg('--src-type', dest='src-type', action='append')
    add_arg('--dst-type', dest='dst-type', action='append')
    add_arg('--limit-iface-in', dest='limit-iface-in', action='append')
    add_arg('--limit-iface-out', dest='limit-iface-out', action='append')
    ## ah
    add_arg('--ahspi', dest='ahspi', action='append')
    ## cluster
    add_arg('--cluster-total-nodes',
            dest='cluster-total-nodes',
            action='append')
    add_arg('--cluster-local-node', dest='cluster-local-node', action='append')
    add_arg('--cluster-local-nodemask',
            dest='cluster-local-nodemask',
            action='append')
    add_arg('--cluster-hash-seed', dest='cluster-hash-seed', action='append')
    add_arg('--h-length', dest='h-length', action='append')
    add_arg('--mangle-mac-s', dest='mangle-mac-s', action='append')
    add_arg('--mangle-mac-d', dest='mangle-mac-d', action='append')
    ## comment
    add_arg('--comment', dest='comment', action='append')
    ## connbytes
    add_arg('--connbytes', dest='connbytes', action='append')
    add_arg('--connbytes-dir', dest='connbytes-dir', action='append')
    add_arg('--connbytes-mode', dest='connbytes-mode', action='append')
    ## connlimit
    add_arg('--connlimit-above', dest='connlimit-above', action='append')
    add_arg('--connlimit-mask', dest='connlimit-mask', action='append')
    ## connmark
    add_arg('--mark', dest='mark', action='append')
    ## conntrack
    add_arg('--ctstate', dest='ctstate', action='append')
    add_arg('--ctproto', dest='ctproto', action='append')
    add_arg('--ctorigsrc', dest='ctorigsrc', action='append')
    add_arg('--ctorigdst', dest='ctorigdst', action='append')
    add_arg('--ctreplsrc', dest='ctreplsrc', action='append')
    add_arg('--ctrepldst', dest='ctrepldst', action='append')
    add_arg('--ctorigsrcport', dest='ctorigsrcport', action='append')
    add_arg('--ctorigdstport', dest='ctorigdstport', action='append')
    add_arg('--ctreplsrcport', dest='ctreplsrcport', action='append')
    add_arg('--ctrepldstport', dest='ctrepldstport', action='append')
    add_arg('--ctstatus', dest='ctstatus', action='append')
    add_arg('--ctexpire', dest='ctexpire', action='append')
    ## dccp
    add_arg('--sport', '--source-port', dest='source_port', action='append')
    add_arg('--dport',
            '--destination-port',
            dest='destination_port',
            action='append')
    add_arg('--dccp-types', dest='dccp-types', action='append')
    add_arg('--dccp-option', dest='dccp-option', action='append')
    ## dscp
    add_arg('--dscp', dest='dscp', action='append')
    add_arg('--dscp-class', dest='dscp-class', action='append')
    ## ecn
    add_arg('--ecn-tcp-cwr', dest='ecn-tcp-cwr', action='append')
    add_arg('--ecn-tcp-ece', dest='ecn-tcp-ece', action='append')
    add_arg('--ecn-ip-ect', dest='ecn-ip-ect', action='append')
    ## esp
    add_arg('--espspi', dest='espspi', action='append')
    ## hashlimit
    add_arg('--hashlimit-upto', dest='hashlimit-upto', action='append')
    add_arg('--hashlimit-above', dest='hashlimit-above', action='append')
    add_arg('--hashlimit-burst', dest='hashlimit-burst', action='append')
    add_arg('--hashlimit-mode', dest='hashlimit-mode', action='append')
    add_arg('--hashlimit-srcmask', dest='hashlimit-srcmask', action='append')
    add_arg('--hashlimit-dstmask', dest='hashlimit-dstmask', action='append')
    add_arg('--hashlimit-name', dest='hashlimit-name', action='append')
    add_arg('--hashlimit-htable-size',
            dest='hashlimit-htable-size',
            action='append')
    add_arg('--hashlimit-htable-max',
            dest='hashlimit-htable-max',
            action='append')
    add_arg('--hashlimit-htable-expire',
            dest='hashlimit-htable-expire',
            action='append')
    add_arg('--hashlimit-htable-gcinterval',
            dest='hashlimit-htable-gcinterval',
            action='append')
    ## helper
    add_arg('--helper', dest='helper', action='append')
    ## icmp
    add_arg('--icmp-type', dest='icmp-type', action='append')
    ## iprange
    add_arg('--src-range', dest='src-range', action='append')
    add_arg('--dst-range', dest='dst-range', action='append')
    ## length
    add_arg('--length', dest='length', action='append')
    ## limit
    add_arg('--limit', dest='limit', action='append')
    add_arg('--limit-burst', dest='limit-burst', action='append')
    ## mac
    add_arg('--mac-source', dest='mac-source', action='append')
    ## multiport
    add_arg('--sports', '--source-ports', dest='source-ports', action='append')
    add_arg('--dports',
            '--destination-ports',
            dest='destination-ports',
            action='append')
    add_arg('--ports', dest='ports', action='append')
    ## owner
    add_arg('--uid-owner', dest='uid-owner', action='append')
    add_arg('--gid-owner', dest='gid-owner', action='append')
    add_arg('--socket-exists', dest='socket-exists', action='append')
    ## physdev
    add_arg('--physdev-in', dest='physdev-in', action='append')
    add_arg('--physdev-out', dest='physdev-out', action='append')
    add_arg('--physdev-is-in', dest='physdev-is-in', action='append')
    add_arg('--physdev-is-out', dest='physdev-is-out', action='append')
    add_arg('--physdev-is-bridged', dest='physdev-is-bridged', action='append')
    ## pkttype
    add_arg('--pkt-type', dest='pkt-type', action='append')
    ## policy
    add_arg('--dir', dest='dir', action='append')
    add_arg('--pol', dest='pol', action='append')
    add_arg('--strict', dest='strict', action='append')
    add_arg('--reqid', dest='reqid', action='append')
    add_arg('--spi', dest='spi', action='append')
    add_arg('--proto', dest='proto', action='append')
    add_arg('--mode', dest='mode', action='append')
    add_arg('--tunnel-src', dest='tunnel-src', action='append')
    add_arg('--tunnel-dst', dest='tunnel-dst', action='append')
    add_arg('--next', dest='next', action='append')
    ## quota
    add_arg('--quota', dest='quota', action='append')
    ## rateest
    add_arg('--rateest1', dest='rateest1', action='append')
    add_arg('--rateest2', dest='rateest2', action='append')
    add_arg('--rateest-delta', dest='rateest-delta', action='append')
    add_arg('--rateest1-bps', dest='rateest1-bps', action='append')
    add_arg('--rateest2-bps', dest='rateest2-bps', action='append')
    add_arg('--rateest1-pps', dest='rateest1-pps', action='append')
    add_arg('--rateest2-pps', dest='rateest2-pps', action='append')
    add_arg('--rateest1-lt', dest='rateest1-lt', action='append')
    add_arg('--rateest1-gt', dest='rateest1-gt', action='append')
    add_arg('--rateest1-eq', dest='rateest1-eq', action='append')
    add_arg('--rateest-name', dest='rateest-name', action='append')
    add_arg('--rateest-interval', dest='rateest-interval', action='append')
    add_arg('--rateest-ewma', dest='rateest-ewma', action='append')
    ## realm
    add_arg('--realm', dest='realm', action='append')
    ## recent
    add_arg('--set', dest='set', action='append')
    add_arg('--name', dest='name', action='append')
    add_arg('--rsource', dest='rsource', action='append')
    add_arg('--rdest', dest='rdest', action='append')
    add_arg('--rcheck', dest='rcheck', action='append')
    add_arg('--update', dest='update', action='append')
    add_arg('--remove', dest='remove', action='append')
    add_arg('--seconds', dest='seconds', action='append')
    add_arg('--hitcount', dest='hitcount', action='append')
    add_arg('--rttl', dest='rttl', action='append')
    ## sctp
    add_arg('--chunk-types', dest='chunk-types', action='append')
    ## set
    add_arg('--match-set', dest='match-set', action='append')
    ## socket
    add_arg('--transparent', dest='transparent', action='append')
    ## state
    add_arg('--state', dest='state', action='append')
    ## statistic
    add_arg('--probability', dest='probability', action='append')
    add_arg('--every', dest='every', action='append')
    add_arg('--packet', dest='packet', action='append')
    ## string
    add_arg('--algo', dest='algo', action='append')
    add_arg('--from', dest='from', action='append')
    add_arg('--to', dest='to', action='append')
    add_arg('--string', dest='string', action='append')
    add_arg('--hex-string', dest='hex-string', action='append')
    ## tcp
    add_arg('--tcp-flags', dest='tcp-flags', action='append')
    add_arg('--syn', dest='syn', action='append')
    add_arg('--tcp-option', dest='tcp-option', action='append')
    ## tcpmss
    add_arg('--mss', dest='mss', action='append')
    ## time
    add_arg('--datestart', dest='datestart', action='append')
    add_arg('--datestop', dest='datestop', action='append')
    add_arg('--monthdays', dest='monthdays', action='append')
    add_arg('--weekdays', dest='weekdays', action='append')
    add_arg('--utc', dest='utc', action='append')
    add_arg('--localtz', dest='localtz', action='append')
    ## tos
    add_arg('--tos', dest='tos', action='append')
    ## ttl
    add_arg('--ttl-eq', dest='ttl-eq', action='append')
    add_arg('--ttl-gt', dest='ttl-gt', action='append')
    add_arg('--ttl-lt', dest='ttl-lt', action='append')
    ## u32
    add_arg('--u32', dest='u32', action='append')

    # CHECKSUM
    add_arg('--checksum-fill', dest='checksum-fill', action='append')

    # CLASSIFY
    add_arg('--set-class', dest='set-class', action='append')

    # CLUSTERIP
    add_arg('--new', dest='new', action='append')
    add_arg('--hashmode', dest='hashmode', action='append')
    add_arg('--clustermac', dest='clustermac', action='append')
    add_arg('--total-nodes', dest='total-nodes', action='append')
    add_arg('--local-node', dest='local-node', action='append')
    add_arg('--hash-init', dest='hash-init', action='append')

    # CONNMARK
    add_arg('--set-xmark', dest='set-xmark', action='append')
    add_arg('--save-mark', dest='save-mark', action='append')
    add_arg('--restore-mark', dest='restore-mark', action='append')
    add_arg('--and-mark', dest='and-mark', action='append')
    add_arg('--or-mark', dest='or-mark', action='append')
    add_arg('--xor-mark', dest='xor-mark', action='append')
    add_arg('--set-mark', dest='set-mark', action='append')

    # DNAT
    add_arg('--to-destination', dest='to-destination', action='append')
    add_arg('--random', dest='random', action='append')
    add_arg('--persistent', dest='persistent', action='append')

    # DSCP
    add_arg('--set-dscp', dest='set-dscp', action='append')
    add_arg('--set-dscp-class', dest='set-dscp-class', action='append')

    # ECN
    add_arg('--ecn-tcp-remove', dest='ecn-tcp-remove', action='append')

    # LOG
    add_arg('--log-level', dest='log-level', action='append')
    add_arg('--log-prefix', dest='log-prefix', action='append')
    add_arg('--log-tcp-sequence', dest='log-tcp-sequence', action='append')
    add_arg('--log-tcp-options', dest='log-tcp-options', action='append')
    add_arg('--log-ip-options', dest='log-ip-options', action='append')
    add_arg('--log-uid', dest='log-uid', action='append')

    # NFLOG
    add_arg('--nflog-group', dest='nflog-group', action='append')
    add_arg('--nflog-prefix', dest='nflog-prefix', action='append')
    add_arg('--nflog-range', dest='nflog-range', action='append')
    add_arg('--nflog-threshold', dest='nflog-threshold', action='append')

    # NFQUEUE
    add_arg('--queue-num', dest='queue-num', action='append')
    add_arg('--queue-balance', dest='queue-balance', action='append')

    # RATEEST
    add_arg('--rateest-ewmalog', dest='rateest-ewmalog', action='append')

    # REDIRECT
    add_arg('--to-ports', dest='to-ports', action='append')

    # REJECT
    add_arg('--reject-with', dest='reject-with', action='append')

    # SAME
    add_arg('--nodst', dest='nodst', action='append')

    # SECMARK
    add_arg('--selctx', dest='selctx', action='append')

    # SET
    add_arg('--add-set', dest='add-set', action='append')
    add_arg('--del-set', dest='del-set', action='append')

    # SNAT
    add_arg('--to-source', dest='to-source', action='append')

    # TCPMSS
    add_arg('--set-mss', dest='set-mss', action='append')
    add_arg('--clamp-mss-to-pmtu', dest='clamp-mss-to-pmtu', action='append')

    # TCPOPTSTRIP
    add_arg('--strip-options', dest='strip-options', action='append')

    # TOS
    add_arg('--set-tos', dest='set-tos', action='append')
    add_arg('--and-tos', dest='and-tos', action='append')
    add_arg('--or-tos', dest='or-tos', action='append')
    add_arg('--xor-tos', dest='xor-tos', action='append')

    # TPROXY
    add_arg('--on-port', dest='on-port', action='append')
    add_arg('--on-ip', dest='on-ip', action='append')
    add_arg('--tproxy-mark', dest='tproxy-mark', action='append')

    # TTL
    add_arg('--ttl-set', dest='ttl-set', action='append')
    add_arg('--ttl-dec', dest='ttl-dec', action='append')
    add_arg('--ttl-inc', dest='ttl-inc', action='append')

    # ULOG
    add_arg('--ulog-nlgroup', dest='ulog-nlgroup', action='append')
    add_arg('--ulog-prefix', dest='ulog-prefix', action='append')
    add_arg('--ulog-cprange', dest='ulog-cprange', action='append')
    add_arg('--ulog-qthreshold', dest='ulog-qthreshold', action='append')

    return parser
