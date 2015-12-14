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

def api_present(name, api_name, swagger_file, lambda_integration_role,
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
        # try to open the swagger file and basic validation
        swagger = Swagger(api_name, swagger_file)

        # first deploy a Rest Api on AWS
        ret = swagger.deploy_api(ret, region=region, key=key, keyid=keyid, profile=profile)
        if ret.get('abort'):
            return ret

        # next, deploy models of to the AWS API
        ret = swagger.deploy_models(ret, region=region, key=key, keyid=keyid, profile=profile)
        if ret.get('abort'):
            return ret

        ret = swagger.deploy_resources(ret, lambda_integration_role=lambda_integration_role,
                                       lambda_region=lambda_region, region=region,
                                       key=key, keyid=keyid, profile=profile)
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
        swagger = Swagger(api_name, swagger_file)

        ret = swagger.delete_api(ret, region=region, key=key, keyid=keyid, profile=profile)

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

    def __init__(self, api_name, swagger_file_path):
        self._api_name = api_name
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
        return self._api_name

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

    def _parse_method_data(self, method_data):
        method_params = {}
        method_models = {}
        if 'parameters' in method_data:
            for param in method_data['parameters']:
                p = Swagger.SwaggerParameter(param)
                if p.name:
                    method_params[p.name] = True
                if p.schema:
                    method_models['application/json'] = p.schema

        request_templates = {}
        if method_params or method_models:
            request_templates = self.REQUEST_TEMPLATE

        return {'params': method_params,
                'models': method_models,
                'request_templates': request_templates}

    def _parse_method_response(self, method_response):
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

    def deploy_method(self, ret, resource_path, method_name, method_data, lambda_integration_role, lambda_region,
                      region=None, key=None, keyid=None, profile=None):
        method = self._parse_method_data(method_data)

        # TODO: 'NONE' ??
        m = __salt__['boto_apigateway.create_api_method'](self.restApiId, resource_path,
            method_name.upper(), 'NONE', requestParameters=method.get('params'), requestModels=method.get('models'),
            region=region, key=key, keyid=keyid, profile=profile)
        if not m.get('created'):
            ret = _log_error_and_abort(ret, m)
            return ret

        ret = _log_changes(ret, 'deploy_method.create_api_method', m)

        lambda_uri = self._lambda_uri(ret, self._lambda_name(resource_path, method_name),
                                      region=region, key=key, keyid=keyid, profile=profile)

        integration = __salt__['boto_apigateway.create_api_integration'](
                self.restApiId, resource_path, method_name.upper(), 'AWS', method_name.upper(),
                lambda_uri, lambda_integration_role, requestTemplates=method.get('request_templates'),
                region=region, key=key, keyid=keyid, profile=profile)
        log.info(integration)
        if not integration.get('created'):
            ret = _log_error_and_abort(ret, integration)
            return ret
        ret = _log_changes(ret, 'deploy_method.create_api_integration', integration)

        if 'responses' in method_data:
            for response, response_data in method_data['responses'].iteritems():
                httpStatus = str(response)
                method_response = self._parse_method_response(Swagger.SwaggerMethodResponse(response_data))

                mr = __salt__['boto_apigateway.create_api_method_response'](
                        self.restApiId, resource_path, method_name.upper(), httpStatus,
                        responseParameters=method_response.get('params'), responseModels=method_response.get('models'),
                        region=region, key=key, keyid=keyid, profile=profile)
                if not mr.get('created'):
                    ret = _log_error_and_abort(ret, mr)
                    return ret
                ret = _log_changes(ret, 'deploy_method.create_api_method_response', mr)

                mir = __salt__['boto_apigateway.create_api_integration_response'](
                        self.restApiId, resource_path, method_name.upper(), httpStatus, '.*',
                        responseParameters=method_response.get('integration_params'),
                        region=region, key=key, keyid=keyid, profile=profile)
                if not mir.get('created'):
                    ret = _log_error_and_abort(ret, mir)
                    return ret
                ret = _log_changes(ret, 'deploy_method.create_api_integration_response', mir)
        else:
            raise ValueError('No responses specified for {0} {1}'.format(resource_path, method_name))

        return ret

    def deploy_resources(self, ret, lambda_integration_role, lambda_region,
                         region=None, key=None, keyid=None, profile=None):
        for path, pathData in self.paths:
            resource_path = ''.join((self.basePath, path))
            resource = __salt__['boto_apigateway.create_api_resources'](restApiId=self.restApiId,
                path=resource_path, region=region, key=key, keyid=keyid, profile=profile)
            if not resource.get('created'):
                ret = _log_error_and_abort(ret, resource)
                return ret
            ret = _log_changes(ret, 'deploy_resources', resource)
            for method, method_data in pathData.iteritems():
                if method in self.SWAGGER_OPERATION_NAMES:
                    ret = self.deploy_method(ret, resource_path, method, method_data, lambda_integration_role, lambda_region,
                                             region=region, key=key, keyid=keyid, profile=profile)
        return ret

