# -*- coding: utf-8 -*-
'''
State module to manage Elasticsearch.

.. versionadded:: 2017.7.0
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import salt libs
from salt.ext import six
import salt.utils.json

log = logging.getLogger(__name__)


def index_absent(name):
    '''
    Ensure that the named index is absent.

    name
        Name of the index to remove
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    try:
        index = __salt__['elasticsearch.index_get'](index=name)
        if index and name in index:
            if __opts__['test']:
                ret['comment'] = 'Index {0} will be removed'.format(name)
                ret['changes']['old'] = index[name]
                ret['result'] = None
            else:
                ret['result'] = __salt__['elasticsearch.index_delete'](index=name)
                if ret['result']:
                    ret['comment'] = 'Successfully removed index {0}'.format(name)
                    ret['changes']['old'] = index[name]
                else:
                    ret['comment'] = 'Failed to remove index {0} for unknown reasons'.format(name)
        else:
            ret['comment'] = 'Index {0} is already absent'.format(name)
    except Exception as err:
        ret['result'] = False
        ret['comment'] = six.text_type(err)

    return ret


def index_present(name, definition=None):
    '''
    Ensure that the named index is present.

    name
        Name of the index to add
    definition
        Optional dict for creation parameters as per https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-create-index.html

    **Example:**

    .. code-block:: yaml

        # Default settings
        mytestindex:
          elasticsearch_index.present

        # Extra settings
        mytestindex2:
          elasticsearch_index.present:
            - definition:
                settings:
                  index:
                    number_of_shards: 10
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    try:
        index_exists = __salt__['elasticsearch.index_exists'](index=name)
        if not index_exists:
            if __opts__['test']:
                ret['comment'] = 'Index {0} does not exist and will be created'.format(name)
                ret['changes'] = {'new': definition}
                ret['result'] = None
            else:
                output = __salt__['elasticsearch.index_create'](index=name, body=definition)
                if output:
                    ret['comment'] = 'Successfully created index {0}'.format(name)
                    ret['changes'] = {'new': __salt__['elasticsearch.index_get'](index=name)[name]}
                else:
                    ret['result'] = False
                    ret['comment'] = 'Cannot create index {0}, {1}'.format(name, output)
        else:
            ret['comment'] = 'Index {0} is already present'.format(name)
    except Exception as err:
        ret['result'] = False
        ret['comment'] = six.text_type(err)

    return ret


def alias_absent(name, index):
    '''
    Ensure that the index alias is absent.

    name
        Name of the index alias to remove
    index
        Name of the index for the alias
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    try:
        alias = __salt__['elasticsearch.alias_get'](aliases=name, indices=index)
        if alias and alias.get(index, {}).get("aliases", {}).get(name, None) is not None:
            if __opts__['test']:
                ret['comment'] = 'Alias {0} for index {1} will be removed'.format(name, index)
                ret['changes']['old'] = alias.get(index, {}).get("aliases", {}).get(name, {})
                ret['result'] = None
            else:
                ret['result'] = __salt__['elasticsearch.alias_delete'](aliases=name, indices=index)
                if ret['result']:
                    ret['comment'] = 'Successfully removed alias {0} for index {1}'.format(name, index)
                    ret['changes']['old'] = alias.get(index, {}).get("aliases", {}).get(name, {})
                else:
                    ret['comment'] = 'Failed to remove alias {0} for index {1} for unknown reasons'.format(name, index)
        else:
            ret['comment'] = 'Alias {0} for index {1} is already absent'.format(name, index)
    except Exception as err:
        ret['result'] = False
        ret['comment'] = six.text_type(err)

    return ret


def alias_present(name, index, definition=None):
    '''
    Ensure that the named index alias is present.

    name
        Name of the alias
    index
        Name of the index
    definition
        Optional dict for filters as per https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-aliases.html

    **Example:**

    .. code-block:: yaml

        mytestalias:
          elasticsearch.alias_present:
            - index: testindex
            - definition:
                filter:
                  term:
                    user: kimchy
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    try:
        alias = __salt__['elasticsearch.alias_get'](aliases=name, indices=index)
        old = {}
        if alias:
            old = alias.get(index, {}).get("aliases", {}).get(name, {})
        if not definition:
            definition = {}

        ret['changes'] = __utils__['dictdiffer.deep_diff'](old, definition)

        if ret['changes'] or not definition:
            if __opts__['test']:
                if not old:
                    ret['comment'] = 'Alias {0} for index {1} does not exist and will be created'.format(name, index)
                else:
                    ret['comment'] = 'Alias {0} for index {1} exists with wrong configuration and will be overriden'.format(name, index)

                ret['result'] = None
            else:
                output = __salt__['elasticsearch.alias_create'](alias=name, indices=index, body=definition)
                if output:
                    if not old:
                        ret['comment'] = 'Successfully created alias {0} for index {1}'.format(name, index)
                    else:
                        ret['comment'] = 'Successfully replaced alias {0} for index {1}'.format(name, index)
                else:
                    ret['result'] = False
                    ret['comment'] = 'Cannot create alias {0} for index {1}, {2}'.format(name, index, output)
        else:
            ret['comment'] = 'Alias {0} for index {1} is already present'.format(name, index)
    except Exception as err:
        ret['result'] = False
        ret['comment'] = six.text_type(err)

    return ret


def index_template_absent(name):
    '''
    Ensure that the named index template is absent.

    name
        Name of the index to remove
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    try:
        index_template = __salt__['elasticsearch.index_template_get'](name=name)
        if index_template and name in index_template:
            if __opts__['test']:
                ret['comment'] = 'Index template {0} will be removed'.format(name)
                ret['changes']['old'] = index_template[name]
                ret['result'] = None
            else:
                ret['result'] = __salt__['elasticsearch.index_template_delete'](name=name)
                if ret['result']:
                    ret['comment'] = 'Successfully removed index template {0}'.format(name)
                    ret['changes']['old'] = index_template[name]
                else:
                    ret['comment'] = 'Failed to remove index template {0} for unknown reasons'.format(name)
        else:
            ret['comment'] = 'Index template {0} is already absent'.format(name)
    except Exception as err:
        ret['result'] = False
        ret['comment'] = six.text_type(err)

    return ret


def index_template_present(name, definition, check_definition=False):
    '''
    Ensure that the named index templat eis present.

    name
        Name of the index to add
    definition
        Required dict for creation parameters as per https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-templates.html
    check_definition
        If the template already exists and the definition is up to date

    **Example:**

    .. code-block:: yaml

        mytestindex2_template:
          elasticsearch_index_template.present:
            - definition:
                template: logstash-*
                order: 1
                settings:
                  number_of_shards: 1
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    try:
        index_template_exists = __salt__['elasticsearch.index_template_exists'](name=name)
        if not index_template_exists:
            if __opts__['test']:
                ret['comment'] = 'Index template {0} does not exist and will be created'.format(name)
                ret['changes'] = {'new': definition}
                ret['result'] = None
            else:
                output = __salt__['elasticsearch.index_template_create'](name=name, body=definition)
                if output:
                    ret['comment'] = 'Successfully created index template {0}'.format(name)
                    ret['changes'] = {'new': __salt__['elasticsearch.index_template_get'](name=name)[name]}
                else:
                    ret['result'] = False
                    ret['comment'] = 'Cannot create index template {0}, {1}'.format(name, output)
        else:
            if check_definition:
                definition_parsed = salt.utils.json.loads(definition)
                current_template = __salt__['elasticsearch.index_template_get'](name=name)[name]
                diff = __utils__['dictdiffer.deep_diff'](current_template, definition_parsed)
                if len(diff) != 0:
                    if __opts__['test']:
                        ret['comment'] = 'Index template {0} exist but need to be updated'.format(name)
                        ret['changes'] = diff
                        ret['result'] = None
                    else:
                        output = __salt__['elasticsearch.index_template_create'](name=name, body=definition)
                        if output:
                            ret['comment'] = 'Successfully updated index template {0}'.format(name)
                            ret['changes'] = diff
                        else:
                            ret['result'] = False
                            ret['comment'] = 'Cannot update index template {0}, {1}'.format(name, output)
                else:
                    ret['comment'] = 'Index template {0} is already present and up to date'.format(name)
            else:
                ret['comment'] = 'Index template {0} is already present'.format(name)
    except Exception as err:
        ret['result'] = False
        ret['comment'] = six.text_type(err)

    return ret


def pipeline_absent(name):
    '''
    Ensure that the named pipeline is absent

    name
        Name of the pipeline to remove
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    try:
        pipeline = __salt__['elasticsearch.pipeline_get'](id=name)
        if pipeline and name in pipeline:
            if __opts__['test']:
                ret['comment'] = 'Pipeline {0} will be removed'.format(name)
                ret['changes']['old'] = pipeline[name]
                ret['result'] = None
            else:
                ret['result'] = __salt__['elasticsearch.pipeline_delete'](id=name)
                if ret['result']:
                    ret['comment'] = 'Successfully removed pipeline {0}'.format(name)
                    ret['changes']['old'] = pipeline[name]
                else:
                    ret['comment'] = 'Failed to remove pipeline {0} for unknown reasons'.format(name)
        else:
            ret['comment'] = 'Pipeline {0} is already absent'.format(name)
    except Exception as err:
        ret['result'] = False
        ret['comment'] = six.text_type(err)

    return ret


def pipeline_present(name, definition):
    '''
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

    try:
        pipeline = __salt__['elasticsearch.pipeline_get'](id=name)
        old = {}
        if pipeline and name in pipeline:
            old = pipeline[name]
        ret['changes'] = __utils__['dictdiffer.deep_diff'](old, definition)

        if ret['changes'] or not definition:
            if __opts__['test']:
                if not pipeline:
                    ret['comment'] = 'Pipeline {0} does not exist and will be created'.format(name)
                else:
                    ret['comment'] = 'Pipeline {0} exists with wrong configuration and will be overriden'.format(name)

                ret['result'] = None
            else:
                output = __salt__['elasticsearch.pipeline_create'](id=name, body=definition)
                if output:
                    if not pipeline:
                        ret['comment'] = 'Successfully created pipeline {0}'.format(name)
                    else:
                        ret['comment'] = 'Successfully replaced pipeline {0}'.format(name)
                else:
                    ret['result'] = False
                    ret['comment'] = 'Cannot create pipeline {0}, {1}'.format(name, output)
        else:
            ret['comment'] = 'Pipeline {0} is already present'.format(name)
    except Exception as err:
        ret['result'] = False
        ret['comment'] = six.text_type(err)

    return ret


def search_template_absent(name):
    '''
    Ensure that the search template is absent

    name
        Name of the search template to remove
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    try:
        template = __salt__['elasticsearch.search_template_get'](id=name)
        if template:
            if __opts__['test']:
                ret['comment'] = 'Search template {0} will be removed'.format(name)
                ret['changes']['old'] = salt.utils.json.loads(template["template"])
                ret['result'] = None
            else:
                ret['result'] = __salt__['elasticsearch.search_template_delete'](id=name)
                if ret['result']:
                    ret['comment'] = 'Successfully removed search template {0}'.format(name)
                    ret['changes']['old'] = salt.utils.json.loads(template["template"])
                else:
                    ret['comment'] = 'Failed to remove search template {0} for unknown reasons'.format(name)
        else:
            ret['comment'] = 'Search template {0} is already absent'.format(name)
    except Exception as err:
        ret['result'] = False
        ret['comment'] = six.text_type(err)

    return ret


def search_template_present(name, definition):
    '''
    Ensure that the named search template is present.

    name
        Name of the search template to add
    definition
        Required dict for creation parameters as per http://www.elastic.co/guide/en/elasticsearch/reference/current/search-template.html

    **Example:**

    .. code-block:: yaml

        test_pipeline:
          elasticsearch.search_template_present:
            - definition:
                inline:
                  size: 10
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    try:
        template = __salt__['elasticsearch.search_template_get'](id=name)

        old = {}
        if template:
            old = salt.utils.json.loads(template["template"])

        ret['changes'] = __utils__['dictdiffer.deep_diff'](old, definition)

        if ret['changes'] or not definition:
            if __opts__['test']:
                if not template:
                    ret['comment'] = 'Search template {0} does not exist and will be created'.format(name)
                else:
                    ret['comment'] = 'Search template {0} exists with wrong configuration and will be overriden'.format(name)

                ret['result'] = None
            else:
                output = __salt__['elasticsearch.search_template_create'](id=name, body=definition)
                if output:
                    if not template:
                        ret['comment'] = 'Successfully created search template {0}'.format(name)
                    else:
                        ret['comment'] = 'Successfully replaced search template {0}'.format(name)
                else:
                    ret['result'] = False
                    ret['comment'] = 'Cannot create search template {0}, {1}'.format(name, output)
        else:
            ret['comment'] = 'Search template {0} is already present'.format(name)
    except Exception as err:
        ret['result'] = False
        ret['comment'] = six.text_type(err)

    return ret
