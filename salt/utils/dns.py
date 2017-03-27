# -*- coding: utf-8 -*-
'''
Compendium of generic DNS utilities
# Examples:
dns.lookup(name, rdtype, ...)
dns.query(name, rdtype, ...)

dns.srv_rec(data)
dns.srv_data('my1.example.com', 389, prio=10, weight=100)
dns.srv_name('ldap/tcp', 'example.com')

'''
from __future__ import print_function, absolute_import
# Python
import base64
import binascii
import hashlib
import itertools
import random
import socket
import shlex
import ssl
import string
from salt.ext.six.moves import zip  # pylint: disable=redefined-builtin
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
    HAS_DNSPYTHON = True
except ImportError as e:
    HAS_DNSPYTHON = False
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
    '''
    Simple holding class for all RFC/IANA registered lists & standards
    '''
    # https://tools.ietf.org/html/rfc6844#section-3
    COO_TAGS = (
        'issue',
        'issuewild',
        'iodef'
    )

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


def _to_port(port):
    try:
        port = int(port)
        assert 1 <= port <= 65535
        return port
    except (ValueError, AssertionError):
        raise ValueError('Invalid port {0}'.format(port))


def _tree(domain, tld=False):
    '''
    Split out a domain in its parents
    :param domain: dc2.ams2.example.com
    :param tld: Include TLD in list
    :return: [ 'dc2.ams2.example.com', 'ams2.example.com', 'example.com']
    '''
    if '.' not in domain:
        raise ValueError('Provide a decent domain')

    res = [domain]
    while True:
        idx = domain.find('.')
        if idx < 0:
            break
        domain = domain[idx + 1:]
        res.append(domain)

    # properly validating the tld is impractical
    if not tld:
        res = res[:-1]

    return res


def _weighted_order(recs):
    res = []
    weights = [rec['weight'] for rec in recs]
    while weights:
        rnd = random.random() * sum(weights)
        for i, w in enumerate(weights):
            rnd -= w
            if rnd < 0:
                res.append(recs.pop(i)['name'])
                weights.pop(i)
                break

    return res


def _data2rec(schema, rec_data):
    '''
    schema = OrderedDict({
        'prio': int,
        'weight': int,
        'port': to_port,
        'name': str,
    })
    rec_data = '10 20 25 myawesome.nl'

    res = {'prio': 10, 'weight': 20, 'port': 25 'name': 'myawesome.nl'}
    '''
    # ppr(schema)
    try:
        rec_fields = rec_data.split(' ')
        assert len(rec_fields) == len(schema)
        return dict((
            (field_name, rec_cast(rec_field))
            for (field_name, rec_cast), rec_field in zip(schema.items(), rec_fields)
        ))
    except (AssertionError, AttributeError, TypeError, ValueError) as e:
        raise ValueError('Unable to cast "{0}" as "{2}": {1}'.format(
            rec_data,
            e,
            ' '.join(schema.keys())
        ))


def _data2rec_group(schema, recs_data, group_key):
    # ppr(schema)
    if not isinstance(recs_data, (list, tuple)):
        recs_data = [recs_data]

    res = OrderedDict()

    try:
        for rdata in recs_data:
            rdata = _data2rec(schema, rdata)
            assert rdata and group_key in rdata
            idx = rdata.pop(group_key)
            if idx not in res:
                res[idx] = []
            res[idx].append(rdata)
        return res
    except (AssertionError, ValueError) as e:
        raise ValueError('Unable to cast "{0}" as a group of "{1}": {2}'.format(
            ','.join(recs_data),
            ' '.join(schema.keys()),
            e
        ))


def _rec2data(*rdata):
    return ' '.join(rdata)


def _lookup_gai(name, rdtype, timeout=None):
    '''
    Use Python's socket interface to lookup addresses
    :param name: Name of record to search
    :param rdtype: A or AAAA
    :param timeout: ignored
    :return: [] of addresses or False if error
    '''
    sock_t = {
        'A':    socket.AF_INET,
        'AAAA': socket.AF_INET6
    }[rdtype]

    if timeout:
        log.warn('Ignoring timeout on gai resolver; fix resolv.conf to do that')

    try:
        addresses = [sock[4][0] for sock in socket.getaddrinfo(name, None, sock_t, 0, socket.SOCK_RAW)]
        return addresses
    except socket.gaierror:
        return False


def _lookup_dig(name, rdtype, timeout=None, servers=None, secure=None):
    '''
    Use dig to lookup addresses
    :param name: Name of record to search
    :param rdtype: DNS record type
    :param timeout: server response timeout
    :param servers: [] of servers to use
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
        log.warning('dig returned ({0}): {1}'.format(
            cmd['retcode'], cmd['stderr']
        ))
        return False

    validated = False
    res = []
    for line in cmd['stdout'].splitlines():
        _, rtype, rdata = line.split(None, 2)
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


def _lookup_drill(name, rdtype, timeout=None, servers=None, secure=None):
    '''
    Use drill to lookup addresses
    :param name: Name of record to search
    :param rdtype: DNS record type
    :param timeout: command return timeout
    :param servers: [] of servers to use
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
        log.warning('drill returned ({0}): {1}'.format(
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

    if res and secure and not validated:
        return False
    else:
        return res


def _lookup_host(name, rdtype, timeout=None, server=None):
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
        log.warning('host returned ({0}): {1}'.format(
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


def _lookup_dnspython(name, rdtype, timeout=None, servers=None, secure=None):
    '''
    Use dnspython to lookup addresses
    :param name: Name of record to search
    :param rdtype: DNS record type
    :param timeout: query timeout
    :param server: [] of server(s) to try in order
    :return: [] of records or False if error
    '''
    resolver = dns.resolver.Resolver()

    if timeout is not None:
        resolver.lifetime = float(timeout)
    if servers:
        resolver.nameservers = servers
    if secure:
        resolver.ednsflags += dns.flags.DO

    try:
        res = [str(rr.to_text().strip(string.whitespace + '"'))
               for rr in resolver.query(name, rdtype, raise_on_no_answer=False)]
        return res
    except (dns.resolver.NXDOMAIN,
            dns.resolver.YXDOMAIN,
            dns.resolver.NoNameservers,
            dns.exception.Timeout):
        return False


def _lookup_nslookup(name, rdtype, timeout=None, server=None):
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
        log.warning('nslookup returned ({0}): {1}'.format(
            cmd['retcode'], cmd['stdout'].splitlines()[-1]
        ))
        return False

    lookup_res = iter(cmd['stdout'].splitlines())

    res = []
    try:
        line = ''
        while True:
            if name in line:
                break
            line = next(lookup_res)

        while True:
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

    if rdtype == 'SOA':
        return [' '.join(res[1:])]
    else:
        return res


def lookup(
    name,
    rdtype,
    method=None,
    servers=None,
    timeout=None,
    walk=False,
    walk_tld=False,
    secure=None
):
    '''
    Lookup DNS record data
    :param name: name to lookup
    :param rdtype: DNS record type
    :param method: gai (getaddrinfo()), pydns, dig, drill, host, nslookup or auto (default)
    :param servers: (list of) server(s) to try in-order
    :param timeout: query timeout or a valiant approximation of that
    :param walk: Find records in parents if they don't exist
    :param walk_tld: Include the final domain in the walk
    :param secure: return only DNSSEC secured responses
    :return: [] of record data
    '''
    # opts = __opts__.get('dns', {})
    opts = {}
    method = method or opts.get('method', 'auto')
    secure = secure or opts.get('secure', None)
    servers = servers or opts.get('servers', None)
    timeout = timeout or opts.get('timeout', False)

    rdtype = rdtype.upper()

    # pylint: disable=bad-whitespace,multiple-spaces-before-keyword
    query_methods = (
        ('gai',       _lookup_gai,       not any((rdtype not in ('A', 'AAAA'), servers, secure))),
        ('dnspython', _lookup_dnspython, HAS_DNSPYTHON),
        ('dig',       _lookup_dig,       HAS_DIG),
        ('drill',     _lookup_drill,     HAS_DRILL),
        ('host',      _lookup_host,      HAS_HOST and not secure),
        ('nslookup',  _lookup_nslookup,  HAS_NSLOOKUP and not secure),
    )
    # pylint: enable=bad-whitespace,multiple-spaces-before-keyword

    try:
        if method == 'auto':
            # The first one not to bork on the conditions becomes the function
            method, resolver = next(((rname, rcb) for rname, rcb, rtest in query_methods if rtest))
        else:
            # The first one not to bork on the conditions becomes the function. And the name must match.
            resolver = next((rcb for rname, rcb, rtest in query_methods if rname == method and rtest))
    except StopIteration:
        log.error(
            'Unable to lookup {1}/{2}: Resolver method {0} invalid, unsupported or unable to perform query'.format(
                method, rdtype, name
            ))
        return False

    res_kwargs = {
        'rdtype': rdtype,
    }

    if servers:
        if not isinstance(servers, (list, tuple)):
            servers = [servers]
        if method in ('pydns', 'dig', 'drill'):
            res_kwargs['servers'] = servers
        else:
            if timeout:
                timeout /= len(servers)

            # Inject a wrapper for multi-server behaviour
            def _multi_srvr(**res_kwargs):
                for server in servers:
                    s_res = resolver(server=server, **res_kwargs)
                    if s_res:
                        return s_res
            resolver = _multi_srvr

    if not walk:
        name = [name]
    else:
        idx = 0
        if rdtype == 'SRV':  # The only rr I know that has 2 name components
            idx = name.find('.') + 1
        idx = name.find('.', idx) + 1
        domain = name[idx:]
        name = name[0:idx]

        name = [name + domain for domain in _tree(domain, walk_tld)]
        if timeout:
            timeout /= len(name)

    if secure:
        res_kwargs['secure'] = secure
    if timeout:
        res_kwargs['timeout'] = timeout

    for rname in name:
        res = resolver(name=rname, **res_kwargs)
        if res:
            return res


def query(
    name,
    rdtype,
    method=None,
    servers=None,
    timeout=None,
    walk=False,
    walk_tld=False,
    secure=None
):
    '''
    Query DNS for information
    :param name: name to lookup
    :param rdtype: DNS record type
    :param method: gai (getaddrinfo()), pydns, dig, drill, host, nslookup or auto (default)
    :param servers: (list of) server(s) to try in-order
    :param timeout: query timeout or a valiant approximation of that
    :param secure: return only DNSSEC secured response
    :param walk: Find records in parents if they don't exist
    :param walk_tld: Include the final domain in the walk
    :return: [] of records
    '''
    rdtype = rdtype.upper()
    qargs = {
        'method':   method,
        'servers':  servers,
        'timeout':  timeout,
        'walk':     walk,
        'walk_tld': walk_tld,
        'secure':   secure
    }

    if rdtype == 'PTR' and not name.endswith('arpa'):
        name = ptr_name(name)

    qres = lookup(name, rdtype, **qargs)
    if rdtype == 'SPF' and not qres:
        # 'SPF' has become a regular 'TXT' again
        qres = [answer for answer in lookup(name, 'TXT', **qargs) if answer.startswith('v=spf')]

    rec_map = {
        'A':    a_rec,
        'AAAA': aaaa_rec,
        'CAA':  caa_rec,
        'MX':   mx_rec,
        'SOA':  soa_rec,
        'SPF':  spf_rec,
        'SRV':  srv_rec,
    }

    if rdtype not in rec_map:
        return qres

    caster = rec_map[rdtype]

    if rdtype in ('MX', 'SRV'):
        # Grouped returns
        res = caster(qres)
    else:
        # List of results
        res = map(caster, qres)

    return res


def a_rec(rdata):
    '''
    Validate and parse DNS record data for an A record
    :param rdata: DNS record data
    :return: { 'address': ip }
    '''
    rschema = OrderedDict((
        ('address', ipaddress.IPv4Address),
    ))
    return _data2rec(rschema, rdata)


def aaaa_rec(rdata):
    '''
    Validate and parse DNS record data for an AAAA record
    :param rdata: DNS record data
    :return: { 'address': ip }
    '''
    rschema = OrderedDict((
        ('address', ipaddress.IPv6Address),
    ))
    return _data2rec(rschema, rdata)


def caa_rec(rdatas):
    '''
    Validate and parse DNS record data for a CAA record
    :param rdata: DNS record data
    :return: dict w/fields
    '''
    rschema = OrderedDict((
        ('flags', lambda flag: ['critical'] if int(flag) > 0 else []),
        ('tag', lambda tag: RFC.validate(tag, RFC.COO_TAGS)),
        ('value', lambda val: str(val).strip('"'))
    ))

    res = _data2rec_group(rschema, rdatas, 'tag')

    for tag in ('issue', 'issuewild'):
        tag_res = res.get(tag, False)
        if not tag_res:
            continue
        for idx, val in enumerate(tag_res):
            if ';' not in val:
                continue
            val, params = val.split(';', 1)
            params = dict(param.split('=') for param in shlex.split(params))
            tag_res[idx] = {val: params}

    return res


def mx_data(target, preference=10):
    '''
    Generate MX record data
    :param target: server
    :param preference: preference number
    :return: DNS record data
    '''
    return _rec2data(int(preference), target)


def mx_rec(rdatas):
    '''
    Validate and parse DNS record data for MX record(s)
    :param rdata: DNS record data
    :return: dict w/fields
    '''
    rschema = OrderedDict((
        ('preference', int),
        ('name', str),
    ))
    return _data2rec_group(rschema, rdatas, 'preference')


def ptr_name(rdata):
    '''
    Return PTR name of given IP
    :param rdata: IP address
    :return: PTR record name
    '''
    try:
        return ipaddress.ip_address(rdata).reverse_pointer
    except ValueError:
        log.error('Unable to generate PTR record; {0} is not a valid IP address'.format(rdata))
        return False


def soa_rec(rdata):
    '''
    Validate and parse DNS record data for SOA record(s)
    :param rdata: DNS record data
    :return: dict w/fields
    '''
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


def spf_rec(rdata):
    '''
    Validate and parse DNS record data for SPF record(s)
    :param rdata: DNS record data
    :return: dict w/fields
    '''
    spf_fields = rdata.split(' ')
    if not spf_fields.pop(0).startswith('v=spf'):
        raise ValueError('Not an SPF record')

    res = OrderedDict()
    mods = set()
    for mech_spec in spf_fields:
        if mech_spec.startswith(('exp', 'redirect')):
            # It's a modifier
            mod, val = mech_spec.split('=', 1)
            if mod in mods:
                raise KeyError('Modifier {0} can only appear once'.format(mod))

            mods.add(mod)
            continue

            # TODO: Should be in something intelligent like an SPF_get
            # if mod == 'exp':
            #     res[mod] = query(val, 'TXT', **qargs)
            #     continue
            # elif mod == 'redirect':
            #     return records(val, 'SPF', **qargs)

        mech = {}
        if mech_spec[0] in ('+', '-', '~', '?'):
            mech['qualifier'] = mech_spec[0]
            mech_spec = mech_spec[1:]

        if ':' in mech_spec:
            mech_spec, val = mech_spec.split(':', 1)
        elif '/' in mech_spec:
            idx = mech_spec.find('/')
            mech_spec = mech_spec[0:idx]
            val = mech_spec[idx:]
        else:
            val = None

        res[mech_spec] = mech
        if not val:
            continue
        elif mech_spec in ('ip4', 'ip6'):
            val = ipaddress.ip_interface(val)
            assert val.version == int(mech_spec[-1])

        mech['value'] = val

    return res


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


def srv_name(svc, proto='tcp', domain=None):
    '''
    Generate SRV record name
    :param svc: ldap, 389 etc
    :param proto: tcp, udp, sctp etc.
    :param domain: name to append
    :return:
    '''
    proto = RFC.validate(proto, RFC.SRV_PROTO)
    if svc.isdigit():
        svc = _to_port(svc)

    if domain:
        domain = '.' + domain
    return '_{0}._{1}{2}'.format(svc, proto, domain)


def srv_rec(rdatas):
    '''
    Validate and parse DNS record data for SRV record(s)
    :param rdata: DNS record data
    :return: dict w/fields
    '''
    rschema = OrderedDict((
        ('prio', int),
        ('weight', int),
        ('port', _to_port),
        ('name', str),
    ))
    return _data2rec_group(rschema, rdatas, 'prio')


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
    ssh_fp = hasher.hexdigest()

    return _rec2data(key_t, hash_t, ssh_fp)


def tlsa_data(pub, usage, selector, matching):
    '''
    Generate a TLSA rec
    :param pub: Pub key in PEM format
    :param usage:
    :param selector:
    :param matching:
    :return: TLSA data portion
    '''
    usage = RFC.validate(usage, RFC.TLSA_USAGE)
    selector = RFC.validate(selector, RFC.TLSA_SELECT)
    matching = RFC.validate(matching, RFC.TLSA_MATCHING)

    pub = ssl.PEM_cert_to_DER_cert(pub.strip())
    if matching == 0:
        cert_fp = binascii.b2a_hex(pub)
    else:
        hasher = hashlib.new(RFC.TLSA_MATCHING[matching])
        hasher.update(
            pub
        )
        cert_fp = hasher.hexdigest()

    return _rec2data(usage, selector, matching, cert_fp)


def service(
    svc,
    proto='tcp',
    domain=None,
    walk=False,
    secure=None
):
    '''
    Find an SRV service in a domain or it's parents
    :param svc: service to find (ldap, 389, etc)
    :param proto: protocol the service talks (tcp, udp, etc)
    :param domain: domain to start search in
    :param walk: walk the parents if domain doesn't provide the service
    :param secure: only return DNSSEC-validated results
    :return: [
        [ prio1server1, prio1server2 ],
        [ prio2server1, prio2server2 ],
    ] (the servers will already be weighted according to the SRV rules)
    '''
    qres = query(srv_name(svc, proto, domain), 'SRV', walk=walk, secure=secure)
    if not qres:
        return False

    res = []
    for _, recs in qres.items():
        res.append(_weighted_order(recs))

    return res


def services(services_file='/etc/services'):
    '''
    Parse through system-known services
    :return: {
        'svc': [
          {  'port': port
             'proto': proto,
             'desc': comment
          },
        ],
    }
    '''
    res = {}
    with salt.utils.fopen(services_file, 'r') as svc_defs:
        for svc_def in svc_defs.readlines():
            svc_def = svc_def.strip()
            if not len(svc_def) or svc_def.startswith('#'):
                continue
            elif '#' in svc_def:
                svc_def, comment = svc_def.split('#', 1)
                comment = comment.strip()
            else:
                comment = None
            svc_def = svc_def.split()

            port, proto = svc_def.pop(1).split('/')
            port = int(port)

            for name in svc_def:
                svc_res = res.get(name, {})
                pp_res = svc_res.get(port, False)
                if not pp_res:
                    svc = {
                        'port':  port,
                        'proto': proto,
                    }
                    if comment:
                        svc['desc'] = comment
                    svc_res[port] = svc
                else:
                    curr_proto = pp_res['proto']
                    if isinstance(curr_proto, (list, tuple)):
                        curr_proto.append(proto)
                    else:
                        pp_res['proto'] = [curr_proto, proto]

                    curr_desc = pp_res.get('desc', False)
                    if comment:
                        if not curr_desc:
                            pp_res['desc'] = comment
                        elif comment != curr_desc:
                            pp_res['desc'] = '{0}, {1}'.format(curr_desc, comment)
                res[name] = svc_res

    for svc, data in res.items():
        if len(data) == 1:
            res[svc] = data.values().pop()
            continue
        else:
            res[svc] = list(data.values())

    return res


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
                                        mask = salt.utils.network.natural_ipv4_netmask(ip_addr)
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
            'nameservers':     nameservers,
            'ip4_nameservers': [ip for ip in nameservers if ip.version == 4],
            'ip6_nameservers': [ip for ip in nameservers if ip.version == 6],
            'sortlist':        [ip.with_netmask for ip in sortlist],
            'domain':          domain,
            'search':          search,
            'options':         options
        }
    except IOError:
        return {}
