# -*- coding: utf-8 -*-
from __future__ import absolute_import
import re
import salt.ext.six as six


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
