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
import yaml


# Import Salt Libs
import salt.utils.dictupdate as dictupdate
import salt.utils

# Import 3rd Party Libs

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_apigateway' if 'boto_apigateway.describe_apis' in __salt__ else False


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

def api_present(name, api_name, swagger_file, api_key_required, lambda_integration_role,
                lambda_region=None, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the spcified api_name with the corresponding swaggerfile is defined in
    AWS ApiGateway.

    This state will take the swagger definition, and perform the necessary actions
    to define a matching rest api in AWS ApiGateway and intgrate the method request
    handling to AWS Lambda functions.

    Please note that the name of the lambda function to be integrated will be derived
    via the following and lowercased:
        api_name parameter as passed in to this state function with consecutive white
        spaces replaced with '_'  +

        resource_path as derived from the swagger file basePath and paths fields with
        '/' replaced with '_' +

        resource's method type

        for example, given the following:
            api_name = 'Test  Api'
            basePath = '/api'
            path = '/a/b/c'
            method = 'POST'

            the derived Lambda Function Name that will be used for look up and
            integration is:

            'test_api_api_a_b_c_post'

    name
        The name of the state definition

    api_name
        The name of the rest api that we want to ensure exists in AWS API Gateway

    swagger_file
        Name of the location of the swagger rest api definition file in YAML format.

    api_key_required
        True or False - whether the API Key is required to call API methods

    lambda_integration_role
        The name or ARN of the IAM role that the AWS ApiGateway assumes when it
        executes your lambda function to handle incoming requests

    lambda_region
        The region where we expect to find the lambda functions.  This is used to
        determine the region where we should look for the Lambda Function for
        integration purposes.  The region determination is based on the following
        priority:

        1) lambda_region as passed in (is not None)
        2) if lambda_region is None, use the region as if a boto_lambda function were
        executed without explicitly specifying lambda region.
        3) if region determined in (2) is different than the region used by
        boto_apigateway functions, a final lookup will be attempted using the
        boto_apigateway region.

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
        common_args = dict([('region', region),
                            ('key', key),
                            ('keyid', keyid),
                            ('profile', profile)])

        # try to open the swagger file and basic validation
        swagger = _Swagger(api_name, swagger_file, common_args)

        # first deploy a Rest Api on AWS
        ret = swagger.deploy_api(ret)
        if ret.get('abort'):
            return ret

        # next, deploy models of to the AWS API
        ret = swagger.deploy_models(ret)
        if ret.get('abort'):
            return ret

        ret = swagger.deploy_resources(ret,
                                       api_key_required=api_key_required,
                                       lambda_integration_role=lambda_integration_role,
                                       lambda_region=lambda_region)
        if ret.get('abort'):
            return ret

    except Exception as e:
        ret['result'] = False
        ret['comment'] = e.message

    return ret


def api_absent(name, api_name, swagger_file, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure AWS Apigateway Rest Api identified by a combination of the api_name and
    the info object specified in the swagger_file is absent.

    name
        Name of the swagger file in YAML format

    api_name
        Name of the rest api on AWS ApiGateway to ensure is absent.

    swagger_file
        Name of the location of the swagger rest api definition file in YAML format.
        The info object in the file is used in conjunction with the api_name to
        uniquely identify a rest api to ensure absent.

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
        common_args = dict([('region', region),
                            ('key', key),
                            ('keyid', keyid),
                            ('profile', profile)])

        swagger = _Swagger(api_name, swagger_file, common_args)

        ret = swagger.delete_api(ret)

    except Exception as e:
        ret['result'] = False
        ret['comment'] = e.message

    return ret


# Helper Swagger Class for swagger version 2.0 API specification
def _gen_md5_filehash(fname):
    '''
    helper function to generate a md5 hash of the swagger definition file
    '''
    _hash = hashlib.md5()
    with salt.utils.fopen(fname, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            _hash.update(chunk)
    return _hash.hexdigest()

def _dict_to_json_pretty(d, sort_keys=True):
    '''
    helper function to generate pretty printed json output
    '''
    return json.dumps(d, indent=4, separators=(',', ': '), sort_keys=sort_keys)

class _Swagger(object):
    '''
    this is a helper class that holds the swagger definition file and the associated logic
    related to how to interpret the file and apply it to AWS Api Gateway.

    The main interface to the outside world is in deploy_api, deploy_models, and deploy_resources
    methods.
    '''

    SWAGGER_OBJ_V2_FIELDS = ('swagger', 'info', 'host', 'basePath', 'schemes', 'consumes', 'produces',
                                'paths', 'definitions', 'parameters', 'responses', 'securityDefinitions',
                                'security', 'tags', 'externalDocs')
    # SWAGGER OBJECT V2 Fields that are required by boto apigateway states.
    SWAGGER_OBJ_V2_FIELDS_REQUIRED = ('swagger', 'info', 'basePath', 'schemes', 'paths', 'definitions')
    # SWAGGER OPERATION NAMES
    SWAGGER_OPERATION_NAMES = ('get', 'put', 'post', 'delete', 'options', 'head', 'patch')
    SWAGGER_VERSIONS_SUPPORTED = ('2.0',)

    # VENDOR SPECIFIC FIELD PATTERNS
    VENDOR_EXT_PATTERN = re.compile('^x-')

    # JSON_SCHEMA_REF
    JSON_SCHEMA_DRAFT_4 = 'http://json-schema.org/draft-04/schema#'

    # AWS integration templates for normal and options methods
    REQUEST_TEMPLATE = {'application/json':
                            '#set($inputRoot = $input.path(\'$\'))'
                            '{'
                            '"header-params" : {'
                            '#set ($map = $input.params().header)'
                            '#foreach( $param in $map.entrySet() )'
                            '"$param.key" : "$param.value" #if( $foreach.hasNext ), #end'
                            '#end'
                            '},'
                            '"query-params" : {'
                            '#set ($map = $input.params().querystring)'
                            '#foreach( $param in $map.entrySet() )'
                            '"$param.key" : "$param.value" #if( $foreach.hasNext ), #end'
                            '#end'
                            '},'
                            '"body-params" : $input.json(\'$\')'
                            '}'}
    REQUEST_OPTION_TEMPLATE = {'application/json': '{"statusCode": 200}'}

    class SwaggerParameter(object):
        '''
        This is a helper class for the Swagger Parameter Object
        '''
        LOCATIONS = ('body', 'query', 'header')

        def __init__(self, paramdict):
            self._paramdict = paramdict

        @property
        def location(self):
            '''
            returns location in the swagger parameter object
            '''
            _location = self._paramdict.get('in')
            if _location in _Swagger.SwaggerParameter.LOCATIONS:
                return _location
            raise ValueError('Unsupported parameter location: {0} in Parameter Object'.format(_location))

        @property
        def name(self):
            '''
            returns parameter name in the swagger parameter object
            '''
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
            '''
            returns the name of the schema given the reference in the swagger parameter object
            '''
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
            '''
            returns the name of the schema given the reference in the swagger method response object
            '''
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
            '''
            returns the headers dictionary in the method response object
            '''
            _headers = self._r.get('headers', {})
            return _headers

    def __init__(self, api_name, swagger_file_path, common_aws_args):
        self._api_name = api_name
        self._common_aws_args = common_aws_args
        self._restApiId = ''

        if os.path.exists(swagger_file_path) and os.path.isfile(swagger_file_path):
            self._swagger_file = swagger_file_path
            self._md5_filehash = _gen_md5_filehash(self._swagger_file)
            with salt.utils.fopen(self._swagger_file, 'rb') as sf:
                self._cfg = yaml.load(sf)
            self._swagger_version = ''
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

        # check for any invalid fields for Swagger Object V2
        for field in self._cfg:
            if (field not in _Swagger.SWAGGER_OBJ_V2_FIELDS and
                not _Swagger.VENDOR_EXT_PATTERN.match(field)):
                raise ValueError('Invalid Swagger Object Field: {0}'.format(field))

        # check for Required Swagger fields by Saltstack boto apigateway state
        for field in _Swagger.SWAGGER_OBJ_V2_FIELDS_REQUIRED:
            if field not in self._cfg:
                raise ValueError('Missing Swagger Object Field: {0}'.format(field))

        # check for Swagger Version
        self._swagger_version = self._cfg.get('swagger')
        if self._swagger_version not in _Swagger.SWAGGER_VERSIONS_SUPPORTED:
            raise ValueError('Unsupported Swagger version: {0},'
                             'Supported versions are {1}'.format(self._swagger_version,
                                                                 _Swagger.SWAGGER_VERSIONS_SUPPORTED))


    @property
    def md5_filehash(self):
        '''
        returns md5 hash for the swagger file
        '''
        return self._md5_filehash

    @property
    def info(self):
        '''
        returns the swagger info object as a dictionary
        '''
        info = self._cfg.get('info')
        if not info:
            raise ValueError('Info Object has no values')
        return info

    @property
    def info_json(self):
        '''
        returns the swagger info object as a pretty printed json string.
        '''
        return _dict_to_json_pretty(self.info)

    @property
    def rest_api_name(self):
        '''
        returns the name of the api
        '''
        return self._api_name

    @property
    def rest_api_version(self):
        '''
        returns the version field in the swagger info object
        '''
        version = self.info.get('version')
        if not version:
            raise ValueError('Missing version value in Info Object')

        return version

    @property
    def models(self):
        '''
        returns an iterator for the models specified in the swagger file
        '''
        models = self._cfg.get('definitions')
        if not models:
            raise ValueError('Definitions Object has no values, You need to define them in your swagger file')
        return models.iteritems()

    @property
    def paths(self):
        '''
        returns an iterator for the relative resource paths specified in the swagger file
        '''
        paths = self._cfg.get('paths')
        if not paths:
            raise ValueError('Paths Object has no values, You need to define them in your swagger file')
        for path in paths:
            if not path.startswith('/'):
                raise ValueError('Path object {0} should start with /. Please fix it'.format(path))
        return paths.iteritems()

    @property
    def basePath(self):
        '''
        returns the base path field as defined in the swagger file
        '''
        basePath = self._cfg.get('basePath', '')
        return basePath

    @property
    def restApiId(self):
        '''
        returns the rest api id as returned by AWS on creation of the rest api
        '''
        return self._restApiId

    @restApiId.setter
    def restApiId(self, restApiId):
        '''
        allows the assignment of the rest api id on creation of the rest api
        '''
        self._restApiId = restApiId

    # methods to interact with boto_apigateway execution modules

    def deploy_api(self, ret):
        '''
        this method create the top level rest api in AWS apigateway
        '''
        # TODO: check to see if the service by this name and description exists,
        # matches the content of swagger.info_json, may need more elaborate checks
        # on the content of the json in description field of AWS ApiGateway Rest API Object.
        exists_response = __salt__['boto_apigateway.api_exists'](name=self.rest_api_name,
                                                                 description=self.info_json,
                                                                 **self._common_aws_args)
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
                                                          **self._common_aws_args)

        if not response.get('created'):
            ret['result'] = False
            ret['abort'] = True
            if 'error' in response:
                ret['comment'] = 'Failed to create rest api: {0}.'.format(response['error']['message'])
            return ret

        self.restApiId = response.get('restapi', {}).get('id')

        return _log_changes(ret, 'deploy_api', response.get('restapi'))

    def delete_api(self, ret):
        '''
        Method to delete a Rest Api named defined in the swagger file's Info Object's title value.

        ret
            a dictionary for returning status to Saltstack
        '''

        exists_response = __salt__['boto_apigateway.api_exists'](name=self.rest_api_name, description=self.info_json,
                                                                 **self._common_aws_args)
        if exists_response.get('exists'):
            if __opts__['test']:
                ret['comment'] = 'Rest API named {0} is set to be deleted.'.format(self.rest_api_name)
                ret['result'] = None
                ret['abort'] = True
                return ret

            delete_api_response = __salt__['boto_apigateway.delete_api'](name=self.rest_api_name,
                                                                         description=self.info_json,
                                                                         **self._common_aws_args)
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

    def deploy_models(self, ret):
        '''
        Method to deploy swagger file's definition objects and associated schema to AWS Apigateway as Models

        ret
            a dictionary for returning status to Saltstack
        '''

        for model, schema  in self.models:
            # add in a few attributes into the model schema that AWS expects
            _schema = schema.copy()
            _schema.update({'$schema': _Swagger.JSON_SCHEMA_DRAFT_4,
                            'title': '{0} Schema'.format(model),
                            'type': 'object'})

            # check to see if model already exists, aws has 2 default models [Empty, Error]
            # which may need upate with data from swagger file
            model_exists_response = __salt__['boto_apigateway.api_model_exists'](restApiId=self.restApiId,
                                                                                 modelName=model,
                                                                                 **self._common_aws_args)

            if model_exists_response.get('exists'):
                # TODO: still needs to also update model description (if there is a field we will
                # populate it with from swagger file)
                update_model_schema_response = (
                    __salt__['boto_apigateway.update_api_model_schema'](restApiId=self.restApiId,
                                                                        modelName=model,
                                                                        schema=_schema,
                                                                        **self._common_aws_args))
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
                create_model_response = (
                    __salt__['boto_apigateway.create_api_model'](restApiId=self.restApiId, modelName=model,
                                                                 modelDescription='test123', schema=_schema,
                                                                 contentType='application/json',
                                                                 **self._common_aws_args))

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
        '''
        Helper method to construct lambda name based on the rule specified in doc string of
        boto_apigateway.api_present function
        '''
        lambda_name = '{0}{1}_{2}'.format(self.rest_api_name.strip(), resourcePath, httpMethod)
        return re.sub(r'\s+|/', '_', lambda_name).lower()

    def _lambda_uri(self, ret, lambda_name, lambda_region):
        '''
        Helper Method to construct the lambda uri for use in method integration
        '''
        profile = self._common_aws_args.get('profile')
        region = self._common_aws_args.get('region')

        lambda_region = __utils__['boto3.get_region']('lambda', lambda_region, profile)
        apigw_region = __utils__['boto3.get_region']('apigateway', region, profile)

        lambda_desc = __salt__['boto_lambda.describe_function'](lambda_name, **self._common_aws_args)

        if lambda_region != apigw_region:
            if not lambda_desc.get('function'):
                # try look up in the same region as the apigateway as well if previous lookup failed
                lambda_desc = __salt__['boto_lambda.describe_function'](lambda_name, **self._common_aws_args)

        if not lambda_desc.get('function'):
            raise ValueError('Could not find lambda function {0} in '
                             'regions [{1}, {2}].'.format(lambda_name, lambda_region, apigw_region))

        lambda_arn = lambda_desc.get('function').get('FunctionArn')
        lambda_uri = ('arn:aws:apigateway:{0}:lambda:path/2015-03-31'
                      '/functions/{1}/invocations'.format(apigw_region, lambda_arn))
        log.info('###############{0}'.format(lambda_uri))
        return lambda_uri

    def _parse_method_data(self, method_name, method_data):
        '''
        Helper function to construct the method request params, models, request_templates and
        integration_type values needed to configure method request integration/mappings.
        '''
        method_params = {}
        method_models = {}
        if 'parameters' in method_data:
            for param in method_data['parameters']:
                p = _Swagger.SwaggerParameter(param)
                if p.name:
                    method_params[p.name] = True
                if p.schema:
                    method_models['application/json'] = p.schema

        request_templates = _Swagger.REQUEST_OPTION_TEMPLATE if method_name == 'options' else _Swagger.REQUEST_TEMPLATE
        integration_type = "MOCK" if method_name == 'options' else "AWS"

        return {'params': method_params,
                'models': method_models,
                'request_templates': request_templates,
                'integration_type': integration_type}

    def _parse_method_response(self, method_name, method_response):
        '''
        Helper function to construct the method response params, models, and integration_params
        values needed to configure method response integration/mappings.
        '''
        method_response_models = {}
        if method_response.schema:
            method_response_models['application/json'] = method_response.schema

        method_response_params = {}
        method_integration_response_params = {}
        for header in method_response.headers:
            method_response_params['method.response.header.{0}'.format(header)] = False
            method_integration_response_params['method.response.header.{0}'.format(header)] = "'*'"

        return {'params': method_response_params,
                'models': method_response_models,
                'integration_params': method_integration_response_params}

    def _deploy_method(self, ret, resource_path, method_name, method_data, api_key_required,
                      lambda_integration_role, lambda_region):
        '''
        Method to create a method for the given resource path, along with its associated
        request and response integrations.

        ret
            a dictionary for returning status to Saltstack

        resource_path
            the full resource path where the named method_name will be associated with.

        method_name
            a string that is one of the following values: 'delete', 'get', 'head', 'options',
            'patch', 'post', 'put'

        method_data
            the value dictionary for this method in the swagger definition file.

        api_key_required
            True or False, whether api key is required to access this method.

        lambda_integration_role
            name of the IAM role or IAM role arn that Api Gateway will assume when executing
            the associated lambda function

        lambda_region
            the region for the lambda function that Api Gateway will integrate to.

        '''
        method = self._parse_method_data(method_name.lower(), method_data)

        # TODO: 'NONE' ??
        m = __salt__['boto_apigateway.create_api_method'](self.restApiId, resource_path,
                                                          method_name.upper(), 'NONE',
                                                          apiKeyRequired=api_key_required,
                                                          requestParameters=method.get('params'),
                                                          requestModels=method.get('models'),
                                                          **self._common_aws_args)
        if not m.get('created'):
            ret = _log_error_and_abort(ret, m)
            return ret

        ret = _log_changes(ret, '_deploy_method.create_api_method', m)

        lambda_uri = ""
        if method_name.lower() != 'options':
            lambda_uri = self._lambda_uri(ret,
                                          self._lambda_name(resource_path, method_name),
                                          lambda_region=lambda_region)

        integration = (
            __salt__['boto_apigateway.create_api_integration'](self.restApiId,
                                                               resource_path,
                                                               method_name.upper(),
                                                               method.get('integration_type'),
                                                               method_name.upper(),
                                                               lambda_uri,
                                                               lambda_integration_role,
                                                               requestTemplates=method.get('request_templates'),
                                                               **self._common_aws_args))
        log.info(integration)
        if not integration.get('created'):
            ret = _log_error_and_abort(ret, integration)
            return ret
        ret = _log_changes(ret, '_deploy_method.create_api_integration', integration)

        if 'responses' in method_data:
            for response, response_data in method_data['responses'].iteritems():
                httpStatus = str(response)
                method_response = self._parse_method_response(method_name.lower(),
                                                             _Swagger.SwaggerMethodResponse(response_data))

                mr = __salt__['boto_apigateway.create_api_method_response'](
                                                                self.restApiId,
                                                                resource_path,
                                                                method_name.upper(),
                                                                httpStatus,
                                                                responseParameters=method_response.get('params'),
                                                                responseModels=method_response.get('models'),
                                                                **self._common_aws_args)
                if not mr.get('created'):
                    ret = _log_error_and_abort(ret, mr)
                    return ret
                ret = _log_changes(ret, '_deploy_method.create_api_method_response', mr)

                mir = __salt__['boto_apigateway.create_api_integration_response'](
                        self.restApiId, resource_path, method_name.upper(), httpStatus, '.*',
                        responseParameters=method_response.get('integration_params'),
                        **self._common_aws_args)
                if not mir.get('created'):
                    ret = _log_error_and_abort(ret, mir)
                    return ret
                ret = _log_changes(ret, '_deploy_method.create_api_integration_response', mir)
        else:
            raise ValueError('No responses specified for {0} {1}'.format(resource_path, method_name))

        return ret

    def deploy_resources(self, ret, api_key_required, lambda_integration_role, lambda_region):
        '''
        Method to deploy resources defined in the swagger file.

        ret
            a dictionary for returning status to Saltstack

        api_key_required
            True or False, whether api key is required to access this method.

        lambda_integration_role
            name of the IAM role or IAM role arn that Api Gateway will assume when executing
            the associated lambda function

        lambda_region
            the region for the lambda function that Api Gateway will integrate to.

        '''

        for path, pathData in self.paths:
            resource_path = ''.join((self.basePath, path))
            resource = __salt__['boto_apigateway.create_api_resources'](restApiId=self.restApiId,
                path=resource_path, **self._common_aws_args)
            if not resource.get('created'):
                ret = _log_error_and_abort(ret, resource)
                return ret
            ret = _log_changes(ret, 'deploy_resources', resource)
            for method, method_data in pathData.iteritems():
                if method in _Swagger.SWAGGER_OPERATION_NAMES:
                    ret = self._deploy_method(ret, resource_path, method, method_data,
                                              api_key_required, lambda_integration_role, lambda_region)
        return ret

