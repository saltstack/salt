"""
    :codeauthor: :email:`Alexandru Bleotu (alexandru.bleotu@morganstanley.com)`


    salt.config.schemas.esxdatacenter
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ESX Datacenter configuration schemas
"""

from salt.utils.schema import ArrayItem, IntegerItem, Schema, StringItem


class EsxdatacenterProxySchema(Schema):
    """
    Schema of the esxdatacenter proxy input
    """

    title = "Esxdatacenter Proxy Schema"
    description = "Esxdatacenter proxy schema"
    additional_properties = False
    proxytype = StringItem(required=True, enum=["esxdatacenter"])
    vcenter = StringItem(required=True, pattern=r"[^\s]+")
    datacenter = StringItem(required=True)
    mechanism = StringItem(required=True, enum=["userpass", "sspi"])
    username = StringItem()
    passwords = ArrayItem(min_items=1, items=StringItem(), unique_items=True)
    # TODO Should be changed when anyOf is supported for schemas
    domain = StringItem()
    principal = StringItem()
    protocol = StringItem()
    port = IntegerItem(minimum=1)
