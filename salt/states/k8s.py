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
from __future__ import absolute_import, unicode_literals, print_function

# Import salt libs
import salt.utils.versions


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
    .. deprecated:: 2017.7.0
        This state has been moved to :py:func:`kubernetes.node_label_present
        <salt.states.kubernetes.node_label_present`.

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

    msg = (
        'The k8s.label_present state has been replaced by '
        'kubernetes.node_label_present. Update your SLS to use the new '
        'function name to get rid of this warning.'
    )
    salt.utils.versions.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)

    return ret


def label_absent(
        name,
        node=None,
        apiserver=None):
    '''
    .. deprecated:: 2017.7.0
        This state has been moved to :py:func:`kubernetes.node_label_absent
        <salt.states.kubernetes.node_label_absent`.

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

    msg = (
        'The k8s.label_absent state has been replaced by '
        'kubernetes.node_label_absent. Update your SLS to use the new '
        'function name to get rid of this warning.'
    )
    salt.utils.versions.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)

    return ret


def label_folder_absent(
        name,
        node=None,
        apiserver=None):
    '''
    .. deprecated:: 2017.7.0
        This state has been moved to :py:func:`kubernetes.node_label_folder_absent
        <salt.states.kubernetes.node_label_folder_absent`.

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

    msg = (
        'The k8s.label_folder_absent state has been replaced by '
        'kubernetes.node_label_folder_absent. Update your SLS to use the new '
        'function name to get rid of this warning.'

    )
    salt.utils.versions.warn_until('Fluorine', msg)
    ret.setdefault('warnings', []).append(msg)

    return ret
