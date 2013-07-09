'''
Support for RFC 2136 dynamic DNS updates.
Requires dnspython module.
'''
# Import python libs
import logging

# Import salt libs
import salt.utils


log = logging.getLogger(__name__)


try:
    import dns.query
    import dns.update
    dns_support = True
except ImportError as e:
    dns_support = False

def __virtual__():
    '''
    Confirm dnspython is available.
    '''
    if dns_support:
        return 'ddns'
    return False


def update(zone, name, ttl, rdtype, data, nameserver='127.0.0.1', replace=False):
    '''
    Add, replace, or update a DNS record.
    nameserver must be an IP address and the minion running this module
    must have update priviledges on that server.
    If replace is true, first deletes all records for this name and type.

    CLI Example::

        salt ns1 ddns.update example.com host1 60 A 10.0.0.1
    '''
    fqdn = '{}.{}'.format(name, zone)
    request = dns.message.make_query(fqdn, rdtype)
    answer = dns.query.udp(request, nameserver)

    rdtype = dns.rdatatype.from_text(rdtype)
    rdata = dns.rdata.from_text(dns.rdataclass.IN, rdtype, data)
    
    is_update = False
    for rrset in answer.answer:
        if rdata in rrset.items:
            rr = rrset.items
            if ttl == rrset.ttl:
                if replace and (len(answer.answer) > 1
                        or len(rrset.items) > 1):
                    is_update = True
                    break
                return None
            is_update = True
            break

    update = dns.update.Update(zone)
    if is_update:
        update.replace(name, ttl, rdata)
    else:
        update.add(name, ttl, rdata)
    answer = dns.query.udp(update, nameserver)
    if answer.rcode() > 0:
        return False
    return True


def delete(zone, name, rdtype=None, data=None, nameserver='127.0.0.1'):
    '''
    Delete a DNS record.

    CLI Example::

        salt ns1 ddns.delete example.com host1 A
    '''
    fqdn = '{}.{}'.format(name, zone)
    request = dns.message.make_query(fqdn, (rdtype or 'ANY'))

    answer = dns.query.udp(request, nameserver)
    if not answer.answer:
        return None

    update = dns.update.Update(zone)

    if rdtype:
        rdtype = dns.rdatatype.from_text(rdtype)
        if data:
            rdata = dns.rdata.from_text(dns.rdataclass.IN, rdtype, data)
            update.delete(name, rdata)
        else:
            update.delete(name, rdtype)
    else:
        update.delete(name)

    answer = dns.query.udp(update, nameserver)
    if answer.rcode() > 0:
        return False
    return True
