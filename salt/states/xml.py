"""
XML Manager
===========

State management of XML files
"""

import logging

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if the XML execution module is available.
    """
    if "xml.get_value" in __salt__:
        return "xml"
    else:
        return False, "The xml execution module is not available"


def value_present(name, xpath, value, **kwargs):
    """
    .. versionadded:: 3000

    Manages a given XML file

    name : string
        The location of the XML file to manage, as an absolute path.

    xpath : string
        xpath location to manage

    value : string
        value to ensure present

    .. code-block:: yaml

        ensure_value_true:
          xml.value_present:
            - name: /tmp/test.xml
            - xpath: .//playwright[@id='1']
            - value: William Shakespeare
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if "test" not in kwargs:
        kwargs["test"] = __opts__.get("test", False)

    current_value = __salt__["xml.get_value"](name, xpath)
    if not current_value:
        ret["result"] = False
        ret["comment"] = f"xpath query {xpath} not found in {name}"
        return ret

    if current_value != value:
        if kwargs["test"]:
            ret["result"] = None
            ret["comment"] = f"{name} will be updated"
            ret["changes"] = {name: {"old": current_value, "new": value}}
        else:
            results = __salt__["xml.set_value"](name, xpath, value)
            ret["result"] = results
            ret["comment"] = f"{name} updated"
            ret["changes"] = {name: {"old": current_value, "new": value}}
    else:
        ret["comment"] = f"{value} is already present"

    return ret
