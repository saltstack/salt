# -*- coding: utf-8 -*-
"""
Functions for analyzing/parsing docstrings
"""

from __future__ import absolute_import, print_function, unicode_literals

import logging
import re

import salt.utils.data
from salt.ext import six

log = logging.getLogger(__name__)


def strip_rst(docs):
    """
    Strip/replace reStructuredText directives in docstrings
    """
    for func, docstring in six.iteritems(docs):
        log.debug("Stripping docstring for %s", func)
        if not docstring:
            continue
        docstring_new = docstring if six.PY3 else salt.utils.data.encode(docstring)
        for regex, repl in (
            (r" *.. code-block:: \S+\n{1,2}", ""),
            (".. note::", "Note:"),
            (".. warning::", "Warning:"),
            (".. versionadded::", "New in version"),
            (".. versionchanged::", "Changed in version"),
        ):
            if six.PY2:
                regex = salt.utils.data.encode(regex)
                repl = salt.utils.data.encode(repl)
            try:
                docstring_new = re.sub(regex, repl, docstring_new)
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "Exception encountered while matching regex %r to "
                    "docstring for function %s",
                    regex,
                    func,
                    exc_info=True,
                )
        if six.PY2:
            docstring_new = salt.utils.data.decode(docstring_new)
        if docstring != docstring_new:
            docs[func] = docstring_new
    return docs


def parse_docstring(docstring):
    """
    Parse a docstring into its parts.

    Currently only parses dependencies, can be extended to parse whatever is
    needed.

    Parses into a dictionary:
        {
            'full': full docstring,
            'deps': list of dependencies (empty list if none)
        }
    """
    # First try with regex search for :depends:
    ret = {"full": docstring}
    regex = r"([ \t]*):depends:[ \t]+- (\w+)[^\n]*\n(\1[ \t]+- (\w+)[^\n]*\n)*"
    match = re.search(regex, docstring, re.M)
    if match:
        deps = []
        regex = r"- (\w+)"
        for line in match.group(0).strip().splitlines():
            deps.append(re.search(regex, line).group(1))
        ret["deps"] = deps
        return ret
    # Try searching for a one-liner instead
    else:
        txt = "Required python modules: "
        data = docstring.splitlines()
        dep_list = list(x for x in data if x.strip().startswith(txt))
        if not dep_list:
            ret["deps"] = []
            return ret
        deps = dep_list[0].replace(txt, "").strip().split(", ")
        ret["deps"] = deps
        return ret
