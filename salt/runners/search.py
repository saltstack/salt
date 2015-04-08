# -*- coding: utf-8 -*-
'''
Runner frontend to search system
'''
from __future__ import absolute_import

# Import salt libs
import salt.search


def query(term):
    '''
    Query the search system

    CLI Example:

    .. code-block:: bash

        salt-run search.query foo
    '''
    search = salt.search.Search(__opts__)
    result = search.query(term)
    return result
