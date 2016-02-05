# -*- coding: utf-8 -*-
'''
Connection module for Amazon Data Pipeline

.. versionadded:: 2016.3.0

:depends: boto3
'''
from __future__ import absolute_import

import logging

from salt._compat import string_types

log = logging.getLogger(__name__)

try:
    import boto3
    import botocore.exceptions
    boto3.set_stream_logger(level=logging.CRITICAL)
    logging.getLogger('botocore').setLevel(logging.CRITICAL)
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def __virtual__():
    '''
    Only load if boto3 libraries exists.
    '''
    if not HAS_BOTO3:
        return False
    return True


def activate_pipeline(pipeline_id, region=None, key=None, keyid=None, profile=None):
    '''
    Start processing pipeline tasks. This function is idempotent.

    CLI example::

        salt myminion boto_datapipeline.activate_pipeline my_pipeline_id
    '''
    client = _get_client(region, key, keyid, profile)
    r = {}
    try:
        client.activate_pipeline(pipelineId=pipeline_id)
        r['result'] = True
    except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        r['error'] = str(e)
    return r


def create_pipeline(name, unique_id, description='', region=None, key=None, keyid=None,
                    profile=None):
    '''
    Create a new, empty pipeline. This function is idempotent.

    CLI example::

        salt myminion boto_datapipeline.create_pipeline my_name my_unique_id
    '''
    client = _get_client(region, key, keyid, profile)
    r = {}
    try:
        response = client.create_pipeline(
            name=name,
            uniqueId=unique_id,
            description=description,
        )
        r['result'] = response['pipelineId']
    except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        r['error'] = str(e)
    return r


def delete_pipeline(pipeline_id, region=None, key=None, keyid=None, profile=None):
    '''
    Delete a pipeline, its pipeline definition, and its run history. This function is idempotent.

    CLI example::

        salt myminion boto_datapipeline.delete_pipeline my_pipeline_id
    '''
    client = _get_client(region, key, keyid, profile)
    r = {}
    try:
        client.delete_pipeline(pipelineId=pipeline_id)
        r['result'] = True
    except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        r['error'] = str(e)
    return r


def describe_pipelines(pipeline_ids, region=None, key=None, keyid=None, profile=None):
    '''
    Retrieve metadata about one or more pipelines.

    CLI example::

        salt myminion boto_datapipeline.describe_pipelines ['my_pipeline_id']
    '''
    client = _get_client(region, key, keyid, profile)
    r = {}
    try:
        r['result'] = client.describe_pipelines(pipelineIds=pipeline_ids)
    except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        r['error'] = str(e)
    return r


def get_pipeline_definition(pipeline_id, version='latest', region=None, key=None, keyid=None,
                            profile=None):
    '''
    Get the definition of the specified pipeline.

    CLI example::

        salt myminion boto_datapipeline.get_pipeline_definition my_pipeline_id
    '''
    client = _get_client(region, key, keyid, profile)
    r = {}
    try:
        r['result'] = client.get_pipeline_definition(
            pipelineId=pipeline_id,
            version=version,
        )
    except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        r['error'] = str(e)
    return r


def list_pipelines(region=None, key=None, keyid=None, profile=None):
    '''
    Get a list of pipeline ids and names for all pipelines.
    '''
    client = _get_client(region, key, keyid, profile)
    r = {}
    try:
        paginator = client.get_paginator('list_pipelines')
        pipelines = []
        for page in paginator.paginate():
            pipelines += page['pipelineIdList']
        r['result'] = pipelines
    except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        r['error'] = str(e)
    return r


def pipeline_id_from_name(name, region=None, key=None, keyid=None, profile=None):
    '''
    Get the pipeline id, if it exists, for the given name.

    CLI example::

        salt myminion boto_datapipeline.pipeline_id_from_name my_pipeline_name
    '''
    r = {}
    result_pipelines = list_pipelines()
    if 'error' in result_pipelines:
        return result_pipelines

    for pipeline in result_pipelines['result']:
        if pipeline['name'] == name:
            r['result'] = pipeline['id']
            return r
    r['error'] = 'No pipeline found with name={0}'.format(name)
    return r


def put_pipeline_definition(pipeline_id, pipeline_objects, parameter_objects=None,
                            parameter_values=None, region=None, key=None, keyid=None, profile=None):
    '''
    Add tasks, schedules, and preconditions to the specified pipeline. This function is
    idempotent and will replace an existing definition.

    CLI example::

        salt myminion boto_datapipeline.put_pipeline_definition my_pipeline_id my_pipeline_objects
    '''
    parameter_objects = parameter_objects or []
    parameter_values = parameter_values or []
    client = _get_client(region, key, keyid, profile)
    r = {}
    try:
        response = client.put_pipeline_definition(
            pipelineId=pipeline_id,
            pipelineObjects=pipeline_objects,
            parameterObjects=parameter_objects,
            parameterValues=parameter_values,
        )
        if response['errored']:
            r['error'] = response['validationErrors']
        else:
            r['result'] = response
    except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        r['error'] = str(e)
    return r


def _get_client(region, key, keyid, profile):
    '''
    Get a boto connection to Data Pipeline.
    '''
    session = _get_session(region, key, keyid, profile)
    if not session:
        log.error("Failed to get datapipeline client.")
        return None

    return session.client('datapipeline')


def _get_session(region, key, keyid, profile):
    '''
    Get a boto3 session
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('datapipeline.region'):
        region = __salt__['config.option']('datapipeline.region')

    if not region:
        region = 'us-east-1'

    return boto3.session.Session(
        region_name=region,
        aws_secret_access_key=key,
        aws_access_key_id=keyid,
    )
