# -*- coding: utf-8 -*-
'''
Manage Apigateway Rest APIs
=================

.. versionadded::

Create and destroy rest apis depending on a swagger version 2 definition file.
Be aware that this interacts with Amazon's services, and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit vpc credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    vpc.keyid: GKTADJGHEIQSXMKKRBJ08H
    vpc.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure Apigateway API exists:
        boto_apigateway.present:
            - name: myfunction
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

'''

# Import Python Libs
from __future__ import absolute_import
import logging
import os
import os.path
import hashlib
import re
import json


# Import Salt Libs
import salt.utils.dictupdate as dictupdate

# Import 3rd Party Libs
import anyconfig


log = logging.getLogger(__name__)

# Helper Swagger Class for swagger version 2.0 API specification
def _gen_md5_filehash(fname):
    '''
    helper function to generate a md5 hash of the swagger definition file
    '''
    _hash = hashlib.md5()
    with open(fname, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            _hash.update(chunk)
    return _hash.hexdigest()

def _dict_to_json_pretty(d, sort_keys=True):
    '''
    helper function to generate pretty printed json output
    '''
    return json.dumps(d, indent=4, separators=(',', ': '), sort_keys=sort_keys)

class Swagger(object):
    # SWAGGER_OBJECT_V2_FIELDS
    SWAGGER_OBJECT_V2_FIELDS = ('swagger', 'info', 'host', 'basePath', 'schemes', 'consumes', 'produces',
                                'paths', 'definitions', 'parameters', 'responses', 'securityDefinitions',
                                'security', 'tags', 'externalDocs')
    # SWAGGER OBJECT V2 Fields that are required by boto apigateway states.
    SWAGGER_OBJECT_V2_FIELDS_REQUIRED = ('swagger', 'info', 'basePath', 'schemes', 'paths', 'definitions')
    # SWAGGER OPERATION NAMES
    SWAGGER_OPERATION_NAMES = ('get', 'put', 'post', 'delete', 'options', 'head', 'patch')
    SWAGGER_VERSIONS_SUPPORTED = ('2.0',)

    # VENDOR SPECIFIC FIELD PATTERNS
    VENDOR_EXT_PATTERN = re.compile('^x-')

    # JSON_SCHEMA_REF
    JSON_SCHEMA_DRAFT_4 = 'http://json-schema.org/draft-04/schema#'

    class SwaggerParameter(object):
        '''
        This is a helper class for the Swagger Parameter Object
        '''
        LOCATIONS = ('body', 'query', 'header')

        def __init__(self, paramdict):
            self._paramdict = paramdict

        @property
        def location(self):
            _location = self._paramdict.get('in')
            if _location in Swagger.SwaggerParameter.LOCATIONS:
                return _location
            raise ValueError('Unsupported parameter location: {0} in Parameter Object'.format(_location))

        @property
        def name(self):
            _name = self._paramdict.get('name')
            if _name:
                if self.location == 'header':
                    return 'method.request.header.{0}'.format(_name)
                elif self.location == 'query':
                    return 'method.request.querystring.{0}'.format(_name)
                return None
            raise ValueError('Parameter must have a name: {0}'.format(_dict_to_json_pretty(self._paramdict)))

        @property
        def schema(self):
            if self.location == 'body':
                _schema = self._paramdict.get('schema')
                if _schema:
                    if '$ref' in _schema:
                        schema_name = _schema.get('$ref').split('/')[-1]
                        return schema_name
                    raise ValueError(('Body parameter must have a JSON reference '
                                      'to the schema definition: {0}'.format(self.name)))
                raise ValueError('Body parameter must have a schema: {0}'.format(self.name))
            return None

    class SwaggerMethodResponse(object):
        '''
        Helper class for Swagger Method Response Object
        '''
        def __init__(self, r):
            self._r = r

        @property
        def schema(self):
            _schema = self._r.get('schema')
            if _schema:
                if '$ref' in _schema:
                    return _schema.get('$ref').split('/')[-1]
                raise ValueError(('Method response must have a JSON reference '
                                  'to the schema definition: {0}'.format(_schema)))
            return None
            # raise ValueError('Method response must have a schema: {0}'.format(self))

        @property
        def headers(self):
            _headers = self._r.get('headers', {})
            return _headers

    def __init__(self, swagger_file_path):
        if os.path.exists(swagger_file_path) and os.path.isfile(swagger_file_path):
            self._swagger_file = swagger_file_path
            self._md5_filehash = _gen_md5_filehash(self._swagger_file)
            self._cfg = anyconfig.load(self._swagger_file)
            self._swagger_version = ''
            # values from AWS APIGateway
            self._restApiId = ''
        else:
            raise IOError('Invalid swagger file path, {0}'.format(swagger_file_path))

        self._validate_swagger_file()

    def _validate_swagger_file(self):
        '''
        High level check/validation of the input swagger file based on
        https://github.com/swagger-api/swagger-spec/blob/master/versions/2.0.md

        This is not a full schema compliance check, but rather make sure that the input file (YAML or
        JSON) can be read into a dictionary, and we check for the content of the Swagger Object for version
        and info.
        '''
        swagger_fields = self._cfg.keys()

        # check for any invalid fields for Swagger Object V2
        for field in swagger_fields:
            if (field not in Swagger.SWAGGER_OBJECT_V2_FIELDS and
                not Swagger.VENDOR_EXT_PATTERN.match(field)):
                raise ValueError('Invalid Swagger Object Field: {0}'.format(field))

        # check for Required Swagger fields by Saltstack boto apigateway state
        for field in Swagger.SWAGGER_OBJECT_V2_FIELDS_REQUIRED:
            if field not in swagger_fields:
                raise ValueError('Missing Swagger Object Field: {0}'.format(field))

        # check for Swagger Version
        self._swagger_version = self._cfg.get('swagger')
        if self._swagger_version not in Swagger.SWAGGER_VERSIONS_SUPPORTED:
            raise ValueError('Unsupported Swagger version: {0},'
                             'Supported versions are {1}'.format(self._swagger_version,
                                                                 Swagger.SWAGGER_VERSIONS_SUPPORTED))


    @property
    def md5_filehash(self):
        return self._md5_filehash

    @property
    def info(self):
        info = self._cfg.get('info')
        if not info:
            raise ValueError('Info Object has no values')
        return info

    @property
    def info_json(self):
        return _dict_to_json_pretty(self.info)

    @property
    def rest_api_name(self):
        api_name = self.info.get('title')
        if not api_name:
            raise ValueError('Missing title value in Info Object, which is used as rest api name')

        return api_name

    @property
    def rest_api_version(self):
        version = self.info.get('version')
        if not version:
            raise ValueError('Missing version value in Info Object')

        return version

    @property
    def models(self):
        models = self._cfg.get('definitions')
        if not models:
            raise ValueError('Definitions Object has no values, You need to define them in your swagger file')
        return models.iteritems()

    @property
    def paths(self):
        paths = self._cfg.get('paths')
        if not paths:
            raise ValueError('Paths Object has no values, You need to define them in your swagger file')
        for path in paths.keys():
            if not path.startswith('/'):
                raise ValueError('Path object {0} should start with /. Please fix it'.format(path))
        return paths.iteritems()

    @property
    def basePath(self):
        basePath = self._cfg.get('basePath', '')
        return basePath

    @property
    def restApiId(self):
        return self._restApiId

    @restApiId.setter
    def restApiId(self, restApiId):
        self._restApiId = restApiId

    # methods to interact with boto_apigateway execution modules

    def deploy_api(self, ret, region=None, key=None, keyid=None, profile=None):
        '''
        this method create the top level rest api in AWS apigateway
        '''
        # TODO: check to see if the service by this name and description exists,
        # matches the content of swagger.info_json, may need more elaborate checks
        # on the content of the json in description field of AWS ApiGateway Rest API Object.
        exists_response = __salt__['boto_apigateway.api_exists'](name=self.rest_api_name, description=self.info_json,
                                                                 region=region, key=key, keyid=keyid, profile=profile)
        if exists_response.get('exists'):
            ret['comment'] = 'rest api already exists'
            ret['abort'] = True
            return ret

        if __opts__['test']:
            ret['comment'] = 'Swagger API Spec {0} is set to be created.'.format(self.rest_api_name)
            ret['result'] = None
            ret['abort'] = True
            return ret

        response = __salt__['boto_apigateway.create_api'](name=self.rest_api_name, description=self.info_json,
                                                          region=region, key=key, keyid=keyid, profile=profile)

        if not response.get('created'):
            ret['result'] = False
            ret['abort'] = True
            if 'error' in response:
                ret['comment'] = 'Failed to create rest api: {0}.'.format(response['error']['message'])
            return ret

        self.restApiId = response.get('restapi', {}).get('id')

        return _log_changes(ret, 'deploy_api', response.get('restapi'))

    def delete_api(self, ret, region=None, key=None, keyid=None, profile=None):
        '''
        Method to delete a Rest Api named defined in the swagger file's Info Object's title value.
        '''
        exists_response = __salt__['boto_apigateway.api_exists'](name=self.rest_api_name, description=self.info_json,
                                                                 region=region, key=key, keyid=keyid, profile=profile)
        if exists_response.get('exists'):
            if __opts__['test']:
                ret['comment'] = 'Rest API named {0} is set to be deleted.'.format(self.rest_api_name)
                ret['result'] = None
                ret['abort'] = True
                return ret

            delete_api_response = __salt__['boto_apigateway.delete_api'](name=self.rest_api_name,
                                                                         description=self.info_json, region=region,
                                                                         key=key, keyid=keyid, profile=profile)
            if not delete_api_response.get('deleted'):
                ret['result'] = False
                ret['abort'] = True
                if 'error' in delete_api_response:
                    ret['comment'] = 'Failed to delete rest api: {0}.'.format(delete_api_response['error']['message'])
                return ret

            ret = _log_changes(ret, 'delete_api', delete_api_response)
        else:
            ret['comment'] = ('api already absent for swagger file: '
                              '{0}, desc: {1}'.format(self.rest_api_name, self.info_json))

        return ret

    def deploy_models(self, ret, region=None, key=None, keyid=None, profile=None):
        '''
        Method to deploy swagger file's definition objects and associated schema to AWS Apigateway as Models
        '''
        for model, schema  in self.models:
            # add in a few attributes into the model schema that AWS expects
            _schema = schema.copy()
            _schema.update({'$schema': Swagger.JSON_SCHEMA_DRAFT_4,
                            'title': '{0} Schema'.format(model),
                            'type': 'object'})

            # check to see if model already exists, aws has 2 default models [Empty, Error]
            # which may need upate with data from swagger file
            model_exists_response = (
                __salt__['boto_apigateway.api_model_exists'](restApiId=self.restApiId, modelName=model,
                                                             region=region, key=key, keyid=keyid, profile=profile))

            if model_exists_response.get('exists'):
                # TODO: still needs to also update model description (if there is a field we will
                # populate it with from swagger file)
                update_model_schema_response = (
                    __salt__['boto_apigateway.update_api_model_schema'](restApiId=self.restApiId, modelName=model,
                                                                        schema=_schema, region=region, key=key,
                                                                        keyid=keyid, profile=profile))
                if not update_model_schema_response.get('updated'):
                    ret['result'] = False
                    ret['abort'] = True
                    if 'error' in update_model_schema_response:
                        ret['comment'] = 'Failed to update existing model {0} with schema {1}, error: {2}'.format(model,
                            _dict_to_json_pretty(schema), update_model_schema_response['error']['message'])
                    return ret

                ret = _log_changes(ret, 'deploy_models', update_model_schema_response)
            else:
                # call into boto_apigateway to create models
                # TODO: model may have descriptions field, need to extract and pass into modelDescription
                # as opposed to the hardcoded 'test123'.
                create_model_response = __salt__['boto_apigateway.create_api_model'](restApiId=self.restApiId,
                    modelName=model, modelDescription='test123', schema=_schema,
                    contentType='application/json', region=region, key=key, keyid=keyid, profile=profile)

                if not create_model_response.get('created'):
                    ret['result'] = False
                    ret['abort'] = True
                    if 'error' in create_model_response:
                        ret['comment'] = 'Failed to create model {0}, schema {1}, error: {2}'.format(model,
                                    _dict_to_json_pretty(schema), create_model_response['error']['message'])
                    return ret

                ret = _log_changes(ret, 'deploy_models', create_model_response)

        return ret

    def _lambda_name(self, resourcePath, httpMethod):
        lambda_name = '{0}{1}_{2}'.format(self.rest_api_name.strip(), resourcePath, httpMethod)
        return re.sub(r'\s+|/', '_', lambda_name).lower()

    def _lambda_uri(self, ret, lambda_name, region=None, key=None, keyid=None, profile=None):
        '''
        Helper Method to construct the lambda uri for use in method integration
        '''
        # TODO: better means of determining lambda region and apigateway_region
        # they can't be in different regions?
        lambda_region = __salt__['pillar.get']('lambda.region')
        if not lambda_region:
            raise ValueError('Region for lambda function {0} has not been specified'.format(lambda_name))
        lambda_desc = __salt__['boto_lambda.describe_function'](lambda_name, region=lambda_region,
                                                                key=key, keyid=keyid, profile=profile)
        if not lambda_desc.get('function'):
            raise ValueError('Could not find lambda function {0}'.format(lambda_name))

        lambda_arn = lambda_desc.get('function').get('FunctionArn')
        apigateway_region = __salt__['pillar.get']('apigateway.region')
        lambda_uri = ('arn:aws:apigateway:{0}:lambda:path/2015-03-31'
                      '/functions/{1}/invocations'.format(apigateway_region, lambda_arn))
        log.info(lambda_uri)
        return lambda_uri

    def deploy_resources(self, ret, region=None, key=None, keyid=None, profile=None):
        for path, pathData in self.paths:
            resource_path = ''.join((self.basePath, path))
            resource = __salt__['boto_apigateway.create_api_resources'](restApiId=self.restApiId,
                path=resource_path, region=region, key=key, keyid=keyid, profile=profile)
            if not resource.get('created'):
                ret = _log_error_and_abort(ret, resource)
                return ret
            ret = _log_changes(ret, 'deploy_resources', resource)
            for method, methodData in pathData.iteritems():
                if method in self.SWAGGER_OPERATION_NAMES:
                    method_params = {}
                    method_models = {}
                    log.info(methodData)
                    if 'parameters' in methodData:
                        for param in methodData['parameters']:
                            p = Swagger.SwaggerParameter(param)
                            if p.name:
                                method_params[p.name] = True
                            if p.schema:
                                method_models['application/json'] = p.schema

                    log.info(method_params)
                    log.info(method_models)

                    # TODO: 'NONE' ??
                    m = __salt__['boto_apigateway.create_api_method'](self.restApiId, resource_path,
                        method.upper(), 'NONE', requestParameters=method_params, requestModels=method_models,
                        region=region, key=key, keyid=keyid, profile=profile)
                    if not m.get('created'):
                        ret = _log_error_and_abort(ret, m)
                        return ret

                    requestTemplates = {}
                    if method_params or method_models:
                        # TODO: move this to a constant for the class.
                        requestTemplates = {'application/json':
                                       """#set($inputRoot = $input.path('$'))
                                       {
                                       \"header-params\" : {
                                       #set ($map = $input.params().header)
                                       #foreach( $param in $map.entrySet() )
                                       \"$param.key\" : \"$param.value\" #if( $foreach.hasNext ), #end
                                       #end
                                       },
                                       \"query-params\" : {
                                       #set ($map = $input.params().querystring)
                                       #foreach( $param in $map.entrySet() )
                                       \"$param.key\" : \"$param.value\" #if( $foreach.hasNext ), #end
                                       #end
                                       },
                                       \"body-params\" : $input.json('$')
                                       }"""}

                    lambda_uri = self._lambda_uri(ret, self._lambda_name(resource_path, method),
                                                  region=region, key=key, keyid=keyid, profile=profile)

                    # TODO: fix this by passing in the ROLE name into the presence function, and
                    # we will get this dynamically through boto_iam instead of through the pillar.
                    agw_policy_arn = __salt__['pillar.get']('apigateway.policyarn')
                    if not agw_policy_arn:
                        raise ValueError('pillar for apigateway.policyarn not populated')

                    integration = __salt__['boto_apigateway.create_api_integration'](
                            self.restApiId, resource_path, method.upper(), 'AWS', method.upper(),
                            lambda_uri, agw_policy_arn, requestTemplates=requestTemplates,
                            region=region, key=key, keyid=keyid, profile=profile)
                    log.info(integration)
                    if not integration.get('created'):
                        ret = _log_error_and_abort(ret, integration)
                        return ret

                    if 'responses' in methodData:
                        for response, responseData in methodData['responses'].iteritems():
                            httpStatus = str(response)
                            methodResponse = Swagger.SwaggerMethodResponse(responseData)

                            method_response_models = {}
                            if methodResponse.schema:
                                method_response_models['application/json'] = methodResponse.schema

                            method_response_params = {}
                            method_integration_response_params = {}
                            for header in methodResponse.headers:
                                method_response_params['method.response.header.{0}'.format(header)] = False
                                method_integration_response_params['method.response.header.{0}'.format(header)] = "'*'"

                            mr = __salt__['boto_apigateway.create_api_method_response'](
                                    self.restApiId, resource_path, method.upper(), httpStatus,
                                    responseParameters=method_response_params, responseModels=method_response_models,
                                    region=region, key=key, keyid=keyid, profile=profile)
                            if not mr.get('created'):
                                ret = _log_error_and_abort(ret, mr)
                                return ret

                            mir = __salt__['boto_apigateway.create_api_integration_response'](
                                    self.restApiId, resource_path, method.upper(), httpStatus, '.*',
                                    responseParameters=method_integration_response_params,
                                    region=region, key=key, keyid=keyid, profile=profile)
                            if not mir.get('created'):
                                ret = _log_error_and_abort(ret, mir)
                                return ret
                    else:
                        raise ValueError('No responses specified for {0} {1}'.format(path, method))

                    ret = _log_changes(ret, 'deploy_resources - methods', m)
        return ret


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_apigateway' if 'boto_apigateway.get_apis' in __salt__ else False


def _log_changes(ret, changekey, changevalue):
    '''
    For logging create/update/delete operations to AWS ApiGateway
    '''
    cl = ret['changes'].get('new', [])
    cl.append({changekey: changevalue})
    ret['changes']['new'] = cl
    return ret

def _log_error_and_abort(ret, obj):
    '''
    helper function to update errors in the return structure
    '''
    ret['result'] = False
    ret['abort'] = True
    if 'error' in obj:
        ret['comment'] = obj.get('error')
    return ret

def present(name,
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the swagger_yaml_file specified is defined in AWS Api Gateway.

    name
        Name of the location of the swagger rest api definition file in YAML format.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    try:
        # try to open the swagger file and basic validation
        swagger = Swagger(name)

        # first deploy a Rest Api on AWS
        ret = swagger.deploy_api(ret, region=region, key=key, keyid=keyid, profile=profile)
        if ret.get('abort'):
            return ret

        # next, deploy models of to the AWS API
        ret = swagger.deploy_models(ret, region=region, key=key, keyid=keyid, profile=profile)
        if ret.get('abort'):
            return ret

        ret = swagger.deploy_resources(ret, region=region, key=key, keyid=keyid, profile=profile)
        if ret.get('abort'):
            return ret

    except Exception as e:
        ret['result'] = False
        ret['comment'] = e.message

    return ret

#
#def _get_role_arn(name, region=None, key=None, keyid=None, profile=None):
#    if name.startswith('arn:aws:iam:'):
#        return name
#
#    account_id = __salt__['boto_iam.get_account_id'](
#        region=region, key=key, keyid=keyid, profile=profile
#    )
#    return 'arn:aws:iam::{0}:role/{1}'.format(account_id, name)
#


def absent(name, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure Lamda function with passed properties is absent.

    name
        Name of the swagger file in YAML format

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''

    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    try:
        swagger = Swagger(name)

        ret = swagger.delete_api(ret, region=region, key=key, keyid=keyid, profile=profile)

    except Exception as e:
        ret['result'] = False
        ret['comment'] = e.message

    return ret
