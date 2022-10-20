"""
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

        elasticsearch-cluster:
          hosts:
            - '10.10.10.100:9200'
            - '10.10.10.101:9200'
            - '10.10.10.102:9200'

        elasticsearch-extra:
          hosts:
            - '10.10.10.100:9200'
          use_ssl: True
          verify_certs: True
          ca_certs: /path/to/custom_ca_bundle.pem
          number_of_shards: 1
          number_of_replicas: 0
          functions_blacklist:
            - 'saltutil.find_job'
            - 'pillar.items'
            - 'grains.items'
          proxies:
            - http: http://proxy:3128
            - https: http://proxy:1080

    When specifying proxies the requests backend will be used and the 'proxies'
    data structure is passed as-is to that module.

    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar.

    Some functionality might be limited by elasticsearch-py and Elasticsearch server versions.
"""


import logging

from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

try:
    import elasticsearch

    # pylint: disable=no-name-in-module
    from elasticsearch import RequestsHttpConnection

    # pylint: enable=no-name-in-module

    logging.getLogger("elasticsearch").setLevel(logging.CRITICAL)
    HAS_ELASTICSEARCH = True
except ImportError:
    HAS_ELASTICSEARCH = False


def __virtual__():
    """
    Only load if elasticsearch libraries exist.
    """
    if not HAS_ELASTICSEARCH:
        return (
            False,
            "Cannot load module elasticsearch: elasticsearch libraries not found",
        )
    return True


def _get_instance(hosts=None, profile=None):
    """
    Return the elasticsearch instance
    """
    es = None
    proxies = None
    use_ssl = False
    ca_certs = None
    verify_certs = True
    http_auth = None
    timeout = 10

    if profile is None:
        profile = "elasticsearch"

    if isinstance(profile, str):
        _profile = __salt__["config.option"](profile, None)
    elif isinstance(profile, dict):
        _profile = profile
    if _profile:
        hosts = _profile.get("host", hosts)
        if not hosts:
            hosts = _profile.get("hosts", hosts)
        proxies = _profile.get("proxies", None)
        use_ssl = _profile.get("use_ssl", False)
        ca_certs = _profile.get("ca_certs", None)
        verify_certs = _profile.get("verify_certs", True)
        username = _profile.get("username", None)
        password = _profile.get("password", None)
        timeout = _profile.get("timeout", 10)

        if username and password:
            http_auth = (username, password)

    if not hosts:
        hosts = ["127.0.0.1:9200"]
    if isinstance(hosts, str):
        hosts = [hosts]
    try:
        if proxies:
            # Custom connection class to use requests module with proxies
            class ProxyConnection(RequestsHttpConnection):
                def __init__(self, *args, **kwargs):
                    proxies = kwargs.pop("proxies", {})
                    super().__init__(*args, **kwargs)
                    self.session.proxies = proxies

            es = elasticsearch.Elasticsearch(
                hosts,
                connection_class=ProxyConnection,
                proxies=proxies,
                use_ssl=use_ssl,
                ca_certs=ca_certs,
                verify_certs=verify_certs,
                http_auth=http_auth,
                timeout=timeout,
            )
        else:
            es = elasticsearch.Elasticsearch(
                hosts,
                use_ssl=use_ssl,
                ca_certs=ca_certs,
                verify_certs=verify_certs,
                http_auth=http_auth,
                timeout=timeout,
            )

        # Try the connection
        es.info()
    except elasticsearch.exceptions.TransportError as err:
        raise CommandExecutionError(
            "Could not connect to Elasticsearch host/ cluster {} due to {}".format(
                hosts, err
            )
        )
    return es


def ping(allow_failure=False, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Test connection to Elasticsearch instance. This method does not fail if not explicitly specified.

    allow_failure
        Throw exception if ping fails

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.ping allow_failure=True
        salt myminion elasticsearch.ping profile=elasticsearch-extra
    """
    try:
        _get_instance(hosts, profile)
    except CommandExecutionError as e:
        if allow_failure:
            raise
        return False
    return True


def info(hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Return Elasticsearch information.

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.info
        salt myminion elasticsearch.info profile=elasticsearch-extra
    """
    es = _get_instance(hosts, profile)

    try:
        return es.info()
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve server information, server returned code {} with"
            " message {}".format(e.status_code, e.error)
        )


def node_info(nodes=None, flat_settings=False, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Return Elasticsearch node information.

    nodes
        List of cluster nodes (id or name) to display stats for. Use _local for connected node, empty for all
    flat_settings
        Flatten settings keys

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.node_info flat_settings=True
    """
    es = _get_instance(hosts, profile)

    try:
        return es.nodes.info(node_id=nodes, flat_settings=flat_settings)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve node information, server returned code {} with message {}".format(
                e.status_code, e.error
            )
        )


def cluster_health(index=None, level="cluster", local=False, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Return Elasticsearch cluster health.

    index
        Limit the information returned to a specific index
    level
        Specify the level of detail for returned information, default 'cluster', valid choices are: 'cluster', 'indices', 'shards'
    local
        Return local information, do not retrieve the state from master node

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.cluster_health
    """
    es = _get_instance(hosts, profile)

    try:
        return es.cluster.health(index=index, level=level, local=local)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve health information, server returned code {} with"
            " message {}".format(e.status_code, e.error)
        )


def cluster_stats(nodes=None, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Return Elasticsearch cluster stats.

    nodes
        List of cluster nodes (id or name) to display stats for. Use _local for connected node, empty for all

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.cluster_stats
    """
    es = _get_instance(hosts, profile)

    try:
        return es.cluster.stats(node_id=nodes)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve cluster stats, server returned code {} with message {}".format(
                e.status_code, e.error
            )
        )


def cluster_get_settings(
    flat_settings=False, include_defaults=False, hosts=None, profile=None
):
    """
    .. versionadded:: 3000

    Return Elasticsearch cluster settings.

    flat_settings
        Return settings in flat format.

    include_defaults
        Whether to return all default clusters setting.

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.cluster_get_settings
    """
    es = _get_instance(hosts, profile)

    try:
        return es.cluster.get_settings(
            flat_settings=flat_settings, include_defaults=include_defaults
        )
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve cluster settings, server returned code {} with message {}".format(
                e.status_code, e.error
            )
        )


def cluster_put_settings(body=None, flat_settings=False, hosts=None, profile=None):
    """
    .. versionadded:: 3000

    Set Elasticsearch cluster settings.

    body
        The settings to be updated. Can be either 'transient' or 'persistent' (survives cluster restart)
        http://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-update-settings.html

    flat_settings
        Return settings in flat format.

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.cluster_put_settings '{"persistent": {"indices.recovery.max_bytes_per_sec": "50mb"}}'
        salt myminion elasticsearch.cluster_put_settings '{"transient": {"indices.recovery.max_bytes_per_sec": "50mb"}}'
    """
    if not body:
        message = "You must provide a body with settings"
        raise SaltInvocationError(message)
    es = _get_instance(hosts, profile)

    try:
        return es.cluster.put_settings(body=body, flat_settings=flat_settings)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot update cluster settings, server returned code {} with message {}".format(
                e.status_code, e.error
            )
        )


def alias_create(indices, alias, hosts=None, body=None, profile=None, source=None):
    """
    Create an alias for a specific index/indices

    indices
        Single or multiple indices separated by comma, use _all to perform the operation on all indices.
    alias
        Alias name
    body
        Optional definition such as routing or filter as defined in https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-aliases.html
    source
        URL of file specifying optional definition such as routing or filter. Cannot be used in combination with ``body``.

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.alias_create testindex_v1 testindex
    """
    es = _get_instance(hosts, profile)
    if source and body:
        message = "Either body or source should be specified but not both."
        raise SaltInvocationError(message)
    if source:
        body = __salt__["cp.get_file_str"](
            source, saltenv=__opts__.get("saltenv", "base")
        )
    try:
        result = es.indices.put_alias(index=indices, name=alias, body=body)
        return result.get("acknowledged", False)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot create alias {} in index {}, server returned code {} with"
            " message {}".format(alias, indices, e.status_code, e.error)
        )


def alias_delete(indices, aliases, hosts=None, body=None, profile=None, source=None):
    """
    Delete an alias of an index

    indices
        Single or multiple indices separated by comma, use _all to perform the operation on all indices.
    aliases
        Alias names separated by comma

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.alias_delete testindex_v1 testindex
    """
    es = _get_instance(hosts, profile)
    if source and body:
        message = "Either body or source should be specified but not both."
        raise SaltInvocationError(message)
    if source:
        body = __salt__["cp.get_file_str"](
            source, saltenv=__opts__.get("saltenv", "base")
        )
    try:
        result = es.indices.delete_alias(index=indices, name=aliases)

        return result.get("acknowledged", False)
    except elasticsearch.exceptions.NotFoundError:
        return True
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot delete alias {} in index {}, server returned code {} with"
            " message {}".format(aliases, indices, e.status_code, e.error)
        )


def alias_exists(aliases, indices=None, hosts=None, profile=None):
    """
    Return a boolean indicating whether given alias exists

    indices
        Single or multiple indices separated by comma, use _all to perform the operation on all indices.
    aliases
        Alias names separated by comma

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.alias_exists None testindex
    """
    es = _get_instance(hosts, profile)
    try:
        return es.indices.exists_alias(name=aliases, index=indices)
    except elasticsearch.exceptions.NotFoundError:
        return False
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot get alias {} in index {}, server returned code {} with message {}".format(
                aliases, indices, e.status_code, e.error
            )
        )


def alias_get(indices=None, aliases=None, hosts=None, profile=None):
    """
    Check for the existence of an alias and if it exists, return it

    indices
        Single or multiple indices separated by comma, use _all to perform the operation on all indices.
    aliases
        Alias names separated by comma

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.alias_get testindex
    """
    es = _get_instance(hosts, profile)

    try:
        return es.indices.get_alias(index=indices, name=aliases)
    except elasticsearch.exceptions.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot get alias {} in index {}, server returned code {} with message {}".format(
                aliases, indices, e.status_code, e.error
            )
        )


def document_create(
    index, doc_type, body=None, id=None, hosts=None, profile=None, source=None
):
    """
    Create a document in a specified index

    index
        Index name where the document should reside
    doc_type
        Type of the document
    body
        Document to store
    source
        URL of file specifying document to store. Cannot be used in combination with ``body``.
    id
        Optional unique document identifier for specified doc_type (empty for random)

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.document_create testindex doctype1 '{}'
    """
    es = _get_instance(hosts, profile)
    if source and body:
        message = "Either body or source should be specified but not both."
        raise SaltInvocationError(message)
    if source:
        body = __salt__["cp.get_file_str"](
            source, saltenv=__opts__.get("saltenv", "base")
        )
    try:
        return es.index(index=index, doc_type=doc_type, body=body, id=id)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot create document in index {}, server returned code {} with"
            " message {}".format(index, e.status_code, e.error)
        )


def document_delete(index, doc_type, id, hosts=None, profile=None):
    """
    Delete a document from an index

    index
        Index name where the document resides
    doc_type
        Type of the document
    id
        Document identifier

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.document_delete testindex doctype1 AUx-384m0Bug_8U80wQZ
    """
    es = _get_instance(hosts, profile)

    try:
        return es.delete(index=index, doc_type=doc_type, id=id)
    except elasticsearch.exceptions.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot delete document {} in index {}, server returned code {} with"
            " message {}".format(id, index, e.status_code, e.error)
        )


def document_exists(index, id, doc_type="_all", hosts=None, profile=None):
    """
    Return a boolean indicating whether given document exists

    index
        Index name where the document resides
    id
        Document identifier
    doc_type
        Type of the document, use _all to fetch the first document matching the ID across all types

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.document_exists testindex AUx-384m0Bug_8U80wQZ
    """
    es = _get_instance(hosts, profile)

    try:
        return es.exists(index=index, id=id, doc_type=doc_type)
    except elasticsearch.exceptions.NotFoundError:
        return False
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve document {} from index {}, server returned code {} with"
            " message {}".format(id, index, e.status_code, e.error)
        )


def document_get(index, id, doc_type="_all", hosts=None, profile=None):
    """
    Check for the existence of a document and if it exists, return it

    index
        Index name where the document resides
    id
        Document identifier
    doc_type
        Type of the document, use _all to fetch the first document matching the ID across all types

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.document_get testindex AUx-384m0Bug_8U80wQZ
    """
    es = _get_instance(hosts, profile)

    try:
        return es.get(index=index, id=id, doc_type=doc_type)
    except elasticsearch.exceptions.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve document {} from index {}, server returned code {} with"
            " message {}".format(id, index, e.status_code, e.error)
        )


def index_create(index, body=None, hosts=None, profile=None, source=None):
    """
    Create an index

    index
        Index name
    body
        Index definition, such as settings and mappings as defined in https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-create-index.html
    source
        URL to file specifying index definition. Cannot be used in combination with ``body``.

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_create testindex
        salt myminion elasticsearch.index_create testindex2 '{"settings" : {"index" : {"number_of_shards" : 3, "number_of_replicas" : 2}}}'
    """
    es = _get_instance(hosts, profile)
    if source and body:
        message = "Either body or source should be specified but not both."
        raise SaltInvocationError(message)
    if source:
        body = __salt__["cp.get_file_str"](
            source, saltenv=__opts__.get("saltenv", "base")
        )
    try:
        result = es.indices.create(index=index, body=body)
        return result.get("acknowledged", False) and result.get(
            "shards_acknowledged", True
        )
    except elasticsearch.TransportError as e:
        if "index_already_exists_exception" == e.error:
            return True

        raise CommandExecutionError(
            "Cannot create index {}, server returned code {} with message {}".format(
                index, e.status_code, e.error
            )
        )


def index_delete(index, hosts=None, profile=None):
    """
    Delete an index

    index
        Index name

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_delete testindex
    """
    es = _get_instance(hosts, profile)

    try:
        result = es.indices.delete(index=index)

        return result.get("acknowledged", False)
    except elasticsearch.exceptions.NotFoundError:
        return True
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot delete index {}, server returned code {} with message {}".format(
                index, e.status_code, e.error
            )
        )


def index_exists(index, hosts=None, profile=None):
    """
    Return a boolean indicating whether given index exists

    index
        Index name

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_exists testindex
    """
    es = _get_instance(hosts, profile)

    try:
        return es.indices.exists(index=index)
    except elasticsearch.exceptions.NotFoundError:
        return False
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve index {}, server returned code {} with message {}".format(
                index, e.status_code, e.error
            )
        )


def index_get(index, hosts=None, profile=None):
    """
    Check for the existence of an index and if it exists, return it

    index
        Index name

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_get testindex
    """
    es = _get_instance(hosts, profile)

    try:
        return es.indices.get(index=index)
    except elasticsearch.exceptions.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve index {}, server returned code {} with message {}".format(
                index, e.status_code, e.error
            )
        )


def index_open(
    index,
    allow_no_indices=True,
    expand_wildcards="closed",
    ignore_unavailable=True,
    hosts=None,
    profile=None,
):
    """
    .. versionadded:: 2017.7.0

    Open specified index.

    index
        Index to be opened
    allow_no_indices
        Whether to ignore if a wildcard indices expression resolves into no concrete indices. (This includes _all string or when no indices have been specified)
    expand_wildcards
        Whether to expand wildcard expression to concrete indices that are open, closed or both., default ‘closed’, valid choices are: ‘open’, ‘closed’, ‘none’, ‘all’
    ignore_unavailable
        Whether specified concrete indices should be ignored when unavailable (missing or closed)

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_open testindex
    """
    es = _get_instance(hosts, profile)

    try:
        result = es.indices.open(
            index=index,
            allow_no_indices=allow_no_indices,
            expand_wildcards=expand_wildcards,
            ignore_unavailable=ignore_unavailable,
        )

        return result.get("acknowledged", False)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot open index {}, server returned code {} with message {}".format(
                index, e.status_code, e.error
            )
        )


def index_close(
    index,
    allow_no_indices=True,
    expand_wildcards="open",
    ignore_unavailable=True,
    hosts=None,
    profile=None,
):
    """
    .. versionadded:: 2017.7.0

    Close specified index.

    index
        Index to be closed
    allow_no_indices
        Whether to ignore if a wildcard indices expression resolves into no concrete indices. (This includes _all string or when no indices have been specified)
    expand_wildcards
        Whether to expand wildcard expression to concrete indices that are open, closed or both., default ‘open’, valid choices are: ‘open’, ‘closed’, ‘none’, ‘all’
    ignore_unavailable
        Whether specified concrete indices should be ignored when unavailable (missing or closed)

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_close testindex
    """
    es = _get_instance(hosts, profile)

    try:
        result = es.indices.close(
            index=index,
            allow_no_indices=allow_no_indices,
            expand_wildcards=expand_wildcards,
            ignore_unavailable=ignore_unavailable,
        )

        return result.get("acknowledged", False)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot close index {}, server returned code {} with message {}".format(
                index, e.status_code, e.error
            )
        )


def index_get_settings(hosts=None, profile=None, **kwargs):
    """
    .. versionadded:: 3000

    Check for the existence of an index and if it exists, return its settings
    http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-get-settings.html

    index
        (Optional, string) A comma-separated list of index names; use _all or empty string for all indices. Defaults to '_all'.
    name
        (Optional, string) The name of the settings that should be included
    allow_no_indices
        (Optional, boolean) Whether to ignore if a wildcard indices expression resolves into no concrete indices.
        (This includes _all string or when no indices have been specified)
    expand_wildcards
        (Optional, string) Whether to expand wildcard expression to concrete indices that are open, closed or both.
        Valid choices are: ‘open’, ‘closed’, ‘none’, ‘all’
    flat_settings
        (Optional, boolean) Return settings in flat format
    ignore_unavailable
        (Optional, boolean) Whether specified concrete indices should be ignored when unavailable (missing or closed)
    include_defaults
        (Optional, boolean) Whether to return all default setting for each of the indices.
    local
        (Optional, boolean) Return local information, do not retrieve the state from master node

    The defaults settings for the above parameters depend on the API version being used.

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_get_settings index=testindex
    """

    es = _get_instance(hosts, profile)

    # Filtering Salt internal keys
    filtered_kwargs = kwargs.copy()
    for k in kwargs:
        if k.startswith("__"):
            filtered_kwargs.pop(k)

    try:
        return es.indices.get_settings(**filtered_kwargs)
    except elasticsearch.exceptions.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve index settings {}, server returned code {} with message {}".format(
                kwargs, e.status_code, e.error
            )
        )


def index_put_settings(body=None, hosts=None, profile=None, source=None, **kwargs):
    """
    .. versionadded:: 3000

    Update existing index settings
    https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-update-settings.html

    body
        The index settings to be updated.
    source
        URL to file specifying index definition. Cannot be used in combination with ``body``.
    index
        (Optional, string) A comma-separated list of index names; use _all or empty string to perform the operation on all indices
    allow_no_indices
        (Optional, boolean) Whether to ignore if a wildcard indices expression resolves into no concrete indices.
        (This includes _all string or when no indices have been specified)
    expand_wildcards
        (Optional, string) Whether to expand wildcard expression to concrete indices that are open, closed or both.
        Valid choices are: ‘open’, ‘closed’, ‘none’, ‘all’
    flat_settings
        (Optional, boolean) Return settings in flat format (default: false)
    ignore_unavailable
        (Optional, boolean) Whether specified concrete indices should be ignored when unavailable (missing or closed)
    master_timeout
        (Optional, time units) Explicit operation timeout for connection to master node
    preserve_existing
        (Optional, boolean) Whether to update existing settings. If set to true existing settings on an index remain unchanged, the default is false

    The defaults settings for the above parameters depend on the API version being used.

    .. note::
        Elasticsearch time units can be found here:
        https://www.elastic.co/guide/en/elasticsearch/reference/current/common-options.html#time-units

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_put_settings index=testindex body='{"settings" : {"index" : {"number_of_replicas" : 2}}}'
    """
    es = _get_instance(hosts, profile)
    if source and body:
        message = "Either body or source should be specified but not both."
        raise SaltInvocationError(message)
    if source:
        body = __salt__["cp.get_file_str"](
            source, saltenv=__opts__.get("saltenv", "base")
        )

    # Filtering Salt internal keys
    filtered_kwargs = kwargs.copy()
    for k in kwargs:
        if k.startswith("__"):
            filtered_kwargs.pop(k)

    try:
        result = es.indices.put_settings(body=body, **filtered_kwargs)
        return result.get("acknowledged", False)
    except elasticsearch.exceptions.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot update index settings {}, server returned code {} with message {}".format(
                kwargs, e.status_code, e.error
            )
        )


def mapping_create(index, doc_type, body=None, hosts=None, profile=None, source=None):
    """
    Create a mapping in a given index

    index
        Index for the mapping
    doc_type
        Name of the document type
    body
        Mapping definition as specified in https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-put-mapping.html
    source
        URL to file specifying mapping definition. Cannot be used in combination with ``body``.

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.mapping_create testindex user '{ "user" : { "properties" : { "message" : {"type" : "string", "store" : true } } } }'
    """
    es = _get_instance(hosts, profile)
    if source and body:
        message = "Either body or source should be specified but not both."
        raise SaltInvocationError(message)
    if source:
        body = __salt__["cp.get_file_str"](
            source, saltenv=__opts__.get("saltenv", "base")
        )
    try:
        result = es.indices.put_mapping(index=index, doc_type=doc_type, body=body)

        return result.get("acknowledged", False)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot create mapping {}, server returned code {} with message {}".format(
                index, e.status_code, e.error
            )
        )


def mapping_delete(index, doc_type, hosts=None, profile=None):
    """
    Delete a mapping (type) along with its data. As of Elasticsearch 5.0 this is no longer available.

    index
        Index for the mapping
    doc_type
        Name of the document type

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.mapping_delete testindex user
    """
    es = _get_instance(hosts, profile)
    try:
        result = es.indices.delete_mapping(index=index, doc_type=doc_type)

        return result.get("acknowledged", False)
    except elasticsearch.exceptions.NotFoundError:
        return True
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot delete mapping {}, server returned code {} with message {}".format(
                index, e.status_code, e.error
            )
        )
    except AttributeError:
        raise CommandExecutionError("Method is not applicable for Elasticsearch 5.0+")


def mapping_get(index, doc_type, hosts=None, profile=None):
    """
    Retrieve mapping definition of index or index/type

    index
        Index for the mapping
    doc_type
        Name of the document type

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.mapping_get testindex user
    """
    es = _get_instance(hosts, profile)

    try:
        return es.indices.get_mapping(index=index, doc_type=doc_type)
    except elasticsearch.exceptions.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve mapping {}, server returned code {} with message {}".format(
                index, e.status_code, e.error
            )
        )


def index_template_create(name, body=None, hosts=None, profile=None, source=None):
    """
    Create an index template

    name
        Index template name

    body
        Template definition as specified in http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-templates.html

    source
        URL to file specifying template definition. Cannot be used in combination with ``body``.

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_template_create testindex_templ '{ "template": "logstash-*", "order": 1, "settings": { "number_of_shards": 1 } }'
    """
    es = _get_instance(hosts, profile)
    if source and body:
        message = "Either body or source should be specified but not both."
        raise SaltInvocationError(message)
    if source:
        body = __salt__["cp.get_file_str"](
            source, saltenv=__opts__.get("saltenv", "base")
        )
    try:
        result = es.indices.put_template(name=name, body=body)
        return result.get("acknowledged", False)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot create template {}, server returned code {} with message {}".format(
                name, e.status_code, e.error
            )
        )


def index_template_delete(name, hosts=None, profile=None):
    """
    Delete an index template (type) along with its data

    name
        Index template name

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_template_delete testindex_templ user
    """
    es = _get_instance(hosts, profile)
    try:
        result = es.indices.delete_template(name=name)

        return result.get("acknowledged", False)
    except elasticsearch.exceptions.NotFoundError:
        return True
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot delete template {}, server returned code {} with message {}".format(
                name, e.status_code, e.error
            )
        )


def index_template_exists(name, hosts=None, profile=None):
    """
    Return a boolean indicating whether given index template exists

    name
        Index template name

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_template_exists testindex_templ
    """
    es = _get_instance(hosts, profile)
    try:
        return es.indices.exists_template(name=name)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve template {}, server returned code {} with message {}".format(
                name, e.status_code, e.error
            )
        )


def index_template_get(name, hosts=None, profile=None):
    """
    Retrieve template definition of index or index/type

    name
        Index template name

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.index_template_get testindex_templ
    """
    es = _get_instance(hosts, profile)

    try:
        return es.indices.get_template(name=name)
    except elasticsearch.exceptions.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot retrieve template {}, server returned code {} with message {}".format(
                name, e.status_code, e.error
            )
        )


def pipeline_get(id, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Retrieve Ingest pipeline definition. Available since Elasticsearch 5.0.

    id
        Pipeline id

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.pipeline_get mypipeline
    """
    es = _get_instance(hosts, profile)

    try:
        return es.ingest.get_pipeline(id=id)
    except elasticsearch.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot create pipeline {}, server returned code {} with message {}".format(
                id, e.status_code, e.error
            )
        )
    except AttributeError:
        raise CommandExecutionError("Method is applicable only for Elasticsearch 5.0+")


def pipeline_delete(id, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Delete Ingest pipeline. Available since Elasticsearch 5.0.

    id
        Pipeline id

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.pipeline_delete mypipeline
    """
    es = _get_instance(hosts, profile)

    try:
        ret = es.ingest.delete_pipeline(id=id)
        return ret.get("acknowledged", False)
    except elasticsearch.NotFoundError:
        return True
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot delete pipeline {}, server returned code {} with message {}".format(
                id, e.status_code, e.error
            )
        )
    except AttributeError:
        raise CommandExecutionError("Method is applicable only for Elasticsearch 5.0+")


def pipeline_create(id, body, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Create Ingest pipeline by supplied definition. Available since Elasticsearch 5.0.

    id
        Pipeline id
    body
        Pipeline definition as specified in https://www.elastic.co/guide/en/elasticsearch/reference/master/pipeline.html

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.pipeline_create mypipeline '{"description": "my custom pipeline", "processors": [{"set" : {"field": "collector_timestamp_millis", "value": "{{_ingest.timestamp}}"}}]}'
    """
    es = _get_instance(hosts, profile)
    try:
        out = es.ingest.put_pipeline(id=id, body=body)
        return out.get("acknowledged", False)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot create pipeline {}, server returned code {} with message {}".format(
                id, e.status_code, e.error
            )
        )
    except AttributeError:
        raise CommandExecutionError("Method is applicable only for Elasticsearch 5.0+")


def pipeline_simulate(id, body, verbose=False, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Simulate existing Ingest pipeline on provided data. Available since Elasticsearch 5.0.

    id
        Pipeline id
    body
        Pipeline definition as specified in https://www.elastic.co/guide/en/elasticsearch/reference/master/pipeline.html
    verbose
        Specify if the output should be more verbose

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.pipeline_simulate mypipeline '{"docs":[{"_index":"index","_type":"type","_id":"id","_source":{"foo":"bar"}},{"_index":"index","_type":"type","_id":"id","_source":{"foo":"rab"}}]}' verbose=True
    """
    es = _get_instance(hosts, profile)
    try:
        return es.ingest.simulate(id=id, body=body, verbose=verbose)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot simulate pipeline {}, server returned code {} with message {}".format(
                id, e.status_code, e.error
            )
        )
    except AttributeError:
        raise CommandExecutionError("Method is applicable only for Elasticsearch 5.0+")


def search_template_get(id, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Obtain existing search template definition.

    id
        Template ID

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.search_template_get mytemplate
    """
    es = _get_instance(hosts, profile)

    try:
        return es.get_template(id=id)
    except elasticsearch.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot obtain search template {}, server returned code {} with message {}".format(
                id, e.status_code, e.error
            )
        )


def search_template_create(id, body, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Create search template by supplied definition

    id
        Template ID
    body
        Search template definition

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.search_template_create mytemplate '{"template":{"query":{"match":{"title":"{{query_string}}"}}}}'
    """
    es = _get_instance(hosts, profile)

    try:
        result = es.put_template(id=id, body=body)

        return result.get("acknowledged", False)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot create search template {}, server returned code {} with message {}".format(
                id, e.status_code, e.error
            )
        )


def search_template_delete(id, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Delete existing search template definition.

    id
        Template ID

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.search_template_delete mytemplate
    """
    es = _get_instance(hosts, profile)

    try:
        result = es.delete_template(id=id)

        return result.get("acknowledged", False)
    except elasticsearch.NotFoundError:
        return True
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot delete search template {}, server returned code {} with message {}".format(
                id, e.status_code, e.error
            )
        )


def repository_get(name, local=False, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Get existing repository details.

    name
        Repository name
    local
        Retrieve only local information, default is false

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.repository_get testrepo
    """
    es = _get_instance(hosts, profile)

    try:
        return es.snapshot.get_repository(repository=name, local=local)
    except elasticsearch.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot obtain repository {}, server returned code {} with message {}".format(
                name, e.status_code, e.error
            )
        )


def repository_create(name, body, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Create repository for storing snapshots. Note that shared repository paths have to be specified in path.repo Elasticsearch configuration option.

    name
        Repository name
    body
        Repository definition as in https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-snapshots.html

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.repository_create testrepo '{"type":"fs","settings":{"location":"/tmp/test","compress":true}}'
    """
    es = _get_instance(hosts, profile)

    try:
        result = es.snapshot.create_repository(repository=name, body=body)

        return result.get("acknowledged", False)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot create repository {}, server returned code {} with message {}".format(
                name, e.status_code, e.error
            )
        )


def repository_delete(name, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Delete existing repository.

    name
        Repository name

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.repository_delete testrepo
    """
    es = _get_instance(hosts, profile)

    try:
        result = es.snapshot.delete_repository(repository=name)

        return result.get("acknowledged", False)
    except elasticsearch.NotFoundError:
        return True
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot delete repository {}, server returned code {} with message {}".format(
                name, e.status_code, e.error
            )
        )


def repository_verify(name, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Obtain list of cluster nodes which successfully verified this repository.

    name
        Repository name

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.repository_verify testrepo
    """
    es = _get_instance(hosts, profile)

    try:
        return es.snapshot.verify_repository(repository=name)
    except elasticsearch.NotFoundError:
        return None
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot verify repository {}, server returned code {} with message {}".format(
                name, e.status_code, e.error
            )
        )


def snapshot_status(
    repository=None, snapshot=None, ignore_unavailable=False, hosts=None, profile=None
):
    """
    .. versionadded:: 2017.7.0

    Obtain status of all currently running snapshots.

    repository
        Particular repository to look for snapshots
    snapshot
        Snapshot name
    ignore_unavailable
        Ignore unavailable snapshots

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.snapshot_status ignore_unavailable=True
    """
    es = _get_instance(hosts, profile)

    try:
        return es.snapshot.status(
            repository=repository,
            snapshot=snapshot,
            ignore_unavailable=ignore_unavailable,
        )
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot obtain snapshot status, server returned code {} with message {}".format(
                e.status_code, e.error
            )
        )


def snapshot_get(
    repository, snapshot, ignore_unavailable=False, hosts=None, profile=None
):
    """
    .. versionadded:: 2017.7.0

    Obtain snapshot residing in specified repository.

    repository
        Repository name
    snapshot
        Snapshot name, use _all to obtain all snapshots in specified repository
    ignore_unavailable
        Ignore unavailable snapshots

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.snapshot_get testrepo testsnapshot
    """
    es = _get_instance(hosts, profile)

    try:
        return es.snapshot.get(
            repository=repository,
            snapshot=snapshot,
            ignore_unavailable=ignore_unavailable,
        )
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot obtain details of snapshot {} in repository {}, server returned"
            " code {} with message {}".format(
                snapshot, repository, e.status_code, e.error
            )
        )


def snapshot_create(repository, snapshot, body=None, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Create snapshot in specified repository by supplied definition.

    repository
        Repository name
    snapshot
        Snapshot name
    body
        Snapshot definition as in https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-snapshots.html

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.snapshot_create testrepo testsnapshot '{"indices":"index_1,index_2","ignore_unavailable":true,"include_global_state":false}'
    """
    es = _get_instance(hosts, profile)

    try:
        response = es.snapshot.create(
            repository=repository, snapshot=snapshot, body=body
        )

        return response.get("accepted", False)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot create snapshot {} in repository {}, server returned code {} with"
            " message {}".format(snapshot, repository, e.status_code, e.error)
        )


def snapshot_restore(repository, snapshot, body=None, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Restore existing snapshot in specified repository by supplied definition.

    repository
        Repository name
    snapshot
        Snapshot name
    body
        Restore definition as in https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-snapshots.html

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.snapshot_restore testrepo testsnapshot '{"indices":"index_1,index_2","ignore_unavailable":true,"include_global_state":true}'
    """
    es = _get_instance(hosts, profile)

    try:
        response = es.snapshot.restore(
            repository=repository, snapshot=snapshot, body=body
        )

        return response.get("accepted", False)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot restore snapshot {} in repository {}, server returned code {} with"
            " message {}".format(snapshot, repository, e.status_code, e.error)
        )


def snapshot_delete(repository, snapshot, hosts=None, profile=None):
    """
    .. versionadded:: 2017.7.0

    Delete snapshot from specified repository.

    repository
        Repository name
    snapshot
        Snapshot name

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.snapshot_delete testrepo testsnapshot
    """
    es = _get_instance(hosts, profile)

    try:
        result = es.snapshot.delete(repository=repository, snapshot=snapshot)

        return result.get("acknowledged", False)
    except elasticsearch.NotFoundError:
        return True
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot delete snapshot {} from repository {}, server returned code {} with"
            " message {}".format(snapshot, repository, e.status_code, e.error)
        )


def flush_synced(hosts=None, profile=None, **kwargs):
    """
    .. versionadded:: 3000

    Perform a normal flush, then add a generated unique marker (sync_id) to all shards.
    http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-synced-flush.html

    index
        (Optional, string) A comma-separated list of index names; use _all or empty string for all indices. Defaults to '_all'.

    ignore_unavailable
        (Optional, boolean) If true, missing or closed indices are not included in the response. Defaults to false.

    allow_no_indices
        (Optional, boolean) If true, the request does not return an error if a wildcard expression or _all value retrieves only missing or closed indices.
        This parameter also applies to index aliases that point to a missing or closed index.

    expand_wildcards
        (Optional, string) Controls what kind of indices that wildcard expressions can expand to.

        Valid values are::

            all - Expand to open and closed indices.
            open - Expand only to open indices.
            closed - Expand only to closed indices.
            none - Wildcard expressions are not accepted.

    The defaults settings for the above parameters depend on the API being used.

    CLI Example:

    .. code-block:: bash

        salt myminion elasticsearch.flush_synced index='index1,index2' ignore_unavailable=True allow_no_indices=True expand_wildcards='all'
    """
    es = _get_instance(hosts, profile)

    try:
        return es.indices.flush_synced(kwargs)
    except elasticsearch.TransportError as e:
        raise CommandExecutionError(
            "Cannot flush synced, server returned code {} with message {}".format(
                e.status_code, e.error
            )
        )
