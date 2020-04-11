# -*- coding: utf-8 -*-
"""
Compendium of generic DNS utilities
# Examples:
dns.lookup(name, rdtype, ...)
dns.query(name, rdtype, ...)

dns.srv_rec(data)
dns.srv_data('my1.example.com', 389, prio=10, weight=100)
dns.srv_name('ldap/tcp', 'example.com')

"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import base64
import binascii
import functools
import hashlib
import itertools
import logging
import random
import re
import shlex
import socket
import ssl
import string

import salt.modules.cmdmod

# Import Salt libs
import salt.utils.files
import salt.utils.network
import salt.utils.path
import salt.utils.stringutils
from salt._compat import ipaddress

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import zip  # pylint: disable=redefined-builtin
from salt.utils.odict import OrderedDict

# Integrations
try:
    import dns.resolver

    HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False
try:
    import tldextract

    HAS_TLDEXTRACT = True
except ImportError:
    HAS_TLDEXTRACT = False
HAS_DIG = salt.utils.path.which("dig") is not None
DIG_OPTIONS = "+search +fail +noall +answer +nocl +nottl"
HAS_DRILL = salt.utils.path.which("drill") is not None
HAS_HOST = salt.utils.path.which("host") is not None
HAS_NSLOOKUP = salt.utils.path.which("nslookup") is not None

__salt__ = {"cmd.run_all": salt.modules.cmdmod.run_all}
log = logging.getLogger(__name__)


class RFC(object):
    """
    Simple holding class for all RFC/IANA registered lists & standards
    """

    # https://tools.ietf.org/html/rfc6844#section-3
    CAA_TAGS = ("issue", "issuewild", "iodef")

    # http://www.iana.org/assignments/dns-sshfp-rr-parameters/dns-sshfp-rr-parameters.xhtml
    SSHFP_ALGO = OrderedDict(((1, "rsa"), (2, "dsa"), (3, "ecdsa"), (4, "ed25519"),))

    SSHFP_HASH = OrderedDict(((1, "sha1"), (2, "sha256"),))

    # http://www.iana.org/assignments/dane-parameters/dane-parameters.xhtml
    TLSA_USAGE = OrderedDict(
        ((0, "pkixta"), (1, "pkixee"), (2, "daneta"), (3, "daneee"),)
    )

    TLSA_SELECT = OrderedDict(((0, "cert"), (1, "spki"),))

    TLSA_MATCHING = OrderedDict(((0, "full"), (1, "sha256"), (2, "sha512"),))

    SRV_PROTO = ("tcp", "udp", "sctp")

    @staticmethod
    def validate(lookup, ref, match=None):
        if lookup in ref:
            return lookup
        elif match == "in":
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
        raise ValueError("Invalid port {0}".format(port))


def _tree(domain, tld=False):
    """
    Split out a domain in its parents

    Leverages tldextract to take the TLDs from publicsuffix.org
    or makes a valiant approximation of that

    :param domain: dc2.ams2.example.com
    :param tld: Include TLD in list
    :return: [ 'dc2.ams2.example.com', 'ams2.example.com', 'example.com']
    """
    domain = domain.rstrip(".")
    assert "." in domain, "Provide a decent domain"

    if not tld:
        if HAS_TLDEXTRACT:
            tld = tldextract.extract(domain).suffix
        else:
            tld = re.search(
                r"((?:(?:ac|biz|com?|info|edu|gov|mil|name|net|n[oi]m|org)\.)?[^.]+)$",
                domain,
            ).group()
            log.info(
                "Without tldextract, dns.util resolves the TLD of {0} to {1}".format(
                    domain, tld
                )
            )

    res = [domain]
    while True:
        idx = domain.find(".")
        if idx < 0:
            break
        domain = domain[idx + 1 :]
        if domain == tld:
            break
        res.append(domain)

    return res


def _weighted_order(recs):
    res = []
    weights = [rec["weight"] for rec in recs]
    while weights:
        rnd = random.random() * sum(weights)
        for i, w in enumerate(weights):
            rnd -= w
            if rnd < 0:
                res.append(recs.pop(i)["name"])
                weights.pop(i)
                break

    return res


def _cast(rec_data, rec_cast):
    if isinstance(rec_cast, dict):
        rec_data = type(rec_cast.keys()[0])(rec_data)
        res = rec_cast[rec_data]
        return res
    elif isinstance(rec_cast, (list, tuple)):
        return RFC.validate(rec_data, rec_cast)
    else:
        return rec_cast(rec_data)


def _data2rec(schema, rec_data):
    """
    schema = OrderedDict({
        'prio': int,
        'weight': int,
        'port': to_port,
        'name': str,
    })
    rec_data = '10 20 25 myawesome.nl'

    res = {'prio': 10, 'weight': 20, 'port': 25 'name': 'myawesome.nl'}
    """
    try:
        rec_fields = rec_data.split(" ")
        # spaces in digest fields are allowed
        assert len(rec_fields) >= len(schema)
        if len(rec_fields) > len(schema):
            cutoff = len(schema) - 1
            rec_fields = rec_fields[0:cutoff] + ["".join(rec_fields[cutoff:])]

        if len(schema) == 1:
            res = _cast(rec_fields[0], next(iter(schema.values())))
        else:
            res = dict(
                (
                    (field_name, _cast(rec_field, rec_cast))
                    for (field_name, rec_cast), rec_field in zip(
                        schema.items(), rec_fields
                    )
                )
            )
        return res
    except (AssertionError, AttributeError, TypeError, ValueError) as e:
        raise ValueError(
            'Unable to cast "{0}" as "{2}": {1}'.format(
                rec_data, e, " ".join(schema.keys())
            )
        )


def _data2rec_group(schema, recs_data, group_key):
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

            if len(rdata) == 1:
                rdata = next(iter(rdata.values()))

            res[idx].append(rdata)
        return res
    except (AssertionError, ValueError) as e:
        raise ValueError(
            'Unable to cast "{0}" as a group of "{1}": {2}'.format(
                ",".join(recs_data), " ".join(schema.keys()), e
            )
        )


def _rec2data(*rdata):
    return " ".join(rdata)


def _data_clean(data):
    data = data.strip(string.whitespace)
    if data.startswith(('"', "'")) and data.endswith(('"', "'")):
        return data[1:-1]
    else:
        return data


def _lookup_dig(name, rdtype, timeout=None, servers=None, secure=None):
    """
    Use dig to lookup addresses
    :param name: Name of record to search
    :param rdtype: DNS record type
    :param timeout: server response timeout
    :param servers: [] of servers to use
    :return: [] of records or False if error
    """
    cmd = "dig {0} -t {1} ".format(DIG_OPTIONS, rdtype)
    if servers:
        cmd += "".join(["@{0} ".format(srv) for srv in servers])
    if timeout is not None:
        if servers:
            timeout = int(float(timeout) / len(servers))
        else:
            timeout = int(timeout)
        cmd += "+time={0} ".format(timeout)
    if secure:
        cmd += "+dnssec +adflag "

    cmd = __salt__["cmd.run_all"](
        "{0} {1}".format(cmd, name), python_shell=False, output_loglevel="quiet"
    )

    if "ignoring invalid type" in cmd["stderr"]:
        raise ValueError("Invalid DNS type {}".format(rdtype))
    elif cmd["retcode"] != 0:
        log.warning(
            "dig returned (%s): %s",
            cmd["retcode"],
            cmd["stderr"].strip(string.whitespace + ";"),
        )
        return False
    elif not cmd["stdout"]:
        return []

    validated = False
    res = []
    for line in cmd["stdout"].splitlines():
        _, rtype, rdata = line.split(None, 2)
        if rtype == "CNAME" and rdtype != "CNAME":
            continue
        elif rtype == "RRSIG":
            validated = True
            continue
        res.append(_data_clean(rdata))

    if res and secure and not validated:
        return False
    else:
        return res


def _lookup_drill(name, rdtype, timeout=None, servers=None, secure=None):
    """
    Use drill to lookup addresses
    :param name: Name of record to search
    :param rdtype: DNS record type
    :param timeout: command return timeout
    :param servers: [] of servers to use
    :return: [] of records or False if error
    """
    cmd = "drill "
    if secure:
        cmd += "-D -o ad "
    cmd += "{0} {1} ".format(rdtype, name)
    if servers:
        cmd += "".join(["@{0} ".format(srv) for srv in servers])
    cmd = __salt__["cmd.run_all"](
        cmd, timeout=timeout, python_shell=False, output_loglevel="quiet"
    )

    if cmd["retcode"] != 0:
        log.warning("drill returned (%s): %s", cmd["retcode"], cmd["stderr"])
        return False

    lookup_res = iter(cmd["stdout"].splitlines())
    validated = False
    res = []
    try:
        line = ""
        while "ANSWER SECTION" not in line:
            line = next(lookup_res)
        while True:
            line = next(lookup_res)
            line = line.strip()
            if not line or line.startswith(";;"):
                break

            l_type, l_rec = line.split(None, 4)[-2:]
            if l_type == "CNAME" and rdtype != "CNAME":
                continue
            elif l_type == "RRSIG":
                validated = True
                continue
            elif l_type != rdtype:
                raise ValueError("Invalid DNS type {}".format(rdtype))

            res.append(_data_clean(l_rec))

    except StopIteration:
        pass

    if res and secure and not validated:
        return False
    else:
        return res


def _lookup_gai(name, rdtype, timeout=None):
    """
    Use Python's socket interface to lookup addresses
    :param name: Name of record to search
    :param rdtype: A or AAAA
    :param timeout: ignored
    :return: [] of addresses or False if error
    """
    try:
        sock_t = {"A": socket.AF_INET, "AAAA": socket.AF_INET6}[rdtype]
    except KeyError:
        raise ValueError("Invalid DNS type {} for gai lookup".format(rdtype))

    if timeout:
        log.info("Ignoring timeout on gai resolver; fix resolv.conf to do that")

    try:
        addresses = [
            sock[4][0]
            for sock in socket.getaddrinfo(name, None, sock_t, 0, socket.SOCK_RAW)
        ]
        return addresses
    except socket.gaierror:
        return False


def _lookup_host(name, rdtype, timeout=None, server=None):
    """
    Use host to lookup addresses
    :param name: Name of record to search
    :param server: Server to query
    :param rdtype: DNS record type
    :param timeout: server response wait
    :return: [] of records or False if error
    """
    cmd = "host -t {0} ".format(rdtype)

    if timeout:
        cmd += "-W {0} ".format(int(timeout))
    cmd += name
    if server is not None:
        cmd += " {0}".format(server)

    cmd = __salt__["cmd.run_all"](cmd, python_shell=False, output_loglevel="quiet")

    if "invalid type" in cmd["stderr"]:
        raise ValueError("Invalid DNS type {}".format(rdtype))
    elif cmd["retcode"] != 0:
        log.warning("host returned (%s): %s", cmd["retcode"], cmd["stderr"])
        return False
    elif "has no" in cmd["stdout"]:
        return []

    res = []
    _stdout = cmd["stdout"] if server is None else cmd["stdout"].split("\n\n")[-1]
    for line in _stdout.splitlines():
        if rdtype != "CNAME" and "is an alias" in line:
            continue
        line = line.split(" ", 3)[-1]
        for prefix in ("record", "address", "handled by", "alias for"):
            if line.startswith(prefix):
                line = line[len(prefix) + 1 :]
                break
        res.append(_data_clean(line))

    return res


def _lookup_dnspython(name, rdtype, timeout=None, servers=None, secure=None):
    """
    Use dnspython to lookup addresses
    :param name: Name of record to search
    :param rdtype: DNS record type
    :param timeout: query timeout
    :param server: [] of server(s) to try in order
    :return: [] of records or False if error
    """
    resolver = dns.resolver.Resolver()

    if timeout is not None:
        resolver.lifetime = float(timeout)
    if servers:
        resolver.nameservers = servers
    if secure:
        resolver.ednsflags += dns.flags.DO

    try:
        res = [
            _data_clean(rr.to_text())
            for rr in resolver.query(name, rdtype, raise_on_no_answer=False)
        ]
        return res
    except dns.rdatatype.UnknownRdatatype:
        raise ValueError("Invalid DNS type {}".format(rdtype))
    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.YXDOMAIN,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
    ):
        return False


def _lookup_nslookup(name, rdtype, timeout=None, server=None):
    """
    Use nslookup to lookup addresses
    :param name: Name of record to search
    :param rdtype: DNS record type
    :param timeout: server response timeout
    :param server: server to query
    :return: [] of records or False if error
    """
    cmd = "nslookup -query={0} {1}".format(rdtype, name)

    if timeout is not None:
        cmd += " -timeout={0}".format(int(timeout))
    if server is not None:
        cmd += " {0}".format(server)

    cmd = __salt__["cmd.run_all"](cmd, python_shell=False, output_loglevel="quiet")

    if cmd["retcode"] != 0:
        log.warning(
            "nslookup returned (%s): %s",
            cmd["retcode"],
            cmd["stdout"].splitlines()[-1].strip(string.whitespace + ";"),
        )
        return False

    lookup_res = iter(cmd["stdout"].splitlines())
    res = []
    try:
        line = next(lookup_res)
        if "unknown query type" in line:
            raise ValueError("Invalid DNS type {}".format(rdtype))

        while True:
            if name in line:
                break
            line = next(lookup_res)

        while True:
            line = line.strip()
            if not line or line.startswith("*"):
                break
            elif rdtype != "CNAME" and "canonical name" in line:
                name = line.split()[-1][:-1]
                line = next(lookup_res)
                continue
            elif rdtype == "SOA":
                line = line.split("=")
            elif line.startswith("Name:"):
                line = next(lookup_res)
                line = line.split(":", 1)
            elif line.startswith(name):
                if "=" in line:
                    line = line.split("=", 1)
                else:
                    line = line.split(" ")

            res.append(_data_clean(line[-1]))
            line = next(lookup_res)

    except StopIteration:
        pass

    if rdtype == "SOA":
        return [" ".join(res[1:])]
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
    secure=None,
):
    """
    Lookup DNS records and return their data

    :param name: name to lookup
    :param rdtype: DNS record type
    :param method: gai (getaddrinfo()), dnspython, dig, drill, host, nslookup or auto (default)
    :param servers: (list of) server(s) to try in-order
    :param timeout: query timeout or a valiant approximation of that
    :param walk: Walk the DNS upwards looking for the record type or name/recordtype if walk='name'.
    :param walk_tld: Include the final domain in the walk
    :param secure: return only DNSSEC secured responses
    :return: [] of record data
    """
    # opts = __opts__.get('dns', {})
    opts = {}
    method = method or opts.get("method", "auto")
    secure = secure or opts.get("secure", None)
    servers = servers or opts.get("servers", None)
    timeout = timeout or opts.get("timeout", False)

    rdtype = rdtype.upper()

    # pylint: disable=bad-whitespace,multiple-spaces-before-keyword
    query_methods = (
        ("gai", _lookup_gai, not any((rdtype not in ("A", "AAAA"), servers, secure))),
        ("dnspython", _lookup_dnspython, HAS_DNSPYTHON),
        ("dig", _lookup_dig, HAS_DIG),
        ("drill", _lookup_drill, HAS_DRILL),
        ("host", _lookup_host, HAS_HOST and not secure),
        ("nslookup", _lookup_nslookup, HAS_NSLOOKUP and not secure),
    )
    # pylint: enable=bad-whitespace,multiple-spaces-before-keyword

    try:
        if method == "auto":
            # The first one not to bork on the conditions becomes the function
            method, resolver = next(
                ((rname, rcb) for rname, rcb, rtest in query_methods if rtest)
            )
        else:
            # The first one not to bork on the conditions becomes the function. And the name must match.
            resolver = next(
                (
                    rcb
                    for rname, rcb, rtest in query_methods
                    if rname == method and rtest
                )
            )
    except StopIteration:
        log.error(
            "Unable to lookup %s/%s: Resolver method %s invalid, unsupported "
            "or unable to perform query",
            method,
            rdtype,
            name,
        )
        return False

    res_kwargs = {
        "rdtype": rdtype,
    }

    if servers:
        if not isinstance(servers, (list, tuple)):
            servers = [servers]
        if method in ("dnspython", "dig", "drill"):
            res_kwargs["servers"] = servers
        else:
            if timeout:
                timeout /= len(servers)

            # Inject a wrapper for multi-server behaviour
            def _multi_srvr(resolv_func):
                @functools.wraps(resolv_func)
                def _wrapper(**res_kwargs):
                    for server in servers:
                        s_res = resolv_func(server=server, **res_kwargs)
                        if s_res:
                            return s_res

                return _wrapper

            resolver = _multi_srvr(resolver)

    if not walk:
        name = [name]
    else:
        idx = 0
        if rdtype in ("SRV", "TLSA"):  # The only RRs I know that have 2 name components
            idx = name.find(".") + 1
        idx = name.find(".", idx) + 1
        domain = name[idx:]
        rname = name[0:idx]

        name = _tree(domain, walk_tld)
        if walk == "name":
            name = [rname + domain for domain in name]

        if timeout:
            timeout /= len(name)

    if secure:
        res_kwargs["secure"] = secure
    if timeout:
        res_kwargs["timeout"] = timeout

    for rname in name:
        res = resolver(name=rname, **res_kwargs)
        if res:
            return res

    return res


def query(
    name,
    rdtype,
    method=None,
    servers=None,
    timeout=None,
    walk=False,
    walk_tld=False,
    secure=None,
):
    """
    Query DNS for information.
    Where `lookup()` returns record data, `query()` tries to interpret the data and return it's results

    :param name: name to lookup
    :param rdtype: DNS record type
    :param method: gai (getaddrinfo()), pydns, dig, drill, host, nslookup or auto (default)
    :param servers: (list of) server(s) to try in-order
    :param timeout: query timeout or a valiant approximation of that
    :param secure: return only DNSSEC secured response
    :param walk: Walk the DNS upwards looking for the record type or name/recordtype if walk='name'.
    :param walk_tld: Include the top-level domain in the walk
    :return: [] of records
    """
    rdtype = rdtype.upper()
    qargs = {
        "method": method,
        "servers": servers,
        "timeout": timeout,
        "walk": walk,
        "walk_tld": walk_tld,
        "secure": secure,
    }

    if rdtype == "PTR" and not name.endswith("arpa"):
        name = ptr_name(name)

    if rdtype == "SPF":
        # 'SPF' has become a regular 'TXT' again
        qres = [
            answer
            for answer in lookup(name, "TXT", **qargs)
            if answer.startswith("v=spf")
        ]
        if not qres:
            qres = lookup(name, rdtype, **qargs)
    else:
        qres = lookup(name, rdtype, **qargs)

    rec_map = {
        "A": a_rec,
        "AAAA": aaaa_rec,
        "CAA": caa_rec,
        "MX": mx_rec,
        "SOA": soa_rec,
        "SPF": spf_rec,
        "SRV": srv_rec,
        "SSHFP": sshfp_rec,
        "TLSA": tlsa_rec,
    }

    if not qres or rdtype not in rec_map:
        return qres
    elif rdtype in ("A", "AAAA", "SSHFP", "TLSA"):
        res = [rec_map[rdtype](res) for res in qres]
    elif rdtype in ("SOA", "SPF"):
        res = rec_map[rdtype](qres[0])
    else:
        res = rec_map[rdtype](qres)

    return res


def host(name, ip4=True, ip6=True, **kwargs):
    """
    Return a list of addresses for name

    ip6:
        Return IPv6 addresses
    ip4:
        Return IPv4 addresses

    the rest is passed on to lookup()
    """
    res = {}
    if ip6:
        ip6 = lookup(name, "AAAA", **kwargs)
        if ip6:
            res["ip6"] = ip6
    if ip4:
        ip4 = lookup(name, "A", **kwargs)
        if ip4:
            res["ip4"] = ip4

    return res


def a_rec(rdata):
    """
    Validate and parse DNS record data for an A record
    :param rdata: DNS record data
    :return: { 'address': ip }
    """
    rschema = OrderedDict((("address", ipaddress.IPv4Address),))
    return _data2rec(rschema, rdata)


def aaaa_rec(rdata):
    """
    Validate and parse DNS record data for an AAAA record
    :param rdata: DNS record data
    :return: { 'address': ip }
    """
    rschema = OrderedDict((("address", ipaddress.IPv6Address),))
    return _data2rec(rschema, rdata)


def caa_rec(rdatas):
    """
    Validate and parse DNS record data for a CAA record
    :param rdata: DNS record data
    :return: dict w/fields
    """
    rschema = OrderedDict(
        (
            ("flags", lambda flag: ["critical"] if int(flag) > 0 else []),
            ("tag", RFC.CAA_TAGS),
            ("value", lambda val: val.strip("',\"")),
        )
    )

    res = _data2rec_group(rschema, rdatas, "tag")

    for tag in ("issue", "issuewild"):
        tag_res = res.get(tag, False)
        if not tag_res:
            continue
        for idx, val in enumerate(tag_res):
            if ";" not in val:
                continue
            val, params = val.split(";", 1)
            params = dict(param.split("=") for param in shlex.split(params))
            tag_res[idx] = {val: params}

    return res


def mx_data(target, preference=10):
    """
    Generate MX record data
    :param target: server
    :param preference: preference number
    :return: DNS record data
    """
    return _rec2data(int(preference), target)


def mx_rec(rdatas):
    """
    Validate and parse DNS record data for MX record(s)
    :param rdata: DNS record data
    :return: dict w/fields
    """
    rschema = OrderedDict((("preference", int), ("name", str),))
    return _data2rec_group(rschema, rdatas, "preference")


def ptr_name(rdata):
    """
    Return PTR name of given IP
    :param rdata: IP address
    :return: PTR record name
    """
    try:
        return ipaddress.ip_address(rdata).reverse_pointer
    except ValueError:
        log.error("Unable to generate PTR record; %s is not a valid IP address", rdata)
        return False


def soa_rec(rdata):
    """
    Validate and parse DNS record data for SOA record(s)
    :param rdata: DNS record data
    :return: dict w/fields
    """
    rschema = OrderedDict(
        (
            ("mname", str),
            ("rname", str),
            ("serial", int),
            ("refresh", int),
            ("retry", int),
            ("expire", int),
            ("minimum", int),
        )
    )
    return _data2rec(rschema, rdata)


def spf_rec(rdata):
    """
    Validate and parse DNS record data for SPF record(s)
    :param rdata: DNS record data
    :return: dict w/fields
    """
    spf_fields = rdata.split(" ")
    if not spf_fields.pop(0).startswith("v=spf"):
        raise ValueError("Not an SPF record")

    res = OrderedDict()
    mods = set()
    for mech_spec in spf_fields:
        if mech_spec.startswith(("exp", "redirect")):
            # It's a modifier
            mod, val = mech_spec.split("=", 1)
            if mod in mods:
                raise KeyError("Modifier {0} can only appear once".format(mod))

            mods.add(mod)
            continue

            # TODO: Should be in something intelligent like an SPF_get
            # if mod == 'exp':
            #     res[mod] = lookup(val, 'TXT', **qargs)
            #     continue
            # elif mod == 'redirect':
            #     return query(val, 'SPF', **qargs)

        mech = {}
        if mech_spec[0] in ("+", "-", "~", "?"):
            mech["qualifier"] = mech_spec[0]
            mech_spec = mech_spec[1:]

        if ":" in mech_spec:
            mech_spec, val = mech_spec.split(":", 1)
        elif "/" in mech_spec:
            idx = mech_spec.find("/")
            mech_spec = mech_spec[0:idx]
            val = mech_spec[idx:]
        else:
            val = None

        res[mech_spec] = mech
        if not val:
            continue
        elif mech_spec in ("ip4", "ip6"):
            val = ipaddress.ip_interface(val)
            assert val.version == int(mech_spec[-1])

        mech["value"] = val

    return res


def srv_data(target, port, prio=10, weight=10):
    """
    Generate SRV record data
    :param target:
    :param port:
    :param prio:
    :param weight:
    :return:
    """
    return _rec2data(prio, weight, port, target)


def srv_name(svc, proto="tcp", domain=None):
    """
    Generate SRV record name
    :param svc: ldap, 389 etc
    :param proto: tcp, udp, sctp etc.
    :param domain: name to append
    :return:
    """
    proto = RFC.validate(proto, RFC.SRV_PROTO)
    if isinstance(svc, int) or svc.isdigit():
        svc = _to_port(svc)

    if domain:
        domain = "." + domain
    return "_{0}._{1}{2}".format(svc, proto, domain)


def srv_rec(rdatas):
    """
    Validate and parse DNS record data for SRV record(s)
    :param rdata: DNS record data
    :return: dict w/fields
    """
    rschema = OrderedDict(
        (("prio", int), ("weight", int), ("port", _to_port), ("name", str),)
    )
    return _data2rec_group(rschema, rdatas, "prio")


def sshfp_data(key_t, hash_t, pub):
    """
    Generate an SSHFP record
    :param key_t: rsa/dsa/ecdsa/ed25519
    :param hash_t: sha1/sha256
    :param pub: the SSH public key
    """
    key_t = RFC.validate(key_t, RFC.SSHFP_ALGO, "in")
    hash_t = RFC.validate(hash_t, RFC.SSHFP_HASH)

    hasher = hashlib.new(hash_t)
    hasher.update(base64.b64decode(pub))
    ssh_fp = hasher.hexdigest()

    return _rec2data(key_t, hash_t, ssh_fp)


def sshfp_rec(rdata):
    """
    Validate and parse DNS record data for TLSA record(s)
    :param rdata: DNS record data
    :return: dict w/fields
    """
    rschema = OrderedDict(
        (
            ("algorithm", RFC.SSHFP_ALGO),
            ("fp_hash", RFC.SSHFP_HASH),
            (
                "fingerprint",
                lambda val: val.lower(),
            ),  # resolvers are inconsistent on this one
        )
    )

    return _data2rec(rschema, rdata)


def tlsa_data(pub, usage, selector, matching):
    """
    Generate a TLSA rec
    :param pub: Pub key in PEM format
    :param usage:
    :param selector:
    :param matching:
    :return: TLSA data portion
    """
    usage = RFC.validate(usage, RFC.TLSA_USAGE)
    selector = RFC.validate(selector, RFC.TLSA_SELECT)
    matching = RFC.validate(matching, RFC.TLSA_MATCHING)

    pub = ssl.PEM_cert_to_DER_cert(pub.strip())
    if matching == 0:
        cert_fp = binascii.b2a_hex(pub)
    else:
        hasher = hashlib.new(RFC.TLSA_MATCHING[matching])
        hasher.update(pub)
        cert_fp = hasher.hexdigest()

    return _rec2data(usage, selector, matching, cert_fp)


def tlsa_rec(rdata):
    """
    Validate and parse DNS record data for TLSA record(s)
    :param rdata: DNS record data
    :return: dict w/fields
    """
    rschema = OrderedDict(
        (
            ("usage", RFC.TLSA_USAGE),
            ("selector", RFC.TLSA_SELECT),
            ("matching", RFC.TLSA_MATCHING),
            ("pub", str),
        )
    )

    return _data2rec(rschema, rdata)


def service(svc, proto="tcp", domain=None, walk=False, secure=None):
    """
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
    """
    qres = query(srv_name(svc, proto, domain), "SRV", walk=walk, secure=secure)
    if not qres:
        return False

    res = []
    for _, recs in qres.items():
        res.append(_weighted_order(recs))

    return res


def services(services_file="/etc/services"):
    """
    Parse through system-known services
    :return: {
        'svc': [
          {  'port': port
             'proto': proto,
             'desc': comment
          },
        ],
    }
    """
    res = {}
    with salt.utils.files.fopen(services_file, "r") as svc_defs:
        for svc_def in svc_defs.readlines():
            svc_def = salt.utils.stringutils.to_unicode(svc_def.strip())
            if not svc_def or svc_def.startswith("#"):
                continue
            elif "#" in svc_def:
                svc_def, comment = svc_def.split("#", 1)
                comment = comment.strip()
            else:
                comment = None
            svc_def = svc_def.split()

            port, proto = svc_def.pop(1).split("/")
            port = int(port)

            for name in svc_def:
                svc_res = res.get(name, {})
                pp_res = svc_res.get(port, False)
                if not pp_res:
                    svc = {
                        "port": port,
                        "proto": proto,
                    }
                    if comment:
                        svc["desc"] = comment
                    svc_res[port] = svc
                else:
                    curr_proto = pp_res["proto"]
                    if isinstance(curr_proto, (list, tuple)):
                        curr_proto.append(proto)
                    else:
                        pp_res["proto"] = [curr_proto, proto]

                    curr_desc = pp_res.get("desc", False)
                    if comment:
                        if not curr_desc:
                            pp_res["desc"] = comment
                        elif comment != curr_desc:
                            pp_res["desc"] = "{0}, {1}".format(curr_desc, comment)
                res[name] = svc_res

    for svc, data in res.items():
        if len(data) == 1:
            res[svc] = data.values().pop()
            continue
        else:
            res[svc] = list(data.values())

    return res


def parse_resolv(src="/etc/resolv.conf"):
    """
    Parse a resolver configuration file (traditionally /etc/resolv.conf)
    """

    nameservers = []
    ip4_nameservers = []
    ip6_nameservers = []
    search = []
    sortlist = []
    domain = ""
    options = []

    try:
        with salt.utils.files.fopen(src) as src_file:
            # pylint: disable=too-many-nested-blocks
            for line in src_file:
                line = salt.utils.stringutils.to_unicode(line).strip().split()

                try:
                    (directive, arg) = (line[0].lower(), line[1:])
                    # Drop everything after # or ; (comments)
                    arg = list(
                        itertools.takewhile(lambda x: x[0] not in ("#", ";"), arg)
                    )
                    if directive == "nameserver":
                        addr = arg[0]
                        try:
                            ip_addr = ipaddress.ip_address(addr)
                            version = ip_addr.version
                            ip_addr = str(ip_addr)
                            if ip_addr not in nameservers:
                                nameservers.append(ip_addr)
                            if version == 4 and ip_addr not in ip4_nameservers:
                                ip4_nameservers.append(ip_addr)
                            elif version == 6 and ip_addr not in ip6_nameservers:
                                ip6_nameservers.append(ip_addr)
                        except ValueError as exc:
                            log.error("%s: %s", src, exc)
                    elif directive == "domain":
                        domain = arg[0]
                    elif directive == "search":
                        search = arg
                    elif directive == "sortlist":
                        # A sortlist is specified by IP address netmask pairs.
                        # The netmask is optional and defaults to the natural
                        # netmask of the net. The IP address and optional
                        # network pairs are separated by slashes.
                        for ip_raw in arg:
                            try:
                                ip_net = ipaddress.ip_network(ip_raw)
                            except ValueError as exc:
                                log.error("%s: %s", src, exc)
                            else:
                                if "/" not in ip_raw:
                                    # No netmask has been provided, guess
                                    # the "natural" one
                                    if ip_net.version == 4:
                                        ip_addr = six.text_type(ip_net.network_address)
                                        # pylint: disable=protected-access
                                        mask = salt.utils.network.natural_ipv4_netmask(
                                            ip_addr
                                        )
                                        ip_net = ipaddress.ip_network(
                                            "{0}{1}".format(ip_addr, mask), strict=False
                                        )
                                    if ip_net.version == 6:
                                        # TODO
                                        pass

                                if ip_net not in sortlist:
                                    sortlist.append(ip_net)
                    elif directive == "options":
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
            log.debug("%s: The domain and search keywords are mutually exclusive.", src)

        return {
            "nameservers": nameservers,
            "ip4_nameservers": ip4_nameservers,
            "ip6_nameservers": ip6_nameservers,
            "sortlist": [ip.with_netmask for ip in sortlist],
            "domain": domain,
            "search": search,
            "options": options,
        }
    except IOError:
        return {}
