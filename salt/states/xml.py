"""
XML Manager
===========

State management of XML files
"""
import copy
import difflib
import xml.etree.ElementTree as ET


def __virtual__():
    """
    Only load if the XML execution module is available.
    """
    if "xml.get_value" in __salt__:
        return "xml"
    else:
        return False, "The xml execution module is not available"


def _element_equal(original, new):
    return (
        new.tag == original.tag
        and new.attrib == original.attrib
        and new.text == original.text
        and new.tail == original.tail
        and len(new) == len(original)
    )


def _element_tree_equal(original, new):
    return _element_equal(original, new) and all(
        _element_tree_equal(original_child, new_child)
        for original_child, new_child in zip(original, new)
    )


def value_present(name, xpath, value, **kwargs):
    """
    .. versionadded:: 3000

    Manages a given XML file

    name
        The location of the XML file to manage, as an absolute path.

    xpath
        xpath location to manage

    value
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
        ret["comment"] = "xpath query {} not found in {}".format(xpath, name)
        return ret

    if current_value != value:
        if kwargs["test"]:
            ret["result"] = None
            ret["comment"] = "{} will be updated".format(name)
            ret["changes"] = {name: {"old": current_value, "new": value}}
        else:
            results = __salt__["xml.set_value"](name, xpath, value)
            ret["result"] = results
            ret["comment"] = "{} updated".format(name)
            ret["changes"] = {name: {"old": current_value, "new": value}}
    else:
        ret["comment"] = "{} is already present".format(value)

    return ret


def contains_tree(name, fragment, xpath=None):
    """
    .. versionadded:: NEXT_RELEASE

    Merge a block of XML into another, in a given file. This is used for
    ensuring a tree exists, or tweaking attributes of a well-known location in
    a config file. This state only matches tags as it merges fragments, so it
    does not work well (if at all) with list-style data.
    This will NOT merge text/tail nodes.

    name
        The location of the XML file to manage, as an absolute path.

    xpath
        optional xpath location under which to place the fragment. See
        https://docs.python.org/3/library/xml.etree.elementtree.html#example
        to see what syntax is supported.

    fragment
        XML fragment to create _under_ the location specified in `path`.
        The fragment must be valid XML. If the path already contains XML and
        the fragment's tags match, they will be merged -- the fragment's
        properties will overwrite any existing properties with the same key.
        This means attributes are merged, text, and tail values are replaced.

    .. code-block:: yaml

        ensure_tree_exists:
        xml.contains_tree:
            - name: /etc/data.xml # MUST already have valid XML.
            - fragment: |
                <people>
                  <artists active="true">
                    <authors />
                  </artists>
                </people>

        ensure_attribute_set:
        xml.contains_tree:
            - name: /etc/data.xml
            - xpath: people
            - fragment: |
                <artists active="false">  # overwrites 'active=true'
                  <authors />
                  <painters />
                </artists>

    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    fragment_root = ET.fromstring(fragment)
    tree = ET.parse(name)

    if xpath is not None:
        target_parent = target_parent.find(xpath)
    else:
        target_parent = tree.getroot()

    def _merge_or_append_elements(original, new):
        changeset = {}
        sub_element = original.find(new.tag)
        if sub_element is not None:
            # Make additions if needed
            if not new.attrib.items() <= sub_element.attrib.items():
                old_attrs = copy.copy(sub_element.attrib)
                sub_element.attrib.update(new.attrib)
                changeset["attrib"] = {
                    "new": str(sub_element.attrib),
                    "old": (old_attrs),
                }

            for index, new_child in enumerate(new):
                sub_changes = _merge_or_append_elements(sub_element, new_child)
                if sub_changes:
                    changeset["{}-{}".format(new_child.tag, index)] = sub_changes
        else:
            original.append(new)
            changeset[new.tag] = {"new": ET.tostring(original)}

        return changeset

    ret["changes"] = _merge_or_append_elements(target_parent, fragment_root)

    if ret["changes"]:
        ret["comment"] = "Changed XML file"
    else:
        ret["comment"] = "No XML elements changed"

    if not __opts__["test"]:
        tree.write(name)
        ret.result = True

    return ret


def contains_fragment(name, fragment, xpath=None, replace=False):
    """
    .. versionadded:: NEXT_RELEASE

    Manage a block of XML inside a given file

    name
        The location of the XML file to manage, as an absolute path.

    xpath
        optional xpath location under which to place the fragment. See
        https://docs.python.org/3/library/xml.etree.elementtree.html#example
        to see what syntax is supported.
        Defaults to the root element.

    fragment
        XML fragment to create _under_ the location specified in `path`.
        The fragment must be valid XML.

    replace
        When adding the fragment and no exact match can be found the state will
        either append the node, or replace it if this parameter is set to True.

    .. code-block:: yaml

        ensure_authors:
          xml.contains_fragment:
            - name: /etc/data.xml
            - xpath: people/artists
            - replace: True    # 'False' would make another '<authors/> block'
            - fragment: |
              <authors>
                <author active="false">
                    <name>William Shakespeare</name>
                    <popularity demographic="educators">10</popularity>
                    <popularity demographic="students">1</popularity>
                </author>
                <author active="true">
                    <name alias="true">JK Rowling</name>
                    <popularity demographic="educators">7</popularity>
                    <popularity demographic="students">10</popularity>
                </author>
              </authors>

    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    fragment_root = ET.fromstring(fragment)
    tree = ET.parse(name)

    if xpath is not None:
        target_parent = tree.find(xpath)
    else:
        target_parent = tree.getroot()

    if target_parent is None:
        ret["comment"] = "No managable XML found"

    no_changes = False
    # First look for an exact matching child element.
    for child in target_parent:
        if _element_tree_equal(child, fragment_root):
            no_changes = True
            break

    if no_changes:
        ret["comment"] = "XML contains fragment. No changes needed"
        return ret

    # No match..
    if replace:
        doppelganger = target_parent.find(fragment_root.tag)
        if doppelganger is not None:
            position = list(target_parent).index(doppelganger)
            target_parent.remove(doppelganger)
            target_parent.insert(position, fragment_root)
            ret["comment"] = "XML replaced old tag."
            ret["changes"][fragment_root.tag] = {
                "diff": "".join(
                    difflib.unified_diff(
                        ET.tostring(doppelganger), ET.tostring(fragment_root),
                    ),
                ),
            }
            return ret

    # Append
    target_parent.append(fragment_root)
    ret["comment"] = "XML appended to target."
    ret["changes"][fragment_root.tag] = {"new": ET.tostring(fragment_root)}

    if not __opts__["test"]:
        tree.write(name)
        ret.result = True

    return ret
