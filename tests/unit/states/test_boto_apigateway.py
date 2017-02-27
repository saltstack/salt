# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
from distutils.version import LooseVersion  # pylint: disable=import-error,no-name-in-module
import logging
import os
import datetime
import random
import string

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import Salt libs
import salt.config
import salt.loader

# Import 3rd-party libs
import yaml

# pylint: disable=import-error,no-name-in-module
from tests.unit.modules.test_boto_apigateway import BotoApiGatewayTestCaseMixin

# Import 3rd-party libs
try:
    import boto3
    import botocore
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from salt.ext.six.moves import range

# Import Salt Libs
from salt.states import boto_apigateway

boto_apigateway.__salt__ = {}
boto_apigateway.__opts__ = {}


# pylint: enable=import-error,no-name-in-module

# the boto_apigateway module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto3_version = '1.2.1'
required_botocore_version = '1.4.49'

region = 'us-east-1'
access_key = 'GKTADJGHEIQSXMKKRBJ08H'
secret_key = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
conn_parameters = {'region': region, 'key': access_key, 'keyid': secret_key, 'profile': {}}
error_message = 'An error occurred (101) when calling the {0} operation: Test-defined error'
error_content = {
  'Error': {
    'Code': 101,
    'Message': "Test-defined error"
  }
}

api_ret = dict(description=u'{\n    "context": "See deployment or stage description",\n    "provisioned_by": "Salt boto_apigateway.present State"\n}',
               createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
               id=u'vni0vq8wzi',
               name=u'unit test api')

no_apis_ret = {u'items': []}

apis_ret = {u'items': [api_ret]}

mock_model_ret = dict(contentType=u'application/json',
                      description=u'mock model',
                      id=u'123abc',
                      name=u'mock model',
                      schema=(u'{\n'
                              u'    "$schema": "http://json-schema.org/draft-04/schema#",\n'
                              u'    "properties": {\n'
                              u'        "field": {\n'
                              u'            "type": "string"\n'
                              u'        }\n'
                              u'    }\n'
                              u'}'))

models_ret = {u'items': [dict(contentType=u'application/json',
                              description=u'Error',
                              id=u'50nw8r',
                              name=u'Error',
                              schema=(u'{\n'
                                      u'    "$schema": "http://json-schema.org/draft-04/schema#",\n'
                                      u'    "properties": {\n'
                                      u'        "code": {\n'
                                      u'            "format": "int32",\n'
                                      u'            "type": "integer"\n'
                                      u'        },\n'
                                      u'        "fields": {\n'
                                      u'            "type": "string"\n'
                                      u'        },\n'
                                      u'        "message": {\n'
                                      u'            "type": "string"\n'
                                      u'        }\n'
                                      u'    },\n'
                                      u'    "title": "Error Schema",\n'
                                      u'    "type": "object"\n'
                                      u'}')),
                         dict(contentType=u'application/json',
                              description=u'User',
                              id=u'terlnw',
                              name=u'User',
                              schema=(u'{\n'
                                      u'    "$schema": "http://json-schema.org/draft-04/schema#",\n'
                                      u'    "properties": {\n'
                                      u'        "password": {\n'
                                      u'            "description": "A password for the new user",\n'
                                      u'            "type": "string"\n'
                                      u'        },\n'
                                      u'        "username": {\n'
                                      u'            "description": "A unique username for the user",\n'
                                      u'            "type": "string"\n'
                                      u'        }\n'
                                      u'    },\n'
                                      u'    "title": "User Schema",\n'
                                      u'    "type": "object"\n'
                                      u'}'))]}

root_resources_ret = {u'items': [dict(id=u'bgk0rk8rqb',
                                      path=u'/')]}

resources_ret = {u'items': [dict(id=u'bgk0rk8rqb',
                                 path=u'/'),
                            dict(id=u'9waiaz',
                                 parentId=u'bgk0rk8rqb',
                                 path=u'/users',
                                 pathPart=u'users',
                                 resourceMethods={u'POST': {}})]}

no_resources_ret = {u'items': []}

stage1_deployment1_ret = dict(cacheClusterEnabled=False,
                              cacheClusterSize=0.5,
                              cacheClusterStatus='NOT_AVAILABLE',
                              createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                              deploymentId=u'kobnrb',
                              description=(u'{\n'
                                           u'    "current_deployment_label": {\n'
                                           u'        "api_name": "unit test api",\n'
                                           u'        "swagger_file": "temp-swagger-sample.yaml",\n'
                                           u'        "swagger_file_md5sum": "4fb17e43bab3a96e7f2410a1597cd0a5",\n'
                                           u'        "swagger_info_object": {\n'
                                           u'            "description": "salt boto apigateway unit test service",\n'
                                           u'            "title": "salt boto apigateway unit test service",\n'
                                           u'            "version": "0.0.0"\n'
                                           u'        }\n'
                                           u'    }\n'
                                           u'}'),
                              lastUpdatedDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                              methodSettings=dict(),
                              stageName='test',
                              variables=dict())

stage1_deployment1_vars_ret = dict(cacheClusterEnabled=False,
                                   cacheClusterSize=0.5,
                                   cacheClusterStatus='NOT_AVAILABLE',
                                   createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                                   deploymentId=u'kobnrb',
                                   description=(u'{\n'
                                                u'    "current_deployment_label": {\n'
                                                u'        "api_name": "unit test api",\n'
                                                u'        "swagger_file": "temp-swagger-sample.yaml",\n'
                                                u'        "swagger_file_md5sum": "4fb17e43bab3a96e7f2410a1597cd0a5",\n'
                                                u'        "swagger_info_object": {\n'
                                                u'            "description": "salt boto apigateway unit test service",\n'
                                                u'            "title": "salt boto apigateway unit test service",\n'
                                                u'            "version": "0.0.0"\n'
                                                u'        }\n'
                                                u'    }\n'
                                                u'}'),
                                   lastUpdatedDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                                   methodSettings=dict(),
                                   stageName='test',
                                   variables={'var1': 'val1'})

stage1_deployment2_ret = dict(cacheClusterEnabled=False,
                              cacheClusterSize=0.5,
                              cacheClusterStatus='NOT_AVAILABLE',
                              createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                              deploymentId=u'kobnrc',
                              description=(u'{\n'
                                           u'    "current_deployment_label": {\n'
                                           u'        "api_name": "unit test api",\n'
                                           u'        "swagger_file": "temp-swagger-sample.yaml",\n'
                                           u'        "swagger_file_md5sum": "5fd538c4336ed5c54b4bf39ddf97c661",\n'
                                           u'        "swagger_info_object": {\n'
                                           u'            "description": "salt boto apigateway unit test service",\n'
                                           u'            "title": "salt boto apigateway unit test service",\n'
                                           u'            "version": "0.0.2"\n'
                                           u'        }\n'
                                           u'    }\n'
                                           u'}'),
                              lastUpdatedDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                              methodSettings=dict(),
                              stageName='test',
                              variables=dict())

stage2_ret = dict(cacheClusterEnabled=False,
                  cacheClusterSize=0.5,
                  cacheClusterStatus='NOT_AVAILABLE',
                  createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                  deploymentId=u'kobnrb',
                  description=(u'{\n'
                               u'    "current_deployment_label": {\n'
                               u'        "api_name": "unit test api",\n'
                               u'        "swagger_file": "temp-swagger-sample.yaml",\n'
                               u'        "swagger_file_md5sum": "4fb17e43bab3a96e7f2410a1597cd0a5",\n'
                               u'        "swagger_info_object": {\n'
                               u'            "description": "salt boto apigateway unit test service",\n'
                               u'            "title": "salt boto apigateway unit test service",\n'
                               u'            "version": "0.0.0"\n'
                               u'        }\n'
                               u'    }\n'
                               u'}'),
                  lastUpdatedDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                  methodSettings=dict(),
                  stageName='dev',
                  variables=dict())

stages_stage2_ret = {u'item': [stage2_ret]}

no_stages_ret = {u'item': []}

deployment1_ret = dict(createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                       description=(u'{\n'
                                    u'    "api_name": "unit test api",\n'
                                    u'    "swagger_file": "temp-swagger-sample.yaml",\n'
                                    u'    "swagger_file_md5sum": "99cd44f491f25a8e8bb468b0a8e23a0a",\n'
                                    u'    "swagger_info_object": {\n'
                                    u'        "description": "salt boto apigateway unit test service",\n'
                                    u'        "title": "salt boto apigateway unit test service",\n'
                                    u'        "version": "0.0.0"\n'
                                    u'    }\n'
                                    u'}'),
                       id=u'kobnrb')

deployment2_ret = dict(createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                       description=(u'{\n'
                                    u'    "api_name": "unit test api",\n'
                                    u'    "swagger_file": "temp-swagger-sample.yaml",\n'
                                    u'    "swagger_file_md5sum": "5fd538c4336ed5c54b4bf39ddf97c661",\n'
                                    u'    "swagger_info_object": {\n'
                                    u'        "description": "salt boto apigateway unit test service",\n'
                                    u'        "title": "salt boto apigateway unit test service",\n'
                                    u'        "version": "0.0.2"\n'
                                    u'    }\n'
                                    u'}'),
                       id=u'kobnrc')

deployments_ret = {u'items': [deployment1_ret, deployment2_ret]}

function_ret = dict(FunctionName='unit_test_api_users_post',
                    Runtime='python2.7',
                    Role=None,
                    Handler='handler',
                    Description='abcdefg',
                    Timeout=5,
                    MemorySize=128,
                    CodeSha256='abcdef',
                    CodeSize=199,
                    FunctionArn='arn:lambda:us-east-1:1234:Something',
                    LastModified='yes')

method_integration_response_200_ret = dict(responseParameters={'method.response.header.Access-Control-Allow-Origin': '*'},
                                           responseTemplates={},
                                           selectionPattern='.*',
                                           statusCode='200')

method_integration_ret = dict(cacheKeyParameters={},
                              cacheNamespace='9waiaz',
                              credentials='arn:aws:iam::1234:role/apigatewayrole',
                              httpMethod='POST',
                              integrationResponses={'200': method_integration_response_200_ret},
                              requestParameters={},
                              requestTemplates={'application/json': ('#set($inputRoot = $input.path(\'$\'))'
                                                                     '{'
                                                                     '"header-params" : {#set ($map = $input.params().header)#foreach( $param in $map.entrySet() )"$param.key" : "$param.value" #if( $foreach.hasNext ), #end#end},'
                                                                     '"query-params" : {#set ($map = $input.params().querystring)#foreach( $param in $map.entrySet() )"$param.key" : "$param.value" #if( $foreach.hasNext ), #end#end},'
                                                                     '"path-params" : {#set ($map = $input.params().path)#foreach( $param in $map.entrySet() )"$param.key" : "$param.value" #if( $foreach.hasNext ), #end#end},'
                                                                     '"body-params" : $input.json(\'$\')'
                                                                     '}')},
                              type='AWS',
                              uri=('arn:aws:apigateway:us-west-2:'
                                   'lambda:path/2015-03-31/functions/arn:aws:lambda:us-west-2:1234567:'
                                   'function:unit_test_api_api_users_post/invocations'))

method_response_200_ret = dict(responseModels={'application/json': 'User'},
                               responseParameters={'method.response.header.Access-Control-Allow-Origin': False},
                               statusCode='200')

method_ret = dict(apiKeyRequired=False,
                  authorizationType='None',
                  httpMethod='POST',
                  methodIntegration=method_integration_ret,
                  methodResponses={'200': method_response_200_ret},
                  requestModels={'application/json': 'User'},
                  requestParameters={})

throttle_rateLimit = 10.0
association_stage_1 = {'apiId': 'apiId1', 'stage': 'stage1'}
association_stage_2 = {'apiId': 'apiId1', 'stage': 'stage2'}

log = logging.getLogger(__name__)

opts = salt.config.DEFAULT_MINION_OPTS
context = {}
utils = salt.loader.utils(opts, whitelist=['boto3'], context=context)
serializers = salt.loader.serializers(opts)
funcs = salt.loader.minion_mods(opts, context=context, utils=utils, whitelist=['boto_apigateway'])
salt_states = salt.loader.states(opts=opts, functions=funcs, utils=utils, whitelist=['boto_apigateway'], serializers=serializers)


def _has_required_boto():
    '''
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    '''
    if not HAS_BOTO:
        return False
    elif LooseVersion(boto3.__version__) < LooseVersion(required_boto3_version):
        return False
    else:
        return True


def _has_required_botocore():
    '''
    Returns True/False boolean depending on if botocore supports usage plan
    '''
    if not HAS_BOTO:
        return False
    elif LooseVersion(botocore.__version__) < LooseVersion(required_botocore_version):
        return False
    else:
        return True


class TempSwaggerFile(object):
    _tmp_swagger_dict = {'info': {'version': '0.0.0',
                                  'description': 'salt boto apigateway unit test service',
                                  'title': 'salt boto apigateway unit test service'},
                         'paths': {'/users': {'post': {'responses': {
                                                            '200': {'headers': {'Access-Control-Allow-Origin': {'type': 'string'}},
                                                                    'description': 'The username of the new user',
                                                                    'schema': {'$ref': '#/definitions/User'}}
                                                                    },
                                                       'parameters': [{'in': 'body',
                                                                       'description': 'New user details.',
                                                                       'name': 'NewUser',
                                                                       'schema': {'$ref': '#/definitions/User'}}],
                                                       'produces': ['application/json'],
                                                       'description': 'Creates a new user.\n',
                                                       'tags': ['Auth'],
                                                       'consumes': ['application/json'],
                                                       'summary': 'Registers a new user'}}},
                         'schemes': ['https'],
                         'produces': ['application/json'],
                         'basePath': '/api',
                         'host': 'rm06h9oac4.execute-api.us-west-2.amazonaws.com',
                         'definitions': {'User': {'properties': {
                                                     'username': {'type': 'string',
                                                                  'description': 'A unique username for the user'},
                                                     'password': {'type': 'string',
                                                                  'description': 'A password for the new user'}
                                                                }},
                                         'Error': {'properties': {
                                                     'fields': {'type': 'string'},
                                                     'message': {'type': 'string'},
                                                     'code': {'type': 'integer',
                                                              'format': 'int32'}
                                                                 }}},
                         'swagger': '2.0'}

    def __enter__(self):
        self.swaggerfile = 'temp-swagger-sample.yaml'
        with salt.utils.fopen(self.swaggerfile, 'w') as f:
            f.write(yaml.dump(self.swaggerdict))
        return self.swaggerfile

    def __exit__(self, objtype, value, traceback):
        os.remove(self.swaggerfile)

    def __init__(self, create_invalid_file=False):
        if create_invalid_file:
            self.swaggerdict = TempSwaggerFile._tmp_swagger_dict.copy()
            # add an invalid top level key
            self.swaggerdict['invalid_key'] = 'invalid'
            # remove one of the required keys 'schemes'
            self.swaggerdict.pop('schemes', None)
            # set swagger version to an unsupported verison 3.0
            self.swaggerdict['swagger'] = '3.0'
            # missing info object
            self.swaggerdict.pop('info', None)
        else:
            self.swaggerdict = TempSwaggerFile._tmp_swagger_dict


class BotoApiGatewayStateTestCaseBase(TestCase):
    conn = None

    # Set up MagicMock to replace the boto3 session
    def setUp(self):
        context.clear()
        # connections keep getting cached from prior tests, can't find the
        # correct context object to clear it. So randomize the cache key, to prevent any
        # cache hits
        conn_parameters['key'] = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(50))

        self.patcher = patch('boto3.session.Session')
        self.addCleanup(self.patcher.stop)
        mock_session = self.patcher.start()

        session_instance = mock_session.return_value
        self.conn = MagicMock()
        session_instance.client.return_value = self.conn


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoApiGatewayTestCase(BotoApiGatewayStateTestCaseBase, BotoApiGatewayTestCaseMixin):
    '''
    TestCase for salt.modules.boto_apigateway state.module
    '''

    def test_present_when_swagger_file_is_invalid(self):
        '''
        Tests present when the swagger file is invalid.
        '''
        result = {}
        with TempSwaggerFile(create_invalid_file=True) as swagger_file:
            result = salt_states['boto_apigateway.present'](
                        'api present',
                        'unit test api',
                        swagger_file,
                        'test',
                        False,
                        'arn:aws:iam::1234:role/apigatewayrole',
                        **conn_parameters)

        self.assertFalse(result.get('result', True))

    def test_present_when_stage_is_already_at_desired_deployment(self):
        '''
        Tests scenario where no action will be taken since we're already
        at desired state
        '''
        self.conn.get_rest_apis.return_value = apis_ret
        self.conn.get_deployment.return_value = deployment1_ret
        self.conn.get_stage.return_value = stage1_deployment1_ret
        self.conn.update_stage.side_effect = ClientError(error_content, 'update_stage should not be called')
        result = {}
        with TempSwaggerFile() as swagger_file:
            result = salt_states['boto_apigateway.present'](
                        'api present',
                        'unit test api',
                        swagger_file,
                        'test',
                        False,
                        'arn:aws:iam::1234:role/apigatewayrole',
                        **conn_parameters)
        self.assertFalse(result.get('abort'))
        self.assertTrue(result.get('current'))
        self.assertIs(result.get('result'), True)
        self.assertNotIn('update_stage should not be called', result.get('comment', ''))

    def test_present_when_stage_is_already_at_desired_deployment_and_needs_stage_variables_update(self):
        '''
        Tests scenario where the deployment is current except for the need to update stage variables
        from {} to {'var1':'val1'}
        '''
        self.conn.get_rest_apis.return_value = apis_ret
        self.conn.get_deployment.return_value = deployment1_ret
        self.conn.get_stage.return_value = stage1_deployment1_ret
        self.conn.update_stage.return_value = stage1_deployment1_vars_ret
        result = {}
        with TempSwaggerFile() as swagger_file:
            result = salt_states['boto_apigateway.present'](
                        'api present',
                        'unit test api',
                        swagger_file,
                        'test',
                        False,
                        'arn:aws:iam::1234:role/apigatewayrole',
                        stage_variables={'var1': 'val1'},
                        **conn_parameters)

        self.assertFalse(result.get('abort'))
        self.assertTrue(result.get('current'))
        self.assertIs(result.get('result'), True)

    def test_present_when_stage_exists_and_is_to_associate_to_existing_deployment(self):
        '''
        Tests scenario where we merely reassociate a stage to a pre-existing
        deployments
        '''
        self.conn.get_rest_apis.return_value = apis_ret
        self.conn.get_deployment.return_value = deployment2_ret
        self.conn.get_deployments.return_value = deployments_ret
        self.conn.get_stage.return_value = stage1_deployment2_ret
        self.conn.update_stage.return_value = stage1_deployment1_ret

        # should never get to the following calls
        self.conn.create_stage.side_effect = ClientError(error_content, 'create_stage')
        self.conn.create_deployment.side_effect = ClientError(error_content, 'create_deployment')

        result = {}
        with TempSwaggerFile() as swagger_file:
            result = salt_states['boto_apigateway.present'](
                        'api present',
                        'unit test api',
                        swagger_file,
                        'test',
                        False,
                        'arn:aws:iam::1234:role/apigatewayrole',
                        **conn_parameters)

        self.assertTrue(result.get('publish'))
        self.assertIs(result.get('result'), True)
        self.assertFalse(result.get('abort'))
        self.assertTrue(result.get('changes', {}).get('new', [{}])[0])

    def test_present_when_stage_is_to_associate_to_new_deployment(self):
        '''
        Tests creation of a new api/model/resource given nothing has been created previously
        '''
        # no api existed
        self.conn.get_rest_apis.return_value = no_apis_ret
        # create top level api
        self.conn.create_rest_api.return_value = api_ret
        # no models existed in the newly created api
        self.conn.get_model.side_effect = ClientError(error_content, 'get_model')
        # create model return values
        self.conn.create_model.return_value = mock_model_ret
        # various paths/resources already created
        self.conn.get_resources.return_value = resources_ret
        # the following should never be called
        self.conn.create_resource.side_effect = ClientError(error_content, 'create_resource')

        # create api method for POST
        self.conn.put_method.return_value = method_ret
        # create api method integration for POST
        self.conn.put_integration.return_value = method_integration_ret
        # create api method response for POST/200
        self.conn.put_method_response.return_value = method_response_200_ret
        # create api method integration response for POST
        self.conn.put_intgration_response.return_value = method_integration_response_200_ret

        result = {}
        with patch.dict(funcs, {'boto_lambda.describe_function': MagicMock(return_value={'function': function_ret})}):
            with TempSwaggerFile() as swagger_file:
                result = salt_states['boto_apigateway.present'](
                            'api present',
                            'unit test api',
                            swagger_file,
                            'test',
                            False,
                            'arn:aws:iam::1234:role/apigatewayrole',
                            **conn_parameters)

        self.assertIs(result.get('result'), True)
        self.assertIs(result.get('abort'), None)

    def test_present_when_stage_associating_to_new_deployment_errored_on_api_creation(self):
        '''
        Tests creation of a new api/model/resource given nothing has been created previously,
        and we failed on creating the top level api object.
        '''
        # no api existed
        self.conn.get_rest_apis.return_value = no_apis_ret
        # create top level api
        self.conn.create_rest_api.side_effect = ClientError(error_content, 'create_rest_api')

        result = {}
        with TempSwaggerFile() as swagger_file:
            result = salt_states['boto_apigateway.present'](
                        'api present',
                        'unit test api',
                        swagger_file,
                        'test',
                        False,
                        'arn:aws:iam::1234:role/apigatewayrole',
                        **conn_parameters)

        self.assertIs(result.get('abort'), True)
        self.assertIs(result.get('result'), False)
        self.assertIn('create_rest_api', result.get('comment', ''))

    def test_present_when_stage_associating_to_new_deployment_errored_on_model_creation(self):
        '''
        Tests creation of a new api/model/resource given nothing has been created previously,
        and we failed on creating the models after successful creation of top level api object.
        '''
        # no api existed
        self.conn.get_rest_apis.return_value = no_apis_ret
        # create top level api
        self.conn.create_rest_api.return_value = api_ret
        # no models existed in the newly created api
        self.conn.get_model.side_effect = ClientError(error_content, 'get_model')
        # create model return error
        self.conn.create_model.side_effect = ClientError(error_content, 'create_model')

        result = {}
        with TempSwaggerFile() as swagger_file:
            result = salt_states['boto_apigateway.present'](
                        'api present',
                        'unit test api',
                        swagger_file,
                        'test',
                        False,
                        'arn:aws:iam::1234:role/apigatewayrole',
                        **conn_parameters)

        self.assertIs(result.get('abort'), True)
        self.assertIs(result.get('result'), False)
        self.assertIn('create_model', result.get('comment', ''))

    def test_present_when_stage_associating_to_new_deployment_errored_on_resource_creation(self):
        '''
        Tests creation of a new api/model/resource given nothing has been created previously,
        and we failed on creating the resource (paths) after successful creation of top level api/model
        objects.
        '''
        # no api existed
        self.conn.get_rest_apis.return_value = no_apis_ret
        # create top level api
        self.conn.create_rest_api.return_value = api_ret
        # no models existed in the newly created api
        self.conn.get_model.side_effect = ClientError(error_content, 'get_model')
        # create model return values
        self.conn.create_model.return_value = mock_model_ret
        # get resources has nothing intiially except to the root path '/'
        self.conn.get_resources.return_value = root_resources_ret
        # create resources return error
        self.conn.create_resource.side_effect = ClientError(error_content, 'create_resource')
        result = {}
        with TempSwaggerFile() as swagger_file:
            result = salt_states['boto_apigateway.present'](
                        'api present',
                        'unit test api',
                        swagger_file,
                        'test',
                        False,
                        'arn:aws:iam::1234:role/apigatewayrole',
                        **conn_parameters)
        self.assertIs(result.get('abort'), True)
        self.assertIs(result.get('result'), False)
        self.assertIn('create_resource', result.get('comment', ''))

    def test_present_when_stage_associating_to_new_deployment_errored_on_put_method(self):
        '''
        Tests creation of a new api/model/resource given nothing has been created previously,
        and we failed on adding a post method to the resource after successful creation of top level
        api, model, resource objects.
        '''
        # no api existed
        self.conn.get_rest_apis.return_value = no_apis_ret
        # create top level api
        self.conn.create_rest_api.return_value = api_ret
        # no models existed in the newly created api
        self.conn.get_model.side_effect = ClientError(error_content, 'get_model')
        # create model return values
        self.conn.create_model.return_value = mock_model_ret
        # various paths/resources already created
        self.conn.get_resources.return_value = resources_ret
        # the following should never be called
        self.conn.create_resource.side_effect = ClientError(error_content, 'create_resource')

        # create api method for POST
        self.conn.put_method.side_effect = ClientError(error_content, 'put_method')

        result = {}
        with patch.dict(funcs, {'boto_lambda.describe_function': MagicMock(return_value={'function': function_ret})}):
            with TempSwaggerFile() as swagger_file:
                result = salt_states['boto_apigateway.present'](
                            'api present',
                            'unit test api',
                            swagger_file,
                            'test',
                            False,
                            'arn:aws:iam::1234:role/apigatewayrole',
                            **conn_parameters)

        self.assertIs(result.get('abort'), True)
        self.assertIs(result.get('result'), False)
        self.assertIn('put_method', result.get('comment', ''))

    def test_present_when_stage_associating_to_new_deployment_errored_on_lambda_function_lookup(self):
        '''
        Tests creation of a new api/model/resource given nothing has been created previously,
        and we failed on adding a post method due to a lamda look up failure after successful
        creation of top level api, model, resource objects.
        '''
        # no api existed
        self.conn.get_rest_apis.return_value = no_apis_ret
        # create top level api
        self.conn.create_rest_api.return_value = api_ret
        # no models existed in the newly created api
        self.conn.get_model.side_effect = ClientError(error_content, 'get_model')
        # create model return values
        self.conn.create_model.return_value = mock_model_ret
        # various paths/resources already created
        self.conn.get_resources.return_value = resources_ret
        # the following should never be called
        self.conn.create_resource.side_effect = ClientError(error_content, 'create_resource')
        # create api method for POST
        self.conn.put_method.return_value = method_ret
        # create api method integration for POST
        self.conn.put_integration.side_effect = ClientError(error_content, 'put_integration should not be invoked')

        result = {}
        with patch.dict(funcs, {'boto_lambda.describe_function': MagicMock(return_value={'error': 'no such lambda'})}):
            with TempSwaggerFile() as swagger_file:
                result = salt_states['boto_apigateway.present'](
                            'api present',
                            'unit test api',
                            swagger_file,
                            'test',
                            False,
                            'arn:aws:iam::1234:role/apigatewayrole',
                            **conn_parameters)

        self.assertIs(result.get('result'), False)
        self.assertNotIn('put_integration should not be invoked', result.get('comment', ''))
        self.assertIn('not find lambda function', result.get('comment', ''))

    def test_present_when_stage_associating_to_new_deployment_errored_on_put_integration(self):
        '''
        Tests creation of a new api/model/resource given nothing has been created previously,
        and we failed on adding an integration for the post method to the resource after
        successful creation of top level api, model, resource objects.
        '''
        # no api existed
        self.conn.get_rest_apis.return_value = no_apis_ret
        # create top level api
        self.conn.create_rest_api.return_value = api_ret
        # no models existed in the newly created api
        self.conn.get_model.side_effect = ClientError(error_content, 'get_model')
        # create model return values
        self.conn.create_model.return_value = mock_model_ret
        # various paths/resources already created
        self.conn.get_resources.return_value = resources_ret
        # the following should never be called
        self.conn.create_resource.side_effect = ClientError(error_content, 'create_resource')

        # create api method for POST
        self.conn.put_method.return_value = method_ret
        # create api method integration for POST
        self.conn.put_integration.side_effect = ClientError(error_content, 'put_integration')

        result = {}
        with patch.dict(funcs, {'boto_lambda.describe_function': MagicMock(return_value={'function': function_ret})}):
            with TempSwaggerFile() as swagger_file:
                result = salt_states['boto_apigateway.present'](
                            'api present',
                            'unit test api',
                            swagger_file,
                            'test',
                            False,
                            'arn:aws:iam::1234:role/apigatewayrole',
                            **conn_parameters)

        self.assertIs(result.get('abort'), True)
        self.assertIs(result.get('result'), False)
        self.assertIn('put_integration', result.get('comment', ''))

    def test_present_when_stage_associating_to_new_deployment_errored_on_put_method_response(self):
        '''
        Tests creation of a new api/model/resource given nothing has been created previously,
        and we failed on adding a method response for the post method to the resource after
        successful creation of top level api, model, resource objects.
        '''
        # no api existed
        self.conn.get_rest_apis.return_value = no_apis_ret
        # create top level api
        self.conn.create_rest_api.return_value = api_ret
        # no models existed in the newly created api
        self.conn.get_model.side_effect = ClientError(error_content, 'get_model')
        # create model return values
        self.conn.create_model.return_value = mock_model_ret
        # various paths/resources already created
        self.conn.get_resources.return_value = resources_ret
        # the following should never be called
        self.conn.create_resource.side_effect = ClientError(error_content, 'create_resource')

        # create api method for POST
        self.conn.put_method.return_value = method_ret
        # create api method integration for POST
        self.conn.put_integration.return_value = method_integration_ret
        # create api method response for POST/200
        self.conn.put_method_response.side_effect = ClientError(error_content, 'put_method_response')

        result = {}
        with patch.dict(funcs, {'boto_lambda.describe_function': MagicMock(return_value={'function': function_ret})}):
            with TempSwaggerFile() as swagger_file:
                result = salt_states['boto_apigateway.present'](
                            'api present',
                            'unit test api',
                            swagger_file,
                            'test',
                            False,
                            'arn:aws:iam::1234:role/apigatewayrole',
                            **conn_parameters)

        self.assertIs(result.get('abort'), True)
        self.assertIs(result.get('result'), False)
        self.assertIn('put_method_response', result.get('comment', ''))

    def test_present_when_stage_associating_to_new_deployment_errored_on_put_integration_response(self):
        '''
        Tests creation of a new api/model/resource given nothing has been created previously,
        and we failed on adding an integration response for the post method to the resource after
        successful creation of top level api, model, resource objects.
        '''
        # no api existed
        self.conn.get_rest_apis.return_value = no_apis_ret
        # create top level api
        self.conn.create_rest_api.return_value = api_ret
        # no models existed in the newly created api
        self.conn.get_model.side_effect = ClientError(error_content, 'get_model')
        # create model return values
        self.conn.create_model.return_value = mock_model_ret
        # various paths/resources already created
        self.conn.get_resources.return_value = resources_ret
        # the following should never be called
        self.conn.create_resource.side_effect = ClientError(error_content, 'create_resource')

        # create api method for POST
        self.conn.put_method.return_value = method_ret
        # create api method integration for POST
        self.conn.put_integration.return_value = method_integration_ret
        # create api method response for POST/200
        self.conn.put_method_response.return_value = method_response_200_ret
        # create api method integration response for POST
        self.conn.put_integration_response.side_effect = ClientError(error_content, 'put_integration_response')

        result = {}
        with patch.dict(funcs, {'boto_lambda.describe_function': MagicMock(return_value={'function': function_ret})}):
            with TempSwaggerFile() as swagger_file:
                result = salt_states['boto_apigateway.present'](
                            'api present',
                            'unit test api',
                            swagger_file,
                            'test',
                            False,
                            'arn:aws:iam::1234:role/apigatewayrole',
                            **conn_parameters)

        self.assertIs(result.get('abort'), True)
        self.assertIs(result.get('result'), False)
        self.assertIn('put_integration_response', result.get('comment', ''))

    def test_absent_when_rest_api_does_not_exist(self):
        '''
        Tests scenario where the given api_name does not exist, absent state should return True
        with no changes.
        '''
        self.conn.get_rest_apis.return_value = apis_ret
        self.conn.get_stage.side_effect = ClientError(error_content, 'get_stage should not be called')

        result = salt_states['boto_apigateway.absent'](
                    'api present',
                    'no_such_rest_api',
                    'no_such_stage',
                    nuke_api=False,
                    **conn_parameters)

        self.assertIs(result.get('result'), True)
        self.assertNotIn('get_stage should not be called', result.get('comment', ''))
        self.assertEqual(result.get('changes'), {})

    def test_absent_when_stage_is_invalid(self):
        '''
        Tests scenario where the stagename doesn't exist
        '''
        self.conn.get_rest_apis.return_value = apis_ret
        self.conn.get_stage.return_value = stage1_deployment1_ret
        self.conn.delete_stage.side_effect = ClientError(error_content, 'delete_stage')

        result = salt_states['boto_apigateway.absent'](
                    'api present',
                    'unit test api',
                    'no_such_stage',
                    nuke_api=False,
                    **conn_parameters)

        self.assertTrue(result.get('abort', False))

    def test_absent_when_stage_is_valid_and_only_one_stage_is_associated_to_deployment(self):
        '''
        Tests scenario where the stagename exists
        '''
        self.conn.get_rest_apis.return_value = apis_ret
        self.conn.get_stage.return_value = stage1_deployment1_ret
        self.conn.delete_stage.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        self.conn.get_stages.return_value = no_stages_ret
        self.conn.delete_deployment.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}

        result = salt_states['boto_apigateway.absent'](
                    'api present',
                    'unit test api',
                    'test',
                    nuke_api=False,
                    **conn_parameters)

        self.assertTrue(result.get('result', False))

    def test_absent_when_stage_is_valid_and_two_stages_are_associated_to_deployment(self):
        '''
        Tests scenario where the stagename exists and there are two stages associated with same deployment
        '''
        self.conn.get_rest_apis.return_value = apis_ret
        self.conn.get_stage.return_value = stage1_deployment1_ret
        self.conn.delete_stage.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        self.conn.get_stages.return_value = stages_stage2_ret

        result = salt_states['boto_apigateway.absent'](
                    'api present',
                    'unit test api',
                    'test',
                    nuke_api=False,
                    **conn_parameters)

        self.assertTrue(result.get('result', False))

    def test_absent_when_failing_to_delete_a_deployment_no_longer_associated_with_any_stages(self):
        '''
        Tests scenario where stagename exists and is deleted, but a failure occurs when trying to delete
        the deployment which is no longer associated to any other stages
        '''
        self.conn.get_rest_apis.return_value = apis_ret
        self.conn.get_stage.return_value = stage1_deployment1_ret
        self.conn.delete_stage.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        self.conn.get_stages.return_value = no_stages_ret
        self.conn.delete_deployment.side_effect = ClientError(error_content, 'delete_deployment')

        result = salt_states['boto_apigateway.absent'](
                    'api present',
                    'unit test api',
                    'test',
                    nuke_api=False,
                    **conn_parameters)

        self.assertTrue(result.get('abort', False))

    def test_absent_when_nuke_api_and_no_more_stages_deployments_remain(self):
        '''
        Tests scenario where the stagename exists and there are no stages associated with same deployment,
        the api would be deleted.
        '''
        self.conn.get_rest_apis.return_value = apis_ret
        self.conn.get_stage.return_value = stage1_deployment1_ret
        self.conn.delete_stage.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        self.conn.get_stages.return_value = no_stages_ret
        self.conn.get_deployments.return_value = deployments_ret
        self.conn.delete_rest_api.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}

        result = salt_states['boto_apigateway.absent'](
                    'api present',
                    'unit test api',
                    'test',
                    nuke_api=True,
                    **conn_parameters)

        self.assertIs(result.get('result'), True)
        self.assertIsNot(result.get('abort'), True)
        self.assertIs(result.get('changes', {}).get('new', [{}])[0].get('delete_api', {}).get('deleted'), True)

    def test_absent_when_nuke_api_and_other_stages_deployments_exist(self):
        '''
        Tests scenario where the stagename exists and there are two stages associated with same deployment,
        though nuke_api is requested, due to remaining deployments, we will not call the delete_rest_api call.
        '''
        self.conn.get_rest_apis.return_value = apis_ret
        self.conn.get_stage.return_value = stage1_deployment1_ret
        self.conn.delete_stage.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        self.conn.get_stages.return_value = stages_stage2_ret
        self.conn.get_deployments.return_value = deployments_ret
        self.conn.delete_rest_api.side_effect = ClientError(error_content, 'unexpected_api_delete')

        result = salt_states['boto_apigateway.absent'](
                    'api present',
                    'unit test api',
                    'test',
                    nuke_api=True,
                    **conn_parameters)

        self.assertIs(result.get('result'), True)
        self.assertIsNot(result.get('abort'), True)


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(_has_required_botocore() is False,
        'The botocore module must be greater than'
        ' or equal to version {0}'.format(required_botocore_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoApiGatewayUsagePlanTestCase(BotoApiGatewayStateTestCaseBase, BotoApiGatewayTestCaseMixin):
    '''
    TestCase for salt.modules.boto_apigateway state.module, usage_plans portion
    '''

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'error': 'error'})})
    def test_usage_plan_present_if_describe_fails(self, *args):
        '''
        Tests correct error processing for describe_usage_plan failure
        '''
        result = {}

        result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Failed to describe existing usage plans')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': []})})
    @patch.dict(boto_apigateway.__opts__, {'test': True})
    def test_usage_plan_present_if_there_is_no_such_plan_and_test_option_is_set(self, *args):
        '''
        TestCse for salt.modules.boto_apigateway state.module, checking that if __opts__['test'] is set
        and usage plan does not exist, correct diagnostic will be returned
        '''
        result = {}

        result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'a new usage plan plan_name would be created')
        self.assertIn('result', result)
        self.assertEqual(result['result'], None)

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': []})})
    @patch.dict(boto_apigateway.__opts__, {'test': False})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.create_usage_plan': MagicMock(return_value={'error': 'error'})})
    def test_usage_plan_present_if_create_usage_plan_fails(self, *args):
        '''
        Tests behavior for the case when creating a new usage plan fails
        '''
        result = {}

        result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Failed to create a usage plan plan_name, error')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{
                                                                                                                'id': 'planid',
                                                                                                                'name': 'planname'
                                                                                                            }]})})
    @patch.dict(boto_apigateway.__opts__, {'test': False})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.update_usage_plan': MagicMock()})
    def test_usage_plan_present_if_plan_is_there_and_needs_no_updates(self, *args):
        '''
        Tests behavior for the case when plan is present and needs no updates
        '''
        result = {}

        result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], True)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'usage plan plan_name is already in a correct state')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

        self.assertTrue(boto_apigateway.__salt__['boto_apigateway.update_usage_plan'].call_count == 0)

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{
                                                                                                                'id': 'planid',
                                                                                                                'name': 'planname',
                                                                                                                'throttle': {'rateLimit': 10.0}
                                                                                                            }]})})
    @patch.dict(boto_apigateway.__opts__, {'test': True})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.update_usage_plan': MagicMock()})
    def test_usage_plan_present_if_plan_is_there_and_needs_updates_but_test_is_set(self, *args):
        '''
        Tests behavior when usage plan needs to be updated by tests option is set
        '''
        result = {}

        result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'a new usage plan plan_name would be updated')
        self.assertIn('result', result)
        self.assertEqual(result['result'], None)
        self.assertTrue(boto_apigateway.__salt__['boto_apigateway.update_usage_plan'].call_count == 0)

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{
                                                                                                                'id': 'planid',
                                                                                                                'name': 'planname',
                                                                                                                'throttle': {'rateLimit': 10.0}
                                                                                                            }]})})
    @patch.dict(boto_apigateway.__opts__, {'test': False})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.update_usage_plan': MagicMock(return_value={'error': 'error'})})
    def test_usage_plan_present_if_plan_is_there_and_needs_updates_but_update_fails(self, *args):
        '''
        Tests error processing for the case when updating an existing usage plan fails
        '''
        result = {}

        result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Failed to update a usage plan plan_name, error')

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=[{'plans': []}, {'plans': [{'id': 'id'}]}])})
    @patch.dict(boto_apigateway.__opts__, {'test': False})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.create_usage_plan': MagicMock(return_value={'created': True})})
    # @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.update_usage_plan': MagicMock(return_value={'error': 'error'})})
    def test_usage_plan_present_if_plan_has_been_created(self, *args):
        '''
        Tests successful case for creating a new usage plan
        '''
        result = {}

        result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], True)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'A new usage plan plan_name has been created')
        self.assertEqual(result['changes']['old'], {'plan': None})
        self.assertEqual(result['changes']['new'], {'plan': {'id': 'id'}})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=[{'plans': [{'id': 'id'}]},
                                                                                                          {'plans': [{'id': 'id',
                                                                                                                      'throttle': {'rateLimit': throttle_rateLimit}}]}])})
    @patch.dict(boto_apigateway.__opts__, {'test': False})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.update_usage_plan': MagicMock(return_value={'updated': True})})
    def test_usage_plan_present_if_plan_has_been_updated(self, *args):
        '''
        Tests successful case for updating a usage plan
        '''
        result = {}

        result = boto_apigateway.usage_plan_present('name', 'plan_name', throttle={'rateLimit': throttle_rateLimit}, **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], True)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'usage plan plan_name has been updated')
        self.assertEqual(result['changes']['old'], {'plan': {'id': 'id'}})
        self.assertEqual(result['changes']['new'], {'plan': {'id': 'id', 'throttle': {'rateLimit': throttle_rateLimit}}})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=ValueError('error'))})
    def test_usage_plan_present_if_ValueError_is_raised(self, *args):
        '''
        Tests error processing for the case when ValueError is raised when creating a usage plan
        '''
        result = {}

        result = boto_apigateway.usage_plan_present('name', 'plan_name', throttle={'rateLimit': throttle_rateLimit}, **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], "('error',)")

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=IOError('error'))})
    def test_usage_plan_present_if_IOError_is_raised(self, *args):
        '''
        Tests error processing for the case when IOError is raised when creating a usage plan
        '''
        result = {}

        result = boto_apigateway.usage_plan_present('name', 'plan_name', throttle={'rateLimit': throttle_rateLimit}, **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], "('error',)")

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'error': 'error'})})
    def test_usage_plan_absent_if_describe_fails(self, *args):
        '''
        Tests correct error processing for describe_usage_plan failure
        '''
        result = {}

        result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Failed to describe existing usage plans')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': []})})
    def test_usage_plan_absent_if_plan_is_not_present(self, *args):
        '''
        Tests behavior for the case when the plan that needs to be absent does not exist
        '''
        result = {}

        result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], True)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Usage plan plan_name does not exist already')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__opts__, {'test': True})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id'}]})})
    def test_usage_plan_absent_if_plan_is_present_but_test_option_is_set(self, *args):
        '''
        Tests behavior for the case when usage plan needs to be deleted by tests option is set
        '''
        result = {}

        result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], None)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Usage plan plan_name exists and would be deleted')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__opts__, {'test': False})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id'}]})})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.delete_usage_plan': MagicMock(return_value={'error': 'error'})})
    def test_usage_plan_absent_if_plan_is_present_but_delete_fails(self, *args):
        '''
        Tests correct error processing when deleting a usage plan fails
        '''
        result = {}

        result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Failed to delete usage plan plan_name, {\'error\': \'error\'}')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__opts__, {'test': False})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id'}]})})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.delete_usage_plan': MagicMock(return_value={'deleted': True})})
    def test_usage_plan_absent_if_plan_has_been_deleted(self, *args):
        '''
        Tests successful case for deleting a usage plan
        '''
        result = {}

        result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], True)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Usage plan plan_name has been deleted')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {'new': {'plan': None}, 'old': {'plan': {'id': 'id'}}})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=ValueError('error'))})
    def test_usage_plan_absent_if_ValueError_is_raised(self, *args):
        '''
        Tests correct error processing for the case when ValueError is raised when deleting a usage plan
        '''
        result = {}

        result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], "('error',)")

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=IOError('error'))})
    def test_usage_plan_absent_if_IOError_is_raised(self, *args):
        '''
        Tests correct error processing for the case when IOError is raised when deleting a usage plan
        '''
        result = {}

        result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], "('error',)")


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(_has_required_botocore() is False,
        'The botocore module must be greater than'
        ' or equal to version {0}'.format(required_botocore_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoApiGatewayUsagePlanAssociationTestCase(BotoApiGatewayStateTestCaseBase, BotoApiGatewayTestCaseMixin):
    '''
    TestCase for salt.modules.boto_apigateway state.module, usage_plans_association portion
    '''

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'error': 'error'})})
    def test_usage_plan_association_present_if_describe_fails(self, *args):
        '''
        Tests correct error processing for describe_usage_plan failure
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_1], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Failed to describe existing usage plans')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': []})})
    def test_usage_plan_association_present_if_plan_is_not_present(self, *args):
        '''
        Tests correct error processing if a plan for which association has been requested is not present
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_1], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Usage plan plan_name does not exist')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1'},
                                                                                                                     {'id': 'id2'}]})})
    def test_usage_plan_association_present_if_multiple_plans_with_the_same_name_exist(self, *args):
        '''
        Tests correct error processing for the case when multiple plans with the same name exist
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_1], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'There are multiple usage plans with the same name - it is not supported')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1',
                                                                                                                      'apiStages':
                                                                                                                        [association_stage_1]}]})})
    def test_usage_plan_association_present_if_association_already_exists(self, *args):
        '''
        Tests the behavior for the case when requested association is already present
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_1], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], True)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Usage plan is already asssociated to all api stages')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1',
                                                                                                                      'apiStages':
                                                                                                                        [association_stage_1]}]})})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.attach_usage_plan_to_apis': MagicMock(return_value={'error': 'error'})})
    def test_usage_plan_association_present_if_update_fails(self, *args):
        '''
        Tests correct error processing for the case when adding associations fails
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_2], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertTrue(result['comment'].startswith('Failed to associate a usage plan'))
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1',
                                                                                                                      'apiStages':
                                                                                                                        [association_stage_1]}]})})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.attach_usage_plan_to_apis': MagicMock(return_value={'result': {'apiStages': [association_stage_1,
                                                                                                                                         association_stage_2]}})})
    def test_usage_plan_association_present_success(self, *args):
        '''
        Tests successful case for adding usage plan associations to a given api stage
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_2], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], True)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'successfully associated usage plan to apis')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {'new': [association_stage_1, association_stage_2], 'old': [association_stage_1]})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=ValueError('error'))})
    def test_usage_plan_association_present_if_value_error_is_thrown(self, *args):
        '''
        Tests correct error processing for the case when IOError is raised while trying to set usage plan associations
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], "('error',)")
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=IOError('error'))})
    def test_usage_plan_association_present_if_io_error_is_thrown(self, *args):
        '''
        Tests correct error processing for the case when IOError is raised while trying to set usage plan associations
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], "('error',)")
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'error': 'error'})})
    def test_usage_plan_association_absent_if_describe_fails(self, *args):
        '''
        Tests correct error processing for describe_usage_plan failure
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Failed to describe existing usage plans')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': []})})
    def test_usage_plan_association_absent_if_plan_is_not_present(self, *args):
        '''
        Tests error processing for the case when plan for which associations need to be modified is not present
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Usage plan plan_name does not exist')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1'},
                                                                                                                     {'id': 'id2'}]})})
    def test_usage_plan_association_absent_if_multiple_plans_with_the_same_name_exist(self, *args):
        '''
        Tests the case when there are multiple plans with the same name but different Ids
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'There are multiple usage plans with the same name - it is not supported')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1', 'apiStages': []}]})})
    def test_usage_plan_association_absent_if_plan_has_no_associations(self, *args):
        '''
        Tests the case when the plan has no associations at all
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], True)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Usage plan plan_name has no associated stages already')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1', 'apiStages': [association_stage_1]}]})})
    def test_usage_plan_association_absent_if_plan_has_no_specific_association(self, *args):
        '''
        Tests the case when requested association is not present already
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_2], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], True)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'Usage plan is already not asssociated to any api stages')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1', 'apiStages': [association_stage_1,
                                                                                                                                                 association_stage_2]}]})})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.detach_usage_plan_from_apis': MagicMock(return_value={'error': 'error'})})
    def test_usage_plan_association_absent_if_detaching_association_fails(self, *args):
        '''
        Tests correct error processing when detaching the usage plan from the api function is called
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_2], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertTrue(result['comment'].startswith('Failed to disassociate a usage plan plan_name from the apis'))
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1', 'apiStages': [association_stage_1,
                                                                                                                                                 association_stage_2]}]})})
    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.detach_usage_plan_from_apis': MagicMock(return_value={'result': {'apiStages': [association_stage_1]}})})
    def test_usage_plan_association_absent_success(self, *args):
        '''
        Tests successful case of disaccosiation the usage plan from api stages
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_2], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], True)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], 'successfully disassociated usage plan from apis')
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {'new': [association_stage_1], 'old': [association_stage_1, association_stage_2]})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=ValueError('error'))})
    def test_usage_plan_association_absent_if_ValueError_is_raised(self, *args):
        '''
        Tests correct error processing for the case where ValueError is raised while trying to remove plan associations
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], "('error',)")
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})

    @patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=IOError('error'))})
    def test_usage_plan_association_absent_if_IOError_is_raised(self, *args):
        '''
        Tests correct error processing for the case where IOError exception is raised while trying to remove plan associations
        '''
        result = {}

        result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)

        self.assertIn('result', result)
        self.assertEqual(result['result'], False)
        self.assertIn('comment', result)
        self.assertEqual(result['comment'], "('error',)")
        self.assertIn('changes', result)
        self.assertEqual(result['changes'], {})
