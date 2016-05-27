# -*- coding: utf-8 -*-
'''
Return data to an elasticsearch server for indexing.

:maintainer:    Jurnell Cockhren <jurnell.cockhren@sophicware.com>, Arnold Bechtoldt <mail@arnoldbechtoldt.com>
:maturity:      New
:depends:       `elasticsearch-py <http://elasticsearch-py.readthedocs.org/en/latest/>`_
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
'''

# Import Python libs
from __future__ import absolute_import
from datetime import tzinfo, datetime, timedelta
import uuid
import logging
import json

# Import Salt libs
import salt.utils.jid

__virtualname__ = 'elasticsearch'

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def _ensure_index(index):
    index_exists = __salt__['elasticsearch.index_exists'](index)
    if not index_exists:
        number_of_shards = __salt__['config.option'](
            'elasticsearch:number_of_shards', 1)
        number_of_replicas = __salt__['config.option'](
            'elasticsearch:number_of_replicas', 0)

        index_definition = {
            'settings': {
                'number_of_shards': number_of_shards,
                'number_of_replicas': number_of_replicas
            }
        }
        __salt__['elasticsearch.index_create']('{0}-v1'.format(index),
                                               index_definition)
        __salt__['elasticsearch.alias_create']('{0}-v1'.format(index), index)


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

    index = 'salt-{0}'.format(job_fun_escaped)
    #index = 'salt-{0}-{1}'.format(job_fun_escaped, datetime.date.today().strftime('%Y.%m.%d')) #TODO prefer this? #TODO make it configurable!
    functions_blacklist = __salt__['config.option'](
        'elasticsearch:functions_blacklist', [])
    doc_type_version = __salt__['config.option'](
        'elasticsearch:doc_type', 'default')

    if job_fun in functions_blacklist:
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
        '@timestamp': datetime.now(utc).isoformat(),
        'success': job_success,
        'retcode': job_retcode,
        'minion': job_minion_id,
        'fun': job_fun,
        'jid': job_id,
        'data': ret['return'],
    }

    ret = __salt__['elasticsearch.document_create'](index=index,
                                                    doc_type=doc_type_version,
                                                    body=json.dumps(data))


def event_return(events):
    '''
    Return events to Elasticsearch

    Requires that the `event_return` configuration be set in master config.
    '''
    index = __salt__['config.option'](
        'elasticsearch:master_event_index',
        'salt-master-event-cache')
    doc_type = __salt__['config.option'](
        'elasticsearch:master_event_doc_type',
        'default'
    )

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


def save_load(jid, load):
    '''
    Save the load to the specified jid id

    .. versionadded:: 2015.8.1
    '''
    index = __salt__['config.option'](
        'elasticsearch:master_job_cache_index',
        'salt-master-job-cache')
    doc_type = __salt__['config.option'](
        'elasticsearch:master_job_cache_doc_type',
        'default')

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
    index = __salt__['config.option'](
        'elasticsearch:master_job_cache_index',
        'salt-master-job-cache')
    doc_type = __salt__['config.option'](
        'elasticsearch:master_job_cache_doc_type',
        'default')

    data = __salt__['elasticsearch.document_get'](index=index,
                                                  id=jid,
                                                  doc_type=doc_type)
    if data:
        return json.loads(data)
    return {}
