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

Minion configuration:
    debug_returner_payload': False
        Output the payload being posted to the log file in debug mode

    doc_type: 'default'
        Document type to use for normal return messages

    functions_blacklist
        Optional list of functions that should not be returned to elasticsearch

    index_date: False
        Use a dated index (e.g. <index>-2016.11.29)

    master_event_index: 'salt-master-event-cache'
        Index to use when returning master events

    master_event_doc_type: 'efault'
        Document type to use got master events

    master_job_cache_index: 'salt-master-job-cache'
        Index to use for master job cache

    master_job_cache_doc_type: 'default'
        Document type to use for master job cache

    number_of_shards: 1
        Number of shards to use for the indexes

    number_of_replicas: 0
        Number of replicas to use for the indexes

    NOTE: The following options are valid for 'state.apply', 'state.sls' and 'state.highstate' functions only.

    states_count: False
        Count the number of states which succeeded or failed and return it in top-level item called 'counts'.
        States reporting None (i.e. changes would be made but it ran in test mode) are counted as successes.
    states_order_output: False
        Prefix the state UID (e.g. file_|-yum_configured_|-/etc/yum.conf_|-managed) with a zero-padded version
        of the '__run_num__' value to allow for easier sorting. Also store the state function (i.e. file.managed)
        into a new key '_func'. Change the index to be '<index>-ordered' (e.g. salt-state_apply-ordered).
    states_single_index: False
        Store results for state.apply, state.sls and state.highstate in the salt-state_apply index
        (or -ordered/-<date>) indexes if enabled

.. code-block:: yaml

    elasticsearch:
        hosts:
          - "10.10.10.10:9200"
          - "10.10.10.11:9200"
          - "10.10.10.12:9200"
        index_date: True
        number_of_shards: 5
        number_of_replicas: 1
        debug_returner_payload: True
        states_count: True
        states_order_output: True
        states_single_index: True
        functions_blacklist:
          - test.ping
          - saltutil.find_job
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import datetime
from datetime import tzinfo, timedelta
import uuid
import logging

# Import Salt libs
import salt.returners
import salt.utils.jid
import salt.utils.json

# Import 3rd-party libs
from salt.ext import six

__virtualname__ = 'elasticsearch'

log = logging.getLogger(__name__)

STATE_FUNCTIONS = {
    'state.apply':     'state_apply',
    'state.highstate': 'state_apply',
    'state.sls':       'state_apply',
}


def __virtual__():
    return __virtualname__


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
        'states_order_output': False,
        'states_count': False,
        'states_single_index': False,
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
        'states_count': 'states_count',
        'states_order_output': 'states_order_output',
        'states_single_index': 'states_single_index',
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
    if isinstance(data, dict):
        new_data = {}
        for k, sub_data in data.items():
            if '.' in k:
                new_data['_orig_key'] = k
                k = k.replace('.', '_')
            new_data[k] = _convert_keys(sub_data)
    elif isinstance(data, list):
        new_data = []
        for item in data:
            new_data.append(_convert_keys(item))
    else:
        return data

    return new_data


def returner(ret):
    '''
    Process the return from Salt
    '''

    job_fun = ret['fun']
    job_fun_escaped = job_fun.replace('.', '_')
    job_id = ret['jid']
    job_retcode = ret.get('retcode', 1)
    job_success = True if not job_retcode else False

    options = _get_options(ret)

    if job_fun in options['functions_blacklist']:
        log.info(
            'Won\'t push new data to Elasticsearch, job with jid=%s and '
            'function=%s which is in the user-defined list of ignored '
            'functions', job_id, job_fun
        )
        return

    if ret.get('return', None) is None:
        log.info(
            'Won\'t push new data to Elasticsearch, job with jid=%s was '
            'not succesful', job_id
        )
        return

    # Build the index name
    if options['states_single_index'] and job_fun in STATE_FUNCTIONS:
        index = 'salt-{0}'.format(STATE_FUNCTIONS[job_fun])
    else:
        index = 'salt-{0}'.format(job_fun_escaped)

    if options['index_date']:
        index = '{0}-{1}'.format(index,
            datetime.date.today().strftime('%Y.%m.%d'))

    counts = {}

    # Do some special processing for state returns
    if job_fun in STATE_FUNCTIONS:
        # Init the state counts
        if options['states_count']:
            counts = {
                'suceeded': 0,
                'failed':   0,
            }

        # Prepend each state execution key in ret['return'] with a zero-padded
        # version of the '__run_num__' field allowing the states to be ordered
        # more easily. Change the index to be
        # index to be '<index>-ordered' so as not to clash with the unsorted
        # index data format
        if options['states_order_output'] and isinstance(ret['return'], dict):
            index = '{0}-ordered'.format(index)
            max_chars = len(six.text_type(len(ret['return'])))

            for uid, data in six.iteritems(ret['return']):
                # Skip keys we've already prefixed
                if uid.startswith(tuple('0123456789')):
                    continue

                # Store the function being called as it's a useful key to search
                decoded_uid = uid.split('_|-')
                ret['return'][uid]['_func'] = '{0}.{1}'.format(
                    decoded_uid[0],
                    decoded_uid[-1]
                )

                # Prefix the key with the run order so it can be sorted
                new_uid = '{0}_|-{1}'.format(
                    six.text_type(data['__run_num__']).zfill(max_chars),
                    uid,
                )

                ret['return'][new_uid] = ret['return'].pop(uid)

        # Catch a state output that has failed and where the error message is
        # not in a dict as expected. This prevents elasticsearch from
        # complaining about a mapping error
        elif not isinstance(ret['return'], dict):
            ret['return'] = {'return': ret['return']}

        # Need to count state successes and failures
        if options['states_count']:
            for state_data in ret['return'].values():
                if state_data['result'] is False:
                    counts['failed'] += 1
                else:
                    counts['suceeded'] += 1

    # Ensure the index exists
    _ensure_index(index)

    # Build the payload
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
        'minion': ret['id'],
        'fun': job_fun,
        'jid': job_id,
        'counts': counts,
        'data': _convert_keys(ret['return'])
    }

    if options['debug_returner_payload']:
        log.debug('elasicsearch payload: %s', data)

    # Post the payload
    ret = __salt__['elasticsearch.document_create'](index=index,
                                                    doc_type=options['doc_type'],
                                                    body=salt.utils.json.dumps(data))


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
                                                    body=salt.utils.json.dumps(data))


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)


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
                                                    body=salt.utils.json.dumps(data))


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
        return salt.utils.json.loads(data)
    return {}
