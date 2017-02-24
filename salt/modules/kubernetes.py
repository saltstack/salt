# -*- coding: utf-8 -*-
'''
Module for handling kubernetes calls.

:optdepends:    - kubernetes Python client
:configuration: The k8s API settings are provided either in a pillar, in
    the minion's config file, or in master's config file::

        kubernetes.user: admin
        kubernetes.password: verybadpass
        kubernetes.api_url: 'http://127.0.0.1:8080'

These settings can be also overrided by adding `api_url`, `api_user`,
or `api_password` parameters when calling a function:

.. code-block:: bash
    salt '*' kubernetes.nodes api_url=http://k8s-api-server:port api_user=myuser api_password=pass

'''

# Import Python Futures
from __future__ import absolute_import
import logging
import yaml

from salt.exceptions import CommandExecutionError
from salt.ext.six import iteritems
import salt.utils
import salt.utils.templates

try:
    import kubernetes  # pylint: disable=import-self
    import kubernetes.client
    from kubernetes.client.rest import ApiException
    from urllib3.exceptions import HTTPError

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


log = logging.getLogger(__name__)

__virtualname__ = 'kubernetes'


def __virtual__():
    '''
    Check dependencies
    '''
    if HAS_LIBS:
        return __virtualname__

    return False, 'python kubernetes library not found'


# pylint: disable=no-member
def _setup_conn(**kwargs):
    '''
    Setup kubernetes API connection singleton
    '''
    host = __salt__['config.option']('kubernetes.api_url',
                                     'http://localhost:8080')
    username = __salt__['config.option']('kubernetes.user')
    password = __salt__['config.option']('kubernetes.password')

    # Override default API settings when settings are provided
    if kwargs.get('api_url'):
        host = kwargs['api_url']

    if kwargs.get('api_user'):
        username = kwargs['api_user']

    if kwargs.get('api_password'):
        password = kwargs['api_password']

    if (kubernetes.client.configuration.host != host or
       kubernetes.client.configuration.user != username or
       kubernetes.client.configuration.password != password):
        # Recreates API connection if settings are changed
        kubernetes.client.configuration.__init__()

    kubernetes.client.configuration.host = host
    kubernetes.client.configuration.user = username
    kubernetes.client.configuration.passwd = password


def ping(**kwargs):
    '''
    Checks connections with the kubernetes API server.
    Returns True if the connection can be established, False otherwise.

    CLI Example:
        salt '*' kubernetes.ping
    '''
    status = True
    try:
        nodes(**kwargs)
    except CommandExecutionError:
        status = False

    return status


def nodes(**kwargs):
    '''
    Return the names of the nodes composing the kubernetes cluster

    CLI Examples::

        salt '*' kubernetes.nodes
        salt '*' kubernetes.nodes api_url=http://myhost:port api_user=my-user
    '''
    _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.list_node()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling CoreV1Api->list_node: {0}".format(exc)
            )
            raise CommandExecutionError(exc)

    ret = []

    for node in api_response.items:
        ret.append(node.metadata.name)

    return ret


def deployments(namespace="default", **kwargs):
    '''
    Return a list of kubernetes deployments defined in the namespace

    CLI Examples::

        salt '*' kubernetes.deployments
        salt '*' kubernetes.deployments namespace=default
    '''
    _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.list_namespaced_deployment(namespace)

        return api_response.to_dict().get('items')
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "ExtensionsV1beta1Api->list_namespaced_deployment: "
                "{0}".format(exc)
            )
            raise CommandExecutionError(exc)


def services(namespace="default", **kwargs):
    '''
    Return a list of kubernetes services defined in the namespace

    CLI Examples::

        salt '*' kubernetes.services
        salt '*' kubernetes.services namespace=default
    '''
    _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.list_namespaced_service(namespace)

        return api_response.to_dict().get('items')
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "CoreV1Api->list_namespaced_service: {0}".format(exc)
            )
            raise CommandExecutionError(exc)


def pods(namespace="default", **kwargs):
    '''
    Return a list of kubernetes pods defined in the namespace

    CLI Examples::

        salt '*' kubernetes.pods
        salt '*' kubernetes.pods namespace=default
    '''
    _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.list_namespaced_pod(namespace)

        return api_response.to_dict().get('items')
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "CoreV1Api->list_namespaced_pod: {0}".format(exc)
            )
            raise CommandExecutionError(exc)


def show_deployment(name, namespace="default", **kwargs):
    '''
    Return the kubernetes deployment defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.show_deployment my-nginx default
        salt '*' kubernetes.show_deployment name=my-nginx namespace=default
    '''
    _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.read_namespaced_deployment(name, namespace)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "ExtensionsV1beta1Api->read_namespaced_deployment: "
                "{0}".format(exc)
            )
            raise CommandExecutionError(exc)


def show_service(name, namespace="default", **kwargs):
    '''
    Return the kubernetes service defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.show_service my-nginx default
        salt '*' kubernetes.show_service name=my-nginx namespace=default
    '''
    _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.read_namespaced_service(name, namespace)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "CoreV1Api->read_namespaced_service: {0}".format(exc)
            )
            raise CommandExecutionError(exc)


def show_pod(name, namespace="default", **kwargs):
    '''
    Return POD information for a given pod name defined in the namespace

    CLI Examples::

        salt '*' kubernetes.show_pod guestbook-708336848-fqr2x
        salt '*' kubernetes.show_pod guestbook-708336848-fqr2x namespace=default
    '''
    _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.read_namespaced_pod(name, namespace)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "CoreV1Api->read_namespaced_pod: {0}".format(exc)
            )
            raise CommandExecutionError(exc)


def delete_deployment(name, namespace="default", **kwargs):
    '''
    Deletes the kubernetes deployment defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.delete_deployment my-nginx
        salt '*' kubernetes.delete_deployment name=my-nginx namespace=default
    '''
    _setup_conn(**kwargs)
    body = kubernetes.client.V1DeleteOptions(orphan_dependents=True)

    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.delete_namespaced_deployment(
            name=name,
            namespace=namespace,
            body=body)
        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "ExtensionsV1beta1Api->delete_namespaced_deployment: "
                "{0}".format(exc)
            )
            raise CommandExecutionError(exc)


def delete_service(name, namespace="default", **kwargs):
    '''
    Deletes the kubernetes service defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.delete_service my-nginx default
        salt '*' kubernetes.delete_service name=my-nginx namespace=default
    '''
    _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.delete_namespaced_service(
            name=name,
            namespace=namespace)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling CoreV1Api->delete_namespaced_service: "
                "{0}".format(exc)
            )
            raise CommandExecutionError(exc)


def delete_pod(name, namespace="default", **kwargs):
    '''
    Deletes the kubernetes pod defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.delete_pod guestbook-708336848-5nl8c default
        salt '*' kubernetes.delete_pod name=guestbook-708336848-5nl8c namespace=default
    '''
    _setup_conn(**kwargs)
    body = kubernetes.client.V1DeleteOptions(orphan_dependents=True)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.delete_namespaced_pod(
            name=name,
            namespace=namespace,
            body=body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "CoreV1Api->delete_namespaced_pod: {0}".format(exc)
            )
            raise CommandExecutionError(exc)


def create_deployment(
        name,
        namespace,
        metadata,
        spec,
        source,
        template,
        saltenv,
        **kwargs):
    '''
    Creates the kubernetes deployment as defined by the user.
    '''
    body = __create_object_body(
        kind='Deployment',
        obj_class=kubernetes.client.V1beta1Deployment,
        spec_creator=__dict_to_deployment_spec,
        name=name,
        namespace=namespace,
        metadata=metadata,
        spec=spec,
        source=source,
        template=template,
        saltenv=saltenv)

    _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.create_namespaced_deployment(
            namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "ExtensionsV1beta1Api->create_namespaced_deployment: "
                "{0}".format(exc)
            )
            raise CommandExecutionError(exc)


def create_service(
        name,
        namespace,
        metadata,
        spec,
        source,
        template,
        saltenv,
        **kwargs):
    '''
    Creates the kubernetes service as defined by the user.
    '''
    body = __create_object_body(
        kind='Service',
        obj_class=kubernetes.client.V1Service,
        spec_creator=__dict_to_service_spec,
        name=name,
        namespace=namespace,
        metadata=metadata,
        spec=spec,
        source=source,
        template=template,
        saltenv=saltenv)

    _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.create_namespaced_service(
            namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "CoreV1Api->create_namespaced_service: {0}".format(exc)
            )
            raise CommandExecutionError(exc)


def replace_deployment(name,
                       metadata,
                       spec,
                       source,
                       template,
                       saltenv,
                       namespace="default",
                       **kwargs):
    '''
    Replaces an existing deployment with a new one defined by name and
    namespace, having the specificed metadata and spec.
    '''
    body = __create_object_body(
        kind='Deployment',
        obj_class=kubernetes.client.V1beta1Deployment,
        spec_creator=__dict_to_deployment_spec,
        name=name,
        namespace=namespace,
        metadata=metadata,
        spec=spec,
        source=source,
        template=template,
        saltenv=saltenv)

    _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.replace_namespaced_deployment(
            name, namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "ExtensionsV1beta1Api->replace_namespaced_deployment: "
                "{0}".format(exc)
            )
            raise CommandExecutionError(exc)


def replace_service(name,
                    metadata,
                    spec,
                    source,
                    template,
                    old_service,
                    saltenv,
                    namespace="default",
                    **kwargs):
    '''
    Replaces an existing service with a new one defined by name and namespace,
    having the specificed metadata and spec.
    '''
    body = __create_object_body(
        kind='Service',
        obj_class=kubernetes.client.V1Service,
        spec_creator=__dict_to_service_spec,
        name=name,
        namespace=namespace,
        metadata=metadata,
        spec=spec,
        source=source,
        template=template,
        saltenv=saltenv)

    # Some attributes have to be preserved
    # otherwise exceptions will be thrown
    body.spec.cluster_ip = old_service['spec']['cluster_ip']
    body.metadata.resource_version = old_service['metadata']['resource_version']

    _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.replace_namespaced_service(
            name, namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                "Exception when calling "
                "CoreV1Api->replace_namespaced_service: {0}".format(exc)
            )
            raise CommandExecutionError(exc)


def __create_object_body(kind,
                         obj_class,
                         spec_creator,
                         name,
                         namespace,
                         metadata,
                         spec,
                         source,
                         template,
                         saltenv):
    '''
    Create a Kubernetes Object body instance.
    '''
    if source:
        sfn = __salt__['cp.cache_file'](source, saltenv)
        if not sfn:
            raise CommandExecutionError(
                'Source file \'{0}\' not found'.format(source))

        with salt.utils.fopen(sfn, 'r') as src:
            contents = src.read()

            if template:
                if template in salt.utils.templates.TEMPLATE_REGISTRY:
                    # TODO: should we allow user to set also `context` like  # pylint: disable=fixme
                    # `file.managed` does?
                    # Apply templating
                    data = salt.utils.templates.TEMPLATE_REGISTRY[template](
                        contents,
                        from_str=True,
                        to_str=True,
                        saltenv=saltenv,
                        grains=__grains__,
                        pillar=__pillar__,
                        salt=__salt__,
                        opts=__opts__)

                    if not data['result']:
                        # Failed to render the template
                        raise CommandExecutionError(
                            'Failed to render file path with error: '
                            '{0}'.format(data['data'])
                        )

                    contents = data['data'].encode('utf-8')
                else:
                    raise CommandExecutionError(
                        'Unknown template specified: {0}'.format(
                            template))

            src_obj = yaml.load(contents)
            if (
                    not isinstance(src_obj, dict) or
                    'kind' not in src_obj or
                    src_obj['kind'] != kind
               ):
                raise CommandExecutionError(
                    'The source file should define only '
                    'a {0} object'.format(kind))

            if 'metadata' in src_obj:
                metadata = src_obj['metadata']
            if 'spec' in src_obj:
                spec = src_obj['spec']

    return obj_class(
        metadata=__dict_to_object_meta(name, namespace, metadata),
        spec=spec_creator(spec))


def __dict_to_object_meta(name, namespace, metadata):
    '''
    Converts a dictionary into kubernetes ObjectMetaV1 instance.
    '''
    meta_obj = kubernetes.client.V1ObjectMeta()
    meta_obj.namespace = namespace
    for key, value in iteritems(metadata):
        if hasattr(meta_obj, key):
            setattr(meta_obj, key, value)

    if meta_obj.name != name:
        log.warning(
            'The object already has a name attribute, overwriting it with '
            'the one defined inside of salt')
        meta_obj.name = name

    return meta_obj


def __dict_to_deployment_spec(spec):
    '''
    Converts a dictionary into kubernetes V1beta1DeploymentSpec instance.
    '''
    spec_obj = kubernetes.client.V1beta1DeploymentSpec()
    for key, value in iteritems(spec):
        if hasattr(spec_obj, key):
            setattr(spec_obj, key, value)

    return spec_obj


def __dict_to_service_spec(spec):
    '''
    Converts a dictionary into kubernetes V1ServiceSpec instance.
    '''
    spec_obj = kubernetes.client.V1ServiceSpec()
    for key, value in iteritems(spec):  # pylint: disable=too-many-nested-blocks
        if key == 'ports':
            spec_obj.ports = []
            for port in value:
                kube_port = kubernetes.client.V1ServicePort()
                if isinstance(port, dict):
                    for port_key, port_value in iteritems(port):
                        if hasattr(kube_port, port_key):
                            setattr(kube_port, port_key, port_value)
                else:
                    kube_port.port = port
                spec_obj.ports.append(kube_port)
        elif hasattr(spec_obj, key):
            setattr(spec_obj, key, value)

    return spec_obj
