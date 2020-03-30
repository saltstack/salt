# -*- coding: utf-8 -*-
'''
Utility functions for zfs

These functions are for dealing with type conversion and basic execution

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.stringutils, salt.ext, salt.module.cmdmod
:platform:      illumos,freebsd,linux

.. versionadded:: 2018.3.1

'''

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
import os
import re
import math
import logging
from numbers import Number

# Import salt libs
from salt.utils.decorators import memoize as real_memoize
from salt.utils.odict import OrderedDict
from salt.utils.stringutils import to_num as str_to_num
import salt.modules.cmdmod

# Import 3rd-party libs
from salt.ext.six.moves import zip

# Size conversion data
re_zfs_size = re.compile(r'^(\d+|\d+(?=\d*)\.\d+)([KkMmGgTtPpEe][Bb]?)$')
zfs_size = ['K', 'M', 'G', 'T', 'P', 'E']

log = logging.getLogger(__name__)


def _check_retcode(cmd):
    '''
    Simple internal wrapper for cmdmod.retcode
    '''
    return salt.modules.cmdmod.retcode(cmd, output_loglevel='quiet', ignore_retcode=True) == 0


def _exec(**kwargs):
    '''
    Simple internal wrapper for cmdmod.run
    '''
    if 'ignore_retcode' not in kwargs:
        kwargs['ignore_retcode'] = True
    if 'output_loglevel' not in kwargs:
        kwargs['output_loglevel'] = 'quiet'
    return salt.modules.cmdmod.run_all(**kwargs)


def _merge_last(values, merge_after, merge_with=' '):
    '''
    Merge values all values after X into the last value
    '''
    if len(values) > merge_after:
        values = values[0:(merge_after-1)] + [merge_with.join(values[(merge_after-1):])]

    return values


def _property_normalize_name(name):
    '''
    Normalizes property names
    '''
    if '@' in name:
        name = name[:name.index('@')+1]
    return name


def _property_detect_type(name, values):
    '''
    Detect the datatype of a property
    '''
    value_type = 'str'
    if values.startswith('on | off'):
        value_type = 'bool'
    elif values.startswith('yes | no'):
        value_type = 'bool_alt'
    elif values in ['<size>', '<size> | none']:
        value_type = 'size'
    elif values in ['<count>', '<count> | none', '<guid>']:
        value_type = 'numeric'
    elif name in ['sharenfs', 'sharesmb', 'canmount']:
        value_type = 'bool'
    elif name in ['version', 'copies']:
        value_type = 'numeric'
    return value_type


def _property_create_dict(header, data):
    '''
    Create a property dict
    '''
    prop = dict(zip(header, _merge_last(data, len(header))))
    prop['name'] = _property_normalize_name(prop['property'])
    prop['type'] = _property_detect_type(prop['name'], prop['values'])
    prop['edit'] = from_bool(prop['edit'])
    if 'inherit' in prop:
        prop['inherit'] = from_bool(prop['inherit'])
    del prop['property']
    return prop


def _property_parse_cmd(cmd, alias=None):
    '''
    Parse output of zpool/zfs get command
    '''
    if not alias:
        alias = {}
    properties = {}

    # NOTE: append get to command
    if cmd[-3:] != 'get':
        cmd += ' get'

    # NOTE: parse output
    prop_hdr = []
    for prop_data in _exec(cmd=cmd)['stderr'].split('\n'):
        # NOTE: make the line data more manageable
        prop_data = prop_data.lower().split()

        # NOTE: skip empty lines
        if not prop_data:
            continue
        # NOTE: parse header
        elif prop_data[0] == 'property':
            prop_hdr = prop_data
            continue
        # NOTE: skip lines after data
        elif not prop_hdr or prop_data[1] not in ['no', 'yes']:
            continue

        # NOTE: create property dict
        prop = _property_create_dict(prop_hdr, prop_data)

        # NOTE: add property to dict
        properties[prop['name']] = prop
        if prop['name'] in alias:
            properties[alias[prop['name']]] = prop

        # NOTE: cleanup some duplicate data
        del prop['name']
    return properties


def _auto(direction, name, value, source='auto', convert_to_human=True):
    '''
    Internal magic for from_auto and to_auto
    '''
    # NOTE: check direction
    if direction not in ['to', 'from']:
        return value

    # NOTE: collect property data
    props = property_data_zpool()
    if source == 'zfs':
        props = property_data_zfs()
    elif source == 'auto':
        props.update(property_data_zfs())

    # NOTE: figure out the conversion type
    value_type = props[name]['type'] if name in props else 'str'

    # NOTE: convert
    if value_type == 'size' and direction == 'to':
        return globals()['{}_{}'.format(direction, value_type)](value, convert_to_human)

    return globals()['{}_{}'.format(direction, value_type)](value)


@real_memoize
def _zfs_cmd():
    '''
    Return the path of the zfs binary if present
    '''
    # Get the path to the zfs binary.
    return salt.utils.path.which('zfs')


@real_memoize
def _zpool_cmd():
    '''
    Return the path of the zpool binary if present
    '''
    # Get the path to the zfs binary.
    return salt.utils.path.which('zpool')


def _command(source, command, flags=None, opts=None,
             property_name=None, property_value=None,
             filesystem_properties=None, pool_properties=None,
             target=None):
    '''
    Build and properly escape a zfs command

    .. note::

        Input is not considered safe and will be passed through
        to_auto(from_auto('input_here')), you do not need to do so
        your self first.

    '''
    # NOTE: start with the zfs binary and command
    cmd = [_zpool_cmd() if source == 'zpool' else _zfs_cmd(), command]

    # NOTE: append flags if we have any
    if flags is None:
        flags = []
    for flag in flags:
        cmd.append(flag)

    # NOTE: append options
    #       we pass through 'sorted' to guarantee the same order
    if opts is None:
        opts = {}
    for opt in sorted(opts):
        if not isinstance(opts[opt], list):
            opts[opt] = [opts[opt]]
        for val in opts[opt]:
            cmd.append(opt)
            cmd.append(to_str(val))

    # NOTE: append filesystem properties (really just options with a key/value)
    #       we pass through 'sorted' to guarantee the same order
    if filesystem_properties is None:
        filesystem_properties = {}
    for fsopt in sorted(filesystem_properties):
        cmd.append('-O' if source == 'zpool' else '-o')
        cmd.append('{key}={val}'.format(
            key=fsopt,
            val=to_auto(fsopt, filesystem_properties[fsopt], source='zfs', convert_to_human=False),
        ))

    # NOTE: append pool properties (really just options with a key/value)
    #       we pass through 'sorted' to guarantee the same order
    if pool_properties is None:
        pool_properties = {}
    for fsopt in sorted(pool_properties):
        cmd.append('-o')
        cmd.append('{key}={val}'.format(
            key=fsopt,
            val=to_auto(fsopt, pool_properties[fsopt], source='zpool', convert_to_human=False),
        ))

    # NOTE: append property and value
    #       the set command takes a key=value pair, we need to support this
    if property_name is not None:
        if property_value is not None:
            if not isinstance(property_name, list):
                property_name = [property_name]
            if not isinstance(property_value, list):
                property_value = [property_value]
            for key, val in zip(property_name, property_value):
                cmd.append('{key}={val}'.format(
                    key=key,
                    val=to_auto(key, val, source=source, convert_to_human=False),
                ))
        else:
            cmd.append(property_name)

    # NOTE: append the target(s)
    if target is not None:
        if not isinstance(target, list):
            target = [target]
        for tgt in target:
            # NOTE: skip None list items
            #       we do not want to skip False and 0!
            if tgt is None:
                continue
            cmd.append(to_str(tgt))

    return ' '.join(cmd)


def is_supported():
    '''
    Check the system for ZFS support
    '''
    # Check for supported platforms
    # NOTE: ZFS on Windows is in development
    # NOTE: ZFS on NetBSD is in development
    on_supported_platform = False
    if salt.utils.platform.is_sunos():
        on_supported_platform = True
    elif salt.utils.platform.is_freebsd() and _check_retcode('kldstat -q -m zfs'):
        on_supported_platform = True
    elif salt.utils.platform.is_linux() and os.path.exists('/sys/module/zfs'):
        on_supported_platform = True
    elif salt.utils.platform.is_linux() and salt.utils.path.which('zfs-fuse'):
        on_supported_platform = True
    elif salt.utils.platform.is_darwin() and \
         os.path.exists('/Library/Extensions/zfs.kext') and \
         os.path.exists('/dev/zfs'):
        on_supported_platform = True

    # Additional check for the zpool command
    return (salt.utils.path.which('zpool') and on_supported_platform) is True


@real_memoize
def has_feature_flags():
    '''
    Check if zpool-features is available
    '''
    # get man location
    man = salt.utils.path.which('man')
    return _check_retcode('{man} zpool-features'.format(
        man=man
    )) if man else False


@real_memoize
def property_data_zpool():
    '''
    Return a dict of zpool properties

    .. note::

        Each property will have an entry with the following info:
            - edit : boolean - is this property editable after pool creation
            - type : str - either bool, bool_alt, size, numeric, or string
            - values : str - list of possible values

    .. warning::

        This data is probed from the output of 'zpool get' with some supplemental
        data that is hardcoded. There is no better way to get this information aside
        from reading the code.

    '''
    # NOTE: man page also mentions a few short forms
    property_data = _property_parse_cmd(_zpool_cmd(), {
        'allocated': 'alloc',
        'autoexpand': 'expand',
        'autoreplace': 'replace',
        'listsnapshots': 'listsnaps',
        'fragmentation': 'frag',
    })

    # NOTE: zpool status/iostat has a few extra fields
    zpool_size_extra = [
        'capacity-alloc', 'capacity-free',
        'operations-read', 'operations-write',
        'bandwith-read', 'bandwith-write',
        'read', 'write',
    ]
    zpool_numeric_extra = [
        'cksum', 'cap',
    ]

    for prop in zpool_size_extra:
        property_data[prop] = {
            'edit': False,
            'type': 'size',
            'values': '<size>',
        }

    for prop in zpool_numeric_extra:
        property_data[prop] = {
            'edit': False,
            'type': 'numeric',
            'values': '<count>',
        }

    return property_data


@real_memoize
def property_data_zfs():
    '''
    Return a dict of zfs properties

    .. note::

        Each property will have an entry with the following info:
            - edit : boolean - is this property editable after pool creation
            - inherit : boolean - is this property inheritable
            - type : str - either bool, bool_alt, size, numeric, or string
            - values : str - list of possible values

    .. warning::

        This data is probed from the output of 'zfs get' with some supplemental
        data that is hardcoded. There is no better way to get this information aside
        from reading the code.

    '''
    return _property_parse_cmd(_zfs_cmd(), {
        'available': 'avail',
        'logicalreferenced': 'lrefer.',
        'logicalused': 'lused.',
        'referenced': 'refer',
        'volblocksize': 'volblock',
        'compression': 'compress',
        'readonly': 'rdonly',
        'recordsize': 'recsize',
        'refreservation': 'refreserv',
        'reservation': 'reserv',
    })


def from_numeric(value):
    '''
    Convert zfs numeric to python int
    '''
    if value == 'none':
        value = None
    elif value:
        value = str_to_num(value)
    return value


def to_numeric(value):
    '''
    Convert python int to zfs numeric
    '''
    value = from_numeric(value)
    if value is None:
        value = 'none'
    return value


def from_bool(value):
    '''
    Convert zfs bool to python bool
    '''
    if value in ['on', 'yes']:
        value = True
    elif value in ['off', 'no']:
        value = False
    elif value == 'none':
        value = None

    return value


def from_bool_alt(value):
    '''
    Convert zfs bool_alt to python bool
    '''
    return from_bool(value)


def to_bool(value):
    '''
    Convert python bool to zfs on/off bool
    '''
    value = from_bool(value)
    if isinstance(value, bool):
        value = 'on' if value else 'off'
    elif value is None:
        value = 'none'

    return value


def to_bool_alt(value):
    '''
    Convert python to zfs yes/no value
    '''
    value = from_bool_alt(value)
    if isinstance(value, bool):
        value = 'yes' if value else 'no'
    elif value is None:
        value = 'none'

    return value


def from_size(value):
    '''
    Convert zfs size (human readable) to python int (bytes)
    '''
    match_size = re_zfs_size.match(str(value))
    if match_size:
        v_unit = match_size.group(2).upper()[0]
        v_size = float(match_size.group(1))
        v_multiplier = math.pow(1024, zfs_size.index(v_unit) + 1)
        value = v_size * v_multiplier
        if int(value) == value:
            value = int(value)
    elif value is not None:
        value = str(value)

    return from_numeric(value)


def to_size(value, convert_to_human=True):
    '''
    Convert python int (bytes) to zfs size

    NOTE: http://src.illumos.org/source/xref/illumos-gate/usr/src/lib/pyzfs/common/util.py#114
    '''
    value = from_size(value)
    if value is None:
        value = 'none'

    if isinstance(value, Number) and value > 1024 and convert_to_human:
        v_power = int(math.floor(math.log(value, 1024)))
        v_multiplier = math.pow(1024, v_power)

        # NOTE: zfs is a bit odd on how it does the rounding,
        #       see libzfs implementation linked above
        v_size_float = float(value) / v_multiplier
        if v_size_float == int(v_size_float):
            value = "{:.0f}{}".format(
                v_size_float,
                zfs_size[v_power-1],
            )
        else:
            for v_precision in ["{:.2f}{}", "{:.1f}{}", "{:.0f}{}"]:
                v_size = v_precision.format(
                    v_size_float,
                    zfs_size[v_power-1],
                )
                if len(v_size) <= 5:
                    value = v_size
                    break

    return value


def from_str(value):
    '''
    Decode zfs safe string (used for name, path, ...)
    '''
    if value == 'none':
        value = None
    if value:
        value = str(value)
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        value = value.replace('\\"', '"')

    return value


def to_str(value):
    '''
    Encode zfs safe string (used for name, path, ...)
    '''
    value = from_str(value)

    if value:
        value = value.replace('"', '\\"')
        if ' ' in value:
            value = '"' + value + '"'
    elif value is None:
        value = 'none'

    return value


def from_auto(name, value, source='auto'):
    '''
    Convert zfs value to python value
    '''
    return _auto('from', name, value, source)


def to_auto(name, value, source='auto', convert_to_human=True):
    '''
    Convert python value to zfs value
    '''
    return _auto('to', name, value, source, convert_to_human)


def from_auto_dict(values, source='auto'):
    '''
    Pass an entire dictionary to from_auto

    .. note::
        The key will be passed as the name

    '''
    for name, value in values.items():
        values[name] = from_auto(name, value, source)

    return values


def to_auto_dict(values, source='auto', convert_to_human=True):
    '''
    Pass an entire dictionary to to_auto

    .. note::
        The key will be passed as the name
    '''
    for name, value in values.items():
        values[name] = to_auto(name, value, source, convert_to_human)

    return values


def is_snapshot(name):
    '''
    Check if name is a valid snapshot name
    '''
    return from_str(name).count('@') == 1


def is_bookmark(name):
    '''
    Check if name is a valid bookmark name
    '''
    return from_str(name).count('#') == 1


def is_dataset(name):
    '''
    Check if name is a valid filesystem or volume name
    '''
    return not is_snapshot(name) and not is_bookmark(name)


def zfs_command(command, flags=None, opts=None, property_name=None, property_value=None,
                filesystem_properties=None, target=None):
    '''
    Build and properly escape a zfs command

    .. note::

        Input is not considered safe and will be passed through
        to_auto(from_auto('input_here')), you do not need to do so
        your self first.

    '''
    return _command(
        'zfs',
        command=command,
        flags=flags,
        opts=opts,
        property_name=property_name,
        property_value=property_value,
        filesystem_properties=filesystem_properties,
        pool_properties=None,
        target=target,
    )


def zpool_command(command, flags=None, opts=None, property_name=None, property_value=None,
                  filesystem_properties=None, pool_properties=None, target=None):
    '''
    Build and properly escape a zpool command

    .. note::

        Input is not considered safe and will be passed through
        to_auto(from_auto('input_here')), you do not need to do so
        your self first.

    '''
    return _command(
        'zpool',
        command=command,
        flags=flags,
        opts=opts,
        property_name=property_name,
        property_value=property_value,
        filesystem_properties=filesystem_properties,
        pool_properties=pool_properties,
        target=target,
    )


def parse_command_result(res, label=None):
    '''
    Parse the result of a zpool/zfs command

    .. note::

        Output on failure is rather predictable.
        - retcode > 0
        - each 'error' is a line on stderr
        - optional 'Usage:' block under those with hits

        We simple check those and return a OrderedDict were
        we set label = True|False and error = error_messages

    '''
    ret = OrderedDict()

    if label:
        ret[label] = res['retcode'] == 0

    if res['retcode'] != 0:
        ret['error'] = []
        for error in res['stderr'].splitlines():
            if error.lower().startswith('usage:'):
                break
            if error.lower().startswith("use '-f'"):
                error = error.replace('-f', 'force=True')
            if error.lower().startswith("use '-r'"):
                error = error.replace('-r', 'recursive=True')
            ret['error'].append(error)

        if ret['error']:
            ret['error'] = "\n".join(ret['error'])
        else:
            del ret['error']

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
