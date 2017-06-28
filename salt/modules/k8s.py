# -*- coding: utf-8 -*-
'''
Salt module to manage Kubernetes cluster

.. versionadded:: 2016.3.0

Roadmap:

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
import base64
import salt.ext.six as six
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module

# TODO Remove requests dependency

import salt.utils
import salt.utils.http as http

__virtualname__ = 'k8s'

# Setup the logger
log = logger.getLogger(__name__)


def __virtual__():
    '''Load load if python-requests is installed.'''
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
        # we failed to discover, lets use k8s default address
        apiserver_url = "http://127.0.0.1:8080"
    log.debug("Discoverd k8s API server address: {0}".format(apiserver_url))
    return apiserver_url


def _kpost(url, data):
    ''' create any object in kubernetes based on URL '''

    # Prepare headers
    headers = {"Content-Type": "application/json"}
    # Make request
    log.trace("url is: {0}, data is: {1}".format(url, data))
    ret = http.query(url, method='POST', header_dict=headers, data=json.dumps(data))
    # Check requests status
    if ret.get('error'):
        return ret
    else:
        return json.loads(ret.get('body'))


def _kput(url, data):
    ''' put any object in kubernetes based on URL '''

    # Prepare headers
    headers = {"Content-Type": "application/json"}
    # Make request
    ret = http.query(url, method='PUT', header_dict=headers, data=json.dumps(data))
    # Check requests status
    if ret.get('error'):
        return ret
    else:
        return json.loads(ret.get('body'))


def _kpatch(url, data):
    ''' patch any object in kubernetes based on URL '''

    # Prepare headers
    headers = {"Content-Type": "application/json-patch+json"}
    # Make request
    ret = http.query(url, method='PATCH', header_dict=headers,
                     data=json.dumps(data))
    # Check requests status
    if ret.get('error'):
        log.error("Got an error: {0}".format(ret.get("error")))
        return ret
    else:
        return json.loads(ret.get('body'))


def _kname(obj):
    '''Get name or names out of json result from API server'''
    if isinstance(obj, dict):
        return [obj.get("metadata", {}).get("name", "")]
    elif isinstance(obj, (list, tuple)):
        names = []
        for i in obj:
            names.append(i.get("metadata", {}).get("name", ""))
        return names
    else:
        return "Unknown type"


def _is_dns_subdomain(name):
    ''' Check that name is DNS subdomain: One or more lowercase rfc1035/rfc1123
    labels separated by '.' with a maximum length of 253 characters '''

    dns_subdomain = re.compile(r"""^[a-z0-9\.-]{1,253}$""")
    if dns_subdomain.match(name):
        log.debug("Name: {0} is valid DNS subdomain".format(name))
        return True
    else:
        log.debug("Name: {0} is not valid DNS subdomain".format(name))
        return False


def _is_port_name(name):
    ''' Check that name is IANA service: An alphanumeric (a-z, and 0-9) string,
    with a maximum length of 15 characters, with the '-' character allowed
    anywhere except the first or the last character or adjacent to another '-'
    character, it must contain at least a (a-z) character '''

    port_name = re.compile("""^[a-z0-9]{1,15}$""")
    if port_name.match(name):
        return True
    else:
        return False


def _is_dns_label(name):
    ''' Check that name is DNS label: An alphanumeric (a-z, and 0-9) string,
    with a maximum length of 63 characters, with the '-' character allowed
    anywhere except the first or last character, suitable for use as a hostname
    or segment in a domain name '''

    dns_label = re.compile(r"""^[a-z0-9][a-z0-9\.-]{1,62}$""")
    if dns_label.match(name):
        return True
    else:
        return False


def _guess_node_id(node):
    '''Try to guess kube node ID using salt minion ID'''
    if node is None:
        return __salt__['grains.get']('id')
    return node


def _get_labels(node, apiserver_url):
    '''Get all labels from a kube node.'''
    # Prepare URL
    url = "{0}/api/v1/nodes/{1}".format(apiserver_url, node)
    # Make request
    ret = http.query(url)
    # Check requests status
    if 'body' in ret:
        ret = json.loads(ret.get('body'))
    elif ret.get('status', 0) == 404:
        return "Node {0} doesn't exist".format(node)
    else:
        return ret
    # Get and return labels
    return ret.get('metadata', {}).get('labels', {})


def _set_labels(node, apiserver_url, labels):
    '''Replace labels dict by a new one'''
    # Prepare URL
    url = "{0}/api/v1/nodes/{1}".format(apiserver_url, node)
    # Prepare data
    data = [{"op": "replace", "path": "/metadata/labels", "value": labels}]
    # Make request
    ret = _kpatch(url, data)
    if ret.get("status") == 404:
        return "Node {0} doesn't exist".format(node)
    return ret


def get_labels(node=None, apiserver_url=None):
    '''
    .. versionadded:: 2016.3.0
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


def label_present(name, value, node=None, apiserver_url=None):
    '''
    .. versionadded:: 2016.3.0

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
        res = _set_labels(node, apiserver_url, labels)
        if res.get('status') == 409:
            # there is an update during operation, need to retry
            log.debug("Got 409, will try later")
            ret['changes'] = {}
            ret['comment'] = "Could not create label {0}, please retry".format(name)
        else:
            ret['comment'] = "Label {0} created".format(name)
    elif labels.get(name) != str(value):
        # This is a old label and we are going to edit it
        ret['changes'] = {name: str(value)}
        labels[name] = str(value)
        res = _set_labels(node, apiserver_url, labels)
        if res.get('status') == 409:
            # there is an update during operation, need to retry
            log.debug("Got 409, will try later")
            ret['changes'] = {}
            ret['comment'] = "Could not update label {0}, please retry".format(name)
        else:
            ret['comment'] = "Label {0} updated".format(name)
    else:
        # This is a old label and it has already the wanted value
        ret['comment'] = "Label {0} already set".format(name)

    return ret


def label_absent(name, node=None, apiserver_url=None):
    '''
    .. versionadded:: 2016.3.0

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
        res = _set_labels(node, apiserver_url, labels)
        if res.get('status') == 409:
            # there is an update during operation, need to retry
            log.debug("Got 409, will try later")
            ret['changes'] = {}
            ret['comment'] = "Could not delete label {0}, please retry".format(name)
        else:
            ret['changes'] = {"deleted": name}
            ret['comment'] = "Label {0} absent".format(name)

    return ret


def label_folder_absent(name, node=None, apiserver_url=None):
    '''
    .. versionadded:: 2016.3.0

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
        res = _set_labels(node, apiserver_url, labels)
        if res.get('status') == 409:
            log.debug("Got 409, will try later")
            ret['changes'] = {}
            ret['comment'] = "Could not delete label folder {0}, please retry".format(folder)
        else:
            ret['changes'] = {"deleted": folder}
            ret['comment'] = "Label folder {0} absent".format(folder)

    return ret


# Namespaces
def _get_namespaces(apiserver_url, name=""):
    '''Get namespace is namespace is defined otherwise return all namespaces'''
    # Prepare URL
    url = "{0}/api/v1/namespaces/{1}".format(apiserver_url, name)
    # Make request
    ret = http.query(url)
    if ret.get("body"):
        return json.loads(ret.get("body"))
    else:
        return None


def _create_namespace(namespace, apiserver_url):
    ''' create namespace on the defined k8s cluster '''
    # Prepare URL
    url = "{0}/api/v1/namespaces".format(apiserver_url)
    # Prepare data
    data = {
        "kind": "Namespace",
        "apiVersion": "v1",
        "metadata": {
            "name": namespace,
        }
    }
    log.trace("namespace creation requests: {0}".format(data))
    # Make request
    ret = _kpost(url, data)
    log.trace("result is: {0}".format(ret))
    # Check requests status
    return ret


def create_namespace(name, apiserver_url=None):
    '''
    .. versionadded:: 2016.3.0

    Create kubernetes namespace from the name, similar to the functionality added to kubectl since v.1.2.0:
    .. code-block:: bash

        kubectl create namespaces namespace-name

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.create_namespace namespace_name

        salt '*' k8s.create_namespace namespace_name http://kube-master.cluster.local

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # Try to get kubernetes master
    apiserver_url = _guess_apiserver(apiserver_url)
    if apiserver_url is None:
        return False

    if not _get_namespaces(apiserver_url, name):
        # This is a new namespace
        _create_namespace(name, apiserver_url)
        ret['changes'] = name
        ret['comment'] = "Namespace {0} created".format(name)
    else:
        ret['comment'] = "Namespace {0} already present".format(name)
    return ret


def get_namespaces(namespace="", apiserver_url=None):
    '''
    .. versionadded:: 2016.3.0

    Get one or all kubernetes namespaces.

    If namespace parameter is omitted, all namespaces will be returned back to user, similar to following kubectl example:

    .. code-block:: bash

        kubectl get namespaces -o json

    In case namespace is set by user, the output will be similar to the one from kubectl:

    .. code-block:: bash

        kubectl get namespaces namespace_name -o json


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
    return ret


# Secrets
def _get_secrets(namespace, name, apiserver_url):
    '''Get secrets of the namespace.'''
    # Prepare URL
    url = "{0}/api/v1/namespaces/{1}/secrets/{2}".format(apiserver_url,
                                                         namespace, name)
    # Make request
    ret = http.query(url)
    if ret.get("body"):
        return json.loads(ret.get("body"))
    else:
        return None


def _update_secret(namespace, name, data, apiserver_url):
    '''Replace secrets data by a new one'''
    # Prepare URL
    url = "{0}/api/v1/namespaces/{1}/secrets/{2}".format(apiserver_url,
                                                         namespace, name)
    # Prepare data
    data = [{"op": "replace", "path": "/data", "value": data}]
    # Make request
    ret = _kpatch(url, data)
    if ret.get("status") == 404:
        return "Node {0} doesn't exist".format(url)
    return ret


def _create_secret(namespace, name, data, apiserver_url):
    ''' create namespace on the defined k8s cluster '''
    # Prepare URL
    url = "{0}/api/v1/namespaces/{1}/secrets".format(apiserver_url, namespace)
    # Prepare data
    request = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
        "data": data
    }
    # Make request
    ret = _kpost(url, request)
    return ret


def _is_valid_secret_file(filename):
    if os.path.exists(filename) and os.path.isfile(filename):
        log.debug("File: {0} is valid secret file".format(filename))
        return True
    log.warning("File: {0} does not exists or not file".format(filename))
    return False


def _file_encode(filename):
    log.trace("Encoding secret file: {0}".format(filename))
    with salt.utils.fopen(filename, "rb") as f:
        data = f.read()
        return base64.b64encode(data)


def _decode_secrets(secrets):
    items = secrets.get("items", [])
    if items:
        for i, secret in enumerate(items):
            log.trace(i, secret)
            for k, v in six.iteritems(secret.get("data", {})):
                items[i]['data'][k] = base64.b64decode(v)
        secrets["items"] = items
        return secrets
    else:
        for k, v in six.iteritems(secrets.get("data", {})):
            secrets['data'][k] = base64.b64decode(v)
        return secrets


def get_secrets(namespace, name="", apiserver_url=None, decode=False, brief=False):
    '''
    Get k8s namespaces

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.get_secrets namespace_name
        salt '*' k8s.get_secrets namespace_name secret_name http://kube-master.cluster.local

    '''
    # Try to get kubernetes master
    apiserver_url = _guess_apiserver(apiserver_url)
    if apiserver_url is None:
        return False

    # Get data
    if not decode:
        ret = _get_secrets(namespace, name, apiserver_url)
    else:
        ret = _decode_secrets(_get_secrets(namespace, name, apiserver_url))
    return ret


def _source_encode(source, saltenv):
    try:
        source_url = _urlparse(source)
    except TypeError:
        return '', {}, ('Invalid format for source parameter')

    protos = ('salt', 'http', 'https', 'ftp', 'swift', 's3', 'file')

    log.trace("parsed source looks like: {0}".format(source_url))
    if not source_url.scheme or source_url.scheme == 'file':
        # just a regular file
        filename = os.path.abspath(source_url.path)
        sname = os.path.basename(filename)
        log.debug("Source is a regular local file: {0}".format(source_url.path))
        if _is_dns_subdomain(sname) and _is_valid_secret_file(filename):
            return sname, _file_encode(filename)
    else:
        if source_url.scheme in protos:
            # The source is a file on a server
            filename = __salt__['cp.cache_file'](source, saltenv)
            if not filename:
                log.warning("Source file: {0} can not be retrieved".format(source))
                return "", ""
            return os.path.basename(filename), _file_encode(filename)
    return "", ""


def update_secret(namespace, name, sources, apiserver_url=None, force=True, saltenv='base'):
    '''
    .. versionadded:: 2016.3.0

    alias to k8s.create_secret with update=true

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.update_secret namespace_name secret_name sources [apiserver_url] [force=true] [update=false] [saltenv='base']

    sources are either dictionary of {name: path, name1: path} pairs or array of strings defining paths.

    Example of paths array:

    .. code-block:: bash

    ['/full/path/filename', "file:///full/path/filename", "salt://secret/storage/file.txt", "http://user:password@securesite.com/secret-file.json"]

    Example of dictionaries:

    .. code-block:: bash

    {"nameit": '/full/path/fiename', name2: "salt://secret/storage/file.txt"}

    optional parameters accepted:

    force=[true] default value is true
    if the to False, secret will not be created in case one of the files is not
    valid kubernetes secret. e.g. capital letters in secret name or _
    in case force is set to True, wrong files will be skipped but secret will be created any way.

    saltenv=['base'] default value is base
    in case 'salt://' path is used, this parameter can change the visibility of files

    '''
    apiserver_url = _guess_apiserver(apiserver_url)

    ret = create_secret(namespace, name, sources, apiserver_url=apiserver_url,
                        force=force, update=True, saltenv=saltenv)
    return ret


def create_secret(namespace, name, sources, apiserver_url=None, force=False, update=False, saltenv='base'):
    '''
    .. versionadded:: 2016.3.0

    Create k8s secrets in the defined namespace from the list of files

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.create_secret namespace_name secret_name sources

        salt '*' k8s.create_secret namespace_name secret_name sources
        http://kube-master.cluster.local

    sources are either dictionary of {name: path, name1: path} pairs or array of strings defining paths.

    Example of paths array:

    .. code-block:: bash

    ['/full/path/filename', "file:///full/path/filename", "salt://secret/storage/file.txt", "http://user:password@securesite.com/secret-file.json"]

    Example of dictionaries:

    .. code-block:: bash

    {"nameit": '/full/path/fiename', name2: "salt://secret/storage/file.txt"}

    optional parameters accepted:

    update=[false] default value is false
    if set to false, and secret is already present on the cluster - warning will be returned and no changes to the secret will be done.
    In case it is set to "true" and secret is present but data is differ - secret will be updated.

    force=[true] default value is true
    if the to False, secret will not be created in case one of the files is not
    valid kubernetes secret. e.g. capital letters in secret name or _
    in case force is set to True, wrong files will be skipped but secret will be created any way.

    saltenv=['base'] default value is base
    in case 'salt://' path is used, this parameter can change the visibility of files

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not sources:
        return {'name': name, 'result': False, 'comment': 'No source available', 'changes': {}}

    apiserver_url = _guess_apiserver(apiserver_url)
    # we need namespace to create secret in it
    if not _get_namespaces(apiserver_url, namespace):
        if force:
            _create_namespace(namespace, apiserver_url)
        else:
            return {'name': name, 'result': False, 'comment': "Namespace doesn't exists", 'changes': {}}

    secret = _get_secrets(namespace, name, apiserver_url)
    if secret and not update:
        log.info("Secret {0} is already present on {1}".format(name, namespace))
        return {'name': name, 'result': False,
                'comment': 'Secret {0} is already present'.format(name),
                'changes': {}}

    data = {}

    for source in sources:
        log.debug("source is: {0}".format(source))
        if isinstance(source, dict):
            # format is array of dictionaries:
            # [{public_auth: salt://public_key}, {test: "/tmp/test"}]
            log.trace("source is dictionary: {0}".format(source))
            for k, v in six.iteritems(source):
                sname, encoded = _source_encode(v, saltenv)
                if sname == encoded == "":
                    ret['comment'] += "Source file {0} is missing or name is incorrect\n".format(v)
                    if force:
                        continue
                    else:
                        return ret
                data[k] = encoded
        elif isinstance(source, six.string_types):
            # expected format is array of filenames
            sname, encoded = _source_encode(source, saltenv)
            if sname == encoded == "":
                if force:
                    ret['comment'] += "Source file {0} is missing or name is incorrect\n".format(source)
                    continue
                else:
                    return ret
            data[sname] = encoded

    log.trace("secret data is: {0}".format(data))

    if secret and update:
        if not data:
            ret["comment"] += "Could not find source files or your sources are empty"
            ret["result"] = False
        elif secret.get("data") and data != secret.get("data"):
            res = _update_secret(namespace, name, data, apiserver_url)
            ret['comment'] = 'Updated secret'
            ret['changes'] = 'Updated secret'
        else:
            log.debug("Secret has not been changed on cluster, skipping it")
            ret['comment'] = 'Has not been changed on cluster, skipping it'
    else:
        res = _create_secret(namespace, name, data, apiserver_url)
    return ret


def delete_secret(namespace, name, apiserver_url=None, force=True):
    '''
    .. versionadded:: 2016.3.0

    Delete kubernetes secret in the defined namespace. Namespace is the mandatory parameter as well as name.

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.delete_secret namespace_name secret_name

        salt '*' k8s.delete_secret namespace_name secret_name http://kube-master.cluster.local

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # Try to get kubernetes master
    apiserver_url = _guess_apiserver(apiserver_url)
    if apiserver_url is None:
        return False

    # we need namespace to delete secret in it
    if not _get_namespaces(apiserver_url, namespace):
        return {'name': name, 'result': False,
                'comment': "Namespace doesn't exists, can't delete anything there",
                'changes': {}}

    url = "{0}/api/v1/namespaces/{1}/secrets/{2}".format(apiserver_url,
                                                         namespace, name)
    res = http.query(url, method='DELETE')
    if res.get('body'):
        ret['comment'] = "Removed secret {0} in {1} namespace".format(name,
                                                                      namespace)
    return ret
