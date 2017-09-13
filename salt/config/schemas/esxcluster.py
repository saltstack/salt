# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu (alexandru.bleotu@morganstanley.com)`


    salt.config.schemas.esxcluster
    ~~~~~~~~~~~~~~~~~~~~~~~

    ESX Cluster configuration schemas
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
from salt.utils.schema import (Schema,
                               ArrayItem,
                               IntegerItem,
                               StringItem)


class EsxclusterProxySchema(Schema):
    '''
    Schema of the esxcluster proxy input
    '''

    title = 'Esxcluster Proxy Schema'
    description = 'Esxcluster proxy schema'
    additional_properties = False
    proxytype = StringItem(required=True,
                           enum=['esxcluster'])
    vcenter = StringItem(required=True, pattern=r'[^\s]+')
    datacenter = StringItem(required=True)
    cluster = StringItem(required=True)
    mechanism = StringItem(required=True, enum=['userpass', 'sspi'])
    username = StringItem()
    passwords = ArrayItem(min_items=1,
                          items=StringItem(),
                          unique_items=True)
    # TODO Should be changed when anyOf is supported for schemas
    domain = StringItem()
    principal = StringItem()
    protocol = StringItem()
    port = IntegerItem(minimum=1)
