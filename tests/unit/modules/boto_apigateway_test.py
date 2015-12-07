# -*- coding: utf-8 -*-

# TODO: Update skipped tests to expect dictionary results from the execution
#       module functions.

# Import Python libs
from __future__ import absolute_import
from distutils.version import LooseVersion  # pylint: disable=import-error,no-name-in-module

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
    pass


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoApiGatewayTestCase(BotoApiGatewayTestCaseBase, BotoApiGatewayTestCaseMixin):
    '''
    TestCase for salt.modules.boto_apigateway module
    '''

    def test_that_when_checking_if_a_rest_api_exists_and_a_rest_api_exists_the_function_api_exists_method_returns_true(self):
        '''
        Tests checking an apigateway rest api existence when api's name exists
        '''
        self.conn.get_rest_apis.return_value={'items': [{'name': 'myapi', 'id': '1234def'}]}
        api_exists_result = boto_apigateway.api_exists(name='myapi', **conn_parameters)

        self.assertTrue(api_exists_result['exists'])

    def test_that_when_checking_if_a_rest_api_exists_and_multiple_rest_api_exist_the_function_api_exists_method_returns_true(self):
        '''
        Tests checking an apigateway rest api existence when multiple api's with same name exists
        '''
        self.conn.get_rest_apis.return_value={'items': [{'name': 'myapi', 'id': '1234abc'},
                                                        {'name': 'myapi', 'id': '1234def'}]}
        api_exists_result = boto_apigateway.api_exists(name='myapi', **conn_parameters)

        self.assertTrue(api_exists_result['exists'])

    def test_that_when_checking_if_a_rest_api_exists_and_no_rest_api_exists_the_function_api_exists_method_returns_false(self):
        '''
        Tests checking an apigateway rest api existence when no matching rest api name exists
        '''
        self.conn.get_rest_apis.return_value={'items': [{'name': 'myapi', 'id': '1234abc'},
                                                        {'name': 'myapi', 'id': '1234def'}]}
        api_exists_result = boto_apigateway.api_exists(name='myapi123', **conn_parameters)
        
        self.assertFalse(api_exists_result['exists'])                                                

#    def test_that_when_creating_a_function_succeeds_the_create_function_method_returns_true(self):
#        '''
#        tests True function created.
#        '''
#        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
#            self.conn.create_function.return_value={'FunctionName': 'testfunction'}
#            with TempZipFile() as zipfile:
#                lambda_creation_result = boto_lambda.create_function(FunctionName='testfunction',
#                                                    Runtime='python2.7',
#                                                    Role='myrole',
#                                                    Handler='file.method',
#                                                    ZipFile=zipfile,
#                                                    **conn_parameters)
#
#        self.assertTrue(lambda_creation_result['created'])
#
#    def test_that_when_creating_a_function_succeeds_the_create_function_method_returns_error(self):
#        '''
#        tests True function created.
#        '''
#        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
#            self.conn.create_function.side_effect=ClientError(error_content, 'create_function')
#            with TempZipFile() as zipfile:
#                lambda_creation_result = boto_lambda.create_function(FunctionName='testfunction',
#                                                    Runtime='python2.7',
#                                                    Role='myrole',
#                                                    Handler='file.method',
#                                                    ZipFile=zipfile,
#                                                    **conn_parameters)
#        self.assertEqual(lambda_creation_result.get('error',{}).get('message'), error_message.format('create_function'))

if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error
    run_tests(BotoApiGatewayTestCase, needs_daemon=False)