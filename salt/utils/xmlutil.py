# -*- coding: utf-8 -*-
'''
Various XML utilities
'''


def to_dict(xmltree):
    '''
    Convert an XML tree into a dict. The tree that is passed in must be an
    ElementTree object.
    '''
    # If this object has no children, the for..loop below will return nothing
    # for it, so just return a single dict representing it.
    if len(xmltree.getchildren()) < 1:
        name = xmltree.tag
        if '}' in name:
            comps = name.split('}')
            name = comps[1]
        return {name: xmltree.text}

    xmldict = {}
    for item in xmltree:
        name = item.tag
        if '}' in name:
            # If this XML tree has an xmlns attribute, then etree will add it
            # to the beginning of the tag, like: "{http://path}tag". This
            # aggression will not stand, man.
            comps = name.split('}')
            name = comps[1]
        if name not in xmldict:
            if len(item.getchildren()) > 0:
                xmldict[name] = to_dict(item)
            else:
                xmldict[name] = item.text
        else:
            # If a tag appears more than once in the same place, convert it to
            # a list. This may require that the caller watch for such a thing
            # to happen, and behave accordingly.
            if not isinstance(xmldict[name], list):
                xmldict[name] = [xmldict[name]]
            xmldict[name].append(to_dict(item))
    return xmldict
