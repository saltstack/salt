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
                               DictItem,
                               IntegerItem,
                               BooleanItem,
                               StringItem,
                               OneOfItem)


class VMwareScsiAddressItem(StringItem):
    pattern = r'vmhba\d+:C\d+:T\d+:L\d+'


class DiskGroupDiskScsiAddressItem(ComplexSchemaItem):
    '''
    Schema item of a ESXi host disk group containing disk SCSI addresses
    '''

    title = 'Diskgroup Disk Scsi Address Item'
    description = 'ESXi host diskgroup item containing disk SCSI addresses'


    cache_scsi_addr = VMwareScsiAddressItem(
        title='Cache Disk Scsi Address',
        description='Specifies the SCSI address of the cache disk',
        required=True)

    capacity_scsi_addrs = ArrayItem(
        title='Capacity Scsi Addresses',
        description='Array with the SCSI addresses of the capacity disks',
        items=VMwareScsiAddressItem(),
        min_items=1)


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


class DiskGroupsDiskScsiAddressSchema(DefinitionsSchema):
    '''
    Schema of ESXi host diskgroups containing disk SCSI addresses
    '''

    title = 'Diskgroups Disk Scsi Address Schema'
    description = 'ESXi host diskgroup schema containing disk SCSI addresses'
    disk_groups = ArrayItem(
        title='Diskgroups',
        description='List of diskgroups in an ESXi host',
        min_items = 1,
        items=DiskGroupDiskScsiAddressItem(),
        required=True)
    erase_disks = BooleanItem(
        title='Erase Diskgroup Disks',
        required=True)


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
