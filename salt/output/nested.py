# -*- coding: utf-8 -*-
"""
Recursively display nested data
===============================

This is the default outputter for most execution functions.

Example output::

    myminion:
        ----------
        foo:
            ----------
            bar:
                baz
            dictionary:
                ----------
                abc:
                    123
                def:
                    456
            list:
                - Hello
                - World
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
from numbers import Number

# Import salt libs
import salt.output
import salt.utils.color
import salt.utils.odict
import salt.utils.stringutils
from salt.ext import six

try:
    from collections.abc import Mapping
except ImportError:
    # pylint: disable=no-name-in-module
    from collections import Mapping

    # pylint: enable=no-name-in-module


class NestDisplay(object):
    """
    Manage the nested display contents
    """

    def __init__(self, retcode=0):
        self.__dict__.update(
            salt.utils.color.get_colors(
                __opts__.get("color"), __opts__.get("color_theme")
            )
        )
        self.strip_colors = __opts__.get("strip_colors", True)
        self.retcode = retcode

    def ustring(self, indent, color, msg, prefix="", suffix="", endc=None):
        if endc is None:
            endc = self.ENDC

        indent *= " "
        fmt = "{0}{1}{2}{3}{4}{5}"

        try:
            return fmt.format(indent, color, prefix, msg, endc, suffix)
        except UnicodeDecodeError:
            try:
                return fmt.format(
                    indent,
                    color,
                    prefix,
                    salt.utils.stringutils.to_unicode(msg),
                    endc,
                    suffix,
                )
            except UnicodeDecodeError:
                # msg contains binary data that can't be decoded
                return str(fmt).format(  # future lint: disable=blacklisted-function
                    indent, color, prefix, msg, endc, suffix
                )

    def display(self, ret, indent, prefix, out):
        """
        Recursively iterate down through data structures to determine output
        """
        if isinstance(ret, bytes):
            try:
                ret = salt.utils.stringutils.to_unicode(ret)
            except UnicodeDecodeError:
                # ret contains binary data that can't be decoded
                pass

        if ret is None or ret is True or ret is False:
            out.append(self.ustring(indent, self.LIGHT_YELLOW, ret, prefix=prefix))
        # Number includes all python numbers types
        #  (float, int, long, complex, ...)
        # use repr() to get the full precision also for older python versions
        # as until about python32 it was limited to 12 digits only by default
        elif isinstance(ret, Number):
            out.append(
                self.ustring(indent, self.LIGHT_YELLOW, repr(ret), prefix=prefix)
            )
        elif isinstance(ret, six.string_types):
            first_line = True
            for line in ret.splitlines():
                line_prefix = " " * len(prefix) if not first_line else prefix
                if isinstance(line, bytes):
                    out.append(
                        self.ustring(
                            indent, self.YELLOW, "Not string data", prefix=line_prefix
                        )
                    )
                    break
                if self.strip_colors:
                    line = salt.output.strip_esc_sequence(line)
                out.append(self.ustring(indent, self.GREEN, line, prefix=line_prefix))
                first_line = False
        elif isinstance(ret, (list, tuple)):
            color = self.GREEN
            if self.retcode != 0:
                color = self.RED
            for ind in ret:
                if isinstance(ind, (list, tuple, Mapping)):
                    out.append(self.ustring(indent, color, "|_"))
                    prefix = "" if isinstance(ind, Mapping) else "- "
                    self.display(ind, indent + 2, prefix, out)
                else:
                    self.display(ind, indent, "- ", out)
        elif isinstance(ret, Mapping):
            if indent:
                color = self.CYAN
                if self.retcode != 0:
                    color = self.RED
                out.append(self.ustring(indent, color, "----------"))

            # respect key ordering of ordered dicts
            if isinstance(ret, salt.utils.odict.OrderedDict):
                keys = ret.keys()
            else:
                keys = sorted(ret)
            color = self.CYAN
            if self.retcode != 0:
                color = self.RED
            for key in keys:
                val = ret[key]
                out.append(self.ustring(indent, color, key, suffix=":", prefix=prefix))
                self.display(val, indent + 4, "", out)
        return out


def output(ret, **kwargs):
    """
    Display ret data
    """
    # Prefer kwargs before opts
    retcode = kwargs.get("_retcode", 0)
    base_indent = kwargs.get("nested_indent", 0) or __opts__.get("nested_indent", 0)
    nest = NestDisplay(retcode=retcode)
    lines = nest.display(ret, base_indent, "", [])
    try:
        return "\n".join(lines)
    except UnicodeDecodeError:
        # output contains binary data that can't be decoded
        return str("\n").join(  # future lint: disable=blacklisted-function
            [salt.utils.stringutils.to_str(x) for x in lines]
        )
