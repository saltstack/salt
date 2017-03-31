# -*- coding: utf-8 -*-
'''
Support for iptables

Configuration Options
---------------------

The following options can be set in the :ref:`minion config
<configuration-salt-minion>`, :ref:`minion grains<configuration-minion-grains>`
, :ref:`minion pillar<configuration-minion-pillar>`, or
`master config<configuration-salt-master>`.

- ``iptables.save_filters``: List of REGEX strings to FILTER OUT matching lines

    This is useful for filtering out chains, rules, etc that you do not
    wish to persist, such as ephemeral Docker rules.

    The default is to not filter out anything.

    .. code-block:: yaml

        iptables.save_filters:
           - "-j CATTLE_PREROUTING"
           - "-j DOCKER"
           - "-A POSTROUTING"
           - "-A CATTLE_POSTROUTING"
           - "-A FORWARD"
'''
from __future__ import absolute_import

# Import python libs
import os
import re
import sys
import uuid
import string

# Import salt libs
import salt.utils
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS
from salt.exceptions import SaltException
from salt.ext import six

import logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load the module if iptables is installed
    '''
    if not salt.utils.which('iptables'):
        return (False, 'The iptables execution module cannot be loaded: iptables not installed.')

    return True


def _iptables_cmd(family='ipv4'):
    '''
    Return correct command based on the family, e.g. ipv4 or ipv6
    '''
    if family == 'ipv6':
        return salt.utils.which('ip6tables')
    else:
        return salt.utils.which('iptables')


def _has_option(option, family='ipv4'):
    '''
    Return truth of whether iptables has `option`.  For example:

    .. code-block:: python

        _has_option('--wait')
        _has_option('--check', family='ipv6')
    '''
    cmd = '{0} --help'.format(_iptables_cmd(family))
    if option in __salt__['cmd.run'](cmd, output_loglevel='quiet'):
        return True
    return False


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
            return '/etc/iptables/rules.v6'
        else:
            return '/etc/iptables/rules.v4'
    elif __grains__['os'] == 'Gentoo':
        if family == 'ipv6':
            return '/var/lib/ip6tables/rules-save'
        else:
            return '/var/lib/iptables/rules-save'
    elif __grains__['os_family'] == 'SUSE':
        # SuSE does not seem to use separate files for IPv4 and IPv6
        return '/etc/sysconfig/scripts/SuSEfirewall2-custom'
    elif __grains__['os'] == 'Alpine':
        if family == 'ipv6':
            return '/etc/iptables/rules6-save'
        else:
            return '/etc/iptables/rules-save'
    else:
        raise SaltException('Saving iptables to file is not' +
                            ' supported on {0}.'.format(__grains__['os']) +
                            ' Please file an issue with SaltStack')


def _conf_save_filters():
    '''
    Return array of strings from `save_filters` in config.

    This array will be pulled from minion config, minion grains,
    minion pillar, or master config.  The default value returned is [].

    .. code-block:: python

        _conf_save_filters()
    '''
    config = __salt__['config.option']('iptables.save_filters', [])
    return config


def _regex_iptables_save(cmd_output, filters=None):
    '''
    Return string with `save_filter` regex entries removed.  For example:

    If `filters` is not provided, it will be pulled from minion config,
    minion grains, minion pillar, or master config. Default return value
    if no filters found is the original cmd_output string.

    .. code-block:: python

        _regex_iptables_save(cmd_output, ['-A DOCKER*'])
    '''
    # grab RE compiled filters from context for performance
    if 'iptables.save_filters' not in __context__:
        __context__['iptables.save_filters'] = []
        for pattern in filters or _conf_save_filters():
            try:
                __context__['iptables.save_filters']\
                    .append(re.compile(pattern))
            except re.error as e:
                log.warning('Skipping regex rule: \'{0}\': {1}'
                            .format(pattern, e))
                continue

    if len(__context__['iptables.save_filters']) > 0:
        # line by line get rid of any regex matches
        _filtered_cmd_output = \
            [line for line in cmd_output.splitlines(True)
             if not any(reg.search(line) for reg
                        in __context__['iptables.save_filters'])]
        return ''.join(_filtered_cmd_output)

    return cmd_output


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


def build_rule(table='filter', chain=None, command=None, position='', full=None, family='ipv4',
               **kwargs):
    '''
    Build a well-formatted iptables rule based on kwargs. A `table` and `chain`
    are not required, unless `full` is True.

    If `full` is `True`, then `table`, `chain` and `command` are required.
    `command` may be specified as either a short option ('I') or a long option
    (`--insert`). This will return the iptables command, exactly as it would
    be used from the command line.

    If a position is required (as with `-I` or `-D`), it may be specified as
    `position`. This will only be useful if `full` is True.

    If `connstate` is passed in, it will automatically be changed to `state`.

    To pass in jump options that doesn't take arguments, pass in an empty
    string.

    CLI Examples:

    .. code-block:: bash

        salt '*' iptables.build_rule match=state \\
            connstate=RELATED,ESTABLISHED jump=ACCEPT

        salt '*' iptables.build_rule filter INPUT command=I position=3 \\
            full=True match=state state=RELATED,ESTABLISHED jump=ACCEPT

        salt '*' iptables.build_rule filter INPUT command=A \\
            full=True match=state state=RELATED,ESTABLISHED \\
            source='127.0.0.1' jump=ACCEPT

        .. Invert Rules
        salt '*' iptables.build_rule filter INPUT command=A \\
            full=True match=state state=RELATED,ESTABLISHED \\
            source='! 127.0.0.1' jump=ACCEPT

        salt '*' iptables.build_rule filter INPUT command=A \\
            full=True match=state state=RELATED,ESTABLISHED \\
            destination='not 127.0.0.1' jump=ACCEPT

        IPv6:
        salt '*' iptables.build_rule match=state \\
            connstate=RELATED,ESTABLISHED jump=ACCEPT \\
            family=ipv6
        salt '*' iptables.build_rule filter INPUT command=I position=3 \\
            full=True match=state state=RELATED,ESTABLISHED jump=ACCEPT \\
            family=ipv6

    '''
    if 'target' in kwargs:
        kwargs['jump'] = kwargs.pop('target')

    # Ignore name and state for this function
    kwargs.pop('name', None)
    kwargs.pop('state', None)

    for ignore in list(_STATE_INTERNAL_KEYWORDS) + ['chain', 'save', 'table']:
        if ignore in kwargs:
            del kwargs[ignore]

    rule = []
    proto = False
    bang_not_pat = re.compile(r'(!|not)\s?')

    def maybe_add_negation(arg):
        '''
        Will check if the defined argument is intended to be negated,
        (i.e. prefixed with '!' or 'not'), and add a '! ' to the rule.

        The prefix will be removed from the value in the kwargs dict.
        '''
        value = str(kwargs[arg])
        if value.startswith('!') or value.startswith('not'):
            kwargs[arg] = re.sub(bang_not_pat, '', value)
            return '! '
        return ''

    if 'if' in kwargs:
        rule.append('{0}-i {1}'.format(maybe_add_negation('if'), kwargs['if']))
        del kwargs['if']

    if 'of' in kwargs:
        rule.append('{0}-o {1}'.format(maybe_add_negation('of'), kwargs['of']))
        del kwargs['of']

    for proto_arg in ('protocol', 'proto'):
        if proto_arg in kwargs:
            if not proto:
                rule.append('{0}-p {1}'.format(maybe_add_negation(proto_arg), kwargs[proto_arg]))
                proto = True
            del kwargs[proto_arg]

    if 'match' in kwargs:
        match_value = kwargs['match']
        if not isinstance(match_value, list):
            match_value = match_value.split(',')
        for match in match_value:
            rule.append('-m {0}'.format(match))
            if 'name_' in kwargs and match.strip() in ('pknock', 'quota2', 'recent'):
                rule.append('--name {0}'.format(kwargs['name_']))
                del kwargs['name_']
        del kwargs['match']

    if 'match-set' in kwargs:
        if isinstance(kwargs['match-set'], six.string_types):
            kwargs['match-set'] = [kwargs['match-set']]
        for match_set in kwargs['match-set']:
            negative_match_set = ''
            if match_set.startswith('!') or match_set.startswith('not'):
                negative_match_set = '! '
                match_set = re.sub(bang_not_pat, '', match_set)
            rule.append('-m set {0}--match-set {1}'.format(negative_match_set, match_set))
        del kwargs['match-set']

    if 'connstate' in kwargs:
        if '-m state' not in rule:
            rule.append('-m state')

        rule.append('{0}--state {1}'.format(maybe_add_negation('connstate'), kwargs['connstate']))

        del kwargs['connstate']

    if 'dport' in kwargs:
        rule.append('{0}--dport {1}'.format(maybe_add_negation('dport'), kwargs['dport']))
        del kwargs['dport']

    if 'sport' in kwargs:
        rule.append('{0}--sport {1}'.format(maybe_add_negation('sport'), kwargs['sport']))
        del kwargs['sport']

    for multiport_arg in ('dports', 'sports'):
        if multiport_arg in kwargs:
            if '-m multiport' not in rule:
                rule.append('-m multiport')
                if not proto:
                    return 'Error: proto must be specified'

            mp_value = kwargs[multiport_arg]
            if isinstance(mp_value, list):
                if any(i for i in mp_value if str(i).startswith('!') or str(i).startswith('not')):
                    mp_value = [re.sub(bang_not_pat, '', str(item)) for item in mp_value]
                    rule.append('!')
                dports = ','.join(str(i) for i in mp_value)
            else:
                if str(mp_value).startswith('!') or str(mp_value).startswith('not'):
                    dports = re.sub(bang_not_pat, '', mp_value)
                    rule.append('!')
                else:
                    dports = mp_value

            rule.append('--{0} {1}'.format(multiport_arg, dports))
            del kwargs[multiport_arg]

    if 'comment' in kwargs:
        if '-m comment' not in rule:
            rule.append('-m comment')

        rule.append('--comment "{0}"'.format(kwargs['comment']))
        del kwargs['comment']

    # --set in ipset is deprecated, works but returns error.
    # rewrite to --match-set if not empty, otherwise treat as recent option
    if 'set' in kwargs and kwargs['set']:
        rule.append('{0}--match-set {1}'.format(maybe_add_negation('set'), kwargs['set']))
        del kwargs['set']

    # Jumps should appear last, except for any arguments that are passed to
    # jumps, which of course need to follow.
    after_jump = []
    # All jump arguments as extracted from man iptables-extensions, man iptables,
    # man xtables-addons and http://www.iptables.info/en/iptables-targets-and-jumps.html
    after_jump_arguments = (
        'j',  # j and jump needs to be first
        'jump',

        # IPTABLES
        'add-set',
        'and-mark',
        'and-tos',
        'checksum-fill',
        'clamp-mss-to-pmtu',
        'clustermac',
        'ctevents',
        'ctmask',
        'del-set',
        'ecn-tcp-remove',
        'exist',
        'expevents',
        'gateway',
        'hash-init',
        'hashmode',
        'helper',
        'label',
        'local-node',
        'log-ip-options',
        'log-level',
        'log-prefix',
        'log-tcp-options',
        'log-tcp-sequence',
        'log-uid',
        'mask',
        'new',
        'nfmask',
        'nflog-group',
        'nflog-prefix',
        'nflog-range',
        'nflog-threshold',
        'nodst',
        'notrack',
        'on-ip',
        'on-port',
        'or-mark',
        'or-tos',
        'persistent',
        'queue-balance',
        'queue-bypass',
        'queue-num',
        'random',
        'rateest-ewmalog',
        'rateest-interval',
        'rateest-name',
        'reject-with',
        'restore',
        'restore-mark',
        #'save',  # no arg, problematic name: How do we avoid collision with this?
        'save-mark',
        'selctx',
        'set-class',
        'set-dscp',
        'set-dscp-class',
        'set-mark',
        'set-mss',
        'set-tos',
        'set-xmark',
        'strip-options',
        'timeout',
        'to',
        'to-destination',
        'to-ports',
        'to-source',
        'total-nodes',
        'tproxy-mark',
        'ttl-dec',
        'ttl-inc',
        'ttl-set',
        'type',
        'ulog-cprange',
        'ulog-nlgroup',
        'ulog-prefix',
        'ulog-qthreshold',
        'xor-mark',
        'xor-tos',
        'zone',

        # IPTABLES-EXTENSIONS
        'dst-pfx',
        'hl-dec',
        'hl-inc',
        'hl-set',
        'hmark-dport-mask',
        'hmark-dst-prefix',
        'hmark-mod',
        'hmark-offset',
        'hmark-proto-mask',
        'hmark-rnd',
        'hmark-spi-mask',
        'hmark-sport-mask',
        'hmark-src-prefix',
        'hmark-tuple',
        'led-always-blink',
        'led-delay',
        'led-trigger-id',
        'queue-cpu-fanout',
        'src-pfx',

        # WEB
        'to-port',

        # XTABLES
        'addr',
        'and-mask',
        'delude',
        'honeypot',
        'or-mask',
        'prefix',
        'reset',
        'reuse',
        'set-mac',
        'shift',
        'static',
        'tarpit',
        'tname',
        'ttl',
    )
    for after_jump_argument in after_jump_arguments:
        if after_jump_argument in kwargs:
            value = kwargs[after_jump_argument]
            if value in (None, ''):  # options without arguments
                after_jump.append('--{0}'.format(after_jump_argument))
            elif any(ws_char in str(value) for ws_char in string.whitespace):
                after_jump.append('--{0} "{1}"'.format(after_jump_argument, value))
            else:
                after_jump.append('--{0} {1}'.format(after_jump_argument, value))
            del kwargs[after_jump_argument]

    for key, value in kwargs.items():
        negation = maybe_add_negation(key)
        flag = '-' if len(key) == 1 else '--'
        value = '' if value in (None, '') else ' {0}'.format(value)
        rule.append('{0}{1}{2}{3}'.format(negation, flag, key, value))

    rule += after_jump

    if full in ['True', 'true']:
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

        wait = '--wait' if _has_option('--wait', family) else ''

        return '{0} {1} -t {2} {3}{4} {5} {6} {7}'.format(_iptables_cmd(family),
               wait, table, flag, command, chain, position, ' '.join(rule))

    return ' '.join(rule)


def get_saved_rules(conf_file=None, family='ipv4'):
    '''
    Return a data structure of the rules in the conf file

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.get_saved_rules

        IPv6:
        salt '*' iptables.get_saved_rules family=ipv6
    '''
    return _parse_conf(conf_file=conf_file, family=family)


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
    try:
        return rules[table][chain]['policy']
    except KeyError:
        return None


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
    try:
        return rules[table][chain]['policy']
    except KeyError:
        return None


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

    wait = '--wait' if _has_option('--wait', family) else ''
    cmd = '{0} {1} -t {2} -P {3} {4}'.format(
            _iptables_cmd(family), wait, table, chain, policy)
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
        filename = _conf(family)

    log.debug('Saving rules to {0}'.format(filename))

    parent_dir = os.path.dirname(filename)
    if not os.path.isdir(parent_dir):
        os.makedirs(parent_dir)
    cmd = '{0}-save'.format(_iptables_cmd(family))
    ipt = __salt__['cmd.run'](cmd)

    # regex out the output if configured with filters
    if len(_conf_save_filters()) > 0:
        ipt = _regex_iptables_save(ipt)

    out = __salt__['file.write'](filename, ipt)
    return out


def check(table='filter', chain=None, rule=None, family='ipv4'):
    '''
    Check for the existence of a rule in the table and chain

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
    ipt_cmd = _iptables_cmd(family)

    if _has_option('--check', family):
        cmd = '{0} -t {1} -C {2} {3}'.format(ipt_cmd, table, chain, rule)
        out = __salt__['cmd.run'](cmd, output_loglevel='quiet')
    else:
        _chain_name = hex(uuid.getnode())

        # Create temporary table
        __salt__['cmd.run']('{0} -t {1} -N {2}'.format(ipt_cmd, table, _chain_name))
        __salt__['cmd.run']('{0} -t {1} -A {2} {3}'.format(ipt_cmd, table, _chain_name, rule))

        out = __salt__['cmd.run']('{0}-save'.format(ipt_cmd))

        # Clean up temporary table
        __salt__['cmd.run']('{0} -t {1} -F {2}'.format(ipt_cmd, table, _chain_name))
        __salt__['cmd.run']('{0} -t {1} -X {2}'.format(ipt_cmd, table, _chain_name))

        for i in out.splitlines():
            if i.startswith('-A {0}'.format(_chain_name)):
                if i.replace(_chain_name, chain) in out.splitlines():
                    return True

        return False

    if not out:
        return True
    return out


def check_chain(table='filter', chain=None, family='ipv4'):
    '''
    .. versionadded:: 2014.1.0

    Check for the existence of a chain in the table

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.check_chain filter INPUT

        IPv6:
        salt '*' iptables.check_chain filter INPUT family=ipv6
    '''

    if not chain:
        return 'Error: Chain needs to be specified'

    cmd = '{0}-save -t {1}'.format(_iptables_cmd(family), table)
    out = __salt__['cmd.run'](cmd).find(':{0} '.format(chain))

    if out != -1:
        out = True
    else:
        out = False

    return out


def new_chain(table='filter', chain=None, family='ipv4'):
    '''
    .. versionadded:: 2014.1.0

    Create new custom chain to the specified table.

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.new_chain filter CUSTOM_CHAIN

        IPv6:
        salt '*' iptables.new_chain filter CUSTOM_CHAIN family=ipv6
    '''

    if not chain:
        return 'Error: Chain needs to be specified'

    wait = '--wait' if _has_option('--wait', family) else ''
    cmd = '{0} {1} -t {2} -N {3}'.format(
            _iptables_cmd(family), wait, table, chain)
    out = __salt__['cmd.run'](cmd)

    if not out:
        out = True
    return out


def delete_chain(table='filter', chain=None, family='ipv4'):
    '''
    .. versionadded:: 2014.1.0

    Delete custom chain to the specified table.

    CLI Example:

    .. code-block:: bash

        salt '*' iptables.delete_chain filter CUSTOM_CHAIN

        IPv6:
        salt '*' iptables.delete_chain filter CUSTOM_CHAIN family=ipv6
    '''

    if not chain:
        return 'Error: Chain needs to be specified'

    wait = '--wait' if _has_option('--wait', family) else ''
    cmd = '{0} {1} -t {2} -X {3}'.format(
            _iptables_cmd(family), wait, table, chain)
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

    wait = '--wait' if _has_option('--wait', family) else ''
    returnCheck = check(table, chain, rule, family)
    if isinstance(returnCheck, bool) and returnCheck:
        return False
    cmd = '{0} {1} -t {2} -A {3} {4}'.format(
            _iptables_cmd(family), wait, table, chain, rule)
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

    If the position specified is a negative number, then the insert will be
        performed counting from the end of the list. For instance, a position
        of -1 will insert the rule as the second to last rule. To insert a rule
        in the last position, use the append function instead.

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

    if position < 0:
        rules = get_rules(family=family)
        size = len(rules[table][chain]['rules'])
        position = (size + position) + 1
        if position is 0:
            position = 1

    wait = '--wait' if _has_option('--wait', family) else ''
    returnCheck = check(table, chain, rule, family)
    if isinstance(returnCheck, bool) and returnCheck:
        return False
    cmd = '{0} {1} -t {2} -I {3} {4} {5}'.format(
            _iptables_cmd(family), wait, table, chain, position, rule)
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

    wait = '--wait' if _has_option('--wait', family) else ''
    cmd = '{0} {1} -t {2} -D {3} {4}'.format(
            _iptables_cmd(family), wait, table, chain, rule)
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

    wait = '--wait' if _has_option('--wait', family) else ''
    cmd = '{0} {1} -t {2} -F {3}'.format(_iptables_cmd(family), wait, table, chain)
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
    parser = _parser()
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
            args = salt.utils.shlex_split(line)
            index = 0
            while index + 1 < len(args):
                swap = args[index] == '!' and args[index + 1].startswith('-')
                if swap:
                    args[index], args[index + 1] = args[index + 1], args[index]
                if args[index].startswith('-'):
                    index += 1
                    if args[index].startswith('-') or (args[index] == '!' and
                                                       not swap):
                        args.insert(index, '')
                    else:
                        while (index + 1 < len(args) and
                               args[index + 1] != '!' and
                               not args[index + 1].startswith('-')):
                            args[index] += ' {0}'.format(args.pop(index + 1))
                index += 1
            if args[-1].startswith('-'):
                args.append('')
            parsed_args = []
            if sys.version.startswith('2.6'):
                (opts, leftover_args) = parser.parse_args(args)
                parsed_args = vars(opts)
            else:
                parsed_args = vars(parser.parse_args(args))
            ret_args = {}
            chain = parsed_args['append']
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
        import argparse  # pylint: disable=minimum-python-version
        parser = argparse.ArgumentParser()
        add_arg = parser.add_argument

    # COMMANDS
    add_arg('-A', '--append', dest='append', action='append')
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
    add_arg('-s', '--source', dest='source', action='append')
    add_arg('-d', '--destination', dest='destination', action='append')
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
    add_arg('--ahlen', dest='ahlen', action='append')
    add_arg('--ahres', dest='ahres', action='append')
    ## bpf
    add_arg('--bytecode', dest='bytecode', action='append')
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
    ## connlabel
    add_arg('--label', dest='label', action='append')
    ## connlimit
    add_arg('--connlimit-upto', dest='connlimit-upto', action='append')
    add_arg('--connlimit-above', dest='connlimit-above', action='append')
    add_arg('--connlimit-mask', dest='connlimit-mask', action='append')
    add_arg('--connlimit-saddr', dest='connlimit-saddr', action='append')
    add_arg('--connlimit-daddr', dest='connlimit-daddr', action='append')
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
    add_arg('--ctdir', dest='ctdir', action='append')
    ## cpu
    add_arg('--cpu', dest='cpu', action='append')
    ## dccp
    add_arg('--sport', '--source-port', dest='source_port', action='append')
    add_arg('--dport',
            '--destination-port',
            dest='destination_port',
            action='append')
    add_arg('--dccp-types', dest='dccp-types', action='append')
    add_arg('--dccp-option', dest='dccp-option', action='append')
    ## devgroup
    add_arg('--src-group', dest='src-group', action='append')
    add_arg('--dst-group', dest='dst-group', action='append')
    ## dscp
    add_arg('--dscp', dest='dscp', action='append')
    add_arg('--dscp-class', dest='dscp-class', action='append')
    ## dst
    add_arg('--dst-len', dest='dst-len', action='append')
    add_arg('--dst-opts', dest='dst-opts', action='append')
    ## ecn
    add_arg('--ecn-tcp-cwr', dest='ecn-tcp-cwr', action='append')
    add_arg('--ecn-tcp-ece', dest='ecn-tcp-ece', action='append')
    add_arg('--ecn-ip-ect', dest='ecn-ip-ect', action='append')
    ## esp
    add_arg('--espspi', dest='espspi', action='append')
    ## frag
    add_arg('--fragid', dest='fragid', action='append')
    add_arg('--fraglen', dest='fraglen', action='append')
    add_arg('--fragres', dest='fragres', action='append')
    add_arg('--fragfirst', dest='fragfirst', action='append')
    add_arg('--fragmore', dest='fragmore', action='append')
    add_arg('--fraglast', dest='fraglast', action='append')
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
    ## hbh
    add_arg('--hbh-len', dest='hbh-len', action='append')
    add_arg('--hbh-opts', dest='hbh-opts', action='append')
    ## helper
    add_arg('--helper', dest='helper', action='append')
    ## hl
    add_arg('--hl-eq', dest='hl-eq', action='append')
    add_arg('--hl-lt', dest='hl-lt', action='append')
    add_arg('--hl-gt', dest='hl-gt', action='append')
    ## icmp
    add_arg('--icmp-type', dest='icmp-type', action='append')
    ## icmp6
    add_arg('--icmpv6-type', dest='icmpv6-type', action='append')
    ## iprange
    add_arg('--src-range', dest='src-range', action='append')
    add_arg('--dst-range', dest='dst-range', action='append')
    ## ipv6header
    add_arg('--soft', dest='soft', action='append')
    add_arg('--header', dest='header', action='append')
    ## ipvs
    add_arg('--ipvs', dest='ipvs', action='append')
    add_arg('--vproto', dest='vproto', action='append')
    add_arg('--vaddr', dest='vaddr', action='append')
    add_arg('--vport', dest='vport', action='append')
    add_arg('--vdir', dest='vdir', action='append')
    add_arg('--vmethod', dest='vmethod', action='append')
    add_arg('--vportctl', dest='vportctl', action='append')
    ## length
    add_arg('--length', dest='length', action='append')
    ## limit
    add_arg('--limit', dest='limit', action='append')
    add_arg('--limit-burst', dest='limit-burst', action='append')
    ## mac
    add_arg('--mac-source', dest='mac-source', action='append')
    ## mh
    add_arg('--mh-type', dest='mh-type', action='append')
    ## multiport
    add_arg('--sports', '--source-ports', dest='source-ports', action='append')
    add_arg('--dports',
            '--destination-ports',
            dest='destination-ports',
            action='append')
    add_arg('--ports', dest='ports', action='append')
    ## nfacct
    add_arg('--nfacct-name', dest='nfacct-name', action='append')
    ## osf
    add_arg('--genre', dest='genre', action='append')
    add_arg('--ttl', dest='ttl', action='append')
    add_arg('--log', dest='log', action='append')
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
    add_arg('--rateest', dest='rateest', action='append')
    add_arg('--rateest1', dest='rateest1', action='append')
    add_arg('--rateest2', dest='rateest2', action='append')
    add_arg('--rateest-delta', dest='rateest-delta', action='append')
    add_arg('--rateest-bps', dest='rateest-bps', action='append')
    add_arg('--rateest-bps1', dest='rateest-bps1', action='append')
    add_arg('--rateest-bps2', dest='rateest-bps2', action='append')
    add_arg('--rateest-pps', dest='rateest-pps', action='append')
    add_arg('--rateest-pps1', dest='rateest-pps1', action='append')
    add_arg('--rateest-pps2', dest='rateest-pps2', action='append')
    add_arg('--rateest-lt', dest='rateest-lt', action='append')
    add_arg('--rateest-gt', dest='rateest-gt', action='append')
    add_arg('--rateest-eq', dest='rateest-eq', action='append')
    add_arg('--rateest-name', dest='rateest-name', action='append')
    add_arg('--rateest-interval', dest='rateest-interval', action='append')
    add_arg('--rateest-ewma', dest='rateest-ewma', action='append')
    ## realm
    add_arg('--realm', dest='realm', action='append')
    ## recent
    add_arg('--name', dest='name', action='append')
    add_arg('--set', dest='set', action='append')
    add_arg('--rsource', dest='rsource', action='append')
    add_arg('--rdest', dest='rdest', action='append')
    add_arg('--mask', dest='mask', action='append')
    add_arg('--rcheck', dest='rcheck', action='append')
    add_arg('--update', dest='update', action='append')
    add_arg('--remove', dest='remove', action='append')
    add_arg('--seconds', dest='seconds', action='append')
    add_arg('--reap', dest='reap', action='append')
    add_arg('--hitcount', dest='hitcount', action='append')
    add_arg('--rttl', dest='rttl', action='append')
    ## rpfilter
    add_arg('--loose', dest='loose', action='append')
    add_arg('--validmark', dest='validmark', action='append')
    add_arg('--accept-local', dest='accept-local', action='append')
    add_arg('--invert', dest='invert', action='append')
    ## rt
    add_arg('--rt-type', dest='rt-type', action='append')
    add_arg('--rt-segsleft', dest='rt-segsleft', action='append')
    add_arg('--rt-len', dest='rt-len', action='append')
    add_arg('--rt-0-res', dest='rt-0-res', action='append')
    add_arg('--rt-0-addrs', dest='rt-0-addrs', action='append')
    add_arg('--rt-0-not-strict', dest='rt-0-not-strict', action='append')
    ## sctp
    add_arg('--chunk-types', dest='chunk-types', action='append')
    ## set
    add_arg('--match-set', dest='match-set', action='append')
    add_arg('--return-nomatch', dest='return-nomatch', action='append')
    add_arg('--update-counters', dest='update-counters', action='append')
    add_arg('--update-subcounters', dest='update-subcounters', action='append')
    add_arg('--packets-eq', dest='packets-eq', action='append')
    add_arg('--packets-lt', dest='packets-lt', action='append')
    add_arg('--packets-gt', dest='packets-gt', action='append')
    add_arg('--bytes-eq', dest='bytes-eq', action='append')
    add_arg('--bytes-lt', dest='bytes-lt', action='append')
    add_arg('--bytes-gt', dest='bytes-gt', action='append')
    ## socket
    add_arg('--transparent', dest='transparent', action='append')
    add_arg('--nowildcard', dest='nowildcard', action='append')
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
    add_arg('--timestart', dest='timestart', action='append')
    add_arg('--timestop', dest='timestop', action='append')
    add_arg('--monthdays', dest='monthdays', action='append')
    add_arg('--weekdays', dest='weekdays', action='append')
    add_arg('--contiguous', dest='contiguous', action='append')
    add_arg('--kerneltz', dest='kerneltz', action='append')
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

    # Xtables-addons matches
    ## condition
    add_arg('--condition', dest='condition', action='append')
    ## dhcpmac
    add_arg('--mac', dest='mac', action='append')
    ## fuzzy
    add_arg('--lower-limit', dest='lower-limit', action='append')
    add_arg('--upper-limit', dest='upper-limit', action='append')
    ## geoip
    add_arg('--src-cc',
            '--source-country',
            dest='source-country',
            action='append')
    add_arg('--dst-cc',
            '--destination-country',
            dest='destination-country',
            action='append')
    ## gradm
    add_arg('--enabled', dest='enabled', action='append')
    add_arg('--disabled', dest='disabled', action='append')
    ## iface
    add_arg('--iface', dest='iface', action='append')
    add_arg('--dev-in', dest='dev-in', action='append')
    add_arg('--dev-out', dest='dev-out', action='append')
    add_arg('--up', dest='up', action='append')
    add_arg('--down', dest='down', action='append')
    add_arg('--broadcast', dest='broadcast', action='append')
    add_arg('--loopback', dest='loopback', action='append')
    add_arg('--pointtopoint', dest='pointtopoint', action='append')
    add_arg('--running', dest='running', action='append')
    add_arg('--noarp', dest='noarp', action='append')
    add_arg('--arp', dest='arp', action='append')
    add_arg('--promisc', dest='promisc', action='append')
    add_arg('--multicast', dest='multicast', action='append')
    add_arg('--dynamic', dest='dynamic', action='append')
    add_arg('--lower-up', dest='lower-up', action='append')
    add_arg('--dormant', dest='dormant', action='append')
    ## ipp2p
    add_arg('--edk', dest='edk', action='append')
    add_arg('--kazaa', dest='kazaa', action='append')
    add_arg('--gnu', dest='gnu', action='append')
    add_arg('--dc', dest='dc', action='append')
    add_arg('--bit', dest='bit', action='append')
    add_arg('--apple', dest='apple', action='append')
    add_arg('--soul', dest='soul', action='append')
    add_arg('--winmx', dest='winmx', action='append')
    add_arg('--ares', dest='ares', action='append')
    add_arg('--debug', dest='debug', action='append')
    ## ipv4options
    add_arg('--flags', dest='flags', action='append')
    add_arg('--any', dest='any', action='append')
    ## length2
    add_arg('--layer3', dest='layer3', action='append')
    add_arg('--layer4', dest='layer4', action='append')
    add_arg('--layer5', dest='layer5', action='append')
    ## lscan
    add_arg('--stealth', dest='stealth', action='append')
    add_arg('--synscan', dest='synscan', action='append')
    add_arg('--cnscan', dest='cnscan', action='append')
    add_arg('--grscan', dest='grscan', action='append')
    ## psd
    add_arg('--psd-weight-threshold',
            dest='psd-weight-threshold',
            action='append')
    add_arg('--psd-delay-threshold',
            dest='psd-delay-threshold',
            action='append')
    add_arg('--psd-lo-ports-weight',
            dest='psd-lo-ports-weight',
            action='append')
    add_arg('--psd-hi-ports-weight',
            dest='psd-hi-ports-weight',
            action='append')
    ## quota2
    add_arg('--grow', dest='grow', action='append')
    add_arg('--no-change', dest='no-change', action='append')
    add_arg('--packets', dest='packets', action='append')
    ## pknock
    add_arg('--knockports', dest='knockports', action='append')
    add_arg('--time', dest='time', action='append')
    add_arg('--autoclose', dest='autoclose', action='append')
    add_arg('--checkip', dest='checkip', action='append')

    # TARGET EXTENSIONS
    ## AUDIT
    add_arg('--type', dest='type', action='append')
    ## CHECKSUM
    add_arg('--checksum-fill', dest='checksum-fill', action='append')
    ## CLASSIFY
    add_arg('--set-class', dest='set-class', action='append')
    ## CLUSTERIP
    add_arg('--new', dest='new', action='append')
    add_arg('--hashmode', dest='hashmode', action='append')
    add_arg('--clustermac', dest='clustermac', action='append')
    add_arg('--total-nodes', dest='total-nodes', action='append')
    add_arg('--local-node', dest='local-node', action='append')
    add_arg('--hash-init', dest='hash-init', action='append')
    ## CONNMARK
    add_arg('--set-xmark', dest='set-xmark', action='append')
    add_arg('--save-mark', dest='save-mark', action='append')
    add_arg('--restore-mark', dest='restore-mark', action='append')
    add_arg('--and-mark', dest='and-mark', action='append')
    add_arg('--or-mark', dest='or-mark', action='append')
    add_arg('--xor-mark', dest='xor-mark', action='append')
    add_arg('--set-mark', dest='set-mark', action='append')
    ## CONNSECMARK
    add_arg('--save', dest='save', action='append')
    add_arg('--restore', dest='restore', action='append')
    ## CT
    add_arg('--notrack', dest='notrack', action='append')
    add_arg('--ctevents', dest='ctevents', action='append')
    add_arg('--expevents', dest='expevents', action='append')
    add_arg('--zone', dest='zone', action='append')
    add_arg('--timeout', dest='timeout', action='append')
    ## DNAT
    add_arg('--to-destination', dest='to-destination', action='append')
    add_arg('--random', dest='random', action='append')
    add_arg('--persistent', dest='persistent', action='append')
    ## DNPT
    add_arg('--src-pfx', dest='src-pfx', action='append')
    add_arg('--dst-pfx', dest='dst-pfx', action='append')
    ## DSCP
    add_arg('--set-dscp', dest='set-dscp', action='append')
    add_arg('--set-dscp-class', dest='set-dscp-class', action='append')
    ## ECN
    add_arg('--ecn-tcp-remove', dest='ecn-tcp-remove', action='append')
    ## HL
    add_arg('--hl-set', dest='hl-set', action='append')
    add_arg('--hl-dec', dest='hl-dec', action='append')
    add_arg('--hl-inc', dest='hl-inc', action='append')
    ## HMARK
    add_arg('--hmark-tuple', dest='hmark-tuple', action='append')
    add_arg('--hmark-mod', dest='hmark-mod', action='append')
    add_arg('--hmark-offset', dest='hmark-offset', action='append')
    add_arg('--hmark-src-prefix', dest='hmark-src-prefix', action='append')
    add_arg('--hmark-dst-prefix', dest='hmark-dst-prefix', action='append')
    add_arg('--hmark-sport-mask', dest='hmark-sport-mask', action='append')
    add_arg('--hmark-dport-mask', dest='hmark-dport-mask', action='append')
    add_arg('--hmark-spi-mask', dest='hmark-spi-mask', action='append')
    add_arg('--hmark-proto-mask', dest='hmark-proto-mask', action='append')
    add_arg('--hmark-rnd', dest='hmark-rnd', action='append')
    ## LED
    add_arg('--led-trigger-id', dest='led-trigger-id', action='append')
    add_arg('--led-delay', dest='led-delay', action='append')
    add_arg('--led-always-blink', dest='led-always-blink', action='append')
    ## LOG
    add_arg('--log-level', dest='log-level', action='append')
    add_arg('--log-prefix', dest='log-prefix', action='append')
    add_arg('--log-tcp-sequence', dest='log-tcp-sequence', action='append')
    add_arg('--log-tcp-options', dest='log-tcp-options', action='append')
    add_arg('--log-ip-options', dest='log-ip-options', action='append')
    add_arg('--log-uid', dest='log-uid', action='append')
    ## MASQUERADE
    add_arg('--to-ports', dest='to-ports', action='append')
    ## NFLOG
    add_arg('--nflog-group', dest='nflog-group', action='append')
    add_arg('--nflog-prefix', dest='nflog-prefix', action='append')
    add_arg('--nflog-range', dest='nflog-range', action='append')
    add_arg('--nflog-threshold', dest='nflog-threshold', action='append')
    ## NFQUEUE
    add_arg('--queue-num', dest='queue-num', action='append')
    add_arg('--queue-balance', dest='queue-balance', action='append')
    add_arg('--queue-bypass', dest='queue-bypass', action='append')
    add_arg('--queue-cpu-fanout', dest='queue-cpu-fanout', action='append')
    ## RATEEST
    add_arg('--rateest-ewmalog', dest='rateest-ewmalog', action='append')
    ## REJECT
    add_arg('--reject-with', dest='reject-with', action='append')
    ## SAME
    add_arg('--nodst', dest='nodst', action='append')
    ## SECMARK
    add_arg('--selctx', dest='selctx', action='append')
    ## SET
    add_arg('--add-set', dest='add-set', action='append')
    add_arg('--del-set', dest='del-set', action='append')
    add_arg('--exist', dest='exist', action='append')
    ## SNAT
    add_arg('--to-source', dest='to-source', action='append')
    ## TCPMSS
    add_arg('--set-mss', dest='set-mss', action='append')
    add_arg('--clamp-mss-to-pmtu', dest='clamp-mss-to-pmtu', action='append')
    ## TCPOPTSTRIP
    add_arg('--strip-options', dest='strip-options', action='append')
    ## TEE
    add_arg('--gateway', dest='gateway', action='append')
    ## TOS
    add_arg('--set-tos', dest='set-tos', action='append')
    add_arg('--and-tos', dest='and-tos', action='append')
    add_arg('--or-tos', dest='or-tos', action='append')
    add_arg('--xor-tos', dest='xor-tos', action='append')
    ## TPROXY
    add_arg('--on-port', dest='on-port', action='append')
    add_arg('--on-ip', dest='on-ip', action='append')
    add_arg('--tproxy-mark', dest='tproxy-mark', action='append')
    ## TTL
    add_arg('--ttl-set', dest='ttl-set', action='append')
    add_arg('--ttl-dec', dest='ttl-dec', action='append')
    add_arg('--ttl-inc', dest='ttl-inc', action='append')
    ## ULOG
    add_arg('--ulog-nlgroup', dest='ulog-nlgroup', action='append')
    add_arg('--ulog-prefix', dest='ulog-prefix', action='append')
    add_arg('--ulog-cprange', dest='ulog-cprange', action='append')
    add_arg('--ulog-qthreshold', dest='ulog-qthreshold', action='append')

    # Xtables-addons targets
    ## ACCOUNT
    add_arg('--addr', dest='addr', action='append')
    add_arg('--tname', dest='tname', action='append')
    ## CHAOS
    add_arg('--delude', dest='delude', action='append')
    add_arg('--tarpit', dest='tarpit', action='append')
    ## DHCPMAC
    add_arg('--set-mac', dest='set-mac', action='append')
    ## DNETMAP
    add_arg('--prefix', dest='prefix', action='append')
    add_arg('--reuse', dest='reuse', action='append')
    add_arg('--static', dest='static', action='append')
    ## IPMARK
    add_arg('--and-mask', dest='and-mask', action='append')
    add_arg('--or-mask', dest='or-mask', action='append')
    add_arg('--shift', dest='shift', action='append')
    ## TARPIT
    add_arg('--honeypot', dest='honeypot', action='append')
    add_arg('--reset', dest='reset', action='append')

    return parser
