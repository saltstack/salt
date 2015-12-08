# -*- coding: utf-8 -*-

# TODO: Update skipped tests to expect dictionary results from the execution
#       module functions.

# Import Python libs
from __future__ import absolute_import
from distutils.version import LooseVersion  # pylint: disable=import-error,no-name-in-module
import datetime
from dateutil.tz import tzlocal
from md5 import md5

# Import Salt Testing libs
from salttesting.unit import skipIf, TestCase
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt libs
import salt.config
import salt.loader
from salt.modules import boto_apigateway
from salt.exceptions import SaltInvocationError, CommandExecutionError

# Import 3rd-party libs
import salt.ext.six as six
from tempfile import NamedTemporaryFile
import logging
import os

# pylint: disable=import-error,no-name-in-module
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# pylint: enable=import-error,no-name-in-module

# the boto_lambda module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto3_version = '1.2.1'

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
#cidr_block = '10.0.0.0/24'
#dhcp_options_parameters = {'domain_name': 'example.com', 'domain_name_servers': ['1.2.3.4'], 'ntp_servers': ['5.6.7.8'],
#                           'netbios_name_servers': ['10.0.0.1'], 'netbios_node_type': 2}
#network_acl_entry_parameters = ('fake', 100, -1, 'allow', cidr_block)
#dhcp_options_parameters.update(conn_parameters)

log = logging.getLogger(__name__)

opts = salt.config.DEFAULT_MINION_OPTS
context = {}
utils = salt.loader.utils(opts, whitelist=['boto3'], context=context)

boto_apigateway.__utils__ = utils
boto_apigateway.__init__(opts)
boto_apigateway.__salt__ = {}


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

class BotoApiGatewayTestCaseBase(TestCase):
    conn = None

    # Set up MagicMock to replace the boto3 session
    def setUp(self):
        global context
        context.clear()

        self.patcher = patch('boto3.session.Session')
        self.addCleanup(self.patcher.stop)
        mock_session = self.patcher.start()

        session_instance = mock_session.return_value
        self.conn = MagicMock()
        session_instance.client.return_value = self.conn

class BotoApiGatewayTestCaseMixin(object):
    def _diff_list_dicts(self, listdict1, listdict2, sortkey):
        '''
        Compares the two list of dictionaries to ensure they have same content.  Returns True
        if there is difference, else False
        '''
        if (len(listdict1) != len(listdict2)):
            return True

        listdict1_sorted = sorted(listdict1, key=lambda x: x[sortkey])
        listdict2_sorted = sorted(listdict2, key=lambda x: x[sortkey])
        for item1, item2 in zip(listdict1_sorted, listdict2_sorted):
            if (len(set(item1) & set(item2)) != len(set(item2))):
                return True
        return False


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoApiGatewayTestCase(BotoApiGatewayTestCaseBase, BotoApiGatewayTestCaseMixin):
    '''
    TestCase for salt.modules.boto_apigateway module
    '''

    def test_that_when_checking_if_a_rest_api_exists_and_a_rest_api_exists_the_api_exists_method_returns_true(self):
        '''
        Tests checking an apigateway rest api existence when api's name exists
        '''
        self.conn.get_rest_apis.return_value={'items': [{'name': 'myapi', 'id': '1234def'}]}
        api_exists_result = boto_apigateway.api_exists(name='myapi', **conn_parameters)

        self.assertTrue(api_exists_result['exists'])

    def test_that_when_checking_if_a_rest_api_exists_and_multiple_rest_api_exist_the_api_exists_method_returns_true(self):
        '''
        Tests checking an apigateway rest api existence when multiple api's with same name exists
        '''
        self.conn.get_rest_apis.return_value={'items': [{'name': 'myapi', 'id': '1234abc'},
                                                        {'name': 'myapi', 'id': '1234def'}]}
        api_exists_result = boto_apigateway.api_exists(name='myapi', **conn_parameters)

        self.assertTrue(api_exists_result['exists'])

    def test_that_when_checking_if_a_rest_api_exists_and_no_rest_api_exists_the_api_exists_method_returns_false(self):
        '''
        Tests checking an apigateway rest api existence when no matching rest api name exists
        '''
        self.conn.get_rest_apis.return_value={'items': [{'name': 'myapi', 'id': '1234abc'},
                                                        {'name': 'myapi', 'id': '1234def'}]}
        api_exists_result = boto_apigateway.api_exists(name='myapi123', **conn_parameters)
        
        self.assertFalse(api_exists_result['exists'])                                                


    def test_that_when_getting_rest_apis_and_no_name_option_the_get_apis_method_returns_list_of_all_rest_apis(self):
        '''
        Tests that all rest apis defined for a region is returned
        '''
        self.conn.get_rest_apis.return_value={u'items': [{u'description': u'A sample API that uses a petstore as an example to demonstrate features in the swagger-2.0 specification', 
                                                          u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50, tzinfo=tzlocal()), 
                                                          u'id': u'2ut6i4vyle', 
                                                          u'name': u'Swagger Petstore'}, 
                                                         {u'description': u'testingabcd', 
                                                          u'createdDate': datetime.datetime(2015, 12, 3, 21, 57, 58, tzinfo=tzlocal()), 
                                                          u'id': u'g41ls77hz0', 
                                                          u'name': u'testingabc'}, 
                                                         {u'description': u'a simple food delivery service test', 
                                                          u'createdDate': datetime.datetime(2015, 11, 4, 23, 57, 28, tzinfo=tzlocal()), 
                                                          u'id': u'h7pbwydho9', 
                                                          u'name': u'Food Delivery Service'}, 
                                                         {u'description': u'Created by AWS Lambda', 
                                                          u'createdDate': datetime.datetime(2015, 11, 4, 17, 55, 41, tzinfo=tzlocal()), 
                                                          u'id': u'i2yyd1ldvj', 
                                                          u'name': u'LambdaMicroservice'}, 
                                                         {u'description': u'cloud tap service with combination of API GW and Lambda', 
                                                          u'createdDate': datetime.datetime(2015, 11, 17, 22, 3, 18, tzinfo=tzlocal()), 
                                                          u'id': u'rm06h9oac4', 
                                                          u'name': u'API Gateway Cloudtap Service'}, 
                                                         {u'description': u'testing1234', 
                                                          u'createdDate': datetime.datetime(2015, 12, 2, 19, 51, 44, tzinfo=tzlocal()), 
                                                          u'id': u'vtir6ssxvd', 
                                                          u'name': u'testing123'}], 
                                              'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        items = self.conn.get_rest_apis.return_value['items']
        get_apis_result = boto_apigateway.get_apis()
        items_dt = map(boto_apigateway._convert_datetime_str, items)
        apis = get_apis_result.get('restapi')
        
        diff = False;
        if (len(apis) != len(items)):
            diff = True
        else:
            # compare individual items.
            diff = self._diff_list_dicts(apis, items_dt, 'id')

        self.assertTrue(apis and not diff)


    def test_that_when_getting_rest_apis_and_name_is_testing123_the_get_apis_method_returns_list_of_two_rest_apis(self):
        '''
        Tests that exactly 2 apis are returned matching 'testing123'
        '''
        self.conn.get_rest_apis.return_value={u'items': [{u'description': u'A sample API that uses a petstore as an example to demonstrate features in the swagger-2.0 specification', 
                                                          u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50, tzinfo=tzlocal()), 
                                                          u'id': u'2ut6i4vyle', 
                                                          u'name': u'Swagger Petstore'}, 
                                                         {u'description': u'testingabcd', 
                                                          u'createdDate': datetime.datetime(2015, 12, 3, 21, 57, 58, tzinfo=tzlocal()), 
                                                          u'id': u'g41ls77hz0', 
                                                          u'name': u'testing123'}, 
                                                         {u'description': u'a simple food delivery service test', 
                                                          u'createdDate': datetime.datetime(2015, 11, 4, 23, 57, 28, tzinfo=tzlocal()), 
                                                          u'id': u'h7pbwydho9', 
                                                          u'name': u'Food Delivery Service'}, 
                                                         {u'description': u'Created by AWS Lambda', 
                                                          u'createdDate': datetime.datetime(2015, 11, 4, 17, 55, 41, tzinfo=tzlocal()), 
                                                          u'id': u'i2yyd1ldvj', 
                                                          u'name': u'LambdaMicroservice'}, 
                                                         {u'description': u'cloud tap service with combination of API GW and Lambda', 
                                                          u'createdDate': datetime.datetime(2015, 11, 17, 22, 3, 18, tzinfo=tzlocal()), 
                                                          u'id': u'rm06h9oac4', 
                                                          u'name': u'API Gateway Cloudtap Service'}, 
                                                         {u'description': u'testing1234', 
                                                          u'createdDate': datetime.datetime(2015, 12, 2, 19, 51, 44, tzinfo=tzlocal()), 
                                                          u'id': u'vtir6ssxvd', 
                                                          u'name': u'testing123'}], 
                                              'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        expected_items = [{u'description': u'testingabcd', u'createdDate': datetime.datetime(2015, 12, 3, 21, 57, 58, tzinfo=tzlocal()), 
                           u'id': u'g41ls77hz0', u'name': u'testing123'}, 
                          {u'description': u'testing1234', u'createdDate': datetime.datetime(2015, 12, 2, 19, 51, 44, tzinfo=tzlocal()), 
                           u'id': u'vtir6ssxvd', u'name': u'testing123'}]  

        get_apis_result = boto_apigateway.get_apis(name='testing123')
        expected_items_dt = map(boto_apigateway._convert_datetime_str, expected_items)
        apis = get_apis_result.get('restapi')
        diff = self._diff_list_dicts(apis, expected_items_dt, 'id')

        self.assertTrue(apis and not diff)

    def test_that_when_getting_rest_apis_and_name_is_testing123_the_get_apis_method_returns_no_matching_items(self):
        '''
        Tests that no apis are returned matching 'testing123'
        '''
        self.conn.get_rest_apis.return_value={u'items': [{u'description': u'A sample API that uses a petstore as an example to demonstrate features in the swagger-2.0 specification', 
                                                          u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50, tzinfo=tzlocal()), 
                                                          u'id': u'2ut6i4vyle', 
                                                          u'name': u'Swagger Petstore'}, 
                                                         {u'description': u'a simple food delivery service test', 
                                                          u'createdDate': datetime.datetime(2015, 11, 4, 23, 57, 28, tzinfo=tzlocal()), 
                                                          u'id': u'h7pbwydho9', 
                                                          u'name': u'Food Delivery Service'}, 
                                                         {u'description': u'Created by AWS Lambda', 
                                                          u'createdDate': datetime.datetime(2015, 11, 4, 17, 55, 41, tzinfo=tzlocal()), 
                                                          u'id': u'i2yyd1ldvj', 
                                                          u'name': u'LambdaMicroservice'}, 
                                                         {u'description': u'cloud tap service with combination of API GW and Lambda', 
                                                          u'createdDate': datetime.datetime(2015, 11, 17, 22, 3, 18, tzinfo=tzlocal()), 
                                                          u'id': u'rm06h9oac4', 
                                                          u'name': u'API Gateway Cloudtap Service'}], 
                                              'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
                                 
        get_apis_result = boto_apigateway.get_apis(name='testing123')
        apis = get_apis_result.get('restapi')
 
        self.assertTrue(not apis)

    def test_that_when_creating_a_rest_api_succeeds_the_create_api_method_returns_true(self):
        '''
        test True if rest api is created
        '''
        created_date = datetime.datetime.now()
        assigned_api_id = unicode(md5('{0}'.format(created_date)).hexdigest()[:10])

        self.conn.create_rest_api.return_value={u'description': u'unit-testing1234', 
                                                u'createdDate': created_date, 
                                                u'id': assigned_api_id, 
                                                u'name': u'unit-testing123',
                                                'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        
        create_api_result = boto_apigateway.create_api(name='unit-testing123', description='unit-testing1234')
        api = create_api_result.get('restapi')

        self.assertTrue(create_api_result.get('created') and api and
                        api['id'] == assigned_api_id and
                        api['createdDate'] == '{0}'.format(created_date) and
                        api['name'] == 'unit-testing123' and
                        api['description'] == 'unit-testing1234')

    def test_that_when_creating_a_rest_api_fails_the_create_api_method_returns_error(self):
        '''
        test True for rest api creation error.
        '''
        self.conn.create_rest_api.side_effect=ClientError(error_content, 'create_rest_api')
        create_api_result = boto_apigateway.create_api(name='unit-testing123', description='unit-testing1234')
        api = create_api_result.get('restapi')

        self.assertEqual(create_api_result.get('error').get('message'), error_message.format('create_rest_api'))

    def test_that_when_deleting_rest_apis_and_name_is_testing123_matching_two_apis_the_delete_api_method_returns_delete_count_of_two(self):
        '''
        test True if the deleted count for "testing123" api is 2.
        '''
        self.conn.get_rest_apis.return_value={u'items': [{u'description': u'A sample API that uses a petstore as an example to demonstrate features in the swagger-2.0 specification', 
                                                          u'createdDate': datetime.datetime(2015, 11, 17, 16, 33, 50, tzinfo=tzlocal()), 
                                                          u'id': u'2ut6i4vyle', 
                                                          u'name': u'Swagger Petstore'}, 
                                                         {u'description': u'testingabcd', 
                                                          u'createdDate': datetime.datetime(2015, 12, 3, 21, 57, 58, tzinfo=tzlocal()), 
                                                          u'id': u'g41ls77hz0', 
                                                          u'name': u'testing123'}, 
                                                         {u'description': u'a simple food delivery service test', 
                                                          u'createdDate': datetime.datetime(2015, 11, 4, 23, 57, 28, tzinfo=tzlocal()), 
                                                          u'id': u'h7pbwydho9', 
                                                          u'name': u'Food Delivery Service'}, 
                                                         {u'description': u'Created by AWS Lambda', 
                                                          u'createdDate': datetime.datetime(2015, 11, 4, 17, 55, 41, tzinfo=tzlocal()), 
                                                          u'id': u'i2yyd1ldvj', 
                                                          u'name': u'LambdaMicroservice'}, 
                                                         {u'description': u'cloud tap service with combination of API GW and Lambda', 
                                                          u'createdDate': datetime.datetime(2015, 11, 17, 22, 3, 18, tzinfo=tzlocal()), 
                                                          u'id': u'rm06h9oac4', 
                                                          u'name': u'API Gateway Cloudtap Service'}, 
                                                         {u'description': u'testing1234', 
                                                          u'createdDate': datetime.datetime(2015, 12, 2, 19, 51, 44, tzinfo=tzlocal()), 
                                                          u'id': u'vtir6ssxvd', 
                                                          u'name': u'testing123'}], 
                                              'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        self.conn.delete_rest_api.return_value = None
        delete_api_result = boto_apigateway.delete_api(name='testing123')

        self.assertTrue(delete_api_result.get('deleted') and
                        delete_api_result.get('count') == 2)

    def test_that_when_deleting_rest_apis_and_name_given_provides_no_match_the_delete_api_method_returns_false(self):
        '''
        Test that the given api name doesn't exists, and delete_api should return deleted status of False
        '''
        self.conn.get_rest_apis.return_value={u'items': [{u'description': u'testing1234', 
                                                          u'createdDate': datetime.datetime(2015, 12, 2, 19, 51, 44, tzinfo=tzlocal()), 
                                                          u'id': u'vtir6ssxvd', 
                                                          u'name': u'testing1234'}], 
                                              'ResponseMetadata': {'HTTPStatusCode': 200, 'RequestId': '2d31072c-9d15-11e5-9977-6d9fcfda9c0a'}}
        self.conn.delete_rest_api.return_value = None
        delete_api_result = boto_apigateway.delete_api(name='testing123')

        self.assertTrue(delete_api_result.get('deleted') == False)



if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error
    run_tests(BotoApiGatewayTestCase, needs_daemon=False)