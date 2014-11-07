# -*- coding: utf-8 -*-
'''
Runner frontend to search system
'''

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
