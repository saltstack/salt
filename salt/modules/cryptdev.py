# -*- coding: utf-8 -*-
'''
Salt module to manage Unix cryptsetup jobs and the crypttab file
'''

# Import python libraries
from __future__ import absolute_import
import json
import logging
import os

# Import salt libraries
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import filter, zip  # pylint: disable=import-error,redefined-builtin

# Set up logger
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'cryptdev'

def __virtual__():
    '''
    Only load on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return (False, 'The cryptdev module cannot be loaded: not a POSIX-like system')
    else:
        return True

class _crypttab_entry(object):
    '''
    Utility class for manipulating crypttab entries. Primarily we're parsing,
    formatting, and comparing lines. Parsing emits dicts expected from
    crypttab() or raises a ValueError.
    '''

    class ParseError(ValueError):
        '''Error raised when a line isn't parsible as a crypttab entry'''

    crypttab_keys = ('name', 'device', 'password', 'options')
    crypttab_format = '{name}\t\t{device}\t\t\t\t{password}\t\t\t{options}'

    @classmethod
    def dict_from_line(cls, line, keys=crypttab_keys):
        if len(keys) != 4:
            raise ValueError('Invalid key array: {0}'.format(keys))
        if line.startswith('#'):
            raise cls.ParseError("Comment!")

        comps = line.split()
        # If there are only three entries, then the options have been omitted.
        if len(comps) == 3:
            comps += ['']

        if len(comps) != 4:
            raise cls.ParseError("Invalid Entry!")

        return dict(zip(keys, comps))

    @classmethod
    def from_line(cls, *args, **kwargs):
        return cls(** cls.dict_from_line(*args, **kwargs))

    @classmethod
    def dict_to_line(cls, entry):
        return cls.crypttab_format.format(**entry)

    def __str__(self):
        '''String value, only works for full repr'''
        return self.dict_to_line(self.criteria)

    def __repr__(self):
        '''Always works'''
        return str(self.criteria)

    def pick(self, keys):
        '''Returns an instance with just those keys'''
        subset = dict([(key, self.criteria[key]) for key in keys])
        return self.__class__(**subset)

    def __init__(self, **criteria):
        '''Store non-empty, non-null values to use as filter'''
        self.criteria = {key: str(value) for key, value in six.iteritems(criteria)
                         if value is not None}

    @staticmethod
    def norm_path(path):
        '''Resolve equivalent paths equivalently'''
        return os.path.normcase(os.path.normpath(path))

    def match(self, line):
        '''Compare potentially partial criteria against a complete line'''
        entry = self.dict_from_line(line)
        for key, value in six.iteritems(self.criteria):
            if entry[key] != value:
                return False
        return True


def crypttab(config='/etc/crypttab'):
    '''
    List the contents of the crypttab

    CLI Example:

    .. code-block:: bash

        salt '*' cryptdev.crypttab
    '''
    ret = {}
    if not os.path.isfile(config):
        return ret
    with salt.utils.fopen(config) as ifile:
        for line in ifile:
            try:
                entry = _crypttab_entry.dict_from_line(line)

                entry['options'] = entry['options'].split(',')

                # Handle duplicate names by appending `_`
                while entry['name'] in ret:
                    entry['name'] += '_'

                ret[entry.pop('name')] = entry
            except _crypttab_entry.ParseError:
                pass

    return ret

def rm_crypttab(name, device, config='/etc/crypttab'):
    '''
    Remove the device point from the crypttab

    CLI Example:

    .. code-block:: bash

        salt '*' cryptdev.rm_crypttab foo /dev/sdg
    '''
    modified = False
    criteria = _crypttab_entry(name=name, device=device)

    # For each line in the config that does not match the criteria, add it to
    # the list. At the end, re-create the config from just those lines.
    lines = []
    try:
        with salt.utils.fopen(config, 'r') as ifile:
            for line in ifile:
                try:
                    if criteria.match(line):
                        modified = True
                    else:
                        lines.append(line)

                except _crypttab_entry.ParseError:
                    lines.append(line)

    except (IOError, OSError) as exc:
        msg = "Couldn't read from {0}: {1}"
        raise CommandExecutionError(msg.format(config, str(exc)))

    if modified:
        try:
            with salt.utils.fopen(config, 'w+') as ofile:
                ofile.writelines(lines)
        except (IOError, OSError) as exc:
            msg = "Couldn't write to {0}: {1}"
            raise CommandExecutionError(msg.format(config, str(exc)))

    # If we reach this point, the changes were successful
    return True
