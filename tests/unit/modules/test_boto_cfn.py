import random
import string

import salt.config
import salt.modules.boto_cfn as boto_cfn
from salt.exceptions import SaltInvocationError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf

try:
    import boto

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

try:
    from moto import mock_cloudformation_deprecated

    HAS_MOTO = True
except ImportError:
    HAS_MOTO = False


def _random_stack_name():
    return "boto_stack-{}".format(
        "".join((random.choice(string.ascii_lowercase)) for char in range(12))
    )


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
class BotoSnsTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.boto_cfn module
    """

    region = "us-east-1"
    access_key = "GKTADJGHEIQSXMKKRBJ08H"
    secret_key = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"
    conn_parameters = {}
    template_body = """
        {
          "Description" : "CloudFormation template for testing boto_cfn",
          "Resources" : {
            "CFNTestPolicy" : {
              "Type" : "AWS::IAM::Policy",
              "Properties" : {
                "PolicyName" : "TestPolicy",
                "PolicyDocument" : {
                  "Statement": [{
                    "Effect"   : "Allow",
                    "Action"   : [
                      "cloudformation:Describe*",
                      "cloudformation:List*",
                      "cloudformation:Get*"
                      ],
                    "Resource" : "*"
                  }]
                }
              }
            }
          }
        }
    """
    conn = None

    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(
            self.opts,
            whitelist=["boto", "args", "systemd", "path", "platform"],
            context={},
        )
        return {boto_cfn: {"__utils__": utils}}

    def setUp(self):
        super().setUp()
        boto_cfn.__init__(self.opts)
        del self.opts

        self.conn_parameters = {
            "region": self.region,
            "key": self.access_key,
            "keyid": self.secret_key,
            "profile": {},
        }

        self.mock = mock_cloudformation_deprecated()
        self.mock.start()
        self.conn = boto.connect_cloudformation()

    def tearDown(self):
        self.mock.stop()

    def test_stack_exists_that_does_not_exist(self):
        name = _random_stack_name()
        self.assertFalse(boto_cfn.exists(name, **self.conn_parameters))

    def test_stack_exists_that_does_exist(self):
        name = _random_stack_name()
        resp = self.conn.create_stack(name, self.template_body)
        self.assertTrue(boto_cfn.exists(name, **self.conn_parameters))

    def test_stack_describe_returns_correct_json(self):
        name = _random_stack_name()
        self.conn.create_stack(name, self.template_body)
        resp = self.conn.describe_stacks(name)

        # Note: this was lifted almost 100% from the boto_cfn code.  The format
        # of this data has changed dramatically between boto2 and boto3, and we
        # need to preserve that format if we are to maintain compatibility.
        stack = resp[0]
        keys = (
            "stack_id",
            "description",
            "stack_status",
            "stack_status_reason",
            "tags",
        )
        data = {k: getattr(stack, k) for k in keys if hasattr(stack, k)}
        o = getattr(stack, "outputs")
        p = getattr(stack, "parameters")
        outputs = {}
        parameters = {}
        for i in o:
            outputs[i.key] = i.value
        data["outputs"] = outputs
        for j in p:
            parameters[j.key] = j.value
        data["parameters"] = parameters
        stack = {"stack": data}

        self.assertEqual(boto_cfn.describe(name, **self.conn_parameters), stack)

    def test_passing_templatebody_and_template_url_raises_exception(self):
        name = _random_stack_name()
        with self.assertRaises(SaltInvocationError):
            boto_cfn.create(
                name, self.template_body, "s3://anywhere", **self.conn_parameters
            )

    def test_stack_create_new_stack_returns_true(self):
        name = _random_stack_name()
        self.assertTrue(
            boto_cfn.create(name, self.template_body, **self.conn_parameters)
        )

    def test_stack_create_existing_stack_returns_false(self):
        name = _random_stack_name()
        resp = self.conn.create_stack(name, self.template_body)
        self.assertFalse(
            boto_cfn.create(name, self.template_body, **self.conn_parameters)
        )

    def test_delete_none_existant_stack_returns_failure(self):
        name = _random_stack_name()
        self.assertFalse(boto_cfn.delete(name, **self.conn_parameters))

    def test_delete_existing_stack_returns_success(self):
        name = _random_stack_name()
        self.conn.create_stack(name, self.template_body)
        self.assertTrue(boto_cfn.delete(name, **self.conn_parameters))
