# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu (alexandru.bleotu@morganstanley.com)`


    salt.config.schemas.esxi
    ~~~~~~~~~~~~~~~~~~~~~~~~

    ESXi host configuration schemas
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
from salt.utils.schema import (Schema,
                               ArrayItem,
                               IntegerItem,
                               StringItem)


class EsxiProxySchema(Schema):
    '''
    Schema of the esxi proxy input
    '''

    title = 'Esxi Proxy Schema'
    description = 'Esxi proxy schema'
    additional_properties = False
    proxytype = StringItem(required=True,
                           enum=['esxi'])
    host = StringItem(pattern=r'[^\s]+') # Used when connecting directly
    vcenter = StringItem(pattern=r'[^\s]+') # Used when connecting via a vCenter
    esxi_host = StringItem()
    username = StringItem()
    passwords = ArrayItem(min_items=1,
                          items=StringItem(),
                          unique_items=True)
    mechanism = StringItem(enum=['userpass', 'sspi'])
    # TODO Should be changed when anyOf is supported for schemas
    domain = StringItem()
    principal = StringItem()
    protocol = StringItem()
    port = IntegerItem(minimum=1)
