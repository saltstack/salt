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
from salt.utils.schema import (DefinitionsSchema,
                               Schema,
                               ComplexSchemaItem,
                               ArrayItem,
                               IntegerItem,
                               BooleanItem,
                               StringItem)


class DiskGroupDiskIdItem(ComplexSchemaItem):
    '''
    Schema item of a ESXi host disk group containg disk ids
    '''

    title = 'Diskgroup Disk Id Item'
    description = 'ESXi host diskgroup item containing disk ids'


    cache_id = StringItem(
        title='Cache Disk Id',
        description='Specifies the id of the cache disk',
        pattern=r'[^\s]+')

    capacity_ids = ArrayItem(
        title='Capacity Disk Ids',
        description='Array with the ids of the capacity disks',
        items=StringItem(pattern=r'[^\s]+'),
        min_items=1)


class DiskGroupsDiskIdSchema(DefinitionsSchema):
    '''
    Schema of ESXi host diskgroups containing disk ids
    '''

    title = 'Diskgroups Disk Id Schema'
    description = 'ESXi host diskgroup schema containing disk ids'
    diskgroups = ArrayItem(
        title='DiskGroups',
        description='List of disk groups in an ESXi host',
        min_items = 1,
        items=DiskGroupDiskIdItem(),
        required=True)


class SimpleHostCacheSchema(Schema):
    '''
    Simplified Schema of ESXi host cache
    '''

    title = 'Simple Host Cache Schema'
    description = 'Simplified schema of the ESXi host cache'
    enabled = BooleanItem(
        title='Enabled',
        required=True)
    datastore_name = StringItem(title='Datastore Name',
                                required=True)
    swap_size_MiB = IntegerItem(title='Host cache swap size in MiB',
                                minimum=1)


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
