# -*- coding: utf-8 -*-
'''
Functions for analyzing/parsing docstrings
'''

from __future__ import absolute_import
import re
from salt.ext import six


def strip_rst(docs):
    '''
    Strip/replace reStructuredText directives in docstrings
    '''
    for func, docstring in six.iteritems(docs):
        if not docstring:
            continue
        docstring_new = re.sub(r' *.. code-block:: \S+\n{1,2}',
                               '', docstring)
        docstring_new = re.sub('.. note::',
                               'Note:', docstring_new)
        docstring_new = re.sub('.. warning::',
                               'Warning:', docstring_new)
        docstring_new = re.sub('.. versionadded::',
                               'New in version', docstring_new)
        docstring_new = re.sub('.. versionchanged::',
                               'Changed in version', docstring_new)
        if docstring != docstring_new:
            docs[func] = docstring_new
    return docs


def parse_docstring(docstring):
    '''
    Parse a docstring into its parts.

    Currently only parses dependencies, can be extended to parse whatever is
    needed.

    Parses into a dictionary:
        {
            'full': full docstring,
            'deps': list of dependencies (empty list if none)
        }
    '''
    # First try with regex search for :depends:
    ret = {'full': docstring}
    regex = r'([ \t]*):depends:[ \t]+- (\w+)[^\n]*\n(\1[ \t]+- (\w+)[^\n]*\n)*'
    match = re.search(regex, docstring, re.M)
    if match:
        deps = []
        regex = r'- (\w+)'
        for line in match.group(0).strip().splitlines():
            deps.append(re.search(regex, line).group(1))
        ret['deps'] = deps
        return ret
    # Try searching for a one-liner instead
    else:
        txt = 'Required python modules: '
        data = docstring.splitlines()
        dep_list = list(x for x in data if x.strip().startswith(txt))
        if not dep_list:
            ret['deps'] = []
            return ret
        deps = dep_list[0].replace(txt, '').strip().split(', ')
        ret['deps'] = deps
        return ret
