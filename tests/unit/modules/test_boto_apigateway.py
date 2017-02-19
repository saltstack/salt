# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import datetime
import logging
import random
import string

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import Salt libs
import salt.loader
from salt.modules import boto_apigateway
from salt.utils.versions import LooseVersion

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module
try:
    import boto3
    import botocore
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from salt.ext.six.moves import range, zip

# pylint: enable=import-error,no-name-in-module

# the boto_lambda module relies on the connect_to_region() method
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

api_key_ret = {
            u'description': u'test-lambda-api-key', u'enabled': True,
            u'stageKeys': [u'123yd1l123/test'],
            u'lastUpdatedDate': datetime.datetime(2015, 11, 4, 19, 22, 18),
            u'createdDate': datetime.datetime(2015, 11, 4, 19, 21, 7),
            u'id': u'88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
            u'name': u'test-salt-key',
            'ResponseMetadata': {'HTTPStatusCode': 200,
                                 'RequestId': '7cc233dd-9dc8-11e5-ba47-1b7350cc2757'}}

api_model_error_schema = u'{"properties":{"code":{"type":"integer","format":"int32"},"message":{"type":"string"},"fields":{"type":"string"}},"definitions":{}}'
api_model_ret = {
            u'contentType': u'application/json',
            u'name': u'Error',
            u'description': u'Error Model',
            u'id': u'iltqcb',
            u'schema': api_model_error_schema,
            'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}

api_resources_ret = {
            u'items': [{u'id': u'hhg2t8f4h9',
                        u'path': u'/'},
                       {u'id': u'isr8q2',
                        u'parentId': u'hhg2t8f4h9',
                        u'path': u'/api',
                        u'pathPart': u'api'},
                       {u'id': u'5pvx7w',
                        u'parentId': 'isr8q2',
                        u'path': u'/api/users',
                        u'pathPart': u'users',
                        u'resourceMethods': {u'OPTIONS': {},
                                             u'POST': {}}}],
            'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}

api_create_resource_ret = {
            u'id': u'123abc',
            u'parentId': u'hhg2t8f4h9',
            u'path': u'/api3',
            u'pathPart': u'api3',
            'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}

usage_plan1 = dict(
    id='plan1_id',
    name='plan1_name',
    description='plan1_desc',
    apiStages=[],
    throttle=dict(
        burstLimit=123,
        rateLimit=123.0
    ),
    quota=dict(
        limit=123,
        offset=123,
        period='DAY'
    )
)
usage_plan2 = dict(
    id='plan2_id',
    name='plan2_name',
    description='plan2_desc',
    apiStages=[],
    throttle=dict(
        burstLimit=123,
        rateLimit=123.0
    ),
    quota=dict(
        limit=123,
        offset=123,
        period='DAY'
    )
)
usage_plan1b = dict(
    id='another_plan1_id',
    name='plan1_name',
    description='another_plan1_desc',
    apiStages=[],
    throttle=dict(
        burstLimit=123,
        rateLimit=123.0
    ),
    quota=dict(
        limit=123,
        offset=123,
        period='DAY'
    )
)
usage_plans_ret = dict(
    items=[
        usage_plan1, usage_plan2, usage_plan1b
    ]
)

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


class BotoApiGatewayTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn = None

    loader_module = boto_apigateway

    def loader_module_globals(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS
        utils = salt.loader.utils(opts, whitelist=['boto3'])
        return {
            '__opts__': opts,
            '__utils__': utils,
        }

    def setUp(self):
        TestCase.setUp(self)
        # __virtual__ must be caller in order for _get_conn to be injected
        boto_apigateway.__init__(self.opts)
        delattr(self, 'opts')

        # Set up MagicMock to replace the boto3 session
        # connections keep getting cached from prior tests, can't find the
        # correct context object to clear it. So randomize the cache key, to prevent any
        # cache hits
        conn_parameters['key'] = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(50))

        self.patcher = patch('boto3.session.Session')
        self.addCleanup(self.patcher.stop)
        self.addCleanup(delattr, self, 'patcher')
        mock_session = self.patcher.start()

        session_instance = mock_session.return_value
        self.conn = MagicMock()
        session_instance.client.return_value = self.conn
        self.addCleanup(delattr, self, 'conn')


class BotoApiGatewayTestCaseMixin(object):
    def _diff_list_dicts(self, listdict1, listdict2, sortkey):
        '''
        Compares the two list of dictionaries to ensure they have same content.  Returns True
        if there is difference, else False
        '''
        if len(listdict1) != len(listdict2):
            return True

        listdict1_sorted = sorted(listdict1, key=lambda x: x[sortkey])
        listdict2_sorted = sorted(listdict2, key=lambda x: x[sortkey])
        for item1, item2 in zip(listdict1_sorted, listdict2_sorted):
            if len(set(item1) & set(item2)) != len(set(item2)):
                return True
        return False


#@skipIf(True, 'Skip these tests while investigating failures')
@skipIf(HAS_BOTO is False, 'The boto3 module must be installed.')
@skipIf(_has_required_boto() is False,
        'The boto3 module must be greater than'
        ' or equal to version {0}'.format(required_boto3_version))
@skipIf(_has_required_botocore() is False,
        'The botocore module must be greater than'
        ' or equal to version {0}'.format(required_botocore_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoApiGatewayTestCase(BotoApiGatewayTestCaseBase, BotoApiGatewayTestCaseMixin):
    '''
    TestCase for salt.modules.boto_apigateway module
    '''

    def test_that_when_checking_if_a_rest_api_exists_and_a_rest_api_exists_the_api_exists_method_returns_true(self):
        '''
        Tests checking an apigateway rest api existence when api's name exists
        '''
        self.conn.get_rest_apis.return_value = {'items': [{'name': 'myapi', 'id': '1234def'}]}
        api_exists_result = boto_apigateway.api_exists(name='myapi', **conn_parameters)

        self.assertTrue(api_exists_result['exists'])

    def test_that_when_checking_if_a_rest_api_exists_and_multiple_rest_api_exist_the_api_exists_method_returns_true(self):
        '''
        Tests checking an apigateway rest api existence when multiple api's with same name exists
        '''
        self.conn.get_rest_apis.return_value = {'items': [{'name': 'myapi', 'id': '1234abc'},
                                                          {'name': 'myapi', 'id': '1234def'}]}
        api_exists_result = boto_apigateway.api_exists(name='myapi', **conn_parameters)
        self.assertTrue(api_exists_result['exists'])

    def test_that_when_checking_if_a_rest_api_exists_and_no_rest_api_exists_the_api_exists_method_returns_false(self):
        '''
        Tests checking an apigateway rest api existence when no matching rest api name exists
        '''
        self.conn.get_rest_apis.return_value = {'items': [{'name': 'myapi', 'id': '1234abc'},
                                                          {'name': 'myapi', 'id': '1234def'}]}
        api_exists_result = boto_apigateway.api_exists(name='myapi123', **conn_parameters)
        self.assertFalse(api_exists_result['exists'])

    def test_that_when_describing_rest_apis_and_no_name_given_the_describe_apis_method_returns_list_of_all_rest_apis(self):
        '''
        Tests that all rest apis defined for a region is returned
        '''
        self.conn.get_rest_apis.return_value = {u'items': [{u'description': u'A sample API that uses a petstore as an example to demonstrate features in the swagger-2.0 specification',
                                                            u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                                            u'id': u'2ut6i4vyle',
                                                            u'name': u'Swagger Petstore'},
                                                           {u'description': u'testingabcd',
                                                            u'createdDate': datetime.datetime(2015, 12, 3, 21, 57, 58),
                                                            u'id': u'g41ls77hz0',
                                                            u'name': u'testingabc'},
                                                           {u'description': u'a simple food delivery service test',
                                                            u'createdDate': datetime.datetime(2015, 11, 4, 23, 57, 28),
                                                            u'id': u'h7pbwydho9',
                                                            u'name': u'Food Delivery Service'},
                                                           {u'description': u'Created by AWS Lambda',
                                                            u'createdDate': datetime.datetime(2015, 11, 4, 17, 55, 41),
                                                            u'id': u'i2yyd1ldvj',
                                                            u'name': u'LambdaMicroservice'},
                                                           {u'description': u'cloud tap service with combination of API GW and Lambda',
                                                            u'createdDate': datetime.datetime(2015, 11, 17, 22, 3, 18),
                                                            u'id': u'rm06h9oac4',
                                                            u'name': u'API Gateway Cloudtap Service'},
                                                           {u'description': u'testing1234',
                                                            u'createdDate': datetime.datetime(2015, 12, 2, 19, 51, 44),
                                                            u'id': u'vtir6ssxvd',
                                                            u'name': u'testing123'}],
                                                'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        items = self.conn.get_rest_apis.return_value['items']
        get_apis_result = boto_apigateway.describe_apis(**conn_parameters)
        items_dt = [boto_apigateway._convert_datetime_str(item) for item in items]
        apis = get_apis_result.get('restapi')

        diff = self._diff_list_dicts(apis, items_dt, 'id')

        self.assertTrue(apis)
        self.assertEqual(len(apis), len(items))
        self.assertFalse(diff)

    def test_that_when_describing_rest_apis_and_name_is_testing123_the_describe_apis_method_returns_list_of_two_rest_apis(self):
        '''
        Tests that exactly 2 apis are returned matching 'testing123'
        '''
        self.conn.get_rest_apis.return_value = {u'items': [{u'description': u'A sample API that uses a petstore as an example to demonstrate features in the swagger-2.0 specification',
                                                            u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                                            u'id': u'2ut6i4vyle',
                                                            u'name': u'Swagger Petstore'},
                                                           {u'description': u'testingabcd',
                                                            u'createdDate': datetime.datetime(2015, 12, 3, 21, 57, 58),
                                                            u'id': u'g41ls77hz0',
                                                            u'name': u'testing123'},
                                                           {u'description': u'a simple food delivery service test',
                                                            u'createdDate': datetime.datetime(2015, 11, 4, 23, 57, 28),
                                                            u'id': u'h7pbwydho9',
                                                            u'name': u'Food Delivery Service'},
                                                           {u'description': u'Created by AWS Lambda',
                                                            u'createdDate': datetime.datetime(2015, 11, 4, 17, 55, 41),
                                                            u'id': u'i2yyd1ldvj',
                                                            u'name': u'LambdaMicroservice'},
                                                           {u'description': u'cloud tap service with combination of API GW and Lambda',
                                                            u'createdDate': datetime.datetime(2015, 11, 17, 22, 3, 18),
                                                            u'id': u'rm06h9oac4',
                                                            u'name': u'API Gateway Cloudtap Service'},
                                                           {u'description': u'testing1234',
                                                            u'createdDate': datetime.datetime(2015, 12, 2, 19, 51, 44),
                                                            u'id': u'vtir6ssxvd',
                                                            u'name': u'testing123'}],
                                                'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        expected_items = [{u'description': u'testingabcd', u'createdDate': datetime.datetime(2015, 12, 3, 21, 57, 58),
                           u'id': u'g41ls77hz0', u'name': u'testing123'},
                          {u'description': u'testing1234', u'createdDate': datetime.datetime(2015, 12, 2, 19, 51, 44),
                           u'id': u'vtir6ssxvd', u'name': u'testing123'}]

        get_apis_result = boto_apigateway.describe_apis(name='testing123', **conn_parameters)
        expected_items_dt = [boto_apigateway._convert_datetime_str(item) for item in expected_items]
        apis = get_apis_result.get('restapi')
        diff = self._diff_list_dicts(apis, expected_items_dt, 'id')

        self.assertTrue(apis)
        self.assertIs(diff, False)

    def test_that_when_describing_rest_apis_and_name_is_testing123_the_describe_apis_method_returns_no_matching_items(self):
        '''
        Tests that no apis are returned matching 'testing123'
        '''
        self.conn.get_rest_apis.return_value = {u'items': [{u'description': u'A sample API that uses a petstore as an example to demonstrate features in the swagger-2.0 specification',
                                                            u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                                            u'id': u'2ut6i4vyle',
                                                            u'name': u'Swagger Petstore'},
                                                           {u'description': u'a simple food delivery service test',
                                                            u'createdDate': datetime.datetime(2015, 11, 4, 23, 57, 28),
                                                            u'id': u'h7pbwydho9',
                                                            u'name': u'Food Delivery Service'},
                                                           {u'description': u'Created by AWS Lambda',
                                                            u'createdDate': datetime.datetime(2015, 11, 4, 17, 55, 41),
                                                            u'id': u'i2yyd1ldvj',
                                                            u'name': u'LambdaMicroservice'},
                                                           {u'description': u'cloud tap service with combination of API GW and Lambda',
                                                            u'createdDate': datetime.datetime(2015, 11, 17, 22, 3, 18),
                                                            u'id': u'rm06h9oac4',
                                                            u'name': u'API Gateway Cloudtap Service'}],
                                                'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        get_apis_result = boto_apigateway.describe_apis(name='testing123', **conn_parameters)
        apis = get_apis_result.get('restapi')
        self.assertFalse(apis)

    def test_that_when_creating_a_rest_api_succeeds_the_create_api_method_returns_true(self):
        '''
        test True if rest api is created
        '''
        created_date = datetime.datetime.now()
        assigned_api_id = 'created_api_id'
        self.conn.create_rest_api.return_value = {u'description': u'unit-testing1234',
                                                  u'createdDate': created_date,
                                                  u'id': assigned_api_id,
                                                  u'name': u'unit-testing123',
                                                  'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}

        create_api_result = boto_apigateway.create_api(name='unit-testing123', description='unit-testing1234', **conn_parameters)
        api = create_api_result.get('restapi')
        self.assertTrue(create_api_result.get('created'))
        self.assertTrue(api)
        self.assertEqual(api['id'], assigned_api_id)
        self.assertEqual(api['createdDate'], '{0}'.format(created_date))
        self.assertEqual(api['name'], 'unit-testing123')
        self.assertEqual(api['description'], 'unit-testing1234')

    def test_that_when_creating_a_rest_api_fails_the_create_api_method_returns_error(self):
        '''
        test True for rest api creation error.
        '''
        self.conn.create_rest_api.side_effect = ClientError(error_content, 'create_rest_api')
        create_api_result = boto_apigateway.create_api(name='unit-testing123', description='unit-testing1234', **conn_parameters)
        api = create_api_result.get('restapi')
        self.assertEqual(create_api_result.get('error').get('message'), error_message.format('create_rest_api'))

    def test_that_when_deleting_rest_apis_and_name_is_testing123_matching_two_apis_the_delete_api_method_returns_delete_count_of_two(self):
        '''
        test True if the deleted count for "testing123" api is 2.
        '''
        self.conn.get_rest_apis.return_value = {u'items': [{u'description': u'A sample API that uses a petstore as an example to demonstrate features in the swagger-2.0 specification',
                                                            u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                                            u'id': u'2ut6i4vyle',
                                                            u'name': u'Swagger Petstore'},
                                                           {u'description': u'testingabcd',
                                                            u'createdDate': datetime.datetime(2015, 12, 3, 21, 57, 58),
                                                            u'id': u'g41ls77hz0',
                                                            u'name': u'testing123'},
                                                           {u'description': u'a simple food delivery service test',
                                                            u'createdDate': datetime.datetime(2015, 11, 4, 23, 57, 28),
                                                            u'id': u'h7pbwydho9',
                                                            u'name': u'Food Delivery Service'},
                                                           {u'description': u'Created by AWS Lambda',
                                                            u'createdDate': datetime.datetime(2015, 11, 4, 17, 55, 41),
                                                            u'id': u'i2yyd1ldvj',
                                                            u'name': u'LambdaMicroservice'},
                                                           {u'description': u'cloud tap service with combination of API GW and Lambda',
                                                            u'createdDate': datetime.datetime(2015, 11, 17, 22, 3, 18),
                                                            u'id': u'rm06h9oac4',
                                                            u'name': u'API Gateway Cloudtap Service'},
                                                           {u'description': u'testing1234',
                                                            u'createdDate': datetime.datetime(2015, 12, 2, 19, 51, 44),
                                                            u'id': u'vtir6ssxvd',
                                                            u'name': u'testing123'}],
                                                'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        self.conn.delete_rest_api.return_value = None
        delete_api_result = boto_apigateway.delete_api(name='testing123', **conn_parameters)

        self.assertTrue(delete_api_result.get('deleted'))
        self.assertEqual(delete_api_result.get('count'), 2)

    def test_that_when_deleting_rest_apis_and_name_given_provides_no_match_the_delete_api_method_returns_false(self):
        '''
        Test that the given api name doesn't exists, and delete_api should return deleted status of False
        '''
        self.conn.get_rest_apis.return_value = {u'items': [{u'description': u'testing1234',
                                                            u'createdDate': datetime.datetime(2015, 12, 2, 19, 51, 44),
                                                            u'id': u'vtir6ssxvd',
                                                            u'name': u'testing1234'}],
                                                'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        self.conn.delete_rest_api.return_value = None
        delete_api_result = boto_apigateway.delete_api(name='testing123', **conn_parameters)

        self.assertFalse(delete_api_result.get('deleted'))

    def test_that_describing_api_keys_the_describe_api_keys_method_returns_all_api_keys(self):
        '''
        tests True if all api_keys are returned.
        '''
        self.conn.get_api_keys.return_value = {
            u'items': [{u'description': u'test-lambda-api-key', u'enabled': True,
                        u'stageKeys': [u'123yd1l123/test'],
                        u'lastUpdatedDate': datetime.datetime(2015, 11, 4, 19, 22, 18),
                        u'createdDate': datetime.datetime(2015, 11, 4, 19, 21, 7),
                        u'id': u'88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                        u'name': u'test-salt-key'},
                       {u'description': u'testing_salt_123', u'enabled': True,
                        u'stageKeys': [],
                        u'lastUpdatedDate': datetime.datetime(2015, 12, 5, 0, 14, 49),
                        u'createdDate': datetime.datetime(2015, 12, 4, 22, 29, 33),
                        u'id': u'999999989b8cNSp4505pL6OgDe3oW7oY29Z3eIZ4',
                        u'name': u'testing_salt'}],
            'ResponseMetadata': {'HTTPStatusCode': 200,
                                 'RequestId': '7cc233dd-9dc8-11e5-ba47-1b7350cc2757'}}

        items = self.conn.get_api_keys.return_value['items']
        get_api_keys_result = boto_apigateway.describe_api_keys(**conn_parameters)
        items_dt = [boto_apigateway._convert_datetime_str(item) for item in items]
        api_keys = get_api_keys_result.get('apiKeys')

        diff = False
        if len(api_keys) != len(items):
            diff = True
        else:
            # compare individual items.
            diff = self._diff_list_dicts(api_keys, items_dt, 'id')

        self.assertTrue(api_keys)
        self.assertIs(diff, False)

    def test_that_describing_api_keys_fails_the_desribe_api_keys_method_returns_error(self):
        '''
        test True for describe api keys error.
        '''
        self.conn.get_api_keys.side_effect = ClientError(error_content, 'get_api_keys')
        result = boto_apigateway.describe_api_keys(**conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('get_api_keys'))

    def test_that_describing_an_api_key_the_describe_api_key_method_returns_matching_api_key(self):
        '''
        tests True if the key is found.
        '''
        self.conn.get_api_key.return_value = api_key_ret
        result = boto_apigateway.describe_api_key(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                  **conn_parameters)
        self.assertEqual(result.get('apiKey', {}).get('id'), self.conn.get_api_key.return_value.get('id'))

    def test_that_describing_an_api_key_that_does_not_exists_the_desribe_api_key_method_returns_error(self):
        '''
        test True for error being thrown.
        '''
        self.conn.get_api_key.side_effect = ClientError(error_content, 'get_api_keys')
        result = boto_apigateway.describe_api_key(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                  **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('get_api_keys'))

    def test_that_when_creating_an_api_key_succeeds_the_create_api_key_method_returns_true(self):
        '''
        tests that we can successfully create an api key and the createDat and lastUpdateDate are
        converted to string
        '''
        now = datetime.datetime.now()
        self.conn.create_api_key.return_value = {
            u'description': u'test-lambda-api-key', u'enabled': True,
            u'stageKeys': [u'123yd1l123/test'],
            u'lastUpdatedDate': now,
            u'createdDate': now,
            u'id': u'88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
            u'name': u'test-salt-key',
            'ResponseMetadata': {'HTTPStatusCode': 200,
                                 'RequestId': '7cc233dd-9dc8-11e5-ba47-1b7350cc2757'}}

        create_api_key_result = boto_apigateway.create_api_key('test-salt-key', 'test-lambda-api-key', **conn_parameters)
        api_key = create_api_key_result.get('apiKey')
        now_str = '{0}'.format(now)

        self.assertTrue(create_api_key_result.get('created'))
        self.assertEqual(api_key.get('lastUpdatedDate'), now_str)
        self.assertEqual(api_key.get('createdDate'), now_str)

    def test_that_when_creating_an_api_key_fails_the_create_api_key_method_returns_error(self):
        '''
        tests that we properly handle errors when create an api key fails.
        '''

        self.conn.create_api_key.side_effect = ClientError(error_content, 'create_api_key')
        create_api_key_result = boto_apigateway.create_api_key('test-salt-key', 'unit-testing1234')
        api_key = create_api_key_result.get('apiKey')

        self.assertFalse(api_key)
        self.assertIs(create_api_key_result.get('created'), False)
        self.assertEqual(create_api_key_result.get('error').get('message'), error_message.format('create_api_key'))

    def test_that_when_deleting_an_api_key_that_exists_the_delete_api_key_method_returns_true(self):
        '''
        test True if the api key is successfully deleted.
        '''
        self.conn.delete_api_key.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.delete_api_key(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2', **conn_parameters)

        self.assertTrue(result.get('deleted'))

    def test_that_when_deleting_an_api_key_that_does_not_exist_the_delete_api_key_method_returns_false(self):
        '''
        Test that the given api key doesn't exists, and delete_api_key should return deleted status of False
        '''
        self.conn.delete_api_key.side_effect = ClientError(error_content, 'delete_api_key')
        result = boto_apigateway.delete_api_key(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2', **conn_parameters)

        self.assertFalse(result.get('deleted'))

    def test_that_when_updating_an_api_key_description_successfully_the_update_api_key_description_method_returns_true(self):
        '''
        Test True if api key descriptipn update is successful
        '''
        self.conn.update_api_key.return_value = api_key_ret
        result = boto_apigateway.update_api_key_description(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                            description='test-lambda-api-key', **conn_parameters)
        self.assertTrue(result.get('updated'))

    def test_that_when_updating_an_api_key_description_for_a_key_that_does_not_exist_the_update_api_key_description_method_returns_false(self):
        '''
        Test False if api key doesn't exists for the update request
        '''
        self.conn.update_api_key.side_effect = ClientError(error_content, 'update_api_key')
        result = boto_apigateway.update_api_key_description(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                            description='test-lambda-api-key', **conn_parameters)
        self.assertFalse(result.get('updated'))

    def test_that_when_enabling_an_api_key_that_exists_the_enable_api_key_method_returns_api_key(self):
        '''
        Test True for the status of the enabled flag of the returned api key
        '''
        self.conn.update_api_key.return_value = api_key_ret
        result = boto_apigateway.enable_api_key(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                **conn_parameters)
        self.assertTrue(result.get('apiKey', {}).get('enabled'))

    def test_that_when_enabling_an_api_key_that_does_not_exist_the_enable_api_key_method_returns_error(self):
        '''
        Test Equality of the returned value of 'erorr'
        '''
        self.conn.update_api_key.side_effect = ClientError(error_content, 'update_api_key')
        result = boto_apigateway.enable_api_key(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('update_api_key'))

    def test_that_when_disabling_an_api_key_that_exists_the_disable_api_key_method_returns_api_key(self):
        '''
        Test False for the status of the enabled flag of the returned api key
        '''
        self.conn.update_api_key.return_value = api_key_ret.copy()
        self.conn.update_api_key.return_value['enabled'] = False
        result = boto_apigateway.disable_api_key(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                 **conn_parameters)
        self.assertFalse(result.get('apiKey', {}).get('enabled'))

    def test_that_when_disabling_an_api_key_that_does_not_exist_the_disable_api_key_method_returns_error(self):
        '''
        Test Equality of the returned value of 'erorr'
        '''
        self.conn.update_api_key.side_effect = ClientError(error_content, 'update_api_key')
        result = boto_apigateway.disable_api_key(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                 **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('update_api_key'))

    def test_that_when_associating_stages_to_an_api_key_that_exists_the_associate_api_key_stagekeys_method_returns_true(self):
        '''
        Test True for returned value of 'associated'
        '''
        self.conn.update_api_key.retuen_value = api_key_ret
        result = boto_apigateway.associate_api_key_stagekeys(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                             stagekeyslist=[u'123yd1l123/test'],
                                                             **conn_parameters)
        self.assertTrue(result.get('associated'))

    def test_that_when_associating_stages_to_an_api_key_that_does_not_exist_the_associate_api_key_stagekeys_method_returns_false(self):
        '''
        Test False returned value of 'associated'
        '''
        self.conn.update_api_key.side_effect = ClientError(error_content, 'update_api_key')
        result = boto_apigateway.associate_api_key_stagekeys(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                             stagekeyslist=[u'123yd1l123/test'],
                                                             **conn_parameters)
        self.assertFalse(result.get('associated'))

    def test_that_when_disassociating_stages_to_an_api_key_that_exists_the_disassociate_api_key_stagekeys_method_returns_true(self):
        '''
        Test True for returned value of 'associated'
        '''
        self.conn.update_api_key.retuen_value = None
        result = boto_apigateway.disassociate_api_key_stagekeys(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                                stagekeyslist=[u'123yd1l123/test'],
                                                                **conn_parameters)
        self.assertTrue(result.get('disassociated'))

    def test_that_when_disassociating_stages_to_an_api_key_that_does_not_exist_the_disassociate_api_key_stagekeys_method_returns_false(self):
        '''
        Test False returned value of 'associated'
        '''
        self.conn.update_api_key.side_effect = ClientError(error_content, 'update_api_key')
        result = boto_apigateway.disassociate_api_key_stagekeys(apiKey='88883333amaa1ZMVGCoLeaTrQk8kzOC36vCgRcT2',
                                                                stagekeyslist=[u'123yd1l123/test'],
                                                                **conn_parameters)
        self.assertFalse(result.get('disassociated'))

    def test_that_when_describing_api_deployments_the_describe_api_deployments_method_returns_list_of_deployments(self):
        '''
        Test Equality for number of deployments is 2
        '''
        self.conn.get_deployments.return_value = {u'items': [{u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                                              u'id': u'n05smo'},
                                                             {u'createdDate': datetime.datetime(2015, 12, 2, 19, 51, 44),
                                                              u'id': u'n05sm1'}],
                                                  'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.describe_api_deployments(restApiId='rm06h9oac4', **conn_parameters)
        self.assertEqual(len(result.get('deployments', {})), 2)

    def test_that_when_describing_api_deployments_and_an_error_occurred_the_describe_api_deployments_method_returns_error(self):
        '''
        Test Equality of error returned
        '''
        self.conn.get_deployments.side_effect = ClientError(error_content, 'get_deployments')
        result = boto_apigateway.describe_api_deployments(restApiId='rm06h9oac4', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_deployments'))

    def test_that_when_describing_an_api_deployment_the_describe_api_deployment_method_returns_the_deployment(self):
        '''
        Test True for the returned deployment
        '''
        self.conn.get_deployment.return_value = {u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                                 u'id': u'n05smo',
                                                 'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.describe_api_deployment(restApiId='rm06h9oac4', deploymentId='n05smo', **conn_parameters)
        self.assertTrue(result.get('deployment'))

    def test_that_when_describing_api_deployment_that_does_not_exist_the_describe_api_deployment_method_returns_error(self):
        '''
        Test Equality of error returned
        '''
        self.conn.get_deployment.side_effect = ClientError(error_content, 'get_deployment')
        result = boto_apigateway.describe_api_deployment(restApiId='rm06h9oac4', deploymentId='n05smo', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_deployment'))

    def test_that_when_activating_api_deployment_for_stage_and_deployment_that_exist_the_activate_api_deployment_method_returns_true(self):
        '''
        Test True for value of 'set'
        '''
        self.conn.update_stage.return_value = {u'cacheClusterEnabled': False,
                                               u'cacheClusterStatus': 'NOT_AVAAILABLE',
                                               u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                               u'deploymentId': 'n05smo',
                                               u'description': 'test',
                                               u'lastUpdatedDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                               u'stageName': 'test',
                                               'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.activate_api_deployment(restApiId='rm06h9oac4', stageName='test', deploymentId='n05smo',
                                                         **conn_parameters)
        self.assertTrue(result.get('set'))

    def test_that_when_activating_api_deployment_for_stage_that_does_not_exist_the_activate_api_deployment_method_returns_false(self):
        '''
        Test False for value of 'set'
        '''
        self.conn.update_stage.side_effect = ClientError(error_content, 'update_stage')
        result = boto_apigateway.activate_api_deployment(restApiId='rm06h9oac4', stageName='test', deploymentId='n05smo',
                                                         **conn_parameters)
        self.assertFalse(result.get('set'))

    def test_that_when_creating_an_api_deployment_succeeds_the_create_api_deployment_method_returns_true(self):
        '''
        tests that we can successfully create an api deployment and the createDate is
        converted to string
        '''
        now = datetime.datetime.now()
        self.conn.create_deployment.return_value = {
            u'description': u'test-lambda-api-key',
            u'id': 'n05smo',
            u'createdDate': now,
            'ResponseMetadata': {'HTTPStatusCode': 200,
                                 'RequestId': '7cc233dd-9dc8-11e5-ba47-1b7350cc2757'}}

        result = boto_apigateway.create_api_deployment(restApiId='rm06h9oac4', stageName='test', **conn_parameters)
        deployment = result.get('deployment')
        now_str = '{0}'.format(now)

        self.assertTrue(result.get('created'))
        self.assertEqual(deployment.get('createdDate'), now_str)

    def test_that_when_creating_an_deployment_fails_the_create_api_deployment_method_returns_error(self):
        '''
        tests that we properly handle errors when create an api deployment fails.
        '''

        self.conn.create_deployment.side_effect = ClientError(error_content, 'create_deployment')
        result = boto_apigateway.create_api_deployment(restApiId='rm06h9oac4', stageName='test', **conn_parameters)
        self.assertIs(result.get('created'), False)
        self.assertEqual(result.get('error').get('message'), error_message.format('create_deployment'))

    def test_that_when_deleting_an_api_deployment_that_exists_the_delete_api_deployment_method_returns_true(self):
        '''
        test True if the api deployment is successfully deleted.
        '''
        self.conn.delete_deployment.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.delete_api_deployment(restApiId='rm06h9oac4', deploymentId='n05smo', **conn_parameters)
        self.assertTrue(result.get('deleted'))

    def test_that_when_deleting_an_api_deployment_that_does_not_exist_the_delete_api_deployment_method_returns_false(self):
        '''
        Test that the given api deployment doesn't exists, and delete_api_deployment should return deleted status of False
        '''
        self.conn.delete_deployment.side_effect = ClientError(error_content, 'delete_deployment')
        result = boto_apigateway.delete_api_deployment(restApiId='rm06h9oac4', deploymentId='n05smo1', **conn_parameters)
        self.assertFalse(result.get('deleted'))

    def test_that_when_describing_api_stages_the_describe_api_stages_method_returns_list_of_stages(self):
        '''
        Test Equality for number of stages for the given deployment is 2
        '''
        self.conn.get_stages.return_value = {u'item': [{u'cacheClusterEnabled': False,
                                                        u'cacheClusterStatus': 'NOT_AVAILABLE',
                                                        u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                                        u'deploymentId': u'n05smo',
                                                        u'description': u'test',
                                                        u'lastUpdatedDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                                        u'stageName': u'test'},
                                                       {u'cacheClusterEnabled': False,
                                                        u'cacheClusterStatus': 'NOT_AVAILABLE',
                                                        u'createdDate': datetime.datetime(2015, 12, 17, 16, 33, 50),
                                                        u'deploymentId': u'n05smo',
                                                        u'description': u'dev',
                                                        u'lastUpdatedDate': datetime.datetime(2015, 12, 17, 16, 33, 50),
                                                        u'stageName': u'dev'}],
                                             'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.describe_api_stages(restApiId='rm06h9oac4', deploymentId='n05smo', **conn_parameters)
        self.assertEqual(len(result.get('stages', {})), 2)

    def test_that_when_describing_api_stages_and_that_the_deployment_does_not_exist_the_describe_api_stages_method_returns_error(self):
        '''
        Test Equality of error returned
        '''
        self.conn.get_stages.side_effect = ClientError(error_content, 'get_stages')
        result = boto_apigateway.describe_api_stages(restApiId='rm06h9oac4', deploymentId='n05smo', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_stages'))

    def test_that_when_describing_an_api_stage_the_describe_api_stage_method_returns_the_stage(self):
        '''
        Test True for the returned stage
        '''
        self.conn.get_stage.return_value = {u'cacheClusterEnabled': False,
                                            u'cacheClusterStatus': 'NOT_AVAILABLE',
                                            u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                            u'deploymentId': u'n05smo',
                                            u'description': u'test',
                                            u'lastUpdatedDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                            u'stageName': u'test',
                                            'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.describe_api_stage(restApiId='rm06h9oac4', stageName='test', **conn_parameters)
        self.assertTrue(result.get('stage'))

    def test_that_when_describing_api_stage_that_does_not_exist_the_describe_api_stage_method_returns_error(self):
        '''
        Test Equality of error returned
        '''
        self.conn.get_stage.side_effect = ClientError(error_content, 'get_stage')
        result = boto_apigateway.describe_api_stage(restApiId='rm06h9oac4', stageName='no_such_stage', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_stage'))

    def test_that_when_overwriting_stage_variables_to_an_existing_stage_the_overwrite_api_stage_variables_method_returns_the_updated_stage(self):
        '''
        Test True for the returned stage
        '''
        self.conn.get_stage.return_value = {u'cacheClusterEnabled': False,
                                            u'cacheClusterStatus': 'NOT_AVAILABLE',
                                            u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                            u'deploymentId': u'n05smo',
                                            u'description': u'test',
                                            u'lastUpdatedDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                            u'stageName': u'test',
                                            u'variables': {'key1': 'val1'},
                                            'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        self.conn.update_stage.return_value = {u'cacheClusterEnabled': False,
                                               u'cacheClusterStatus': 'NOT_AVAILABLE',
                                               u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                               u'deploymentId': u'n05smo',
                                               u'description': u'test',
                                               u'lastUpdatedDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                               u'stageName': u'test',
                                               u'variables': {'key1': 'val2'},
                                               'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.overwrite_api_stage_variables(restApiId='rm06h9oac4', stageName='test',
                                                               variables=dict(key1='val2'), **conn_parameters)
        self.assertEqual(result.get('stage').get('variables').get('key1'), 'val2')

    def test_that_when_overwriting_stage_variables_to_a_nonexisting_stage_the_overwrite_api_stage_variables_method_returns_error(self):
        '''
        Test Equality of error returned
        '''
        self.conn.get_stage.side_effect = ClientError(error_content, 'get_stage')
        result = boto_apigateway.overwrite_api_stage_variables(restApiId='rm06h9oac4', stageName='no_such_stage',
                                                               variables=dict(key1="val1", key2="val2"), **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_stage'))

    def test_that_when_overwriting_stage_variables_to_an_existing_stage_the_overwrite_api_stage_variables_method_returns_error(self):
        '''
        Test Equality of error returned due to update_stage
        '''
        self.conn.get_stage.return_value = {u'cacheClusterEnabled': False,
                                            u'cacheClusterStatus': 'NOT_AVAILABLE',
                                            u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                            u'deploymentId': u'n05smo',
                                            u'description': u'test',
                                            u'lastUpdatedDate': datetime.datetime(2015, 11, 17, 16, 33, 50),
                                            u'stageName': u'test',
                                            u'variables': {'key1': 'val1'},
                                            'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        self.conn.update_stage.side_effect = ClientError(error_content, 'update_stage')
        result = boto_apigateway.overwrite_api_stage_variables(restApiId='rm06h9oac4', stageName='test',
                                                               variables=dict(key1='val2'), **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('update_stage'))

    def test_that_when_creating_an_api_stage_succeeds_the_create_api_stage_method_returns_true(self):
        '''
        tests that we can successfully create an api stage and the createDate is
        converted to string
        '''
        now = datetime.datetime.now()
        self.conn.create_stage.return_value = {u'cacheClusterEnabled': False,
                                               u'cacheClusterStatus': 'NOT_AVAILABLE',
                                               u'createdDate': now,
                                               u'deploymentId': u'n05smo',
                                               u'description': u'test',
                                               u'lastUpdatedDate': now,
                                               u'stageName': u'test',
                                               'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}

        result = boto_apigateway.create_api_stage(restApiId='rm06h9oac4', stageName='test', deploymentId='n05smo',
                                                  **conn_parameters)
        stage = result.get('stage')
        now_str = '{0}'.format(now)
        self.assertIs(result.get('created'), True)
        self.assertEqual(stage.get('createdDate'), now_str)
        self.assertEqual(stage.get('lastUpdatedDate'), now_str)

    def test_that_when_creating_an_api_stage_fails_the_create_api_stage_method_returns_error(self):
        '''
        tests that we properly handle errors when create an api stage fails.
        '''

        self.conn.create_stage.side_effect = ClientError(error_content, 'create_stage')
        result = boto_apigateway.create_api_stage(restApiId='rm06h9oac4', stageName='test', deploymentId='n05smo',
                                                  **conn_parameters)
        self.assertIs(result.get('created'), False)
        self.assertEqual(result.get('error').get('message'), error_message.format('create_stage'))

    def test_that_when_deleting_an_api_stage_that_exists_the_delete_api_stage_method_returns_true(self):
        '''
        test True if the api stage is successfully deleted.
        '''
        self.conn.delete_stage.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.delete_api_stage(restApiId='rm06h9oac4', stageName='test', **conn_parameters)
        self.assertTrue(result.get('deleted'))

    def test_that_when_deleting_an_api_stage_that_does_not_exist_the_delete_api_stage_method_returns_false(self):
        '''
        Test that the given api stage doesn't exists, and delete_api_stage should return deleted status of False
        '''
        self.conn.delete_stage.side_effect = ClientError(error_content, 'delete_stage')
        result = boto_apigateway.delete_api_stage(restApiId='rm06h9oac4', stageName='no_such_stage', **conn_parameters)
        self.assertFalse(result.get('deleted'))

    def test_that_when_flushing_api_stage_cache_for_an_existing_stage_the_flush_api_stage_cache_method_returns_true(self):
        '''
        Test True for 'flushed'
        '''
        self.conn.flush_stage_cache.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.flush_api_stage_cache(restApiId='rm06h9oac4', stageName='no_such_stage', **conn_parameters)
        self.assertTrue(result.get('flushed'))

    def test_that_when_flushing_api_stage_cache_and_the_stage_does_not_exist_the_flush_api_stage_cache_method_returns_false(self):
        '''
        Test False for 'flushed'
        '''
        self.conn.flush_stage_cache.side_effect = ClientError(error_content, 'flush_stage_cache')
        result = boto_apigateway.flush_api_stage_cache(restApiId='rm06h9oac4', stageName='no_such_stage', **conn_parameters)
        self.assertFalse(result.get('flushed'))

    def test_that_when_describing_api_models_the_describe_api_models_method_returns_list_of_models(self):
        '''
        Test Equality for number of models for the given api is 2
        '''
        self.conn.get_models.return_value = {u'items': [{u'contentType': u'application/json',
                                                         u'name': u'Error',
                                                         u'description': u'Error Model',
                                                         u'id': u'iltqcb',
                                                         u'schema': u'{"properties":{"code":{"type":"integer","format":"int32"},"message":{"type":"string"},"fields":{"type":"string"}},"definitions":{}}'},
                                                        {u'contentType': u'application/json',
                                                         u'name': u'User',
                                                         u'description': u'User Model',
                                                         u'id': u'iltqcc',
                                                         u'schema': u'{"properties":{"username":{"type":"string","description":"A unique username for the user"},"password":{"type":"string","description":"A password for the new user"}},"definitions":{}}'}],
                                             'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.describe_api_models(restApiId='rm06h9oac4', **conn_parameters)
        self.assertEqual(len(result.get('models', {})), 2)

    def test_that_when_describing_api_models_and_that_the_api_does_not_exist_the_describe_api_models_method_returns_error(self):
        '''
        Test Equality of error returned
        '''
        self.conn.get_models.side_effect = ClientError(error_content, 'get_models')
        result = boto_apigateway.describe_api_models(restApiId='rm06h9oac4', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_models'))

    def test_that_when_describing_api_model_the_describe_api_model_method_returns_the_model(self):
        '''
        Test True for the returned stage
        '''
        self.conn.get_model.return_value = api_model_ret
        result = boto_apigateway.describe_api_model(restApiId='rm06h9oac4', modelName='Error', **conn_parameters)
        self.assertTrue(result.get('model'))

    def test_that_when_describing_api_model_and_that_the_model_does_not_exist_the_describe_api_model_method_returns_error(self):
        '''
        Test Equality of error returned
        '''
        self.conn.get_model.side_effect = ClientError(error_content, 'get_model')
        result = boto_apigateway.describe_api_model(restApiId='rm06h9oac4', modelName='Error', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_model'))

    def test_that_model_exists_the_api_model_exists_method_returns_true(self):
        '''
        Tests True when model exists
        '''
        self.conn.get_model.return_value = api_model_ret
        result = boto_apigateway.api_model_exists(restApiId='rm06h9oac4', modelName='Error', **conn_parameters)
        self.assertTrue(result.get('exists'))

    def test_that_model_does_not_exists_the_api_model_exists_method_returns_false(self):
        '''
        Tests False when model does not exist
        '''
        self.conn.get_model.side_effect = ClientError(error_content, 'get_model')
        result = boto_apigateway.api_model_exists(restApiId='rm06h9oac4', modelName='Error', **conn_parameters)
        self.assertFalse(result.get('exists'))

    def test_that_updating_model_schema_the_update_api_model_schema_method_returns_true(self):
        '''
        Tests True when model schema is updated.
        '''
        self.conn.update_model.return_value = api_model_ret
        result = boto_apigateway.update_api_model_schema(restApiId='rm06h9oac4', modelName='Error',
                                                         schema=api_model_error_schema, **conn_parameters)
        self.assertTrue(result.get('updated'))

    def test_that_updating_model_schema_when_model_does_not_exist_the_update_api_model_schema_emthod_returns_false(self):
        '''
        Tests False when model schema is not upated.
        '''
        self.conn.update_model.side_effect = ClientError(error_content, 'update_model')
        result = boto_apigateway.update_api_model_schema(restApiId='rm06h9oac4', modelName='no_such_model',
                                                         schema=api_model_error_schema, **conn_parameters)
        self.assertFalse(result.get('updated'))

    def test_that_when_creating_an_api_model_succeeds_the_create_api_model_method_returns_true(self):
        '''
        tests that we can successfully create an api model
        '''
        self.conn.create_model.return_value = api_model_ret
        result = boto_apigateway.create_api_model(restApiId='rm06h9oac4', modelName='Error',
                                                  modelDescription='Error Model', schema=api_model_error_schema,
                                                  **conn_parameters)
        self.assertTrue(result.get('created'))

    def test_that_when_creating_an_api_model_fails_the_create_api_model_method_returns_error(self):
        '''
        tests that we properly handle errors when create an api model fails.
        '''
        self.conn.create_model.side_effect = ClientError(error_content, 'create_model')
        result = boto_apigateway.create_api_model(restApiId='rm06h9oac4', modelName='Error',
                                                  modelDescription='Error Model', schema=api_model_error_schema,
                                                  **conn_parameters)
        self.assertFalse(result.get('created'))

    def test_that_when_deleting_an_api_model_that_exists_the_delete_api_model_method_returns_true(self):
        '''
        test True if the api model is successfully deleted.
        '''
        self.conn.delete_model.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.delete_api_model(restApiId='rm06h9oac4', modelName='Error', **conn_parameters)
        self.assertTrue(result.get('deleted'))

    def test_that_when_deleting_an_api_model_that_does_not_exist_the_delete_api_model_method_returns_false(self):
        '''
        Test that the given api model doesn't exists, and delete_api_model should return deleted status of False
        '''
        self.conn.delete_model.side_effect = ClientError(error_content, 'delete_model')
        result = boto_apigateway.delete_api_model(restApiId='rm06h9oac4', modelName='no_such_model', **conn_parameters)
        self.assertFalse(result.get('deleted'))

    def test_that_when_describing_api_resources_the_describe_api_resources_method_returns_list_of_3_resources(self):
        '''
        Test Equality for number of resources for the given api is 3
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.describe_api_resources(restApiId='rm06h9oac4', **conn_parameters)
        self.assertEqual(len(result.get('resources')), len(api_resources_ret.get('items')))

    def test_that_when_describing_api_resources_and_that_the_api_does_not_exist_the_describe_api_resources_method_returns_error(self):
        '''
        Test Equality of error returned
        '''
        self.conn.get_resources.side_effect = ClientError(error_content, 'get_resources')
        result = boto_apigateway.describe_api_resources(restApiId='rm06h9oac4', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_resources'))

    def test_that_when_describing_an_api_resource_that_exists_the_describe_api_resource_method_returns_the_resource(self):
        '''
        Test Equality of the resource path returned is /api
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.describe_api_resource(restApiId='rm06h9oac4', path="/api", **conn_parameters)
        self.assertEqual(result.get('resource', {}).get('path'), '/api')

    def test_that_when_describing_an_api_resource_that_does_not_exist_the_describe_api_resource_method_returns_the_resource_as_none(self):
        '''
        Test Equality of the 'resource' is None
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.describe_api_resource(restApiId='rm06h9oac4', path='/path/does/not/exist',
                                                       **conn_parameters)
        self.assertEqual(result.get('resource'), None)

    def test_that_when_describing_an_api_resource_and_that_the_api_does_not_exist_the_describe_api_resource_method_returns_error(self):
        '''
        Test Equality of error returned
        '''
        self.conn.get_resources.side_effect = ClientError(error_content, 'get_resources')
        result = boto_apigateway.describe_api_resource(restApiId='bad_id', path="/api", **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_resources'))

    def test_that_when_creating_api_resources_for_a_path_that_creates_one_new_resource_the_create_resources_api_method_returns_all_resources(self):
        '''
        Tests that a path of '/api3' returns 2 resources, named '/' and '/api'.
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.create_resource.return_value = api_create_resource_ret

        result = boto_apigateway.create_api_resources(restApiId='rm06h9oac4', path='/api3', **conn_parameters)

        resources = result.get('resources')
        self.assertIs(result.get('created'), True)
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0].get('path'), '/')
        self.assertEqual(resources[1].get('path'), '/api3')

    def test_that_when_creating_api_resources_for_a_path_whose_resources_exist_the_create_resources_api_method_returns_all_resources(self):
        '''
        Tests that a path of '/api/users' as defined in api_resources_ret return resources named '/', '/api',
        and '/api/users'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.create_api_resources(restApiId='rm06h9oac4', path='/api/users', **conn_parameters)
        resources = result.get('resources')
        self.assertIs(result.get('created'), True)
        self.assertEqual(len(resources), len(api_resources_ret.get('items')))
        self.assertEqual(resources[0].get('path'), '/')
        self.assertEqual(resources[1].get('path'), '/api')
        self.assertEqual(resources[2].get('path'), '/api/users')

    def test_that_when_creating_api_resource_fails_the_create_resources_api_method_returns_false(self):
        '''
        Tests False if we failed to create a resource
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.create_resource.side_effect = ClientError(error_content, 'create_resource')
        result = boto_apigateway.create_api_resources(restApiId='rm06h9oac4', path='/api4', **conn_parameters)
        self.assertFalse(result.get('created'))

    def test_that_when_deleting_api_resources_for_a_resource_that_exists_the_delete_api_resources_method_returns_true(self):
        '''
        Tests True for '/api'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.delete_api_resources(restApiId='rm06h9oac4', path='/api', **conn_parameters)
        self.assertTrue(result.get('deleted'))

    def test_that_when_deleting_api_resources_for_a_resource_that_does_not_exist_the_delete_api_resources_method_returns_false(self):
        '''
        Tests False for '/api5'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.delete_api_resources(restApiId='rm06h9oac4', path='/api5', **conn_parameters)
        self.assertFalse(result.get('deleted'))

    def test_that_when_deleting_the_root_api_resource_the_delete_api_resources_method_returns_false(self):
        '''
        Tests False for '/'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.delete_api_resources(restApiId='rm06h9oac4', path='/', **conn_parameters)
        self.assertFalse(result.get('deleted'))

    def test_that_when_deleting_api_resources_and_delete_resource_throws_error_the_delete_api_resources_method_returns_false(self):
        '''
        Tests False delete_resource side side_effect
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.delete_resource.side_effect = ClientError(error_content, 'delete_resource')
        result = boto_apigateway.delete_api_resources(restApiId='rm06h9oac4', path='/api', **conn_parameters)
        self.assertFalse(result.get('deleted'))

    def test_that_when_describing_an_api_resource_method_that_exists_the_describe_api_resource_method_returns_the_method(self):
        '''
        Tests True for '/api/users' and POST
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.get_method.return_value = {u'httpMethod': 'POST',
                                             'ResponseMetadata': {'HTTPStatusCode': 200,
                                                                  'RequestId': '7cc233dd-9dc8-11e5-ba47-1b7350cc2757'}}
        result = boto_apigateway.describe_api_resource_method(restApiId='rm06h9oac4',
                                                              resourcePath='/api/users',
                                                              httpMethod='POST', **conn_parameters)
        self.assertTrue(result.get('method'))

    def test_that_when_describing_an_api_resource_method_whose_method_does_not_exist_the_describe_api_resource_method_returns_error(self):
        '''
        Tests Equality of returned error for '/api/users' and PUT
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.get_method.side_effect = ClientError(error_content, 'get_method')
        result = boto_apigateway.describe_api_resource_method(restApiId='rm06h9oac4',
                                                              resourcePath='/api/users',
                                                              httpMethod='PUT', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_method'))

    def test_that_when_describing_an_api_resource_method_whose_resource_does_not_exist_the_describe_api_resrouce_method_returns_error(self):
        '''
        Tests True for resource not found error for '/does/not/exist' and POST
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.describe_api_resource_method(restApiId='rm06h9oac4',
                                                              resourcePath='/does/not/exist',
                                                              httpMethod='POST', **conn_parameters)
        self.assertTrue(result.get('error'))

    def test_that_when_creating_an_api_method_the_create_api_method_method_returns_true(self):
        '''
        Tests True on 'created' for '/api/users' and 'GET'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.put_method.return_value = {u'httpMethod': 'GET',
                                             'ResponseMetadata': {'HTTPStatusCode': 200,
                                                                  'RequestId': '7cc233dd-9dc8-11e5-ba47-1b7350cc2757'}}
        result = boto_apigateway.create_api_method(restApiId='rm06h9oac4',
                                                   resourcePath='/api/users',
                                                   httpMethod='GET',
                                                   authorizationType='NONE', **conn_parameters)
        self.assertTrue(result.get('created'))

    def test_that_when_creating_an_api_method_and_resource_does_not_exist_the_create_api_method_method_returns_false(self):
        '''
        Tests False on 'created' for '/api5', and 'GET'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.create_api_method(restApiId='rm06h9oac4',
                                                   resourcePath='/api5',
                                                   httpMethod='GET',
                                                   authorizationType='NONE', **conn_parameters)
        self.assertFalse(result.get('created'))

    def test_that_when_creating_an_api_method_and_error_thrown_on_put_method_the_create_api_method_method_returns_false(self):
        '''
        Tests False on 'created' for '/api/users' and 'GET'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.put_method.side_effect = ClientError(error_content, 'put_method')
        result = boto_apigateway.create_api_method(restApiId='rm06h9oac4',
                                                   resourcePath='/api/users',
                                                   httpMethod='GET',
                                                   authorizationType='NONE', **conn_parameters)
        self.assertFalse(result.get('created'))

    def test_that_when_deleting_an_api_method_for_a_method_that_exist_the_delete_api_method_method_returns_true(self):
        '''
        Tests True for '/api/users' and 'POST'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.delete_method.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.delete_api_method(restApiId='rm06h9oac4', resourcePath='/api/users',
                                                   httpMethod='POST', **conn_parameters)
        self.assertTrue(result.get('deleted'))

    def test_that_when_deleting_an_api_method_for_a_method_that_does_not_exist_the_delete_api_method_method_returns_false(self):
        '''
        Tests False for '/api/users' and 'GET'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.delete_method.side_effect = ClientError(error_content, 'delete_method')
        result = boto_apigateway.delete_api_method(restApiId='rm06h9oac4', resourcePath='/api/users',
                                                   httpMethod='GET', **conn_parameters)
        self.assertFalse(result.get('deleted'))

    def test_that_when_deleting_an_api_method_for_a_resource_that_does_not_exist_the_delete_api_method_method_returns_false(self):
        '''
        Tests False for '/api/users5' and 'POST'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.delete_api_method(restApiId='rm06h9oac4', resourcePath='/api/users5',
                                                   httpMethod='POST', **conn_parameters)
        self.assertFalse(result.get('deleted'))

    def test_that_when_describing_an_api_method_response_that_exists_the_describe_api_method_respond_method_returns_the_response(self):
        '''
        Tests True for 'response' for '/api/users', 'POST', and 200
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.get_method_response.return_value = {u'statusCode': 200,
                                                      'ResponseMetadata': {'HTTPStatusCode': 200,
                                                                           'RequestId': '7cc233dd-9dc8-11e5-ba47-1b7350cc2757'}}
        result = boto_apigateway.describe_api_method_response(restApiId='rm06h9oac4',
                                                              resourcePath='/api/users',
                                                              httpMethod='POST',
                                                              statusCode=200, **conn_parameters)
        self.assertTrue(result.get('response'))

    def test_that_when_describing_an_api_method_response_and_response_code_does_not_exist_the_describe_api_method_response_method_returns_error(self):
        '''
        Tests Equality of error msg thrown from get_method_response for '/api/users', 'POST', and 250
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.get_method_response.side_effect = ClientError(error_content, 'get_method_response')
        result = boto_apigateway.describe_api_method_response(restApiId='rm06h9oac4',
                                                              resourcePath='/api/users',
                                                              httpMethod='POST',
                                                              statusCode=250, **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_method_response'))

    def test_that_when_describing_an_api_method_response_and_resource_does_not_exist_the_describe_api_method_response_method_returns_error(self):
        '''
        Tests True for existence of 'error' for '/api5/users', 'POST', and 200
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.describe_api_method_response(restApiId='rm06h9oac4',
                                                              resourcePath='/api5/users',
                                                              httpMethod='POST',
                                                              statusCode=200, **conn_parameters)
        self.assertTrue(result.get('error'))

    def test_that_when_creating_an_api_method_response_the_create_api_method_response_method_returns_true(self):
        '''
        Tests True on 'created' for '/api/users', 'POST', 201
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.put_method_response.return_value = {u'statusCode': '201',
                                                      'ResponseMetadata': {'HTTPStatusCode': 200,
                                                                           'RequestId': '7cc233dd-9dc8-11e5-ba47-1b7350cc2757'}}
        result = boto_apigateway.create_api_method_response(restApiId='rm06h9oac4',
                                                            resourcePath='/api/users',
                                                            httpMethod='POST',
                                                            statusCode='201', **conn_parameters)
        self.assertTrue(result.get('created'))

    def test_that_when_creating_an_api_method_response_and_resource_does_not_exist_the_create_api_method_response_method_returns_false(self):
        '''
        Tests False on 'created' for '/api5', 'POST', 200
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.create_api_method_response(restApiId='rm06h9oac4',
                                                            resourcePath='/api5',
                                                            httpMethod='POST',
                                                            statusCode='200', **conn_parameters)
        self.assertFalse(result.get('created'))

    def test_that_when_creating_an_api_method_response_and_error_thrown_on_put_method_response_the_create_api_method_response_method_returns_false(self):
        '''
        Tests False on 'created' for '/api/users', 'POST', 200
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.put_method_response.side_effect = ClientError(error_content, 'put_method_response')
        result = boto_apigateway.create_api_method_response(restApiId='rm06h9oac4',
                                                            resourcePath='/api/users',
                                                            httpMethod='POST',
                                                            statusCode='200', **conn_parameters)
        self.assertFalse(result.get('created'))

    def test_that_when_deleting_an_api_method_response_for_a_response_that_exist_the_delete_api_method_response_method_returns_true(self):
        '''
        Tests True for '/api/users', 'POST', 200
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.delete_method_response.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        result = boto_apigateway.delete_api_method_response(restApiId='rm06h9oac4', resourcePath='/api/users',
                                                            httpMethod='POST', statusCode='200', **conn_parameters)
        self.assertTrue(result.get('deleted'))

    def test_that_when_deleting_an_api_method_response_for_a_response_that_does_not_exist_the_delete_api_method_response_method_returns_false(self):
        '''
        Tests False for '/api/users', 'POST', 201
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.delete_method_response.side_effect = ClientError(error_content, 'delete_method_response')
        result = boto_apigateway.delete_api_method_response(restApiId='rm06h9oac4', resourcePath='/api/users',
                                                            httpMethod='GET', statusCode='201', **conn_parameters)
        self.assertFalse(result.get('deleted'))

    def test_that_when_deleting_an_api_method_response_for_a_resource_that_does_not_exist_the_delete_api_method_response_method_returns_false(self):
        '''
        Tests False for '/api/users5', 'POST', 200
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.delete_api_method_response(restApiId='rm06h9oac4', resourcePath='/api/users5',
                                                            httpMethod='POST', statusCode='200', **conn_parameters)
        self.assertFalse(result.get('deleted'))

    def test_that_when_describing_an_api_integration_that_exists_the_describe_api_integration_method_returns_the_intgration(self):
        '''
        Tests True for 'integration' for '/api/users', 'POST'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.get_integration.return_value = {u'type': 'AWS',
                                                  u'uri': 'arn:aws:apigateway:us-west-2:lambda:path/2015-03-31/functions/arn:aws:lambda:us-west-2:1234568992820:function:echo_event/invocations',
                                                  u'credentials': 'testing',
                                                  u'httpMethod': 'POST',
                                                  u'intgrationResponses': {'200': {}},
                                                  u'requestTemplates': {'application/json': {}},
                                                  'ResponseMetadata': {'HTTPStatusCode': 200,
                                                                       'RequestId': '7cc233dd-9dc8-11e5-ba47-1b7350cc2757'}}
        result = boto_apigateway.describe_api_integration(restApiId='rm06h9oac4',
                                                          resourcePath='/api/users',
                                                          httpMethod='POST',
                                                          **conn_parameters)
        self.assertTrue(result.get('integration'))

    def test_that_when_describing_an_api_integration_and_method_does_not_have_integration_defined_the_describe_api_integration_method_returns_error(self):
        '''
        Tests Equality of error msg thrown from get_method_response for '/api/users', 'GET'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.get_integration.side_effect = ClientError(error_content, 'get_integration')
        result = boto_apigateway.describe_api_integration(restApiId='rm06h9oac4',
                                                          resourcePath='/api/users',
                                                          httpMethod='GET',
                                                          **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_integration'))

    def test_that_when_describing_an_api_integration_and_resource_does_not_exist_the_describe_api_integration_method_returns_error(self):
        '''
        Tests True for existence of 'error' for '/api5/users', 'POST'
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.describe_api_integration(restApiId='rm06h9oac4',
                                                          resourcePath='/api5/users',
                                                          httpMethod='POST',
                                                          **conn_parameters)
        self.assertTrue(result.get('error'))

    def test_that_when_describing_an_api_integration_response_that_exists_the_describe_api_integration_response_method_returns_the_intgration(self):
        '''
        Tests True for 'response' for '/api/users', 'POST', 200
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.get_integration_response.return_value = {u'responseParameters': {},
                                                           u'statusCode': 200,
                                                           'ResponseMetadata': {'HTTPStatusCode': 200,
                                                                                'RequestId': '7cc233dd-9dc8-11e5-ba47-1b7350cc2757'}}
        result = boto_apigateway.describe_api_integration_response(restApiId='rm06h9oac4',
                                                                   resourcePath='/api/users',
                                                                   httpMethod='POST',
                                                                   statusCode='200',
                                                                   **conn_parameters)
        self.assertTrue(result.get('response'))

    def test_that_when_describing_an_api_integration_response_and_status_code_does_not_exist_the_describe_api_integration_response_method_returns_error(self):
        '''
        Tests Equality of error msg thrown from get_method_response for '/api/users', 'POST', 201
        '''
        self.conn.get_resources.return_value = api_resources_ret
        self.conn.get_integration_response.side_effect = ClientError(error_content, 'get_integration_response')
        result = boto_apigateway.describe_api_integration_response(restApiId='rm06h9oac4',
                                                                   resourcePath='/api/users',
                                                                   httpMethod='POST',
                                                                   statusCode='201',
                                                                   **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_integration_response'))

    def test_that_when_describing_an_api_integration_response_and_resource_does_not_exist_the_describe_api_integration_response_method_returns_error(self):
        '''
        Tests True for existence of 'error' for '/api5/users', 'POST', 200
        '''
        self.conn.get_resources.return_value = api_resources_ret
        result = boto_apigateway.describe_api_integration_response(restApiId='rm06h9oac4',
                                                                   resourcePath='/api5/users',
                                                                   httpMethod='POST',
                                                                   statusCode='200',
                                                                   **conn_parameters)
        self.assertTrue(result.get('error'))

    def test_that_when_describing_usage_plans_and_an_exception_is_thrown_in_get_usage_plans(self):
        '''
        Tests True for existence of 'error'
        '''
        self.conn.get_usage_plans.side_effect = ClientError(error_content, 'get_usage_plans_exception')
        result = boto_apigateway.describe_usage_plans(name='some plan', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('get_usage_plans_exception'))

    def test_that_when_describing_usage_plans_and_plan_name_or_id_does_not_exist_that_results_have_empty_plans_list(self):
        '''
        Tests for plans equaling empty list
        '''
        self.conn.get_usage_plans.return_value = usage_plans_ret

        result = boto_apigateway.describe_usage_plans(name='does not exist', **conn_parameters)
        self.assertEqual(result.get('plans'), [])

        result = boto_apigateway.describe_usage_plans(plan_id='does not exist', **conn_parameters)
        self.assertEqual(result.get('plans'), [])

        result = boto_apigateway.describe_usage_plans(name='does not exist', plan_id='does not exist', **conn_parameters)
        self.assertEqual(result.get('plans'), [])

        result = boto_apigateway.describe_usage_plans(name='plan1_name', plan_id='does not exist', **conn_parameters)
        self.assertEqual(result.get('plans'), [])

        result = boto_apigateway.describe_usage_plans(name='does not exist', plan_id='plan1_id', **conn_parameters)
        self.assertEqual(result.get('plans'), [])

    def test_that_when_describing_usage_plans_for_plans_that_exist_that_the_function_returns_all_matching_plans(self):
        '''
        Tests for plans filtering properly if they exist
        '''
        self.conn.get_usage_plans.return_value = usage_plans_ret

        result = boto_apigateway.describe_usage_plans(name=usage_plan1['name'], **conn_parameters)
        self.assertEqual(len(result.get('plans')), 2)
        for plan in result['plans']:
            self.assertTrue(plan in [usage_plan1, usage_plan1b])

    def test_that_when_creating_or_updating_a_usage_plan_and_throttle_or_quota_failed_to_validate_that_an_error_is_returned(self):
        '''
        Tests for TypeError and ValueError in throttle and quota
        '''
        for throttle, quota in (([], None), (None, []), ('abc', None), (None, 'def')):
            res = boto_apigateway.create_usage_plan('plan1_name', description=None, throttle=throttle, quota=quota, **conn_parameters)
            self.assertNotEqual(None, res.get('error'))
            res = boto_apigateway.update_usage_plan('plan1_id', throttle=throttle, quota=quota, **conn_parameters)
            self.assertNotEqual(None, res.get('error'))

        for quota in ({'limit': 123}, {'period': 123}, {'period': 'DAY'}):
            res = boto_apigateway.create_usage_plan('plan1_name', description=None, throttle=None, quota=quota, **conn_parameters)
            self.assertNotEqual(None, res.get('error'))
            res = boto_apigateway.update_usage_plan('plan1_id', quota=quota, **conn_parameters)
            self.assertNotEqual(None, res.get('error'))

        self.assertTrue(self.conn.get_usage_plans.call_count == 0)
        self.assertTrue(self.conn.create_usage_plan.call_count == 0)
        self.assertTrue(self.conn.update_usage_plan.call_count == 0)

    def test_that_when_creating_a_usage_plan_and_create_usage_plan_throws_an_exception_that_an_error_is_returned(self):
        '''
        tests for ClientError
        '''
        self.conn.create_usage_plan.side_effect = ClientError(error_content, 'create_usage_plan_exception')
        result = boto_apigateway.create_usage_plan(name='some plan', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('create_usage_plan_exception'))

    def test_that_create_usage_plan_succeeds(self):
        '''
        tests for success user plan creation
        '''
        res = 'unit test create_usage_plan succeeded'
        self.conn.create_usage_plan.return_value = res
        result = boto_apigateway.create_usage_plan(name='some plan', **conn_parameters)
        self.assertEqual(result.get('created'), True)
        self.assertEqual(result.get('result'), res)

    def test_that_when_udpating_a_usage_plan_and_update_usage_plan_throws_an_exception_that_an_error_is_returned(self):
        '''
        tests for ClientError
        '''
        self.conn.update_usage_plan.side_effect = ClientError(error_content, 'update_usage_plan_exception')
        result = boto_apigateway.update_usage_plan(plan_id='plan1_id', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format('update_usage_plan_exception'))

    def test_that_when_updating_a_usage_plan_and_if_throttle_and_quota_parameters_are_none_update_usage_plan_removes_throttle_and_quota(self):
        '''
        tests for throttle and quota removal
        '''
        ret = 'some success status'
        self.conn.update_usage_plan.return_value = ret
        result = boto_apigateway.update_usage_plan(plan_id='plan1_id', throttle=None, quota=None, **conn_parameters)
        self.assertEqual(result.get('updated'), True)
        self.assertEqual(result.get('result'), ret)
        self.assertTrue(self.conn.update_usage_plan.call_count >= 1)

    def test_that_when_deleting_usage_plan_and_describe_usage_plans_had_error_that_the_same_error_is_returned(self):
        '''
        tests for error in describe_usage_plans returns error
        '''
        ret = 'get_usage_plans_exception'
        self.conn.get_usage_plans.side_effect = ClientError(error_content, ret)
        result = boto_apigateway.delete_usage_plan(plan_id='some plan id', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format(ret))
        self.assertTrue(self.conn.delete_usage_plan.call_count == 0)

    def test_that_when_deleting_usage_plan_and_plan_exists_that_the_functions_returns_deleted_true(self):
        self.conn.get_usage_plans.return_value = usage_plans_ret
        ret = 'delete_usage_plan_retval'
        self.conn.delete_usage_plan.return_value = ret
        result = boto_apigateway.delete_usage_plan(plan_id='plan1_id', **conn_parameters)
        self.assertEqual(result.get('deleted'), True)
        self.assertEqual(result.get('usagePlanId'), 'plan1_id')
        self.assertTrue(self.conn.delete_usage_plan.call_count >= 1)

    def test_that_when_deleting_usage_plan_and_plan_does_not_exist_that_the_functions_returns_deleted_true(self):
        '''
        tests for ClientError
        '''
        self.conn.get_usage_plans.return_value = dict(
            items=[]
        )
        ret = 'delete_usage_plan_retval'
        self.conn.delete_usage_plan.return_value = ret
        result = boto_apigateway.delete_usage_plan(plan_id='plan1_id', **conn_parameters)
        self.assertEqual(result.get('deleted'), True)
        self.assertEqual(result.get('usagePlanId'), 'plan1_id')
        self.assertTrue(self.conn.delete_usage_plan.call_count == 0)

    def test_that_when_deleting_usage_plan_and_delete_usage_plan_throws_exception_that_an_error_is_returned(self):
        '''
        tests for ClientError
        '''
        self.conn.get_usage_plans.return_value = usage_plans_ret
        error_msg = 'delete_usage_plan_exception'
        self.conn.delete_usage_plan.side_effect = ClientError(error_content, error_msg)
        result = boto_apigateway.delete_usage_plan(plan_id='plan1_id', **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format(error_msg))
        self.assertTrue(self.conn.delete_usage_plan.call_count >= 1)

    def test_that_attach_or_detach_usage_plan_when_apis_is_empty_that_success_is_returned(self):
        '''
        tests for border cases when apis is empty list
        '''
        result = boto_apigateway.attach_usage_plan_to_apis(plan_id='plan1_id', apis=[], **conn_parameters)
        self.assertEqual(result.get('success'), True)
        self.assertEqual(result.get('result', 'no result?'), None)
        self.assertTrue(self.conn.update_usage_plan.call_count == 0)

        result = boto_apigateway.detach_usage_plan_from_apis(plan_id='plan1_id', apis=[], **conn_parameters)
        self.assertEqual(result.get('success'), True)
        self.assertEqual(result.get('result', 'no result?'), None)
        self.assertTrue(self.conn.update_usage_plan.call_count == 0)

    def test_that_attach_or_detach_usage_plan_when_api_does_not_contain_apiId_or_stage_that_an_error_is_returned(self):
        '''
        tests for invalid key in api object
        '''
        for api in ({'apiId': 'some Id'}, {'stage': 'some stage'}, {}):
            result = boto_apigateway.attach_usage_plan_to_apis(plan_id='plan1_id', apis=[api], **conn_parameters)
            self.assertNotEqual(result.get('error'), None)

            result = boto_apigateway.detach_usage_plan_from_apis(plan_id='plan1_id', apis=[api], **conn_parameters)
            self.assertNotEqual(result.get('error'), None)

        self.assertTrue(self.conn.update_usage_plan.call_count == 0)

    def test_that_attach_or_detach_usage_plan_and_update_usage_plan_throws_exception_that_an_error_is_returned(self):
        '''
        tests for ClientError
        '''
        api = {'apiId': 'some_id', 'stage': 'some_stage'}
        error_msg = 'update_usage_plan_exception'
        self.conn.update_usage_plan.side_effect = ClientError(error_content, error_msg)

        result = boto_apigateway.attach_usage_plan_to_apis(plan_id='plan1_id', apis=[api], **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format(error_msg))

        result = boto_apigateway.detach_usage_plan_from_apis(plan_id='plan1_id', apis=[api], **conn_parameters)
        self.assertEqual(result.get('error').get('message'), error_message.format(error_msg))

    def test_that_attach_or_detach_usage_plan_updated_successfully(self):
        '''
        tests for update_usage_plan called
        '''
        api = {'apiId': 'some_id', 'stage': 'some_stage'}
        attach_ret = 'update_usage_plan_add_op_succeeded'
        detach_ret = 'update_usage_plan_remove_op_succeeded'
        self.conn.update_usage_plan.side_effect = [attach_ret, detach_ret]

        result = boto_apigateway.attach_usage_plan_to_apis(plan_id='plan1_id', apis=[api], **conn_parameters)
        self.assertEqual(result.get('success'), True)
        self.assertEqual(result.get('result'), attach_ret)

        result = boto_apigateway.detach_usage_plan_from_apis(plan_id='plan1_id', apis=[api], **conn_parameters)
        self.assertEqual(result.get('success'), True)
        self.assertEqual(result.get('result'), detach_ret)
