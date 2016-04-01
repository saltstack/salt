# -*- coding: utf-8 -*-
'''
Elasticsearch - A distributed RESTful search and analytics server

Module to provide Elasticsearch compatibility to Salt
(compatible with Elasticsearch version 1.5.2+)

.. versionadded:: 2015.8.0

:depends:       `elasticsearch-py <http://elasticsearch-py.readthedocs.org/en/latest/>`_

:configuration: This module accepts connection configuration details either as
    parameters or as configuration settings in /etc/salt/minion on the relevant
    minions:

    .. code-block:: yaml

        elasticsearch:
          host: '10.10.10.100:9200'

        elasticsearch:
          hosts:
            - '10.10.10.100:9200'
            - '10.10.10.101:9200'
            - '10.10.10.102:9200'

        elasticsearch:
          hosts:
            - '10.10.10.100:9200'
          number_of_shards: 1
          number_of_replicas: 0
          functions_blacklist:
            - 'saltutil.find_job'
            - 'pillar.items'
            - 'grains.items'


    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar.
'''

from __future__ import absolute_import
from salt.exceptions import CommandExecutionError

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


def _get_instance(hosts=None, profile=None):
    '''
    Return the elasticsearch instance
    '''
    es = None

    if profile is None:
        profile = 'elasticsearch'

    if isinstance(profile, string_types):
        _profile = __salt__['config.option'](profile, None)
    elif isinstance(profile, dict):
        _profile = profile
    if _profile:
        hosts = _profile.get('host', None)
        if not hosts:
            hosts = _profile.get('hosts', None)

    if not hosts:
        hosts = ['127.0.0.1:9200']
    if isinstance(hosts, string_types):
        hosts = [hosts]
    try:
        es = elasticsearch.Elasticsearch(hosts)
        if not es.ping():
            raise CommandExecutionError('Could not connect to Elasticsearch host/ cluster {0}, is it unhealthy?'.format(hosts))
    except elasticsearch.exceptions.ConnectionError:
        raise CommandExecutionError('Could not connect to Elasticsearch host/ cluster {0}'.format(hosts))
    return es


def alias_create(indices, alias, hosts=None, body=None, profile=None):
    '''
    Create an alias for a specific index/indices

    CLI example::

        salt myminion elasticsearch.alias_create testindex_v1 testindex
    '''
    es = _get_instance(hosts, profile)
    try:
        result = es.indices.put_alias(index=indices, name=alias, body=body)  # TODO error handling
        return True
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def alias_delete(indices, aliases, hosts=None, body=None, profile=None):
    '''
    Delete an alias of an index

    CLI example::

        salt myminion elasticsearch.alias_delete testindex_v1 testindex
    '''
    es = _get_instance(hosts, profile)
    try:
        result = es.indices.delete_alias(index=indices, name=aliases)

        if result.get('acknowledged', False):  # TODO error handling
            return True
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def alias_exists(aliases, indices=None, hosts=None, profile=None):
    '''
    Return a boolean indicating whether given alias exists

    CLI example::

        salt myminion elasticsearch.alias_exists testindex
    '''
    es = _get_instance(hosts, profile)
    try:
        if es.indices.exists_alias(name=aliases, index=indices):
            return True
        else:
            return False
    except elasticsearch.exceptions.NotFoundError:
        return None
    except elasticsearch.exceptions.ConnectionError:
        # TODO log error
        return None
    return None


def alias_get(indices=None, aliases=None, hosts=None, profile=None):
    '''
    Check for the existence of an alias and if it exists, return it

    CLI example::

        salt myminion elasticsearch.alias_get testindex
    '''
    es = _get_instance(hosts, profile)

    try:
        ret = es.indices.get_alias(index=indices, name=aliases)  # TODO error handling
        return ret
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def document_create(index, doc_type, body=None, id=None, hosts=None, profile=None):
    '''
    Create a document in a specified index

    CLI example::

        salt myminion elasticsearch.document_create testindex doctype1 '{}'
    '''
    es = _get_instance(hosts, profile)
    try:
        result = es.index(index=index, doc_type=doc_type, body=body, id=id)  # TODO error handling
        return True
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def document_delete(index, doc_type, id, hosts=None, profile=None):
    '''
    Delete a document from an index

    CLI example::

        salt myminion elasticsearch.document_delete testindex doctype1 AUx-384m0Bug_8U80wQZ
    '''
    es = _get_instance(hosts, profile)
    try:
        if not index_exists(index=index):
            return True
        else:
            result = es.delete(index=index, doc_type=doc_type, id=id)

            if result.get('found', False):  # TODO error handling
                return True
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def document_exists(index, id, doc_type='_all', hosts=None, profile=None):
    '''
    Return a boolean indicating whether given document exists

    CLI example::

        salt myminion elasticsearch.document_exists testindex AUx-384m0Bug_8U80wQZ
    '''
    es = _get_instance(hosts, profile)
    try:
        if es.exists(index=index, id=id, doc_type=doc_type):
            return True
        else:
            return False
    except elasticsearch.exceptions.NotFoundError:
        return None
    except elasticsearch.exceptions.ConnectionError:
        # TODO log error
        return None
    return None


def document_get(index, id, doc_type='_all', hosts=None, profile=None):
    '''
    Check for the existence of a document and if it exists, return it

    CLI example::

        salt myminion elasticsearch.document_get testindex AUx-384m0Bug_8U80wQZ
    '''
    es = _get_instance(hosts, profile)

    try:
        ret = es.get(index=index, id=id, doc_type=doc_type)  # TODO error handling
        return ret
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def index_create(index, body=None, hosts=None, profile=None):
    '''
    Create an index

    CLI example::

        salt myminion elasticsearch.index_create testindex
    '''
    es = _get_instance(hosts, profile)
    try:
        if index_exists(index):
            return True
        else:
            result = es.indices.create(index=index, body=body)  # TODO error handling
            return True
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def index_delete(index, hosts=None, profile=None):
    '''
    Delete an index

    CLI example::

        salt myminion elasticsearch.index_delete testindex
    '''
    es = _get_instance(hosts, profile)
    try:
        if not index_exists(index=index):
            return True
        else:
            result = es.indices.delete(index=index)

            if result.get('acknowledged', False):  # TODO error handling
                return True
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def index_exists(index, hosts=None, profile=None):
    '''
    Return a boolean indicating whether given index exists

    CLI example::

        salt myminion elasticsearch.index_exists testindex
    '''
    es = _get_instance(hosts, profile)
    try:
        if not isinstance(index, list):
            index = [index]
        if es.indices.exists(index=index):
            return True
        else:
            return False
    except elasticsearch.exceptions.NotFoundError:
        return None
    except elasticsearch.exceptions.ConnectionError:
        # TODO log error
        return None
    return None


def index_get(index, hosts=None, profile=None):
    '''
    Check for the existence of an index and if it exists, return it

    CLI example::

        salt myminion elasticsearch.index_get testindex
    '''
    es = _get_instance(hosts, profile)

    try:
        if index_exists(index):
            ret = es.indices.get(index=index)  # TODO error handling
            return ret
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def mapping_create(index, doc_type, body, hosts=None, profile=None):
    '''
    Create a mapping in a given index

    CLI example::

        salt myminion elasticsearch.mapping_create testindex user '{ "user" : { "properties" : { "message" : {"type" : "string", "store" : true } } } }'
    '''
    es = _get_instance(hosts, profile)
    try:
        result = es.indices.put_mapping(index=index, doc_type=doc_type, body=body)  # TODO error handling
        return mapping_get(index, doc_type)
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def mapping_delete(index, doc_type, hosts=None, profile=None):
    '''
    Delete a mapping (type) along with its data

    CLI example::

        salt myminion elasticsearch.mapping_delete testindex user
    '''
    es = _get_instance(hosts, profile)
    try:
        # TODO check if mapping exists, add method mapping_exists()
        result = es.indices.delete_mapping(index=index, doc_type=doc_type)

        if result.get('acknowledged', False):  # TODO error handling
            return True
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def mapping_get(index, doc_type, hosts=None, profile=None):
    '''
    Retrieve mapping definition of index or index/type

    CLI example::

        salt myminion elasticsearch.mapping_get testindex user
    '''
    es = _get_instance(hosts, profile)

    try:
        ret = es.indices.get_mapping(index=index, doc_type=doc_type)  # TODO error handling
        return ret
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def index_template_create(name, body, hosts=None, profile=None):
    '''
    Create an index template

    CLI example::

        salt myminion elasticsearch.index_template_create testindex_templ '{ "template": "logstash-*", "order": 1, "settings": { "number_of_shards": 1 } }'
    '''
    es = _get_instance(hosts, profile)
    try:
        result = es.indices.put_template(name=name, body=body)  # TODO error handling
        return True
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def index_template_delete(name, hosts=None, profile=None):
    '''
    Delete an index template (type) along with its data

    CLI example::

        salt myminion elasticsearch.index_template_delete testindex_templ user
    '''
    es = _get_instance(hosts, profile)
    try:
        # TODO check if template exists, add method template_exists() ?
        result = es.indices.delete_template(name=name)

        if result.get('acknowledged', False):  # TODO error handling
            return True
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def index_template_exists(name, hosts=None, profile=None):
    '''
    Return a boolean indicating whether given index template exists

    CLI example::

        salt myminion elasticsearch.index_template_exists testindex_templ
    '''
    es = _get_instance(hosts, profile)
    try:
        if es.indices.exists_template(name=name):
            return True
        else:
            return False
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None


def index_template_get(name, hosts=None, profile=None):
    '''
    Retrieve template definition of index or index/type

    CLI example::

        salt myminion elasticsearch.index_template_get testindex_templ user
    '''
    es = _get_instance(hosts, profile)

    try:
        ret = es.indices.get_template(name=name)  # TODO error handling
        return ret
    except elasticsearch.exceptions.NotFoundError:
        return None
    return None
