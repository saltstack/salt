# -*- coding: utf-8 -*-
'''
State module to manage Elasticsearch Ingest pipelines

.. versionadded:: 2017.x
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
log = logging.getLogger(__name__)


def absent(name):
    '''
    Ensure that the named pipeline is absent

    name
        Name of the pipeline to remove
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    pipeline = __salt__['elasticsearch.pipeline_get'](id=name)
    if pipeline and name in pipeline:
        if __opts__['test']:
            ret['comment'] = 'Pipeline {0} will be removed'.format(name)
            ret['changes']['old'] = pipeline[name]
            ret['result'] = None
        else:
            try:
                ret['result'] = __salt__['elasticsearch.pipeline_delete'](id=name)
                if ret['result']:
                    ret['comment'] = 'Successfully removed pipeline {0}'.format(name)
                    ret['changes']['old'] = pipeline[name]
                else:
                    ret['comment'] = 'Failed to remove pipeline {0} for unknown reasons'.format(name)
            except Exception as e:
                ret['result'] = False
                ret['comment'] = str(e)
    else:
        ret['comment'] = 'Pipeline {0} is already absent'.format(name)

    return ret


def present(name, definition):
    '''
    .. versionadded:: 2017.3.0

    Ensure that the named pipeline is present.

    name
        Name of the index to add

    definition
        Required dict for creation parameters as per https://www.elastic.co/guide/en/elasticsearch/reference/master/pipeline.html

    **Example:**

    .. code-block:: yaml
        test_pipeline:
          elasticsearch_pipeline.present:
            - definition:
                description: example pipeline
                processors:
                  - set:
                      field: collector_timestamp_millis
                      value: '{{ '{{' }}_ingest.timestamp{{ '}}' }}'
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    pipeline = __salt__['elasticsearch.pipeline_get'](id=name)
    old = {}
    if pipeline and name in pipeline:
        old = pipeline[name]
    ret['changes'] = __utils__['dictdiffer.deep_diff'](old, definition)

    if ret['changes']:
        if __opts__['test']:
            if not pipeline:
                ret['comment'] = 'Pipeline {0} does not exist and will be created'.format(name)
            else:
                ret['comment'] = 'Pipeline {0} exists with wrong configuration and will be overriden'.format(name)

            ret['result'] = None
        else:
            try:
                output = __salt__['elasticsearch.pipeline_create'](id=name, body=definition)
                if output:
                    if not pipeline:
                        ret['comment'] = 'Successfully created pipeline {0}'.format(name)
                    else:
                        ret['comment'] = 'Successfully replaced pipeline {0}'.format(name)
                else:
                    ret['comment'] = 'Cannot create pipeline {0}, {1}'.format(name, output)
            except Exception as e:
                ret['result'] = False
                ret['comment'] = str(e)
    else:
        ret['comment'] = 'Index {0} is already present'.format(name)

    return ret
