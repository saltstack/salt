# -*- coding: utf-8 -*-
'''
Guard that checks for AWS resources being managed multiple times.
This is only enabled for AWS resources as for some kinds of resources,
it can make sense to have multiple states managing them (e.g. file states).
'''
from __future__ import absolute_import

# Import Python libs
import collections
import logging

# Import Salt libs
from salt.ext import six

log = logging.getLogger(__name__)


def check_chunks(chunks):
    resources = collections.defaultdict(lambda: collections.defaultdict(set))
    for chunk in chunks:
        if chunk['state'].startswith('boto_'):
            # Have to use the full_func and not just the chunk['state'],
            # as some state modules manage multiple kinds of resources,
            # e.g. users and groups and roles for boto_iam.
            full_func = '{0}.{1}'.format(chunk['state'], chunk['fun'])
            resources[full_func][chunk['name']].add(chunk['__id__'])

    errors = []
    for state_func, names in six.iteritems(resources):
        for name, ids in six.iteritems(names):
            if len(ids) > 1:
                msg = (
                    u'Multiple {0} states found for resource with name {1}, '
                    u'with ids: '
                ).format(state_func, name)
                lines = [msg] + ['  - {0}'.format(id) for id in ids]
                errors.append('\n'.join(lines))

    return errors


def check_state(chunk):
    return []
