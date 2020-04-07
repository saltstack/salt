# -*- coding: utf-8 -*-
"""
Salt module to manage Unix cryptsetup jobs and the crypttab file

.. versionadded:: 2018.3.0
"""

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import re

# Import salt libraries
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six

# Set up logger
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "cryptdev"


def __virtual__():
    """
    Only load on POSIX-like systems
    """
    if salt.utils.platform.is_windows():
        return (False, "The cryptdev module cannot be loaded: not a POSIX-like system")

    return True


class _crypttab_entry(object):
    """
    Utility class for manipulating crypttab entries. Primarily we're parsing,
    formatting, and comparing lines. Parsing emits dicts expected from
    crypttab() or raises a ValueError.
    """

    class ParseError(ValueError):
        """Error raised when a line isn't parsible as a crypttab entry"""

    crypttab_keys = ("name", "device", "password", "options")
    crypttab_format = "{name: <12} {device: <44} {password: <22} {options}\n"

    @classmethod
    def dict_from_line(cls, line, keys=crypttab_keys):
        if len(keys) != 4:
            raise ValueError("Invalid key array: {0}".format(keys))
        if line.startswith("#"):
            raise cls.ParseError("Comment!")

        comps = line.split()
        # If there are only three entries, then the options have been omitted.
        if len(comps) == 3:
            comps += [""]

        if len(comps) != 4:
            raise cls.ParseError("Invalid Entry!")

        return dict(six.moves.zip(keys, comps))

    @classmethod
    def from_line(cls, *args, **kwargs):
        return cls(**cls.dict_from_line(*args, **kwargs))

    @classmethod
    def dict_to_line(cls, entry):
        return cls.crypttab_format.format(**entry)

    def __str__(self):
        """String value, only works for full repr"""
        return self.dict_to_line(self.criteria)

    def __repr__(self):
        """Always works"""
        return repr(self.criteria)

    def pick(self, keys):
        """Returns an instance with just those keys"""
        subset = dict([(key, self.criteria[key]) for key in keys])
        return self.__class__(**subset)

    def __init__(self, **criteria):
        """Store non-empty, non-null values to use as filter"""
        self.criteria = {
            key: salt.utils.stringutils.to_unicode(value)
            for key, value in six.iteritems(criteria)
            if value is not None
        }

    @staticmethod
    def norm_path(path):
        """Resolve equivalent paths equivalently"""
        return os.path.normcase(os.path.normpath(path))

    def match(self, line):
        """Compare potentially partial criteria against a complete line"""
        entry = self.dict_from_line(line)
        for key, value in six.iteritems(self.criteria):
            if entry[key] != value:
                return False
        return True


def active():
    """
    List existing device-mapper device details.
    """
    ret = {}
    # TODO: This command should be extended to collect more information, such as UUID.
    devices = __salt__["cmd.run_stdout"]("dmsetup ls --target crypt")
    out_regex = re.compile(r"(?P<devname>\w+)\W+\((?P<major>\d+), (?P<minor>\d+)\)")

    log.debug(devices)
    for line in devices.split("\n"):
        match = out_regex.match(line)
        if match:
            dev_info = match.groupdict()
            ret[dev_info["devname"]] = dev_info
        else:
            log.warning("dmsetup output does not match expected format")

    return ret


def crypttab(config="/etc/crypttab"):
    """
    List the contents of the crypttab

    CLI Example:

    .. code-block:: bash

        salt '*' cryptdev.crypttab
    """
    ret = {}
    if not os.path.isfile(config):
        return ret
    with salt.utils.files.fopen(config) as ifile:
        for line in ifile:
            line = salt.utils.stringutils.to_unicode(line).rstrip("\n")
            try:
                entry = _crypttab_entry.dict_from_line(line)

                entry["options"] = entry["options"].split(",")

                # Handle duplicate names by appending `_`
                while entry["name"] in ret:
                    entry["name"] += "_"

                ret[entry.pop("name")] = entry
            except _crypttab_entry.ParseError:
                pass

    return ret


def rm_crypttab(name, config="/etc/crypttab"):
    """
    Remove the named mapping from the crypttab. If the described entry does not
    exist, nothing is changed, but the command succeeds by returning
    ``'absent'``. If a line is removed, it returns ``'change'``.

    CLI Example:

    .. code-block:: bash

        salt '*' cryptdev.rm_crypttab foo
    """
    modified = False
    criteria = _crypttab_entry(name=name)

    # For each line in the config that does not match the criteria, add it to
    # the list. At the end, re-create the config from just those lines.
    lines = []
    try:
        with salt.utils.files.fopen(config, "r") as ifile:
            for line in ifile:
                line = salt.utils.stringutils.to_unicode(line)
                try:
                    if criteria.match(line):
                        modified = True
                    else:
                        lines.append(line)

                except _crypttab_entry.ParseError:
                    lines.append(line)

    except (IOError, OSError) as exc:
        msg = "Could not read from {0}: {1}"
        raise CommandExecutionError(msg.format(config, exc))

    if modified:
        try:
            with salt.utils.files.fopen(config, "w+") as ofile:
                ofile.writelines(
                    (salt.utils.stringutils.to_str(line) for line in lines)
                )
        except (IOError, OSError) as exc:
            msg = "Could not write to {0}: {1}"
            raise CommandExecutionError(msg.format(config, exc))

    # If we reach this point, the changes were successful
    return "change" if modified else "absent"


def set_crypttab(
    name,
    device,
    password="none",
    options="",
    config="/etc/crypttab",
    test=False,
    match_on="name",
):
    """
    Verify that this device is represented in the crypttab, change the device to
    match the name passed, or add the name if it is not present.

    CLI Example:

    .. code-block:: bash

        salt '*' cryptdev.set_crypttab foo /dev/sdz1 mypassword swap,size=256
    """

    # Fix the options type if it is not a string
    if options is None:
        options = ""
    elif isinstance(options, six.string_types):
        pass
    elif isinstance(options, list):
        options = ",".join(options)
    else:
        msg = "options must be a string or list of strings"
        raise CommandExecutionError(msg)

    # preserve arguments for updating
    entry_args = {
        "name": name,
        "device": device,
        "password": password if password is not None else "none",
        "options": options,
    }

    lines = []
    ret = None

    # Transform match_on into list--items will be checked later
    if isinstance(match_on, list):
        pass
    elif not isinstance(match_on, six.string_types):
        msg = "match_on must be a string or list of strings"
        raise CommandExecutionError(msg)
    else:
        match_on = [match_on]

    # generate entry and criteria objects, handle invalid keys in match_on
    entry = _crypttab_entry(**entry_args)
    try:
        criteria = entry.pick(match_on)

    except KeyError:
        filterFn = lambda key: key not in _crypttab_entry.crypttab_keys
        invalid_keys = six.moves.filter(filterFn, match_on)

        msg = 'Unrecognized keys in match_on: "{0}"'.format(invalid_keys)
        raise CommandExecutionError(msg)

    # parse file, use ret to cache status
    if not os.path.isfile(config):
        raise CommandExecutionError('Bad config file "{0}"'.format(config))

    try:
        with salt.utils.files.fopen(config, "r") as ifile:
            for line in ifile:
                line = salt.utils.stringutils.to_unicode(line)
                try:
                    if criteria.match(line):
                        # Note: If ret isn't None here,
                        # we've matched multiple lines
                        ret = "present"
                        if entry.match(line):
                            lines.append(line)
                        else:
                            ret = "change"
                            lines.append(six.text_type(entry))
                    else:
                        lines.append(line)

                except _crypttab_entry.ParseError:
                    lines.append(line)

    except (IOError, OSError) as exc:
        msg = "Couldn't read from {0}: {1}"
        raise CommandExecutionError(msg.format(config, exc))

    # add line if not present or changed
    if ret is None:
        lines.append(six.text_type(entry))
        ret = "new"

    if ret != "present":  # ret in ['new', 'change']:
        if not test:
            try:
                with salt.utils.files.fopen(config, "w+") as ofile:
                    # The line was changed, commit it!
                    ofile.writelines(
                        (salt.utils.stringutils.to_str(line) for line in lines)
                    )
            except (IOError, OSError):
                msg = "File not writable {0}"
                raise CommandExecutionError(msg.format(config))

    return ret


def open(name, device, keyfile):
    """
    Open a crypt device using ``cryptsetup``. The ``keyfile`` must not be
    ``None`` or ``'none'``, because ``cryptsetup`` will otherwise ask for the
    password interactively.

    CLI Example:

    .. code-block:: bash

        salt '*' cryptdev.open foo /dev/sdz1 /path/to/keyfile
    """
    if keyfile is None or keyfile == "none" or keyfile == "-":
        raise CommandExecutionError(
            "For immediate crypt device mapping, keyfile must not be none"
        )

    code = __salt__["cmd.retcode"](
        "cryptsetup open --key-file {0} {1} {2}".format(keyfile, device, name)
    )
    return code == 0


def close(name):
    """
    Close a crypt device using ``cryptsetup``.

    CLI Example:

    .. code-block:: bash

        salt '*' cryptdev.close foo
    """
    code = __salt__["cmd.retcode"]("cryptsetup close {0}".format(name))
    return code == 0
