"""
Manage kubernetes resources as salt states
==========================================

NOTE: This module requires the proper pillar values set. See
salt.modules.kubernetesmod for more information.

.. warning::

    Configuration options will change in 2019.2.0.

The kubernetes module is used to manage different kubernetes resources.


.. code-block:: yaml

    my-nginx:
      kubernetes.deployment_present:
        - namespace: default
          metadata:
            app: frontend
          spec:
            replicas: 1
            template:
              metadata:
                labels:
                  run: my-nginx
              spec:
                containers:
                - name: my-nginx
                  image: nginx
                  ports:
                  - containerPort: 80

    my-mariadb:
      kubernetes.deployment_absent:
        - namespace: default

    # kubernetes deployment as specified inside of
    # a file containing the definition of the the
    # deployment using the official kubernetes format
    redis-master-deployment:
      kubernetes.deployment_present:
        - name: redis-master
        - source: salt://k8s/redis-master-deployment.yml
      require:
        - pip: kubernetes-python-module

    # kubernetes service as specified inside of
    # a file containing the definition of the the
    # service using the official kubernetes format
    redis-master-service:
      kubernetes.service_present:
        - name: redis-master
        - source: salt://k8s/redis-master-service.yml
      require:
        - kubernetes.deployment_present: redis-master

    # kubernetes deployment as specified inside of
    # a file containing the definition of the the
    # deployment using the official kubernetes format
    # plus some jinja directives
     nginx-source-template:
      kubernetes.deployment_present:
        - source: salt://k8s/nginx.yml.jinja
        - template: jinja
      require:
        - pip: kubernetes-python-module


    # Kubernetes secret
    k8s-secret:
      kubernetes.secret_present:
        - name: top-secret
          data:
            key1: value1
            key2: value2
            key3: value3

.. versionadded:: 2017.7.0
"""

import copy
import logging

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if the kubernetes module is available in __salt__
    """
    if "kubernetes.ping" in __salt__:
        return True
    return (False, "kubernetes module could not be loaded")


def _error(ret, err_msg):
    """
    Helper function to propagate errors to
    the end user.
    """
    ret["result"] = False
    ret["comment"] = err_msg
    return ret


def deployment_absent(name, namespace="default", **kwargs):
    """
    Ensures that the named deployment is absent from the given namespace.

    name
        The name of the deployment

    namespace
        The name of the namespace
    """

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    deployment = __salt__["kubernetes.show_deployment"](name, namespace, **kwargs)

    if deployment is None:
        ret["result"] = True if not __opts__["test"] else None
        ret["comment"] = "The deployment does not exist"
        return ret

    if __opts__["test"]:
        ret["comment"] = "The deployment is going to be deleted"
        ret["result"] = None
        return ret

    res = __salt__["kubernetes.delete_deployment"](name, namespace, **kwargs)
    if res["code"] == 200:
        ret["result"] = True
        ret["changes"] = {"kubernetes.deployment": {"new": "absent", "old": "present"}}
        ret["comment"] = res["message"]
    else:
        ret["comment"] = f"Something went wrong, response: {res}"

    return ret


def deployment_present(
    name,
    namespace="default",
    metadata=None,
    spec=None,
    source="",
    template="",
    **kwargs,
):
    """
    Ensures that the named deployment is present inside of the specified
    namespace with the given metadata and spec.
    If the deployment exists it will be replaced.

    name
        The name of the deployment.

    namespace
        The namespace holding the deployment. The 'default' one is going to be
        used unless a different one is specified.

    metadata
        The metadata of the deployment object.

    spec
        The spec of the deployment object.

    source
        A file containing the definition of the deployment (metadata and
        spec) in the official kubernetes format.

    template
        Template engine to be used to render the source file.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if (metadata or spec) and source:
        return _error(
            ret, "'source' cannot be used in combination with 'metadata' or 'spec'"
        )

    if metadata is None:
        metadata = {}

    if spec is None:
        spec = {}

    deployment = __salt__["kubernetes.show_deployment"](name, namespace, **kwargs)

    if deployment is None:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The deployment is going to be created"
            return ret
        res = __salt__["kubernetes.create_deployment"](
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec,
            source=source,
            template=template,
            saltenv=__env__,
            **kwargs,
        )
        ret["changes"][f"{namespace}.{name}"] = {"old": {}, "new": res}
    else:
        if __opts__["test"]:
            ret["result"] = None
            return ret

        # TODO: improve checks  # pylint: disable=fixme
        log.info("Forcing the recreation of the deployment")
        ret["comment"] = "The deployment is already present. Forcing recreation"
        res = __salt__["kubernetes.replace_deployment"](
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec,
            source=source,
            template=template,
            saltenv=__env__,
            **kwargs,
        )

    ret["changes"] = {"metadata": metadata, "spec": spec}
    ret["result"] = True
    return ret


def service_present(
    name,
    namespace="default",
    metadata=None,
    spec=None,
    source="",
    template="",
    **kwargs,
):
    """
    Ensures that the named service is present inside of the specified namespace
    with the given metadata and spec.
    If the deployment exists it will be replaced.

    name
        The name of the service.

    namespace
        The namespace holding the service. The 'default' one is going to be
        used unless a different one is specified.

    metadata
        The metadata of the service object.

    spec
        The spec of the service object.

    source
        A file containing the definition of the service (metadata and
        spec) in the official kubernetes format.

    template
        Template engine to be used to render the source file.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if (metadata or spec) and source:
        return _error(
            ret, "'source' cannot be used in combination with 'metadata' or 'spec'"
        )

    if metadata is None:
        metadata = {}

    if spec is None:
        spec = {}

    service = __salt__["kubernetes.show_service"](name, namespace, **kwargs)

    if service is None:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The service is going to be created"
            return ret
        res = __salt__["kubernetes.create_service"](
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec,
            source=source,
            template=template,
            saltenv=__env__,
            **kwargs,
        )
        ret["changes"][f"{namespace}.{name}"] = {"old": {}, "new": res}
    else:
        if __opts__["test"]:
            ret["result"] = None
            return ret

        # TODO: improve checks  # pylint: disable=fixme
        log.info("Forcing the recreation of the service")
        ret["comment"] = "The service is already present. Forcing recreation"
        res = __salt__["kubernetes.replace_service"](
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec,
            source=source,
            template=template,
            old_service=service,
            saltenv=__env__,
            **kwargs,
        )

    ret["changes"] = {"metadata": metadata, "spec": spec}
    ret["result"] = True
    return ret


def service_absent(name, namespace="default", **kwargs):
    """
    Ensures that the named service is absent from the given namespace.

    name
        The name of the service

    namespace
        The name of the namespace
    """

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    service = __salt__["kubernetes.show_service"](name, namespace, **kwargs)

    if service is None:
        ret["result"] = True if not __opts__["test"] else None
        ret["comment"] = "The service does not exist"
        return ret

    if __opts__["test"]:
        ret["comment"] = "The service is going to be deleted"
        ret["result"] = None
        return ret

    res = __salt__["kubernetes.delete_service"](name, namespace, **kwargs)
    if res["code"] == 200:
        ret["result"] = True
        ret["changes"] = {"kubernetes.service": {"new": "absent", "old": "present"}}
        ret["comment"] = res["message"]
    else:
        ret["comment"] = f"Something went wrong, response: {res}"

    return ret


def namespace_absent(name, **kwargs):
    """
    Ensures that the named namespace is absent.

    name
        The name of the namespace
    """

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    namespace = __salt__["kubernetes.show_namespace"](name, **kwargs)

    if namespace is None:
        ret["result"] = True if not __opts__["test"] else None
        ret["comment"] = "The namespace does not exist"
        return ret

    if __opts__["test"]:
        ret["comment"] = "The namespace is going to be deleted"
        ret["result"] = None
        return ret

    res = __salt__["kubernetes.delete_namespace"](name, **kwargs)
    if (
        res["code"] == 200
        or (isinstance(res["status"], str) and "Terminating" in res["status"])
        or (isinstance(res["status"], dict) and res["status"]["phase"] == "Terminating")
    ):
        ret["result"] = True
        ret["changes"] = {"kubernetes.namespace": {"new": "absent", "old": "present"}}
        if res["message"]:
            ret["comment"] = res["message"]
        else:
            ret["comment"] = "Terminating"
    else:
        ret["comment"] = f"Something went wrong, response: {res}"

    return ret


def namespace_present(name, **kwargs):
    """
    Ensures that the named namespace is present.

    name
        The name of the namespace.

    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    namespace = __salt__["kubernetes.show_namespace"](name, **kwargs)

    if namespace is None:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The namespace is going to be created"
            return ret

        res = __salt__["kubernetes.create_namespace"](name, **kwargs)
        ret["result"] = True
        ret["changes"]["namespace"] = {"old": {}, "new": res}
    else:
        ret["result"] = True if not __opts__["test"] else None
        ret["comment"] = "The namespace already exists"

    return ret


def secret_absent(name, namespace="default", **kwargs):
    """
    Ensures that the named secret is absent from the given namespace.

    name
        The name of the secret

    namespace
        The name of the namespace
    """

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    secret = __salt__["kubernetes.show_secret"](name, namespace, **kwargs)

    if secret is None:
        ret["result"] = True if not __opts__["test"] else None
        ret["comment"] = "The secret does not exist"
        return ret

    if __opts__["test"]:
        ret["comment"] = "The secret is going to be deleted"
        ret["result"] = None
        return ret

    __salt__["kubernetes.delete_secret"](name, namespace, **kwargs)

    # As for kubernetes 1.6.4 doesn't set a code when deleting a secret
    # The kubernetes module will raise an exception if the kubernetes
    # server will return an error
    ret["result"] = True
    ret["changes"] = {"kubernetes.secret": {"new": "absent", "old": "present"}}
    ret["comment"] = "Secret deleted"
    return ret


def secret_present(
    name, namespace="default", data=None, source=None, template=None, **kwargs
):
    """
    Ensures that the named secret is present inside of the specified namespace
    with the given data.
    If the secret exists it will be replaced.

    name
        The name of the secret.

    namespace
        The namespace holding the secret. The 'default' one is going to be
        used unless a different one is specified.

    data
        The dictionary holding the secrets.

    source
        A file containing the data of the secret in plain format.

    template
        Template engine to be used to render the source file.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if data and source:
        return _error(ret, "'source' cannot be used in combination with 'data'")

    secret = __salt__["kubernetes.show_secret"](name, namespace, **kwargs)

    if secret is None:
        if data is None:
            data = {}

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The secret is going to be created"
            return ret
        res = __salt__["kubernetes.create_secret"](
            name=name,
            namespace=namespace,
            data=data,
            source=source,
            template=template,
            saltenv=__env__,
            **kwargs,
        )
        ret["changes"][f"{namespace}.{name}"] = {"old": {}, "new": res}
    else:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The secret is going to be replaced"
            return ret

        # TODO: improve checks  # pylint: disable=fixme
        log.info("Forcing the recreation of the service")
        ret["comment"] = "The secret is already present. Forcing recreation"
        res = __salt__["kubernetes.replace_secret"](
            name=name,
            namespace=namespace,
            data=data,
            source=source,
            template=template,
            saltenv=__env__,
            **kwargs,
        )

    ret["changes"] = {
        # Omit values from the return. They are unencrypted
        # and can contain sensitive data.
        "data": list(res["data"])
    }
    ret["result"] = True

    return ret


def configmap_absent(name, namespace="default", **kwargs):
    """
    Ensures that the named configmap is absent from the given namespace.

    name
        The name of the configmap

    namespace
        The namespace holding the configmap. The 'default' one is going to be
        used unless a different one is specified.
    """

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    configmap = __salt__["kubernetes.show_configmap"](name, namespace, **kwargs)

    if configmap is None:
        ret["result"] = True if not __opts__["test"] else None
        ret["comment"] = "The configmap does not exist"
        return ret

    if __opts__["test"]:
        ret["comment"] = "The configmap is going to be deleted"
        ret["result"] = None
        return ret

    __salt__["kubernetes.delete_configmap"](name, namespace, **kwargs)
    # As for kubernetes 1.6.4 doesn't set a code when deleting a configmap
    # The kubernetes module will raise an exception if the kubernetes
    # server will return an error
    ret["result"] = True
    ret["changes"] = {"kubernetes.configmap": {"new": "absent", "old": "present"}}
    ret["comment"] = "ConfigMap deleted"

    return ret


def configmap_present(
    name, namespace="default", data=None, source=None, template=None, **kwargs
):
    """
    Ensures that the named configmap is present inside of the specified namespace
    with the given data.
    If the configmap exists it will be replaced.

    name
        The name of the configmap.

    namespace
        The namespace holding the configmap. The 'default' one is going to be
        used unless a different one is specified.

    data
        The dictionary holding the configmaps.

    source
        A file containing the data of the configmap in plain format.

    template
        Template engine to be used to render the source file.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if data and source:
        return _error(ret, "'source' cannot be used in combination with 'data'")
    elif data is None:
        data = {}

    configmap = __salt__["kubernetes.show_configmap"](name, namespace, **kwargs)

    if configmap is None:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The configmap is going to be created"
            return ret
        res = __salt__["kubernetes.create_configmap"](
            name=name,
            namespace=namespace,
            data=data,
            source=source,
            template=template,
            saltenv=__env__,
            **kwargs,
        )
        ret["changes"][f"{namespace}.{name}"] = {"old": {}, "new": res}
    else:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The configmap is going to be replaced"
            return ret

        # TODO: improve checks  # pylint: disable=fixme
        log.info("Forcing the recreation of the service")
        ret["comment"] = "The configmap is already present. Forcing recreation"
        res = __salt__["kubernetes.replace_configmap"](
            name=name,
            namespace=namespace,
            data=data,
            source=source,
            template=template,
            saltenv=__env__,
            **kwargs,
        )

    ret["changes"] = {"data": res["data"]}
    ret["result"] = True
    return ret


def pod_absent(name, namespace="default", **kwargs):
    """
    Ensures that the named pod is absent from the given namespace.

    name
        The name of the pod

    namespace
        The name of the namespace
    """

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    pod = __salt__["kubernetes.show_pod"](name, namespace, **kwargs)

    if pod is None:
        ret["result"] = True if not __opts__["test"] else None
        ret["comment"] = "The pod does not exist"
        return ret

    if __opts__["test"]:
        ret["comment"] = "The pod is going to be deleted"
        ret["result"] = None
        return ret

    res = __salt__["kubernetes.delete_pod"](name, namespace, **kwargs)
    if res["code"] == 200 or res["code"] is None:
        ret["result"] = True
        ret["changes"] = {"kubernetes.pod": {"new": "absent", "old": "present"}}
        if res["code"] is None:
            ret["comment"] = "In progress"
        else:
            ret["comment"] = res["message"]
    else:
        ret["comment"] = f"Something went wrong, response: {res}"

    return ret


def pod_present(
    name,
    namespace="default",
    metadata=None,
    spec=None,
    source="",
    template="",
    **kwargs,
):
    """
    Ensures that the named pod is present inside of the specified
    namespace with the given metadata and spec.
    If the pod exists it will be replaced.

    name
        The name of the pod.

    namespace
        The namespace holding the pod. The 'default' one is going to be
        used unless a different one is specified.

    metadata
        The metadata of the pod object.

    spec
        The spec of the pod object.

    source
        A file containing the definition of the pod (metadata and
        spec) in the official kubernetes format.

    template
        Template engine to be used to render the source file.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if (metadata or spec) and source:
        return _error(
            ret, "'source' cannot be used in combination with 'metadata' or 'spec'"
        )

    if metadata is None:
        metadata = {}

    if spec is None:
        spec = {}

    pod = __salt__["kubernetes.show_pod"](name, namespace, **kwargs)

    if pod is None:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The pod is going to be created"
            return ret
        res = __salt__["kubernetes.create_pod"](
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec,
            source=source,
            template=template,
            saltenv=__env__,
            **kwargs,
        )
        ret["changes"][f"{namespace}.{name}"] = {"old": {}, "new": res}
    else:
        if __opts__["test"]:
            ret["result"] = None
            return ret

        # TODO: fix replace_namespaced_pod validation issues
        ret["comment"] = (
            "salt is currently unable to replace a pod without "
            "deleting it. Please perform the removal of the pod requiring "
            "the 'pod_absent' state if this is the desired behaviour."
        )
        ret["result"] = False
        return ret

    ret["changes"] = {"metadata": metadata, "spec": spec}
    ret["result"] = True
    return ret


def node_label_absent(name, node, **kwargs):
    """
    Ensures that the named label is absent from the node.

    name
        The name of the label

    node
        The name of the node
    """

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    labels = __salt__["kubernetes.node_labels"](node, **kwargs)

    if name not in labels:
        ret["result"] = True if not __opts__["test"] else None
        ret["comment"] = "The label does not exist"
        return ret

    if __opts__["test"]:
        ret["comment"] = "The label is going to be deleted"
        ret["result"] = None
        return ret

    __salt__["kubernetes.node_remove_label"](node_name=node, label_name=name, **kwargs)

    ret["result"] = True
    ret["changes"] = {"kubernetes.node_label": {"new": "absent", "old": "present"}}
    ret["comment"] = "Label removed from node"

    return ret


def node_label_folder_absent(name, node, **kwargs):
    """
    Ensures the label folder doesn't exist on the specified node.

    name
        The name of label folder

    node
        The name of the node
    """

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    labels = __salt__["kubernetes.node_labels"](node, **kwargs)

    folder = name.strip("/") + "/"
    labels_to_drop = []
    new_labels = []
    for label in labels:
        if label.startswith(folder):
            labels_to_drop.append(label)
        else:
            new_labels.append(label)

    if not labels_to_drop:
        ret["result"] = True if not __opts__["test"] else None
        ret["comment"] = "The label folder does not exist"
        return ret

    if __opts__["test"]:
        ret["comment"] = "The label folder is going to be deleted"
        ret["result"] = None
        return ret

    for label in labels_to_drop:
        __salt__["kubernetes.node_remove_label"](
            node_name=node, label_name=label, **kwargs
        )

    ret["result"] = True
    ret["changes"] = {
        "kubernetes.node_label_folder_absent": {"old": list(labels), "new": new_labels}
    }
    ret["comment"] = "Label folder removed from node"

    return ret


def node_label_present(name, node, value, **kwargs):
    """
    Ensures that the named label is set on the named node
    with the given value.
    If the label exists it will be replaced.

    name
        The name of the label.

    value
        Value of the label.

    node
        Node to change.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    labels = __salt__["kubernetes.node_labels"](node, **kwargs)

    if name not in labels:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The label is going to be set"
            return ret
        __salt__["kubernetes.node_add_label"](
            label_name=name, label_value=value, node_name=node, **kwargs
        )
    elif labels[name] == value:
        ret["result"] = True
        ret["comment"] = "The label is already set and has the specified value"
        return ret
    else:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The label is going to be updated"
            return ret

        ret["comment"] = "The label is already set, changing the value"
        __salt__["kubernetes.node_add_label"](
            node_name=node, label_name=name, label_value=value, **kwargs
        )

    old_labels = copy.copy(labels)
    labels[name] = value

    ret["changes"][f"{node}.{name}"] = {"old": old_labels, "new": labels}
    ret["result"] = True

    return ret
