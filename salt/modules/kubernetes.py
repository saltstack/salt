'''
Module for handling kubernetes calls.

:optdepends:    - kubernetes Python client
:configuration: This module is not usable until the following are specified
    either in a pillar or in the minion's config file::

        kubernetes.user: admin
        kubernetes.password: verybadpass
        kubernetes.api_url: 'http://127.0.0.1:8080'
'''
# Import Python Futures
from __future__ import absolute_import
from salt.ext.six import iteritems
from salt.exceptions import CommandExecutionError
import salt.utils
import salt.utils.templates
import yaml

try:
    import kubernetes
    import kubernetes.client
    from kubernetes.client.rest import ApiException

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


import logging
log = logging.getLogger(__name__)

__virtualname__ = 'kubernetes'


def __virtual__():
    '''
    Check dependencies
    '''
    if HAS_LIBS:
        return __virtualname__

    return False


def ping():
    '''
    Checks connections with the kubernetes API server.
    Returns True if the connection can be established, False otherwise.

    CLI Example:
        salt '*' kubernetes.ping
    '''
    status = True
    try:
        nodes()
    except Exception:
        status = False

    return status


def nodes():
    '''
    Return the names of the nodes composing the kubernetes cluster

    CLI Examples::

        salt '*' kubernetes.nodes
    '''
    _setup_conn()

    api_instance = kubernetes.client.CoreV1Api()
    api_response = api_instance.list_node()

    ret = []

    for node in api_response.items:
        ret.append(node.metadata.name)

    return ret


def _setup_conn():
    '''
    Setup kubernetes API connection singleton
    '''
    host = __salt__['config.option']('kubernetes.api_url',
                                     'http://localhost:8080')
    username = __salt__['config.option']('kubernetes.user')
    password = __salt__['config.option']('kubernetes.password')
    kubernetes.client.configuration.host = host
    kubernetes.client.configuration.user = username
    kubernetes.client.configuration.passwd = password


def show_deployment(name, namespace):
    '''
    Return the kubernetes deployment defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.show_deployment my-nginx,default
        salt '*' kubernetes.show_deployment name=my-nginx,namespace=default
    '''
    _setup_conn()
    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.read_namespaced_deployment(name, namespace)

        return api_response.to_dict()
    except ApiException as exc:
        if exc.status == 404:
            return None
        else:
            log.exception(exc)
            raise exc


def show_service(name, namespace):
    '''
    Return the kubernetes service defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.show_service my-nginx,default
        salt '*' kubernetes.show_service name=my-nginx,namespace=default
    '''
    _setup_conn()
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.read_namespaced_service(name, namespace)

        return api_response.to_dict()
    except ApiException as exc:
        if exc.status == 404:
            return None
        else:
            log.exception(exc)
            raise exc


def delete_deployment(name, namespace):
    '''
    Deletes the kubernetes deployment defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.delete_deployment my-nginx,default
        salt '*' kubernetes.delete_deployment name=my-nginx,namespace=default
    '''
    _setup_conn()
    body = kubernetes.client.V1DeleteOptions(orphan_dependents=True)

    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.delete_namespaced_deployment(
            name=name,
            namespace=namespace,
            body=body)

        return api_response.to_dict()
    except ApiException as exc:
        if exc.status == 404:
            return None
        else:
            log.exception(exc)
            raise exc


def delete_service(name, namespace):
    '''
    Deletes the kubernetes service defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.delete_service my-nginx,default
        salt '*' kubernetes.delete_service name=my-nginx,namespace=default
    '''
    _setup_conn()

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.delete_namespaced_service(
            name=name,
            namespace=namespace)

        return api_response.to_dict()
    except ApiException as exc:
        if exc.status == 404:
            return None
        else:
            log.exception(exc)
            raise exc


def create_deployment(
        name,
        namespace,
        metadata,
        spec,
        source,
        template,
        saltenv):
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

    _setup_conn()

    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.create_namespaced_deployment(
            namespace, body)

        return api_response.to_dict()
    except ApiException as exc:
        if exc.status == 404:
            return None
        else:
            log.exception(exc)
            raise exc


def create_service(
        name,
        namespace,
        metadata,
        spec,
        source,
        template,
        saltenv):
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

    _setup_conn()

    log.warning(body)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.create_namespaced_service(
            namespace, body)

        return api_response.to_dict()
    except ApiException as exc:
        if exc.status == 404:
            return None
        else:
            log.exception(exc)
            raise exc


def replace_deployment(name,
                       namespace,
                       metadata,
                       spec,
                       source,
                       template,
                       saltenv):
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

    _setup_conn()

    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.replace_namespaced_deployment(
            name, namespace, body)

        return api_response.to_dict()
    except ApiException as exc:
        if exc.status == 404:
            return None
        else:
            log.exception(exc)
            raise exc


def replace_service(name,
                    namespace,
                    metadata,
                    spec,
                    source,
                    template,
                    old_service,
                    saltenv):
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

    _setup_conn()

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.replace_namespaced_service(
            name, namespace, body)

        return api_response.to_dict()
    except ApiException as exc:
        if exc.status == 404:
            return None
        else:
            log.exception(exc)
            raise exc


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
                    # TODO: should we allow user to set also `context` like
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
                            '%s' % data['data'])

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
    for key, value in iteritems(spec):
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
