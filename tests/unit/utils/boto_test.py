# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
from distutils.version import LooseVersion  # pylint: disable=import-error,no-name-in-module

# Import Salt Testing libs
from salttesting.unit import skipIf, TestCase
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import Salt libs
from salt.exceptions import SaltInvocationError
import salt.utils.boto
import salt.utils.boto3

# Import 3rd-party libs
# pylint: disable=import-error
try:
    import boto
    import boto.exception
    from boto.exception import BotoServerError

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

try:
    import boto3

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    from moto import mock_ec2

    HAS_MOTO = True
except ImportError:
    HAS_MOTO = False

    def mock_ec2(self):
        '''
        if the mock_ec2 function is not available due to import failure
        this replaces the decorated function with stub_function.
        Allows unit tests to use the @mock_ec2 decorator
        without a "NameError: name 'mock_ec2' is not defined" error.
        '''

        def stub_function(self):
            pass

        return stub_function


required_boto_version = '2.0.0'
required_boto3_version = '1.2.1'
region = 'us-east-1'
access_key = 'GKTADJGHEIQSXMKKRBJ08H'
secret_key = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
conn_parameters = {'region': region, 'key': access_key, 'keyid': secret_key, 'profile': {}}

service = 'ec2'
resource_name = 'test-instance'
resource_id = 'i-a1b2c3'


error_body = '''
<Response>
    <Errors>
         <Error>
           <Code>Error code text</Code>
           <Message>Error message</Message>
         </Error>
    </Errors>
    <RequestID>request ID</RequestID>
</Response>
'''

no_error_body = '''
<Response>
    <Errors />
    <RequestID>request ID</RequestID>
</Response>
'''


def _has_required_boto():
    '''
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    '''
    if not HAS_BOTO:
        return False
    elif LooseVersion(boto.__version__) < LooseVersion(required_boto_version):
        return False
    else:
        return True


def _has_required_boto3():
    '''
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    '''
    if not HAS_BOTO3:
        return False
    elif LooseVersion(boto3.__version__) < LooseVersion(required_boto3_version):
        return False
    else:
        return True


def _has_required_moto():
    '''
    Returns True/False boolean depending on if Moto is installed and correct
    version.
    '''
    if not HAS_MOTO:
        return False
    else:
        import pkg_resources

        if LooseVersion(pkg_resources.get_distribution('moto').version) < LooseVersion('0.3.7'):
            return False
        return True


class BotoUtilsTestCaseBase(TestCase):

    def setUp(self):
        salt.utils.boto.__context__ = {}
        salt.utils.boto.__opts__ = {}
        salt.utils.boto.__pillar__ = {}
        salt.utils.boto.__salt__ = {'config.option': MagicMock(return_value='dummy_opt')}


class BotoUtilsCacheIdTestCase(BotoUtilsTestCaseBase):
    def test_set_and_get_with_no_auth_params(self):
        salt.utils.boto.cache_id(service, resource_name, resource_id=resource_id)
        self.assertEqual(salt.utils.boto.cache_id(service, resource_name), resource_id)

    def test_set_and_get_with_explicit_auth_params(self):
        salt.utils.boto.cache_id(service, resource_name, resource_id=resource_id, **conn_parameters)
        self.assertEqual(salt.utils.boto.cache_id(service, resource_name, **conn_parameters), resource_id)

    def test_set_and_get_with_different_region_returns_none(self):
        salt.utils.boto.cache_id(service, resource_name, resource_id=resource_id, region='us-east-1')
        self.assertEqual(salt.utils.boto.cache_id(service, resource_name, region='us-west-2'), None)

    def test_set_and_get_after_invalidation_returns_none(self):
        salt.utils.boto.cache_id(service, resource_name, resource_id=resource_id)
        salt.utils.boto.cache_id(service, resource_name, resource_id=resource_id, invalidate=True)
        self.assertEqual(salt.utils.boto.cache_id(service, resource_name), None)

    def test_partial(self):
        cache_id = salt.utils.boto.cache_id_func(service)
        cache_id(resource_name, resource_id=resource_id)
        self.assertEqual(cache_id(resource_name), resource_id)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
class BotoUtilsGetConnTestCase(BotoUtilsTestCaseBase):

    @mock_ec2
    def test_conn_is_cached(self):
        conn = salt.utils.boto.get_connection(service, **conn_parameters)
        self.assertTrue(conn in salt.utils.boto.__context__.values())

    @mock_ec2
    def test_conn_is_cache_with_profile(self):
        conn = salt.utils.boto.get_connection(service, profile=conn_parameters)
        self.assertTrue(conn in salt.utils.boto.__context__.values())

    @mock_ec2
    def test_get_conn_with_no_auth_params_raises_invocation_error(self):
        with patch('boto.{0}.connect_to_region'.format(service),
                   side_effect=boto.exception.NoAuthHandlerFound()):
            with self.assertRaises(SaltInvocationError):
                salt.utils.boto.get_connection(service)

    @mock_ec2
    def test_get_conn_error_raises_command_execution_error(self):
        with patch('boto.{0}.connect_to_region'.format(service),
                   side_effect=BotoServerError(400, 'Mocked error', body=error_body)):
            with self.assertRaises(BotoServerError):
                salt.utils.boto.get_connection(service)

    @mock_ec2
    def test_partial(self):
        get_conn = salt.utils.boto.get_connection_func(service)
        conn = get_conn(**conn_parameters)
        self.assertTrue(conn in salt.utils.boto.__context__.values())


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
class BotoUtilsGetErrorTestCase(BotoUtilsTestCaseBase):
    def test_error_message(self):
        e = BotoServerError('400', 'Mocked error', body=error_body)
        r = salt.utils.boto.get_error(e)
        expected = {'aws': {'code': 'Error code text',
                            'message': 'Error message',
                            'reason': 'Mocked error',
                            'status': '400'},
                    'message': 'Mocked error: Error message'}
        self.assertEqual(r, expected)

    def test_exception_message_with_no_body(self):
        e = BotoServerError('400', 'Mocked error')
        r = salt.utils.boto.get_error(e)
        expected = {'aws': {'reason': 'Mocked error',
                            'status': '400'},
                    'message': 'Mocked error'}
        self.assertEqual(r, expected)

    def test_exception_message_with_no_error_in_body(self):
        e = BotoServerError('400', 'Mocked error', body=no_error_body)
        r = salt.utils.boto.get_error(e)
        expected = {'aws': {'reason': 'Mocked error', 'status': '400'},
                            'message': 'Mocked error'}
        self.assertEqual(r, expected)


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
@skipIf(HAS_BOTO3 is False, 'The boto3 module must be installed.')
@skipIf(_has_required_boto3() is False, 'The boto3 module must be greater than'
                                        ' or equal to version {0}'
        .format(required_boto3_version))
class BotoBoto3CacheContextCollisionTest(BotoUtilsTestCaseBase):

    def setUp(self):
        salt.utils.boto.__context__ = {}
        salt.utils.boto.__opts__ = {}
        salt.utils.boto.__pillar__ = {}
        salt.utils.boto.__salt__ = {'config.option': MagicMock(return_value='dummy_opt')}

        salt.utils.boto3.__context__ = salt.utils.boto.__context__
        salt.utils.boto3.__opts__ = salt.utils.boto.__opts__
        salt.utils.boto3.__pillar__ = salt.utils.boto.__pillar__
        salt.utils.boto3.__salt__ = salt.utils.boto.__salt__

    def test_context_conflict_between_boto_and_boto3_utils(self):
        salt.utils.boto.assign_funcs(__name__, 'ec2')
        salt.utils.boto3.assign_funcs(__name__, 'ec2', get_conn_funcname="_get_conn3")

        boto_ec2_conn = salt.utils.boto.get_connection('ec2',
                                                       region=region,
                                                       key=secret_key,
                                                       keyid=access_key)
        boto3_ec2_conn = salt.utils.boto3.get_connection('ec2',
                                                         region=region,
                                                         key=secret_key,
                                                         keyid=access_key)

        # These should *not* be the same object!
        self.assertNotEqual(id(boto_ec2_conn), id(boto3_ec2_conn))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BotoUtilsGetConnTestCase, needs_daemon=False)
