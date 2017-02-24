# -*- coding: utf-8 -*-
'''
Manage kubernetes resources as salt states
==========================================

NOTE: This module requires the proper pillar values set. See
salt.modules.kubernetes for more information.

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

'''
from __future__ import absolute_import

import logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if the kubernetes module is available in __salt__
    '''
    return 'kubernetes.ping' in __salt__


def _error(ret, err_msg):
    '''
    Helper function to propagate errors to
    the end user.
    '''
    ret['result'] = False
    ret['comment'] = err_msg
    return ret


def deployment_absent(name, namespace='default', **kwargs):
    '''
    Ensures that the named deployment is absent from the given namespace.

    name
        The name of the deployment

    namespace
        The name of the namespace
    '''

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    deployment = __salt__['kubernetes.show_deployment'](name, namespace, **kwargs)

    if deployment is None:
        ret['result'] = True if not __opts__['test'] else None
        ret['comment'] = 'The deployment does not exist'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The deployment is going to be deleted'
        ret['result'] = None
        return ret

    res = __salt__['kubernetes.delete_deployment'](name, namespace, **kwargs)
    if res['code'] == 200:
        ret['result'] = True
        ret['changes'] = {
            'kubernetes.deployment': {
                'new': 'absent', 'old': 'present'}}

    ret['comment'] = res['message']
    return ret


def deployment_present(
        name,
        namespace='default',
        metadata=None,
        spec=None,
        source='',
        template='',
        **kwargs):
    '''
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
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if (metadata or spec) and source:
        return _error(
            ret,
            '\'source\' cannot be used in combination with \'metadata\' or '
            '\'spec\''
        )

    if metadata is None:
        metadata = {}

    if spec is None:
        spec = {}

    deployment = __salt__['kubernetes.show_deployment'](name, namespace, **kwargs)

    if deployment is None:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'The deployment is going to be created'
            return ret
        res = __salt__['kubernetes.create_deployment'](name=name,
                                                       namespace=namespace,
                                                       metadata=metadata,
                                                       spec=spec,
                                                       source=source,
                                                       template=template,
                                                       saltenv=__env__,
                                                       **kwargs)
        ret['changes']['{0}.{1}'.format(namespace, name)] = {
            'old': {},
            'new': res}
    else:
        if __opts__['test']:
            ret['result'] = None
            return ret

        # TODO: improve checks  # pylint: disable=fixme
        log.info('Forcing the recreation of the deployment')
        res = __salt__['kubernetes.replace_deployment'](
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec,
            source=source,
            template=template,
            saltenv=__env__,
            **kwargs)

    ret['changes'] = {
        'metadata': metadata,
        'spec': spec
    }
    ret['comment'] = 'The deployment is already present. Forcing recreation'
    ret['result'] = True
    return ret


def service_present(
        name,
        namespace='default',
        metadata=None,
        spec=None,
        source='',
        template='',
        **kwargs):
    '''
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
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if (metadata or spec) and source:
        return _error(
            ret,
            '\'source\' cannot be used in combination with \'metadata\' or '
            '\'spec\''
        )

    if metadata is None:
        metadata = {}

    if spec is None:
        spec = {}

    service = __salt__['kubernetes.show_service'](name, namespace, **kwargs)

    if service is None:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'The service is going to be created'
            return ret
        res = __salt__['kubernetes.create_service'](name=name,
                                                    namespace=namespace,
                                                    metadata=metadata,
                                                    spec=spec,
                                                    source=source,
                                                    template=template,
                                                    saltenv=__env__,
                                                    **kwargs)
        ret['changes']['{0}.{1}'.format(namespace, name)] = {
            'old': {},
            'new': res}
    else:
        if __opts__['test']:
            ret['result'] = None
            return ret

        # TODO: improve checks  # pylint: disable=fixme
        log.info('Forcing the recreation of the service')
        res = __salt__['kubernetes.replace_service'](
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec,
            source=source,
            template=template,
            old_service=service,
            saltenv=__env__,
            **kwargs)

    ret['changes'] = {
        'metadata': metadata,
        'spec': spec
    }
    ret['comment'] = 'The service is already present. Forcing recreation'
    ret['result'] = True
    return ret


def service_absent(name, namespace='default', **kwargs):
    '''
    Ensures that the named service is absent from the given namespace.

    name
        The name of the service

    namespace
        The name of the namespace
    '''

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    service = __salt__['kubernetes.show_service'](name, namespace, **kwargs)

    if service is None:
        ret['result'] = True if not __opts__['test'] else None
        ret['comment'] = 'The service does not exist'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The service is going to be deleted'
        ret['result'] = None
        return ret

    res = __salt__['kubernetes.delete_service'](name, namespace, **kwargs)
    if res['code'] == 200:
        ret['result'] = True
        ret['changes'] = {
            'kubernetes.service': {
                'new': 'absent', 'old': 'present'}}
    ret['comment'] = res['message']
    return ret
