'''
Support for RFC 2136 dynamic DNS updates.
Requires dnspython module.
'''
# Import python libs
import logging


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


def add_host(zone, name, ttl, ip, nameserver='127.0.0.1', replace=True):
    '''
    Add, replace, or update the A and PTR (reverse) records for a host.

    Note: This function attempts to add reverse records to each
    possible zone, beginning with the least specific.

    CLI Example::
        
        salt ns1 ddns.add_host example.com host1 60 10.1.1.1
    '''

    a = update(zone, name, ttl, 'A', ip, nameserver, replace)
    if a is False:
        return False
    
    fqdn = '{0}.{1}.'.format(name, zone)
    zone = 'in-addr.arpa.'
    parts = ip.split('.')
    ptr = False

    # Iterate over possible reverse zones, starting at the
    # least specific.
    while len(parts) > 1:
        zone = '{0}.{1}'.format(parts.pop(0), zone)
        name = ip.replace('{0}.'.format('.'.join(parts)), '')
        ptr = update(zone, name, ttl, 'PTR', fqdn, nameserver, replace)
        if ptr:
            return True
        elif ptr is None:
            return a
    return False


def delete_host(zone, name, nameserver='127.0.0.1'):
    '''
    Delete the A and PTR (reverse) records for a host.

    Note: This attempts to delete reverse records from each
    possible zone, beginning with the least specific.

    CLI Example::
        
        salt ns1 ddns.delete_host example.com host1
    '''

    fqdn = '{}.{}'.format(name, zone)
    request = dns.message.make_query(fqdn, 'A')
    answer = dns.query.udp(request, nameserver)
    try:
        ip = answer.answer[0].items[0].address
    except IndexError:
        ip = None

    a = delete(zone, name, 'A', nameserver=nameserver)
    if not ip:
        return a

    zone = 'in-addr.arpa.'
    parts = ip.split('.')
    ptr = False

    # Iterate over possible reverse zones, starting at the
    # least specific.
    while len(parts) > 1:
        zone = '{0}.{1}'.format(parts.pop(0), zone)
        name = ip.replace('{0}.'.format('.'.join(parts)), '')
        ptr = delete(zone, name, 'PTR', nameserver=nameserver)
        if ptr:
            return True
        elif ptr is None:
            return a
    return False


def update(zone, name, ttl, rdtype, data, nameserver='127.0.0.1', replace=False):
    '''
    Add, replace, or update a DNS record.
    nameserver must be an IP address and the minion running this module
    must have update privileges on that server.
    If replace is true, first deletes all records for this name and type.

    CLI Example::

        salt ns1 ddns.update example.com host1 60 A 10.0.0.1
    '''

    name = str(name)
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

    dns_update = dns.update.Update(zone)
    if is_update:
        dns_update.replace(name, ttl, rdata)
    else:
        dns_update.add(name, ttl, rdata)
    answer = dns.query.udp(dns_update, nameserver)
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

    dns_update = dns.update.Update(zone)

    if rdtype:
        rdtype = dns.rdatatype.from_text(rdtype)
        if data:
            rdata = dns.rdata.from_text(dns.rdataclass.IN, rdtype, data)
            dns_update.delete(name, rdata)
        else:
            dns_update.delete(name, rdtype)
    else:
        dns_update.delete(name)

    answer = dns.query.udp(dns_update, nameserver)
    if answer.rcode() > 0:
        return False
    return True
