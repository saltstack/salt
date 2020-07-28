"""
Various XML utilities
"""

# Import Python libs

import re
from xml.etree import ElementTree


def _conv_name(x):
    """
    If this XML tree has an xmlns attribute, then etree will add it
    to the beginning of the tag, like: "{http://path}tag".
    """
    if "}" in x:
        comps = x.split("}")
        name = comps[1]
        return name
    return x


def _to_dict(xmltree):
    """
    Converts an XML ElementTree to a dictionary that only contains items.
    This is the default behavior in version 2017.7. This will default to prevent
    unexpected parsing issues on modules dependent on this.
    """
    # If this object has no children, the for..loop below will return nothing
    # for it, so just return a single dict representing it.
    if not xmltree:
        name = _conv_name(xmltree.tag)
        return {name: xmltree.text}

    xmldict = {}
    for item in xmltree:
        name = _conv_name(item.tag)

        if name not in xmldict:
            if item:
                xmldict[name] = _to_dict(item)
            else:
                xmldict[name] = item.text
        else:
            # If a tag appears more than once in the same place, convert it to
            # a list. This may require that the caller watch for such a thing
            # to happen, and behave accordingly.
            if not isinstance(xmldict[name], list):
                xmldict[name] = [xmldict[name]]
            xmldict[name].append(_to_dict(item))
    return xmldict


def _to_full_dict(xmltree):
    """
    Returns the full XML dictionary including attributes.
    """
    xmldict = {}

    for attrName, attrValue in xmltree.attrib.items():
        xmldict[attrName] = attrValue

    if not xmltree:
        if not xmldict:
            # If we don't have attributes, we should return the value as a string
            # ex: <entry>test</entry>
            return xmltree.text
        elif xmltree.text:
            # XML allows for empty sets with attributes, so we need to make sure that capture this.
            # ex: <entry name="test"/>
            xmldict[_conv_name(xmltree.tag)] = xmltree.text

    for item in xmltree:
        name = _conv_name(item.tag)

        if name not in xmldict:
            xmldict[name] = _to_full_dict(item)
        else:
            # If a tag appears more than once in the same place, convert it to
            # a list. This may require that the caller watch for such a thing
            # to happen, and behave accordingly.
            if not isinstance(xmldict[name], list):
                xmldict[name] = [xmldict[name]]

            xmldict[name].append(_to_full_dict(item))

    return xmldict


def to_dict(xmltree, attr=False):
    """
    Convert an XML tree into a dict. The tree that is passed in must be an
    ElementTree object.
    Args:
        xmltree: An ElementTree object.
        attr: If true, attributes will be parsed. If false, they will be ignored.

    """
    if attr:
        return _to_full_dict(xmltree)
    else:
        return _to_dict(xmltree)


def get_xml_node(node, xpath):
    """
    Get an XML node using a path (super simple xpath showing complete node ancestry).
    This also creates the missing nodes.

    The supported XPath can contain elements filtering using [@attr='value'].

    Args:
        node: an Element object
        xpath: simple XPath to look for.
    """
    if not xpath.startswith("./"):
        xpath = "./{}".format(xpath)
    res = node.find(xpath)
    if res is None:
        parent_xpath = xpath[: xpath.rfind("/")]
        parent = node.find(parent_xpath)
        if parent is None:
            parent = get_xml_node(node, parent_xpath)
        segment = xpath[xpath.rfind("/") + 1 :]
        # We may have [] filter in the segment
        matcher = re.match(
            r"""(?P<tag>[^[]+)(?:\[@(?P<attr>\w+)=["'](?P<value>[^"']+)["']])?""",
            segment,
        )
        attrib = (
            {matcher.group("attr"): matcher.group("value")}
            if matcher.group("attr") and matcher.group("value")
            else {}
        )
        res = ElementTree.SubElement(parent, matcher.group("tag"), attrib)
    return res
