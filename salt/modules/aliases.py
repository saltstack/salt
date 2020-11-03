# -*- coding: utf-8 -*-
"""
Manage the information in the aliases file
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import os
import re
import stat
import tempfile

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError

# Import third party libs
from salt.ext import six

__outputter__ = {
    "rm_alias": "txt",
    "has_target": "txt",
    "get_target": "txt",
    "set_target": "txt",
    "list_aliases": "yaml",
}

__ALIAS_RE = re.compile(r"([^:#]*)\s*:?\s*([^#]*?)(\s+#.*|$)")


def __get_aliases_filename():
    """
    Return the path to the appropriate aliases file
    """
    return os.path.realpath(__salt__["config.option"]("aliases.file"))


def __parse_aliases():
    """
    Parse the aliases file, and return a list of line components:

    [
      (alias1, target1, comment1),
      (alias2, target2, comment2),
    ]
    """
    afn = __get_aliases_filename()
    ret = []
    if not os.path.isfile(afn):
        return ret
    with salt.utils.files.fopen(afn, "r") as ifile:
        for line in ifile:
            line = salt.utils.stringutils.to_unicode(line)
            match = __ALIAS_RE.match(line)
            if match:
                ret.append(match.groups())
            else:
                ret.append((None, None, line.strip()))
    return ret


def __write_aliases_file(lines):
    """
    Write a new copy of the aliases file.  Lines is a list of lines
    as returned by __parse_aliases.
    """
    afn = __get_aliases_filename()
    adir = os.path.dirname(afn)

    out = tempfile.NamedTemporaryFile(dir=adir, delete=False)

    if not __opts__.get("integration.test", False):
        if os.path.isfile(afn):
            afn_st = os.stat(afn)
            os.chmod(out.name, stat.S_IMODE(afn_st.st_mode))
            os.chown(out.name, afn_st.st_uid, afn_st.st_gid)
        else:
            os.chmod(out.name, 0o644)
            os.chown(out.name, 0, 0)

    for (line_alias, line_target, line_comment) in lines:
        if isinstance(line_target, list):
            line_target = ", ".join(line_target)
        if not line_comment:
            line_comment = ""
        if line_alias and line_target:
            write_line = "{0}: {1}{2}\n".format(line_alias, line_target, line_comment)
        else:
            write_line = "{0}\n".format(line_comment)
        if six.PY3:
            write_line = write_line.encode(__salt_system_encoding__)
        out.write(write_line)

    out.close()
    os.rename(out.name, afn)

    # Search $PATH for the newalises command
    newaliases = salt.utils.path.which("newaliases")
    if newaliases is not None:
        __salt__["cmd.run"](newaliases)

    return True


def list_aliases():
    """
    Return the aliases found in the aliases file in this format::

        {'alias': 'target'}

    CLI Example:

    .. code-block:: bash

        salt '*' aliases.list_aliases
    """
    ret = dict((alias, target) for alias, target, comment in __parse_aliases() if alias)
    return ret


def get_target(alias):
    """
    Return the target associated with an alias

    CLI Example:

    .. code-block:: bash

        salt '*' aliases.get_target alias
    """
    aliases = list_aliases()
    if alias in aliases:
        return aliases[alias]
    return ""


def has_target(alias, target):
    """
    Return true if the alias/target is set

    CLI Example:

    .. code-block:: bash

        salt '*' aliases.has_target alias target
    """
    if target == "":
        raise SaltInvocationError("target can not be an empty string")
    aliases = list_aliases()
    if alias not in aliases:
        return False
    if isinstance(target, list):
        target = ", ".join(target)
    return target == aliases[alias]


def set_target(alias, target):
    """
    Set the entry in the aliases file for the given alias, this will overwrite
    any previous entry for the given alias or create a new one if it does not
    exist.

    CLI Example:

    .. code-block:: bash

        salt '*' aliases.set_target alias target
    """

    if alias == "":
        raise SaltInvocationError("alias can not be an empty string")

    if target == "":
        raise SaltInvocationError("target can not be an empty string")

    if get_target(alias) == target:
        return True

    lines = __parse_aliases()
    out = []
    ovr = False
    for (line_alias, line_target, line_comment) in lines:
        if line_alias == alias:
            if not ovr:
                out.append((alias, target, line_comment))
                ovr = True
        else:
            out.append((line_alias, line_target, line_comment))
    if not ovr:
        out.append((alias, target, ""))

    __write_aliases_file(out)
    return True


def rm_alias(alias):
    """
    Remove an entry from the aliases file

    CLI Example:

    .. code-block:: bash

        salt '*' aliases.rm_alias alias
    """
    if not get_target(alias):
        return True

    lines = __parse_aliases()
    out = []
    for (line_alias, line_target, line_comment) in lines:
        if line_alias != alias:
            out.append((line_alias, line_target, line_comment))

    __write_aliases_file(out)
    return True
