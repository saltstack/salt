# -*- coding: utf-8 -*-
'''
Common functions for working with RPM packages
'''

# Import python libs
from __future__ import absolute_import

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin


def combine_comments(comments):
    '''
    Given a list of comments, or a comment submitted as a string, return a
    single line of text containing all of the comments.
    '''
    if isinstance(comments, list):
        for idx in range(len(comments)):
            if not isinstance(comments[idx], six.string_types):
                comments[idx] = str(comments[idx])
    else:
        if not isinstance(comments, six.string_types):
            comments = [str(comments)]
        else:
            comments = [comments]
    return ' '.join(comments).strip()
