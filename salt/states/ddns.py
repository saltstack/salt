# -*- coding: utf-8 -*-
'''
Dynamic DNS updates.
====================

Ensure a DNS record is present or absent utilizing RFC 2136
type dynamic updates. Requires dnspython module.

.. code-block:: yaml

    webserver:
      ddns.present:
        - zone: example.com
        - ttl: 60
'''


def __virtual__():
    return 'ddns' if 'ddns.update' in __salt__ else False


def present(name, zone, ttl, data, rdtype='A'):
    '''
    Ensures that the named DNS record is present with the given ttl.

    name
        The host portion of the DNS record, e.g., 'webserver'

    zone
        The zone to check/update

    ttl
        TTL for the record

    data
        Data for the DNS record. E.g., the IP addres for an A record.

    rdtype
        DNS resource type. Default 'A'.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = '{0} record "{1}" will be updated'.format(rdtype, name)
        return ret

    status = __salt__['ddns.update'](zone, name, ttl, rdtype, data)

    if status is None:
        ret['result'] = True
        ret['comment'] = '{0} record "{1}" already present with ttl of {2}'.format(
                rdtype, name, ttl)
    elif status:
        ret['result'] = True
        ret['comment'] = 'Updated {0} record for "{1}"'.format(rdtype, name)
        ret['changes'] = {'name': name,
                          'zone': zone,
                          'ttl': ttl,
                          'rdtype': rdtype,
                          'data': data
                         }
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to create or update {0} record for "{1}"'.format(rdtype, name)
    return ret


def absent(name, zone, data=None, rdtype=None):
    '''
    Ensures that the named DNS record is absent.

    name
        The host portion of the DNS record, e.g., 'webserver'

    zone
        The zone to check

    data
        Data for the DNS record. E.g., the IP addres for an A record. If omitted,
        all records matching name (and rdtype, if provided) will be purged.

    rdtype
        DNS resource type. If omitted, all types will be purged.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = '{0} record "{1}" will be deleted'.format(rdtype, name)
        return ret

    status = __salt__['ddns.delete'](zone, name, rdtype, data)

    if status is None:
        ret['result'] = True
        ret['comment'] = 'No matching DNS record(s) present'
    elif status:
        ret['result'] = True
        ret['comment'] = 'Deleted DNS record(s)'
        ret['changes'] = True
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to delete DNS record(s)'
    return ret
