# -*- coding: utf-8 -*-
'''
Return data to a redis server

To enable this returner the minion will need the python client for redis
installed and the following values configured in the minion or master
config, these are the defaults:

.. code-block:: yaml

    redis.db: '0'
    redis.host: 'salt'
    redis.port: 6379

Cluster Mode Example:

.. code-block::yaml

    redis.db: '0'
    redis.cluster_mode: true
    redis.cluster.skip_full_coverage_check: true
    redis.cluster.startup_nodes:
      - host: redis-member-1
        port: 6379
      - host: redis-member-2
        port: 6379

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location:

.. code-block:: yaml

    alternative.redis.db: '0'
    alternative.redis.host: 'salt'
    alternative.redis.port: 6379

To use the redis returner, append '--return redis' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return redis

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return redis --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return redis --return_kwargs '{"db": "another-salt"}'

Redis Cluster Mode Options:

cluster_mode: ``False``
    Whether cluster_mode is enabled or not

cluster.startup_nodes:
    A list of host, port dictionaries pointing to cluster members. At least one is required
    but multiple nodes are better

    .. code-block::yaml

        cache.redis.cluster.startup_nodes
          - host: redis-member-1
            port: 6379
          - host: redis-member-2
            port: 6379

cluster.skip_full_coverage_check: ``False``
    Some cluster providers restrict certain redis commands such as CONFIG for enhanced security.
    Set this option to true to skip checks that required advanced privileges.

    .. note::

        Most cloud hosted redis clusters will require this to be set to ``True``


'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt libs
import salt.returners
import salt.utils.jid
import salt.utils.json
import salt.utils.platform

# Import 3rd-party libs
from salt.ext import six
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

log = logging.getLogger(__name__)

try:
    from rediscluster import StrictRedisCluster
    HAS_REDIS_CLUSTER = True
except ImportError:
    HAS_REDIS_CLUSTER = False

# Define the module's virtual name
__virtualname__ = 'redis'


def __virtual__():
    '''
    The redis library must be installed for this module to work.

    The redis redis cluster library must be installed if cluster_mode is True
    '''

    if not HAS_REDIS:
        return False, 'Could not import redis returner; ' \
                      'redis python client is not installed.'
    if not HAS_REDIS_CLUSTER and _get_options()['cluster_mode']:
        return (False, "Please install the redis-py-cluster package.")
    return __virtualname__


def _get_options(ret=None):
    '''
    Get the redis options from salt.
    '''
    attrs = {'host': 'host',
             'port': 'port',
             'db': 'db',
             'cluster_mode': 'cluster_mode',
             'startup_nodes': 'cluster.startup_nodes',
             'skip_full_coverage_check': 'cluster.skip_full_coverage_check',
        }

    if salt.utils.platform.is_proxy():
        return {
            'host': __opts__.get('redis.host', 'salt'),
            'port': __opts__.get('redis.port', 6379),
            'db': __opts__.get('redis.db', '0'),
            'cluster_mode': __opts__.get('redis.cluster_mode', False),
            'startup_nodes': __opts__.get('redis.cluster.startup_nodes', {}),
            'skip_full_coverage_check': __opts__.get('redis.cluster.skip_full_coverage_check', False)
        }

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


CONN_POOL = None


def _get_conn_pool(_options):
    global CONN_POOL
    if CONN_POOL is None:
        CONN_POOL = redis.ConnectionPool(host=_options.get('host'),
                                         port=_options.get('port'),
                                         db=_options.get('db'))
    return CONN_POOL


def _get_serv(ret=None):
    '''
    Return a redis server object
    '''
    _options = _get_options(ret)

    if _options.get('cluster_mode'):
        return StrictRedisCluster(startup_nodes=_options.get('startup_nodes'),
                                  skip_full_coverage_check=_options.get('skip_full_coverage_check'),
                                  decode_responses=True)
    else:
        pool = _get_conn_pool(_options)
        return redis.StrictRedis(connection_pool=pool)


def _get_ttl():
    return __opts__.get('keep_jobs', 24) * 3600


def returner(ret):
    '''
    Return data to a redis data store
    '''
    serv = _get_serv(ret)
    pipeline = serv.pipeline(transaction=False)
    minion, jid = ret['id'], ret['jid']
    pipeline.hset('ret:{0}'.format(jid), minion, salt.utils.json.dumps(ret))
    pipeline.expire('ret:{0}'.format(jid), _get_ttl())
    pipeline.set('{0}:{1}'.format(minion, ret['fun']), jid)
    pipeline.sadd('minions', minion)
    pipeline.execute()


def save_load(jid, load, minions=None):
    '''
    Save the load to the specified jid
    '''
    serv = _get_serv(ret=None)
    serv.setex('load:{0}'.format(jid), _get_ttl(), salt.utils.json.dumps(load))


def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
    '''
    Included for API consistency
    '''
    pass


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    serv = _get_serv(ret=None)
    data = serv.get('load:{0}'.format(jid))
    if data:
        return salt.utils.json.loads(data)
    return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    serv = _get_serv(ret=None)
    ret = {}
    for minion, data in six.iteritems(serv.hgetall('ret:{0}'.format(jid))):
        if data:
            ret[minion] = salt.utils.json.loads(data)
    return ret


def get_fun(fun):
    '''
    Return a dict of the last function called for all minions
    '''
    serv = _get_serv(ret=None)
    ret = {}
    for minion in serv.smembers('minions'):
        ind_str = '{0}:{1}'.format(minion, fun)
        try:
            jid = serv.get(ind_str)
        except Exception:
            continue
        if not jid:
            continue
        data = serv.get('{0}:{1}'.format(minion, jid))
        if data:
            ret[minion] = salt.utils.json.loads(data)
    return ret


def get_jids():
    '''
    Return a dict mapping all job ids to job information
    '''
    serv = _get_serv(ret=None)
    ret = {}
    for s in serv.mget(serv.keys('load:*')):
        if s is None:
            continue
        load = salt.utils.json.loads(s)
        jid = load['jid']
        ret[jid] = salt.utils.jid.format_jid_instance(jid, load)
    return ret


def get_minions():
    '''
    Return a list of minions
    '''
    serv = _get_serv(ret=None)
    return list(serv.smembers('minions'))


def clean_old_jobs():
    '''
    Clean out minions's return data for old jobs.

    Normally, hset 'ret:<jid>' are saved with a TTL, and will eventually
    get cleaned by redis.But for jobs with some very late minion return, the
    corresponding hset's TTL will be refreshed to a too late timestamp, we'll
    do manually cleaning here.
    '''
    serv = _get_serv(ret=None)
    ret_jids = serv.keys('ret:*')
    living_jids = set(serv.keys('load:*'))
    to_remove = []
    for ret_key in ret_jids:
        load_key = ret_key.replace('ret:', 'load:', 1)
        if load_key not in living_jids:
            to_remove.append(ret_key)
    if len(to_remove) != 0:
        serv.delete(*to_remove)
        log.debug('clean old jobs: %s', to_remove)


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)
