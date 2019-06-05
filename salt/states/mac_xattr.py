# -*- coding: utf-8 -*-
'''
Allows you to manage extended attributes on files or directories
================================================================

Install, enable and disable assistive access on macOS minions

.. code-block:: yaml

    /path/to/file:
      xattr.exists:
        - attributes:
            - com.file.attr=test
            - com.apple.quarantine=0x00001111
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import logging
import os

log = logging.getLogger(__name__)
__virtualname__ = "xattr"


def __virtual__():
    '''
    Only work on Mac OS
    '''
    if __grains__['os'] in ['MacOS', 'Darwin']:
        return __virtualname__
    return False


def exists(name, attributes):
    '''
    Make sure the given attributes exist on the file/directory

    name
        The path to the file/directory

    attributes
        The attributes that should exist on the file/directory, this is accepted as
        an array, with key and value split with an equals sign, if you want to specify
        a hex value then add 0x to the beginning of the value.

    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    if not os.path.exists(name):
        ret['result'] = False
        ret['comment'] = "File or directory doesn't exist"
        return ret

    current_attrs = __salt__['xattr.list'](name)
    current_ids = current_attrs.keys()

    for attr in attributes:
        attr_id, attr_val = attr.split("=")
        attr_hex = attr_val.startswith("0x")

        if attr_hex:
            # Remove spaces and new lines so we can match these
            current_attrs[attr_id] = __salt__['xattr.read'](name, attr_id, hex=True).replace(" ", "").replace("\n", "")
            attr_val = attr_val[2:].replace(" ", "")

        if attr_id not in current_attrs:
            value_matches = False
        else:
            value_matches = ((current_attrs[attr_id] == attr_val) or
                             (attr_hex and current_attrs[attr_id] == attr_val))

        if attr_id in current_ids and value_matches:
            continue
        else:
            ret['changes'][attr_id] = attr_val
            __salt__['xattr.write'](name, attr_id, attr_val, attr_hex)

    if len(ret['changes'].keys()) == 0:
        ret['comment'] = 'All values existed correctly.'

    return ret


def delete(name, attributes):
    '''
    Make sure the given attributes are deleted from the file/directory

    name
        The path to the file/directory

    attributes
        The attributes that should be removed from the file/directory, this is accepted as
        an array.
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    if not os.path.exists(name):
        ret['result'] = False
        ret['comment'] = "File or directory doesn't exist"
        return ret

    current_attrs = __salt__['xattr.list'](name)
    current_ids = current_attrs.keys()

    for attr in attributes:

        if attr in current_ids:
            __salt__['xattr.delete'](name, attr)
            ret['changes'][attr] = 'delete'

    if len(ret['changes'].keys()) == 0:
        ret['comment'] = 'All attributes were already deleted.'

    return ret
