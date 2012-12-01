'''
Support for iptables
'''

# Import Python libs
import os
import argparse

# Import Salt libs
import salt.utils
from salt.exceptions import SaltException


def __virtual__():
    '''
    Only load the module if iptables is installed
    '''
    if salt.utils.which('iptables'):
        return 'iptables'
    return False


def _conf():
    '''
    Some distros have a specific location for config files
    '''
    if __grains__['os_family'] == 'RedHat':
        return '/etc/sysconfig/iptables'
    elif __grains__['os_family'] == 'Arch':
        return '/etc/iptables/iptables.rules'
    else:
        return False


def version():
    '''
    Return version from iptables --version

    CLI Example::

        salt '*' iptables.version
    '''
    cmd = 'iptables --version'
    out = __salt__['cmd.run'](cmd).split()
    return out[1]


def get_saved_rules(conf_file=None):
    '''
    Return a data structure of the rules in the conf file

    CLI Example::

        salt '*' iptables.get_saved_rules
    '''
    return _parse_conf(conf_file)


def get_rules():
    '''
    Return a data structure of the current, in-memory rules

    CLI Example::

        salt '*' iptables.get_rules
    '''
    return _parse_conf(in_mem=True)


def get_saved_policy(table='filter', chain=None, conf_file=None):
    '''
    Return the current policy for the specified table/chain

    CLI Examples::

        salt '*' iptables.get_saved_policy filter INPUT
        salt '*' iptables.get_saved_policy filter INPUT conf_file=/etc/iptables.saved
    '''
    if not chain:
        return 'Error: Chain needs to be specified'

    rules = _parse_conf(conf_file)
    return rules[table][chain]['policy']


def get_policy(table='filter', chain=None):
    '''
    Return the current policy for the specified table/chain

    CLI Example::

        salt '*' iptables.get_policy filter INPUT
    '''
    if not chain:
        return 'Error: Chain needs to be specified'

    rules = _parse_conf(in_mem=True)
    return rules[table][chain]['policy']


def set_policy(table='filter', chain=None, policy=None):
    '''
    Set the current policy for the specified table/chain

    CLI Example::

        salt '*' iptables.set_policy filter INPUT ACCEPT
    '''
    if not chain:
        return 'Error: Chain needs to be specified'
    if not policy:
        return 'Error: Policy needs to be specified'

    cmd = 'iptables -t {0} -P {1} {2}'.format(table, chain, policy)
    out = __salt__['cmd.run'](cmd)
    return out


def _parse_conf(conf_file=None, in_mem=False):
    '''
    If a file is not passed in, and the correct one for this OS is not
    detected, return False
    '''
    if _conf() and not conf_file and not in_mem:
        conf_file = _conf()

    rules = ''
    if conf_file:
        f = open(conf_file, 'r')
        rules = f.read()
        f.close()
    elif in_mem:
        cmd = 'iptables-save'
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
        elif line.startswith('-A'):
            parser = _parser()
            parsed_args = vars(parser.parse_args(line.split()))
            ret_args = {}
            chain = parsed_args['append']
            for arg in parsed_args:
                if parsed_args[arg] and arg is not 'append':
                    ret_args[arg] = parsed_args[arg]
            ret[table][chain[0]]['rules'].append(ret_args)
    return ret


def _parser():
    '''
    This function contains _all_ the options I could find in man 8 iptables,
    listed in the first section that I found them in. They will not all be used
    by all parts of the module; use them intelligently and appropriately.
    '''
    parser = argparse.ArgumentParser()
    # COMMANDS
    parser.add_argument('-A', '--append', dest='append', action='append')
    parser.add_argument('-D', '--delete', dest='delete', action='append')
    parser.add_argument('-I', '--insert', dest='insert', action='append')
    parser.add_argument('-R', '--replace', dest='replace', action='append')
    parser.add_argument('-L', '--list', dest='list', action='append')
    parser.add_argument('-F', '--flush', dest='flush', action='append')
    parser.add_argument('-Z', '--zero', dest='zero', action='append')
    parser.add_argument('-N', '--new-chain', dest='new-chain', action='append')
    parser.add_argument('-X', '--delete-chain', dest='delete-chain', action='append')
    parser.add_argument('-P', '--policy', dest='policy', action='append')
    parser.add_argument('-E', '--rename-chain', dest='rename-chain', action='append')

    # PARAMETERS
    parser.add_argument('-p', '--protocol', dest='protocol', action='append')
    parser.add_argument('-s', '--source', dest='source', action='append')
    parser.add_argument('-d', '--destination', dest='destination', action='append')
    parser.add_argument('-j', '--jump', dest='jump', action='append')
    parser.add_argument('-g', '--goto', dest='goto', action='append')
    parser.add_argument('-i', '--in-interface', dest='in-interface', action='append')
    parser.add_argument('-o', '--out-interface', dest='out-interface', action='append')
    parser.add_argument('-f', '--fragment', dest='fragment', action='append')
    parser.add_argument('-c', '--set-counters', dest='set-counters', action='append')

    # MATCH EXTENSIONS
    parser.add_argument('-m', '--match', dest='match', action='append')
    ## addrtype
    parser.add_argument('--src-type', dest='src-type', action='append')
    parser.add_argument('--dst-type', dest='dst-type', action='append')
    parser.add_argument('--limit-iface-in', dest='limit-iface-in', action='append')
    parser.add_argument('--limit-iface-out', dest='limit-iface-out', action='append')
    ## ah
    parser.add_argument('--ahspi', dest='ahspi', action='append')
    ## cluster
    parser.add_argument('--cluster-total-nodes', dest='cluster-total-nodes', action='append')
    parser.add_argument('--cluster-local-node', dest='cluster-local-node', action='append')
    parser.add_argument('--cluster-local-nodemask', dest='cluster-local-nodemask', action='append')
    parser.add_argument('--cluster-hash-seed', dest='cluster-hash-seed', action='append')
    parser.add_argument('--h-length', dest='h-length', action='append')
    parser.add_argument('--mangle-mac-s', dest='mangle-mac-s', action='append')
    parser.add_argument('--mangle-mac-d', dest='mangle-mac-d', action='append')
    ## comment
    parser.add_argument('--comment', dest='comment', action='append')
    ## connbytes
    parser.add_argument('--connbytes', dest='connbytes', action='append')
    parser.add_argument('--connbytes-dir', dest='connbytes-dir', action='append')
    parser.add_argument('--connbytes-mode', dest='connbytes-mode', action='append')
    ## connlimit
    parser.add_argument('--connlimit-above', dest='connlimit-above', action='append')
    parser.add_argument('--connlimit-mask', dest='connlimit-mask', action='append')
    ## connmark
    parser.add_argument('--mark', dest='mark', action='append')
    ## conntrack
    parser.add_argument('--ctstate', dest='ctstate', action='append')
    parser.add_argument('--ctproto', dest='ctproto', action='append')
    parser.add_argument('--ctorigsrc', dest='ctorigsrc', action='append')
    parser.add_argument('--ctorigdst', dest='ctorigdst', action='append')
    parser.add_argument('--ctreplsrc', dest='ctreplsrc', action='append')
    parser.add_argument('--ctrepldst', dest='ctrepldst', action='append')
    parser.add_argument('--ctorigsrcport', dest='ctorigsrcport', action='append')
    parser.add_argument('--ctorigdstport', dest='ctorigdstport', action='append')
    parser.add_argument('--ctreplsrcport', dest='ctreplsrcport', action='append')
    parser.add_argument('--ctrepldstport', dest='ctrepldstport', action='append')
    parser.add_argument('--ctstatus', dest='ctstatus', action='append')
    parser.add_argument('--ctexpire', dest='ctexpire', action='append')
    ## dccp
    parser.add_argument('--sport', '--source-port', dest='source_port', action='append')
    parser.add_argument('--dport', '--destination-port', dest='destination_port', action='append')
    parser.add_argument('--dccp-types', dest='dccp-types', action='append')
    parser.add_argument('--dccp-option', dest='dccp-option', action='append')
    ## dscp
    parser.add_argument('--dscp', dest='dscp', action='append')
    parser.add_argument('--dscp-class', dest='dscp-class', action='append')
    ## ecn
    parser.add_argument('--ecn-tcp-cwr', dest='ecn-tcp-cwr', action='append')
    parser.add_argument('--ecn-tcp-ece', dest='ecn-tcp-ece', action='append')
    parser.add_argument('--ecn-ip-ect', dest='ecn-ip-ect', action='append')
    ## esp
    parser.add_argument('--espspi', dest='espspi', action='append')
    ## hashlimit
    parser.add_argument('--hashlimit-upto', dest='hashlimit-upto', action='append')
    parser.add_argument('--hashlimit-above', dest='hashlimit-above', action='append')
    parser.add_argument('--hashlimit-burst', dest='hashlimit-burst', action='append')
    parser.add_argument('--hashlimit-mode', dest='hashlimit-mode', action='append')
    parser.add_argument('--hashlimit-srcmask', dest='hashlimit-srcmask', action='append')
    parser.add_argument('--hashlimit-dstmask', dest='hashlimit-dstmask', action='append')
    parser.add_argument('--hashlimit-name', dest='hashlimit-name', action='append')
    parser.add_argument('--hashlimit-htable-size', dest='hashlimit-htable-size', action='append')
    parser.add_argument('--hashlimit-htable-max', dest='hashlimit-htable-max', action='append')
    parser.add_argument('--hashlimit-htable-expire', dest='hashlimit-htable-expire', action='append')
    parser.add_argument('--hashlimit-htable-gcinterval', dest='hashlimit-htable-gcinterval', action='append')
    ## helper
    parser.add_argument('--helper', dest='helper', action='append')
    ## icmp
    parser.add_argument('--icmp-type', dest='icmp-type', action='append')
    ## iprange
    parser.add_argument('--src-range', dest='src-range', action='append')
    parser.add_argument('--dst-range', dest='dst-range', action='append')
    ## length
    parser.add_argument('--length', dest='length', action='append')
    ## limit
    parser.add_argument('--limit', dest='limit', action='append')
    parser.add_argument('--limit-burst', dest='limit-burst', action='append')
    ## mac
    parser.add_argument('--mac-source', dest='mac-source', action='append')
    ## multiport
    parser.add_argument('--source-ports', dest='source-ports', action='append')
    parser.add_argument('--destination-ports', dest='destination-ports', action='append')
    parser.add_argument('--ports', dest='ports', action='append')
    ## owner
    parser.add_argument('--uid-owner', dest='uid-owner', action='append')
    parser.add_argument('--gid-owner', dest='gid-owner', action='append')
    parser.add_argument('--socket-exists', dest='socket-exists', action='append')
    ## physdev
    parser.add_argument('--physdev-in', dest='physdev-in', action='append')
    parser.add_argument('--physdev-out', dest='physdev-out', action='append')
    parser.add_argument('--physdev-is-in', dest='physdev-is-in', action='append')
    parser.add_argument('--physdev-is-out', dest='physdev-is-out', action='append')
    parser.add_argument('--physdev-is-bridged', dest='physdev-is-bridged', action='append')
    ## pkttype
    parser.add_argument('--pkt-type', dest='pkt-type', action='append')
    ## policy
    parser.add_argument('--dir', dest='dir', action='append')
    parser.add_argument('--pol', dest='pol', action='append')
    parser.add_argument('--strict', dest='strict', action='append')
    parser.add_argument('--reqid', dest='reqid', action='append')
    parser.add_argument('--spi', dest='spi', action='append')
    parser.add_argument('--proto', dest='proto', action='append')
    parser.add_argument('--mode', dest='mode', action='append')
    parser.add_argument('--tunnel-src', dest='tunnel-src', action='append')
    parser.add_argument('--tunnel-dst', dest='tunnel-dst', action='append')
    parser.add_argument('--next', dest='next', action='append')
    ## quota
    parser.add_argument('--quota', dest='quota', action='append')
    ## rateest
    parser.add_argument('--rateest1', dest='rateest1', action='append')
    parser.add_argument('--rateest2', dest='rateest2', action='append')
    parser.add_argument('--rateest-delta', dest='rateest-delta', action='append')
    parser.add_argument('--rateest1-bps', dest='rateest1-bps', action='append')
    parser.add_argument('--rateest2-bps', dest='rateest2-bps', action='append')
    parser.add_argument('--rateest1-pps', dest='rateest1-pps', action='append')
    parser.add_argument('--rateest2-pps', dest='rateest2-pps', action='append')
    parser.add_argument('--rateest1-lt', dest='rateest1-lt', action='append')
    parser.add_argument('--rateest1-gt', dest='rateest1-gt', action='append')
    parser.add_argument('--rateest1-eq', dest='rateest1-eq', action='append')
    parser.add_argument('--rateest-name', dest='rateest-name', action='append')
    parser.add_argument('--rateest-interval', dest='rateest-interval', action='append')
    parser.add_argument('--rateest-ewma', dest='rateest-ewma', action='append')
    ## realm
    parser.add_argument('--realm', dest='realm', action='append')
    ## recent
    parser.add_argument('--set', dest='set', action='append')
    parser.add_argument('--name', dest='name', action='append')
    parser.add_argument('--rsource', dest='rsource', action='append')
    parser.add_argument('--rdest', dest='rdest', action='append')
    parser.add_argument('--rcheck', dest='rcheck', action='append')
    parser.add_argument('--update', dest='update', action='append')
    parser.add_argument('--remove', dest='remove', action='append')
    parser.add_argument('--seconds', dest='seconds', action='append')
    parser.add_argument('--hitcount', dest='hitcount', action='append')
    parser.add_argument('--rttl', dest='rttl', action='append')
    ## sctp
    parser.add_argument('--chunk-types', dest='chunk-types', action='append')
    ## set
    parser.add_argument('--match-set', dest='match-set', action='append')
    ## socket
    parser.add_argument('--transparent', dest='transparent', action='append')
    ## state
    parser.add_argument('--state', dest='state', action='append')
    ## statistic
    parser.add_argument('--probability', dest='probability', action='append')
    parser.add_argument('--every', dest='every', action='append')
    parser.add_argument('--packet', dest='packet', action='append')
    ## string
    parser.add_argument('--algo', dest='algo', action='append')
    parser.add_argument('--from', dest='from', action='append')
    parser.add_argument('--to', dest='to', action='append')
    parser.add_argument('--string', dest='string', action='append')
    parser.add_argument('--hex-string', dest='hex-string', action='append')
    ## tcp
    parser.add_argument('--tcp-flags', dest='tcp-flags', action='append')
    parser.add_argument('--syn', dest='syn', action='append')
    parser.add_argument('--tcp-option', dest='tcp-option', action='append')
    ## tcpmss
    parser.add_argument('--mss', dest='mss', action='append')
    ## time
    parser.add_argument('--datestart', dest='datestart', action='append')
    parser.add_argument('--datestop', dest='datestop', action='append')
    parser.add_argument('--monthdays', dest='monthdays', action='append')
    parser.add_argument('--weekdays', dest='weekdays', action='append')
    parser.add_argument('--utc', dest='utc', action='append')
    parser.add_argument('--localtz', dest='localtz', action='append')
    ## tos
    parser.add_argument('--tos', dest='tos', action='append')
    ## ttl
    parser.add_argument('--ttl-eq', dest='ttl-eq', action='append')
    parser.add_argument('--ttl-gt', dest='ttl-gt', action='append')
    parser.add_argument('--ttl-lt', dest='ttl-lt', action='append')
    ## u32
    parser.add_argument('--u32', dest='u32', action='append')

    # CHECKSUM
    parser.add_argument('--checksum-fill', dest='checksum-fill', action='append')

    # CLASSIFY
    parser.add_argument('--set-class', dest='set-class', action='append')

    # CLUSTERIP
    parser.add_argument('--new', dest='new', action='append')
    parser.add_argument('--hashmode', dest='hashmode', action='append')
    parser.add_argument('--clustermac', dest='clustermac', action='append')
    parser.add_argument('--total-nodes', dest='total-nodes', action='append')
    parser.add_argument('--local-node', dest='local-node', action='append')
    parser.add_argument('--hash-init', dest='hash-init', action='append')

    # CONNMARK
    parser.add_argument('--set-xmark', dest='set-xmark', action='append')
    parser.add_argument('--save-mark', dest='save-mark', action='append')
    parser.add_argument('--restore-mark', dest='restore-mark', action='append')
    parser.add_argument('--and-mark', dest='and-mark', action='append')
    parser.add_argument('--or-mark', dest='or-mark', action='append')
    parser.add_argument('--xor-mark', dest='xor-mark', action='append')
    parser.add_argument('--set-mark', dest='set-mark', action='append')

    # DNAT
    parser.add_argument('--to-destination', dest='to-destination', action='append')
    parser.add_argument('--random', dest='random', action='append')
    parser.add_argument('--persistent', dest='persistent', action='append')

    # DSCP
    parser.add_argument('--set-dscp', dest='set-dscp', action='append')
    parser.add_argument('--set-dscp-class', dest='set-dscp-class', action='append')

    # ECN
    parser.add_argument('--ecn-tcp-remove', dest='ecn-tcp-remove', action='append')

    # LOG
    parser.add_argument('--log-level', dest='log-level', action='append')
    parser.add_argument('--log-prefix', dest='log-prefix', action='append')
    parser.add_argument('--log-tcp-sequence', dest='log-tcp-sequence', action='append')
    parser.add_argument('--log-tcp-options', dest='log-tcp-options', action='append')
    parser.add_argument('--log-ip-options', dest='log-ip-options', action='append')
    parser.add_argument('--log-uid', dest='log-uid', action='append')

    # NFLOG
    parser.add_argument('--nflog-group', dest='nflog-group', action='append')
    parser.add_argument('--nflog-prefix', dest='nflog-prefix', action='append')
    parser.add_argument('--nflog-range', dest='nflog-range', action='append')
    parser.add_argument('--nflog-threshold', dest='nflog-threshold', action='append')

    # NFQUEUE
    parser.add_argument('--queue-num', dest='queue-num', action='append')
    parser.add_argument('--queue-balance', dest='queue-balance', action='append')

    # RATEEST
    parser.add_argument('--rateest-ewmalog', dest='rateest-ewmalog', action='append')

    # REDIRECT
    parser.add_argument('--to-ports', dest='to-ports', action='append')

    # REJECT
    parser.add_argument('--reject-with', dest='reject-with', action='append')

    # SAME
    parser.add_argument('--nodst', dest='nodst', action='append')

    # SECMARK
    parser.add_argument('--selctx', dest='selctx', action='append')

    # SET
    parser.add_argument('--add-set', dest='add-set', action='append')
    parser.add_argument('--del-set', dest='del-set', action='append')

    # SNAT
    parser.add_argument('--to-source', dest='to-source', action='append')

    # TCPMSS
    parser.add_argument('--set-mss', dest='set-mss', action='append')
    parser.add_argument('--clamp-mss-to-pmtu', dest='clamp-mss-to-pmtu', action='append')

    # TCPOPTSTRIP
    parser.add_argument('--strip-options', dest='strip-options', action='append')

    # TOS
    parser.add_argument('--set-tos', dest='set-tos', action='append')
    parser.add_argument('--and-tos', dest='and-tos', action='append')
    parser.add_argument('--or-tos', dest='or-tos', action='append')
    parser.add_argument('--xor-tos', dest='xor-tos', action='append')

    # TPROXY
    parser.add_argument('--on-port', dest='on-port', action='append')
    parser.add_argument('--on-ip', dest='on-ip', action='append')
    parser.add_argument('--tproxy-mark', dest='tproxy-mark', action='append')

    # TTL
    parser.add_argument('--ttl-set', dest='ttl-set', action='append')
    parser.add_argument('--ttl-dec', dest='ttl-dec', action='append')
    parser.add_argument('--ttl-inc', dest='ttl-inc', action='append')

    # ULOG
    parser.add_argument('--ulog-nlgroup', dest='ulog-nlgroup', action='append')
    parser.add_argument('--ulog-prefix', dest='ulog-prefix', action='append')
    parser.add_argument('--ulog-cprange', dest='ulog-cprange', action='append')
    parser.add_argument('--ulog-qthreshold', dest='ulog-qthreshold', action='append')

    return parser

