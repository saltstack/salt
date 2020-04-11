# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Rod McKenzie (roderick.mckenzie@morganstanley.com)`
    :codeauthor: :email:`Alexandru Bleotu (alexandru.bleotu@morganstanley.com)`

    salt.config.schemas.vcenter
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    VCenter configuration schemas
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from salt.utils.schema import ArrayItem, IntegerItem, Schema, StringItem


class VCenterEntitySchema(Schema):
    """
    Entity Schema for a VCenter.
    """

    title = "VCenter Entity Schema"
    description = "VCenter entity schema"
    type = StringItem(
        title="Type",
        description="Specifies the entity type",
        required=True,
        enum=["vcenter"],
    )

    vcenter = StringItem(
        title="vCenter", description="Specifies the vcenter hostname", required=True
    )


class VCenterProxySchema(Schema):
    """
    Schema for the configuration for the proxy to connect to a VCenter.
    """

    title = "VCenter Proxy Connection Schema"
    description = "Schema that describes the connection to a VCenter"
    additional_properties = False
    proxytype = StringItem(required=True, enum=["vcenter"])
    vcenter = StringItem(required=True, pattern=r"[^\s]+")
    mechanism = StringItem(required=True, enum=["userpass", "sspi"])
    username = StringItem()
    passwords = ArrayItem(min_items=1, items=StringItem(), unique_items=True)

    domain = StringItem()
    principal = StringItem(default="host")
    protocol = StringItem(default="https")
    port = IntegerItem(minimum=1)
