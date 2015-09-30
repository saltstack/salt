# -*- coding: utf-8 -*-
'''
states for infoblox stuff
'''
from __future__ import absolute_import

# Import Python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    make sure the infoblox module is available
    '''
    return True if 'infoblox.get_record' in __salt__ else False


def present(name,
            value,
            record_type,
            dns_view,
            infoblox_server=None,
            infoblox_user=None,
            infoblox_password=None,
            infoblox_api_version='v1.4.2',
            sslVerify=True):
    '''
    Ensure a record exists

    name
        Name of the record

    value
        Value of the record

    record_type
        record type (host, a, cname, etc)

    dns_view
        DNS View

    infoblox_server
        infoblox server to connect to (will try pillar if not specified)

    infoblox_user
        username to use to connect to infoblox (will try pillar if not specified)

    infoblox_password
        password to use to connect to infoblox (will try pillar if not specified)

    verify_ssl
        verify SSL certificates
    '''
    record_type = record_type.lower()
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    records = __salt__['infoblox.get_record'](name,
                                              record_type,
                                              infoblox_server=infoblox_server,
                                              infoblox_user=infoblox_user,
                                              infoblox_password=infoblox_password,
                                              dns_view=dns_view,
                                              infoblox_api_version=infoblox_api_version,
                                              sslVerify=sslVerify)
    if records:
        #check records for updates
        for record in records:
            if record_type == 'cname':
                if record['Canonical Name'] != value:
                    if __opts__['test']:
                        ret['result'] = None
                        ret['comment'] = ' '.join([ret['comment'],
                                         'DNS {0} record {1} in view {2} will be update'.format(record_type,
                                                                                                name,
                                                                                                dns_view)])
                    else:
                        retval = __salt__['infoblox.update_record'](name,
                                                                    value,
                                                                    dns_view,
                                                                    record_type,
                                                                    infoblox_server=infoblox_server,
                                                                    infoblox_user=infoblox_user,
                                                                    infoblox_password=infoblox_password,
                                                                    infoblox_api_version=infoblox_api_version,
                                                                    sslVerify=sslVerify)
                        if retval:
                            if 'old' not in ret['changes']:
                                ret['changes']['old'] = []
                            if 'new' not in ret['changes']:
                                ret['changes']['new'] = []
                            ret['changes']['old'].append(record)
                            ret['changes']['new'].append(__salt__['infoblox.get_record'](name,
                                                                                         record_type,
                                                                                         infoblox_server=infoblox_server,
                                                                                         infoblox_user=infoblox_user,
                                                                                         infoblox_password=infoblox_password,
                                                                                         dns_view=dns_view,
                                                                                         infoblox_api_version=infoblox_api_version,
                                                                                         sslVerify=sslVerify))
                        else:
                            ret['result'] = False
                            return ret
    else:
        #no records
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ' '.join([ret['comment'],
                             'DNS {0} record {1} set to be added to view {2}'.format(record_type,
                                                                                     name,
                                                                                     dns_view)])
            return ret
        retval = __salt__['infoblox.add_record'](name,
                                                 value,
                                                 record_type,
                                                 dns_view,
                                                 infoblox_server=None,
                                                 infoblox_user=None,
                                                 infoblox_password=None,
                                                 infoblox_api_version='v1.4.2',
                                                 sslVerify=sslVerify)
        if retval:
            ret['result'] = True
            ret['changes']['old'] = None
            ret['changes']['new'] = __salt__['infoblox.get_record'](name,
                                                                    record_type,
                                                                    infoblox_server=infoblox_server,
                                                                    infoblox_user=infoblox_user,
                                                                    infoblox_password=infoblox_password,
                                                                    dns_view=dns_view,
                                                                    infoblox_api_version=infoblox_api_version,
                                                                    sslVerify=sslVerify)
    return ret


def absent(name,
           record_type,
           dns_view,
           infoblox_server=None,
           infoblox_user=None,
           infoblox_password=None,
           infoblox_api_version='v1.4.2',
           sslVerify=True):
    '''
    Ensure a record does not exists

    name
        Name of the record
    record_type
        record type (host, a, cname, etc)
    dns_view
        DNS View
    infoblox_server
        infoblox server to connect to (will try pillar if not specified)
    infoblox_user
        username to use to connect to infoblox (will try pillar if not specified)
    infoblox_password
        password to use to connect to infoblox (will try pillar if not specified)
    verify_ssl
        verify SSL certificates

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    record = __salt__['infoblox.get_record'](name,
                                             record_type,
                                             infoblox_server=infoblox_server,
                                             infoblox_user=infoblox_user,
                                             infoblox_password=infoblox_password,
                                             dns_view=dns_view,
                                             infoblox_api_version=infoblox_api_version,
                                             sslVerify=sslVerify)
    if record:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ' '.join([ret['comment'],
                             'DNS {0} record {1} in view {2} will be removed'.format(record_type,
                                                                                     name,
                                                                                     dns_view)])
        else:
            retval = __salt__['infoblox.delete_record'](name,
                                                        dns_view,
                                                        record_type,
                                                        infoblox_server=infoblox_server,
                                                        infoblox_user=infoblox_user,
                                                        infoblox_password=infoblox_password,
                                                        infoblox_api_version=infoblox_api_version,
                                                        sslVerify=sslVerify)
            if retval:
                if 'old' not in ret['changes']:
                    ret['changes']['old'] = []
                ret['changes']['new'] = None
                ret['changes']['old'].append(record)
            else:
                ret['result'] = False
                return ret
    else:
        #record not found
        ret['result'] = True
        ret['changes']['old'] = None
        ret['changes']['new'] = None
        ret['comment'] = 'DNS record does not exist'

    return ret
