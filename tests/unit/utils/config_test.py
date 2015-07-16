# -*- coding: utf-8 -*-
# pylint: disable=function-redefined
# TODO: Remove the following PyLint disable as soon as we support YAML and RST rendering
# pylint: disable=abstract-method

# Import python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.utils import config

# Import 3rd-party libs
try:
    import jsonschema
    import jsonschema.exceptions
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# pylint: disable=unused-import
try:
    import rfc3987
    HAS_RFC3987 = True
except ImportError:
    HAS_RFC3987 = False

try:
    import strict_rfc3339
    HAS_STRICT_RFC3339 = True
except ImportError:
    HAS_STRICT_RFC3339 = False

try:
    import isodate
    HAS_ISODATE = True
except ImportError:
    HAS_ISODATE = False
# pylint: enable=unused-import


class ConfigTestCase(TestCase):
    '''
    TestCase for salt.utils.config module
    '''

    def test_configuration_subclass_inherits_items(self):
        class BaseConfig(config.Schema):
            base = config.BooleanItem(default=True, required=True)

        class SubClassedConfig(BaseConfig):
            hungry = config.BooleanItem(title='Hungry', description='Are you hungry?', required=True)

        self.assertDictEqual(
            SubClassedConfig.serialize(),
            {
                '$schema': 'http://json-schema.org/draft-04/schema#',
                'type': 'object',
                'properties': {
                    'base': {
                      'default': True,
                      'type': 'boolean',
                      'title': 'base'
                     },
                     'hungry': {
                        'type': 'boolean',
                        'description': 'Are you hungry?',
                        'title': 'Hungry'
                    }
                },
                'required': ['base', 'hungry'],
                'x-ordering': ['base', 'hungry'],
                'additionalProperties': False,
            }
        )

    def test_configuration_items_order(self):

        class One(config.Schema):
            one = config.BooleanItem()

        class Three(config.Schema):
            three = config.BooleanItem()

        class Final(One):
            two = config.BooleanItem()
            three = Three(flatten=True)

        self.assertEqual(Final.serialize()['x-ordering'], ['one', 'two', 'three'])

    def test_optional_requirements_config(self):
        class BaseRequirements(config.Schema):
            driver = config.StringItem(default='digital_ocean', format='hidden')

        class SSHKeyFileSchema(config.Schema):
            ssh_key_file = config.StringItem(
                title='SSH Private Key',
                description='The path to an SSH private key which will be used '
                            'to authenticate on the deployed VMs',
                required=True)

        class SSHKeyNamesSchema(config.Schema):
            ssh_key_names = config.StringItem(
                title='SSH Key Names',
                description='The names of an SSH key being managed on '
                            'Digital Ocean account which will be used to '
                            'authenticate on the deployed VMs',
                required=True)

        class Requirements(BaseRequirements):
            title = 'Digital Ocean'
            description = 'Digital Ocean Cloud VM configuration requirements.'

            personal_access_token = config.StringItem(
                title='Personal Access Token',
                description='This is the API access token which can be generated '
                            'under the API/Application on your account',
                required=True)

            requirements_definition = config.AnyOfItem(
                items=(
                    SSHKeyFileSchema.as_requirements_item(),
                    SSHKeyNamesSchema.as_requirements_item()
                ),
            )(flatten=True)
            ssh_key_file = SSHKeyFileSchema(flatten=True)
            ssh_key_names = SSHKeyNamesSchema(flatten=True)

        expexcted = {
                "$schema": "http://json-schema.org/draft-04/schema#",
                "title": "Digital Ocean",
                "description": "Digital Ocean Cloud VM configuration requirements.",
                "type": "object",
                "properties": {
                    "driver": {
                        "default": "digital_ocean",
                        "format": "hidden",
                        "type": "string",
                        "title": "driver"
                    },
                    "personal_access_token": {
                        "type": "string",
                        "description": "This is the API access token which can be "
                                       "generated under the API/Application on your account",
                        "title": "Personal Access Token"
                    },
                    "ssh_key_file": {
                        "type": "string",
                        "description": "The path to an SSH private key which will "
                                       "be used to authenticate on the deployed VMs",
                        "title": "SSH Private Key"
                    },
                    "ssh_key_names": {
                        "type": "string",
                        "description": "The names of an SSH key being managed on Digital "
                                       "Ocean account which will be used to authenticate "
                                       "on the deployed VMs",
                        "title": "SSH Key Names"
                    }
                },
                "anyOf": [
                    {"required": ["ssh_key_file"]},
                    {"required": ["ssh_key_names"]}
                ],
                "required": [
                    "personal_access_token"
                ],
                "x-ordering": [
                    "driver",
                    "personal_access_token",
                    "ssh_key_file",
                    "ssh_key_names",
                ],
                "additionalProperties": False
            }
        self.assertDictEqual(expexcted, Requirements.serialize())

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_optional_requirements_config_validation(self):
        class BaseRequirements(config.Schema):
            driver = config.StringItem(default='digital_ocean', format='hidden')

        class SSHKeyFileSchema(config.Schema):
            ssh_key_file = config.StringItem(
                title='SSH Private Key',
                description='The path to an SSH private key which will be used '
                            'to authenticate on the deployed VMs',
                required=True)

        class SSHKeyNamesSchema(config.Schema):
            ssh_key_names = config.StringItem(
                title='SSH Key Names',
                description='The names of an SSH key being managed on  '
                            'Digial Ocean account which will be used to '
                            'authenticate on the deployed VMs',
                required=True)

        class Requirements(BaseRequirements):
            title = 'Digital Ocean'
            description = 'Digital Ocean Cloud VM configuration requirements.'

            personal_access_token = config.StringItem(
                title='Personal Access Token',
                description='This is the API access token which can be generated '
                            'under the API/Application on your account',
                required=True)

            requirements_definition = config.AnyOfItem(
                items=(
                    SSHKeyFileSchema.as_requirements_item(),
                    SSHKeyNamesSchema.as_requirements_item()
                ),
            )(flatten=True)
            ssh_key_file = SSHKeyFileSchema(flatten=True)
            ssh_key_names = SSHKeyNamesSchema(flatten=True)

        try:
            jsonschema.validate(
                {"personal_access_token": "foo", "ssh_key_names": "bar", "ssh_key_file": "test"},
                Requirements.serialize()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate(
                {"personal_access_token": "foo", "ssh_key_names": "bar"},
                Requirements.serialize()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate(
                {"personal_access_token": "foo", "ssh_key_file": "test"},
                Requirements.serialize()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate(
                {"personal_access_token": "foo"},
                Requirements.serialize()
            )
        self.assertIn('is not valid under any of the given schemas', excinfo.exception.message)

    def test_boolean_config(self):
        item = config.BooleanItem(title='Hungry', description='Are you hungry?')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'boolean',
                'title': item.title,
                'description': item.description
            }
        )

        item = config.BooleanItem(title='Hungry',
                                    description='Are you hungry?',
                                    default=False)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'boolean',
                'title': item.title,
                'description': item.description,
                'default': item.default
            }
        )

        item = config.BooleanItem(title='Hungry',
                                    description='Are you hungry?',
                                    default=config.Null)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'boolean',
                'title': item.title,
                'description': item.description,
                'default': None
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_boolean_config_validation(self):
        class TestConf(config.Schema):
            item = config.BooleanItem(title='Hungry', description='Are you hungry?')

        try:
            jsonschema.validate({'item': False}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 1}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

    def test_string_config(self):
        item = config.StringItem(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description
            }
        )

        item = config.StringItem(title='Foo', description='Foo Item', min_length=1, max_length=3)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'minLength': item.min_length,
                'maxLength': item.max_length
            }
        )

        item = config.StringItem(title='Foo',
                                   description='Foo Item',
                                   min_length=1,
                                   max_length=3,
                                   default='foo')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'minLength': item.min_length,
                'maxLength': item.max_length,
                'default': 'foo'
            }
        )

        item = config.StringItem(title='Foo',
                                   description='Foo Item',
                                   min_length=1,
                                   max_length=3,
                                   enum=('foo', 'bar'))
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'minLength': item.min_length,
                'maxLength': item.max_length,
                'enum': ['foo', 'bar']
            }
        )

        item = config.StringItem(title='Foo',
                                   description='Foo Item',
                                   min_length=1,
                                   max_length=3,
                                   enum=('foo', 'bar'),
                                   enumNames=('Foo', 'Bar'))
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'minLength': item.min_length,
                'maxLength': item.max_length,
                'enum': ['foo', 'bar'],
                'enumNames': ['Foo', 'Bar']
            }
        )

        item = config.StringItem(title='Foo',
                                   description='Foo Item',
                                   pattern=r'^([\w_-]+)$')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'pattern': item.pattern
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_string_config_validation(self):
        class TestConf(config.Schema):
            item = config.StringItem(title='Foo', description='Foo Item')

        try:
            jsonschema.validate({'item': 'the item'}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(config.Schema):
            item = config.StringItem(title='Foo', description='Foo Item',
                                       min_length=1, max_length=10)

        try:
            jsonschema.validate({'item': 'the item'}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 'the item the item'}, TestConf.serialize())
        self.assertIn('is too long', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.StringItem(title='Foo', description='Foo Item',
                                       min_length=10, max_length=100)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 'the item'}, TestConf.serialize())
        self.assertIn('is too short', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.StringItem(title='Foo',
                                       description='Foo Item',
                                       enum=('foo', 'bar'))

        try:
            jsonschema.validate({'item': 'foo'}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(config.Schema):
            item = config.StringItem(title='Foo',
                                       description='Foo Item',
                                       enum=('foo', 'bar'))
        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 'bin'}, TestConf.serialize())
        self.assertIn('is not one of', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.StringItem(title='Foo', description='Foo Item',
                                       pattern=r'^([\w_-]+)$')

        try:
            jsonschema.validate({'item': 'the-item'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 'the item'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('does not match', excinfo.exception.message)

    def test_email_config(self):
        item = config.EMailItem(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_email_config_validation(self):
        class TestConf(config.Schema):
            item = config.EMailItem(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': 'nobody@nowhere.com'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_ipv4_config(self):
        item = config.IPv4Item(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_ipv4_config_validation(self):
        class TestConf(config.Schema):
            item = config.IPv4Item(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': '127.0.0.1'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_ipv6_config(self):
        item = config.IPv6Item(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_ipv6_config_validation(self):
        class TestConf(config.Schema):
            item = config.IPv6Item(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': '::1'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_hostname_config(self):
        item = config.HostnameItem(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_hostname_config_validation(self):
        class TestConf(config.Schema):
            item = config.HostnameItem(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': 'localhost'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_datetime_config(self):
        item = config.DateTimeItem(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    @skipIf(any([HAS_ISODATE, HAS_STRICT_RFC3339]) is False, 'The \'strict_rfc3339\' or \'isodate\' library is missing')
    def test_datetime_config_validation(self):
        class TestConf(config.Schema):
            item = config.DateTimeItem(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': '2015-07-01T18:05:27+01:00'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_secret_config(self):
        item = config.SecretItem(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    def test_uri_config(self):
        item = config.UriItem(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    @skipIf(HAS_RFC3987 is False, 'The \'rfc3987\' library is missing')
    def test_uri_config_validation(self):
        class TestConf(config.Schema):
            item = config.UriItem(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': 'ssh://localhost'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_number_config(self):
        item = config.NumberItem(title='How many dogs', description='Question')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description
            }
        )

        item = config.NumberItem(title='How many dogs',
                                   description='Question',
                                   minimum=0,
                                   maximum=10)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum
            }
        )

        item = config.NumberItem(title='How many dogs',
                                   description='Question',
                                   multiple_of=2)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description,
                'multipleOf': item.multiple_of
            }
        )

        item = config.NumberItem(title='How many dogs',
                                   description='Question',
                                   minimum=0,
                                   exclusive_minimum=True,
                                   maximum=10,
                                   exclusive_maximum=True)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'exclusiveMinimum': True,
                'exclusiveMaximum': True
            }
        )

        item = config.NumberItem(title='How many dogs',
                                   description='Question',
                                   minimum=0,
                                   maximum=10,
                                   default=0)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'default': 0
            }
        )

        item = config.NumberItem(title='How many dogs',
                                   description='Question',
                                   minimum=0,
                                   maximum=10,
                                   default=0,
                                   enum=(0, 2, 4, 6))
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'default': 0,
                'enum': [0, 2, 4, 6]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_number_config_validation(self):
        class TestConf(config.Schema):
            item = config.NumberItem(title='How many dogs', description='Question')

        try:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.NumberItem(title='How many dogs',
                                       description='Question',
                                       multiple_of=2.2)

        try:
            jsonschema.validate({'item': 4.4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        self.assertIn('is not a multiple of', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.NumberItem(title='Foo', description='Foo Item',
                                       minimum=1, maximum=10)

        try:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 11}, TestConf.serialize())
        self.assertIn('is greater than the maximum of', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.NumberItem(title='Foo', description='Foo Item',
                                       minimum=10, maximum=100)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is less than the minimum of', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.NumberItem(title='How many dogs',
                                       description='Question',
                                       minimum=0,
                                       exclusive_minimum=True,
                                       maximum=10,
                                       exclusive_maximum=True)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 0}, TestConf.serialize())
        self.assertIn('is less than or equal to the minimum of', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 10}, TestConf.serialize())
        self.assertIn('is greater than or equal to the maximum of', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.NumberItem(title='Foo',
                                       description='Foo Item',
                                       enum=(0, 2, 4, 6))

        try:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(config.Schema):
            item = config.NumberItem(title='Foo',
                                       description='Foo Item',
                                       enum=(0, 2, 4, 6))
        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is not one of', excinfo.exception.message)

    def test_integer_config(self):
        item = config.IntegerItem(title='How many dogs', description='Question')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description
            }
        )

        item = config.IntegerItem(title='How many dogs',
                                    description='Question',
                                    minimum=0,
                                    maximum=10)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum
            }
        )

        item = config.IntegerItem(title='How many dogs',
                                    description='Question',
                                    multiple_of=2)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description,
                'multipleOf': item.multiple_of
            }
        )

        item = config.IntegerItem(title='How many dogs',
                                    description='Question',
                                    minimum=0,
                                    exclusive_minimum=True,
                                    maximum=10,
                                    exclusive_maximum=True)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'exclusiveMinimum': True,
                'exclusiveMaximum': True
            }
        )

        item = config.IntegerItem(title='How many dogs',
                                    description='Question',
                                    minimum=0,
                                    maximum=10,
                                    default=0)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'default': 0
            }
        )

        item = config.IntegerItem(title='How many dogs',
                                    description='Question',
                                    minimum=0,
                                    maximum=10,
                                    default=0,
                                    enum=(0, 2, 4, 6))
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'default': 0,
                'enum': [0, 2, 4, 6]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_integer_config_validation(self):
        class TestConf(config.Schema):
            item = config.IntegerItem(title='How many dogs', description='Question')

        try:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3.1}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.IntegerItem(title='How many dogs',
                                        description='Question',
                                        multiple_of=2)

        try:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is not a multiple of', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.IntegerItem(title='Foo', description='Foo Item',
                                        minimum=1, maximum=10)

        try:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 11}, TestConf.serialize())
        self.assertIn('is greater than the maximum of', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.IntegerItem(title='Foo', description='Foo Item',
                                        minimum=10, maximum=100)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is less than the minimum of', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.IntegerItem(title='How many dogs',
                                        description='Question',
                                        minimum=0,
                                        exclusive_minimum=True,
                                        maximum=10,
                                        exclusive_maximum=True)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 0}, TestConf.serialize())
        self.assertIn('is less than or equal to the minimum of', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 10}, TestConf.serialize())
        self.assertIn('is greater than or equal to the maximum of', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.IntegerItem(title='Foo',
                                        description='Foo Item',
                                        enum=(0, 2, 4, 6))

        try:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(config.Schema):
            item = config.IntegerItem(title='Foo',
                                        description='Foo Item',
                                        enum=(0, 2, 4, 6))
        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is not one of', excinfo.exception.message)

    def test_array_config(self):
        string_item = config.StringItem(title='Dog Name',
                                          description='The dog name')
        item = config.ArrayItem(title='Dog Names',
                                  description='Name your dogs',
                                  items=string_item)

        self.assertDictEqual(
            item.serialize(), {
                'type': 'array',
                'title': item.title,
                'description': item.description,
                'items': {
                    'type': 'string',
                    'title': string_item.title,
                    'description': string_item.description
                }
            }
        )

        integer_item = config.IntegerItem(title='Dog Age',
                                            description='The dog age')
        item = config.ArrayItem(title='Dog Names',
                                  description='Name your dogs',
                                  items=(string_item, integer_item))

        self.assertDictEqual(
            item.serialize(), {
                'type': 'array',
                'title': item.title,
                'description': item.description,
                'items': [
                    {
                        'type': 'string',
                        'title': string_item.title,
                        'description': string_item.description
                    },
                    {
                        'type': 'integer',
                        'title': integer_item.title,
                        'description': integer_item.description
                    }
                ]
            }
        )

        item = config.ArrayItem(title='Dog Names',
                                  description='Name your dogs',
                                  items=(config.StringItem(),
                                         config.IntegerItem()),
                                  min_items=1,
                                  max_items=3,
                                  additional_items=False,
                                  unique_items=True)

        self.assertDictEqual(
            item.serialize(), {
                'type': 'array',
                'title': item.title,
                'description': item.description,
                'minItems': item.min_items,
                'maxItems': item.max_items,
                'uniqueItems': item.unique_items,
                'additionalItems': item.additional_items,
                'items': [
                    {
                        'type': 'string',
                    },
                    {
                        'type': 'integer',
                    }
                ]
            }
        )

        class HowManyConfig(config.Schema):
            item = config.IntegerItem(title='How many dogs', description='Question')

        item = config.ArrayItem(title='Dog Names',
                                  description='Name your dogs',
                                  items=HowManyConfig())
        self.assertDictEqual(
            item.serialize(), {
                'type': 'array',
                'title': item.title,
                'description': item.description,
                'items': HowManyConfig.serialize()
            }
        )

        class AgesConfig(config.Schema):
            item = config.IntegerItem()

        item = config.ArrayItem(title='Dog Names',
                                  description='Name your dogs',
                                  items=(HowManyConfig(), AgesConfig()))
        self.assertDictEqual(
            item.serialize(), {
                'type': 'array',
                'title': item.title,
                'description': item.description,
                'items': [
                    HowManyConfig.serialize(),
                    AgesConfig.serialize()
                ]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_array_config_validation(self):
        class TestConf(config.Schema):
            item = config.ArrayItem(title='Dog Names',
                                      description='Name your dogs',
                                      items=config.StringItem())

        try:
            jsonschema.validate({'item': ['Tobias', 'Óscar']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Tobias', 'Óscar', 3]}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.ArrayItem(title='Dog Names',
                                      description='Name your dogs',
                                      items=config.StringItem(),
                                      min_items=1,
                                      max_items=2)

        try:
            jsonschema.validate({'item': ['Tobias', 'Óscar']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Tobias', 'Óscar', 'Pepe']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is too long', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': []}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is too short', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.ArrayItem(title='Dog Names',
                                      description='Name your dogs',
                                      items=config.StringItem(),
                                      uniqueItems=True)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Tobias', 'Tobias']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('has non-unique elements', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.ArrayItem(items=(config.StringItem(),
                                             config.IntegerItem()))
        try:
            jsonschema.validate({'item': ['Óscar', 4]}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Tobias', 'Óscar']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.ArrayItem(
                items=config.ArrayItem(
                    items=(config.StringItem(),
                           config.IntegerItem())
                )
            )

        try:
            jsonschema.validate({'item': [['Tobias', 8], ['Óscar', 4]]}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': [['Tobias', 8], ['Óscar', '4']]}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.ArrayItem(items=config.StringItem(enum=['Tobias', 'Óscar']))
        try:
            jsonschema.validate({'item': ['Óscar']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))
        try:
            jsonschema.validate({'item': ['Tobias']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Pepe']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not one of', excinfo.exception.message)

    def test_dict_config(self):
        item = config.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            properties={
                'sides': config.IntegerItem()
            }
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'properties': {
                    'sides': {'type': 'integer'}
                }
            }
        )

        item = config.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            properties={
                'sides': config.IntegerItem()
            },
            min_properties=1,
            max_properties=2
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'properties': {
                    'sides': {'type': 'integer'}
                },
                'minProperties': 1,
                'maxProperties': 2
            }
        )

        item = config.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            pattern_properties={
                's*': config.IntegerItem()
            },
            min_properties=1,
            max_properties=2
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'patternProperties': {
                    's*': {'type': 'integer'}
                },
                'minProperties': 1,
                'maxProperties': 2
            }
        )

        item = config.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            properties={
                'color': config.StringItem(enum=['red', 'green', 'blue'])
            },
            pattern_properties={
                's*': config.IntegerItem()
            },
            min_properties=1,
            max_properties=2
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'properties': {
                    'color': {
                        'type': 'string',
                        'enum': ['red', 'green', 'blue']
                    }
                },
                'patternProperties': {
                    's*': {'type': 'integer'}
                },
                'minProperties': 1,
                'maxProperties': 2
            }
        )

        item = config.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            properties={
                'color': config.StringItem(enum=['red', 'green', 'blue'])
            },
            pattern_properties={
                's*': config.IntegerItem()
            },
            additional_properties=True,
            min_properties=1,
            max_properties=2
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'properties': {
                    'color': {
                        'type': 'string',
                        'enum': ['red', 'green', 'blue']
                    }
                },
                'patternProperties': {
                    's*': {'type': 'integer'}
                },
                'minProperties': 1,
                'maxProperties': 2,
                'additionalProperties': True
            }
        )
        item = config.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            properties={
                'sides': config.IntegerItem()
            },
            additional_properties=config.OneOfItem(items=[config.BooleanItem(),
                                                            config.StringItem()])
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'properties': {
                    'sides': {'type': 'integer'}
                },
                'additionalProperties': {
                    'oneOf': [
                        {'type': 'boolean'},
                        {'type': 'string'}
                    ]
                }
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_dict_config_validation(self):
        class TestConf(config.Schema):
            item = config.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'sides': config.IntegerItem()
                }
            )

        try:
            jsonschema.validate({'item': {'sides': 1}}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'sides': '1'}}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'color': config.StringItem(enum=['red', 'green', 'blue'])
                },
                pattern_properties={
                    'si.*': config.IntegerItem()
                },
            )

        try:
            jsonschema.validate({'item': {'sides': 1, 'color': 'red'}}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'sides': '4', 'color': 'blue'}}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'color': config.StringItem(enum=['red', 'green', 'blue'])
                },
                pattern_properties={
                    'si.*': config.IntegerItem()
                },
                additional_properties=False
            )

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'color': 'green', 'sides': 4, 'surfaces': 4}}, TestConf.serialize())
        self.assertIn('Additional properties are not allowed', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'color': config.StringItem(enum=['red', 'green', 'blue'])
                },
                additional_properties=config.OneOfItem(items=[
                    config.BooleanItem(),
                    config.IntegerItem()

                ])
            )

        try:
            jsonschema.validate({'item': {'sides': 1,
                                          'color': 'red',
                                          'rugged_surface': False}}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'sides': '4', 'color': 'blue'}}, TestConf.serialize())
        self.assertIn('is not valid under any of the given schemas', excinfo.exception.message)

        class TestConf(config.Schema):
            item = config.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'color': config.StringItem(enum=['red', 'green', 'blue'])
                },
                additional_properties=config.OneOfItem(items=[
                    config.BooleanItem(),
                    config.IntegerItem()

                ]),
                min_properties=2,
                max_properties=3
            )

        try:
            jsonschema.validate({'item': {'color': 'red', 'sides': 1}}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': {'sides': 1, 'color': 'red', 'rugged_surface': False}}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'color': 'blue'}}, TestConf.serialize())
        self.assertIn('does not have enough properties', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'sides': 4,
                                          'color': 'blue',
                                          'rugged_surface': False,
                                          'opaque': True}}, TestConf.serialize())
        self.assertIn('has too many properties', excinfo.exception.message)

    def test_oneof_config(self):
        item = config.OneOfItem(
            items=(config.StringItem(title='Yes', enum=['yes']),
                   config.StringItem(title='No', enum=['no']))
        )
        self.assertEqual(
            item.serialize(), {
                'oneOf': [i.serialize() for i in item.items]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_oneof_config_validation(self):
        class TestConf(config.Schema):
            item = config.ArrayItem(
                title='Hungry',
                description='Are you hungry?',
                items=config.OneOfItem(
                    items=(config.StringItem(title='Yes', enum=['yes']),
                           config.StringItem(title='No', enum=['no']))
                )
            )

        try:
            jsonschema.validate({'item': ['no']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['maybe']}, TestConf.serialize())
        self.assertIn('is not valid under any of the given schemas', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

    def test_anyof_config(self):
        item = config.AnyOfItem(
            items=(config.StringItem(title='Yes', enum=['yes']),
                   config.StringItem(title='No', enum=['no']))
        )
        self.assertEqual(
            item.serialize(), {
                'anyOf': [i.serialize() for i in item.items]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_anyof_config_validation(self):
        class TestConf(config.Schema):
            item = config.ArrayItem(
                title='Hungry',
                description='Are you hungry?',
                items=config.AnyOfItem(
                    items=(config.StringItem(title='Yes', enum=['yes']),
                           config.StringItem(title='No', enum=['no']),
                           config.BooleanItem())
                )
            )

        try:
            jsonschema.validate({'item': ['no']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': ['yes']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': [True]}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': [False]}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['maybe']}, TestConf.serialize())
        self.assertIn('is not valid under any of the given schemas', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

    def test_allof_config(self):
        item = config.AllOfItem(
            items=(config.StringItem(min_length=2),
                   config.StringItem(max_length=3))
        )
        self.assertEqual(
            item.serialize(), {
                'allOf': [i.serialize() for i in item.items]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_allof_config_validation(self):
        class TestConf(config.Schema):
            item = config.ArrayItem(
                title='Hungry',
                description='Are you hungry?',
                items=config.AllOfItem(
                    items=(config.StringItem(min_length=2),
                           config.StringItem(max_length=3))
                )
            )

        try:
            jsonschema.validate({'item': ['no']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': ['yes']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['maybe']}, TestConf.serialize())
        self.assertIn('is too long', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['hmmmm']}, TestConf.serialize())
        self.assertIn('is too long', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

    def test_not_config(self):
        item = config.NotItem(item=config.BooleanItem())
        self.assertEqual(
            item.serialize(), {
                'not': item.item.serialize()
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_not_config_validation(self):
        class TestConf(config.Schema):
            item = config.ArrayItem(
                title='Hungry',
                description='Are you hungry?',
                items=config.NotItem(item=config.BooleanItem())
            )

        try:
            jsonschema.validate({'item': ['no']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': ['yes']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': [True]}, TestConf.serialize())
        self.assertIn('is not allowed for', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': [False]}, TestConf.serialize())
        self.assertIn('is not allowed for', excinfo.exception.message)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ConfigTestCase, needs_daemon=False)
