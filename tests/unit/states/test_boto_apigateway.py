# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import datetime
import random
import string

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import Salt libs
import salt.config
import salt.loader
import salt.utils.files
import salt.utils.yaml
from salt.utils.versions import LooseVersion

# pylint: disable=import-error,no-name-in-module
from tests.unit.modules.test_boto_apigateway import BotoApiGatewayTestCaseMixin

# Import 3rd-party libs
from salt.ext.six.moves import range
try:
    import boto3
    import botocore
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


# Import Salt Libs
import salt.states.boto_apigateway as boto_apigateway

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

api_ret = dict(description='{\n    "context": "See deployment or stage description",\n    "provisioned_by": "Salt boto_apigateway.present State"\n}',
               createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
               id='vni0vq8wzi',
               name='unit test api')

no_apis_ret = {'items': []}

apis_ret = {'items': [api_ret]}

mock_model_ret = dict(contentType='application/json',
                      description='mock model',
                      id='123abc',
                      name='mock model',
                      schema=('{\n'
                              '    "$schema": "http://json-schema.org/draft-04/schema#",\n'
                              '    "properties": {\n'
                              '        "field": {\n'
                              '            "type": "string"\n'
                              '        }\n'
                              '    }\n'
                              '}'))

models_ret = {'items': [dict(contentType='application/json',
                              description='Error',
                              id='50nw8r',
                              name='Error',
                              schema=('{\n'
                                      '    "$schema": "http://json-schema.org/draft-04/schema#",\n'
                                      '    "properties": {\n'
                                      '        "code": {\n'
                                      '            "format": "int32",\n'
                                      '            "type": "integer"\n'
                                      '        },\n'
                                      '        "fields": {\n'
                                      '            "type": "string"\n'
                                      '        },\n'
                                      '        "message": {\n'
                                      '            "type": "string"\n'
                                      '        }\n'
                                      '    },\n'
                                      '    "title": "Error Schema",\n'
                                      '    "type": "object"\n'
                                      '}')),
                         dict(contentType='application/json',
                              description='User',
                              id='terlnw',
                              name='User',
                              schema=('{\n'
                                      '    "$schema": "http://json-schema.org/draft-04/schema#",\n'
                                      '    "properties": {\n'
                                      '        "password": {\n'
                                      '            "description": "A password for the new user",\n'
                                      '            "type": "string"\n'
                                      '        },\n'
                                      '        "username": {\n'
                                      '            "description": "A unique username for the user",\n'
                                      '            "type": "string"\n'
                                      '        }\n'
                                      '    },\n'
                                      '    "title": "User Schema",\n'
                                      '    "type": "object"\n'
                                      '}'))]}

root_resources_ret = {'items': [dict(id='bgk0rk8rqb',
                                      path='/')]}

resources_ret = {'items': [dict(id='bgk0rk8rqb',
                                 path='/'),
                            dict(id='9waiaz',
                                 parentId='bgk0rk8rqb',
                                 path='/users',
                                 pathPart='users',
                                 resourceMethods={'POST': {}})]}

no_resources_ret = {'items': []}

stage1_deployment1_ret = dict(cacheClusterEnabled=False,
                              cacheClusterSize=0.5,
                              cacheClusterStatus='NOT_AVAILABLE',
                              createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                              deploymentId='kobnrb',
                              description=('{\n'
                                           '    "current_deployment_label": {\n'
                                           '        "api_name": "unit test api",\n'
                                           '        "swagger_file": "temp-swagger-sample.yaml",\n'
                                           '        "swagger_file_md5sum": "4fb17e43bab3a96e7f2410a1597cd0a5",\n'
                                           '        "swagger_info_object": {\n'
                                           '            "description": "salt boto apigateway unit test service",\n'
                                           '            "title": "salt boto apigateway unit test service",\n'
                                           '            "version": "0.0.0"\n'
                                           '        }\n'
                                           '    }\n'
                                           '}'),
                              lastUpdatedDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                              methodSettings=dict(),
                              stageName='test',
                              variables=dict())

stage1_deployment1_vars_ret = dict(cacheClusterEnabled=False,
                                   cacheClusterSize=0.5,
                                   cacheClusterStatus='NOT_AVAILABLE',
                                   createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                                   deploymentId='kobnrb',
                                   description=('{\n'
                                                '    "current_deployment_label": {\n'
                                                '        "api_name": "unit test api",\n'
                                                '        "swagger_file": "temp-swagger-sample.yaml",\n'
                                                '        "swagger_file_md5sum": "4fb17e43bab3a96e7f2410a1597cd0a5",\n'
                                                '        "swagger_info_object": {\n'
                                                '            "description": "salt boto apigateway unit test service",\n'
                                                '            "title": "salt boto apigateway unit test service",\n'
                                                '            "version": "0.0.0"\n'
                                                '        }\n'
                                                '    }\n'
                                                '}'),
                                   lastUpdatedDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                                   methodSettings=dict(),
                                   stageName='test',
                                   variables={'var1': 'val1'})

stage1_deployment2_ret = dict(cacheClusterEnabled=False,
                              cacheClusterSize=0.5,
                              cacheClusterStatus='NOT_AVAILABLE',
                              createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                              deploymentId='kobnrc',
                              description=('{\n'
                                           '    "current_deployment_label": {\n'
                                           '        "api_name": "unit test api",\n'
                                           '        "swagger_file": "temp-swagger-sample.yaml",\n'
                                           '        "swagger_file_md5sum": "5fd538c4336ed5c54b4bf39ddf97c661",\n'
                                           '        "swagger_info_object": {\n'
                                           '            "description": "salt boto apigateway unit test service",\n'
                                           '            "title": "salt boto apigateway unit test service",\n'
                                           '            "version": "0.0.2"\n'
                                           '        }\n'
                                           '    }\n'
                                           '}'),
                              lastUpdatedDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                              methodSettings=dict(),
                              stageName='test',
                              variables=dict())

stage2_ret = dict(cacheClusterEnabled=False,
                  cacheClusterSize=0.5,
                  cacheClusterStatus='NOT_AVAILABLE',
                  createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                  deploymentId='kobnrb',
                  description=('{\n'
                               '    "current_deployment_label": {\n'
                               '        "api_name": "unit test api",\n'
                               '        "swagger_file": "temp-swagger-sample.yaml",\n'
                               '        "swagger_file_md5sum": "4fb17e43bab3a96e7f2410a1597cd0a5",\n'
                               '        "swagger_info_object": {\n'
                               '            "description": "salt boto apigateway unit test service",\n'
                               '            "title": "salt boto apigateway unit test service",\n'
                               '            "version": "0.0.0"\n'
                               '        }\n'
                               '    }\n'
                               '}'),
                  lastUpdatedDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                  methodSettings=dict(),
                  stageName='dev',
                  variables=dict())

stages_stage2_ret = {'item': [stage2_ret]}

no_stages_ret = {'item': []}

deployment1_ret = dict(createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                       description=('{\n'
                                    '    "api_name": "unit test api",\n'
                                    '    "swagger_file": "temp-swagger-sample.yaml",\n'
                                    '    "swagger_file_md5sum": "55a948ff90ad80ff747ec91657c7a299",\n'
                                    '    "swagger_info_object": {\n'
                                    '        "description": "salt boto apigateway unit test service",\n'
                                    '        "title": "salt boto apigateway unit test service",\n'
                                    '        "version": "0.0.0"\n'
                                    '    }\n'
                                    '}'),
                       id='kobnrb')

deployment2_ret = dict(createdDate=datetime.datetime(2015, 11, 17, 16, 33, 50),
                       description=('{\n'
                                    '    "api_name": "unit test api",\n'
                                    '    "swagger_file": "temp-swagger-sample.yaml",\n'
                                    '    "swagger_file_md5sum": "5fd538c4336ed5c54b4bf39ddf97c661",\n'
                                    '    "swagger_info_object": {\n'
                                    '        "description": "salt boto apigateway unit test service",\n'
                                    '        "title": "salt boto apigateway unit test service",\n'
                                    '        "version": "0.0.2"\n'
                                    '    }\n'
                                    '}'),
                       id='kobnrc')

deployments_ret = {'items': [deployment1_ret, deployment2_ret]}

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
                                                       'description': 'Creates a new user.',
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
        with salt.utils.files.fopen(self.swaggerfile, 'w') as fp_:
            salt.utils.yaml.safe_dump(self.swaggerdict, fp_, default_flow_style=False)
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
            # set swagger version to an unsupported version 3.0
            self.swaggerdict['swagger'] = '3.0'
            # missing info object
            self.swaggerdict.pop('info', None)
        else:
            self.swaggerdict = TempSwaggerFile._tmp_swagger_dict


class BotoApiGatewayStateTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn = None

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        cls.opts['grains'] = salt.loader.grains(cls.opts)

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def setup_loader_modules(self):
        context = {}
        utils = salt.loader.utils(
            self.opts,
            whitelist=['boto', 'boto3', 'args', 'systemd', 'path', 'platform', 'reg'],
            context=context)
        serializers = salt.loader.serializers(self.opts)
        self.funcs = salt.loader.minion_mods(self.opts, context=context, utils=utils, whitelist=['boto_apigateway'])
        self.salt_states = salt.loader.states(opts=self.opts, functions=self.funcs, utils=utils, whitelist=['boto_apigateway'], serializers=serializers)
        return {
            boto_apigateway: {
                '__opts__': self.opts,
                '__utils__': utils,
                '__salt__': self.funcs,
                '__states__': self.salt_states,
                '__serializers__': serializers,
            }
        }

    # Set up MagicMock to replace the boto3 session
    def setUp(self):
        self.addCleanup(delattr, self, 'funcs')
        self.addCleanup(delattr, self, 'salt_states')
        # connections keep getting cached from prior tests, can't find the
        # correct context object to clear it. So randomize the cache key, to prevent any
        # cache hits
        conn_parameters['key'] = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(50))

        patcher = patch('boto3.session.Session')
        self.addCleanup(patcher.stop)
        mock_session = patcher.start()

        session_instance = mock_session.return_value
        self.conn = MagicMock()
        self.addCleanup(delattr, self, 'conn')
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
            result = self.salt_states['boto_apigateway.present'](
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
            result = self.salt_states['boto_apigateway.present'](
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
            result = self.salt_states['boto_apigateway.present'](
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
            result = self.salt_states['boto_apigateway.present'](
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
        with patch.dict(self.funcs, {'boto_lambda.describe_function': MagicMock(return_value={'function': function_ret})}):
            with TempSwaggerFile() as swagger_file:
                result = self.salt_states['boto_apigateway.present'](
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
            result = self.salt_states['boto_apigateway.present'](
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
            result = self.salt_states['boto_apigateway.present'](
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
            result = self.salt_states['boto_apigateway.present'](
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
        with patch.dict(self.funcs, {'boto_lambda.describe_function': MagicMock(return_value={'function': function_ret})}):
            with TempSwaggerFile() as swagger_file:
                result = self.salt_states['boto_apigateway.present'](
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
        with patch.dict(self.funcs, {'boto_lambda.describe_function': MagicMock(return_value={'error': 'no such lambda'})}):
            with TempSwaggerFile() as swagger_file:
                result = self.salt_states['boto_apigateway.present'](
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
        with patch.dict(self.funcs, {'boto_lambda.describe_function': MagicMock(return_value={'function': function_ret})}):
            with TempSwaggerFile() as swagger_file:
                result = self.salt_states['boto_apigateway.present'](
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
        with patch.dict(self.funcs, {'boto_lambda.describe_function': MagicMock(return_value={'function': function_ret})}):
            with TempSwaggerFile() as swagger_file:
                result = self.salt_states['boto_apigateway.present'](
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
        with patch.dict(self.funcs, {'boto_lambda.describe_function': MagicMock(return_value={'function': function_ret})}):
            with TempSwaggerFile() as swagger_file:
                result = self.salt_states['boto_apigateway.present'](
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

        result = self.salt_states['boto_apigateway.absent'](
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

        result = self.salt_states['boto_apigateway.absent'](
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

        result = self.salt_states['boto_apigateway.absent'](
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

        result = self.salt_states['boto_apigateway.absent'](
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

        result = self.salt_states['boto_apigateway.absent'](
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

        result = self.salt_states['boto_apigateway.absent'](
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

        result = self.salt_states['boto_apigateway.absent'](
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

    def test_usage_plan_present_if_describe_fails(self, *args):
        '''
        Tests correct error processing for describe_usage_plan failure
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'error': 'error'})}):
            result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'Failed to describe existing usage plans')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_present_if_there_is_no_such_plan_and_test_option_is_set(self, *args):
        '''
        TestCse for salt.modules.boto_apigateway state.module, checking that if __opts__['test'] is set
        and usage plan does not exist, correct diagnostic will be returned
        '''
        with patch.dict(boto_apigateway.__opts__, {'test': True}):
            with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': []})}):
                result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)
                self.assertIn('comment', result)
                self.assertEqual(result['comment'], 'a new usage plan plan_name would be created')
                self.assertIn('result', result)
                self.assertEqual(result['result'], None)

    def test_usage_plan_present_if_create_usage_plan_fails(self, *args):
        '''
        Tests behavior for the case when creating a new usage plan fails
        '''
        with patch.dict(boto_apigateway.__opts__, {'test': False}):
            with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': []}),
                                                       'boto_apigateway.create_usage_plan': MagicMock(return_value={'error': 'error'})}):
                result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

                self.assertIn('result', result)
                self.assertEqual(result['result'], False)
                self.assertIn('comment', result)
                self.assertEqual(result['comment'], 'Failed to create a usage plan plan_name, error')
                self.assertIn('changes', result)
                self.assertEqual(result['changes'], {})

    def test_usage_plan_present_if_plan_is_there_and_needs_no_updates(self, *args):
        '''
        Tests behavior for the case when plan is present and needs no updates
        '''
        with patch.dict(boto_apigateway.__opts__, {'test': False}):
            with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{
                                                                                                                'id': 'planid',
                                                                                                                'name': 'planname'
                                                                                                            }]}),
                                                       'boto_apigateway.update_usage_plan': MagicMock()}):
                result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

                self.assertIn('result', result)
                self.assertEqual(result['result'], True)
                self.assertIn('comment', result)
                self.assertEqual(result['comment'], 'usage plan plan_name is already in a correct state')
                self.assertIn('changes', result)
                self.assertEqual(result['changes'], {})

                self.assertTrue(boto_apigateway.__salt__['boto_apigateway.update_usage_plan'].call_count == 0)

    def test_usage_plan_present_if_plan_is_there_and_needs_updates_but_test_is_set(self, *args):
        '''
        Tests behavior when usage plan needs to be updated by tests option is set
        '''
        with patch.dict(boto_apigateway.__opts__, {'test': True}):
            with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{
                                                                                                                       'id': 'planid',
                                                                                                                       'name': 'planname',
                                                                                                                       'throttle': {'rateLimit': 10.0}
                                                                                                                   }]}),
                                                       'boto_apigateway.update_usage_plan': MagicMock()}):
                result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

                self.assertIn('comment', result)
                self.assertEqual(result['comment'], 'a new usage plan plan_name would be updated')
                self.assertIn('result', result)
                self.assertEqual(result['result'], None)
                self.assertTrue(boto_apigateway.__salt__['boto_apigateway.update_usage_plan'].call_count == 0)

    def test_usage_plan_present_if_plan_is_there_and_needs_updates_but_update_fails(self, *args):
        '''
        Tests error processing for the case when updating an existing usage plan fails
        '''
        with patch.dict(boto_apigateway.__opts__, {'test': False}):
            with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{
                                                                                                                       'id': 'planid',
                                                                                                                       'name': 'planname',
                                                                                                                       'throttle': {'rateLimit': 10.0}
                                                                                                                   }]}),
                                                       'boto_apigateway.update_usage_plan': MagicMock(return_value={'error': 'error'})}):
                result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

                self.assertIn('result', result)
                self.assertEqual(result['result'], False)
                self.assertIn('comment', result)
                self.assertEqual(result['comment'], 'Failed to update a usage plan plan_name, error')

    def test_usage_plan_present_if_plan_has_been_created(self, *args):
        '''
        Tests successful case for creating a new usage plan
        '''
        with patch.dict(boto_apigateway.__opts__, {'test': False}):
            with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=[{'plans': []}, {'plans': [{'id': 'id'}]}]),
                                                       'boto_apigateway.create_usage_plan': MagicMock(return_value={'created': True})}):
                result = boto_apigateway.usage_plan_present('name', 'plan_name', **conn_parameters)

                self.assertIn('result', result)
                self.assertEqual(result['result'], True)
                self.assertIn('comment', result)
                self.assertEqual(result['comment'], 'A new usage plan plan_name has been created')
                self.assertEqual(result['changes']['old'], {'plan': None})
                self.assertEqual(result['changes']['new'], {'plan': {'id': 'id'}})

    def test_usage_plan_present_if_plan_has_been_updated(self, *args):
        '''
        Tests successful case for updating a usage plan
        '''
        with patch.dict(boto_apigateway.__opts__, {'test': False}):
            with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=[{'plans': [{'id': 'id'}]},
                                                                                                                      {'plans': [{'id': 'id',
                                                                                                                                  'throttle': {'rateLimit': throttle_rateLimit}}]}]),
                                                       'boto_apigateway.update_usage_plan': MagicMock(return_value={'updated': True})}):
                result = boto_apigateway.usage_plan_present('name', 'plan_name', throttle={'rateLimit': throttle_rateLimit}, **conn_parameters)

                self.assertIn('result', result)
                self.assertEqual(result['result'], True)
                self.assertIn('comment', result)
                self.assertEqual(result['comment'], 'usage plan plan_name has been updated')
                self.assertEqual(result['changes']['old'], {'plan': {'id': 'id'}})
                self.assertEqual(result['changes']['new'], {'plan': {'id': 'id', 'throttle': {'rateLimit': throttle_rateLimit}}})

    def test_usage_plan_present_if_ValueError_is_raised(self, *args):
        '''
        Tests error processing for the case when ValueError is raised when creating a usage plan
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=ValueError('error'))}):
            result = boto_apigateway.usage_plan_present('name', 'plan_name', throttle={'rateLimit': throttle_rateLimit}, **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], repr(('error',)))

    def test_usage_plan_present_if_IOError_is_raised(self, *args):
        '''
        Tests error processing for the case when IOError is raised when creating a usage plan
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=IOError('error'))}):
            result = boto_apigateway.usage_plan_present('name', 'plan_name', throttle={'rateLimit': throttle_rateLimit}, **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], repr(('error',)))

    def test_usage_plan_absent_if_describe_fails(self, *args):
        '''
        Tests correct error processing for describe_usage_plan failure
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'error': 'error'})}):
            result = {}

            result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'Failed to describe existing usage plans')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_absent_if_plan_is_not_present(self, *args):
        '''
        Tests behavior for the case when the plan that needs to be absent does not exist
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': []})}):
            result = {}

            result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], True)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'Usage plan plan_name does not exist already')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_absent_if_plan_is_present_but_test_option_is_set(self, *args):
        '''
        Tests behavior for the case when usage plan needs to be deleted by tests option is set
        '''
        with patch.dict(boto_apigateway.__opts__, {'test': True}):
            with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id'}]})}):
                result = {}

                result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

                self.assertIn('result', result)
                self.assertEqual(result['result'], None)
                self.assertIn('comment', result)
                self.assertEqual(result['comment'], 'Usage plan plan_name exists and would be deleted')
                self.assertIn('changes', result)
                self.assertEqual(result['changes'], {})

    def test_usage_plan_absent_if_plan_is_present_but_delete_fails(self, *args):
        '''
        Tests correct error processing when deleting a usage plan fails
        '''
        with patch.dict(boto_apigateway.__opts__, {'test': False}):
            with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id'}]}),
                                                       'boto_apigateway.delete_usage_plan': MagicMock(return_value={'error': 'error'})}):
                result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

                self.assertIn('result', result)
                self.assertEqual(result['result'], False)
                self.assertIn('comment', result)
                self.assertEqual(result['comment'], 'Failed to delete usage plan plan_name, ' + repr({'error': 'error'}))
                self.assertIn('changes', result)
                self.assertEqual(result['changes'], {})

    def test_usage_plan_absent_if_plan_has_been_deleted(self, *args):
        '''
        Tests successful case for deleting a usage plan
        '''
        with patch.dict(boto_apigateway.__opts__, {'test': False}):
            with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id'}]}),
                                                       'boto_apigateway.delete_usage_plan': MagicMock(return_value={'deleted': True})}):
                result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

                self.assertIn('result', result)
                self.assertEqual(result['result'], True)
                self.assertIn('comment', result)
                self.assertEqual(result['comment'], 'Usage plan plan_name has been deleted')
                self.assertIn('changes', result)
                self.assertEqual(result['changes'], {'new': {'plan': None}, 'old': {'plan': {'id': 'id'}}})

    def test_usage_plan_absent_if_ValueError_is_raised(self, *args):
        '''
        Tests correct error processing for the case when ValueError is raised when deleting a usage plan
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=ValueError('error'))}):
            result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], repr(('error',)))

    def test_usage_plan_absent_if_IOError_is_raised(self, *args):
        '''
        Tests correct error processing for the case when IOError is raised when deleting a usage plan
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=IOError('error'))}):
            result = boto_apigateway.usage_plan_absent('name', 'plan_name', **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], repr(('error',)))


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

    def test_usage_plan_association_present_if_describe_fails(self, *args):
        '''
        Tests correct error processing for describe_usage_plan failure
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'error': 'error'})}):
            result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_1], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'Failed to describe existing usage plans')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_present_if_plan_is_not_present(self, *args):
        '''
        Tests correct error processing if a plan for which association has been requested is not present
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': []})}):
            result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_1], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'Usage plan plan_name does not exist')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_present_if_multiple_plans_with_the_same_name_exist(self, *args):
        '''
        Tests correct error processing for the case when multiple plans with the same name exist
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1'},
                                                                                                                  {'id': 'id2'}]})}):
            result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_1], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'There are multiple usage plans with the same name - it is not supported')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_present_if_association_already_exists(self, *args):
        '''
        Tests the behavior for the case when requested association is already present
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1',
                                                                                                                              'apiStages':
                                                                                                                              [association_stage_1]}]})}):
            result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_1], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], True)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'Usage plan is already asssociated to all api stages')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_present_if_update_fails(self, *args):
        '''
        Tests correct error processing for the case when adding associations fails
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1',
                                                                                                                              'apiStages':
                                                                                                                                [association_stage_1]}]}),
                                                   'boto_apigateway.attach_usage_plan_to_apis': MagicMock(return_value={'error': 'error'})}):
            result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_2], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertTrue(result['comment'].startswith('Failed to associate a usage plan'))
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_present_success(self, *args):
        '''
        Tests successful case for adding usage plan associations to a given api stage
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1',
                                                                                                                              'apiStages':
                                                                                                                                [association_stage_1]}]}),
                                                   'boto_apigateway.attach_usage_plan_to_apis': MagicMock(return_value={'result': {'apiStages': [association_stage_1,
                                                                                                                                                 association_stage_2]}})}):
            result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [association_stage_2], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], True)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'successfully associated usage plan to apis')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {'new': [association_stage_1, association_stage_2], 'old': [association_stage_1]})

    def test_usage_plan_association_present_if_value_error_is_thrown(self, *args):
        '''
        Tests correct error processing for the case when IOError is raised while trying to set usage plan associations
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=ValueError('error'))}):
            result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], repr(('error',)))
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_present_if_io_error_is_thrown(self, *args):
        '''
        Tests correct error processing for the case when IOError is raised while trying to set usage plan associations
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=IOError('error'))}):
            result = boto_apigateway.usage_plan_association_present('name', 'plan_name', [], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], repr(('error',)))
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_absent_if_describe_fails(self, *args):
        '''
        Tests correct error processing for describe_usage_plan failure
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'error': 'error'})}):
            result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)
            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'Failed to describe existing usage plans')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_absent_if_plan_is_not_present(self, *args):
        '''
        Tests error processing for the case when plan for which associations need to be modified is not present
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': []})}):
            result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'Usage plan plan_name does not exist')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_absent_if_multiple_plans_with_the_same_name_exist(self, *args):
        '''
        Tests the case when there are multiple plans with the same name but different Ids
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1'},
                                                                                                                             {'id': 'id2'}]})}):
            result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'There are multiple usage plans with the same name - it is not supported')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_absent_if_plan_has_no_associations(self, *args):
        '''
        Tests the case when the plan has no associations at all
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1', 'apiStages': []}]})}):
            result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], True)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'Usage plan plan_name has no associated stages already')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_absent_if_plan_has_no_specific_association(self, *args):
        '''
        Tests the case when requested association is not present already
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1', 'apiStages': [association_stage_1]}]})}):
            result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_2], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], True)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'Usage plan is already not asssociated to any api stages')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_absent_if_detaching_association_fails(self, *args):
        '''
        Tests correct error processing when detaching the usage plan from the api function is called
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1', 'apiStages': [association_stage_1,
                                                                                                                                                         association_stage_2]}]}),
                                                   'boto_apigateway.detach_usage_plan_from_apis': MagicMock(return_value={'error': 'error'})}):
            result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_2], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertTrue(result['comment'].startswith('Failed to disassociate a usage plan plan_name from the apis'))
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_absent_success(self, *args):
        '''
        Tests successful case of disaccosiation the usage plan from api stages
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(return_value={'plans': [{'id': 'id1', 'apiStages': [association_stage_1,
                                                                                                                                                         association_stage_2]}]}),
                                                   'boto_apigateway.detach_usage_plan_from_apis': MagicMock(return_value={'result': {'apiStages': [association_stage_1]}})}):
            result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_2], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], True)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], 'successfully disassociated usage plan from apis')
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {'new': [association_stage_1], 'old': [association_stage_1, association_stage_2]})

    def test_usage_plan_association_absent_if_ValueError_is_raised(self, *args):
        '''
        Tests correct error processing for the case where ValueError is raised while trying to remove plan associations
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=ValueError('error'))}):
            result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], repr(('error',)))
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})

    def test_usage_plan_association_absent_if_IOError_is_raised(self, *args):
        '''
        Tests correct error processing for the case where IOError exception is raised while trying to remove plan associations
        '''
        with patch.dict(boto_apigateway.__salt__, {'boto_apigateway.describe_usage_plans': MagicMock(side_effect=IOError('error'))}):
            result = boto_apigateway.usage_plan_association_absent('name', 'plan_name', [association_stage_1], **conn_parameters)

            self.assertIn('result', result)
            self.assertEqual(result['result'], False)
            self.assertIn('comment', result)
            self.assertEqual(result['comment'], repr(('error',)))
            self.assertIn('changes', result)
            self.assertEqual(result['changes'], {})
