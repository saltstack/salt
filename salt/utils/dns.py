# -*- coding: utf-8 -*-
'''
Compendium of generic DNS utilities

# Examples:
dns.lookup(name, rdtype, ...)
dns.records(name, rdtype, ...)

dns.srv_rec(data)
dns.srv_data('my1.example.com', 389, prio=10, weight=100)
dns.srv_name('ldap/tcp', 'example.com')

# can replace
- my stuff
    - gai
    - tmpltools.dns_secure


# should replace/augment
https://github.com/saltstack/salt/pull/39615/files
https://blog.widodh.nl/2016/07/calculating-ds-record-from-dnskey-with-python-3/
https://github.com/saltstack/salt/pull/36180
- modules:
    - ddns
    - dnsutil
    - dig
    - libcloud dns
- states
    - libcoud dns
- utils
    - network

# should fix
https://github.com/saltstack/salt/issues/25953
https://github.com/saltstack/salt/issues/20275
'''
from __future__ import print_function, absolute_import
# Python
import base64
import hashlib
import itertools
import socket
import string
from salt.ext.six.moves import zip
from salt._compat import ipaddress
from salt.utils.odict import OrderedDict

# Salt
import salt.modules.cmdmod
import salt.utils

# Debug & Logging
import logging
import pprint

# Integrations
try:
    import dns.resolver
    HAS_PYDNS = True
except ImportError as e:
    HAS_PYDNS = False
HAS_DIG = salt.utils.which('dig') is not None
HAS_DRILL = salt.utils.which('drill') is not None
HAS_HOST = salt.utils.which('host') is not None
HAS_NSLOOKUP = salt.utils.which('nslookup') is not None

__salt__ = {
    'cmd.run_all': salt.modules.cmdmod.run_all
}
log = logging.getLogger(__name__)
ppr = pprint.PrettyPrinter(indent=2).pprint


class RFC(object):
    # http://www.iana.org/assignments/dns-sshfp-rr-parameters/dns-sshfp-rr-parameters.xhtml
    SSHFP_ALGO = OrderedDict((
        (1, 'rsa'),
        (2, 'dsa'),
        (3, 'ecdsa'),
        (4, 'ed25519'),
    ))

    SSHFP_HASH = OrderedDict((
        (1, 'sha1'),
        (2, 'sha256'),
    ))

    # http://www.iana.org/assignments/dane-parameters/dane-parameters.xhtml
    TLSA_USAGE = OrderedDict((
        (0, 'pkixta'),
        (1, 'pkixee'),
        (2, 'daneta'),
        (3, 'daneee'),
    ))

    TLSA_SELECT = OrderedDict((
        (0, 'pkixta'),
        (1, 'pkixee'),
        (2, 'daneta'),
        (3, 'daneee'),
    ))

    TLSA_MATCHING = OrderedDict((
        (0, 'full'),
        (1, 'sha256'),
        (2, 'sha512'),
    ))

    SRV_PROTO = (
        'tcp',
        'udp',
        'sctp'
    )

    @staticmethod
    def validate(lookup, ref, match=None):
        if lookup in ref:
            return lookup
        elif match == 'in':
            return [code for code, name in ref.items() if lookup in name][-1]
        else:
            # OrderedDicts only!(?)
            return ref.keys()[ref.values().index(lookup)]


def _data2rec(rschema, rdata):
    '''
    OrderedDict({
        'prio': int,
        'weight': int,
        'port': to_port,
        'name': str,
    })
    '10 20 25 myawesome.nl'

    '''
    try:
        rdata = rdata.split(' ', len(rschema))
        rschema = rschema.items()
        return dict((
            (fname, rcb(rdata)) for (fname, rcb), rdata in zip(rschema, rdata)
        ))
    except:  # pylint: disable=bare-except
        log.error('Cant parse DNS record data: {}'.format(rdata))
        return False


def _rec2data(*rdata):
    return ' '.join(rdata)


def _to_port(port):
    try:
        port = int(port)
        assert 1 <= port <= 65535
        return port
    except (ValueError, AssertionError):
        raise ValueError('Invalid port {0}'.format(port))


def _query_simple(name, rdtype, timeout=None):
    '''
    Use Python's socket interface to lookup addresses
    :param name: Name of record to search
    :param rdtype: A or AAAA
    :param timeout: ignored
    :return: [] of addresses or False if error
    '''
    sock_t = {
        'A': socket.AF_INET,
        'AAAA': socket.AF_INET6
    }[rdtype]

    if timeout:
        log.warn('Ignoring timeout on simple resolver; fix resolv.conf to do that')

    try:
        addresses = [sock[4][0] for sock in socket.getaddrinfo(name, None, sock_t, 0, socket.SOCK_RAW)]
        return addresses
    except socket.gaierror:
        return False


def _query_dig(name, rdtype, timeout=None, servers=[], secure=None):
    '''
    Use dig to lookup addresses
    :param name: Name of record to search
    :param rdtype: DNS record type
    :param timeout: server response timeout
    :return: [] of records or False if error
    '''
    cmd = 'dig +search +fail +noall +answer +noclass +nottl -t {0} '.format(rdtype)
    if servers:
        cmd += ''.join(['@{0} '.format(srv) for srv in servers])
    if timeout is not None:
        if servers:
            timeout = int(float(timeout) / len(servers))
        else:
            timeout = int(timeout)
        cmd += '+time={0} '.format(timeout)
    if secure:
        cmd += '+dnssec +adflag '

    cmd = __salt__['cmd.run_all'](cmd + str(name), python_shell=False, output_loglevel='quiet')

    # In this case, 0 is not the same as False
    if cmd['retcode'] != 0:
        log.warning(
            'dig returned ({0}): {1}'.format(
                cmd['retcode'], cmd['stderr']
        ))
        return False

    validated = False
    res = []
    for line in cmd['stdout'].splitlines():
        rname, rtype, rdata = line.split(None, 2)
        if rtype == 'CNAME' and rdtype != 'CNAME':
            continue
        elif rtype == 'RRSIG':
            validated = True
            continue
        res.append(rdata.strip(string.whitespace + '"'))

    if res and secure and not validated:
        return False
    else:
        return res


def _query_drill(name, rdtype, timeout=None, servers=[], secure=None):
    '''
    Use drill to lookup addresses
    :param name: Name of record to search
    :param rdtype: DNS record type
    :param timeout: command return timeout
    :return: [] of records or False if error
    '''
    cmd = 'drill '
    if secure:
        cmd += '-D -o ad '
    cmd += '{0} {1} '.format(rdtype, name)
    if servers:
        cmd += ''.join(['@{0} '.format(srv) for srv in servers])
    cmd = __salt__['cmd.run_all'](
        cmd, timeout=timeout,
        python_shell=False, output_loglevel='quiet')

    # In this case, 0 is not the same as False
    if cmd['retcode'] != 0:
        log.warning(
            'drill returned ({0}): {1}'.format(
                cmd['retcode'], cmd['stderr']
            ))
        return False

    lookup_res = iter(cmd['stdout'].splitlines())
    res = []
    try:
        line = ''
        while 'ANSWER SECTION' not in line:
            line = next(lookup_res)
        while True:
            line = next(lookup_res)
            line = line.strip()
            if not line or line.startswith(';;'):
                break

            l_type, l_rec = line.split(None, 4)[-2:]
            if l_type == 'CNAME' and rdtype != 'CNAME':
                continue
            elif l_type == 'RRSIG':
                validated = True
                continue

            res.append(l_rec.strip(string.whitespace + '"'))

    except StopIteration:
        pass
    finally:
        if res and secure and not validated:
            return False
        else:
            return res


def _query_host(name, rdtype, timeout=None, server=None):
    '''
    Use host to lookup addresses
    :param name: Name of record to search
    :param server: Server to query
    :param rdtype: DNS record type
    :param timeout: server response wait
    :return: [] of records or False if error
    '''
    cmd = 'host -t {0} '.format(rdtype)

    if server is not None:
        cmd += '@{0} '.format(server)
    if timeout:
        cmd += '-W {0} '.format(int(timeout))

    cmd = __salt__['cmd.run_all'](cmd + name, python_shell=False, output_loglevel='quiet')

    # In this case, 0 is not the same as False
    if cmd['retcode'] != 0:
        log.warning(
            'host returned ({0}): {1}'.format(
                cmd['retcode'], cmd['stdout']
        ))
        return False
    elif 'has no' in cmd['stdout']:
        return []

    res = []
    for line in cmd['stdout'].splitlines():
        if rdtype != 'CNAME' and 'is an alias' in line:
            continue
        line = line.split(' ', 3)[-1]
        for prefix in ('record', 'address', 'handled by', 'alias for'):
            if line.startswith(prefix):
                line = line[len(prefix) + 1:]
                break
        res.append(line.strip(string.whitespace + '"'))

    return res


def _query_pydns(name, rdtype, timeout=None, servers=[], secure=None):
    '''
    Use dnspython to lookup addresses
    :param name: Name of record to search
    :param rdtype: DNS record type
    :param timeout: query timeout
    :param server: (list of) server(s) to try in order
    :return: [] of records or False if error
    '''
    resolver = dns.resolver.Resolver(configure=False)

    resolver.ednsflags += dns.flags.DO

    if timeout is not None:
        resolver.lifetime = float(timeout)
    if servers:
        resolver.nameservers = servers
    if secure:
        resolver.ednsflags += dns.flags.DO

    try:
        # ARGH... DNSPython actually does a lot already as well :(
        res = [str(rr.to_text().strip(string.whitespace + '"'))
               for rr in resolver.query(name, rdtype, raise_on_no_answer=False)]
        return res
    except:
        return False


def _query_nslookup(name, rdtype, timeout=None, server=None):
    '''
    Use nslookup to lookup addresses
    :param name: Name of record to search
    :param rdtype: DNS record type
    :param timeout: server response timeout
    :param server: server to query
    :return: [] of records or False if error
    '''
    cmd = 'nslookup -query={0} {1}'.format(rdtype, str(name))

    if timeout is not None:
        cmd += ' -timeout={0}'.format(int(timeout))
    if server is not None:
        cmd += ' {0}'.format(server)

    cmd = __salt__['cmd.run_all'](cmd, python_shell=False, output_loglevel='quiet')
    # In this case, 0 is not the same as False
    if cmd['retcode'] != 0:
        log.warning(
            'nslookup returned ({0}): {1}'.format(
                cmd['retcode'], cmd['stdout'].splitlines()[-1]
            ))
        return False

    # ppr(cmd['stdout'].splitlines())

    lookup_res = iter(cmd['stdout'].splitlines())

    res = []
    try:
        line = ''
        while True:
            if name in line:
                break
            line = next(lookup_res)

        while True:
            # ppr('{}: now at {}'.format(name, line))
            line = line.strip()
            if not line or line.startswith('*'):
                break
            elif rdtype != 'CNAME' and 'canonical name' in line:
                name = line.split()[-1][:-1]
                line = next(lookup_res)
                continue
            elif rdtype == 'SOA':
                line = line.split('=')
            elif line.startswith('Name:'):
                line = next(lookup_res)
                line = line.split(':', 1)
            elif line.startswith(name):
                if '=' in line:
                    line = line.split('=', 1)
                else:
                    line = line.split(' ')

            res.append(line[-1].strip(string.whitespace + '"'))
            line = next(lookup_res)

    except StopIteration:
        pass
    finally:
        if rdtype == 'SOA':
            return [' '.join(res[1:])]
        else:
            return res


def query(
        name,
        rdtype,
        method=None,
        servers=None,
        timeout=None,
        secure=None
):
    '''
    Lookup DNS records
    :param name: name to lookup
    :param rdtype: DNS record type
    :param method: simple, pydns, dig, drill, host, nslookup or auto (default)
    :param servers: (list of) server(s) to try in-order
    :param timeout: query timeout or a valiant approximation of that
    :param secure: return only DNSSEC validated responses
    :return: [] of record data
    '''
    # opts = __opts__.get('dns', {})
    opts = {}
    rdtype = rdtype.upper()

    query_methods = (
        ('simple',   _query_simple,   not any((rdtype not in ('A', 'AAAA'), servers, secure))),
        ('pydns',    _query_pydns,    HAS_PYDNS),
        ('dig',      _query_dig,      HAS_DIG),
        ('drill',    _query_drill,    HAS_DRILL),
        ('host',     _query_host,     HAS_HOST and not secure),
        ('nslookup', _query_nslookup, HAS_NSLOOKUP and not secure),
    )

    method = method or opts.get('method', 'auto')
    try:
        if method == 'auto':
            method, resolver = next(((rname, rcb) for rname, rcb, rtest in query_methods if rtest))
        else:
            resolver = next((rcb for rname, rcb, rtest in query_methods if rname == method and rtest))
    except StopIteration:
        log.error(
            'Unable to lookup {1}/{2}: Resolver method {0} invalid, unsupported or unable to perform query'.format(
                method, rdtype, name
            ))
        return False

    res_kwargs = {
        'name': name,
        'rdtype': rdtype
    }
    if timeout:
        res_kwargs['timeout'] = timeout
    if secure:
        res_kwargs['secure'] = secure

    if not servers:
        res = resolver(**res_kwargs)
    else:
        if not isinstance(servers, (list, tuple)):
            servers = [servers]
        if method in ('pydns', 'dig', 'drill'):
            res_kwargs['servers'] = servers
            res = resolver(**res_kwargs)
        else:
            if timeout:
                res_kwargs['timeout'] = timeout / len(servers)
            for server in servers:
                res = resolver(server=server, **res_kwargs)
                if res:
                    break

    return res


def records(
        name,
        rdtype,
        method=None,
        servers=None,
        timeout=None,
        secure=None
):
    '''
    Parse DNS records
    :param name: name to lookup
    :param rdtype: DNS record type
    :param method: simple, pydns, dig, drill, host, nslookup or auto (default)
    :param servers: (list of) server(s) to try in-order
    :param timeout: query timeout or a valiant approximation of that
    :param secure: return only validated responses
    :return: [] of records
    '''
    rdtype = rdtype.upper()
    if rdtype == 'PTR' and not name.endswith('arpa'):
        name = ptr_name(name)

    res = {}
    for answer in query(name, rdtype, method=method, servers=servers, timeout=timeout, secure=secure):
        ares = {
            'A': a_rec,
            'AAAA': aaaa_rec,
            'SRV': srv_rec
        }
        if rdtype in ares:
            answer = ares[rdtype](answer)
        res.append(answer)

    return res


def ptr_name(rdata):
    '''
    Return PTR name of given IP
    :param rdata: IP address
    :return: PTR record name
    '''
    try:
        return ipaddress.ip_address(rdata).reverse_pointer
    except:  # pylint: disable=bare-except
        log.error('Unable to generate PTR record; {0} is not a valid IP address'.format(rdata))
        return False


def soa_rec(rdata):
    rschema = OrderedDict((
        ('mname', str),
        ('rname', str),
        ('serial', int),
        ('refresh', int),
        ('retry', int),
        ('expire', int),
        ('minimum', int),
    ))
    return _data2rec(rschema, rdata)


def a_rec(rdata):
    rschema = OrderedDict((
        ('address', ipaddress.IPv4Address),
    ))
    return _data2rec(rschema, rdata)


def aaaa_rec(rdata):
    rschema = OrderedDict((
        ('address', ipaddress.IPv6Address),
    ))
    return _data2rec(rschema, rdata)


def srv_data(target, port, prio=10, weight=10):
    '''
    Generate SRV record data
    :param target:
    :param port:
    :param prio:
    :param weight:
    :return:
    '''
    return _rec2data(prio, weight, port, target)


def srv_name(svc, name=None):
    '''
    Generate SRV record name
    :param svc: ldap/tcp, 389/tcp etc

    :param name:
    :return:
    '''
    svc, proto = svc.split('/', 1)

    proto = RFC.validate(proto, RFC.SRV_PROTO)
    if svc.isdigit():
        svc = _to_port(svc)

    if name:
        name = '.' + name
    return '_{0}._{1}{2}'.format(svc, proto, name)


def srv_rec(rdata):
    '''
    Parse SRV record fields
    :param rdata:
    :return:
    '''
    rschema = OrderedDict((
        ('prio', int),
        ('weight', int),
        ('port', _to_port),
        ('name', str),
    ))
    return _data2rec(rschema, rdata)


def sshfp_data(key_t, hash_t, pub):
    '''
    Generate an SSHFP record
    :param key_t: rsa/dsa/ecdsa/ed25519
    :param hash_t: sha1/sha256
    :param pub: the SSH public key
    '''
    key_t = RFC.validate(key_t, RFC.SSHFP_ALGO, 'in')
    hash_t = RFC.validate(hash_t, RFC.SSHFP_HASH)

    hasher = hashlib.new(hash_t)
    hasher.update(
        base64.b64decode(pub)
    )
    fp = hasher.hexdigest()

    return _rec2data(key_t, hash_t, fp)


def parse_resolv(src='/etc/resolv.conf'):
    '''
    Parse a resolver configuration file (traditionally /etc/resolv.conf)
    '''

    nameservers = []
    search = []
    sortlist = []
    domain = ''
    options = []

    try:
        with salt.utils.fopen(src) as src_file:
            # pylint: disable=too-many-nested-blocks
            for line in src_file:
                line = line.strip().split()

                try:
                    (directive, arg) = (line[0].lower(), line[1:])
                    # Drop everything after # or ; (comments)
                    arg = list(itertools.takewhile(
                        lambda x: x[0] not in ('#', ';'), arg))

                    if directive == 'nameserver':
                        try:
                            ip_addr = ipaddress.ip_address(arg[0])
                            if ip_addr not in nameservers:
                                nameservers.append(ip_addr)
                        except ValueError as exc:
                            log.error('{0}: {1}'.format(src, exc))
                    elif directive == 'domain':
                        domain = arg[0]
                    elif directive == 'search':
                        search = arg
                    elif directive == 'sortlist':
                        # A sortlist is specified by IP address netmask pairs.
                        # The netmask is optional and defaults to the natural
                        # netmask of the net. The IP address and optional
                        # network pairs are separated by slashes.
                        for ip_raw in arg:
                            try:
                                ip_net = ipaddress.ip_network(ip_raw)
                            except ValueError as exc:
                                log.error('{0}: {1}'.format(src, exc))
                            else:
                                if '/' not in ip_raw:
                                    # No netmask has been provided, guess
                                    # the "natural" one
                                    if ip_net.version == 4:
                                        ip_addr = str(ip_net.network_address)
                                        # pylint: disable=protected-access
                                        mask = salt.utils.network.\
                                            natural_ipv4_netmask(ip_addr)

                                        ip_net = ipaddress.ip_network(
                                            '{0}{1}'.format(ip_addr, mask),
                                            strict=False
                                        )
                                    if ip_net.version == 6:
                                        # TODO
                                        pass

                                if ip_net not in sortlist:
                                    sortlist.append(ip_net)
                    elif directive == 'options':
                        # Options allows certain internal resolver variables to
                        # be modified.
                        if arg[0] not in options:
                            options.append(arg[0])
                except IndexError:
                    continue

        if domain and search:
            # The domain and search keywords are mutually exclusive.  If more
            # than one instance of these keywords is present, the last instance
            # will override.
            log.debug('{0}: The domain and search keywords are mutually '
                        'exclusive.'.format(src))

        return {
            'nameservers': nameservers,
            'ip4_nameservers': [ip for ip in nameservers if ip.version == 4],
            'ip6_nameservers': [ip for ip in nameservers if ip.version == 6],
            'sortlist': [ip.with_netmask for ip in sortlist],
            'domain': domain,
            'search': search,
            'options': options
        }
    except IOError:
        return {}
