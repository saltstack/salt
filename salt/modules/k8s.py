# -*- coding: utf-8 -*-
'''
Salt module to manage Kubernetes cluster

.. versionadded:: 2016.3.0

Roadmap:

* Remove python-requests dependency
* Add creation of K8S objects (pod, rc, service, ...)
* Add replace of K8S objects (pod, rc, service, ...)
* Add deletion of K8S objects (pod, rc, service, ...)
* Add rolling update
* Add (auto)scalling

'''

from __future__ import absolute_import

import os
import re
import json
import logging as logger

# TODO Remove requests dependency
# Import third party libs
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import salt.utils


__virtualname__ = 'k8s'

# Setup the logger                                                              
log = logger.getLogger(__name__)


def __virtual__():
    '''Load load if python-requests is installed.'''
    if not HAS_REQUESTS:
        return False
    return __virtualname__


def _guess_apiserver(apiserver_url=None):
    '''Try to guees the kubemaster url from environ,
    then from `/etc/kubernetes/config` file
    '''
    default_config = "/etc/kubernetes/config"
    if apiserver_url is not None:
        return apiserver_url
    if "KUBERNETES_MASTER" in os.environ:
        apiserver_url = os.environ.get("KUBERNETES_MASTER")
    elif __salt__['config.get']('k8s:master'):
        apiserver_url = __salt__['config.get']('k8s:master')
    elif os.path.exists(default_config) or __salt__['config.get']('k8s:config', ""):
        config = __salt__['config.get']('k8s:config', default_config)
        kubeapi_regex = re.compile("""KUBE_MASTER=['"]--master=(.*)['"]""",
                                   re.MULTILINE)
        with salt.utils.fopen(config) as fh_k8s:
            for line in fh_k8s.readlines():
                match_line = kubeapi_regex.match(line)
            if match_line:
                apiserver_url = match_line.group(1)
    else:
        apiserver_url = "http://127.0.0.1:8080"
        log.debug("discoverd k8s API server address: {}".format(apiserver_url))
    return apiserver_url


def _guess_node_id(node):
    '''Try to guess kube node ID using salt minion ID'''
    if node is None:
        return __salt__['grains.get']('id')
    return node


def _get_labels(node, apiserver_url):
    '''Get all labels from a kube node.'''
    # Prepare URL
    url = apiserver_url + "/api/v1/nodes/" + node
    # Make request
    ret = requests.get(url)
    # Check requests status
    try:
        ret.raise_for_status()
    except requests.HTTPError as exp:
        if ret.status_code == 404:
            return "Node {0} doesn't exist".format(node)
        else:
            return exp
    # Get and return labels
    return ret.json().get('metadata', {}).get('labels', {})


def _get_obj_name(k8s_obj):
    '''Get name or names out of json result'''
    if isinstance(k8s_obj, dict):
        return [k8s_obj.get("metadata",{}).get("name", "")]
    elif isinstance(k8s_obj, (list, tuple)):
        names = []
        for i in k8s_obj:
            names.append(i.get("metadata",{}).get("name", ""))
        return names
    else:
        return "Unknown type"


def _get_namespaces(apiserver_url, name=""):
    '''Get namespace is namespace is defined otherwise return all namespaces'''
    # Prepare URL
    url = apiserver_url + "/api/v1/namespaces/" +  name
    # Make request
    ret = requests.get(url)
    # Check requests status
    try:
        ret.raise_for_status()
    except requests.HTTPError as exp:
        if ret.status_code == 404:
            return "Namespace {0} doesn't exist".format(name)
        else:
            return exp
    # Get and return labels
    return ret.json()


def _set_labels(node, apiserver_url, labels):
    '''Replace labels dict by a new one'''
    # Prepare URL
    url = apiserver_url + "/api/v1/nodes/" + node
    # Prepare data
    data = [{"op": "replace", "path": "/metadata/labels", "value": labels}]
    # Prepare headers
    headers = {"Content-Type": "application/json-patch+json"}
    # Make request
    ret = requests.patch(url, headers=headers, json=data)
    # Check requests status
    try:
        ret.raise_for_status()
    except requests.HTTPError as exp:
        if ret.status_code == 404:
            return "Node {0} doesn't exist".format(node)
        else:
            return exp
    return ret


def _create_namespace(namespace, apiserver_url):
    ''' create namespace on the defined k8s cluster '''
    # Prepare URL
    url = apiserver_url + "/api/v1/namespaces"
    # Prepare data
    data = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": namespace,
        }
    }
    log.trace("namespace creation requests: {}".format(data))
    # Prepare headers
    headers = {"Content-Type": "application/json"}
    # Make request
    ret = requests.post(url, headers=headers, data=json.dumps(data))
    # Check requests status
    try:
        ret.raise_for_status()
    except requests.HTTPError as exp:
        if ret.status_code == 405:
            return "Not allowed".format(node)
        return exp
    return ret


def get_labels(node=None, apiserver_url=None):
    '''
    Get labels from the current node

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.get_labels
        salt '*' k8s.get_labels kube-node.cluster.local http://kube-master.cluster.local

    '''
    # Get salt minion ID
    node = _guess_node_id(node)
    # Try to get kubernetes master
    apiserver_url = _guess_apiserver(apiserver_url)
    if apiserver_url is None:
        return False

    # Get data
    ret = _get_labels(node, apiserver_url)
    return {"labels": ret}


def get_namespaces(namespace="", apiserver_url=None):
    '''
    Get k8s namespaces

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.get_namespaces
        salt '*' k8s.get_namespaces namespace_name http://kube-master.cluster.local

    '''
    # Try to get kubernetes master
    apiserver_url = _guess_apiserver(apiserver_url)
    if apiserver_url is None:
        return False

    # Get data
    ret = _get_namespaces(apiserver_url, namespace)
    return {"namespaces": ret}

def label_present(
        name,
        value,
        node=None,
        apiserver_url=None):
    '''
    Set label to the current node

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.label_present hw/disktype ssd

        salt '*' k8s.label_present hw/disktype ssd kube-node.cluster.local http://kube-master.cluster.local

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # Get salt minion ID
    node = _guess_node_id(node)
    # Try to get kubernetes master
    apiserver_url = _guess_apiserver(apiserver_url)
    if apiserver_url is None:
        return False

    # Get all labels
    labels = _get_labels(node, apiserver_url)

    if name not in labels:
        # This is a new label
        ret['changes'] = {name: value}
        labels[name] = str(value)
        _set_labels(node, apiserver_url, labels)
        ret['comment'] = "Label {0} created".format(name)
    elif labels.get(name) != str(value):
        # This is a old label and we are going to edit it
        ret['changes'] = {name: str(value)}
        labels[name] = value
        _set_labels(node, apiserver_url, labels)
        ret['comment'] = "Label {0} updated".format(name)
    else:
        # This is a old label and it has already the wanted value
        ret['comment'] = "Label {0} already set".format(name)

    return ret


def label_absent(
        name,
        node=None,
        apiserver_url=None):
    '''
    Delete label to the current node

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.label_absent hw/disktype
        salt '*' k8s.label_absent hw/disktype kube-node.cluster.local http://kube-master.cluster.local

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # Get salt minion ID
    node = _guess_node_id(node)
    # Try to get kubernetes master
    apiserver_url = _guess_apiserver(apiserver_url)
    if apiserver_url is None:
        return False

    # Get all labels
    old_labels = _get_labels(node, apiserver_url)
    # Prepare a temp labels dict
    labels = dict([(key, value) for key, value in old_labels.items()
                   if key != name])
    # Compare old labels and what we want
    if labels == old_labels:
        # Label already absent
        ret['comment'] = "Label {0} already absent".format(name)
    else:
        # Label needs to be delete
        _set_labels(node, apiserver_url, labels)
        ret['changes'] = {"deleted": name}
        ret['comment'] = "Label {0} absent".format(name)

    return ret


def label_folder_absent(
        name,
        node=None,
        apiserver_url=None):
    '''
    Delete label folder to the current node

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.label_folder_absent hw
        salt '*' k8s.label_folder_absent hw/ kube-node.cluster.local http://kube-master.cluster.local

    '''
    folder = name.strip("/") + "/"
    ret = {'name': folder, 'result': True, 'comment': '', 'changes': {}}

    # Get salt minion ID
    node = _guess_node_id(node)
    # Try to get kubernetes master
    apiserver_url = _guess_apiserver(apiserver_url)
    if apiserver_url is None:
        return False

    # Get all labels
    old_labels = _get_labels(node, apiserver_url)
    # Prepare a temp labels dict
    labels = dict([(key, value) for key, value in old_labels.items()
                   if not key.startswith(folder)])
    # Prepare a temp labels dict
    if labels == old_labels:
        # Label already absent
        ret['comment'] = "Label folder {0} already absent".format(folder)
    else:
        # Label needs to be delete
        _set_labels(node, apiserver_url, labels)
        ret['changes'] = {"deleted": folder}
        ret['comment'] = "Label folder {0} absent".format(folder)

    return ret

def namespace_present(
        name,
        apiserver_url=None):
    '''
    Create k8s namespace 

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.namespace_present {namespace name}

        salt '*' k8s.namespace_present {namespace name} http://kube-master.cluster.local

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # Try to get kubernetes master
    apiserver_url = _guess_apiserver(apiserver_url)
    if apiserver_url is None:
        return False

    # Get all labels
    namespaces = _get_obj_name(_get_namespaces(apiserver_url, name))

    if name not in namespaces:
        # This is a new namespace
        ret['changes'] = {name}
        _create_namespace(name, apiserver_url)
        ret['comment'] = "Namespace {0} created".format(name)
    else:
        # This is a old label and it has already the wanted value
        ret['comment'] = "Namespace {0} already present".format(name)

    return ret
