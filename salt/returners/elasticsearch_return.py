# -*- coding: utf-8 -*-
'''
Return data to an elasticsearch server for indexing.

:maintainer:    Jurnell Cockhren <jurnell.cockhren@sophicware.com>, Arnold Bechtoldt <mail@arnoldbechtoldt.com>
:maturity:      New
:depends:       `elasticsearch-py <https://elasticsearch-py.readthedocs.io/en/latest/>`_
:platform:      all

To enable this returner the elasticsearch python client must be installed
on the desired minions (all or some subset).

Please see documentation of :mod:`elasticsearch execution module <salt.modules.elasticsearch>`
for a valid connection configuration.

.. warning::

        The index that you wish to store documents will be created by Elasticsearch automatically if
        doesn't exist yet. It is highly recommended to create predefined index templates with appropriate mapping(s)
        that will be used by Elasticsearch upon index creation. Otherwise you will have problems as described in #20826.

To use the returner per salt call:

.. code-block:: bash

    salt '*' test.ping --return elasticsearch

In order to have the returner apply to all minions:

.. code-block:: yaml

    ext_job_cache: elasticsearch

Minion configuration example:

.. code-block:: yaml

    elasticsearch:
        hosts:
          - "10.10.10.10:9200"
          - "10.10.10.11:9200"
          - "10.10.10.12:9200"
        index_date: True
        number_of_shards: 5
        number_of_replicas: 1
        functions_blacklist:
          - "test.ping"

'''

# Import Python libs
from __future__ import absolute_import
import datetime
from datetime import tzinfo, timedelta
import uuid
import logging
import json

# Import Salt libs
import salt.returners
import salt.utils.jid

__virtualname__ = 'elasticsearch'

log = logging.getLogger(__name__)


def __virtual__():
    return 'elasticsearch.alias_exists' in __salt__


def _get_options(ret=None):
    '''
    Get the returner options from salt.
    '''

    defaults = {
        'debug_returner_payload': False,
        'doc_type': 'default',
        'functions_blacklist': [],
        'index_date': False,
        'master_event_index': 'salt-master-event-cache',
        'master_event_doc_type': 'default',
        'master_job_cache_index': 'salt-master-job-cache',
        'master_job_cache_doc_type': 'default',
        'number_of_shards': 1,
        'number_of_replicas': 0,
    }

    attrs = {
        'debug_returner_payload': 'debug_returner_payload',
        'doc_type': 'doc_type',
        'functions_blacklist': 'functions_blacklist',
        'index_date': 'index_date',
        'master_event_index': 'master_event_index',
        'master_event_doc_type': 'master_event_doc_type',
        'master_job_cache_index': 'master_job_cache_index',
        'master_job_cache_doc_type': 'master_job_cache_doc_type',
        'number_of_shards': 'number_of_shards',
        'number_of_replicas': 'number_of_replicas',
    }

    _options = salt.returners.get_returner_options(
        __virtualname__,
        ret,
        attrs,
        __salt__=__salt__,
        __opts__=__opts__,
        defaults=defaults)
    return _options


def _ensure_index(index):
    index_exists = __salt__['elasticsearch.index_exists'](index)
    if not index_exists:
        options = _get_options()

        index_definition = {
            'settings': {
                'number_of_shards': options['number_of_shards'],
                'number_of_replicas': options['number_of_replicas'],
            }
        }
        __salt__['elasticsearch.index_create']('{0}-v1'.format(index),
                                               index_definition)
        __salt__['elasticsearch.alias_create']('{0}-v1'.format(index), index)


def _convert_keys(data):
    if not isinstance(data, dict):
        return data

    new_data = {}
    for k, sub_data in data.items():
        if '.' in k:
            new_data['_orig_key'] = k
            k = k.replace('.', '_')

        new_data[k] = _convert_keys(sub_data)

    return new_data


def returner(ret):
    '''
    Process the return from Salt
    '''
    job_fun = ret['fun']
    job_fun_escaped = job_fun.replace('.', '_')
    job_id = ret['jid']
    job_minion_id = ret['id']
    job_success = True if ret['return'] else False
    job_retcode = ret.get('retcode', 1)

    options = _get_options(ret)

    index = 'salt-{0}'.format(job_fun_escaped)
    if options['index_date']:
        index = '{0}-{1}'.format(index,
            datetime.date.today().strftime('%Y.%m.%d'))

    if job_fun in options['functions_blacklist']:
        log.info(
            'Won\'t push new data to Elasticsearch, job with jid={0} and '
            'function={1} which is in the user-defined list of ignored '
            'functions'.format(job_id, job_fun))
        return

    if not job_success:
        log.info('Won\'t push new data to Elasticsearch, job with jid={0} was '
                 'not succesful'.format(job_id))
        return

    _ensure_index(index)

    class UTC(tzinfo):
        def utcoffset(self, dt):
            return timedelta(0)

        def tzname(self, dt):
            return 'UTC'

        def dst(self, dt):
            return timedelta(0)

    utc = UTC()
    data = {
        '@timestamp': datetime.datetime.now(utc).isoformat(),
        'success': job_success,
        'retcode': job_retcode,
        'minion': job_minion_id,
        'fun': job_fun,
        'jid': job_id,
        'data': _convert_keys(ret['return'])
    }

    if options['debug_returner_payload']:
        log.debug('Payload: {0}'.format(data))

    ret = __salt__['elasticsearch.document_create'](index=index,
                                                    doc_type=options['doc_type'],
                                                    body=json.dumps(data))


def event_return(events):
    '''
    Return events to Elasticsearch

    Requires that the `event_return` configuration be set in master config.
    '''
    options = _get_options()

    index = options['master_event_index']
    doc_type = options['master_event_doc_type']

    if options['index_date']:
        index = '{0}-{1}'.format(index,
            datetime.date.today().strftime('%Y.%m.%d'))

    _ensure_index(index)

    for event in events:
        data = {
            'tag': event.get('tag', ''),
            'data': event.get('data', '')
        }

    ret = __salt__['elasticsearch.document_create'](index=index,
                                                    doc_type=doc_type,
                                                    id=uuid.uuid4(),
                                                    body=json.dumps(data))


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid()


def save_load(jid, load, minions=None):
    '''
    Save the load to the specified jid id

    .. versionadded:: 2015.8.1
    '''
    options = _get_options()

    index = options['master_job_cache_index']
    doc_type = options['master_job_cache_doc_type']

    _ensure_index(index)

    data = {
        'jid': jid,
        'load': load,
    }

    ret = __salt__['elasticsearch.document_create'](index=index,
                                                    doc_type=doc_type,
                                                    id=jid,
                                                    body=json.dumps(data))


def get_load(jid):
    '''
    Return the load data that marks a specified jid

    .. versionadded:: 2015.8.1
    '''
    options = _get_options()

    index = options['master_job_cache_index']
    doc_type = options['master_job_cache_doc_type']

    data = __salt__['elasticsearch.document_get'](index=index,
                                                  id=jid,
                                                  doc_type=doc_type)
    if data:
        return json.loads(data)
    return {}
