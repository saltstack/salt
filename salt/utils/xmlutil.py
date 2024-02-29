"""
Various XML utilities
"""

import re
import string  # pylint: disable=deprecated-module
from xml.etree import ElementTree

import salt.utils.data


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
        xpath = f"./{xpath}"
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


def set_node_text(node, value):
    """
    Function to use in the ``set`` value in the :py:func:`change_xml` mapping items to set the text.
    This is the default.

    :param node: the node to set the text to
    :param value: the value to set
    """
    node.text = str(value)


def clean_node(parent_map, node, ignored=None):
    """
    Remove the node from its parent if it has no attribute but the ignored ones, no text and no child.
    Recursively called up to the document root to ensure no empty node is left.

    :param parent_map: dictionary mapping each node to its parent
    :param node: the node to clean
    :param ignored: a list of ignored attributes.
    :return: True if anything has been removed, False otherwise
    """
    has_text = node.text is not None and node.text.strip()
    parent = parent_map.get(node)
    removed = False
    if (
        len(node.attrib.keys() - (ignored or [])) == 0
        and not list(node)
        and not has_text
        and parent
    ):
        parent.remove(node)
        removed = True
    # Clean parent nodes if needed
    if parent is not None:
        parent_cleaned = clean_node(parent_map, parent, ignored)
        removed = removed or parent_cleaned
    return removed


def del_text(parent_map, node):
    """
    Function to use as ``del`` value in the :py:func:`change_xml` mapping items to remove the text.
    This is the default function.
    Calls :py:func:`clean_node` before returning.
    """
    parent = parent_map[node]
    parent.remove(node)
    clean_node(parent, node)
    return True


def del_attribute(attribute, ignored=None):
    """
    Helper returning a function to use as ``del`` value in the :py:func:`change_xml` mapping items to
    remove an attribute.

    The generated function calls :py:func:`clean_node` before returning.

    :param attribute: the name of the attribute to remove
    :param ignored: the list of attributes to ignore during the cleanup

    :return: the function called by :py:func:`change_xml`.
    """

    def _do_delete(parent_map, node):
        if attribute not in node.keys():
            return False
        node.attrib.pop(attribute)
        clean_node(parent_map, node, ignored)
        return True

    return _do_delete


def attribute(path, xpath, attr_name, ignored=None, convert=None):
    """
    Helper function creating a change_xml mapping entry for a text XML attribute.

    :param path: the path to the value in the data
    :param xpath: the xpath to the node holding the attribute
    :param attr_name: the attribute name
    :param ignored: the list of attributes to ignore when cleaning up the node
    :param convert: a function used to convert the value
    """
    entry = {
        "path": path,
        "xpath": xpath,
        "get": lambda n: n.get(attr_name),
        "set": lambda n, v: n.set(attr_name, str(v)),
        "del": salt.utils.xmlutil.del_attribute(attr_name, ignored),
    }
    if convert:
        entry["convert"] = convert
    return entry


def int_attribute(path, xpath, attr_name, ignored=None):
    """
    Helper function creating a change_xml mapping entry for a text XML integer attribute.

    :param path: the path to the value in the data
    :param xpath: the xpath to the node holding the attribute
    :param attr_name: the attribute name
    :param ignored: the list of attributes to ignore when cleaning up the node
    """
    return {
        "path": path,
        "xpath": xpath,
        "get": lambda n: int(n.get(attr_name)) if n.get(attr_name) else None,
        "set": lambda n, v: n.set(attr_name, str(v)),
        "del": salt.utils.xmlutil.del_attribute(attr_name, ignored),
    }


def change_xml(doc, data, mapping):
    """
    Change an XML ElementTree document according.

    :param doc: the ElementTree parsed XML document to modify
    :param data: the dictionary of values used to modify the XML.
    :param mapping: a list of items describing how to modify the XML document.
        Each item is a dictionary containing the following keys:

        .. glossary::
            path
                the path to the value to set or remove in the ``data`` parameter.
                See :py:func:`salt.utils.data.get_value <salt.utils.data.get_value>` for the format
                of the value.

            xpath
                Simplified XPath expression used to locate the change in the XML tree.
                See :py:func:`get_xml_node` documentation for details on the supported XPath syntax

            get
                function gettin the value from the XML.
                Takes a single parameter for the XML node found by the XPath expression.
                Default returns the node text value.
                This may be used to return an attribute or to perform value transformation.

            set
                function setting the value in the XML.
                Takes two parameters for the XML node and the value to set.
                Default is to set the text value.

            del
                function deleting the value in the XML.
                Takes two parameters for the parent node and the node matched by the XPath.
                Returns True if anything was removed, False otherwise.
                Default is to remove the text value.
                More cleanup may be performed, see the :py:func:`clean_node` function for details.

            convert
                function modifying the user-provided value right before comparing it with the one from the XML.
                Takes the value as single parameter.
                Default is to apply no conversion.

    :return: ``True`` if the XML has been modified, ``False`` otherwise.
    """
    need_update = False
    for param in mapping:
        # Get the value from the function parameter using the path-like description
        # Using an empty list as a default value will cause values not provided by the user
        # to be left untouched, as opposed to explicit None unsetting the value
        values = salt.utils.data.get_value(data, param["path"], [])
        xpath = param["xpath"]
        # Prepend the xpath with ./ to handle the root more easily
        if not xpath.startswith("./"):
            xpath = f"./{xpath}"

        placeholders = [
            s[1:-1]
            for s in param["path"].split(":")
            if s.startswith("{") and s.endswith("}")
        ]

        ctx = {placeholder: "$$$" for placeholder in placeholders}
        all_nodes_xpath = string.Template(xpath).substitute(ctx)
        all_nodes_xpath = re.sub(
            r"""(?:=['"]\$\$\$["'])|(?:\[\$\$\$\])""", "", all_nodes_xpath
        )

        # Store the nodes that are not removed for later cleanup
        kept_nodes = set()

        for value_item in values:
            new_value = value_item["value"]

            # Only handle simple type values. Use multiple entries or a custom get for dict or lists
            if isinstance(new_value, list) or isinstance(new_value, dict):
                continue

            if new_value is not None:
                # We need to increment ids from arrays since xpath starts at 1
                converters = {
                    p: ((lambda n: n + 1) if f"[${p}]" in xpath else (lambda n: n))
                    for p in placeholders
                }
                ctx = {
                    placeholder: converters[placeholder](
                        value_item.get(placeholder, "")
                    )
                    for placeholder in placeholders
                }
                node_xpath = string.Template(xpath).substitute(ctx)
                node = get_xml_node(doc, node_xpath)

                kept_nodes.add(node)

                get_fn = param.get("get", lambda n: n.text)
                set_fn = param.get("set", set_node_text)
                current_value = get_fn(node)

                # Do we need to apply some conversion to the user-provided value?
                convert_fn = param.get("convert")
                if convert_fn:
                    new_value = convert_fn(new_value)

                # Allow custom comparison. Can be useful for almost equal numeric values
                compare_fn = param.get("equals", lambda o, n: str(o) == str(n))
                if not compare_fn(current_value, new_value):
                    set_fn(node, new_value)
                    need_update = True
            else:
                nodes = doc.findall(all_nodes_xpath)
                del_fn = param.get("del", del_text)
                parent_map = {c: p for p in doc.iter() for c in p}
                for node in nodes:
                    deleted = del_fn(parent_map, node)
                    need_update = need_update or deleted

        # Clean the left over XML elements if there were placeholders
        if placeholders and [v for v in values if v.get("value") != []]:
            all_nodes = set(doc.findall(all_nodes_xpath))
            to_remove = all_nodes - kept_nodes
            del_fn = param.get("del", del_text)
            parent_map = {c: p for p in doc.iter() for c in p}
            for node in to_remove:
                deleted = del_fn(parent_map, node)
                need_update = need_update or deleted
    return need_update


def strip_spaces(node):
    """
    Remove all spaces and line breaks before and after nodes.
    This helps comparing XML trees.

    :param node: the XML node to remove blanks from
    :return: the node
    """

    if node.tail is not None:
        node.tail = node.tail.strip(" \t\n")
    if node.text is not None:
        node.text = node.text.strip(" \t\n")
    try:
        for child in node:
            strip_spaces(child)
    except RecursionError:
        raise Exception("Failed to recurse on the node")

    return node


def element_to_str(node):
    """
    Serialize an XML node into a string
    """
    return salt.utils.stringutils.to_str(ElementTree.tostring(node))
