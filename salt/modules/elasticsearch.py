# -*- coding: utf-8 -*-
'''
Connection module for Elasticsearch

:depends: elasticsearch
'''
from __future__ import absolute_import

# Import Python libs
import logging

log = logging.getLogger(__name__)

# Import third party libs
try:
    import elasticsearch
    logging.getLogger('elasticsearch').setLevel(logging.CRITICAL)
    HAS_ELASTICSEARCH = True
except ImportError:
    HAS_ELASTICSEARCH = False

from salt.ext.six import string_types


def __virtual__():
    '''
    Only load if elasticsearch libraries exist.
    '''
    if not HAS_ELASTICSEARCH:
        return False
    return True


def exists(index, id, doc_type='_all', hosts=None, profile='elasticsearch'):
    '''
    Check for the existence of an elasticsearch document specified by id in the
    index.

    CLI example::

        salt myminion elasticsearch.exists grafana-dash mydash profile='grafana'
    '''
    es = _get_instance(hosts, profile)
    try:
        return es.exists(index=index, id=id, doc_type=doc_type)
    except elasticsearch.exceptions.NotFoundError:
        return False


def index(index, doc_type, body, id=None, hosts=None, profile='elasticsearch'):
    '''
    Create or update an index with the specified body for the specified id.

    CLI example::

        salt myminion elasticsearch.index grafana-dash dashboard '{"user":"guest","group":"guest","body":"",...}' mydash profile='grafana'
    '''
    es = _get_instance(hosts, profile)
    return es.index(index=index, doc_type=doc_type, body=body, id=id)


def get(index, id, doc_type='_all', hosts=None, profile='elasticsearch'):
    '''
    Get the contents of the specifed id from the index.

    CLI example::

        salt myminion elasticsearch.get grafana-dash mydash profile='grafana'
    '''
    es = _get_instance(hosts, profile)
    return es.get(index=index, id=id, doc_type=doc_type)


def delete(index, doc_type, id, hosts=None, profile='elasticsearch'):
    '''
    Delete the document specified by the id in the index.

    CLI example::

        salt myminion elasticsearch.delete grafana-dash dashboard mydash profile='grafana'
    '''
    es = _get_instance(hosts, profile)
    try:
        es.delete(index=index, doc_type=doc_type, id=id)
        return True
    except elasticsearch.exceptions.NotFoundError:
        return True
    except Exception:
        return False


def _get_instance(hosts, profile):
    '''
    Return the elasticsearch instance
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        if _profile:
            hosts = _profile.get('host')
            if not hosts:
                hosts = _profile.get('hosts')
    if isinstance(hosts, string_types):
        hosts = [hosts]
    return elasticsearch.Elasticsearch(hosts)
