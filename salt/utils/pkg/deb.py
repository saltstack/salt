# -*- coding: utf-8 -*-
'''
Common functions for working with deb packages
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

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
                comments[idx] = six.text_type(comments[idx])
    else:
        if not isinstance(comments, six.string_types):
            comments = [six.text_type(comments)]
        else:
            comments = [comments]
    return ' '.join(comments).strip()


def strip_uri(repo):
    '''
    Remove the trailing slash from the URI in a repo definition
    '''
    splits = repo.split()
    for idx in range(len(splits)):
        if any(splits[idx].startswith(x)
               for x in ('http://', 'https://', 'ftp://')):
            splits[idx] = splits[idx].rstrip('/')
    return ' '.join(splits)
