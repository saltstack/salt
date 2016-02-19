# -*- coding: utf-8 -*-
'''
Manage Kubernetes

.. versionadded:: 2016.3.0

.. code-block:: yaml

    kube_label_1:
      k8s.label_present:
        - name: mylabel
        - value: myvalue
        - node: myothernodename
        - apiserver: http://mykubeapiserer:8080

    kube_label_2:
      k8s.label_absent:
        - name: mylabel
        - node: myothernodename
        - apiserver: http://mykubeapiserer:8080

    kube_label_3:
      k8s.label_folder_present:
        - name: mylabel
        - node: myothernodename
        - apiserver: http://mykubeapiserer:8080
'''

__virtualname__ = 'k8s'


def __virtual__():
    '''Load only if kubernetes module is available.'''
    if 'k8s.get_labels' not in __salt__:
        return False
    return True


def label_present(
        name,
        value,
        node=None,
        apiserver=None):
    '''
    Ensure the label exists on the kube node.

    name
        Name of the label.

    value
        Value of the label.

    node
        Override node ID.

    apiserver
        K8S apiserver URL.

    '''
    # Use salt k8s module to set label
    ret = __salt__['k8s.label_present'](name, value, node, apiserver)

    return ret


def label_absent(
        name,
        node=None,
        apiserver=None):
    '''
    Ensure the label doesn't exist on the kube node.

    name
        Name of the label.

    node
        Override node ID.

    apiserver
        K8S apiserver URL.

    '''
    # Use salt k8s module to set label
    ret = __salt__['k8s.label_absent'](name, node, apiserver)

    return ret


def label_folder_absent(
        name,
        node=None,
        apiserver=None):
    '''
    Ensure the label folder doesn't exist on the kube node.

    name
        Name of the label folder.

    node
        Override node ID.

    apiserver
        K8S apiserver URL.

    '''
    # Use salt k8s module to set label
    ret = __salt__['k8s.folder_absent'](name, node, apiserver)

    return ret
