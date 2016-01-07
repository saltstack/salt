# -*- coding: utf-8 -*-
'''
Property List Module
====================

The Property List module reads and writes .plist files which are used
heavily throughout OSX using the PyObjC bridge for NSPropertyListSerialization

Several parts of this code have been taken/modified from gneagle's
FoundationPlist class which is a part of the munki project.

Remember that changes may not be effected immediately, and that you should try to avoid modifying the plist
of any running process (If using NSPropertyListSerialization).

TODO:

- The write_key/read_key executions should support collections. Operations on selections via command line
are always a bit clunky, so need to put some thought into this.

:maintainer:    Mosen <mosen@github.com>
:maturity:      new
:depends:       objc,Foundation
:platform:      darwin
'''
from __future__ import absolute_import

# Import python libs
import os

# Import salt libs
import salt.utils
import logging

log = logging.getLogger(__name__)  # Start logging

# Import 3rd party libs
HAS_LIBS = False
try:
    from Foundation import NSData, \
        NSPropertyListSerialization, \
        NSPropertyListMutableContainers, \
        NSPropertyListXMLFormat_v1_0, \
        NSPropertyListBinaryFormat_v1_0, \
        NSNumber, \
        NSString, \
        NSMutableDictionary

    HAS_LIBS = True
except ImportError:
    log.debug('Error importing dependencies for plist execution module.')

__virtualname__ = 'plist'


def __virtual__():
    '''
    Only load if the platform is correct and we can use PyObjC libs
    '''
    if not salt.utils.is_darwin():
        return False, 'Not Darwin'

    if not HAS_LIBS:
        return False, 'Failed to load libraries'

    return __virtualname__


class FoundationPlistException(Exception):
    pass


class NSPropertyListSerializationException(FoundationPlistException):
    pass


class NSPropertyListWriteException(FoundationPlistException):
    pass


def _readPlist(filepath):
    """
    Read a .plist file from filepath.  Return the unpacked root object
    (which is usually a dictionary).

    If the file doesn't exist, this returns None
    """
    if not os.path.isfile(filepath):
        log.debug('Tried to read non-existent property list at path: {0}'.format(filepath))
        return None

    plistData = NSData.dataWithContentsOfFile_(filepath)

    if not plistData:
        log.error('Failed to read {0}'.format(filepath))
        return None

    dataObject, plistFormat, error = \
        NSPropertyListSerialization.propertyListFromData_mutabilityOption_format_errorDescription_(
            plistData, NSPropertyListMutableContainers, None, None)
    if error:
        error = error.encode('ascii', 'ignore')
        errmsg = "%s in file %s" % (error, filepath)

        import traceback

        log.debug(errmsg)
        log.debug(traceback.format_exc())
        raise NSPropertyListSerializationException(errmsg)
    else:
        return dataObject



def _writePlist(dataObject, filepath):
    '''
    Write 'rootObject' as a plist to filepath.
    '''
    plistData, error = \
        NSPropertyListSerialization.dataFromPropertyList_format_errorDescription_(
            dataObject, NSPropertyListXMLFormat_v1_0, None)
    if error:
        error = error.encode('ascii', 'ignore')
        log.debug('Error writing plist')
        log.debug(error)
        raise NSPropertyListSerializationException(error)
    else:
        if plistData.writeToFile_atomically_(filepath, True):
            return
        else:
            errmsg = "Failed to write plist data to %s" % filepath

            import traceback

            log.debug(errmsg)
            log.debug(traceback.format_exc())
            raise NSPropertyListWriteException(errmsg)


def _writePlistToString(rootObject):
    '''Return 'rootObject' as a plist-formatted string.'''
    plistData, error = \
        NSPropertyListSerialization.dataFromPropertyList_format_errorDescription_(
            rootObject, NSPropertyListXMLFormat_v1_0, None)
    if error:
        error = error.encode('ascii', 'ignore')
        log.debug('Error encoding to plist')
        log.debug(error)
        raise NSPropertyListSerializationException(error)
    else:
        return str(plistData)


def _valueToNSObject(value, nstype):
    '''Convert a string with a type specifier to a native Objective-C NSObject (serializable).'''
    return {
        'string': lambda v: NSString.stringWithUTF8String_(v),
        'int': lambda v: NSNumber.numberWithInt_(v),
        'float': lambda v: NSNumber.numberWithFloat_(v),
        'bool': lambda v: True if v == 'true' else False,
        'data': lambda v: NSData.initWithBytes_length_(v, len(v))
    }[nstype](value)

def _objectsForKeyDict(dict, keys, collector):
    """Get plist values extracted by providing a list of keys and their hierarchy.

    Recursive call traverses the specified keys in the NSDictionary, and retrieves the associated
    object at each 'leaf node', assigning a hierarchy of keys and the found value to the collector.

        Args:
            dict (NSDictionary): The current dictionary being operated on

            keys: The current dict describing a key or nested key in the dict parameter.

            collector: A reference to the current dict which can have value(s) set.
    """
    # Stop collecting values if the specified key hierarchy doesn't exist.
    if dict is None:
        collector = None
        return

    for key, value in keys.items():
        if type(value) is dict:
            collector[key] = {}
            plist_value = dict.objectForKey_(key)
            _objectsForKeyDict(plist_value, value, collector[key])
        else:

            collector[key] = dict.objectForKey_(key)

def _setObjectsForKeyDict(dict, keys, changed={}):
    """Set plist values using a given dict.

    Recursively finds or creates keys given and sets their values. This can be used to maintain a partial or
    complete override of any given property list file.

        Args:
            dict (NSMutableDictionary): The current dictionary being operated on. For a non existent file this will be
            blank.

            keys: A dict representing a hierarchy with leaf node values.
    """
    for key, value in keys.items():
        existing_value = dict.objectForKey_(key)

        if type(value) is dict:
            # Value unavailable, so create structure
            if existing_value is None:
                child = NSMutableDictionary()
                dict.setObject_forKey_(child, key)

            changed[key] = {}
            _setObjectsForKeyDict(child, value, changed[key])
        else:
            if existing_value != value:
                dict.setObject_forKey_(value, key)
                changed[key] = value


def _removeObjectsForKeyDict(dict, keys, changed={}):
    """Remove plist values using a given dict.

    Traverse each entry in the keys dict and remove the corresponding key (if it exists).
    If it doesn't exist then the function returns early.
    If the key was removed, the full path to that key is indicated in the changed dict.

        Args:
            dict (NSMutableDictionary): The current dictionary being operated on. For a non existent file this will be
            blank.

            keys: A dict representing a hierarchy pointing to keys to be removed

            changed: A dict used to record changes made
    """
    for key, value in keys.items():
        existing_value = dict.objectForKey_(key)

        if not existing_value is None:  # No need to process removal for non existent keys
            if type(value) is dict:
                changed[key] = {}
                _removeObjectsForKeyDict(existing_value, value, changed[key])  # Recurse deeper until not a dict
            else:
                dict.removeObjectForKey_(key)
                changed[key] = value


def _objectForKeyList(dict, keys):
    '''
    Get an object inside a nested NSDictionary structure, using a list of nested keys
    '''
    key = keys.pop(0)

    # User accidentally supplies zero length key
    if len(key) == 0:
        return dict

    if len(keys) > 0:
        return _objectForKeyList(dict.objectForKey_(key), keys)
    else:
        # TODO: special case for array index notation [x] if current object is NSArray
        # if dict.isKindOfClass_(NSArray.class_()):
        # return
        return dict.objectForKey_(key)


def _setObjectForKeyList(dict, keys, value):
    '''
    Set the value of an object inside a nested NSDictionary structure, using a list of keys
    '''
    key = keys.pop(0)

    # User accidentally supplies zero length key
    if len(key) == 0:
        return dict

    if len(keys) > 0:
        return _objectForKeyList(dict.objectForKey_(key), keys)
    else:
        # TODO: special case for array index notation [x] if current object is NSArray
        # if dict.isKindOfClass_(NSArray.class_()):
        # return
        dict.setObject_forKey_(value, key)


def _removeObjectForKeyList(dict, keys):
    '''
    Remove an object inside a nested NSDictionary structure, using a list of nested keys
    '''
    key = keys.pop(0)

    # User accidentally supplies zero length key
    if len(key) == 0:
        return dict

    if len(keys) > 0:
        return _objectForKeyList(dict.objectForKey_(key), keys)
    else:
        # TODO: special case for array index notation [x] if current object is NSArray
        # if dict.isKindOfClass_(NSArray.class_()):
        # return
        return dict.removeObjectForKey_(key)


def gen_string(data, format='xml'):
    '''
    Take a python struct (normally a dict) and generate a string representing a property list.

    data
        Python data structure (dict)

    format (default 'xml')
        Generate format, 'xml' or 'binary'
    '''
    serialization = NSPropertyListXMLFormat_v1_0 if format == 'xml' else NSPropertyListBinaryFormat_v1_0
    plistData, error = \
        NSPropertyListSerialization.dataFromPropertyList_format_errorDescription_(
            data, serialization, None)
    if error:
        error = error.encode('ascii', 'ignore')
        log.debug('Error writing plist')
        log.debug(error)
        raise NSPropertyListSerializationException(error)
    else:
        return plistData

def parse_string(data):
    '''
    Take a property list as a string and return a python native representation.

    Used by other modules in salt-osx
    '''
    plistData = buffer(data)
    dataObject, plistFormat, error = \
        NSPropertyListSerialization.propertyListFromData_mutabilityOption_format_errorDescription_(
            plistData, NSPropertyListMutableContainers, None, None)
    if error:
        error = error.encode('ascii', 'ignore')

        import traceback

        log.debug('Error parsing plist from string')
        log.debug(error)
        raise NSPropertyListSerializationException(error)
    else:
        return dataObject

def read_key(path, key=''):
    '''
    Read the value of a key contained within the Property List file specified

    path
        An absolute path to a property list (.plist) file, including the extension

    key
        The path specification for the key to modify. A list of keys separated by a colon. eg. 'path:to:name'

    CLI Example:

    .. code-block:: bash

        salt '*' plist.read <path> [key]
    '''
    dataObject = _readPlist(path)

    if dataObject is None:
        return None

    keys = key.split(':')
    if type(keys) is str:
        keys = list(keys)

    value = _objectForKeyList(dataObject, keys)
    return value


def write_key(path, key, nstype, value):
    '''
    Write the value of a key contained within the Property List file specified.
    If the property list file does not exist, the default behaviour is to create it with the keys/values given.

    path
        An absolute path to a property list (.plist) file, including the extension

    key
        The path specification for the key to modify. A list of keys separated by a colon.

    nstype
        The value type to write, one of 'string', 'int', 'float', 'bool'

    value
        The property value. If not specified it will be set to an empty value.

    CLI Example:

    .. code-block:: bash

        salt '*' plist.write <path> <key> <nstype> [value]
    '''
    dataObject = _readPlist(path)

    keys = key.split(':')
    if type(keys) is str:
        keys = list(keys)

    if dataObject is None:
        dataObject = NSMutableDictionary()

    _setObjectForKeyList(dataObject, keys, _valueToNSObject(value, nstype))
    _writePlist(dataObject, path)


def delete_key(path, key):
    '''
    Delete the key from the property list at the specified path

    path
        An absolute path to a property list (.plist) file, including the extension

    key
        The specification of the key to modify. A list of keys separated by a colon.

    .. code-block:: bash

        salt '*' plist.delete <path> [key]
    '''
    dataObject = _readPlist(path)

    if dataObject is None:
        return None  # None indicating no action was taken.

    keys = key.split(':')
    if type(keys) is str:
        keys = list(keys)

    _removeObjectForKeyList(dataObject, keys)
    _writePlist(dataObject, path)


def read(path):
    '''
    Read the entire contents of the property list at the specified path

    path
        An absolute path to a property list (.plist) file, including the extension

    .. code-block:: bash

        salt '*' plist.read <path>
    '''
    dataObject = _readPlist(path)
    return dataObject

def write(path, contents_dict):
    '''
    (over)write the entire contents of the property list at the specified path

    path
        An absolute path to a property list (.plist) file, including the extension

    contents_dict
        A python dict containing the objects to be encoded into the plist file.
    '''
    _writePlist(path, contents_dict)


def read_keys(path, keys):
    """
    Read values of keys described by a dict.
    Each dict entry is traversed until it has no child dict.

    path
        An absolute path to a property list (.plist) file, including the extension

    keys
        A dict describing a key or nested keys, with any leaf values used to look up the
        corresponding plist value.
    """
    dataObject = _readPlist(path)

    collector = {}
    _objectsForKeyDict(dataObject, keys, collector)

    return collector


def write_keys(path, keys, test=False):
    """
    Write key structure and its values to the given property list.
    If a key does not exist in the target plist, it is created as a dictionary by default.

    path
        An absolute path to a property list (.plist) file, including the extension

    keys
        A dict describing a structure and value(s) that should exist inside the target plist

    test
        If test is true, no changes will be written, but you will receive a dict containing the changes that
        would have been performed.
    """
    dataObject = _readPlist(path)

    if dataObject is None:
        dataObject = NSMutableDictionary()

    changed = {}
    _setObjectsForKeyDict(dataObject, keys, changed)

    if test == False:
        _writePlist(dataObject, path)

    return changed


def delete_keys(path, keys, test=False):
    """
    Delete keys indicated by key dict structure.
    The deepest, or leaf node, of each dictionary entry will be removed from the plist.

    path
        An absolute path to a property list (.plist) file, including the extension

    keys
        A dict describing keys that should NOT exist inside the target plist

    test
        If test is true, no changes will be written, but you will receive a dict containing the keys that
        would have been removed.
    """
    dataObject = _readPlist(path)
    changed = {}

    if dataObject is None:
        return changed  # No need to remove anything from non existent property list

    _removeObjectsForKeyDict(dataObject, keys, changed)

    if test == False:
        _writePlist(dataObject, path)

    return changed