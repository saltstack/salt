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
