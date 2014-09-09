#! -*- coding: utf-8 -*-
'''
Return data to an elasticsearch server for indexing.

:maintainer:    Jurnell Cockhren <jurnell.cockhren@sophicware.com>
:maturity:      New
:depends:       `elasticsearch-py <http://elasticsearch-py.readthedocs.org/en/latest/>`_,  `jsonpickle <https://pypi.python.org/pypi/jsonpickle>`_
:platform:      all

To enable this returner the elasticsearch python client must be installed
on the desired minions (all or some subset).

The required configuration is as follows:

.. code-block:: yaml

    elasticsearch:
      host: 'somehost.example.com:9200'
      index: 'salt'
      number_of_shards: 1 (optional)
      number_of_replicas: 0 (optional)

or to specify multiple elasticsearch hosts for resiliency:

.. code-block:: yaml

    elasticsearch:
      host:
        - 'somehost.example.com:9200'
        - 'anotherhost.example.com:9200'
        - 'yetanotherhost.example.com:9200'
      index: 'salt'
      number_of_shards: 1 (optional)
      number_of_replicas: 0 (optional)

The above configuration can be placed in a targeted pillar, minion or
master configurations.

To use the returner per salt call:

.. code-block:: bash

    salt '*' test.ping --return elasticsearch

In order to have the returner apply to all minions:

.. code-block:: yaml

    ext_job_cache: elasticsearch
'''

import datetime

__virtualname__ = 'elasticsearch'

try:
    import elasticsearch
    HAS_ELASTICSEARCH = True
except ImportError:
    HAS_ELASTICSEARCH = False

try:
    from jsonpickle.pickler import Pickler
    HAS_PICKLER = True
except ImportError:
    HAS_PICKLER = False


def _create_index(client, index):
    # create empty index
    client.indices.create(
        index=index,
        body={
            'settings': {
                'number_of_shards': __salt__['config.get']('elasticsearch:number_of_shards') or 1,
                'number_of_replicas': __salt__['config.get']('elasticsearch:number_of_replicas') or 0,
            },
            'mappings': {
                'returner': {
                    'properties': {
                        '@timestamp': {
                            'type': 'date'
                        },
                        'success': {
                            'type': 'boolean'
                        },
                        'id': {
                            'type': 'string'
                        },
                        'retcode': {
                            'type': 'integer'
                        },
                        'fun': {
                            'type': 'string'
                        },
                        'jid': {
                            'type': 'string'
                        }
                    }
                }
            }
        },
        ignore=400
    )


def __virtual__():
    if HAS_ELASTICSEARCH and HAS_PICKLER:
        return __virtualname__
    return False


def _get_pickler():
    return Pickler(max_depth=5)


def _get_instance():
    # Check whether we have a single elasticsearch host string, or a list of host strings.
    if isinstance(__salt__['config.get']('elasticsearch:host'), list):
        return elasticsearch.Elasticsearch(__salt__['config.get']('elasticsearch:host'))
    else:
        return elasticsearch.Elasticsearch([__salt__['config.get']('elasticsearch:host')])


def returner(ret):
    es = _get_instance()
    _create_index(es, __salt__['config.get']('elasticsearch:index'))
    r = ret
    the_time = datetime.datetime.now().isoformat()
    r['@timestamp'] = the_time
    es.index(index=__salt__['config.get']('elasticsearch:index'),
             doc_type='returner',
             body=_get_pickler().flatten(r),
             )
