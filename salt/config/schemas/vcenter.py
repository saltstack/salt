# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rod McKenzie (roderick.mckenzie@morganstanley.com)`
    :codeauthor: :email:`Alexandru Bleotu (alexandru.bleotu@morganstanley.com)`

    salt.config.schemas.vcenter
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    VCenter configuration schemas
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
from salt.utils.schema import (Schema,
                               StringItem)


class VCenterEntitySchema(Schema):
    '''
    Entity Schema for a VCenter.
    '''
    title = 'VCenter Entity Schema'
    description = 'VCenter entity schema'
    type = StringItem(title='Type',
                      description='Specifies the entity type',
                      required=True,
                      enum=['vcenter'])

    vcenter = StringItem(title='vCenter',
                         description='Specifies the vcenter hostname',
                         required=True)
